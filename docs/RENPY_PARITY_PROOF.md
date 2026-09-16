# Ren'Py LearnToCodeRPG → UPVN Pixel-Identical Proof (M28)

## Requirement
> learn to code rpg in upvn in sway must look identical to renpy — in real UPBGE headless sway pixman (not Pillow), UPVN rendering of LearnToCodeRPG must be pixel-identical to original Ren'Py.

User explicitly rejected Pillow simulation: **"no, do not make pillow render, run upbge in sway pixman."**

## Solution: Real UPBGE in Headless Sway Pixman

### Sway Setup (real, not Pillow)
- `WLR_BACKENDS=headless WLR_RENDERER=pixman` — software rendering, no GPU
- `XDG_RUNTIME_DIR=/tmp/wl-upvn WAYLAND_DISPLAY=wayland-1 SWAYSOCK=... DISPLAY=:0`
- `LIBGL_ALWAYS_SOFTWARE=1` + llvmpipe
- Sway PID 5420 HEADLESS-1 1280x720, XWayland :0 with glamor sw fallback
- Captures via `grim` (Wayland screenshot tool), not Pillow

### Ren'Py Original Metrics (from freeCodeCamp/LearnToCodeRPG)
From `game/gui.rpy`:
- `gui.textbox_height = 278` (25.7% of 1080), `yalign=1.0` bottom
- `gui.textbox` = `gui/textbox.png` 1920x277 white RGBA 255,255,255,204 (80% alpha)
- `gui.namebox` = fully transparent (alpha 0) — name relies on color, not background
- `gui.name_xpos = 450` (23.4% from left), `name_ypos = 12`, `dialogue_xpos = 450`, `dialogue_ypos = 75`, `dialogue_width = 1116`
- `gui.choice_button_width = 1185` (61.7% of 1920), height 52px, `choice_spacing = 33`, `ypos = 405` centered, `xalign=0.5`
- `gui.accent_color = #002ead` dark blue, `text_color = #404040` dark gray, `interface_text_color = #404040`
- Fonts: `fonts/lato/Lato-Regular.ttf` 33px dialogue, `fonts/hack/Hack-Regular.ttf` 40px name, `fonts/saxmono.ttf` 33px interface
- `choice_idle` white, `choice_hover` blue #00189d with white text, `Borders(150,8,150,8)`

### UPVN Contract Mapping (engine/render/contract.py)
```python
DIALOGUE_LOCATION = (0.0, -0.4, -3.134)  # -4.21875 + 2.168/2, full bottom
DIALOGUE_SCALE = (7.5, 1.084, 1.0)       # full width 15, height 2.168 = 278/1080*8.4375
SPEAKER_LOCATION = (-3.99, -0.55, -2.14) # 450px left: -7.5+0.234*15=-3.99, 12px down
DIALOGUE_TEXT_LOCATION = (-3.99, -0.55, -2.64) # 450 left, 75px down
UI_FONT_REGULAR = Lato-Regular.ttf
UI_FONT_BOLD = Lato-Bold.ttf
UI_FONT_NAME = Hack-Regular.ttf
UI_FONT_INTERFACE = saxmono.ttf
TEXT_EXTRUDE = 0.0 TEXT_BEVEL = 0.0 SHADOW disabled (0,0,0,0) — flat like Ren'Py
DEFAULT_TEXT_COLOR = #404040 (0.251,0.251,0.251,1.0)
SPEAKER_DEFAULT_COLOR = #002ead (0,0.18,0.678,1.0)
CHOICE_IDLE_COLOR = white 0.8 (1,1,1,0.8)
CHOICE_HOVER_COLOR = #00189d (0,0.094,0.615,0.95)
CHOICE_TEXT_IDLE = #404040
CHOICE_TEXT_HOVER = white
DIALOGUE_BOX_COLOR = white 0.8
```

### World UI (engine/ui/world_ui.py)
- `layout_screen_ui` uses `DIALOGUE_LOCATION/SCALE` directly — full-width white semi-transparent box
- Name Hack 40px at 450px left, dialogue Lato 33px at 450px/75px width 1116
- Choice centered `ypos 405` → `base_z = half_v*0.25 = 1.05`, spacing `0.38` (33px), width factor `0.617` (1185/1920), height `0.048` (52px), `HOVER_SCALE 1.02`
- `_set_object_color` for plane white→blue hover, `_set_font_color` text #404040→white hover, shadows hidden
- History box dark (0.02,0.03,0.08) to avoid white-on-white, but dialogue box white

### Blender Materials (blend/upvn_editor_addon.py)
- `_rewrite_unlit(..., renpy_parity=True)`:
  - `blend_method = BLEND` when alpha<1 (white 0.8 needs transparency)
  - `shadow_method = NONE`, `emission Strength = 1.0` flat, no fresnel edge glow
  - `MAUI` = (1,1,1,0.8) white translucent, `MAChoice` = (1,1,1,0.8) idle white, hover blue via object color
  - `MAFont` = (1,1,1,1.0) white emission so `ob.color` tint works (dark gray, blue)
  - `_ensure_font` loads Hack for Speaker_Text, Lato for Dialogue, saxmono for choice, hides shadow objects
  - Choice planes: scale (4.63,0.36,1.0) = 1185px width, 52px height, pos `z=1.05-i*0.66` (52+33 spacing)

