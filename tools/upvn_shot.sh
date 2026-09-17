#!/bin/bash
# Screenshot the REAL UPVN player at a chosen line (headless sway + pixman).
#
#   tools/upvn_shot.sh <blend> <out.png> [match_text] [max_presses] [max_secs]
#
# The player is started on the X11/XWayland path (UPBGE 0.53's native Wayland
# backend segfaults on a seat-less headless sway — see docs/SANDBOX_UPBGE.md),
# and advanced with synthetic Space presses until `UPVN_HEARTBEAT` reports a
# dialogue line containing `match_text` (default: first line that appears).
# The shot is taken with `grim` on the compositor side, so it can never be a
# black/empty frame the way per-window X11 captures can.
#
# Env: UPBGE_DIR, UPVN_WL_DIR, UPVN_WIN="W H X Y" (default 1024 576 0 0)
set -u
BLEND="${1:?usage: tools/upvn_shot.sh <blend> <out.png> [match_text] [max_presses] [max_secs]}"
OUT="${2:?out.png required}"
MATCH="${3:-}"
MAXP="${4:-14}"
MAXS="${5:-90}"

REPO="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
UPBGE="${UPBGE_DIR:-/var/tmp/upbge/bin}"
WL="${UPVN_WL_DIR:-/tmp/wl-upvn}"
[ -f "$WL/env.sh" ] && . "$WL/env.sh"
unset WAYLAND_DISPLAY            # force X11 (native Wayland crashes, see above)
export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-$WL}"
export LIBGL_ALWAYS_SOFTWARE=1 SDL_AUDIODRIVER=dummy LP_NUM_THREADS=1
export UPVN_HEARTBEAT=/tmp/upvn_shot_hb.json
HB="$UPVN_HEARTBEAT"

rm -f "$HB"
pkill -9 -x blenderplayer 2>/dev/null; sleep 1
read -r -a WIN <<< "${UPVN_WIN:-1024 576 0 0}"
cd "$(dirname "$BLEND")"
"$UPBGE/blenderplayer" -w "${WIN[0]}" "${WIN[1]}" "${WIN[2]}" "${WIN[3]}" "$BLEND" \
    > /tmp/upvn_shot_player.log 2>&1 &
PID=$!
trap 'kill -9 $PID 2>/dev/null; pkill -9 -x blenderplayer 2>/dev/null' EXIT

hb() { python3 - "$HB" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print(""); raise SystemExit
print(" ".join(str(d.get(k, "")) for k in ("speaker", "dialogue")).strip())
PY
}

shoot() { XDG_RUNTIME_DIR="$XDG_RUNTIME_DIR" WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}" \
              grim "$OUT"; }

elapsed=0
line=""
while [ "$elapsed" -lt "$MAXS" ]; do
    sleep 3; elapsed=$((elapsed + 3))
    kill -0 "$PID" 2>/dev/null || { echo "player died; see /tmp/upvn_shot_player.log" >&2; exit 3; }
    line="$(hb)"
    [ -z "$line" ] && continue
    if [ -z "$MATCH" ] || printf '%s' "$line" | grep -qi -- "$MATCH"; then
        sleep 2; shoot
        echo "MATCH after ${elapsed}s: $line"
        echo "shot=$OUT"
        kill -9 $PID 2>/dev/null
        exit 0
    fi
    # advance
    DISPLAY="$DISPLAY" xdotool key --delay 140 space >/dev/null 2>&1
    [ $((elapsed % 6)) -eq 0 ] && echo "  t=${elapsed}s at: ${line:0:60}"
done

shoot
echo "TIMEOUT (no match for '$MATCH'); last line: ${line:0:80}" >&2
kill -9 $PID 2>/dev/null
exit 4
