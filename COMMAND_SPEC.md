# Command Specification (three tiers, one IR)

Every command compiles to a typed AST node `{"cmd": ..., ... , "_loc": {file,line,col}}` (see `engine/script/ast_nodes.py`). Source `.rpy` is direct, no YAML leak — Ren'Py itself does NOT use YAML/JSON (`renpy/parser.py` → `renpy.ast`).

Three tiers share this IR: `.urpy` (fully declarative, `engine/script/urpy_parser.py`),
`.rpy` safe subset (`mode='safe'`, default), `.rpy` full (`mode='full'`, drop-in Ren'Py).

## Declarative forms (canonical, M15)

```rpy
state:                       # typed, saved variables
    affection: int = 0
character e:                 # declarative character definition
    name "Eileen"
    color "#c8ffc8"
image "bg classroom" = "backgrounds/classroom.png"
audio theme = "music/theme.ogg"
stage classroom_3d = "stages/classroom.blend"
set affection += 1           # canonical assignment ($ is a legacy alias)
menu:
    choice "Help Eileen":    # declarative choice form
        set affection += 1
    end
end                           # optional explicit block terminator
```

| Form | AST / effect | Notes |
| --- | --- | --- |
| `state:` block | `defaults` + `types` (→ `VNState.declared_types`) | types: int, float, str/string, bool, list; value must be a literal of that type |
| `character id:` block | `characters[id] = {name, color}` | same registry as `define … Character(…)` |
| `image/audio/stage name = path` | `assets[images|audio|stages][name] = path` | resolved via `VNState.resolve_asset`; events keep declared name |
| `set target op expr` | `{"cmd":"assign", ...}` | identical to `$`; type-checked against `state:` |
| `choice "Text":` | menu choice (with `id`) | bare `"Text":` still valid |
| `end` | closes label/menu/if/state/character/choice | optional; must match the block's indent |

## Dialogue

```rpy
"This is narration."
e "Hello."
e happy "Hello with expression tag (ignored in Tier1, stored)."
"Text with [variable] interpolation and {b}Bold{/b} {color=#f00}red{/color}"
```

→ `{"cmd":"say","who":null|"e","expression":null|"happy","text":"..."}`

**Bad:** `e Hello` (missing quotes) → `ParseError: unknown statement: 'e Hello'` + hint `check quotes`.

**Test:** `tests/test_say.py`

---

## Character definition

```rpy
define e = Character("Eileen", color="#aaffaa")
define s = Character(_("Sylvie"), color="#c8ffc8")  # _() translatable
```

→ `{"cmd":"define_character","id":"e","name":"Eileen","color":"#aaffaa"}` stored in `VNState.characters`. Only top-level.

**Bad:** `define e = Character` (missing parens) → hint `define e = Character("Name")`

---

## Default variable (typed, saved)

```rpy
default affection = 0
default route = "none"
default has_key = False
```

→ initial `VNState.variables`. Only literals: int, float, bool, None, "...".

**Bad:** `default affection = some_func()` → `must be a literal`

---

## Assignment

```rpy
$ affection += 1
$ route = "good"
$ has_key = True
```

→ `{"cmd":"assign","target":"affection","op":"+=","expr":"1"}` evaluated via `safe_eval` (no imports, no I/O).

No `python:` blocks. Extension code lives in `.py` plugins via `@upvn_command`.

---

## Label / Jump / Call / Return

```rpy
label start:
    "hi"
    jump somewhere
    call somewhere   # pushes return address
    return           # pops or ends game if top-level

label somewhere:
    "there."
    return
```

→ `jump` → `{"cmd":"jump","label":"somewhere"}`. Invalid target → `LabelNotFoundError`.

**Bad:** `jump somewhere:` → `ParseError: jump does not take a colon — use: jump somewhere`

---

## Menu

```rpy
menu:
    "Caption shown above choices (optional, bare quoted line)":
    "Help her":
        $ affection += 1
        jump helped
    "Leave":
        jump left
```

→ `{"cmd":"menu","caption":"...","choices":[{"text":"Help her","block":[...]},...]}`

Conditional choices (Tier 3): `"Use key" if has_key:` — not yet.

**Bad:** `menu` (no colon) → `menu needs a colon — use: menu:` ; indented wrong (not 4) → `choice must be indented 8 spaces…`

---

## Conditional

```rpy
if affection >= 3:
    jump good
elif affection >= 1:
    jump neutral
else:
    jump bad
```

→ `{"cmd":"if","branches":[{"cond":"affection >= 3","block":[...]}, {"cond":null,"block":[...]}]}`. Conditions via `safe_eval`.

---

## Scene / Show / Hide / With

```rpy
scene bg classroom
scene bg classroom with fade
scene black with dissolve
show eileen happy at left
show eileen happy at center with dissolve
hide eileen
with fade   # standalone applies to previous
```

→ `{"cmd":"scene","asset":"bg classroom","transition":"fade"}`, `{"cmd":"show","asset":"eileen happy","tag":"eileen","position":"left"}`, `{"cmd":"hide","tag":"eileen"}`. `scene` clears shown_actors (Ren'Py behavior).

---

## Audio

```rpy
play music "theme" fadein 1.0
stop music fadeout 1.0
play sound "knock.ogg"
play voice "eileen_001.ogg"
```

→ `play_music`, `stop_music`, `play_sound`, `play_voice`. Channels: music (loop), sound (one-shot), voice (per-line).

In `VNState.audio.music`.

---

## Pause

```rpy
pause 0.5
```

→ `{"cmd":"pause","duration":0.5}` wait True.

---

## 3D stubs (hybrid)

```rpy
load_stage classroom_3d
show3d eileen at marker_eileen
anim eileen wave
camera preset closeup_eileen
pause 0.5
```

→ `load_stage`, `show3d`, `anim`, `camera_preset`. Stored in `VNState.stage / stage_objects / camera`. LLM can drive these via Python (`stage_manager.py`) without DSL.

---

## Full `.rpy` tier (drop-in Ren'Py, `mode='full'`)

| Command | AST / effect | Notes |
| --- | --- | --- |
| `python:` block | `{"cmd":"python", "code":…}` | exec'd with variables + `renpy`/`store`/defines in scope; results synced back (JSON-safe only) |
| `init python:` / `init:` / `init offset = N` | `init_python` / parsed as top-level | runs once before the first label |
| `$ python_stmt` | `assign` (simple) or `python` (arbitrary) | one-line Python |
| `while cond:` / `break` / `continue` / `pass` | `while` (spliced), `break`, `continue`, `pass` | loop body re-spliced per iteration; `break`/`continue` carry the enclosing loop id |
| `label name(params):` | `label_params[name]` | params bound to variables (defaults supported), restored on `return` |
| `call label(args)` | `call` with `args` | positional args mapped to params |
| `jump/call expression expr` | `jump`/`call` with `expr` | target label computed at runtime |
| `menu:` choice `"Text" if cond:` | choice `cond` | false choices are filtered out before display |
| `window show\|hide\|auto` | `window` → `VNState.window` | |
| `nvl clear\|show\|hide`, `nvl mode nvl\|adv` | `nvl`, `nvl_mode` → `VNState.nvl(_mode)` | |
| `voice "…"` | `play_voice` | |
| `queue music\|sound "…"` | `play_music`/`play_sound` with `queue: true` | |
| `show/hide/call screen x` | `show_screen`/`hide_screen`/`call_screen` | `call_screen` waits for input |
| `screen:` / `style:` / `transform:` / `translate:` | `screens`/`styles`/`transforms`/`translations` | captured as raw lines for the editor-built UI layer |
| `renpy.jump/call/quit`, `renpy.loadable`, `renpy.has_label`, `renpy.get_playing`, `renpy.random.*`, `renpy.store.*` | `engine/script/renpy_compat.py` | allowlist stand-in object, not a real import |

In safe mode all of the above raise `ParseError` with hint `parse with mode='full'`.

## What is NOT in the declarative tiers (tiers 1–2)

- ATL (`transform`, `at`, `parallel`), `screen` language, `translate`, `init python`, `call screen`, `image` declaration, `layeredimage`, video — all explicit anti-goals in `docs/renpy_criticism.md`; they exist only in the full tier and are captured (not auto-rendered).

Every command entry follows: **Good / Bad / Error / Test / Migration note**.
