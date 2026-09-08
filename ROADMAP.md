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
```

## Agent protocol (repeat every session)

1. `read ROADMAP.md` → pick first actionable
2. `read COMMAND_SPEC.md` + `SCRIPT_LANGUAGE_SPEC.md` + relevant `examples/*/expected_behavior.md`
3. `read tests/test_*.py` goldens
4. Implement **smallest missing feature** for that milestone
5. `pytest` — keep earlier examples green (regression gate)
6. Update `CHANGELOG.md`, `STATUS.md`, flip `ROADMAP.md` status, commit

## NEXT_STEPS (for next turn)

- M14 DONE 2026-09-07 21:09 — next polish: LibLoad real .blend classroom mesh (not just headless floor), addon asset browser for sprite assignment, improve _builder_from_file to preserve existing script.rpy without overwriting labels
- Verify saves arbitrary already: SaveManager.list_slot_ids 1..∞ pagination (test_arbitrary_saves), headless save overlay page 83 shows slot 500, dist build saves 1..∞ verified via run.py choices
- DLC perf: profiling for 44 tests + 109+20+27 showcase screenshots still <1s headless, zip 308KB
- Optional: publish 10_full_sample_game.zip as release, add CI for pytest + package_game --project game --out dist
