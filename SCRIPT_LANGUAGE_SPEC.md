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
file := (define | default | state | character | image | audio | stage | label)*
define := "define" ID "=" "Character" "(" char_args ")" newline
default := "default" ID "=" literal newline
state := "state" ":" newline (typed_var | var)* "end"?
typed_var := ID ":" TYPE ("=" literal)? newline
character := "character" ID ":" newline (name | color)* "end"?
image := "image" image_name "=" path newline
audio := "audio" ID "=" path newline
stage := "stage" ID "=" path newline
label := "label" ID ":" newline block "end"?
```

`define`/`default` may appear in any order but must be top-level. Missing `label start:` is an error.

`literal` for `default` / `state:`: `True` | `False` | `None` | INT | FLOAT | `"..."` | `'...'` | `[...]` (evaluated via `ast.literal_eval`, never code).

Example (legacy forms — still supported):

```rpy
define e = Character("Eileen", color="#c8ffc8")
define s = Character(_("Sylvie"), color="#c8ffc8")
default book = False
label start:
    ...
```

## Declarative forms (canonical — what the editor generates)

The language is **declarative**: no `python:` blocks, no `$` required. The
legacy Ren'Py-like forms above still parse (for compatibility with existing
scripts and *The Question*), but the canonical forms below are preferred.

```rpy
# assets — explicit manifest (no filename guessing)
image "bg classroom" = "backgrounds/classroom.png"
image eileen happy = "characters/eileen/happy.png"
audio theme = "music/theme.ogg"
stage classroom_3d = "stages/classroom.blend"

# characters — declarative block
character e:
    name "Eileen"
    color "#c8ffc8"

# typed state — declared, saved, rollback-safe
state:
    affection: int = 0
    route: str = "none"
    has_key: bool = False
    inventory: list = []

label start:
    scene bg classroom with fade
    show eileen happy at center
    e "Hi. Affection is [affection]."

    menu:
        choice "Help Eileen":
            set affection += 1
            set route = "good"
        end
        choice "Ignore her":
            set route = "neutral"
        end
    end

    if affection >= 1:
        jump good
    else:
        jump neutral
    end
    return
end
```

Rules:

- `state:` variables become `VNState.variables` with their type in
  `VNState.declared_types`. Assigning a value of the wrong type (`set`) is a
  runtime error. Types: `int`, `float`, `str` (or `string`), `bool`, `list`.
- `set` is the canonical assignment (`$` is a legacy alias — same AST).
- `character e:` compiles to the same `characters` registry as
  `define e = Character(...)`. Properties: `name`, `color`.
- `image`/`audio`/`stage` populate `VNState.assets` (kind: `images`/`audio`/`stages`);
  `VNState.resolve_asset(kind, name)` returns the path (falls back to the name).
  Script events still carry the *declared* name, so golden traces are unchanged.
- `choice "Text":` is the declarative menu choice form; the bare `"Text":`
  form still works (including the single-caption rule).
- `end` is an **optional** explicit block terminator. It may close
  `label`, `menu`, `if`, `state`, `character`, and `choice` blocks. It must
  be dedented to the same indent as the block it closes. Indentation-only
  blocks without `end` remain valid.
- Expressions (in `if`/`elif`/`set`/`$`) are evaluated by an AST whitelist
  (`engine/script/expr_eval.py`): literals, names, arithmetic, comparisons,
  `and`/`or`/`not`, `in`/`not in`, ternary, list/tuple/dict/set literals, and
  the pure functions `len,int,float,str,bool,abs,min,max`. Attribute access,
  subscripts, comprehensions, lambdas and arbitrary calls are **errors** — no
  sandbox escape, no arbitrary Python.

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
