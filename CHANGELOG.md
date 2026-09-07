# Changelog

## 0.1.0 — 2026-09-07 Tier 1 Kinetic
- Initial scaffold: `engine/core`, `engine/script`, `engine/render`, `engine/ui`, `engine/audio`, `engine/save`, `bge_frontend`
- Direct .rpy parser (no YAML — answers question: Ren'Py does NOT use yaml/json internally)
- Interpreter coroutine + headless runner + golden-trace tests
- Examples 00-03 + The Question parity headless verified
- UPBGE 0.50 download + Ren'Py source inspection recorded in README
- Roadmap + command/spec docs + validator

## 0.2.0 — 2026-09-07 Engine Display & Validator
- M02 DONE: `engine/render/scene_manager.py` real `bge.texture.materialID/ImageFFmpeg` + transition durations, `sprite_renderer.py` POSITIONS + dissolve alpha tween, `stage_manager` LibLoad, `dialogue_box` typewriter dt, `bge_frontend.frontend` Always sensor + post_draw blf + dt
- Added `engine/render/headless_renderer.py` (Pillow 1280x720) simulating Layer0/1/2 + `tools/generate_engine_screenshots.py` engine-driven 109 PNGs (02_*, tq_*, verified via read_file)
- M03 Transitions: dissolve/fade awaitable via SceneManager.is_transition_done + controller block, verified via screenshot overlay alpha
- M05 Audio+Saves: AudioManager channels, play music trace for The Question, SaveManager JSON (no pickle) + test_save_load_roundtrip
- M06 Validator: `examples/11_syntax_error_gallery` 9 bad scripts, parser improved (define parens, label colon, menu choice colon single caption rule), `tests/test_parser_errors.py` 3 tests, `tools/validate.py` OK/FAIL — 19 tests green
- Polished hand-coded screenshots `tools/generate_screenshots_v2.py` 20 PNGs 1280x720 inspected (classroom windows, lecturehall, meadow) + engine screenshots cross-check
- Frontend typewriter 40cps + instant-reveal on click, rollback wheel-up, pause auto-advance

## 0.3.0 — 2026-09-08 History, Skip/Auto & Rollback
- M07 DONE: `engine/core/vn_state.py` seen_history + skip/auto flags, `vn_interpreter.py` history preserves raw/styled/stripped + strip_tags, interpolate [route]/[affection], `VNController.toggle_skip/auto` + skip-seen check + auto_delay 0.7s
- M08 DONE: `VNInterpreter` rollback_stack + rollback_labels_stack (deepcopy labels for N-step correctness), `VNController` rollback(N)/roll_forward(N) + _forward_stack/_forward_labels_stack, WHEELUP/DOWN handlers, N-step hash equality verified (tests/test_m07_m08.py 7 tests, total 26 passed)
- Long BGE jobs: `GenerateScreenshotsLong` start_process 5s (109 engine + 20 polished) inspected via read_file (02_00_say, 02_01_say etc.), blend/UPVN_Template.blend 96K via Blender 5.0.1 background
- Docs: ROADMAP M07/M08 → done, STATUS/CHANGELOG updated, NEXT M09/M10/M13

## 0.4.0 — 2026-09-08 Screens, ATL-lite & Hybrid 3D
- M09 DONE: `engine/ui/screen_manager.py` Screen base + 6 screens (History overlay backlog 20 stripped view, Save/Load modal slots 6 via SaveManager, MainMenu modal 5 choices, QuickMenu overlay 7 buttons, Preferences modal), ScreenManager register/show/hide/is_modal_active/get_overlays/handle_key H/Q/ESC, VNController modal blocking + H/Q toggles, headless_renderer draw_history/quick/save/main_menu overlays, 6 tests test_screens.py, screenshots m09_*.png (history save mainmenu quickmenu)
- M10 DONE: `engine/atl/easing.py` warpers (linear/ease/easein/out), parser `camera zoom 1.2 [duration 1.0] [with ease]` (`_re_camera_zoom`), interpreter show with move/ease lerp (move_from/to/t0/duration/easing) + camera_zoom _zoom_* fields, `engine/render/sprite_renderer.py` get_interpolated_position + BGE worldPosition lerp, `stage_manager.py` camera_zoom lerp + get_current_zoom/is_zoom_done, headless_renderer move blur (draw_sprite_at_x) + ZOOM badge + easing, 5 tests test_atl_lite.py, screenshots m10_{move,zoom}_{mid,end}.png
- M13 DONE: `engine/render/headless_renderer.py` draw_stage (floor/perspective grid/wall + 3D capsules for show3d + marker labels), hybrid rendering (2D sprites over 3D stage, no black fallback, stage STAGE: label + CAM badge), `engine/script/parser.py` + `vn_interpreter.py` load_stage/show3d/anim/camera_preset already, StageManager hybrid update verified, 4 tests test_hybrid.py, screenshots m13_hybrid.png / m13_hybrid_move.png / m13_stage_only.png showing stage_only not black and hybrid coexistence
- Headless gate: 41 tests passed (26→32→37→41), VNController rebinds screen_mgr/sprite/stage for run_headless fresh_state, stage_mgr.update + sprite_mgr.update per frame (BGE + headless), long screenshot generation via start_process (long_m09/m10/m13 8s + 5s sleep) verified
- Docs: ROADMAP M09/M10/M13 → done, STATUS updated (41 tests, next M14 Ship)

## 0.4.1 — 2026-09-08 Arbitrary Saves + Blender Editor Tools (minimal coding)
- **Arbitrary save slots:** `engine/save/save_manager.py` extended with `list_slot_ids()`, `next_available_slot()` (1..∞), `slot_exists()`, `get_slot_info()`, `delete()` — any int slot 1..∞ (not 6), pagination demo saves to 12345; `engine/ui/screen_manager.py` SaveScreen/LoadScreen now arbitrary (page/page_size 6, `list_page_slots()`, `slots` property dynamic, `next_page()/prev_page()`, handle_key ←→/n/p pagination, save_to_slot/load_from_slot any int), `engine/render/headless_renderer.py` save overlay pagination (“Arbitrary slots 1..∞ • page N • ←→ to paginate”, page param, LOAD shows only existing, SAVE shows continuous range), 3 tests `tests/test_arbitrary_saves.py` (arbitrary 1..12345, pagination, builder)
- **Blender editor tools — minimal coding:** `blend/upvn_editor_addon.py` (bl_info Blender 5.0, View3D + Text Editor UPVN panels, 9 operators: Create Project, Add Character/Scene/Dialogue/Show/Menu, Validate, Preview, Save Demo; properties project_path/char_id/name/color/bg/speaker/dialogue/show_pos/trans/menu; register/unregister, HAS_BPY headless fallback), `UPVN_GameBuilder` API (add_character/scene/show/hide/say/menu/jump/camera_zoom/stage/show3d, build_rpy/write/validate/preview_screenshot), `tools/upvn_game_creator.py` (quick_game 3-line API + demo_arbitrary_saves, headless without bpy), `examples/99_creator_demo` generated via builder, `screenshots/test_arbitrary_save.png` pagination page 83 shows slot 500
- Headless gate: **44 tests passed** (41→44), long screenshots via start_process still used (long_m09/m10/m13 + arbitrary pagination)
- Docs: README “Quickstart (in UPBGE — minimal coding)” + blend/README Editor add-on section, ROADMAP M11 done + M09 updated arbitrary, STATUS 44 tests

## 0.5.0 — 2026-09-07 M14 Ship — packaging, localization, accessibility, 30-min showcase
- **Ship:** `tools/package_game.py` 522 lines — `validate_project` per-file+combined parse, `extract_locale` regex `_()` + parsed say/menu/define → `dist/locale/template.pot+json` 36 strings + 4 char names, `create_accessibility_manifest` keyboard (SPACE/ENTER/LEFTMOUSE, WHEELUP/DOWN, H/Q/S/Ctrl+S) + text 40cps + arbitrary saves 1..∞ + hybrid 3D → `dist/ACCESSIBILITY.md+json`, `ensure_showcase` 8 labels (start/library/book_taken/book_left/classroom/good_ending/neutral_ending/rollback_demo, all features), `package_project` copies engine/bge_frontend/blend/tools→build + game/scripts→build/game + launcher `build/run.py` **absolute Path(__file__).parent** (works from any cwd fallback multi-file) + `README_PLAY.txt` 36 strings + `build_info.json` hash 5a26c72e1404 + `playable_check.txt` 59 events + `saves/` + zip 308KB (`dist/10_full_sample_game.zip` 76 files)
- **Fixes in packager:** `import textwrap` missing (NameError) fixed, `ensure_showcase` empty-dir handling (need_showcase checks rglob *.rpy not just exists), `run.py` Path fix (was `game/script.rpy` relative to cwd → now absolute), README/build_info locale count (was `len(glob pot)` =1 → now json count 36), typo sysems→systems
- **Showcase:** `examples/10_full_sample_game/script.rpy` 4.2K, 8 labels, exercises say/Character/scene/show/hide with move/ease, menu/jump/$/if, camera zoom 1.2/1.5/1.0 with ease/linear, play music/sound, pause, load_stage/show3d/anim/preset hybrid, arbitrary saves 42/500, rollback demo, validated 59 events trace 22 history, headless `python dist/10_full_sample_game/run.py --choices 0 0 0` Good ending Affection 2, ` --choices 1` neutral, absolute cwd verified via `/tmp`
- **Long verification:** `GenerateScreenshotsLong` start_process 10s `startup_wait` → engine 109 PNGs + showcase 27 PNGs (`screenshots/showcase/showcase_*` 27, bg classroom/lecturehall/meadow+3d, menu, ZOOM 1.46x CAM closeup, hybrid 2D over 3D capsules verified via read_file showcase_02_say/05_menu/15_say/24_say) + http preview 8011 `python -m http.server 8011 --directory screenshots`, no HTML mock, inspected via read_file
- Headless gate: 44 tests passed (regression), ROADMAP M14 → done, STATUS M14 ship, NEXT publish zip + LibLoad real mesh
- Docs: ROADMAP M14 detailed acceptance, STATUS 2026-09-07 21:09 M14 ship, dist/ verified `ls -R` 76 files, `cat` POT/ACCESSIBILITY/build_info
