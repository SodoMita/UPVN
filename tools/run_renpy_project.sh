#!/bin/bash
# run_renpy_project.sh — play ANY Ren'Py project in UPVN with ONE command.
#
#   tools/run_renpy_project.sh <renpy_project_dir> [seconds] [shot.png]
#
# Does, in order (all idempotent):
#   1. convert the project (tools/renpy_convert.py)  -> $UPVN_OUT (default
#      /var/tmp/upvn_projects/<name>, kept OUT of the repo)
#   2. bake its gui.json look into the blend (tools/apply_gui_to_blend.py)
#   3. make sure the headless sway+pixman desktop is up (tools/desktop_sway.sh)
#   4. run the UPBGE player, wait for dialogue, screenshot, print the line
#
# Env: UPVN_OUT, UPBGE_DIR, UPVN_WIN ("W H X Y", default 1280 720 0 0),
#      UPVN_CLICK="X Y" (click once dialogue is up, default: window center)
set -euo pipefail

PROJ="${1:?usage: tools/run_renpy_project.sh <renpy_project_dir> [seconds] [shot.png]}"
SECS="${2:-30}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="$(basename "$(realpath -m "$PROJ")")"
OUT="${UPVN_OUT:-/var/tmp/upvn_projects/$NAME}"
UPBGE="${UPBGE_DIR:-/opt/upbge/upbge-0.50-linux-x64}"
WL="${UPVN_WL_DIR:-/tmp/wl-upvn}"
SHOT="${3:-$OUT/shot.png}"
HB=/tmp/upvn_run_hb.json
BLEND="$OUT/blend/UPVN_Template.blend"
info() { echo "▸ $*"; }

[ -d "$PROJ/game" ] || { echo "FATAL: no game/ dir in $PROJ (not a Ren'Py project?)" >&2; exit 2; }

# 1) convert
info "convert $PROJ -> $OUT"
python3 "$REPO/tools/renpy_convert.py" "$PROJ" --out "$OUT" --blender "$UPBGE/blender" 2>&1 | grep -E "\[convert\]|fonts|error" | tail -8

# 2) bake gui look (colors/sizes/fonts source: the project's own gui.rpy)
info "apply gui.json -> blend"
"$UPBGE/blender" --background "$BLEND" --python "$REPO/tools/apply_gui_to_blend.py" -- \
    "$OUT/game/upvn_gui.json" 2>/dev/null | grep apply_gui || true

# 3) desktop
if [ -f "$WL/env.sh" ] && pgrep -x sway >/dev/null; then
    . "$WL/env.sh"
else
    info "starting sway+pixman desktop"
    UPBGE_DIR="$UPBGE" bash "$REPO/tools/desktop_sway.sh" >/dev/null 2>&1 || true
    . "$WL/env.sh"
fi
export DISPLAY="${DISPLAY:-:0}" LIBGL_ALWAYS_SOFTWARE=1 SDL_AUDIODRIVER=dummy LP_NUM_THREADS=1

# 4) play
rm -f "$HB"
read -r -a WIN <<< "${UPVN_WIN:-1280 720 0 0}"
info "player ${WIN[*]} for ${SECS}s"
# -u WAYLAND_DISPLAY: UPBGE 0.53 prefers its native Wayland backend and
# segfaults in wl_proxy_get_version() on headless sway (no seat) — force X11.
env -u WAYLAND_DISPLAY UPVN_HEARTBEAT="$HB" UPVN_DEBUG_TEE=/tmp/upvn_run_debug.log \
    "$UPBGE/blenderplayer" -w "${WIN[0]}" "${WIN[1]}" "${WIN[2]}" "${WIN[3]}" \
    "$BLEND" >/tmp/upvn_run_player.log 2>&1 &
PID=$!
trap 'kill -9 $PID 2>/dev/null || true' EXIT

# wait for the first spoken line, click once, then shoot
CLICK="${UPVN_CLICK:-$((WIN[0] / 2)) $((WIN[0] > 1000 ? WIN[3] + WIN[1] - 100 : WIN[3] + WIN[1] - 60))}"
LINE=""
for i in $(seq 1 $((SECS / 2))); do
    sleep 2
    [ -s "$HB" ] || { kill -0 $PID 2>/dev/null || { echo "FATAL: player died early; log tail:"; tail -5 /tmp/upvn_run_player.log; exit 3; }; continue; }
    LINE="$(python3 -c "import json;d=json.load(open('$HB'));print((d.get('speaker') or '')+' | '+(d.get('dialogue') or '')[:60])" 2>/dev/null || true)"
    [ -n "$LINE" ] && break
done
[ -n "$LINE" ] && { info "dialogue: $LINE"; read -r CX CY <<< "$CLICK"; DISPLAY="$DISPLAY" xdotool mousemove "$CX" "$CY" click 1 || true; sleep 3; }
# llvmpipe can need >10 s to present the first frame at 1280x720: wait for the
# player's X window to appear in the tree before shooting, else grim captures
# an empty (black) output
for _ in $(seq 1 30); do
    DISPLAY="$DISPLAY" xwininfo -root -tree 2>/dev/null \
        | grep -qiE "blender|upvn|template" && break
    sleep 1
done
sleep 3
mkdir -p "$(dirname "$SHOT")"
XDG_RUNTIME_DIR="$WL" WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}" grim "$SHOT"
info "screenshot: $SHOT"
kill $PID 2>/dev/null || true
for _ in $(seq 1 10); do kill -0 $PID 2>/dev/null || break; sleep 0.5; done
kill -9 $PID 2>/dev/null || true
wait $PID 2>/dev/null || true
trap - EXIT
echo "DONE $NAME: $LINE"
