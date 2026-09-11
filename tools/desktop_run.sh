#!/bin/bash
# Run the UPVN game in blenderplayer on the headless Wayland desktop (XWayland).
# Usage: tools/desktop_run.sh <blend> [seconds]
#   <blend> defaults to the repo template; relative paths resolve against the repo root.
#   Env: UPBGE_DIR, UPVN_WL_DIR (default /tmp/wl-upvn), UPVN_HEARTBEAT,
#        UPVN_WIN="W H X Y", UPVN_LOG, UPVN_NO_TAIL=1
set -u

REPO="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
UPBGE="${UPBGE_DIR:-/opt/upbge/upbge-0.50-linux-x64}"
WL="${UPVN_WL_DIR:-/tmp/wl-upvn}"
SECS="${2:-25}"

# env.sh from tools/desktop_sway.sh carries the real DISPLAY / Wayland socket;
# falling back to :0 keeps the old behaviour when the file is missing.
[ -f "$WL/env.sh" ] && . "$WL/env.sh"
export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-$WL}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-$(ls "$WL" 2>/dev/null | grep '^wayland-' | grep -v lock | head -1)}"
export LIBGL_ALWAYS_SOFTWARE=1
export SDL_AUDIODRIVER=dummy
export UPVN_HEARTBEAT="${UPVN_HEARTBEAT:-/tmp/upvn_hb.json}"
export UPVN_DEBUG_TEE="${UPVN_DEBUG_TEE:-/tmp/upvn_debug.log}"
export UPVN_POINTER_PROBE="${UPVN_POINTER_PROBE:-1}"
# Small sandboxes (2 vCPU / 2 GB) OOM-starve the compositor when llvmpipe uses
# every core for a 1024x576 window: the whole box stops answering for minutes.
# Cap the software rasteriser to one worker and, when UPVN_PIN is set, pin the
# player to the second core so sway + tools keep a CPU for themselves.
export LP_NUM_THREADS="${LP_NUM_THREADS:-1}"
export GALLIUM_DRIVER="${GALLIUM_DRIVER:-llvmpipe}"
NICE="nice -n 10"
CPUSET=""
if [ "${UPVN_PIN:-1}" != "0" ] && command -v taskset >/dev/null 2>&1; then
    LASTCPU=$(( $(nproc) > 1 ? $(nproc) - 1 : 0 ))
    CPUSET="taskset -c $LASTCPU"
fi

BLEND="${1:-$REPO/blend/UPVN_Template.blend}"
case "$BLEND" in
    /*) ;;
    *)  BLEND="$REPO/$BLEND" ;;
esac
[ -f "$BLEND" ] || { echo "no such blend: $BLEND" >&2; exit 2; }
[ -x "$UPBGE/blenderplayer" ] || { echo "no blenderplayer in $UPBGE (run tools/desktop_sway.sh)" >&2; exit 2; }

# -w W H X Y — keep it inside the compositor output size (see SANDBOX doc).
read -r -a WIN <<< "${UPVN_WIN:-1024 576 0 0}"
LOG="${UPVN_LOG:-/tmp/player_run.log}"
rm -f "$UPVN_HEARTBEAT"

cd "$REPO"
$NICE $CPUSET timeout -s KILL "$SECS" "$UPBGE/blenderplayer" -w "${WIN[0]}" "${WIN[1]}" "${WIN[2]}" "${WIN[3]}" "$BLEND" > "$LOG" 2>&1
rc=$?
echo "exit=$rc log=$LOG hb=$UPVN_HEARTBEAT"
exit $rc
