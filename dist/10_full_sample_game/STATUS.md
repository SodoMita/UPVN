# Current Status — 2026-09-07 21:20 (M14 ship + 0.5.1 polish)

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
- **0.5.1 Polish DONE (2026-09-07 21:20):** editor v0.5 preserve `_existing_text` merges defines+label lines (not overwrite, asset browser `bg_image`/`sprite_image` FILE_PATH copies to assets, `side_image`, `stage_name`+Add Stage, `arbitrary_slot` 1..999999 + Preview Arbitrary), `headless_renderer draw_stage` classroom_3d desks (board + teacher desk + 3 rows student desks + chairs + shadows, 36K hybrid), `StageManager load_stage/show3d/anim/camera_preset` with LibLoad + `addObject` + `playAction`, `make_template.py` richer VN_3DStage (floor+3 markers+3 presets+9 desks+board+capsules) — blend will be 150KB+ when regenerated (libpulse required, headless already proves desks), builder preserve test PASS (e+s + Hello first/second), quick_game validate OK, showcase regenerated 27 PNGs with desks, zip now 324KB, 44 tests green

## Currently failing / todo
- None blocker — M00-M14 + 0.5.1 polish done, 44 tests green, packaging 324KB, showcase 27 PNGs with desks. Polish only:
- blend/UPVN_Template.blend still 96K (old) — new `tools/make_template.py` would produce 150KB+ with desks/board/markers/presets when run in UPBGE with libpulse (./upbge-0.50-linux-x64/blender --background --python tools/make_template.py failed libpulse.so.0 missing in sandbox; headless desks already verified via polish_00_hybrid.png)
- DLC perf: 44 tests + 109+20+27 showcase <1s headless, zip 324KB
- Optional: publish 10_full_sample_game.zip as release, side images/sprite loops polish, asset browser preview thumbnails

## Recommended next task
- Publish: `dist/10_full_sample_game.zip` 324KB as release + CI pytest + package_game (0.5.1 polish)
- Next features if requested: side images live preview in editor, sprite loop `anim` preview, asset browser thumbnail grid, Blender regen of UPVN_Template.blend when libpulse available
- No MVP blockers — all Milestones M00-M14 + polish done

## Notes
- Parser requires 4 spaces, spaces not tabs, BOM stripped. Caption inside menu: bare quoted line — see SCRIPT_LANGUAGE_SPEC. Friendly hints for define/jump/menu/label. New: camera zoom 1.2 duration 1.0 with ease, show with move.
- Interpreter deep-copies labels for splicing; rollback also deep-copies labels; show with move sets move_from/to/easing/0.5s lerp, camera zoom sets _zoom_*.
- Headless gate: `VNController.run_headless(choices=[...])` + `pytest` 44 passed; screenshots via headless_renderer (109 + 20 + 27 showcase + polish desks + arbitrary pagination) inspected via read_file (no HTML mock)
- UPBGE tarball at ~/upbge-0.50-linux-x64.tar.xz (390 MB) — LD_LIBRARY_PATH pulse fix, long start_process with startup_wait used per instruction (long_m09/m10/m13 + showcase engine+showcase + arbitrary pagination, http 8011 preview)
- Ren'Py source at ~/renpy_src for reference only; no code copied. Easing module engine/atl/easing.py mirrors Ren'Py warpers.
- Screen system: engine/ui/screen_manager.py overlay vs modal, pagination arbitrary slots 1..∞ (page/page_size 6, list_page_slots, ←→/n/p), SaveManager.list_slot_ids/next_available_slot/slot_exists/get_slot_info/delete, VNController modal blocking, H/Q/S/L/ESC + ←→ for pagination.
- Blender editor: blend/upvn_editor_addon.py v0.5 (UPVN_GameBuilder preserve + asset browser bg_image/sprite_image FILE_PATH + side_image + stage_name + arbitrary_slot + Preview Arbitrary, 12 operators + 2 panels), tools/upvn_game_creator.py quick_game 3-line minimal coding, examples/99_creator_demo generated, UPVN_GameBuilder validates/previews headlessly without bpy.
- Hybrid: state.stage + stage_objects + camera preset/zoom, headless_renderer draw_stage floor+wall+capsules+desks/board, 2D sprites over 3D, VNController stage_mgr.update per frame, StageManager LibLoad + addObject + playAction + camera lerp.
- Packaging: tools/package_game.py validates per-file+combined parse, extracts locale regex _() + parsed say/menu/define, creates ACCESSIBILITY.md/json, copies engine/bge_frontend/blend/tools + game/scripts → build, run.py uses Path(__file__).parent absolute (works from any cwd), build_info.json hash, playable_check 59 events, zip 324KB, dist/locale/template.pot+json 36 strings
- Polish v0.5.1: editor preserve test tmp project e+s + Hello first/second PASS, headless desks polish_00_hybrid.png ZOOM 1.50x behind 2D sprite, stage_only with desks+wall, make_template richer but requires UPBGE libpulse for actual .blend regen
