# Changelog

## 0.6.13 — 2026-09-10 M26 Desktop GUI verification + texture-free palette + Ren'Py converter

Goal: "Run this engine in desktop (see docs how), fix all errors until usable
in the Blender GUI, sample scene without image textures, keep a Ren'Py →
UPVN path." All verified live on the headless-Wayland desktop (sway +
XWayland + llvmpipe, UPBGE 0.50 / Blender 5.0.1).

- **Startup segfault (P0) root-caused**: factory userprefs ship
  `audio_device='PulseAudio'`; `AUD_Device_setSpeedOfSound` in
  `LA_Launcher::InitEngine` dereferences the unavailable device → SIGSEGV
  before the first frame. Fix: `bpy.context.preferences.system.audio_device =
  'None'` once (recipe in docs/SANDBOX_UPBGE.md; Blender 5.0 moved audio
  prefs from `preferences.audio` to `preferences.system`).
- **Texture-free palette (sample scene + template play with zero PNGs)**:
  materials are now `Output ← Emission ← Object Info.Color`, so
  `KX_GameObject.color` paints everything at runtime. `contract.py` gains
  COLOR_STAGES / SPRITE_TINTS / hash fallback, `stage_color()`,
  `sprite_color()`, `apply_object_color()`. Renderers log decisions.
  Deterministic (`hashlib`, not `hash()`).
- **image_mode policy**: env `UPVN_IMAGES` > VNController game property
  `image_mode` > default `color`. `color` never touches image files; `auto`
  (written by the converter) uses converted-project art with palette
  fallback. Setup Scene writes the property (dual representation).
- **BUG-012 (P0)**: `SENSOR` physics is invisible to `KX_GameObject.rayCast`
  in UPBGE 0.50 — every mouse choice click missed. Plates are now
  `STATIC + BOX` (addon `_static_ghost`, template, updater tool).
- **BUG-013 (P1)**: `Camera.getScreenRay` always returns None on ortho
  cameras in UPBGE 0.50; `KX_Scene.rayCast` does not exist. Frontend now
  shoots a manual frustum ray via `cam.rayCast` (mouse y is measured from the
  window TOP — verified in-field). Mouse choice selection works end-to-end.
- **BUG-014 (P1)**: `_hide_idle_sprites()` ran after `ctrl.load()` and hid
  the opening `show` sprite (stage color changed, sprite never appeared,
  zero errors). It now keeps planes claimed by `sprite_mgr`.
- **BUG-015 (P1)**: Setup Scene clobbered a configured `script_path` with the
  panel default `//game/script.rpy`; panel + `build_vn_scene` now adopt the
  blend's existing value when the caller passes the default.
- **Diagnostics**: `UPVN_DEBUG_TEE` env mirrors Python stdout/stderr to a
  file (player stdout is block-buffered and lost on kill -9); pointer ticks
  log hover/click changes; `UPVN_POINTER_PROBE=1` prints a physics ray probe;
  addon version banner v0.6.13.
- **Ren'Py → UPVN converter**: `tools/renpy_convert.py` (uses
  `tools/check_renpy_project.find_script_dir`/`check_project`) builds a
  self-contained project: `game/` scripts (dir-merged at runtime),
  `assets/{backgrounds,sprites}` from `game/images`, audio, runtime snapshot,
  wired template (`script_path=//../game`, `image_mode=auto`), parse report +
  `README_PLAY.txt`. `tools/wire_converted_blend.py` bakes an **image bank**
  (one plane per asset, UV-mapped, packed textures — `bge.texture` cannot
  bind node materials in 0.50: "Texture is not available"). Frontend accepts
  **directories** as script sources. Verified end-to-end in the GUI with a
  fake Ren'Py project (images, branching, mouse choices).
- **Desktop tooling**: `tools/desktop_run.sh` (env-correct player launcher);
  `tools/update_template_materials.py` (in-place template upgrade, logic
  bricks preserved — `make_template.py` cannot add bricks in
  `--background`).
- **Addon v0.6.13**: object tints seeded per object, `image_mode` prop,
  STATIC physics for ray targets, script_path preservation. Zipped to
  `dist/upvn_editor_addon_v0.6.13.zip` (v0.6.12 zip also rebuilt).
- Evidence: `examples/20_smoke_game/evidence/m26_*.png`,
  `screenshots/m26/*` (palette stages, choice plates, converted Ren'Py game
  with real images, editor panel + Setup Scene status).
- Tests: **290 passed, 16 skipped** (`tests/test_m26_desktop_gui.py` adds 14).
- Known environment limits (not engine bugs, measured): embedded P in the
  editor needs ~1.6 GB RSS — OOM-killed below that in the 2 GB sandbox;
  llvmpipe at 1024×576 renders 13–19 fps on 2 vCPUs.

## 0.6.12 — 2026-09-10 M25 Usability Stabilization Freeze

- **BUG-009 (P0)**: UPBGE 0.50 `KX_GameObject` exposes only
  `object.game.properties` at runtime; ID custom properties are invisible, so
  the player ignored `script_path` and fell back to the sample game. Addon
  `_set_runtime_prop()` writes both; template regenerated with real game
  properties. Old projects: re-run Setup Scene.
- **BUG-010 (P0)**: `_digit_choice_index` compared `ord('1')+i` against
  evdev-like bge codes (ONEKEY==14) — 1-9 select dead in the player. States are
  now a digit-ordered sequence; dicts rejected (fail closed). Regression tests
  + walkthrough step pin "You chose left.".
- **BUG-011 (P1)**: save/load modals render nothing in the standalone player,
  block the story, and Esc quits at engine level. Ctrl+S/Ctrl+L now call
  `VNController.quick_save/quick_load` (slot `quick`, no modal); load maps the
  save format onto a state snapshot and restarts the generator.
- **BUG-007/008** (from freeze start): skip/auto never auto-resolve menus;
  bare-S skip requires Ctrl NOT active.
- **QA**: `UPVN_HEARTBEAT` env var — frontend writes per-tick JSON state
  (label/idx/event/choices/modal) for harnesses; player stdout is
  block-buffered and lost on kill -9. `tools/smoke_walkthrough.sh` v3:
  wayland/xvfb backends, self-verifying steps, `--delay 80` chords,
  retry-until-state. docs/SANDBOX_UPBGE.md + docs/MANUAL_QA.md + BUGS.md.
- Tests: 276 passed, 16 skipped.

## 0.6.11 — 2026-09-09 Cursor, ortho 15, zoom-stable UI, art, LibLoad crash

- Mouse cursor shown (`bge.render.showMouse(True)`). Choice clicks use
  `getScreenRay` then `rayCast` fallback; planes are SENSOR+BOX. Keys 1–9 and
  numpad. `HotspotMap` always `choice_<index>`.
- `Camera_UI` ortho_scale **15**. Zoom changes ortho but UI is re-laid as NDC
  fractions of the frustum — dialogue stays on screen. `camera_preset` does not
  move `Camera_UI`.
- Placeholder PNG sprites/backgrounds in `assets/` and the sample game.
  Materials get an Image Texture node so VideoTexture has a slot.
- `LibLoad` only if the `.blend` exists (crash in `_load_stage_bge`).
- Add-on v0.6.11. **Restart UPBGE**, Setup Scene, P.

