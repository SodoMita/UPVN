#!/bin/bash
# Bootstrap the headless Wayland desktop + UPBGE for UPVN (Debian 13, no GPU,
# no root needed beyond apt sudo). Idempotent — safe to re-run.
# See docs/how agent can run desktop.md and docs/SANDBOX_UPBGE.md.
set -e

# 1) packages
if ! command -v sway >/dev/null 2>&1 || [ ! -d /opt/upbge/upbge-0.50-linux-x64 ]; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq sway grim foot wtype wayvnc jq \
        libgl1-mesa-dri libegl-mesa0 fonts-dejavu-core xwayland \
        x11-xserver-utils xdotool imagemagick libpulse0 libsndfile1 \
        libjack-jackd2-0 mesa-utils gdb
fi

# 2) UPBGE 0.50 tarball → /opt (kept out of the repo workspace: 408 MB)
if [ ! -x /opt/upbge/upbge-0.50-linux-x64/blenderplayer ]; then
    sudo mkdir -p /opt/upbge && sudo chown "$USER" /opt/upbge
    curl -sL -o /tmp/upbge.tar.xz \
        https://github.com/UPBGE/upbge/releases/download/v0.50/upbge-0.50-linux-x64.tar.xz
    tar -xJf /tmp/upbge.tar.xz -C /opt/upbge
fi
UPBGE=/opt/upbge/upbge-0.50-linux-x64

# 3) headless sway (XWayland hosts the X11-only player)
# M26e fix: this MUST be exported — a bare assignment is invisible to the
# sway child, which aborted with "XDG_RUNTIME_DIR is not set in the
# environment" (the whole "in-script sway start broken" mystery).
export XDG_RUNTIME_DIR=/tmp/wl-upvn
mkdir -m 700 -p "$XDG_RUNTIME_DIR"
if ! pgrep -x sway >/dev/null 2>&1; then
    # M26e fix: headless outputs have no mode list — sway's config word is
    # `model` (W×H@R). The old `mode 1280x800` was rejected at startup and
    # sway died with "output config mode unavailable" (in-script sway start
    # looked permanently broken while the manual recipe worked).
    printf 'output HEADLESS-1 model 1280x800\ndefault_border none\n' \
        > "$XDG_RUNTIME_DIR/cfg"
    WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 WLR_RENDERER=pixman \
        nohup sway -c "$XDG_RUNTIME_DIR/cfg" >"$XDG_RUNTIME_DIR/sway.log" 2>&1 &
    sleep 1.5
fi
WAYLAND_DISPLAY="$(ls "$XDG_RUNTIME_DIR" | grep '^wayland-' | grep -v lock | head -1)"
export WAYLAND_DISPLAY SWAYSOCK="$(ls "$XDG_RUNTIME_DIR"/sway-ipc.*.sock | head -1)"

# 4) userpref prep (BUG-016: audio device — without it the player segfaults)
if [ ! -f "$HOME/.config/upbge/5.0/config/userpref.blend" ]; then
    LIBGL_ALWAYS_SOFTWARE=1 "$UPBGE/blender" --background --python-expr \
        "import bpy; bpy.context.preferences.system.audio_device='None'; \
         bpy.context.preferences.filepaths.use_scripts_auto_execute=True; \
         bpy.ops.wm.save_userpref()"
fi

echo "desktop ready: WAYLAND_DISPLAY=$WAYLAND_DISPLAY SWAYSOCK=$SWAYSOCK"
echo "player:        DISPLAY=:0 LIBGL_ALWAYS_SOFTWARE=1 \\"
echo "               $UPBGE/blenderplayer -w 1024 576 0 0 <game>.blend"
echo "or:            tools/desktop_run.sh <game>.blend"
