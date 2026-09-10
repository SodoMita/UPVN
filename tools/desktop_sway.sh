#!/bin/bash
# Bootstrap the headless Wayland desktop + UPBGE for UPVN (Debian 13, no GPU,
# no root needed beyond apt sudo). Idempotent — safe to re-run.
# See docs/how agent can run desktop.md and docs/SANDBOX_UPBGE.md.
#
#   tools/desktop_sway.sh          # bootstrap (apt + UPBGE + sway + userpref)
#   tools/desktop_sway.sh status   # is the desktop up? what does the tree look like?
#   tools/desktop_sway.sh stop     # kill sway
#   source /tmp/wl-upvn/env.sh     # after bootstrap: get WAYLAND_DISPLAY/SWAYSOCK/DISPLAY
set -e

RUNDIR="${UPVN_WL_DIR:-/tmp/wl-upvn}"
UPBGE="${UPBGE_DIR:-/opt/upbge/upbge-0.50-linux-x64}"

stop_desktop() {
    pkill -x sway 2>/dev/null || true
    echo "sway stopped"
}

status_desktop() {
    export XDG_RUNTIME_DIR="$RUNDIR"
    local sock
    sock="$(ls "$RUNDIR"/sway-ipc.*.sock 2>/dev/null | head -1 || true)"
    if [ -z "$sock" ]; then
        echo "NOT RUNNING (no sway-ipc socket in $RUNDIR)"
        [ -f "$RUNDIR/sway.log" ] && { echo "--- sway.log ---"; tail -20 "$RUNDIR/sway.log"; }
        return 1
    fi
    export SWAYSOCK="$sock"
    swaymsg -t get_outputs
    swaymsg -t get_tree | tr ',' '\n' | grep -E '"(app_id|name)":' | sort -u | head -30
    return 0
}

case "${1:-up}" in
    stop)   stop_desktop;   exit 0 ;;
    status) status_desktop; exit $? ;;
esac

# 1) packages
if ! command -v sway >/dev/null 2>&1 || [ ! -d "$UPBGE" ]; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq sway grim foot wtype wayvnc jq \
        libgl1-mesa-dri libegl-mesa0 fonts-dejavu-core xwayland \
        x11-xserver-utils xdotool imagemagick libpulse0 libsndfile1 \
        libjack-jackd2-0 mesa-utils gdb
fi

# 2) UPBGE 0.50 tarball → /opt (kept out of the repo workspace: 408 MB)
if [ ! -x "$UPBGE/blenderplayer" ]; then
    sudo mkdir -p /opt/upbge && sudo chown "$(id -un)" /opt/upbge
    [ -f /tmp/upbge.tar.xz ] || \
        curl -L --retry 3 -o /tmp/upbge.tar.xz \
        https://github.com/UPBGE/upbge/releases/download/v0.50/upbge-0.50-linux-x64.tar.xz
    tar -xJf /tmp/upbge.tar.xz -C /opt/upbge
fi

# 3) headless sway (XWayland hosts the X11-only player)
#
# XDG_RUNTIME_DIR must be EXPORTED, not merely prefixed: sway validates the
# env var itself and aborts with "XDG_RUNTIME_DIR is not set in the
# environment" when it is only used for the mkdir (this silently killed the
# desktop for a whole QA cycle).
export XDG_RUNTIME_DIR="$RUNDIR"
mkdir -m 700 -p "$XDG_RUNTIME_DIR"
if ! pgrep -x sway >/dev/null 2>&1; then
    printf 'output HEADLESS-1 mode 1280x800\ndefault_border none\n' \
        > "$XDG_RUNTIME_DIR/cfg"
    # setsid: survive the calling shell's process-group kill (agents/CI run
    # this through a wrapper that reaps children the moment it returns).
    WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 WLR_RENDERER=pixman \
        setsid sway -c "$XDG_RUNTIME_DIR/cfg" >"$XDG_RUNTIME_DIR/sway.log" 2>&1 < /dev/null &
    # poll instead of guessing: wlroots picks its own socket name (wayland-1,
    # wayland-2 ... after stale sockets), so wait for it to appear.
    for _ in $(seq 1 60); do
        [ -n "$(ls "$XDG_RUNTIME_DIR" 2>/dev/null | grep '^wayland-' | grep -v lock || true)" ] && break
        sleep 0.25
    done
fi
WAYLAND_DISPLAY="$(ls "$XDG_RUNTIME_DIR" | grep '^wayland-' | grep -v lock | head -1)"
SWAYSOCK="$(ls "$XDG_RUNTIME_DIR"/sway-ipc.*.sock 2>/dev/null | head -1)"
[ -n "$WAYLAND_DISPLAY" ] || { echo "FATAL: sway did not create a wayland socket; see $XDG_RUNTIME_DIR/sway.log"; tail -20 "$XDG_RUNTIME_DIR/sway.log"; exit 1; }
export WAYLAND_DISPLAY SWAYSOCK

# XWayland is lazy: sway only spawns it when a client first connects. Nudge it
# (xdpyinfo against the default display) so DISPLAY=:0 really answers before
# any tool/harness relies on it; that first connect is what boots XWayland.
DISPLAY_NO=":0"
for i in 0 1 2 3 4 5; do
    if timeout 15 env DISPLAY=":$i" xdpyinfo >/dev/null 2>&1; then
        DISPLAY_NO=":$i"; break
    fi
done
if ! timeout 5 env DISPLAY="$DISPLAY_NO" xdpyinfo >/dev/null 2>&1; then
    echo "WARN: XWayland did not answer (no :0). Player can still start -- sway"
    echo "      launches XWayland on its first connect; treat this as informational."
fi

# 4) userpref prep (BUG-016: audio device — without it the player segfaults)
if [ ! -f "$HOME/.config/upbge/5.0/config/userpref.blend" ]; then
    LIBGL_ALWAYS_SOFTWARE=1 "$UPBGE/blender" --background --python-expr \
        "import bpy; bpy.context.preferences.system.audio_device='None'; \
         bpy.context.preferences.filepaths.use_scripts_auto_execute=True; \
         bpy.ops.wm.save_userpref()"
fi

cat > "$RUNDIR/env.sh" <<EOF
export XDG_RUNTIME_DIR=$RUNDIR
export WAYLAND_DISPLAY=$WAYLAND_DISPLAY
export SWAYSOCK=$SWAYSOCK
export DISPLAY=$DISPLAY_NO
export LIBGL_ALWAYS_SOFTWARE=1
export UPBGE_DIR=$UPBGE
EOF

echo "desktop ready: WAYLAND_DISPLAY=$WAYLAND_DISPLAY SWAYSOCK=$SWAYSOCK DISPLAY=$DISPLAY_NO"
echo "source it with:  source $RUNDIR/env.sh"
echo "player:        DISPLAY=$DISPLAY_NO LIBGL_ALWAYS_SOFTWARE=1 \\"
echo "               $UPBGE/blenderplayer -w 1024 576 0 0 <game>.blend"
echo "or:            tools/desktop_run.sh <game>.blend"
