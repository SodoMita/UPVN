# Sandbox UPBGE recipe — headless Wayland (preferred) and Xvfb (fallback)

How to run the UPVN template/game in a GUI-less Linux sandbox with software
GL, take screenshots, and drive input. Written for UPBGE 0.50 (Blender 5.0.1,
**X11-only build** — `ldd` shows no libwayland, so a native Wayland client
path does not exist; XWayland hosts the player).

## Stack A — headless wlroots compositor (sway) + XWayland  ✅ preferred

```
apt install sway wtype grim xwayland x11-xserver-utils xdotool imagemagick \
            mesa-utils libgl1-mesa-dri libpulse0 libsndfile1 libjack-jackd2-0
```

1. Runtime dir + minimal config (`default_border none`, headless output mode):
   ```bash
   mkdir -p /tmp/xdg && chmod 700 /tmp/xdg
   cat > /tmp/sway_upvn.conf <<'EOF'
   default_border none
   output HEADLESS-1 mode 1280x720
   # xwayland stays enabled: UPBGE 0.50 is an X11 client (BUG-009 era finding)
   EOF
   ```
2. Start the compositor (pixman renderer auto-falls-back when no DRM/GPU):
   ```bash
   XDG_RUNTIME_DIR=/tmp/xdg WLR_BACKENDS=headless sway -c /tmp/sway_upvn.conf -d
   ```
   Expect in the log: `HEADLESS-1` output, `wayland-1` display, XWayland
   lazy-starting `/tmp/.X11-unix/X0` ⇒ **DISPLAY=:0**.
3. One-time UPBGE userpref prep (BUG-006/BUG-016, exact Blender 5.0 API):
   ```bash
   LIBGL_ALWAYS_SOFTWARE=1 ./blender --background --python-expr \
     "import bpy; bpy.context.preferences.system.audio_device='None'; \
      bpy.context.preferences.filepaths.use_scripts_auto_execute=True; \
      bpy.ops.wm.save_userpref()"
   ```
   (5.0 moved audio prefs to `preferences.system`; without this the player
   SIGSEGVs in `AUD_Device_setSpeedOfSound` before the first frame.)
4. Play:
   ```bash
   DISPLAY=:0 LIBGL_ALWAYS_SOFTWARE=1 \
     ./blenderplayer -w 1024 576 0 0 /path/to/UPVN_Template.blend &
   ```
5. Evidence:
   - screenshots (compositor side, never black): `XDG_RUNTIME_DIR=/tmp/xdg \
     WAYLAND_DISPLAY=wayland-1 grim out.png`
   - window/state: `SWAYSOCK=/tmp/xdg/sway-ipc.*.sock swaymsg -t get_tree`
   - input: `xdotool` against DISPLAY=:0 (XWayland translates to the client).
     `wtype` speaks Wayland protocol only — useless for this X11 client.
   - machine-readable story state: run the player with
     `UPVN_HEARTBEAT=/tmp/upvn_hb.json` (frontend writes label/idx/event/
     choices/modal every tick). Player stdout is block-buffered and lost on
     `kill -9` — never assert on logs.

## Stack B — Xvfb (fallback)

```bash
Xvfb :99 -screen 0 1280x720x24 & DISPLAY=:99 ./blenderplayer -w 1024 576 128 64 ...
DISPLAY=:99 import -window $WID shot.png     # imagemagick, per-window
```
Works (M24 evidence was captured this way) but in this sandbox Xvfb went
zombie twice (`xdpyinfo` hangs, fresh displays never answer) and root-window
captures are black for the first ~16 s. Keep `-w W H X Y` inside the root
size: a window larger than the Xvfb screen makes `import -window root` hang.

## Wayland vs Xvfb — measured in this sandbox (2026-09-10)

| | sway headless + XWayland | Xvfb |
|---|---|---|
| startup reliability | 6/6 clean starts | 2 zombie incidents |
| screenshots | `grim` compositor-side, correct from first frame | black <16 s; per-window `import` can hang after exit |
| input | xdotool via XWayland (same flake class as Xvfb) | xdotool |
| window management | sway tiling = window always fully visible | manual offsets vs root |
| extra deps | sway/wlroots/grim | xvfb/imagemagick |
| llvmpipe fps (1024x576) | ~13–19 logic fps | ~13–19 logic fps (same) |

Verdict: same rendering performance (llvmpipe either way), strictly better
capture + process hygiene on Wayland. `tools/smoke_walkthrough.sh`
auto-detects: `SMOKE_BACKEND=wayland|xvfb|auto`.

## Input flake (both stacks)
Synthetic XTest events intermittently drop; zero-delay chords (`ctrl+s`)
release Ctrl between logic ticks (13–19 fps under llvmpipe) so the
`active(LEFTCTRL)` half never registers. Harness rules: `xdotool key
--delay 80` for chords, and **retry-until-state** using the heartbeat file
(`press_until` in the walkthrough). Never fire bare `Escape`: blenderplayer
quits on Esc at engine level, modal or not (BUG-011).

## Housekeeping
- Kill strays with `pkill -9 -x blenderplayer` / `-x blender` — never `pkill -f`.
- `timeout -s KILL` for bounded runs; the player ignores TERM.
- Keep the UPBGE tarball mirror inside the workspace (`tmp/upbge.tar.xz`):
  sandbox reprovisions wipe installed packages and big binaries between
  sessions; the 408 MB download is the slowest recovery step.

## UPBGE 0.50 runtime API findings (M26, all verified live)

- `KX_GameObject.rayCast` does NOT see `physics_type='SENSOR'` objects —
  ray-target plates must be `STATIC` (+ BOX collision bounds).
- `Camera.getScreenRay` returns None on orthographic cameras.
- `KX_Scene.rayCast` does not exist — cast from a camera/object.
- `bge.logic.mouse.position` y is measured from the window TOP.
- `bge.texture.Texture` cannot bind node-based (Emission) materials —
  "Texture is not available"; use editor-assigned image planes or object
  color tints.
- `blender -w WxH+X+Y` opens the editor windowed (the argument before the
  blend is still parsed as a file — order matters: `-w 800x450+0+0 file.blend`).
- Embedded P (editor) needs ~1.6 GB RSS; on 2 GB hosts it gets OOM-killed
  (~2 s after engine start) — use the standalone blenderplayer there.
- `tools/desktop_run.sh` wraps the env-correct standalone player run
  (DISPLAY, LIBGL_ALWAYS_SOFTWARE, SDL dummy audio, heartbeat + debug tee).
