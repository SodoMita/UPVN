# Script Language Spec — UPVN script language (three tiers, one IR)

**.rpy is parsed directly** — no YAML/JSON is the source. This mirrors Ren'Py's own `renpy/lexer.py` + `renpy/parser.py` → `renpy.ast`. Our `engine/script/lexer.py` + `parser.py` are a subset with friendlier errors.

## Three language tiers (one internal IR)

All three compile to the **same IR** (`{"labels", "characters", "defaults", "types", "assets", …}`), so the interpreter and the whole engine treat them identically.

| Tier | File | Parser | Embedded Python | Use |
|------|------|--------|-----------------|-----|
| 1 — `.urpy` declarative | `.urpy` | `engine/script/urpy_parser.py` | **none** (no `$`, `define`, `default`, `python:`/`init`) | strict, analyzable, editor-authored |
| 2 — `.rpy` safe subset | `.rpy` | `parser.parse(mode='safe')` (default) | none — full-tier constructs are rejected with guidance | declarative Ren'Py-like scripts |
| 3 — `.rpy` full | `.rpy` | `parser.parse(mode='full')` / `parse_string_full` | **yes** — `python:`/`init`, `while`, `$`, `renpy.*` compat | drop-in Ren'Py replacement |

Tier 3 additionally populates `label_params`, `defines`, `init_python`, `transforms`, `screens`, `styles`, `translations`, and sets `"full": true` in the IR. Tier 1 sets `"language": "urpy"`.

`VNController(script_path, mode="safe"|"full")`; `tools/run_headless.py` / `tools/validate.py` accept `--mode safe|full`. `.urpy` files are auto-dispatched by extension.

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

In **tiers 1–2** (`.urpy` and `.rpy` safe):

- `python:` / `init python` / `init:` blocks → `ParseError` + hint `parse with mode='full'`
- `while`/`break`/`continue`/`pass`, `window`, `nvl`, `voice`, `queue`, `jump/call expression`, `call label(args)`, label parameters, `show/hide/call screen`, arbitrary `define`, `transform`, `screen`, `style`, `translate` → same guidance
- In `.urpy`, additionally: `$`, `define`, `default` are rejected with targeted hints (`use set`, `use a character block`, `declare in a state: block`), and every block requires an explicit `end`.

Always (all tiers):

- YAML/JSON scripts → not a `.rpy`. We don't read YAML as story source (answers your question). Internal AST *is* JSON-serialisable (`{"cmd":"say",...}`) for caching/tracing, but that's build artifact, not author file.
- Orphan `.rpyc`/cache execution → never. We hash source (`VNState.script_hash`) and re-parse.

## Full `.rpy` tier (drop-in Ren'Py)

With `mode='full'` the parser accepts the Ren'Py constructs above and passes them to
the interpreter:

- `python:` blocks — executed with the variables dict, `renpy`, `store`, and `define`s in scope; results are copied back into the saveable state (only JSON-friendly values).
- `init python:` / `init:` / `init offset = N` — run once before the first label.
- `$ expr` — one-line Python (plain assignments still become `assign` nodes).
- `while cond:` / `break` / `continue` / `pass` — full control flow.
- `label name(params):` + `call label(args)` — parameters bound into variables (defaults supported); restored on `return`.
- `jump expression expr` / `call expression expr` — computed targets.
- `menu:` choices with `"Text" if cond:` — conditions evaluated; false choices are hidden.
- `window show|hide|auto`, `nvl clear|show|hide`, `nvl mode nvl|adv`, `voice "…"`, `queue music|sound …`.
- `show screen x` / `hide screen x` / `call screen x` + `screen:` / `style:` / `transform:` / `translate:` blocks (captured into `screens`/`styles`/`transforms`/`translations` for the editor-built UI layer).
- `renpy.*` compat namespace (`engine/script/renpy_compat.py`): `renpy.jump`/`call`/`quit`, `renpy.loadable`, `renpy.has_label`, `renpy.get_playing`, `renpy.random.*`, `renpy.store.*` — a small allowlist object, not a real import (dunder attributes blocked).

The **expression sandbox** still applies to story expressions, but in full mode attribute
access is permitted *only* on the injected `renpy`/`store` objects (never `_`-prefixed,
never on arbitrary values) — so `renpy.loadable("…")` works while
`().__class__.__mro__…` escapes stay closed.

