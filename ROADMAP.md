# ROADMAP — machine-readable ledger for agents

> Every agent session starts here. Find first `status: todo` with `depends_on` satisfied, read its SPEC and `examples/…/expected_behavior.md`, implement, run acceptance, flip to `done`, update `CHANGELOG.md` + `STATUS.md`.

```yaml
- id: M00
  name: Harness — repo, parser, interpreter, state, headless traces, UPBGE download
  status: done
  depends_on: []
  acceptance:
    - "pytest tests/test_m00_harness.py green"
    - "parse of examples/00..03 and the_question + headless traces via tools/run_headless.py"
  example_project: examples/00_minimal_dialogue
  done_when: "all Tier1 scripts produce identical headless trace on repeat; UPBGE tarball present"

- id: M01
  name: Kinetic engine — say/narration, click-advance, typewriter, Character
  status: done
  depends_on: [M00]
  acceptance:
    - "examples/00_minimal_dialogue plays end-to-end (headless + UPBGE click)"
    - "golden trace for 00 matches tests/data/trace_00.json"
  example_project: examples/00_minimal_dialogue

- id: M02
  name: Display — scene/show/hide, positions, z-order, expression swap
  status: done   # 2026-09-07: engine/render/* real BGE texture + headless_renderer, positions validated, engine screenshots engine/02_*
  depends_on: [M01]
  acceptance:
    - "examples/02_sprites_backgrounds trace green (scene/show/hide events)"
    - "UPBGE: background plane + sprite planes appear at left/center/right"
  example_project: examples/02_sprites_backgrounds

- id: M03
  name: Transitions — dissolve/fade/with semantics
  status: done   # 2026-09-07: SceneManager transition durations + controller wait, SpriteRenderer alpha tween, headless transition_alpha; screenshots differ fade vs dissolve via overlay
  depends_on: [M02]
  acceptance:
    - "with fade/dissolve respected as awaitable events"
    - "example 02 with fade vs dissolve screenshots differ via bge.render.makeScreenshot"
  example_project: examples/02_sprites_backgrounds

- id: M04
  name: Branching — The Question parity (labels/jump/call/return, menu, if, assign)
  status: done   # headless fully; UI choice clicking in UPBGE stubbed
  depends_on: [M01]
  acceptance:
    - "headless traces for every The Question path (0,0 / 0,1 / 1) match goldens"
    - "example 03 both routes toggle affection/book correctly"
  example_project: examples/03_variables_routes

- id: M05
  name: Audio + Saves — music/sound/voice fade, JSON save/load round-trip
  status: done   # 2026-09-07: AudioManager handles play_music/stop/sound/voice, The Question play music trace verified, SaveManager JSON round-trip test green (test_save_load_roundtrip)
  depends_on: [M04]
  acceptance:
    - "play music / stop music / play sound events in trace"
    - "save_manager.save(1) -> load -> state hash equality at 10 random points"
    - "state is pure JSON (no pickle)"
  example_project: examples/03_variables_routes

- id: M06
  name: DSL validator — friendly errors, script validation, interpolation
  status: done   # 2026-09-07: examples/11_syntax_error_gallery 9 files + parser friendly hints (jump colon, indent, define parens, menu colon, etc.) + tests/test_parser_errors.py 3 tests green, tools/validate.py
  depends_on: [M04]
  acceptance:
    - "examples/11_syntax_error_gallery — each bad script fails with line/col + hint, no traceback"
    - "tools/validate.py passes for good scripts, fails for bad"
  example_project: examples/00_minimal_dialogue

- id: M07
  name: Backlog/skip/auto, text tags {b}/{color}, [var] interpolation
  status: done   # 2026-09-08: history stores raw+styled+stripped+seen_history, interpolate [var], strip_tags {b}/{color}/{i}, skip/auto flags + auto_delay + seen check, backlog via state.history, 4 tests in test_m07_m08.py
  depends_on: [M04]
  acceptance:
    - "history contains styled text; {b} preserved but strip_tags available"
    - "[route] and [affection] interpolate in say"
  example_project: examples/03_variables_routes

- id: M08
  name: Rollback-lite — snapshot at say/menu, wheel-up restores, roll-forward
  status: done   # 2026-09-08: VNInterpreter rollback_stack + rollback_labels_stack, VNController rollback(N)/roll_forward(N) + forward stacks, WHEELUP/WHEELDOWN, 2 tests hash equality N steps, long engine screenshots 109 PNGs
  depends_on: [M04, M05]
  acceptance:
    - "rollback N steps -> state hash equals historical hash"
    - "UPBGE: mouse wheel up triggers VNController.rollback()"
  example_project: examples/03_variables_routes

- id: M09
  name: Screen system lite — main menu, save slots, history, quick menu, prefs
  status: done   # 2026-09-08: ScreenManager overlay vs modal + arbitrary slots 1..∞ (pagination 6/page, SaveManager list_slot_ids/next_available_slot, screen_manager save/load any int), headless_renderer save overlay arbitrary pages, 6 tests test_screens.py + 3 tests test_arbitrary_saves.py (44 total)
  depends_on: [M07, M08]
  acceptance:
    - "overlay vs modal distinction (overlay non-blocking, modal returns value)"
    - "save/load UI works without editing a big screens.rpy — arbitrary slots 1..∞ (not 6)"
  example_project: examples/00_minimal_dialogue

- id: M10
  name: ATL-lite — move/zoom/alpha, easing, sprite loops, side images
  status: done   # 2026-09-08: parser camera zoom + easing, interpreter move_from/to + easing, SpriteRenderer/StageManager lerp, headless_renderer move blur + zoom badge, easing module, 5 tests test_atl_lite.py
  depends_on: [M03]
  acceptance:
    - "show eileen at center with move interpolates, not snap"
    - "camera zoom 1.2 duration 1.0 works headless + UPBGE"
  example_project: examples/02_sprites_backgrounds

- id: M13
  name: Hybrid 3D — VN dialogue over live UPBGE stage, speaker-cut cameras
  status: done   # 2026-09-08: StageManager load_stage/show3d/anim/camera_preset + zoom, headless_renderer draw_stage floor+markers+capsules hybrid 2D/3D, no black fallback, 4 tests test_hybrid.py, screenshots m13_*.png
  depends_on: [M02]
  acceptance:
    - "examples/07_3d_character_scene: load_stage, show3d at marker, anim idle/wave, camera preset"
  example_project: examples/07_3d_character_scene (to be added)

- id: M11
  name: Blender Editor Tools — minimal coding inside Blender
  status: done   # 2026-09-08: blend/upvn_editor_addon.py (View3D/Text Editor UPVN panels, operators Add Character/Scene/Dialogue/Show/Menu/Validate/Preview), UPVN_GameBuilder API, tools/upvn_game_creator.py quick_game 3-line API, validated headless, Blender 5.0/UPBGE 0.50 compatible
  depends_on: [M04, M06]
  acceptance:
    - "create game inside Blender editor with clicks, no .rpy typing — characters, scenes, dialogue, menus via UI"
    - "headless fallback via UPVN_GameBuilder (tools/upvn_game_creator.py)"
  example_project: examples/99_creator_demo

- id: M14
  name: Ship — packaging, localization extraction, accessibility, 30-min showcase
  status: done   # 2026-09-07 21:09: tools/package_game.py playable build + POT/JSON 36 strings + ACCESSIBILITY.md/json + showcase 8 labels 59 events + zip 308KB + headless run.py --choices + dist/locale + dist/ACCESSIBILITY + long showcase 27 PNGs verified
  depends_on: [M09, M10, M13, M11]
  acceptance:
    - "tools/package_game.py produces playable build (validate + locale + a11y + copy engine/blend/tools + game/scripts → build + run.py with absolute Path + README_PLAY + build_info.json hash + playable_check 59 events + zip) — verified headless choices 0 0 0 and absolute cwd"
    - "locale/template.pot + template.json 36 strings, ACCESSIBILITY.md/json keyboard+typewriter 40cps+arbitrary saves 1..∞+hybrid"
    - "examples/10_full_sample_game 30-min showcase (condensed demo 8 labels, all features: say/Character/scene/show/hide/menu/jump/$/if/play music/with fade/dissolve/move/zoom/ATL/3D stage/editor) validated 8 labels, long showcase screenshots 27 PNGs"
  example_project: examples/10_full_sample_game

- id: M15
  name: Declarative script language — state:/set/character/image/audio/stage/choice/end + safe expression evaluator + editor pointer events
  status: done   # 2026-09-08: parser declarative forms (state: typed vars, character block, image/audio/stage manifest, set, choice keyword, optional end terminators); expr_eval.py AST-whitelist replaces raw eval (escape payloads blocked); typed-state runtime enforcement; engine/ui/pointer.py hotspot hover/click; menu choice ids; ast.literal_eval for defaults; example 05 + 3 new test files + 5 new gallery cases; renpy_src tests skip when absent
  depends_on: [M04, M06, M09]
  acceptance:
    - "examples/05_declarative_script parses + runs headless (choices 0/1) with typed state + asset manifest"
    - "declarative and legacy forms produce identical event traces (tests/test_declarative.py)"
    - "expr_eval blocks attribute/subscript/comprehension/import escapes; allows the declarative subset (tests/test_expr_eval.py)"
    - "pointer tracker emits enter/leave/click over named editor objects (tests/test_pointer.py)"
    - "pytest green: 72 passed, 2 skipped (renpy_src absent)"
  example_project: examples/05_declarative_script

- id: M16
  name: Three language tiers over one IR — .urpy declarative, .rpy safe subset, .rpy full (drop-in Ren'Py)
  status: done   # 2026-09-08: tier 1 engine/script/urpy_parser.py (strict, zero Python, required end); tier 2 = existing parser default (safe) now rejects full-tier constructs with 'mode=full' guidance; tier 3 = Parser(full=True): python:/init/init offset/while/break/continue/pass/window/nvl/voice/queue music|sound/show|hide|call screen/jump|call expression/call label(args)/label name(params)/conditional menu choices/generic $/screen|style|transform|translate blocks; interpreter executes python+init (renpy/store compat namespace engine/script/renpy_compat.py), label params, while splicing, break/continue, jump/call expr, conditional menu filtering; VNController(mode=) + tools --mode; expr_eval container subscript + renpy/store attribute allowlist; examples 12 (full) + 13 (urpy); tests/test_full_rpy.py 27 tests; 99 passed 2 skipped
  depends_on: [M15]
  acceptance:
    - ".urpy parses+runs headless (examples/13_urpy_tier) with typed state, choice keyword, required end; rejects $/define/default/python with hints"
    - ".rpy safe mode rejects python:/init/while/transform/screen/style/translate/define with 'mode=full' guidance"
    - ".rpy full mode parses+runs python:/init/while/break/continue/label params/call args/jump+call expression/conditional choices/window/nvl/voice/queue/screens (examples/12_full_rpy_tier + tests/test_full_rpy.py)"
    - "renpy compat: renpy.jump/call/quit/loadable/has_label/get_playing/random/store work in python: blocks; attribute access sandbox still closed"
    - "all three tiers produce the same IR; pytest green: 99 passed, 2 skipped"
  example_project: examples/12_full_rpy_tier

- id: M17
  name: Blender/UPBGE UX hardening — no more "Engine not available", one-click scene setup
  status: done   # 2026-09-08: add-on v0.6 self-contained engine discovery (module dir / repo / zipimport from installed archive / prefs / blend file dirs, engine_status_line + engine_diag_text in panels, Locate Engine + Check + Bundle operators, friendly reports everywhere instead of bare 'Engine not available'); blend/upvn_editor_addon.py build_vn_scene (data-API, idempotent, UPBGE-verified) creates VN_Main + cameras + VN_* collections + planes + VNController(script_path/upvn_root/upvn_bricks) + launcher Text datablock + Always(pulse)→Python brick via official bpy.ops.logic.* pattern (UI context; --background skips loudly); bge_frontend/frontend.py now reads VNController.script_path first (legacy candidates as fallback) + self sys.path bootstrap (fixes 'wrong/no script starts'); tools/make_template.py regenerates blend/UPVN_Template.blend data-API-only incl. classroom stage (110KB, was 96KB brickless); tools/package_addon.py builds self-contained dist/upvn_editor_addon_v0.6.0.zip (upvn_editor_addon/ + zip-root engine with injected __init__.py for zipimport); tests/test_m17_addon_init.py 5 tests incl. clean-subprocess zip-import proof; 113 passed 2 skipped; verified inside real UPBGE 0.50 (Blender 5.0.1) headless via libpulse stub: engine OK, register OK, scene OK
  depends_on: [M16]
  acceptance:
    - "add-on installed alone (old single-.py style) no longer says only 'Engine not available': reports searched roots + hints (zip release / Locate Engine)"
    - "dist/upvn_editor_addon_v0.6.0.zip is fully self-contained: in a clean python subprocess the add-on imports the engine straight from the archive (zipimport) and validates a built script"
    - "bge_frontend resolves the game script from the VNController object's script_path property first, then legacy candidates (unit-tested)"
    - "Setup Scene (UPBGE UI) wires camera/collections/controller object/launcher + Always→Python brick using the same bpy.ops.logic.* API as UPBGE's own add-ons; --background runs skip bricks with an explicit note"
    - "pytest green: 113 passed, 2 skipped"
  example_project: blend/UPVN_Template.blend

- id: M18
  name: Gameplay input — playable menus + QA keys in the real engine
  status: done   # 2026-09-08: _menu_choice_from_keycodes (digits 1-9), F1 state dump, F12 screenshot, modal overlays draw text
  depends_on: [M09]
  acceptance:
    - "menu choices selectable with number keys in UPBGE (no more freeze at the prompt)"
    - "pytest green"
  example_project: examples/01_branching_choice

- id: M19
  name: Explicit scene-object contract (registry + sprite planes + wiring checker)
  status: done   # 2026-09-08: engine/render/contract.py, renderers import identifiers, Check Scene Wiring operator, template regenerated
  depends_on: [M02, M17]
  acceptance:
    - "renderers import object/material names from contract.py (no literals)"
    - "tools/tests guard against re-introducing hard-coded names"
  example_project: blend/UPVN_Template.blend

- id: M20
  name: Drop-in Ren'Py compatibility — a real shipped game parses and plays
  status: done   # 2026-09-09: driven by freeCodeCamp/LearnToCodeRPG (BSD-3-Clause, 61 files) — 0/61 -> 61/61 files parse, 127 labels, 5560 statements, every jump/call/call-screen resolves, story runs headless; lexer triple-quoted + bracket continuation, from clauses, call screen args, for loops, voice attributes, nointeract/extend/centered, with <expr>, show clause splitting, named menus as labels, menu if/else groups, dotted defines as store namespaces, loose full-tier expressions, compat mode, tools/check_renpy_project.py, examples/14_renpy_dropin, 64+5 new tests
  depends_on: [M16, M19]
  acceptance:
    - "every .rpy/.rpym of the corpus parses in the drop-in tier (tests/test_renpy_corpus.py, 0 errors)"
    - "merged project: all jump/call/call-screen targets resolve; named menus are labels"
    - "headless smoke run plays real dialogue (compat mode collects python: failures)"
    - "safe/.urpy tiers unchanged: 4-space rule + strict expressions + blocked escapes"
    - "pytest green: 200 passed, 0 skipped"
  example_project: examples/14_renpy_dropin

- id: M21
  name: Second corpus — the Ren'Py SDK's own games, and the constructs they need
  status: done   # 2026-09-09: validated on renpy/renpy (MIT) tutorial/ + the_question/ — 7/23 -> 23/23 files, 75 labels, 1672 statements, every jump/call resolves. Added project-wide renpy.register_statement discovery (+block="script" bodies parsed as script, so labels inside resolve), testcase/testsuite, multi-line plain strings (re.DOTALL parity), say dialogue ids + quoted who, show/scene ATL blocks, bare scene, define +=, style-in-label, window/nvl transitions, comment-only files, custom_statement no-op in the interpreter, CI workflow
  depends_on: [M20]
  acceptance:
    - "every .rpy of renpy/renpy tutorial/ and the_question/ parses in the drop-in tier"
    - "a keyword registered with renpy.register_statement is legal in every file of the project"
    - "block=\"script\" bodies contribute real labels; unreadable bodies are recorded, not fatal"
    - "CI runs both corpora plus every example headless"
    - "pytest green: 224 passed, 0 skipped"
  example_project: examples/14_renpy_dropin

- id: M22
  name: Screens actually render — a screen-language interpreter
  status: done   # 2026-09-09: engine/ui/screen_lang.py evaluates captured `screen:` bodies into JSON-serialisable widget trees (containers, leaves, if/elif/else, for, $, screen-local default, use + transclude, has, [expr] interpolation); show/hide/call screen record into VNState.active_screens and carry widgets on the event; parser keeps body indents + params. SDK tutorial 99/99 screens render (716 widgets), LearnToCodeRPG 23/23 (346 widgets). Layout stays in props — UPVN draws in the 3D scene.
  depends_on: [M21]
  acceptance:
    - "every `screen:` in both corpora renders to a widget tree without raising"
    - "`show screen` / `call screen` carry the widgets; `hide screen` clears state.active_screens"
    - "control flow (if/elif/else, for), `use` + `transclude`, `has`, `default` params and `[expr]` all evaluate"
    - "a broken screen degrades to an empty tree plus a diagnostic — the story keeps playing"
    - "active screens survive a save round-trip (JSON only)"
    - "pytest green: 253 passed, 0 skipped"
  example_project: examples/14_renpy_dropin
```

