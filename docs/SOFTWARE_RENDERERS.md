# Software rendering — llvmpipe vs lavapipe (UPVN desktop recipe)

UPVN's BGE path now avoids **all image textures** (palette colours on white
emission + `object.color`). This makes the choice of software renderer a
non-issue, but you still need to know what you are setting.

| Driver | API | Mesa package | What uses it | Env knobs |
|--------|-----|--------------|--------------|-----------|
| **llvmpipe** | OpenGL 4.5 / GLES 3.2 (soft) | `libgl1-mesa-dri` + `mesa-libgallium` | Blender, UPBGE, blenderplayer, any GL/EGL app | `LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe` (usually auto) |
| **lavapipe** (`lvp`) | Vulkan 1.4 (soft) | `mesa-vulkan-drivers` | Vulkan apps, `vkcube` (when forced), Wayland compositors on Vulkan | `VK_DRIVER_FILES=/usr/share/vulkan/icd.d/lvp_icd.json` or `…/lvp_icd.x86_64.json` |

**UPBGE 0.50 is an X11 + OpenGL app** (`ldd …/blenderplayer | grep wayland` shows
no libwayland). It never touches Vulkan, so **llvmpipe is what matters**.
`lavapipe` is present on the same Mesa install but is only reached if you run
Vulkan workloads. Setting both hurts nothing.

## Verified in this sandbox (2026-09-10)

- Debian 13, Mesa 25.0.7
- `sway` headless + XWayland (pixman) + `grim` screenshots — works without GPU.
- `glmark2-es2-wayland` inside the headless desktop: score ~385 on 2 vCPUs (llvmpipe).
- Blender 4.3.2 background: `blender --background --python` + UPVN add-on loads,
  `engine: OK`, `build_vn_scene` produces 798KB template.
- Headless UPVN preview: `python -m tools.run_headless examples/20_smoke_game/script.rpy`
  and `render_state` → PNG (20KB) with palette colours, no image files.
- Converted Ren'Py project: `python -m tools.convert_renpy examples/14_renpy_dropin /tmp/out`
  → 3 scripts, 33 events headless, no assets needed.

## Recommended launch

```bash
# Inside a headless sway (see docs/SANDBOX_UPBGE.md for full recipe):
export XDG_RUNTIME_DIR=/tmp/xdg WLR_BACKENDS=headless WLR_RENDERER=pixman
export LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe
export VK_DRIVER_FILES=/usr/share/vulkan/icd.d/lvp_icd.json   # or lvp_icd.x86_64.json
# then:
./upbge-0.50-linux-x64/blenderplayer -w 1024 576 0 0 blend/UPVN_Template.blend
# or plain Blender for editing:
blender blend/UPVN_Template.blend
```

No image files need to exist: `scene bg classroom` shows `#ece0bf`, `show eileen happy`
shows `#c8ffc8` (or the character's `color=`), etc. See `engine/render/contract.py`
`BG_PALETTE` / `SPRITE_PALETTE` for the full map. Headless and in-engine look
identical by construction.
