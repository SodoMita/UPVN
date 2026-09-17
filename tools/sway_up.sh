#!/bin/bash
# Headless sway desktop (wlroots headless backend + **pixman** renderer) for
# real UPBGE / Ren'Py screenshots.  Minimal and idempotent — unlike
# tools/desktop_sway.sh it never installs packages or downloads UPBGE; point it
# at an existing install with UPBGE_DIR / RENPY_SDK.
#
#   tools/sway_up.sh up       # start (prints: source /tmp/wl-upvn/env.sh)
#   tools/sway_up.sh status   # outputs + window tree
#   tools/sway_up.sh stop
#
# After a successful start:
#   source /tmp/wl-upvn/env.sh
#   grim shot.png                       # screenshot (compositor side, never black)
#   $UPBGE_DIR/bin/blenderplayer -w 1024 576 0 0 game.blend
#
# See docs/SANDBOX_UPBGE.md and docs/how agent can run desktop.md.
set -u

RUNDIR="${UPVN_WL_DIR:-/tmp/wl-upvn}"
export XDG_RUNTIME_DIR="$RUNDIR"
mkdir -m 700 -p "$RUNDIR"

status() {
    local sock
    sock="$(ls "$RUNDIR"/sway-ipc.*.sock 2>/dev/null | head -1 || true)"
    if [ -z "$sock" ]; then echo "NOT RUNNING (no sway-ipc socket in $RUNDIR)"; return 1; fi
    SWAYSOCK="$sock" swaymsg -t get_outputs 2>/dev/null | grep -E '"(name|make|current_mode|rect)"' | head -20
    SWAYSOCK="$sock" swaymsg -t get_tree 2>/dev/null \
        | tr ',' '\n' | grep -E '"(app_id|name)":' | sort -u | head -30
    return 0
}

case "${1:-up}" in
    stop)   pkill -x sway 2>/dev/null; echo "sway stopped"; exit 0 ;;
    status) status; exit $? ;;
esac

if pgrep -x sway >/dev/null 2>&1; then
    echo "sway already running"
else
    # Keep the config mode-free: the `output ... mode` syntax differs between
    # sway builds and a bad line aborts startup / parks a swaynag banner.
    printf 'default_border none\n' > "$RUNDIR/cfg"
    unset WAYLAND_DISPLAY DISPLAY
    WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 WLR_RENDERER=pixman \
        setsid sway -c "$RUNDIR/cfg" >"$RUNDIR/sway.log" 2>&1 < /dev/null &
    for _ in $(seq 1 60); do
        [ -n "$(ls "$RUNDIR" 2>/dev/null | grep '^wayland-' | grep -v lock || true)" ] && break
        sleep 0.25
    done
fi

WAYLAND_DISPLAY="$(ls "$RUNDIR" | grep '^wayland-' | grep -v lock | head -1)"
SWAYSOCK="$(ls "$RUNDIR"/sway-ipc.*.sock 2>/dev/null | head -1)"
[ -n "$WAYLAND_DISPLAY" ] || { echo "FATAL: no wayland socket; see $RUNDIR/sway.log"; tail -20 "$RUNDIR/sway.log"; exit 1; }

# headless outputs expose no mode list — try both syntaxes, non-fatal.
[ -n "$SWAYSOCK" ] && {
    SWAYSOCK="$SWAYSOCK" swaymsg output HEADLESS-1 mode --custom 1280x720 >/dev/null 2>&1 \
        || SWAYSOCK="$SWAYSOCK" swaymsg output HEADLESS-1 model 1280x720 >/dev/null 2>&1 || true
}

# XWayland is lazy: it only starts when a client connects.  Nudge it so
# DISPLAY=:0 really answers before anything depends on it.
DISPLAY_NO=":0"
for i in 0 1 2 3 4 5; do
    if timeout 15 env DISPLAY=":$i" xdpyinfo >/dev/null 2>&1; then DISPLAY_NO=":$i"; break; fi
done

cat > "$RUNDIR/env.sh" <<EOF
export XDG_RUNTIME_DIR=$RUNDIR
export WAYLAND_DISPLAY=$WAYLAND_DISPLAY
export SWAYSOCK=$SWAYSOCK
export DISPLAY=$DISPLAY_NO
export LIBGL_ALWAYS_SOFTWARE=1
export WLR_RENDERER=pixman
export UPBGE_DIR=${UPBGE_DIR:-/var/tmp/upbge}
export RENPY_SDK=${RENPY_SDK:-/var/tmp/renpy/renpy-8.3.6-sdk}
export RENPY_GAMES=${RENPY_GAMES:-/var/tmp/renpy/games}
EOF

echo "desktop ready: WAYLAND_DISPLAY=$WAYLAND_DISPLAY SWAYSOCK=$SWAYSOCK DISPLAY=$DISPLAY_NO"
echo "source it with:  source $RUNDIR/env.sh"
status || true