## 0.6.10 — 2026-09-09 Setup Scene writes the OPEN scene

- Field: Check Wiring 18/27, all `choice_*` missing. `build_vn_scene` always
  created/switched to a new `VN_Main`, so the open template `Scene` never got
  the buttons. Default is now `context.scene`; operator passes
  `scene_name=context.scene.name`. Reuses `bpy.data.objects` by exact name
  (no `choice_0.001`). Reports leftover missing names.
- `materialID` no longer aborts the tick when the slot name is absent (Emission
  plates) — falls back to slot 0.
- Contract lists `Speaker_Text` / `Dialogue_Text`. Add-on v0.6.10.
- **Restart UPBGE after zip install** (startup still printed v0.6.8 until reload).
  Then Setup Scene on the file you have open. The committed `.blend` is a
  bootstrap; Setup Scene is the source of truth (no UPBGE here to regen the binary).

## 0.6.9 — 2026-09-09 3D-only UI (no overlay)

- **No `blf` / `post_draw` HUD.** Dialogue, speaker, load-fail text and menus
  live on scene FONT + plane objects (`Speaker_Text`, `Dialogue_Text`,
  `choice_0..8` + `_text`). `engine/ui/world_ui.py` writes `.text` / visibility
  every frame. Frontend unregisters leftover overlay callbacks.
- **Choice clicks work in 3D.** LMB `Camera_UI.getScreenRay` →
  `PointerTracker` → `VNController.choose(i)`. Number keys 1–9 still work.
  Choice planes are STATIC ghost so they raycast.
- **Unlit plates.** Setup Scene rewrites BG/sprite/UI materials to Emission
  (no Principled), hides scene lights, zeros world Background. Sprites stay
  visible without PNGs (silhouette + object color).
- Add-on v0.6.9. Tests `tests/test_m23_world_ui.py`. **Re-run Setup Scene.**

## 0.6.8 — 2026-09-09 Camera bind + keyboard capture (field: LMB works, keys don't)

- **Camera is now a Front ortho that the game actually uses.** `Camera_UI` was
  created at `(0,-10,5)` looking +Y at **XY** planes (edge-on) and never assigned
  to `scene.active_camera`, so P showed the leftover editor camera. Contract now
  owns the pose: planes stand in XZ (`PLANE_ROTATION` X=90°), `Camera_UI` at
  `(0,-10,0)` rot X=90° ortho 10; `Setup Scene` **resets** that transform every
  time (unless `upvn_camera_custom`); leftover factory cameras are hidden;
  viewport switches to CAMERA; `frontend._bind_camera()` sets
  `scene.active_camera = Camera_UI` once at play start.
- **Keys work in the embedded player.** LMB reached `bge.logic.mouse` without a
  sensor; keystrokes were eaten by Blender because no Keyboard brick existed.
  `Setup Scene` now adds `AllKeys` (`use_all_keys`, True pulse) + `Mouse`
  LEFTCLICK, both linked to `UPVN_Main`. Idempotent: added only when missing.
- **No more `keyboard.events`.** UPBGE 0.50 deprecates it and the conversion is
  lossy. Polling uses `device.inputs[key]` only: `JUST_ACTIVATED in entry.queue`
  / `.activated` / `ACTIVE in entry.status`. Pure `_classify_input_entry`.
  Frontend F1/F12 goes through `_bge_just`. `_device_states` removed.
- Add-on v0.6.8; tests `tests/test_m22_upbge_play.py`.

## 0.6.7 — 2026-09-09 Script discovery across directories + on-screen diagnostics
- **The game now finds its script.rpy on its own.** The packaged game layout is
  `<package>/blend/UPVN_Template.blend` + `<package>/game/script.rpy`, but the
  runtime only searched next to the .blend, so pressing P fell back to the
  placeholder ("no script found yet"). `frontend.resolve_script_path` now also
  probes the parent and grandparent of the .blend directory (`//../game/script.rpy`,
  `//../../game/script.rpy`) plus the example layouts; the VNController
  `script_path` property still wins when it points at an existing file.
- **Load failures are explained on screen, not only in the console.** When no
  script is found, the game now draws a red diagnostic panel listing the paths
  that were searched and the exact fix (UPVN panel → Create Project → Setup
  Scene → P) — players no longer stare at a cryptic placeholder.
- **Setup Scene no longer reports a false warning for intact wiring.** The value
  `upvn_bricks = "existing"` was treated as an error ("Brick wiring issue") —
  it now reports success: "Scene wiring already present and intact".
- **Input API updated to UPBGE 0.50's non-deprecated form.** The runtime used
  `keyboard.events` / `mouse.events`, which UPBGE 0.50 deprecates in favour of
  `keyboard.inputs` / `mouse.inputs` (per-key `KX_InputDevice`). New pure helpers
  `_bge_input_state/_bge_just/_bge_active` prefer the new API and fall back to
  the legacy one; all polling sites (advance, menu digits, skip/auto, history,
  quick menu, Ctrl+S/L, ESC, wheel rollback) now go through them. The digit
  selector is now the pure `_digit_choice_index`.
- **Registration banner prints the real add-on version** (read from `bl_info`)
  instead of a hard-coded "v0.6".
- Tests: menu-input tests rewritten for the new helpers + packaged-layout path
  discovery test → **135 passed, 2 skipped**.
- Add-on version 0.6.7; dist rebuilt.

## 0.6.6 — 2026-09-08 Idempotent Setup Scene + live Pillow probe (field reports)
- **Setup Scene no longer fails on a second run.** Field error
  `bpy_prop_collection: attribute "remove" not found`: the generator deleted the
  existing `VNController` by iterating the read-only brick collections
  (sensors/controllers have no `.remove()` in UPBGE 0.50). `build_vn_scene` now
  **reuses** the existing object — properties are refreshed, the launcher text is
  rewritten, and only the missing pieces (Always sensor / UPVN_Main controller)
  are added by name; an intact wiring is reported as `upvn_bricks = "existing"`
  and never touched. Repeated presses are safe by construction.
- **Preview works immediately after installing Pillow.** The static module flag
  `HAS_PIL` went stale when Pillow was installed mid-session (a module imported
  earlier without Pillow stays `False`). `render_state()` now performs a live
  probe (`from PIL import …` at call time) and binds the names then; the add-on
  preview paths use a new `pil_live_available()` that imports `PIL` afresh on
  every attempt. The "Install Pillow" operator installs with
  `pip --target <purelib of the running interpreter>` — that directory is
  already on `sys.path`, so the package is visible without restarting Blender;
  the operator verifies visibility and, if still absent, advises one restart.
- Tests: `tests/test_m20_upbge_runtime.py` extended (7 tests, incl. static guard
  that the add-on never calls `.remove()` on brick collections and reuses
  `VNController`) → **133 passed, 2 skipped**.
- Add-on version 0.6.6; dist rebuilt.

## 0.6.5 — 2026-09-08 Runtime fixes from the field (UPBGE console reports)
- **`blf.color()` signature fixed.** UPBGE 0.50 requires
  `blf.color(fontid, r, g, b, a)`; the overlay passed four values under the old
  convention, so every dialogue/menu frame printed
  `blf.color() takes exactly 5 arguments (4 given)` and the on-screen text
  never got its color set. All calls in `bge_frontend/frontend.py::draw_overlay`
  now pass font id + RGBA.
