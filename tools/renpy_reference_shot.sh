#!/bin/bash
# Screenshot the REAL Ren'Py engine at an exact script line — the ground truth
# for "does UPVN look like Ren'Py?" comparisons.  Runs headless (sway/pixman)
# and warps straight to `file:line` so no menu clicking is needed.
#
#   tools/renpy_reference_shot.sh <project_dir> <warp:file:line> <out.png> [secs]
#
#   tools/renpy_reference_shot.sh \
#       /var/tmp/renpy/renpy-8.3.6-sdk/the_question script.rpy:34 /tmp/say.png
#
# Env: RENPY_SDK (default /var/tmp/renpy/renpy-8.3.6-sdk), UPVN_WL_DIR
set -u
PROJ="${1:?usage: tools/renpy_reference_shot.sh <project_dir> <warp file:line> <out.png> [secs]}"
WARP="${2:?warp location, e.g. script.rpy:34}"
OUT="${3:?out.png required}"
SECS="${4:-35}"
SDK="${RENPY_SDK:-/var/tmp/renpy/renpy-8.3.6-sdk}"
WL="${UPVN_WL_DIR:-/tmp/wl-upvn}"
[ -f "$WL/env.sh" ] && . "$WL/env.sh"
export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-$WL}"
export SDL_VIDEODRIVER=x11 LIBGL_ALWAYS_SOFTWARE=1 SDL_AUDIODRIVER=dummy
unset WAYLAND_DISPLAY

# NB: never `pkill -f <project path>` — the pattern matches this script's own
# command line and the tool kills itself (silent exit, no output).  The real
# Ren'Py process is the compiled `renpy` binary under the SDK's lib dir.
pkill -x renpy 2>/dev/null || pkill -f "lib/py3-linux-x86_64/renpy" 2>/dev/null
sleep 1
cd "$SDK"
setsid ./renpy.sh "$PROJ" --warp "$WARP" --savedir /tmp/renpy_saves \
    > /tmp/renpy_reference.log 2>&1 < /dev/null &
PID=$!
trap 'pkill -P $PID 2>/dev/null; kill -9 $PID 2>/dev/null' EXIT

sleep "$SECS"
XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}" grim "$OUT"
echo "shot=$OUT (warp $WARP, ${SECS}s)"
grep -iE "exception|error|traceback" /tmp/renpy_reference.log | head -5 || true
