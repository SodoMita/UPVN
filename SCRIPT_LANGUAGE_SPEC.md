# Script Language Spec — UPVN `.rpy` subset (Tier 1-2)

**.rpy is parsed directly** — no YAML/JSON is the source. This mirrors Ren'Py's own `renpy/lexer.py` + `renpy/parser.py` → `renpy.ast`. Our `engine/script/lexer.py` + `parser.py` are a 500-line subset with friendlier errors.

## Files & encoding

- Extension: `.rpy` (stored under `game/` or `examples/*/script.rpy`). For future multi-file projects we'll use an explicit manifest (`project.upvn.toml` — list of files + entry label), never an implicit whole-folder scan that executes orphan `.rpyc` (see `docs/renpy_criticism.md`).
- Encoding: UTF-8, BOM (`\ufeff`) stripped.
- Comments: `#` to end of line, outside strings. Blank lines ignored.
- Case-sensitive, **spaces only** (tabs error), **4 spaces per indent level**. Parser emits `ParseError` with caret and `Hint:` if mis-indented.
- Line endings: `\n`.

## Top-level statements (indent 0)

```ebnf
file := (define | default | label)*
define := "define" ID "=" "Character" "(" char_args ")" newline
default := "default" ID "=" literal newline
label := "label" ID ":" newline block
```

`define`/`default` may appear in any order but must be top-level. Missing `label start:` is an error.

`literal` for `default`: `True` | `False` | `None` | INT | FLOAT | `"..."` | `'...'`.

Example:

```rpy
define e = Character("Eileen", color="#c8ffc8")
define s = Character(_("Sylvie"), color="#c8ffc8")
default book = False
label start:
    ...
```

## Blocks

```ebnf
block := (indent 4*N > parent) statement+
```

`parent` is enclosing indent (0 for label). Every child must be exactly `parent+4`. The parser's `group_logical_lines` preserves indent for the block parser.

## Statements inside blocks

```ebnf
statement :=
    scene | show | hide | standalone_with |
    play_music | play_sound | play_voice | stop |
    pause |
    say | narration |
    assign | if_stmt | menu | jump | call | return |
    load_stage | show3d | anim | camera_preset

scene := "scene" image_name ["with" TRANSITION]
show  := "show" image_name ["at" POSITION] ["with" TRANSITION]
hide  := "hide" TAG ["with" TRANSITION]
standalone_with := "with" TRANSITION
play_music := "play" "music" (QUOTED | WORD) ["fadein" FLOAT]
stop  := "stop" ("music"|"sound"|"voice") ["fadeout" FLOAT]
pause := "pause" FLOAT

say        := ID [ID] QUOTED   # e "hi"  / e happy "hi" (second ID ignored in Tier1)
narration  := QUOTED           # "hi"
assign     := "$" ID ("="|"+="|"-="|"*="|"/=") expr
jump       := "jump" ID
call       := "call" ID
return     := "return"
if_stmt    := "if" expr ":" newline block ("elif" expr ":" newline block)* ("else:" newline block)?
menu       := "menu:" newline (quoted_caption? choice+)
choice     := QUOTED ":" newline block
```

`image_name` is like `bg lecturehall`, `sylvie green smile` — words separated by spaces; position is suffix after ` at `.

`QUOTED` is `"..."` with `\"` escapes; `extract_quoted` via `unicode_escape`.

`expr` for `if`/`$`: Python expression evaluated in `safe_eval` with only `variables` + whitelisted builtins (`len`, `int`, …). No imports.

**Caption inside menu:** a bare `QUOTED` at `menu`+4 without `:` is treated as `caption`, not a choice. This matches *The Question*'s:

```rpy
menu:
    "As soon as she catches my eye, I decide..."
    "To ask her right away.":
        jump rightaway
```

## Example (full, parses and runs)

```rpy
define e = Character("Eileen")
default affection = 0
label start:
    scene bg classroom with fade
    show eileen neutral at center
    e "Hi. [affection] so far."
    menu:
        "Help":
            $ affection += 1
            jump good
        "Ignore":
            jump bad
label good:
    if affection >= 1:
        e "Thanks!"
    else:
        e "..."
    return
label bad:
    e "Oh."
    return
```

## What is NOT allowed (and errors)

- `python:` / `init python` / `init:` blocks → `ParseError: expected "label", "define" or "default"...` + hint `extension code lives in .py plugins`
- `image` declarations, `transform`, `screen` → postponed; will be `unknown statement` with `check spelling`
- YAML/JSON scripts → not a `.rpy`. We don't read YAML as story source (answers your question). Internal AST *is* JSON-serialisable (`{"cmd":"say",...}`) for caching/tracing, but that's build artifact, not author file.
- Orphan `.rpyc`/cache execution → never. We hash source (`VNState.script_hash`) and re-parse.

## Diagnostics (LLM-friendly)

Every `ParseError` includes:

```
file:line:col: message
    offending line text
    ^ carets
Hint: suggestion
```

Examples:

```
script.rpy:10:13: menu choice missing colon: '"Help"'
    "Help"
            ^
Hint: write: "Choice text":
```

```
script.rpy:14:9: choice body must be indented 8 spaces, got 6
    jump there
        ^
Hint: indent this line to 8 spaces (4 per level)
```

No Python traceback leaks to authors; `tools/validate.py` returns exit 0/1 and prints these.

## Compilation & caching (not required for Tier 1)

Future `project.upvn.toml`:

```toml
[project]
name = "My VN"
entry = "start"
scripts = ["game/script.rpy", "game/chapters/*.rpy"]
```

Cache (if any) goes to `.cache/upvn/script_cache.json` with `{source_hash, engine_version, ast}`. If source missing, fail loudly — no orphan execution.

## Extensions

LLM / author Python extensions register via:

```python
@upvn_command(name="inventory.add", mutates=["state.inventory"], rollback=True)
def add(ctx, item): ctx.state.variables["inventory"].append(item)
```

Used in script as a first-class command (not `$`): `inventory add "key"`. This keeps story analysable (see criticism #6).
