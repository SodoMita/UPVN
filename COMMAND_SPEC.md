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
| `screen:` / `style:` / `transform:` / `translate:` | `screens`/`styles`/`transforms`/`translations` | captured with relative indents + params; `screen:` bodies are then **evaluated** into widget trees (see M22) |
| `renpy.jump/call/quit`, `renpy.loadable`, `renpy.has_label`, `renpy.get_playing`, `renpy.random.*`, `renpy.store.*` | `engine/script/renpy_compat.py` | allowlist stand-in object, not a real import |

### M20 additions (driven by a real 61-file Ren'Py game)

| Command | AST / effect | Notes |
| --- | --- | --- |
| `call/jump label from _id` and bare `from _id` | `call`/`jump` with `from_id`, `from_clause` | Ren'Py inserts these for save compatibility; recorded in `from_clauses`, no-ops at runtime |
| `call screen f(a, b) with t` | `call_screen` with `args`, `transition` | same for `show screen f(args)` / `hide screen f` |
| `for x in items:` (and `for k, v in pairs:`) | `for` (spliced per item) | `break`/`continue` work exactly like `while` |
| `who @ attr "text"` | `say` with `voice_attr` | Ren'Py 7.4+ voice attributes |
| `who happy -sweat "text"` | `say` with `expression="-sweat"` | negated image attributes |
| `who "text" nointeract` | `say` with `nointeract` → `wait: false` | does not wait for a click |
| `extend "more"` / `centered "t"` / `vcentered "t"` | `say` with `extend` / `centered` | |
| `with Dissolve(0.5)` / `with None` | `with` with any expression | also on `scene`/`show`/`hide` |
| `show img as tag at a, b behind x zorder 2 onlayer master` | `show` with `as_tag`/`position`/`behind`/`zorder`/`layer` | clauses recognised in any order, never inside dialogue text |
| `pause` / `pause delay` / `pause 1.0 with fade` | `pause` with float or expression | expression evaluated at runtime |
| `play/queue/stop music\|sound\|voice\|audio …` | `play_*`/`stop_*` | playlists, `fadein`/`fadeout`/`loop`/`noloop`/`with` |
| `voice sustain` | `voice_sustain` | |
| `menu name:` + `set var` inside it | `menu` with `name`/`set`; name registered as a **label** | Ren'Py lets you `jump`/`call` a named menu |
| `if`/`elif`/`else` inside `menu:` | choices inherit `cond` (`(a)`, `not (a) and (b)`) | |
| dialogue / `$` / `set` / `python:` before the choices | `menu.pre` (spliced in front of the menu) | |
| `"Text" (icon="x") if cond:` | choice text + `choice_props` + `cond` | caption parsed first, so `if` inside the text stays text |
| `default x = expr()` / `default a.b = 1` / `default` inside a label | deferred to `init_python` / dotted define / collected | Ren'Py collects `default` wherever it appears |
| `define gui.x = …`, `define config.y = …` | store **namespaces** (`interp.namespaces`) | unknown members are permissive no-ops (`gui.init(1920, 1080)`) |
| `image n = <expr>`, `layeredimage n:` block | `assets.images` / `image_blocks` | non-string RHS kept verbatim |
| `style x.y = v`, `style x prop v`, `style n is p:` | `styles` | both `style x.y` and `style.x.y` forms |
| `screen f(a) tag t modal m zorder z:`, `transform f(a):` | `screens` / `transforms` | parameters and trailing keywords accepted |
| `init python hide:` / `python early:` / `init python in mod:` | `init_python` | |
| `label n(p) hide:` | `label_params` | |
| multi-line `define`, triple-quoted text, `\` and bracket continuation | lexer | `call screen f(\n … )` joins into one logical line |
| `_( )` / `_p( )` | identity translation helper | UPVN has no catalogue |

**Loose expressions (full tier only).** Unknown names/attributes/functions evaluate
to `None` (recorded in `ExpressionEvaluator.missing`) instead of aborting, comparisons
with `None` degrade to `False`, keyword arguments and comprehensions are allowed.
Dunder access stays blocked in **both** modes. Safe/.urpy tiers are unchanged (strict).

**Compat mode.** `VNController(..., mode="full", compat=True)` collects failing
`init python:` / `python:` blocks into `interp.init_errors` / `interp.python_errors`
and keeps playing, and unknown globals in `python:` blocks resolve to recorded no-ops
(`PermissiveEnv`). Default (`compat=False`) still raises.

In safe mode all of the above raise `ParseError` with hint `parse with mode='full'`.

### M21 additions (driven by the Ren'Py SDK's own games)

| Command | AST / effect | Notes |
| --- | --- | --- |
| a keyword from `renpy.register_statement("NAME", …)` | `custom_statement` (no-op event) | discovery is **project-wide** — a registration in one file makes `NAME` legal in every file; the body is captured, never executed |
| … registered with `block="script"` | body parsed as script | labels inside become real jump targets (`label play_pong:` in the SDK tutorial); an unreadable body lands in `custom_statement_errors`, not an exception |
| `testcase n:` / `testsuite n:` | `custom_statement` | Ren'Py's own test DSL (`renpy/parser.py:1230/1239`) — recognised without any registration |
| `e "one` ⏎ `   two."` | one `say` | Ren'Py lexes strings with `re.DOTALL`, so a plain quote may close on a later line; unterminated → friendly error naming the delimiter |
| `e "text" id a1b2c3d4` | `say` with `id` | the automatic dialogue IDs Ren'Py's translation tooling writes into every shipped game |
| `"Lucy" "text"` | `say` with `who="Lucy"` | the who is an expression, so a bare string literal is a dynamic name |
| `show pos:` + indented ATL / `scene bg:` + ATL | `show`/`scene` with `atl` (raw lines) | captured, not animated |
| `scene` (no target) | `scene` with empty asset | clears the layer — `ast.Scene(loc, None, layer)` |
| `define x += [ … ]` | `defines` | augmented form |
| `style n:` inside a label | `styles` | `style` is legal as a statement, not only at top level |
| `window show\|hide\|auto [t]`, `nvl show\|hide\|clear [t]` | `window`/`nvl` with `transition` | the transition is optional |
| a file holding only comments | empty IR | legal in a multi-file project; a single-file script still needs `label start:` |

### M22 additions (screens render)

| Construct | Effect | Notes |
| --- | --- | --- |
| `screen n(params):` body | evaluated by `engine/ui/screen_lang.py` into a JSON widget tree | containers `vbox`/`hbox`/`frame`/`window`/`fixed`/`null`/`bar`; leaves `text`/`textbutton`/`imagebutton`/`add`/`label`/`input`/`key` |
| `if` / `elif` / `else` in a screen | branch chosen against the store | an unresolvable condition is a diagnostic, not an exception |
| `for x in items:` | one copy of the body per item | a non-iterable is a diagnostic |
| `$ expr` in a screen | executed against the store | feeds `[expr]` in the same screen |
| `default x = e` | screen-local binding | applied unless the caller passed the name |
| `use other(args):` | inlines another screen | `transclude` inside it receives the `use` body |
| `has vbox` | the following siblings become that container's children | a declaration, not a block — the container is synthesised |
| `text "Hi [name]"` | `[expr]` interpolated | unresolvable brackets stay verbatim |
| `show screen f(args)` | `show_screen` + `widgets`, recorded in `VNState.active_screens` | `modal: false` |
| `call screen f(args)` | `call_screen` + `widgets`, `wait: true` | `modal: true`; positional **and** keyword args bind by name |
| `hide screen f` | `hide_screen` | clears `VNState.active_screens[f]` |

Layout is intentionally **not** modelled: positions, sizes, styles and anchors
stay in each widget's `props`. A screen that cannot be resolved yields an empty
tree plus `errors`, so the story keeps playing.

## What is NOT in the declarative tiers (tiers 1–2)

- ATL (`transform`, `at`, `parallel`), `screen` language, `translate`, `init python`, `call screen`, `image` declaration, `layeredimage`, video — all explicit anti-goals in `docs/renpy_criticism.md`; they exist only in the full tier and are captured (not auto-rendered).

Every command entry follows: **Good / Bad / Error / Test / Migration note**.