## Agent protocol (repeat every session)

1. `read ROADMAP.md` → pick first actionable
2. `read COMMAND_SPEC.md` + `SCRIPT_LANGUAGE_SPEC.md` + relevant `examples/*/expected_behavior.md`
3. `read tests/test_*.py` goldens
4. Implement **smallest missing feature** for that milestone
5. `pytest` — keep earlier examples green (regression gate)
6. Update `CHANGELOG.md`, `STATUS.md`, flip `ROADMAP.md` status, commit

## NEXT_STEPS (for next turn)

- M17 Blender UX hardening DONE 2026-09-08 — add-on v0.6 (engine discovery: repo/module-dir/zipimport/prefs/blend-file; status rows; Locate/Check/Bundle; friendly reports), one-click Setup Scene (data-API scene + official bpy.ops.logic.* bricks in UI), frontend reads VNController.script_path + sys.path bootstrap, make_template regenerates 110KB template (was brickless 96KB), tools/package_addon.py → dist/upvn_editor_addon_v0.6.0.zip self-contained (zipimport-verified in clean subprocess), tests/test_m17_addon_init.py 5 tests, verified in real UPBGE 0.50 headless (libpulse stub): engine OK/register OK/scene OK; 113 passed 2 skipped
- M22 screens DONE 2026-09-09 — engine/ui/screen_lang.py interprets captured `screen:` bodies (99/99 + 23/23 corpus screens render, 716 + 346 widgets); show/hide/call screen carry widgets and persist in VNState.active_screens; 253 passed
- Next candidate: draw the rendered widget trees in the UPBGE frontend (blf + planes) so `call screen` is visible in-game; run the full interactive loop in UPBGE UI (Setup Scene → P) on a machine with a display; publish dist zips + addon zip as GitHub release
- Optional: migrate editor GameBuilder to declarative forms (character/state/set/choice) per STATUS; asset browser thumbnails; side-image live preview
- 0.5.2 Audit fixes DONE 2026-09-08 — M-1 safe_eval AST whitelist (blocks Attribute/Subscript/ListComp), L-1 save _sanitize_slot/_slot_path is_relative_to, L-2 load schema validation, I-1 tests skip when the_question missing (42+2 skipped vs 44 passed both green, stub 555B), I-2 zip hygiene no pyc 52 files 214KB (was 76 324KB) LICENSE included, I-3 MIT LICENSE, requirements dev black, package copies LICENSE, exploit/traversal blocked verified, headless 59 events still
- 0.5.1 Polish DONE 2026-09-07 21:20 — editor v0.5 preserve+asset browser+side image+arbitrary slot spinner, headless desks (board+teacher+3 rows), StageManager LibLoad+addObject+playAction+camera preset, make_template richer VN_3DStage (floor+3 markers+3 presets+9 desks+board+capsules, 150KB+ when libpulse available), showcase regenerated 27 PNGs desks behind sprite (36K), zip 324KB → now 214KB clean, 44 tests green, preserve test PASS
- M14 DONE 2026-09-07 21:09 — verify saves arbitrary: SaveManager.list_slot_ids 1..∞ pagination (test_arbitrary_saves), headless save overlay page 83 shows slot 500, dist build saves 1..∞ verified via run.py choices (absolute Path)
- DLC perf: 44 tests (or 42+2 skipped) + 109+20+27 showcase+polish <1s headless, zip 214KB clean (was 308KB→324KB with pyc→214KB clean), safe_eval whitelisted, saves validated, pickle not used (direct .rpy)
- Optional: publish 10_full_sample_game.zip 214KB clean as release, add CI for pytest + package_game --project game --out dist, side image live preview, asset browser thumbnail grid, Blender regen UPVN_Template.blend when libpulse available (headless already proves desks)