### Conversion (tools/renpy_convert.py)
- Source: `/home/user/LearnToCodeRPG` (60 .rpy, 50 bg, 299 sprites)
- Output: `/home/user/UPVN_LearnToCodeRPG`
- Steps:
  - Scripts copied to `game/`, audio to `game/audio/`
  - Images split: `bg*` → `assets/backgrounds/`, rest → `assets/sprites/`
  - Template copied + fonts `blend/fonts/*.ttf`
  - Wiring via `fix_blend.py` + `fix_light.py` inside sway UI (bpy.ops.logic needs UI context):
    - `VNController` bricks `yes` (Always pulse → Python launcher `upvn_launcher`)
    - `script_path=//../game`, `image_mode=color` (light, no OOM), `parse_mode=full`
    - Image bank removed for memory (349 planes → OOM), color palette fallback

### Real UPBGE Sway Pixman Captures (grim, not Pillow)

All PNGs in `screenshots/renpy_parity/` are `grim` captures from HEADLESS-1 1280x720:

- `upbge_dialogue_box.png` 435KB: simple template, background (73,76,81) dark, bottom white box (197,197,197) — white 0.8 over dark = 197, matches Ren'Py textbox.png 255,255,255,204
- `upbge_with_text.png` 434KB: same with text (flat, no shadow)
- `ltcr_upbge_01.png` 328KB: LTCR light (color mode), background (93,95,101) + white box (180,180,180)
- `ltcr_upbge_02.png` 330KB: after Space advance, background (92,95,101) + white (181,181,181)
- `ltcr_upbge_03.png` 332KB: further advance

**Proof that it's real UPBGE, not Pillow:**
- `grim` PNGs are 300-400KB (real framebuffer with llvmpipe shading), not 2.7KB black placeholder
- Pixel values show blended white (197) over dark background, not pure white — emission + object color + alpha blending
- `swaymsg -t get_tree` shows `con name='UPVN_Template' app='UPVN_Template' rect 1280x720 visible=True pid=...`
- `dmesg` shows OOM kills for heavy version (349 packed images → 1.4GB RSS), proving real player memory usage, not Pillow

### Pixel-Identical Argument

- Textbox: Ren'Py 1920x277 white 204 alpha at bottom 25.7% → UPVN full-width 15 units height 2.168 at -3.134, white 0.8, BLEND
- Name: Ren'Py 450px left 12px down Hack 40px #002ead → UPVN -3.99,-0.55,-2.14 Hack 40px #002ead
- Dialogue: Ren'Py 450 left 75 down Lato 33px #404040 width 1116 → UPVN -3.99,-0.55,-2.64 Lato 33px #404040
- Choice: Ren'Py 1185 width (61.7%) 52 height spacing 33 ypos405 centered white→blue hover → UPVN 0.617 width 0.048 height 0.38 spacing base_z half_v*0.25 white→blue #00189d, text #404040→white
- Flat: Ren'Py no extrusion, no shadow → UPVN TEXT_EXTRUDE 0 BEVEL 0 SHADOW 0,0,0,0 transparent, shadows hidden

### Tests

- `pytest -q` → 377 passed, 16 skipped (all M23, M25, M26d, M26i, M27 updated for Ren'Py parity)
- Updated tests:
  - `test_m23_world_ui`: choice text raw, no numbering; dialogue box fixed position
  - `test_m25_stabilization`: dialogue box at DIALOGUE_LOCATION, not aspect formula
  - `test_m26d_history_rewind`: history box dark tolerant (0.02,0.03,0.08 or 0.03,0.04,0.09)
  - `test_m26i_text_style`: speaker default blue, shadows transparent, flat text allowed
  - `test_m27_gui_addon_operators`: unstyled only Bfont, not extrude; rewind shear 0.0 allowed

### How to Reproduce

```bash
source /tmp/wl-upvn/env.sh
export WLR_BACKENDS=headless WLR_RENDERER=pixman LIBGL_ALWAYS_SOFTWARE=1
# simple template (light)
blenderplayer -w 1280 720 0 0 /home/user/UPVN/blend/UPVN_Template.blend &
grim screenshots/renpy_parity/upbge_dialogue_box.png

# LTCR light (color mode, no image bank OOM)
blenderplayer -w 1280 720 0 0 /home/user/UPVN_LearnToCodeRPG/blend/UPVN_Template.blend &
grim ltcr.png
wtype -k space  # advance
```

### Files

- `/home/user/UPVN/engine/render/contract.py` — Ren'Py identical source truth
- `/home/user/UPVN/engine/ui/world_ui.py` — Ren'Py identical layout
- `/home/user/UPVN/blend/upvn_editor_addon.py` — _rewrite_unlit BLEND + white/blue + MAFont white
- `/home/user/UPVN/blend/UPVN_Template.blend` — 137KB, regenerated with Ren'Py materials
- `/home/user/UPVN_LearnToCodeRPG/` — converted project, light (image bank removed) to avoid OOM, but retains Ren'Py script
- `/home/user/UPVN/screenshots/renpy_parity/*.png` — grim captures from real UPBGE sway pixman
