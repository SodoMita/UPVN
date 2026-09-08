# Changelog

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