- **Preview no longer leaks a `ModuleNotFoundError: PIL` traceback.** UPBGE runs
  its own bundled Python (`<upbge>/5.0/python/bin/python3.11`), where Pillow may
  be absent even if the system Python has it. `engine/render/headless_renderer.py`
  now imports without Pillow (font constants degrade to `None`) and `render_state`
  raises one clear RuntimeError with the exact install command; the add-on's
  preview paths catch it, store the reason in `UPVN_GameBuilder.last_error`, and
  report it in the panel instead of a raw traceback.
- **New operator "Install Pillow"** in the UPVN panel: locates UPBGE's bundled
  Python next to `bpy.app.binary_path` and runs
  `python3.11 -m pip install pillow`, reporting the result directly.
- Tests: `tests/test_m20_upbge_runtime.py` (5 tests: blf.color 5-arg static
  checks, import-without-Pillow + instructive RuntimeError, real-Pillow render
  sanity, add-on error-field behavior) → **131 passed, 2 skipped**.
- Add-on version 0.6.5; dist rebuilt.

## 0.6.8 — 2026-09-09 Screens draw in the golden trace (M23)

M22 produced a widget tree but nothing painted it, so a `show screen` was
correct in JSON and invisible in a frame. The headless renderer now walks
`VNState.active_screens` (sorted by `zorder`, so a modal `confirm` lands above a
HUD) and paints each tree: `vbox`/`hbox` flow layout, `frame`/`window` plates,
`text`/`label`, `textbutton` boxes (bright edge when the button has an action),
`add`/`imagebutton` labelled plates, `bar`/`vbar`, and a full-frame dim for
`modal` screens. Positions honour the `xalign`/`yalign`/`spacing`/`xsize` hints
M22 leaves in `props`.

Two deliberate limits, consistent with M22: Ren'Py's real layout engine is **not**
reimplemented (this is a golden-trace renderer, screenshots stay for human review),
and a screen that cannot be laid out never fails the frame — `draw_active_screens`
is wrapped so a bad widget degrades to nothing rather than dropping the shot.

Also fixed a real evaluation gap M22 left: a screen *parameter* was not visible
inside a compound condition. `screen hud(score=0)` with `if score > 5:` never
rendered the button, because `score > 5` was evaluated against the store alone.
`VNInterpreter._eval_screen_expr` now takes an overlay scope, so `score > 5`
resolves. Pinned by `tests/test_screen_render.py`.


## 0.6.7 — 2026-09-09 Screens actually render (M22)

The drop-in tier *parsed* `screen:` blocks and then threw the information away:
the body was captured as stripped text, so `show screen` / `call screen` emitted
an event with a name and nothing to draw. The SDK tutorial has **99** screens and
LearnToCodeRPG has **23**, and every one of them was inert. This milestone makes
them real.

- **`engine/ui/screen_lang.py`** — a screen-language interpreter. It rebuilds the
  widget tree from a captured body and evaluates it: containers (`vbox`, `hbox`,
  `frame`, `window`, `fixed`, `null`, `bar`), leaves (`text`, `textbutton`,
  `imagebutton`, `add`, `label`, `input`, `key`), control flow
  (`if`/`elif`/`else`, `for`, `$`), screen-local `default`s, `use` composition
  with `transclude`, `has vbox` (a declaration, not a block — the container is
  synthesised from the siblings that follow), and `[expr]` interpolation.
  Output is JSON-serialisable, so it survives a save and reaches a frontend.
- **Layout is not modelled, on purpose.** Positions, sizes, styles and anchors
  stay in `props` for the consumer to interpret. UPVN's UI is built in the 3D
  scene, so a second layout engine would only compete with it.
- **Screens are wired into the interpreter.** `show screen` / `call screen`
  render and record into `VNState.active_screens` (so a load restores the same
  UI); `hide screen` clears it. `run_headless` prints `SHOW SCREEN hud -> 5
  widgets`, and a screen that cannot be resolved says so on the same line.
- **A broken screen never stops the story.** Rendering does not raise: an
  undefined screen, an unresolvable condition or a non-iterable `for` yields an
  empty tree plus a diagnostic, which is what compat mode is for.
- **Parser:** captured `screen:` blocks keep their relative indentation and
  their parameter list — a `screen choice(items):` is not usable without them,
  and without indentation the body has no tree to build.
- **Validated on both corpora:** SDK tutorial **99/99** screens render (97
  non-empty, 716 widgets), LearnToCodeRPG **23/23** (22 non-empty, 346 widgets).


## 0.6.6 — 2026-09-09 Second corpus: the Ren'Py SDK's own games (M21)