### M20 — what the drop-in tier now accepts (verified on a real game)

The full tier is no longer a demo subset: it parses a complete shipped game
(freeCodeCamp/LearnToCodeRPG, BSD-3-Clause, 61 files, 5.5k statements) with zero
errors. Beyond the list above it accepts:

- **Lexical:** triple-quoted strings across lines, trailing-`\` continuation, and
  *unbalanced-bracket* continuation (`call screen f(` … `)`), BOM anywhere,
  `#` only outside strings.
- **Statements:** `from` clauses, `call screen f(args) with t`, `show/hide screen f(args)`,
  `for` loops (incl. tuple targets), voice attributes (`who @ attr "text"`), negated
  image attributes (`who -sweat "text"`), `nointeract`, `extend`, `centered`/`vcentered`,
  `with <any expression>`, `show` clauses in any order (`as`/`at`/`behind`/`zorder`/`onlayer`),
  `pause` with an expression, playlists + `loop`/`noloop`/`fadeout`, `voice sustain`,
  `stop audio`.
- **Menus:** `menu name:` (also a jump/call target), `set var`, `if`/`elif`/`else`
  choice groups, dialogue/`$`/`python:` before the choices, `"Text" (props) if cond:`.
- **Top level:** `default` with an expression / dotted name / inside a label,
  dotted `define` (store namespaces `gui`/`config`/`build`), `image … = <expr>`,
  `layeredimage:` blocks, style property statements, `screen`/`transform` with
  parameters, `init python hide:` / `python early:`.
- **Indentation:** the safe/.urpy tiers still demand exactly 4 spaces; the drop-in
  tier accepts any *consistent* indent (real projects use 2, 4 or 8).
- **Multi-file:** each file is parsed on its own (`require_start=False`) and merged,
  so errors keep their real `file:line` and `start` may live in any file.

Run `python -m tools.check_renpy_project <project> --run` for a full report.

### M21 — verified against a second corpus (the Ren'Py SDK's own games)

One game proves the parser can read that game. So the tier was re-validated
against the games that ship inside `renpy/renpy` itself (MIT) — `tutorial/`
(23 scripts) and `the_question/` — written by different people in a different
style. Result: **23/23** files, 75 labels, every jump/call resolves. Beyond M20:

- **Custom statements.** Ren'Py lets a project define its own keywords with
  `renpy.register_statement("NAME", parse=…, execute=…)`. Registration is
  project-wide, so discovery is too: `discover_custom_statements()` scans every
  file first and the resulting map is passed to each `Parser` (the checker,
  `tools/validate.py` and `VNController` all do this). UPVN **captures** these
  bodies and never executes the foreign callback; at runtime the node is a
  no-op event. `testcase`/`testsuite` are built into Ren'Py and need no
  registration.
- **`block="script"`.** That argument tells Ren'Py the body *is* script, so
  UPVN parses it as such — labels declared inside become real jump targets (the
  tutorial hides `label play_pong:` inside an `example` block). A body we
  cannot read is recorded in `custom_statement_errors` rather than aborting the
  file; our own `init:` errors stay hard.
- **Strings may span lines.** Ren'Py lexes string literals with `re.DOTALL`
  (`renpy/lexer.py`), so `e "one` ⏎ `   two."` is one string. An unterminated
  quote now reports `unterminated string` with the delimiter named.
- **Say:** Ren'Py's automatic dialogue IDs (`e "text" id a1b2c3d4`, written by
  the translation tooling) and a quoted who (`"Lucy" "text"`).
- **Display:** `show`/`scene` may carry an ATL block; bare `scene` clears the
  layer.
- **Other:** `define x += [ … ]`, `style n:` as a statement inside a label,
  `window show|hide|auto [transition]`, `nvl show|hide|clear [transition]`,
  comment-only files.

Point `UPVN_RENPY_SDK` at a `renpy/renpy` checkout to run the gate:

```bash
git clone --depth 1 https://github.com/renpy/renpy ~/renpy_sdk
UPVN_RENPY_SDK=~/renpy_sdk pytest tests/test_renpy_sdk_corpus.py
```

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
