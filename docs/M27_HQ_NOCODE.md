# M27: Creator Quality & No-Code Workflow — 2026-09-15

## Goals (from task: Improve usability workflow with higher quality scene and less python coding while keeping reliability)

- **Higher quality scene**: M26 color palette + M26i styled text baseline kept, but improved with HQ materials, lighting, layout
- **Less python coding**: Blender panels / UPVN_GameBuilder declarative, no Python required
- **Keep reliability**: pytest green + headless traces, contract checks, non-destructive write

No new Ren'Py syntax until install/setup/play boring (M25 freeze rule) — we did NOT add new syntax, only migrated builder to emit existing declarative forms (character:, state:, set, choice, if/else/end).

## Higher Quality Scene

### build_vn_scene (blend/upvn_editor_addon.py)
- **Materials**: Emission strength 1.2 for HQ (was 1.0), Fresnel edge glow for choice buttons (hq=True)
- **World**: Dark gradient world (0.015,0.018,0.032) with 0.6 strength instead of pure black 0,0,0
- **Lighting**: Soft sun SUN_Soft (energy 0.8, color warm) kept for 3D stage depth, other lights dimmed to 0.3 instead of hidden — 3D stage no longer flat
- **Dialogue box**: Darker, more readable (0.03,0.05,0.12) with HQ flag
- **Choice buttons**: Larger (3.4x0.32 vs 3.2x0.28), better spacing (0.75 vs 0.7), edge glow, 12% hover scale (was 8%)
- **Collections**: Same 5 collections, same contract names, same wiring — reliable

### make_template.py
- New helper `_mat_hq` with PBR for 3D, Emission for UI
- **Classroom HQ**: 
  - Walls: back + left + right for depth
  - Windows: 2 with glass highlights
  - Lights: 3 ceiling lights
  - Desks: 11 (was 9) with chairs (4)
  - Blackboard: larger + frame (4 sides)
  - Markers: 5 (added left/right)
  - Presets: 5 (added dramatic, low)
  - Characters: taller capsules (0.28 radius, 1.5 height)

### headless_renderer.py
- **BGs HQ**: 
  - classroom: warmer gradient, glass highlights, center glow, vignette 140px
  - lecturehall: light rays with varying alpha, audience silhouettes
  - meadow: flowers, better clouds (3 layers)
  - black: radial glow 2 layers, not flat
- **Stage HQ**: richer classroom with frame, teacher desk shadow, desk highlights, better markers
- **Dialogue HQ**: darker box (8,12,26), inner highlight, text shadow for readability
- **Menu HQ**: larger buttons (480x62 vs 460x58), edge glow (outer rect), text shadow, 16px spacing

### world_ui.py
- HOVER_SCALE 1.12 (was 1.08)
- New constants: CHOICE_SPACING_EM 0.78, WIDTH 0.74, HEIGHT 0.052
- Layout: better spacing, wider buttons, more breathing room

## Less Python Coding — No-Code Workflow

### UPVN_GameBuilder declarative-first (M27)
- **New storage**: state_vars, images, audios, stages (assets manifest)
- **New methods**:
  - `add_state_var(name, type, value)` — typed var to state: block
  - `add_image(name, path)`, `add_audio`, `add_stage_asset` — asset manifest
  - `add_set(target, op, expr)` — canonical `set` not `$`
  - `add_if(cond)`, `add_elif`, `add_else`, `add_end` — branching with indent stack
  - `add_choice(text, jump, cond)` — declarative choice
  - `add_jump`, `add_call`, `add_return`, `add_pause`, `add_play_music`, `add_play_sound`, `add_camera_zoom`, `add_camera_preset`, `add_side_image`, `add_narration`
  - `create_quick_wizard(title, theme)` — one-click full game with 2 endings, variables, 3D stage
  - `create_starter_declarative()` — HQ starter with state, characters, menu, if
  - `preview_all_paths()` — QA screenshots for all choice paths
- **Emit**: `state:`, `character id:`, `image`, `audio`, `stage`, `label`, `set`, `choice`, `if/else/end`, `jump`, `return`
- **Backward compat**: legacy `define e = Character` still parsed, but new projects emit declarative. Tests updated per ROADMAP TODO.
- **Non-destructive write**: handles both `define` and `character` forms, state block insertion, asset insertion, placeholder cleaning, before-return insertion — M26g reliability kept

