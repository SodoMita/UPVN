# Current Status — 2026-09-08 (M15 declarative language)

## Last completed
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
- M14 Ship DONE (2026-09-07 21:09): `tools/package_game.py` (522 lines, textwrap+validate+locale+POT+JSON+a11y+copy+build_info hash+playable_check+zip) + `examples/10_full_sample_game/script.rpy` 8 labels 59 events + `dist/` (locale/template.pot+json 36 strings, ACCESSIBILITY.md/json, 10_full_sample_game/ with run.py absolute Path + README_PLAY 36 strings + build_info.json hash 5a26c72e1404 + playable_check + saves/ + zip 308KB) + headless run.py --choices 0 0 0 (59 events, saves arbitrary 1..∞) verified from any cwd + long showcase screenshots 27 PNGs (engine+showcase hybrid 3D ZOOM/CAM badges) via start_process startup_wait 10s + http preview 8011
- M15 Declarative language DONE (2026-09-08, branch feat/declarative-rpy): parser `state:` typed block / `character` block / `image`/`audio`/`stage` manifest / `set` / `choice` keyword / optional `end` terminators; `engine/script/expr_eval.py` AST-whitelist evaluator replaces raw `eval` (attribute/subscript/comprehension/import escapes blocked); typed-state runtime enforcement; `engine/ui/pointer.py` hotspot hover/click for editor-built UI; menu choice `id`s; `ast.literal_eval` for default/state literals; example 05; tests test_declarative/test_expr_eval/test_pointer; +5 syntax gallery cases; renpy_src tests skip when absent → 72 passed, 2 skipped

## Currently failing / todo
- None blocker — M15 done, 72 passed + 2 skipped (renpy_src absent), 0 failures
- `dist/` tree deleted from working tree (left by prior agent cleanup, uncommitted) — rebuild via `tools/package_game.py` when shipping; don't commit the deletion into a feature commit
- Next up (not blockers): make `UPVN_GameBuilder` emit declarative forms (`character`/`state`/`set`/`choice`) instead of legacy `define`/`$`; wire `VNState.resolve_asset` into renderers so scene/show/play_music actually resolve manifest paths; wire `engine/ui/pointer.py` into `bge_frontend/frontend.py` (raycast object under cursor → `PointerTracker.update` → `controller.choose(i)`)
- DLC perf: 72 tests <1s headless

## Recommended next task
- Wire `engine/ui/pointer.py` into `bge_frontend/frontend.py` + `VNController` (hover/click over editor-built choice objects → `controller.choose`) — the UI/input half of M15
- Update `UPVN_GameBuilder.build_rpy()` to emit the canonical declarative forms (and update `test_arbitrary_saves.py::test_blender_builder_minimal_coding`)
- Polish/DLC: LibLoad real .blend classroom mesh, addon asset browser, publish release + CI

## Notes
- Parser requires 4 spaces, spaces not tabs, BOM stripped. Caption inside menu: bare quoted line — see SCRIPT_LANGUAGE_SPEC. Friendly hints for define/jump/menu/label. New: camera zoom 1.2 duration 1.0 with ease, show with move.
- Interpreter deep-copies labels for splicing; rollback also deep-copies labels; show with move sets move_from/to/easing/0.5s lerp, camera zoom sets _zoom_*.
- Headless gate: `VNController.run_headless(choices=[...])` + `pytest` 44 passed; screenshots via headless_renderer (109 + 20 + 27 showcase + arbitrary pagination) inspected via read_file (no HTML mock)
- UPBGE tarball at ~/upbge-0.50-linux-x64.tar.xz (390 MB) — LD_LIBRARY_PATH pulse fix, long start_process with startup_wait used per instruction (long_m09/m10/m13 + showcase engine+showcase + arbitrary pagination, http 8011 preview)
- Ren'Py source at ~/renpy_src for reference only; no code copied. Easing module engine/atl/easing.py mirrors Ren'Py warpers.
- Screen system: engine/ui/screen_manager.py overlay vs modal, pagination arbitrary slots 1..∞ (page/page_size 6, list_page_slots, ←→/n/p), SaveManager.list_slot_ids/next_available_slot/slot_exists/get_slot_info/delete, VNController modal blocking, H/Q/S/L/ESC + ←→ for pagination.
- Blender editor: blend/upvn_editor_addon.py (UPVN_GameBuilder API + 9 operators + 2 panels), tools/upvn_game_creator.py quick_game 3-line minimal coding, examples/99_creator_demo generated, UPVN_GameBuilder validates/previews headlessly without bpy.
- Hybrid: state.stage + stage_objects + camera preset/zoom, headless_renderer draw_stage floor+wall+capsules, 2D sprites over 3D, VNController stage_mgr.update per frame.
- Packaging: tools/package_game.py validates per-file+combined parse, extracts locale regex _() + parsed say/menu/define, creates ACCESSIBILITY.md/json, copies engine/bge_frontend/blend/tools + game/scripts → build, run.py uses Path(__file__).parent absolute (works from any cwd), build_info.json hash, playable_check 59 events, zip 308KB, dist/locale/template.pot+json 36 strings
- Declarative language (M15): `state:` → defaults+types (VNState.declared_types), `character e:` block, `image/audio/stage` → VNState.assets (+resolve_asset), `set` canonical assign (typed-checked), `choice` keyword + optional `end`; expr_eval.py AST whitelist (no eval escapes); pointer.py hotspot hover/click for editor UI; menu choices carry stable `id`s
