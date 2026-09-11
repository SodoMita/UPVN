# Current Status — 2026-09-10 (M26b: sprite textures work at runtime, branch feat/desktop-gui)

## Last completed
- **M26b (branch `feat/desktop-gui`, v0.6.14)**: runtime sprite/background
  textures via a texture-capable material graph (TexImage packed-white ×
  MixRGBA(ObjectInfo, Tex, Factor)) — palette at Factor 0, texture at 1;
  UV quads on all VN planes; per-position sprite materials; renderers try
  bank → node swap → bge.texture → palette. Cross-reviewed
  `feat/desktop-no-textures`: AABB pick rejected (3D-object contract → ray
  pick kept and live-verified), fileless generated white images SEGFAULT the
  player (bisected; packed is safe), their regenerated template lost logic
  bricks + game properties. Live-verified in the player on llvmpipe:
  auto mode renders PNG sprites with transparency + full-width backgrounds;
  color mode unchanged; converted Ren'Py project still plays. 295 tests.

# Current Status — 2026-09-10 (M26 Desktop GUI verification DONE, branch feat/desktop-gui)

## Last completed
- **M26 Desktop GUI + texture-free palette + Ren'Py converter (branch
  `feat/desktop-gui`)**: engine verified live in UPBGE 0.50 (Blender 5.0.1)
  on the headless-Wayland desktop (docs/how agent can run desktop.md).
  Startup segfault root-caused (audio_device userpref, see CHANGELOG 0.6.13);
  template + sample scenes play with ZERO image textures (Object Info →
  Emission palette, image_mode policy); mouse choices fixed (SENSOR is not
  rayCast-hittable in 0.50 → STATIC+BOX; ortho getScreenRay dead → manual
  frustum rayCast; mouse y from window top); opening sprite hidden-after-load
  fixed; Setup Scene no longer clobbers script_path; UPVN panel verified in
  the editor GUI (Engine OK, Setup Scene status, game properties show
  image_mode); Ctrl+S/Ctrl+L round-trip re-verified in GUI;
  **tools/renpy_convert.py** converts a Ren'Py project to a playable UPVN
  project (image bank bake, palette fallback) — verified end-to-end with a
  fake Ren'Py game. Addon v0.6.13 (dist zip). Tests: 290 passed / 16 skipped.
  Evidence: examples/20_smoke_game/evidence/m26_*.png, screenshots/m26/*.
  Embedded P in-editor works but needs ~1.6 GB RSS (OOM below that in the
  2 GB sandbox; standalone player is the lean path here).

# Current Status — 2026-09-10 (M25 Usability Stabilization Freeze DONE)

## Last completed
- **M25 Usability Stabilization Freeze (2026-09-10)**: feature freeze + P0-P2
  stabilization. BUGS.md opened (BUG-001..011). Field fixes verified IN-GAME on
  a headless Wayland stack (sway 1.10 + XWayland + llvmpipe): BUG-009 game
  properties invisible at runtime (addon now writes `object.game.properties`,
  template regenerated); BUG-010 digit choice select compared ASCII ordinals to
  evdev-like bge key codes (states now digit-ordered, helper fails closed on
  dicts); BUG-011 save/load modals were invisible story-blockers and Esc quits
  blenderplayer at engine level (Ctrl+S/Ctrl+L now direct quick-save/load,
  `saves/save_quick.json` round-trip proven in-game). `tools/smoke_walkthrough.sh`
  rebuilt: backend-agnostic (wayland/xvfb), self-verifying via the new
  `UPVN_HEARTBEAT` per-tick state file, retry-until-state for flaky synthetic
  input. docs/SANDBOX_UPBGE.md (headless-wayland recipe + Xvfb comparison),
  docs/MANUAL_QA.md (human checklist), evidence PNGs in
  examples/20_smoke_game/evidence/. Tests 276 passed / 16 skipped.
  **Freeze rule active: no new Ren'Py syntax/features until install/setup/play
  is boring and reliable.**


## Last completed
- M24 play feel (2026-09-09): mouse visible; ortho 15; UI NDC-laid so zoom leaves text; placeholder PNG sprites/BGs; LibLoad skipped if missing (crash fix); choice rayCast + SENSOR physics + keys/numpad. v0.6.11. Restart UPBGE, Setup Scene, P.
- M23.1 Setup Scene writes the OPEN scene (2026-09-09): field 18/27 missing choice_* because objects landed on VN_Main while the template Scene stayed old. v0.6.10. Restart UPBGE, Setup Scene, Check Wiring on that scene.
- **M22 Screen-language interpreter DONE (2026-09-09, branch `feat/renpy-corpus-compat`)**: the drop-in tier *parsed* `screen:` blocks and then discarded them — the body was captured as stripped text, so `show screen` / `call screen` emitted an event with a name and nothing to draw. The SDK tutorial has **99** screens and LearnToCodeRPG **23**; all were inert.
  - **`engine/ui/screen_lang.py`**: rebuilds the widget tree from a captured body and evaluates it — containers (`vbox`/`hbox`/`frame`/`window`/`fixed`/`null`/`bar`), leaves (`text`/`textbutton`/`imagebutton`/`add`/`label`/`input`/`key`), control flow (`if`/`elif`/`else`, `for`, `$`), screen-local `default`s, `use` + `transclude`, `has vbox` (a declaration, not a block — the container is synthesised from the siblings that follow), and `[expr]` interpolation. Output is JSON-serialisable.
  - **Layout deliberately not modelled**: positions, sizes, styles and anchors stay in `props`. UPVN's UI is built in the 3D scene, so a second layout engine would only compete with it.
  - **Wired into the interpreter**: `show screen`/`call screen` render and record into `VNState.active_screens` (a load restores the same UI); `hide screen` clears it. `run_headless` prints `SHOW SCREEN hud -> 5 widgets`, plus the first diagnostic when a screen could not be resolved.
  - **A broken screen never stops the story**: rendering does not raise — an undefined screen, an unresolvable condition or a non-iterable `for` yields an empty tree plus a diagnostic.
  - **Parser**: captured `screen:` blocks keep relative indentation and their parameter list; without them there is no tree to build and `screen choice(items):` is unusable.
  - **Validated on both corpora**: SDK tutorial **99/99** screens render (97 non-empty, 716 widgets), LearnToCodeRPG **23/23** (22 non-empty, 346 widgets).
  - Tests: **253 passed, 0 skipped** — `tests/test_screen_lang.py` (29) covers tokenising, tree shape, `has`, condition chains, control flow, `use`/`transclude`, param and keyword binding, degradation, the interpreter wiring and a save round-trip.
- **M21 Second corpus DONE (2026-09-09, branch `feat/renpy-corpus-compat`)**: M20 proved the drop-in tier on one shipped game; that is not the same as proving it on Ren'Py, so this milestone validates against a second, unrelated FOSS codebase — the games that ship inside the SDK itself (`renpy/renpy`, MIT): `tutorial/` (23 scripts) and `the_question/`. Before: **7/23** tutorial files parsed. After: **23/23**, 75 labels, 1672 statements, every `jump`/`call`/`call screen` resolves.
  - **Project-registered statements**: `renpy.register_statement("example", …)` in one file makes `example` legal in every other file — discovery is project-wide (`discover_custom_statements`) and runs before parsing in the checker, `tools/validate.py` and `VNController`. Bodies are captured, never executed. `testcase`/`testsuite` (Ren'Py's own test DSL, `renpy/parser.py:1230/1239`) recognised out of the box.
  - **`block="script"` honoured**: labels declared inside such a body are real jump targets — the tutorial hides `label play_pong:` inside an `example` block and it now resolves. A body we cannot read is recorded in `custom_statement_errors` instead of aborting the file; our own `init:` errors stay hard.
  - **Lexer**: a plain `"…"` string may run over several lines (Ren'Py lexes strings with `re.DOTALL`); an unterminated one now gets a friendly error naming the delimiter instead of silently eating the rest of the file.
  - **Say**: Ren'Py's automatic dialogue IDs (`e "…" id a1b2c3d4`) and a quoted who (`"Lucy" "text"`).
  - **Display**: `show`/`scene` may carry an ATL block; bare `scene` clears the layer.
  - **Other**: `define x += [ … ]`, `style NAME:` inside a label, `window show|hide|auto [transition]`, `nvl show|hide|clear [transition]`, comment-only files no longer error in a multi-file project, `custom_statement` is a no-op event at runtime.
  - **CI added** (`.github/workflows/ci.yml`): `tests`, `examples` (every example validated in its own tier + played headless; the syntax gallery must fail), `renpy-corpus` (LearnToCodeRPG) and `renpy-sdk` (this corpus) — both corpora via blob-filtered sparse checkout (~3 MB / ~6 MB instead of 288 MB / 500 MB).
  - **Cleanup**: README gained a "Drop-in Ren'Py compatibility" section; 20 regexes and a helper left dead by the M20 rewrite removed (97 → 77 regexes, none unused).
  - Tests: **224 passed, 0 skipped** — `tests/test_renpy_compat.py` +15 tests pinning every construct above, `tests/test_renpy_sdk_corpus.py` (9, skips without `UPVN_RENPY_SDK`).
- **M20 Drop-in Ren'Py compatibility DONE (2026-09-09, branch `feat/renpy-corpus-compat`)**: the full `.rpy` tier now parses and plays a **real shipped game** — `freeCodeCamp/LearnToCodeRPG` (BSD-3-Clause, 61 `.rpy`/`.rpym`, ~2 MB). Before: **0/61** files parsed. After: **61/61**, 127 labels, 5560 statements, every `jump`/`call`/`call screen` resolves, and the story runs headless (real dialogue out).
  - Lexer: triple-quoted strings across lines, `\` continuation, **unbalanced-bracket continuation** (`call screen f(` … `)`), BOM anywhere, `#` only outside strings, hint for unterminated `"""`.
  - Parser: `from` clauses, `call screen f(args) with t`, `show/hide screen f(args)`, `for` loops (+tuple targets), voice attributes (`player @ surprised`), negated image attributes (`e -sweat`), `nointeract`, `extend`, `centered`/`vcentered`, `with <expr>`, `scene/show/hide` clause splitting in any order (`as`/`at`/`behind`/`zorder`/`onlayer`, never inside dialogue text), expression `pause`, playlists + `loop`/`noloop`/`fadeout`, `voice sustain`, `stop audio`.
  - Menus: **named menus are jump/call targets** (Ren'Py semantics), `set var`, `if`/`elif`/`else` choice groups, dialogue/`$`/`python:` before choices (`menu.pre`), `"Text" (props) if cond:` (caption parsed first, so a literal "if" in the text stays text).
  - Top level: `default` as expression / dotted / inside a label, dotted `define` → store **namespaces** (`gui`/`config`/`build`, permissive unknown members), `image n = <expr>`, `layeredimage:` blocks, style property statements, `screen f(a) tag/modal/zorder:`, `transform f(a):`, `init python hide:` / `python early:`, multi-line `Character(...)`.
  - Indentation: safe/.urpy still demand exactly 4 spaces (gallery intact); drop-in tier accepts any *consistent* indent.
  - **Multi-file loading fixed**: `VNController` used to concatenate all `.rpy` into one buffer (a mid-file BOM broke it and line numbers were fiction) — files are now parsed individually (`require_start=False`) and merged; `start` checked on the merged script.
  - Interpreter: `for` splicing with `break`/`continue`, `from_clause` no-ops, `menu.pre`, screen args, expression `pause`, `voice_sustain`, say extras, `stop_sound/voice/audio`, namespaces injected into the python env, `_()`/`_p()` identity helper, `base_dir` wired for `renpy.loadable`.
  - Loose expressions (full tier only): unknown names/attributes/functions → `None` (recorded), `None` comparisons → `False`, kwargs + comprehensions, more pure builtins. **Dunder escapes still blocked in both modes (tested).**
  - Compat mode (`VNController(..., mode="full", compat=True)`): `init python:`/`python:` failures collected in `interp.init_errors`/`interp.python_errors`, unknown globals → recorded no-ops (`PermissiveEnv`), unknown `renpy.*` → no-ops that can be subclassed (`__mro_entries__`) and are logged in `renpy.compat_log`. Default still raises.
  - New `tools/check_renpy_project.py` (per-file report, duplicates, unresolved targets, `renpy.*` usage, `--json`, `--run` smoke run) and example `examples/14_renpy_dropin` (3 files, stock Ren'Py syntax, both routes run).
  - Tests: `tests/test_renpy_compat.py` (64) + `tests/test_renpy_corpus.py` (5, skips without `UPVN_RENPY_CORPUS`); The Question restored at `~/renpy_src` so the 2 long-skipped tests run again → **200 passed, 0 skipped**.

- M23 3D-only UI DONE (2026-09-09): no blf overlay; FONT Speaker_Text/Dialogue_Text + choice_0..8 planes; LMB getScreenRay → PointerTracker.choose; Emission unlit + lights off; sprites visible without PNG. Add-on v0.6.9. Re-run Setup Scene.
- M22 UPBGE play: camera bind + keyboard capture DONE (2026-09-09): Camera_UI Front (XZ planes, (0,-10,0) rot X=90°) reset every Setup Scene; runtime `scene.active_camera = Camera_UI`; AllKeys+Mouse bricks so embedded P receives keys (LMB already worked); input path is `inputs.queue` only — `keyboard.events` gone (deprecation + lossy conversion). Add-on v0.6.8. tests/test_m22_upbge_play.py
- M21 Script discovery + diagnostics DONE (2026-09-09): runtime searches parent/grandparent dirs of the .blend (`//../game/script.rpy`, `//../../game/script.rpy`, example layouts) — packaged `<pkg>/blend` + `<pkg>/game` now loads without manual path setup; load failure draws an on-screen red diagnostic (searched paths + fix steps) instead of a console-only warning; Setup Scene reports intact wiring as INFO (was false "Brick wiring issue: existing" warning); input polling moved off deprecated keyboard.events/mouse.events to device.inputs via pure helpers `_bge_input_state/_bge_just/_bge_active` with legacy fallback; digit selector rewritten as pure `_digit_choice_index`; register banner prints real bl_info version; add-on v0.6.7; tests updated (+packaged-layout path test) → 135 passed 2 skipped
- M20 r2 Idempotent Setup + live Pillow DONE (2026-09-09): Setup Scene reuses existing `VNController` (brick collections have no .remove() in UPBGE 0.50 — field error fixed), refreshes props/launcher, adds only missing bricks by name (`upvn_bricks='existing'` when intact); `render_state` live-probes PIL at call time (static HAS_PIL went stale after mid-session install); add-on `pil_live_available()` per attempt; Install Pillow uses `pip --target <running purelib>` → visible without Blender restart + verifies + advises restart if needed; add-on v0.6.6; 7 tests in test_m20 → 133 passed 2 skipped
- M20 UPBGE runtime fixes from the field DONE (2026-09-08): `blf.color(fontid,r,g,b,a)` 5-arg signature in all overlay calls (was: 4-arg → per-frame error, no text color); `headless_renderer.py` imports without Pillow + `render_state` raises one clear RuntimeError with install command; add-on preview stores reason in `UPVN_GameBuilder.last_error` and reports it (no raw `ModuleNotFoundError: PIL` traceback); new operator "Install Pillow" runs `python3.11 -m pip install pillow` in UPBGE's bundled Python; add-on v0.6.5; 5 new tests → 131 passed 2 skipped
- M19 Explicit scene-object contract DONE (2026-09-08): `engine/render/contract.py` single source of truth (objects/materials/collections/text/asset dirs each with purpose + used_by); scene_manager/sprite_renderer import identifiers from contract (no literals); build_vn_scene + make_template create all five `Sprite_*` planes with `MASprite` (previously missing → 'show' could not display); shipped UPVN_Template.blend regenerated in X11 (113KB) — 16/16 items present, bricks wired; operator `upvn.check_wiring` writes report to UPVN_WIRING text; docs table in blend/README; 7 tests → 126 passed 2 skipped

- M18 Gameplay input DONE (2026-09-08): menu choices selectable with number keys 1..9 in the real engine (pure helper `_menu_choice_from_keycodes`, digit ASCII codes, respects choice count, JUST_ACTIVATED only) — menus no longer freeze in UPBGE; debug/QA keys F1 (state dump) + F12 (in-game screenshot via bge.render.makeScreenshot to //screenshots/) in frontend; modal screens (save/load/history/quickmenu) now draw a text overlay (title+page) in-game; add-on bumped v0.6.3, dist rebuilt; 6 new tests → 119 passed 2 skipped
- M17 r2 Blender/UPBGE hardening — VERIFIED IN REAL X11 (2026-09-08): add-on v0.6.2 — fixed field crash `AttributeError: bpy.data.filepath` during startup enable (getattr + never-raise ensure_engine/register; registration OK in real UPBGE 0.50 UI with AND without open file); install zip now single-folder `upvn_editor_addon/` (no addons/engine+bge_frontend bl_info pollution; clear hint when zip dropped compressed); **committed blend/UPVN_Template.blend is pre-wired & playable** — generated in interactive X11 (Xvfb) session: Always(pulse)→Python(SCRIPT upvn_launcher) brick present AND linked (sensor.controllers==['UPVN_Main'], mode SCRIPT, text set, upvn_bricks='yes') so pressing P runs the game; frontend tick-guard (no per-frame spam), overlay for fallback script, launcher one-time error hint; 113 passed 2 skipped
- M17 Blender/UPBGE UX hardening DONE (2026-09-08): add-on v0.6 self-contained engine discovery (module dir / repo root / zipimport from installed archive / prefs engine_path / open .blend dirs) + live ✓/✗ status rows + Locate Engine/Check/Bundle operators + friendly reports (no more bare "Engine not available"); one-click `Setup Scene` (UPBGE): `build_vn_scene` data-API creates VN_Main+cameras+VN_* collections+planes+VNController(script_path/upvn_root/upvn_bricks)+`upvn_launcher` Text+bricks via official `bpy.ops.logic.*` (UI context; --background skips loudly); `bge_frontend/frontend.py` reads VNController.script_path first + self sys.path bootstrap (wrong/no script bug fixed); `tools/make_template.py` data-API regen (110KB was brickless 96KB); `tools/package_addon.py` → dist/upvn_editor_addon_v0.6.2.zip self-contained; tests/test_m17_addon_init.py 5 tests
- M00 Harness done: parser, interpreter, state, headless runner, UPBGE 0.50 download verified (408 MB, Blender 5.0.1), The Question parses and runs 3 paths
- M01 Kinetic done: 00_minimal_dialogue headless + UPBGE controller + blf typewriter dt via bge_frontend.frontend
- M02 Display DONE (2026-09-07 late): engine/render/* real BGE texture + headless_renderer 109 PNGs, positions validated
- M03 Transitions DONE: fade 0.6s/dissolve 0.45s + alpha tween
- M04 The Question parity headless DONE: 3 paths
- M05 Audio+Saves DONE: play music trace, JSON round-trip (19 → 26 tests) — now arbitrary 1..∞ (M09)
- M06 Validator DONE: 9-file gallery + parser hints + tests/test_parser_errors.py
- M07 Backlog/skip/auto DONE (2026-09-08): history stores raw/styled/stripped + interpolate [var] + strip_tags {b}/{color}/{i}, seen_history, skip/auto flags + seen-check, VNController.toggle_skip/auto, 4 new tests
- M08 Rollback-lite DONE (2026-09-08): rollback_stack + rollback_labels_stack, VNController rollback(N)/roll_forward(N), WHEELUP/DOWN, N-step hash equality, long screenshots 109 PNGs
- M09 Screen system lite UPDATED (2026-09-08 late): **arbitrary slots 1..∞** — SaveManager.list_slot_ids/next_available_slot/slot_exists/get_slot_info/delete + pagination (page/page_size 6, list_slot_ids, ←→ next/prev), SaveScreen/LoadScreen arbitrary, headless save overlay pagination “Arbitrary slots 1..∞” + page indicator, 6 tests + 3 new = 44 total
- M10 ATL-lite DONE (2026-09-08): camera zoom 1.2 duration 1.0 + easing, show with move lerp not snap, easing module, 5 tests
- M11 Blender Editor Tools DONE (2026-09-08 late): `blend/upvn_editor_addon.py` (View3D/Text Editor UPVN panels, 9 operators: Create Project, Add Character/Scene/Dialogue/Show/Menu, Validate, Preview, Save Demo), `UPVN_GameBuilder` API (add_character/scene/say/show/menu/camera/stage/show3d/write/validate/preview), `tools/upvn_game_creator.py` quick_game 3-line minimal coding + arbitrary saves demo, `examples/99_creator_demo` generated
- M13 Hybrid 3D DONE (2026-09-08): load_stage/show3d/anim/preset, hybrid 2D over 3D, no black fallback, 4 tests
- M14 Ship DONE (2026-09-07 21:09): `tools/package_game.py` (522 lines, textwrap+validate+locale+POT+JSON+a11y+copy+build_info hash+playable_check+zip) + `examples/10_full_sample_game/script.rpy` 8 labels 59 events + `dist/` (locale/template.pot+json 36 strings, ACCESSIBILITY.md/json, 10_full_sample_game/ with run.py absolute Path + README_PLAY 36 strings + build_info.json hash + playable_check + saves/ + zip) + headless run.py --choices 0 0 0 verified from any cwd + long showcase screenshots via start_process
- **0.5.1 Polish DONE (2026-09-07 21:20):** editor v0.5 preserve `_existing_text` merges defines+label lines (not overwrite), asset browser `bg_image`/`sprite_image` FILE_PATH copies to assets, `side_image`, `stage_name`+Add Stage, `arbitrary_slot` 1..999999 + Preview Arbitrary; `headless_renderer draw_stage` classroom_3d desks (board + teacher desk + 3 rows student desks + chairs + shadows, 36K hybrid); `StageManager load_stage/show3d/anim/camera_preset` with LibLoad + `addObject` + `playAction`; `make_template.py` richer VN_3DStage; showcase regenerated 27 PNGs with desks; 44 tests green
- **0.5.2 Security & hygiene DONE (2026-09-08):** audit 941e8b2 — M-1 safe_eval AST whitelist (blocks `().__class__`, `__import__`, `ListComp` etc, legit still pass), L-1 save `_sanitize_slot`/`_slot_path` (int 1..10M or ^[A-Za-z0-9_-]+$ or auto, rejects /\\.., is_relative_to), L-2 load validates version/label/index/variables dict/scene/history truncate 200 + cleans actors, I-1 tests skip when `/home/user/renpy_src/...` missing, I-2 zip hygiene no pyc + LICENSE included, I-3 MIT LICENSE + requirements dev black; exploit + traversal blocked; 59 events still
- M15 Declarative language DONE (2026-09-08, branch feat/declarative-rpy): parser `state:` typed block / `character` block / `image`/`audio`/`stage` manifest / `set` / `choice` keyword / optional `end` terminators; `engine/script/expr_eval.py` AST-whitelist evaluator replaces raw `eval` (attribute/subscript/comprehension/import escapes blocked); typed-state runtime enforcement; `engine/ui/pointer.py` hotspot hover/click for editor-built UI; menu choice `id`s; `ast.literal_eval` for default/state literals; example 05; tests test_declarative/test_expr_eval/test_pointer; +5 syntax gallery cases; renpy_src tests skip when absent → 72 passed, 2 skipped
- M16 Three language tiers DONE (2026-09-08): tier 1 `engine/script/urpy_parser.py` (strict `.urpy`, zero embedded Python, required `end`, rejects `$`/`define`/`default`/`python:` with hints); tier 2 `.rpy` safe = existing declarative subset now rejecting full-tier constructs with `parse with mode='full'` guidance; tier 3 `.rpy` full = `Parser(full=True)` (python:/init/init offset/while/break/continue/pass/window/nvl/voice/queue music|sound/show|hide|call screen/jump+call expression/call label(args)/label name(params)/conditional menu choices/generic `$`/screen|style|transform|translate blocks); interpreter executes python+init (`renpy`/`store` compat via `engine/script/renpy_compat.py`), label params, while splicing + break/continue, jump/call expression, conditional-menu filtering; expr_eval now allows container subscripts + attribute access only on injected renpy/store; `VNController(mode=)` + `tools --mode safe|full`; examples 12 (full) + 13 (urpy); `tests/test_full_rpy.py` → 108 passed, 2 skipped
- M16 merge + debugging DONE (2026-09-08): merged `feat/declarative-rpy` into `main` (resolved 4 conflicts: vn_interpreter safe_eval kept delegating to expr_eval whitelist, STATUS/CHANGELOG combined, tests use shared TQ_SCRIPT) and pushed. Debug fixes: multi-file dirs no longer require `start` in every `.urpy` (`require_start=False`, checked on merged script); `store.x`/`renpy.store.x`/bare names share one namespace in python blocks (stale-copy overwrite fixed via StoreWrapper over the exec dict + runtime.store_dict); label re-entry resets to `_pristine_labels` so spliced while/if/menu nodes never accumulate; dialogue `[...]` interpolation evaluates whitelisted expressions (`[gold*2]`, `[store.gold]`) with verbatim fallback; `store` injected into expr `extra`. 108 passed, 2 skipped

## Currently failing / todo
- None blocker — 224 passed, 0 skipped, 0 failures (CI green on GitHub, all 4 jobs)
- Drop-in tier still **captures** (does not render) `screen`/`style`/`transform`/`translate` bodies; the editor-built UI layer is the consumer
- `python:` blocks run for real: a game needing third-party modules or `renpy.display.*` classes needs `compat=True` (LearnToCodeRPG needs `supermemo2.SMTwo`, which its pinned dependency version no longer exports — 7 collected init errors, story still plays)
- None blocker — pytest + M22; 2 skipped (renpy_src absent), 0 failures

- Full game-engine loop (pressing P, seeing/clicking dialogue) still needs a machine with a working GL display: bricks are created and linked (verified in X11/Xvfb), but the sandbox segfaults when the game engine itself starts (blenderplayer/view3d.game_start, llvmpipe) — user acceptance on a real GPU machine is the remaining check
- Next up (not blockers): make `UPVN_GameBuilder` emit declarative forms (`character`/`state`/`set`/`choice`) instead of legacy `define`/`$`; wire `VNState.resolve_asset` into renderers so scene/show/play_music actually resolve manifest paths; wire `engine/ui/pointer.py` into `bge_frontend/frontend.py` (raycast object under cursor → `PointerTracker.update` → `controller.choose(i)`); publish GitHub release with dist zips

## Recommended next task
- **Draw the widget trees in the UPBGE frontend too.** M23 proves the headless renderer can paint them; the 3D frontend still ignores `active_screens`. Walking the same widget list into blf + planes (text → blf, frame/vbox/hbox → quads from the `props` positions) makes `call screen` visible in-game, closing the loop the headless side now demonstrates.
- A third corpus for regression breadth (a GPL Ren'Py game, e.g. an Everlasting Summer port) — the checker is corpus-agnostic, so this is config, not code
- Publish a GitHub release with the `dist/` zips
- Human-in-the-loop acceptance (user): open blend/UPVN_Template.blend in UPBGE → UPVN tab shows ✓ Engine → Create Project → P → click/Space to advance; report console output if anything looks off

## CI (`.github/workflows/ci.yml`, green)
Four jobs, all verified: `tests` (pytest), `examples` (every example validated in its own tier + played headless, and the syntax gallery must *fail*), `renpy-corpus` (LearnToCodeRPG) and `renpy-sdk` (the SDK's own games). Both corpora are fetched with a blob-filtered sparse checkout (~3 MB / ~6 MB instead of 288 MB / 500 MB) and their reports upload as artifacts. Jobs install `requirements.txt` — a bare `pip install pytest` left Pillow out and aborted test collection for the whole suite.
- Human-in-the-loop: open blend, **Setup Scene** (resets Camera_UI + adds AllKeys), P. Expect: Front ortho of BG/sprites, Space/Enter/1-9 work, console has `active_camera bound to Camera_UI` and no `keyboard.events` warning.

- Wire `engine/ui/pointer.py` into `bge_frontend/frontend.py` + `VNController` (hover/click over editor-built choice objects → `controller.choose`) — the UI/input half of M15
- Update `UPVN_GameBuilder.build_rpy()` to emit the canonical declarative forms (and update `test_arbitrary_saves.py::test_blender_builder_minimal_coding`)

## Notes
- **Corpus for the drop-in tier**: `UPVN_RENPY_CORPUS=/path/to/project python -m tools.check_renpy_project /path/to/project --run`. Working checkout used here: `/home/user/renpy_corpus/LearnToCodeRPG` (BSD-3-Clause, `.rpy`/`.rpym` only, 2.1 MB). The corpus is NOT vendored; tests skip without it.
- Drop-in tier: `Parser(src, f, full=True, require_start=False)` per file + `_merge_scripts`; named menus become labels; `menu.pre` is spliced in front of the menu at runtime (marked `_pre_done` so re-entry does not repeat it).
- Parser requires 4 spaces, spaces not tabs, BOM stripped. Caption inside menu: bare quoted line — see SCRIPT_LANGUAGE_SPEC. Friendly hints for define/jump/menu/label. New: camera zoom 1.2 duration 1.0 with ease, show with move.
- Interpreter deep-copies labels for splicing; rollback also deep-copies labels; show with move sets move_from/to/easing/0.5s lerp, camera zoom sets _zoom_*.
- Headless gate: `VNController.run_headless(choices=[...])` + `pytest` 108 passed (or N+2 skipped when renpy_src missing); screenshots via headless_renderer (109 + 20 + 27 showcase + polish desks + arbitrary pagination) inspected via read_file (no HTML mock) — safe_eval whitelisted, saves validated
- UPBGE tarball at ~/upbge-0.50-linux-x64.tar.xz (390 MB) — LD_LIBRARY_PATH pulse fix, long start_process with startup_wait used per instruction (http 8011 preview)
- Ren'Py source at ~/renpy_src for reference only; no code copied. Easing module engine/atl/easing.py mirrors Ren'Py warpers.
- Screen system: engine/ui/screen_manager.py overlay vs modal, pagination arbitrary slots 1..∞ (page/page_size 6, list_page_slots, ←→/n/p), SaveManager.list_slot_ids/next_available_slot/slot_exists/get_slot_info/delete, VNController modal blocking, H/Q/S/L/ESC + ←→ for pagination.
- Blender editor: blend/upvn_editor_addon.py v0.5 (UPVN_GameBuilder preserve + asset browser bg_image/sprite_image FILE_PATH + side_image + stage_name + arbitrary_slot + Preview Arbitrary, 12 operators + 2 panels), tools/upvn_game_creator.py quick_game 3-line minimal coding, examples/99_creator_demo generated, validates/previews headlessly without bpy.
- Hybrid: state.stage + stage_objects + camera preset/zoom, headless_renderer draw_stage floor+wall+capsules+desks/board, 2D sprites over 3D, VNController stage_mgr.update per frame, StageManager LibLoad + addObject + playAction + camera lerp.
- Packaging: tools/package_game.py validates per-file+combined parse, extracts locale regex _() + parsed say/menu/define, creates ACCESSIBILITY.md/json, copies engine/bge_frontend/blend/tools + LICENSE/README → build (ignore __pycache__/*.pyc), run.py uses Path(__file__).parent absolute (works from any cwd), build_info.json hash, playable_check 59 events, zip 214KB clean 52 files, dist/locale/template.pot+json 36 strings, dist/LICENSE included (I-3)
- Audit 0.5.2: safe_eval AST whitelist (no Attribute/Subscript/ListComp), SaveManager _sanitize_slot/_slot_path + is_relative_to, load schema validation, tests skip when the_question missing, zip hygiene no pyc, MIT LICENSE, requirements dev black
- Declarative language (M15): `state:` → defaults+types (VNState.declared_types), `character e:` block, `image/audio/stage` → VNState.assets (+resolve_asset), `set` canonical assign (typed-checked), `choice` keyword + optional `end`; expr_eval.py AST whitelist (no eval escapes); pointer.py hotspot hover/click for editor UI; menu choices carry stable `id`s
- Three tiers (M16): `.urpy` (urpy_parser, required `end`, no Python), `.rpy` safe (default; full-tier constructs → ParseError 'mode=full' hint), `.rpy` full (Parser(full=True), parse_string_full, VNController(mode='full'), tools --mode). Full tier adds label_params/defines/init_python/transforms/screens/styles/translations + `"full": true` to IR; interpreter runs python:/init via exec with renpy/store compat (renpy_compat.py) and syncs JSON-safe vars back; while-loop body is spliced per-iteration with loop-id tail markers for break/continue; label params bound/restored on call/return. Expression sandbox: container subscripts allowed, attribute access only on injected renpy/store (dunders blocked)

## M26c — play-by-script: audio real, camera zoom real, segfault fixed (2026-09-10)

Full-sample game (`examples/10_full_sample_game`, template + flipped
`script_path`) played start→end in the player with a per-event heartbeat
(label/idx/event/choices/ortho). Evidence in this session's logs; repro:
`UPVN_HEARTBEAT=/tmp/upvn_hb.json UPVN_DEBUG_TEE=/tmp/upvn_debug.log
blenderplayer -w 800 450 blend/UPVN_Template.blend` (+VNController.script_path
flipped to the sample script), xdotool clicks/keys to advance.

- **Fixed segfault** (was killing the player at `load_stage classroom_3d`):
  SceneManager LibLoad without exists-check → sig=11. StageManager owns stage
  loading now; SceneManager logs-and-continues. AST regression tests.
- **Audio**: play music/sound/voice are real aud playback (Sound.file API —
  this build has no aud.device()/Factory), prefix×ext resolver, warn-once
  missing-file, loop=-1 music, fade ramp in update(dt), single "no audio
  device — running silent" warning when no backend exists (sandbox), per-
  channel stop. Sample wavs committed in blend/ (theme.wav, knock.ogg.wav).
- **Camera zoom** applies to ortho with the authored easing; heartbeat
  measured 15→12.5→10→15 exactly. Contract constant = base (single writer;
  two live traps with measured-base schemes documented in code).
- `anim`/`show3d`/`camera preset`: state-only 3D tier, safe continue without
  a stage project (LibLoad logs when stages/ files absent).
- Hover (M26c, previous commit): HOVER_SCALE 1.08, single scale writer in
  layout_screen_ui, zoom-proof; 5 headless tests.

Status: 307 passed / 16 skipped. `feat/desktop-gui`.

## M26d — 3D stage tier + hover proven live (2026-09-10)

- LibLoad SEGFAULTS UPBGE 0.50.0 on any file (bisected incl. template-copy
  control) → opt-in via UPVN_ENABLE_LIBLOAD=1; baked stages are the tier:
  tools/bake_stage_into_template.py (no stage cameras; templates parked at
  30,-3,-30 — excluded collections don't exist at runtime, addObject rejects
  active objects → spawn() repositions the master).
- camera_preset guards Camera_UI BEFORE resolving Camera_3D (moving the
  dormant template camera stole the viewport: perspective render, no UI).
- _bind_camera re-asserts every tick (stage camera present ⇒ viewport could
  drift despite active_camera reading Camera_UI).
- Hover LIVE-MEASURED over a 3D scene menu: plate 560 → 604 px (×1.08),
  symmetric ±22 px, previously-hovered plate returns to base; click selects
  and the story advances (probe script reached `end`, player alive).
- package_game.py ships the whole project tree now (was *.rpy only — assets/
  stages/ were lost in packaged builds); stage path candidates include
  //../game/stages/ (packaged layout).
- Sample stage: examples/10_full_sample_game/stages/classroom_3d.blend
  (+evidence m26d_hover_scale_live.png). Tests: 314 passed / 16 skipped
  (7 new M26d regressions).

## M26e — bootstrap script fixed, bake tool executed + standalone-verified (2026-09-10)

- desktop_sway.sh: export XDG_RUNTIME_DIR (was bare assignment → sway abort)
  + `model` not `mode` for headless output config. Verified by kill-and-
  rebuild via the script itself. Both pinned in tests.
- bake_stage_into_template.py: EXCLUDE_SUFFIX interpolation NameError fixed
  (first real run); copies engine/ + bge_frontend/ next to --out (launcher
  resolves //; otherwise ModuleNotFoundError). Baked game live-verified from
  /tmp/bakedgame: spawns/anim/preset-skip/menu/hover-click-select → end,
  ALIVE.
- Tests: 318 passed / 16 skipped (4 new M26e; bake tests skip without /opt).

## M26f — package_game verified live, script_path baked (2026-09-10)

- Packager runs clean on the sample game (zip 1740 KB; in-packager playable
  check 59 events). Packaged blend has VNController.script_path =
  //game/script.rpy pre-baked (binary-optional with manual fallback; .blend1
  removed post-flip). README_PLAY updated — "press P" with no manual step.
- Packaged build live-verified start→end in the player: assets palette OK,
  game/stages/classroom_3d.blend FOUND (LibLoad-gated message correct), theme
  resolves, endings menu, ALIVE.
- Removed accidentally-tracked blend/sample_test.blend; SceneManager
  load_stage log wording fixed (deferred-to-StageManager, no false "no stage
  file").
- Tests: 322 passed / 16 skipped (4 new M26f).

## M26g (v0.6.15) — plugin update works live, no uninstall/restart (2026-09-11)

- register() purges stale registrations by RNA name (panels via bl_idname
  UPVN_PT_main; operators via lowercase keys like UPVN_OT_reload_addon)
  before binding — install-over-a-running-UPBGE applies immediately.
- Scene.upvn_addon_version live property + upvn.reload_addon operator
  ("Apply Update") for file-replaced updates; synchronous in background,
  timer-deferred in UI.
- Proven in one blender session (test_m26g_addon_live_update.py, 5 tests):
  real addon_install of the 0.6.15 zip over live 0.6.14 → new code live with
  no restart; reload op applies an on-disk 0.6.99 bump in-session.
- Blender 5.0.1 findings: addons/ not on sys.path until
  refresh_script_paths() (the install operator calls it);
  addon_utils.enable returns module-or-None (unpacking it as (ok, err)
  raises).
- package_addon.py mkdir fix (missing dist/ wrote a FILE named dist).
  Tests: 327 passed / 16 skipped.