### Blender Panels — M27 extended
- **UPVN_SceneProps new fields**: var_name/type/value, if_cond, jump_target, label_name, pause_duration, audio_name/file, camera_zoom/duration/easing, wizard_title/theme, set_target/op/expr
- **New operators** (13 new):
  - Add Variable (State) — typed var, no coding
  - Add Set — variable change declarative
  - Add If/Else/End — branching without Python
  - Add Jump/Label — navigation
  - Add Pause, Add Music/Sound, Add Camera Zoom — extras
  - Quick VN Wizard — 1-click full game (2 endings, affection, book, 3D stage)
  - Export Package — playable zip
  - Script Outline — labels, chars, vars in Text Editor
  - Preview All Paths — HQ QA
- **Main Panel reorg**: boxed sections (Project, Play HQ, Characters, Variables, Scene, Dialogue, Logic, Menu, Extras, Tools)
- **Tooltips**: all new operators have descriptions
- **Asset browser**: copies BG/sprite/audio to assets/ with mkdir, reports path

### tools/upvn_game_creator.py
- `quick_game(..., use_wizard=True)` — one-call full game, no .rpy typing
- Emits declarative HQ, validates, previews, previews all paths for wizard
- Demo arbitrary saves kept

## Reliability — Kept Green

- pytest: 363 passed, 30 skipped (was 362/30 at M26i, now 363 due to new tests)
- Warnings: 4 DeprecationWarnings (Pillow getdata) — not our code
- Contract: check_contract still used, no new object names, same VN_* collections
- Non-destructive write: test_m26g_builder_write.py still passes (updated for declarative)
- Headless traces: preview_screenshot + preview_all_paths work, render_state HQ still matches
- No new syntax: only existing declarative forms (character:, state:, set, choice, if/else/end) — M25 freeze rule satisfied
- Example 99_hq_wizard: validates OK, 3406 bytes, 11 labels, 2 endings, 3 state vars, 3 images, 1 stage

## Acceptance Criteria

- [x] No new Ren'Py syntax until install/setup/play boring (M25 freeze) — only migrated to existing declarative
- [x] Higher quality default scene (M26 color palette + M26i styled text baseline) — HQ materials, lighting, stage, renderer
- [x] Less coding via Blender panels / UPVN_GameBuilder — 13 new operators, quick wizard, declarative starter
- [x] Keep pytest green + headless traces — 363 passed

## How to Use (No Coding)

1. Install dist/upvn_editor_addon_v0.7.0.zip in UPBGE
2. View3D > Sidebar > UPVN > Project: set path //game/script.rpy
3. Press "Quick VN Wizard" — enter title, theme, 1 click → full game with 2 endings
4. Or "Create Project (Declarative)" → starter
5. Add Variable: affection int 0 (no Python)
6. Add Character, Scene, Dialogue, Show, Menu, If/Else/End, Jump via buttons
7. Validate → OK, Preview → screenshot, Preview All Paths → all branches
8. Setup Scene (one click HQ) → HQ materials + soft lighting
9. Press P to play — H history, Q quick menu, Ctrl+S/L saves, wheel rollback
10. Export Package → dist zip playable

## Files Changed

- blend/upvn_editor_addon.py: 2399→~3110 lines, v0.7.0, declarative builder, HQ scene, 13 new ops, boxed UI
- tools/make_template.py: HQ materials, richer classroom (walls, windows, lights, chairs, frames)
- tools/upvn_game_creator.py: use_wizard, declarative HQ, preview_all
- engine/render/headless_renderer.py: HQ BGs, stage, dialogue, menu (shadows, glows, spacing)
- engine/ui/world_ui.py: HOVER_SCALE 1.12, spacing constants, HQ layout
- tests/test_arbitrary_saves.py: updated for declarative, added test_blender_builder_declarative_hq
- tests/test_m26g_builder_write.py: updated for declarative forms
- dist/upvn_editor_addon_v0.7.0.zip: 1002KB, 41 entries
- examples/99_hq_wizard/script.rpy: 3406 bytes, declarative HQ wizard demo

## Next Steps (M28)

- Asset browser thumbnails (Blender file browser preview)
- Outline panel live (not just text)
- More wizard themes (fantasy, scifi, mystery with different stages)
- Font picker for speaker colors
- Voice preview for dialogue