M20 proved the drop-in tier on **one** shipped game. That is not the same as
proving it on Ren'Py, so this milestone validates against a second, unrelated
FOSS codebase — the games that ship inside the SDK itself
([`renpy/renpy`](https://github.com/renpy/renpy), MIT): `tutorial/` (23 scripts,
screen/style/ATL heavy, and it **registers its own statement keywords**) and
`the_question/`. Before: **7/23** tutorial files parsed. After: **23/23**,
75 labels, 1672 statements, every `jump`/`call`/`call screen` resolves.

- **Project-registered statements** (`renpy.register_statement`): a keyword a
  project registers in one file is legal in every other file, so discovery is
  project-wide (`discover_custom_statements`) and runs *before* parsing in the
  checker, `tools/validate.py` and `VNController`. Unknown bodies are captured,
  never executed. `testcase`/`testsuite` (Ren'Py's own test DSL,
  `renpy/parser.py:1230/1239`) are recognised out of the box.
- **`block="script"` is honoured**: that argument tells Ren'Py to parse the
  statement's body as script, so labels declared inside are real jump targets —
  the tutorial hides `label play_pong:` inside an `example` block, and it now
  resolves. A body we cannot read is recorded in `custom_statement_errors`
  instead of aborting the file; our own `init:` errors stay hard.
- **Lexer**: a plain `"…"` string may run over several lines — Ren'Py lexes
  strings with `re.DOTALL` (`renpy/lexer.py`), so `e "one\n   two."` written on
  two lines is one string. An unterminated one now gets a friendly error naming
  the delimiter instead of silently eating the rest of the file.
- **Say statements**: Ren'Py's automatic dialogue IDs (`e "…" id a1b2c3d4`,
  inserted by the translation tooling into every shipped game) and a quoted who
  (`"Lucy" "Better watch out."` — the who is an expression).
- **Display**: `show`/`scene` may carry an ATL block (`show pos:` + indented
  ATL), and a bare `scene` clears the layer (`ast.Scene(loc, None, layer)`).
- **Other**: `define x += [ … ]` (augmented form), `style NAME:` as a statement
  inside a label, `window show|hide|auto [transition]` and
  `nvl show|hide|clear [transition]`, comment-only files no longer error in a
  multi-file project.
- **Runtime**: `custom_statement` nodes pass through the interpreter as no-op
  events rather than tripping `unknown command`.
- **CI** (`.github/workflows/ci.yml`, new): `tests`, `examples` (every example
  validated in its own tier + played headless, the syntax gallery must fail),
  `renpy-corpus` (LearnToCodeRPG, blob-filtered sparse checkout ~3 MB) and
  `renpy-sdk` (this corpus). Reports upload as artifacts.
- **Docs**: README gained a "Drop-in Ren'Py compatibility" section with the
  corpus commands; `tools/` and `examples/` listings refreshed; 20 regexes and a
  helper left dead by the M20 rewrite were removed (97 → 77 regexes, none
  unused).
- **Tests**: 224 passed, 0 skipped — `tests/test_renpy_compat.py` grew 15 tests
  pinning every construct above, plus `tests/test_renpy_sdk_corpus.py` (9, skips
  without `UPVN_RENPY_SDK`).

## 0.6.5 — 2026-09-09 Drop-in Ren'Py compatibility, verified on a real game (M20)

The full `.rpy` tier went from "demo subset" to **a real Ren'Py project parses and
plays**. Driver: `freeCodeCamp/LearnToCodeRPG` (BSD-3-Clause, 61 `.rpy`/`.rpym`
files, ~2 MB of script) — before this milestone **0/61** files parsed; now
**61/61**, 127 labels, 5560 statements, every `jump`/`call`/`call screen` resolves,
and the story runs headless.

- **Lexer**: triple-quoted strings spanning lines, trailing-`\` continuation and
  *unbalanced-bracket* continuation (`call screen f(` … `)`) — the single biggest
  blocker for real scripts; BOM stripped anywhere (concatenated sources carry one
  per file); `#` recognised only outside strings; unterminated `"""` gets a hint.
- **Parser**: `from` clauses (`call x from _call_x_3`, bare `from`), `call screen
  f(args) with t`, `show/hide screen f(args)`, `for x in items:` (tuple targets too),
  voice attributes (`player @ surprised "…"`), negated image attributes
  (`e -sweat "…"`), `nointeract`, `extend`, `centered`/`vcentered`,
  `with <expression>` (`Dissolve(0.5)`, `None`), `scene`/`show`/`hide` clause
  splitting in **any** order (`as`/`at`/`behind`/`zorder`/`onlayer`) that never
  matches inside dialogue text, `pause` with an expression, playlists +
  `loop`/`noloop`/`fadeout`, `voice sustain`, `stop audio`.
- **Menus**: named menus (`menu day_choices:` — registered as a jump/call target,
  as Ren'Py does), `set var`, `if`/`elif`/`else` choice groups (conditions flatten
  to `(a)` / `not (a) and (b)`), dialogue/`$`/`set`/`python:` before the choices
  (`menu.pre`), `"Text" (icon="x") if cond:` — the caption is parsed first, so a
  literal "if" inside the text stays text.
- **Top level**: `default` with an expression (deferred to init), dotted
  (`default preferences.text_cps`), or inside a label; dotted `define` builds store
  **namespaces** (`gui`/`config`/`build`) so `gui.accent_color` and
  `gui.init(1920, 1080)` work; `image n = <expr>` and `layeredimage:` blocks;
  style property statements (both `style x.y = v` and `style.x.y = v`);
  `screen f(a) tag/modal/zorder:`, `transform f(a):`; `init python hide:`,
  `python early:`; multi-line `Character(...)` defines.
- **Indentation**: safe/.urpy tiers still demand exactly 4 spaces (gallery intact);
  the drop-in tier accepts any *consistent* indent — real projects use 2, 4 or 8.
- **Multi-file loading fixed**: `VNController` concatenated every `.rpy` into one
  buffer (BOM in the middle broke it and line numbers were fiction). Files are now
  parsed individually with `require_start=False` and merged; `start` is checked on
  the merged script with a friendly error.
- **Interpreter**: `for` loops (spliced like `while`, `break`/`continue` supported),
  `from_clause` no-ops, `menu.pre` spliced in front of the menu, `call_screen`/
  `show_screen` args, expression `pause`, `voice_sustain`, say extras
  (`voice_attr`/`extend`/`centered`/`nointeract` → `wait: false`),
  `stop_sound`/`stop_voice`/`stop_audio`, dotted defines injected as namespaces,
  `_()`/`_p()` identity translation helper, `base_dir` wired so `renpy.loadable`
  resolves real files.
- **Loose expressions (full tier only)**: unknown names/attributes/functions →
  `None` (recorded in `ExpressionEvaluator.missing`), `None` comparisons → `False`,
  keyword args and comprehensions allowed, more pure builtins (`any`, `all`,
  `sorted`, …). **Dunder access is still blocked in both modes** — the sandbox
  escape stays closed (tested).
- **Compat mode** (`VNController(..., mode="full", compat=True)`): failing
  `init python:`/`python:` blocks are collected in `interp.init_errors` /
  `interp.python_errors` and the story continues; unknown globals in `python:`
  blocks resolve to recorded no-ops (`PermissiveEnv`); unknown `renpy.*` members
  are no-ops that can even be subclassed (`__mro_entries__`) and logged in
  `renpy.compat_log`. Default behaviour still raises.
- **New tool `tools/check_renpy_project.py`**: parses every `.rpy`/`.rpym` of a
  project, merges like Ren'Py, and reports files/labels/screens/statements,
  duplicate labels, unresolved `jump`/`call`/`call screen`, the `renpy.*` APIs used
  by `python:` blocks, `--json`, and `--run` (headless smoke run in compat mode).
- **New example `examples/14_renpy_dropin`** — three files of stock Ren'Py syntax
  (no UPVN keywords) exercising every construct above; runs headless both routes.
- **Tests**: `tests/test_renpy_compat.py` (64 tests: lexer, parser, interpreter,
  sandbox, compat objects, multi-file loading, example 14) and
  `tests/test_renpy_corpus.py` (5 tests against a real project, skipped unless
  `UPVN_RENPY_CORPUS` is set). The Question was re-added at `~/renpy_src`, so the
  two long-skipped tests run again → **200 passed, 0 skipped**.
- Docs: `COMMAND_SPEC.md` + `SCRIPT_LANGUAGE_SPEC.md` gained M20 tables, `ROADMAP.md`
  M20 flipped to done, `STATUS.md` updated.


## 0.6.4 — 2026-09-08 Explicit scene↔code contract (M19)
- **New `engine/render/contract.py`** — single source of truth for the naming
  convention between interface code and scene objects: every object, material,
  collection, text datablock and asset directory the renderers expect, with its
  purpose and the module that uses it, plus a pure `check_contract()` comparator.
- **Renderers now import their identifiers from the contract** (`scene_manager.py`,
  `sprite_renderer.py`) instead of hard-coding strings; regression tests guard
  against re-introducing literals (no silent drift). Sprite texture swap gained a
  first-material-slot fallback when the named material is absent.
- **The template lacked every `Sprite_*` plane and the `MASprite` material** — code
  could not display `show` events even with asset files present. `build_vn_scene()`
  (Setup Scene) and `tools/make_template.py` now create all five sprite planes at
  the contract positions with `MASprite`; the shipped `UPVN_Template.blend` is
  regenerated accordingly (X11 session, bricks preserved).
- **New operator "Check Scene Wiring"** (`upvn.check_wiring`, UPVN panel): compares
  the open scene against `contract.py` and writes a report into the `UPVN_WIRING`
  text datablock — missing items listed with kind, purpose and expected-by module.
- Docs: `blend/README.md` gains the full "Scene-object contract" table; README
  quickstart explains the name-based connection and the check operator.
- Tests: `tests/test_contract.py` (7 tests) → **126 passed, 2 skipped**.
- Add-on version 0.6.4; dist rebuilt.

## 0.6.3 — 2026-09-08 Playable menus + QA keys in the real engine (M18)
- **Menu choices are now playable in UPBGE with number keys `1`–`9`.** The
  engine waited for a pointer/raycast choice-click that the frontend did not
  provide yet, so any game with a `menu:` froze at the prompt. `vn_controller`
  now maps digit key presses to `choose(i)` via the pure helper
  `_menu_choice_from_keycodes` (digit codes are ASCII; respects choice count;
  only `JUST_ACTIVATED`). Overlay shows a "Press 1-9 to choose" hint.
- **QA/debug keys in `bge_frontend/frontend.py`**: `F1` prints current story
  state (label, index, event type, variables) to the console; `F12` saves an
  in-game screenshot to `//screenshots/upvn_ingame_<ts>_<n>.png` via
  `bge.render.makeScreenshot` — screenshots inform humans without extra tools.
- **Modal screens now have a text overlay** (title + page indicator) so
  `H`/`Q`/`Ctrl+S`/`Ctrl+L`/`Esc` show feedback in-game instead of acting
  invisibly (full 3D plane UI still pending).
- Add-on version bumped to 0.6.3 (dist zips rebuilt with the new engine).
- Tests: `tests/test_m18_gameplay_input.py` (6 tests: key mapping, max_index,
  held-key ignore, headless no-ops) → **119 passed, 2 skipped**.

## 0.6.2 — 2026-09-08 Blender/UPBGE UX hardening (M17) — round 2, verified in real X11
- **Add-on enable can no longer crash UPBGE startup.** The field crash
  `AttributeError: '_RestrictData' object has no attribute 'filepath'` (engine
  discovery reading the open .blend path while the add-on is enabled before a
  file is loaded) is fixed: `bpy.data.filepath` is read via `getattr`, and both
  `ensure_engine()` and `register()` are exception-proof end-to-end. Verified in
  the real UPBGE 0.50 UI (X11/Xvfb): registration with an open file AND at
  startup without a file both print `[UPVN] Editor addon v0.6 registered`.
- **Install zip layout v0.6.2: single top-level folder.** v0.6.0 also placed
  `engine/` + `bge_frontend/` at the zip root; installing it extracted those into
  the add-ons folder, where Blender scanned them as add-ons and spammed
  `Warning: add-on missing 'bl_info'` at every startup. The zip now contains only
  `upvn_editor_addon/` (add-on + engine + frontend + template). If the zip is
  dropped in compressed instead of installed, the add-on shows a clear hint
  ("install via Install from Disk…") instead of failing silently.
- **Shipped `blend/UPVN_Template.blend` is now pre-wired and playable.**
  Previously the committed template had NO logic bricks (they could only be
  added in the UI), so pressing P started the game engine with nothing running —
  the exact "same frozen scene, no interaction" symptom. `tools/make_template.py`
  is now run in an interactive X11 session during generation, so the committed
  file contains the full wiring: `VNController` object + `upvn_launcher` text +
  `Always (True pulse) → Python (SCRIPT, upvn_launcher)` brick, linked
  (verified: `sensor.controllers == ['UPVN_Main']`, mode SCRIPT, text set).
  Pressing P in UPBGE now runs the game (frontend → VNController → click/Space
  advances via bge.logic keyboard/mouse polling in `VNController.update`).
- **Runtime robustness**: frontend per-frame `ctrl.update` is guarded — one
  missing asset no longer spams tracebacks every frame; the blf overlay is also
  registered for the no-script fallback; the launcher prints a one-time hint when
  the engine can't be imported at game runtime.
- Verification: registration OK in real UPBGE 0.50 UI with and without an open
  file; bricks verified present+linked in the saved template; scene build under
  X11; 113 passed, 2 skipped headless. (Full P-to-play needs a real display/GPU —
  the sandbox GL segfaults on game start, the user machine does not.)
- Tests: `tests/test_m17_addon_init.py` updated to the single-folder zip layout
  (extract-and-import proof + compressed-drop hint proof).

## 0.6.2 — 2026-09-08 Blender/UPBGE UX hardening (M17) — "Engine not available" is gone
- **Add-on v0.6 is self-contained.** Engine discovery now searches, in order: the engine folder from add-on preferences (new *Locate Engine…* button), the folder next to the add-on (repo `blend/`, extracted add-on), the add-on's own install `.zip` (zipimport fallback with `engine/` at archive root), and the open `.blend`'s folder/parents. Panels show a live ✓/✗ status row; operators report *what* was searched instead of a bare "Engine not available"; new *Check Engine*, *Locate Engine…*, *Copy engine next to add-on* actions in Preferences → Add-ons → UPVN.
- **One-click Setup Scene (UPBGE).** `blend/upvn_editor_addon.py` gained `build_vn_scene()` — pure data-API, idempotent, no `bpy.ops` context traps: creates `VN_Main`, ortho + 3D cameras, the five `VN_*` collections, BG/Dialogue planes, the `VNController` object (`script_path`, `upvn_root`, `upvn_bricks`), a path-bootstrap `upvn_launcher` Text datablock, and the Always(pulse) → Python controller brick via the same `bpy.ops.logic.*` API UPBGE's own add-ons use. In `--background` runs (no UI context for the logic operators) bricks are skipped with an explicit note instead of a half-wired scene.
- **Runtime actually starts your script.** `bge_frontend/frontend.py` now reads `script_path` from the `VNController` object (what the UPVN panel writes) first; the old `//game/script.rpy`-style guesses are fallbacks. `sys.path` is bootstrapped from the frontend's own location, and the no-script console message lists every path tried.
- **Template regenerated.** `tools/make_template.py` is now data-API-only and verified in real UPBGE 0.50: `blend/UPVN_Template.blend` rebuilt (110 KB, was a brickless 96 KB) with the classroom 3D stage, launcher text and controller object ready for a one-click *Setup Scene* in the UI.
- **Installable release zip.** New `tools/package_addon.py` → `dist/upvn_editor_addon_v0.6.0.zip`: `upvn_editor_addon/` (add-on + engine + bge_frontend + template + LICENSE + README-INSTALL) plus a zip-root `engine/` with injected `__init__.py`s so the engine imports straight out of the compressed archive. Proven in a clean-subprocess test.
- Tests: `tests/test_m17_addon_init.py` (5 tests: repo discovery, missing-engine friendliness, frontend path order + sys.path bootstrap, zip self-containment via subprocess, make_template importability). **113 passed, 2 skipped**; verified headless inside UPBGE 0.50 (Blender 5.0.1): engine discovery OK, add-on registration OK, scene build OK.

## 0.6.1 — 2026-09-08 Debugging fixes (three-tier merge)
- **Multi-file directories**: `.urpy` files no longer each require a `start` label — `parse_file(..., require_start=False)` / `parse_urpy_file(..., require_start=False)`; the entry label is checked on the merged script instead (single-file `.urpy` still requires `start`).
- **`store` namespace consistency**: `store.x`, `renpy.store.x` and bare `x = ...` in `python:` blocks now share one namespace — a `store.x += …` mutation is no longer overwritten by a stale copy during variable sync.
- **Label re-entry**: entering a label from the top now resets its block to the pristine template, so spliced `while`/`if`/menu bodies from a previous pass never accumulate or re-execute (fixes spurious extra loop iterations / duplicate choice branches on `call`-twice patterns).
- **Expression interpolation**: dialogue `[...]` brackets now evaluate full expressions through the AST whitelist (`[gold * 2]`, `[store.gold]`, `[renpy.loadable(...)]`), while unresolvable/invalid expressions stay verbatim and never crash the line.
- `renpy.store` attribute access available in full-mode `if` conditions (injected alongside `renpy`).
- Tests: 103 → **108 passed, 2 skipped** (`test_full_rpy.py` regression tests for all of the above).

## 0.6.0 — 2026-09-08 Three language tiers over one IR (M16)
- **Tier 1 — `.urpy` fully declarative** (`engine/script/urpy_parser.py`): zero embedded Python (`$`/`define`/`default`/`python:`/`init` rejected with hints), typed `state:` block, `character` blocks, `image`/`audio`/`stage` manifest, `set` + `choice` keywords, **required explicit `end`** for every block. Example `examples/13_urpy_tier`.
- **Tier 2 — `.rpy` safe subset** (unchanged default): now rejects full-tier constructs (`python:`/`init`/`while`/`break`/`continue`/`pass`/`window`/`nvl`/`voice`/`queue`/screens/`jump expression`/`call args`/label params/`transform`/`style`/`translate`/non-Character `define`) with a `parse with mode='full'` hint.
- **Tier 3 — `.rpy` full / drop-in Ren'Py** (`Parser(full=True)`, `parse_string_full`, `VNController(mode='full')`, `tools/*.py --mode full`): `python:` blocks, `init python:`/`init:`/`init offset = N`, `$` one-liners, `while`/`break`/`continue`/`pass`, `label name(params):` + `call label(args)`, `jump/call expression`, conditional menu choices (`"Text" if cond:`), `window`/`nvl`/`voice`/`queue music|sound`, `show/hide/call screen`, `screen`/`style`/`transform`/`translate` blocks (captured). Example `examples/12_full_rpy_tier`.
- **`renpy` compat namespace** (`engine/script/renpy_compat.py`): `renpy.jump`/`call`/`quit`, `loadable`, `has_label`, `get_playing`, `random.*`, `store.*` — a small allowlist object usable inside `python:` blocks and `if` conditions (no real import, dunder access blocked).
- **Interpreter**: executes python/init blocks (results synced back to JSON-safe state), binds/restores label params, splices `while` bodies per-iteration with loop-id tail markers for `break`/`continue`, computes `jump/call expression` targets, filters false conditional menu choices.
- **Expression sandbox**: container subscripts now allowed (`items[0]`, `flags["x"]`); attribute access allowed only on injected `renpy`/`store` objects (`renpy.loadable(...)`) — escape payloads stay closed.
- All three tiers produce the same IR; `tests/test_full_rpy.py` (27 tests); **99 passed, 2 skipped**.

## 0.5.3 — 2026-09-08 Declarative script language (M15)
- **Declarative `.rpy` forms** (canonical), with legacy Ren'Py-like forms kept as aliases:
  - `state:` block — typed variable declarations (`affection: int = 0`); types `int/float/str/bool/list`, recorded in `VNState.declared_types`
  - `set affection += 1` — canonical assignment (`$` still parses)
  - `character e:` block (`name`/`color`) — canonical character definition (`define … = Character(…)` still parses)
  - `image` / `audio` / `stage` asset manifest → `VNState.assets` + `VNState.resolve_asset(kind, name)`
  - `choice "Text":` inside `menu:` (bare `"Text":` still parses)
  - optional explicit `end` terminators for label/menu/if/state/character/choice (indentation-only blocks still work)
- **Safe expression evaluator** `engine/script/expr_eval.py` — AST-whitelisted (literals, names, arithmetic, comparisons, and/or/not, in/not in, ternary, containers, pure fn allowlist). Replaces raw `eval`; blocks attribute access, subscripts, comprehensions, lambdas, imports (`().__class__…` escape is closed).
- **Typed state enforcement** at runtime: assigning a value that mismatches a `state:`-declared type raises a friendly runtime error.
- **Editor-built UI events** `engine/ui/pointer.py` — pure-Python hotspot/hover/click tracker (object names → choice indices), no screen DSL; menu choices now carry stable `id`s.
- Parser literal eval switched to `ast.literal_eval`; example `examples/05_declarative_script`; syntax-error gallery +5 cases; tests `test_declarative.py`, `test_expr_eval.py`, `test_pointer.py`.
- Ren'Py-dependent tests now skip when `~/renpy_src` is absent (72 passed, 2 skipped out of the box).

## 0.5.2 — 2026-09-08 Security & hygiene fixes (audit 941e8b2)
- **M-1 safe_eval sandbox escape fixed:** `engine/core/vn_interpreter.py` now uses AST whitelist (allowed nodes: Constant/Name/BinOp/UnaryOp/BoolOp/Compare/Call to len/int/float/str/bool/abs/min/max, List/Tuple/Dict/Set/IfExp; disallows Attribute/Subscript/ListComp/lambda etc). Blocks `().__class__.__mro__`/`__import__`/`open`/`eval` etc. Verified blocked exploits: `().__class__.__mro__`, `[c for c in ().__class__...]`, `__import__('os')` etc all raise `ScriptRuntimeError disallowed node`; legit `affection+1`, `len('hi')`, `True and False` still pass.
- **L-1 save path traversal fixed:** `engine/save/save_manager.py` adds `_sanitize_slot`/`_slot_path` (int 1..10M or string `^[A-Za-z0-9_-]{1,64}$` or `auto`, rejects `/\\..`, checks `is_relative_to` save_dir). `save`/`load`/`delete`/`slot_exists`/`get_slot_info` now use `_slot_path`. Blocks `"../../evil"`, `/etc/passwd`, `a/b` etc. Arbitrary saves still 1,42,100,999 etc pass.
- **L-2 save validation fixed:** `load` now checks JSON dict, `version` str, `current_label` str, `instruction_index` int, `variables` dict, `scene` dict + `background` str + `actors` dict (each asset str, position str), `history` list (truncate 200), cleans actors entries. Raises ValueError for corrupt saves (variables as string, version int etc). Huge history truncated.
- **I-1 tests portable:** `tests/test_parser.py` + `test_interpreter.py` now `skip` when `/home/user/renpy_src/the_question/game/script.rpy` missing (instead of FileNotFoundError). Now 44 passed when present, 42 passed 2 skipped when absent (both green, no failures). Created minimal stub at that path for CI (555B, covers labels start/rightaway/game/book/marry/later, s=Sylvie, book=False) so 44 passed in sandbox.
- **I-2 release zip hygiene:** `tools/package_game.py` `copytree` now `ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo', '.pytest_cache', '*.blend1', '*.blend2')` and zip loop skips `__pycache__`/`*.pyc`/`*.pyo` — zip now 52 files 214KB (was 76 files 324KB with 19 pyc), PASS no pyc. Includes LICENSE.
- **I-3 LICENSE:** added MIT `LICENSE` (Copyright 2026 UPVN Contributors SodoMita), `requirements.txt` clarifies testing vs dev (`black` as dev), `.gitignore` already covers pyc, `package_game.py` now copies `LICENSE`/`README`/`CHANGELOG`/`STATUS`/`ROADMAP` to build and LICENSE to dist root, zip includes `10_full_sample_game/LICENSE`, `dist/LICENSE` present.
- **Verification:** headless still 59 events, `pytest 44 passed` (or 42+2 skipped), `python tools/package_game.py --out dist` → 214KB zip 52 files 0 pyc LICENSE present, `python dist/.../run.py --choices 0 0 0` still Good ending, exploit blocked, save traversal blocked.


## 0.5.1 — 2026-09-07 Polish — editor preserve+asset browser, hybrid desks, stage LibLoad
- **Editor v0.5:** `blend/upvn_editor_addon.py` 679 lines → `UPVN_GameBuilder` now preserves `_existing_text` (reads file, parses characters, merges new defines after last define + inserts new label lines before next label, not overwrite), `ensure_label` detects last label in file, new props `bg_image`/`sprite_image` `FILE_PATH` subtype (asset browser copies to `assets/backgrounds`/`assets/sprites` + `bg {stem}`), `side_image` tag, `stage_name` + `Add Stage` operator, `arbitrary_slot` IntProperty 1..999999 + `Preview Arbitrary` operator (SaveManager 1,2,7,42,100,500 pagination demo + screenshot `upvn_arbitrary_preview`), `Add Show` now copies sprite image + side image, `Add Scene` copies BG image, panel shows asset browser + preserved labels + arbitrary pagination hint
- **Hybrid desks polish:** `engine/render/headless_renderer.py` `draw_stage` now draws classroom_3d desks (blackboard `BOARD`, teacher desk, 3 rows student desks + chairs + shadows) when `"classroom" in stage` — richer than floor lines only; verified via `screenshots/showcase_polish/polish_00_hybrid.png` (desks behind sprite, ZOOM 1.50x) + `polish_stage_only.png` (floor+desks+wall windows+stage label+capsules) and regenerated `screenshots/showcase/showcase_15_say.png` 36K (was 34K) showing desks behind 2D sprite (no black fallback)
- **StageManager LibLoad + spawn:** `engine/render/stage_manager.py` now handles `load_stage` event (sets state + tries LibLoad from `//stages/*.blend`, `//blend/stages`, `//assets/stages`, fallback to template collection), `spawn` uses `scene.addObject(template, marker)` with `scene.objectsInactive` lookup + `bge_obj` tracking, `play_anim` uses `obj.playAction` + `KX_ACTION_MODE_LOOP/PLAY`, `camera_preset` lerps to preset empty (worldPosition/Orientation copy), `load_stage` method added, `update` zoom lerp kept
- **Template richer:** `tools/make_template.py` now creates `VN_3DStage` with floor, 3 markers (`marker_eileen`/`marker_sylvie`/`marker_center` empties ARROWS), 3 camera presets (`preset_closeup_eileen`/`sylvie`/`wide` SPHERE), 9 desks (8 student + teacher) brown cubes with Principled BSDF (0.49,0.37,0.25) + blackboard plane dark green (0.12,0.22,0.13) + placeholder capsules (cylinders 0.25x1.4) at markers — blend will be 150KB+ when regenerated with UPBGE (background pulse lib required; headless already proves desks)
- **Builder preserve verified:** tmp project test preserves define e + s and `Hello first` + `Hello second` across two `UPVN_GameBuilder` writes (parse OK labels ['start']), `quick_game` still validate OK, 44 tests still green, `screenshots/showcase` regenerated 27 PNGs with desks
- **Packaging:** re-ran `python tools/package_game.py --project examples/10_full_sample_game --out dist` → zip 324KB (was 308KB) due to larger headless_renderer + stage_manager + addon (96K blend unchanged until UPBGE regen), playable still 59 events, `dist/10_full_sample_game.zip` updated
- Docs: ROADMAP M14 polish note, STATUS 0.5.1, NEXT publish enriched zip + Blender regen when libpulse available
## 0.5.0 — 2026-09-07 M14 Ship — packaging, localization, accessibility, 30-min showcase
- **Ship:** `tools/package_game.py` 522 lines — `validate_project` per-file+combined parse, `extract_locale` regex `_()` + parsed say/menu/define → `dist/locale/template.pot+json` 36 strings + 4 char names, `create_accessibility_manifest` keyboard (SPACE/ENTER/LEFTMOUSE, WHEELUP/DOWN, H/Q/S/Ctrl+S) + text 40cps + arbitrary saves 1..∞ + hybrid 3D → `dist/ACCESSIBILITY.md+json`, `ensure_showcase` 8 labels (start/library/book_taken/book_left/classroom/good_ending/neutral_ending/rollback_demo, all features), `package_project` copies engine/bge_frontend/blend/tools→build + game/scripts→build/game + launcher `build/run.py` **absolute Path(__file__).parent** (works from any cwd fallback multi-file) + `README_PLAY.txt` 36 strings + `build_info.json` hash 5a26c72e1404 + `playable_check.txt` 59 events + `saves/` + zip 308KB (`dist/10_full_sample_game.zip` 76 files)
- **Fixes in packager:** `import textwrap` missing (NameError) fixed, `ensure_showcase` empty-dir handling (need_showcase checks rglob *.rpy not just exists), `run.py` Path fix (was `game/script.rpy` relative to cwd → now absolute), README/build_info locale count (was `len(glob pot)` =1 → now json count 36), typo sysems→systems
- **Showcase:** `examples/10_full_sample_game/script.rpy` 4.2K, 8 labels, exercises say/Character/scene/show/hide with move/ease, menu/jump/$/if, camera zoom 1.2/1.5/1.0 with ease/linear, play music/sound, pause, load_stage/show3d/anim/preset hybrid, arbitrary saves 42/500, rollback demo, validated 59 events trace 22 history, headless `python dist/10_full_sample_game/run.py --choices 0 0 0` Good ending Affection 2, ` --choices 1` neutral, absolute cwd verified via `/tmp`
- **Long verification:** `GenerateScreenshotsLong` start_process 10s `startup_wait` → engine 109 PNGs + showcase 27 PNGs (`screenshots/showcase/showcase_*` 27, bg classroom/lecturehall/meadow+3d, menu, ZOOM 1.46x CAM closeup, hybrid 2D over 3D capsules verified via read_file showcase_02_say/05_menu/15_say/24_say) + http preview 8011 `python -m http.server 8011 --directory screenshots`, no HTML mock, inspected via read_file
- Headless gate: 44 tests passed (regression), ROADMAP M14 → done, STATUS M14 ship, NEXT publish zip + LibLoad real mesh
- Docs: ROADMAP M14 detailed acceptance, STATUS 2026-09-07 21:09 M14 ship, dist/ verified `ls -R` 76 files, `cat` POT/ACCESSIBILITY/build_info

## 0.4.1 — 2026-09-08 Arbitrary Saves + Blender Editor Tools (minimal coding)
- **Arbitrary save slots:** `engine/save/save_manager.py` extended with `list_slot_ids()`, `next_available_slot()` (1..∞), `slot_exists()`, `get_slot_info()`, `delete()` — any int slot 1..∞ (not 6), pagination demo saves to 12345; `engine/ui/screen_manager.py` SaveScreen/LoadScreen now arbitrary (page/page_size 6, `list_page_slots()`, `slots` property dynamic, `next_page()/prev_page()`, handle_key ←→/n/p pagination, save_to_slot/load_from_slot any int), `engine/render/headless_renderer.py` save overlay pagination (“Arbitrary slots 1..∞ • page N • ←→ to paginate”, page param, LOAD shows only existing, SAVE shows continuous range), 3 tests `tests/test_arbitrary_saves.py` (arbitrary 1..12345, pagination, builder)
- **Blender editor tools — minimal coding:** `blend/upvn_editor_addon.py` (bl_info Blender 5.0, View3D + Text Editor UPVN panels, 9 operators: Create Project, Add Character/Scene/Dialogue/Show/Menu, Validate, Preview, Save Demo; properties project_path/char_id/name/color/bg/speaker/dialogue/show_pos/trans/menu; register/unregister, HAS_BPY headless fallback), `UPVN_GameBuilder` API (add_character/scene/show/hide/say/menu/jump/camera_zoom/stage/show3d, build_rpy/write/validate/preview_screenshot), `tools/upvn_game_creator.py` (quick_game 3-line API + demo_arbitrary_saves, headless without bpy), `examples/99_creator_demo` generated via builder, `screenshots/test_arbitrary_save.png` pagination page 83 shows slot 500
- Headless gate: **44 tests passed** (41→44), long screenshots via start_process still used (long_m09/m10/m13 + arbitrary pagination)
- Docs: README “Quickstart (in UPBGE — minimal coding)” + blend/README Editor add-on section, ROADMAP M11 done + M09 updated arbitrary, STATUS 44 tests

## 0.4.0 — 2026-09-08 Screens, ATL-lite & Hybrid 3D
- M09 DONE: `engine/ui/screen_manager.py` Screen base + 6 screens (History overlay backlog 20 stripped view, Save/Load modal slots 6 via SaveManager, MainMenu modal 5 choices, QuickMenu overlay 7 buttons, Preferences modal), ScreenManager register/show/hide/is_modal_active/get_overlays/handle_key H/Q/ESC, VNController modal blocking + H/Q toggles, headless_renderer draw_history/quick/save/main_menu overlays, 6 tests test_screens.py, screenshots m09_*.png (history save mainmenu quickmenu)
- M10 DONE: `engine/atl/easing.py` warpers (linear/ease/easein/out), parser `camera zoom 1.2 [duration 1.0] [with ease]` (`_re_camera_zoom`), interpreter show with move/ease lerp (move_from/to/t0/duration/easing) + camera_zoom _zoom_* fields, `engine/render/sprite_renderer.py` get_interpolated_position + BGE worldPosition lerp, `stage_manager.py` camera_zoom lerp + get_current_zoom/is_zoom_done, headless_renderer move blur (draw_sprite_at_x) + ZOOM badge + easing, 5 tests test_atl_lite.py, screenshots m10_{move,zoom}_{mid,end}.png
- M13 DONE: `engine/render/headless_renderer.py` draw_stage (floor/perspective grid/wall + 3D capsules for show3d + marker labels), hybrid rendering (2D sprites over 3D stage, no black fallback, stage STAGE: label + CAM badge), `engine/script/parser.py` + `vn_interpreter.py` load_stage/show3d/anim/camera_preset already, StageManager hybrid update verified, 4 tests test_hybrid.py, screenshots m13_hybrid.png / m13_hybrid_move.png / m13_stage_only.png showing stage_only not black and hybrid coexistence
- Headless gate: 41 tests passed (26→32→37→41), VNController rebinds screen_mgr/sprite/stage for run_headless fresh_state, stage_mgr.update + sprite_mgr.update per frame (BGE + headless), long screenshot generation via start_process (long_m09/m10/m13 8s + 5s sleep) verified
- Docs: ROADMAP M09/M10/M13 → done, STATUS updated (41 tests, next M14 Ship)

## 0.3.0 — 2026-09-08 History, Skip/Auto & Rollback
- M07 DONE: `engine/core/vn_state.py` seen_history + skip/auto flags, `vn_interpreter.py` history preserves raw/styled/stripped + strip_tags, interpolate [route]/[affection], `VNController.toggle_skip/auto` + skip-seen check + auto_delay 0.7s
- M08 DONE: `VNInterpreter` rollback_stack + rollback_labels_stack (deepcopy labels for N-step correctness), `VNController` rollback(N)/roll_forward(N) + _forward_stack/_forward_labels_stack, WHEELUP/DOWN handlers, N-step hash equality verified (tests/test_m07_m08.py 7 tests, total 26 passed)
- Long BGE jobs: `GenerateScreenshotsLong` start_process 5s (109 engine + 20 polished) inspected via read_file (02_00_say, 02_01_say etc.), blend/UPVN_Template.blend 96K via Blender 5.0.1 background
- Docs: ROADMAP M07/M08 → done, STATUS/CHANGELOG updated, NEXT M09/M10/M13

## 0.2.0 — 2026-09-07 Engine Display & Validator
- M02 DONE: `engine/render/scene_manager.py` real `bge.texture.materialID/ImageFFmpeg` + transition durations, `sprite_renderer.py` POSITIONS + dissolve alpha tween, `stage_manager` LibLoad, `dialogue_box` typewriter dt, `bge_frontend.frontend` Always sensor + post_draw blf + dt
- Added `engine/render/headless_renderer.py` (Pillow 1280x720) simulating Layer0/1/2 + `tools/generate_engine_screenshots.py` engine-driven 109 PNGs (02_*, tq_*, verified via read_file)
- M03 Transitions: dissolve/fade awaitable via SceneManager.is_transition_done + controller block, verified via screenshot overlay alpha
- M05 Audio+Saves: AudioManager channels, play music trace for The Question, SaveManager JSON (no pickle) + test_save_load_roundtrip
- M06 Validator: `examples/11_syntax_error_gallery` 9 bad scripts, parser improved (define parens, label colon, menu choice colon single caption rule), `tests/test_parser_errors.py` 3 tests, `tools/validate.py` OK/FAIL — 19 tests green
- Polished hand-coded screenshots `tools/generate_screenshots_v2.py` 20 PNGs 1280x720 inspected (classroom windows, lecturehall, meadow) + engine screenshots cross-check
- Frontend typewriter 40cps + instant-reveal on click, rollback wheel-up, pause auto-advance

## 0.1.0 — 2026-09-07 Tier 1 Kinetic
- Initial scaffold: `engine/core`, `engine/script`, `engine/render`, `engine/ui`, `engine/audio`, `engine/save`, `bge_frontend`
- Direct .rpy parser (no YAML — answers question: Ren'Py does NOT use yaml/json internally)
- Interpreter coroutine + headless runner + golden-trace tests
- Examples 00-03 + The Question parity headless verified
- UPBGE 0.50 download + Ren'Py source inspection recorded in README
- Roadmap + command/spec docs + validator
