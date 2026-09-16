#!/bin/bash
# UPVN desktop screenshot harness — launch the standalone player on the
# headless Wayland (sway/pixman) desktop, capture the window, print state.
#
# usage: tools/desktop_shot.sh <out.webp> [seconds] [blend]
#        tools/desktop_shot.sh art/qa/line1.webp 22
#
# Why this exists: every M29 verification loop needs the same four things —
# the compositor env from tools/desktop_sway.sh, the player's env contract
# (LIBGL_ALWAYS_SOFTWARE, SDL dummy audio, heartbeat + debug tee), a capture
# that is NOT black, and the machine-readable story state next to it. Doing
# that by hand is where QA cycles go to die.
#
# Captures are WebP (M29 rule: no PNG in the repo). `grim` only writes PNG, so
# the PNG is a temporary file in /tmp and wiped immediately.
set -u
OUT="${1:-/tmp/upvn_shot.webp}"
SECS="${2:-22}"
BLEND="${3:-blend/UPVN_Template.blend}"
REPO="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
RUNDIR="${UPVN_WL_DIR:-/tmp/wl-upvn}"
UPBGE="${UPBGE_DIR:-/opt/upbge/upbge-0.50-linux-x64}"

[ -f "$RUNDIR/env.sh" ] && . "$RUNDIR/env.sh"
: "${WAYLAND_DISPLAY:=wayland-1}"
: "${DISPLAY:=:0}"
export XDG_RUNTIME_DIR="$RUNDIR" WAYLAND_DISPLAY DISPLAY
export LIBGL_ALWAYS_SOFTWARE=1 LP_NUM_THREADS="${LP_NUM_THREADS:-1}"
export SDL_AUDIODRIVER=dummy
HB="${UPVN_HEARTBEAT:-/tmp/upvn_hb.json}"
TEE="${UPVN_DEBUG_TEE:-/tmp/upvn_debug.log}"
export UPVN_HEARTBEAT="$HB" UPVN_DEBUG_TEE="$TEE"

[ -x "$UPBGE/blenderplayer" ] || { echo "no blenderplayer in $UPBGE — run tools/desktop_sway.sh" >&2; exit 2; }
case "$BLEND" in /*) ;; *) BLEND="$REPO/$BLEND" ;; esac
[ -f "$BLEND" ] || { echo "no such blend: $BLEND" >&2; exit 2; }

mkdir -p "$(dirname "$OUT")"
rm -f "$HB" "$TEE"
pkill -9 -x blenderplayer 2>/dev/null || true
sleep 1
(
  cd "$REPO"
  setsid nice -n 10 "$UPBGE/blenderplayer" -w 1280 720 0 0 "$BLEND" \
    > /tmp/upvn_player.log 2>&1 < /dev/null &
)
# Wait for a frame instead of guessing: the heartbeat file is written by the
# frontend every tick, so its existence means the engine is running and the
# window is mapped. llvmpipe needs 15-25 s for the first frame on 2 vCPUs, so
# poll up to the budget and only then fall back to a fixed sleep.
DEADLINE=$((SECS * 3))
for _ in $(seq 1 "$DEADLINE"); do
  [ -s "$HB" ] && break
  sleep 1
done
if [ -s "$HB" ]; then
  sleep 3          # a couple of frames for the UI to settle
else
  echo "warning: no heartbeat after ${DEADLINE}s — capturing anyway" >&2
fi

TMP_PNG="$(mktemp /tmp/upvn_shot_XXXX.png)"
# "Wait for pixels, not for time": a heartbeat proves the engine is running,
# but the compositor may still be holding an empty XWayland surface, and grim
# then saves a perfectly black frame (measured: black regardless of state).
# Retry until the capture is a real image (many distinct colors).
CAPTURED=0
for _try in $(seq 1 "${UPVN_SHOT_TRIES:-10}"); do
  if grim "$TMP_PNG" 2>/dev/null && python3 - "$TMP_PNG" <<'PYCHK'
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB")
raise SystemExit(0 if len(im.getcolors(maxcolors=200000) or []) > 500 else 1)
PYCHK
  then
    CAPTURED=1
    break
  fi
  echo "… waiting for a composited frame (attempt $_try)"
  sleep 2
done
if [ "$CAPTURED" = "1" ]; then
  python3 - "$TMP_PNG" "$REPO/$OUT" <<'PY'
import sys
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
Image.open(src).convert("RGB").save(dst, "WEBP", quality=90, method=6)
print(f"captured {dst}")
PY
  rm -f "$TMP_PNG"
else
  echo "grim failed or the frame stayed black (is sway running? tools/desktop_sway.sh status)" >&2
fi

echo "--- story state ($HB)"
python3 - "$HB" <<'PY' 2>/dev/null || echo "(no heartbeat — the player did not reach a frame)"
import json, sys
d = json.load(open(sys.argv[1]))
keys = ("label", "idx", "event", "speaker", "dialogue", "dialogue_visible",
        "choices", "font_body", "font_speaker", "ui_status")
print(json.dumps({k: d[k] for k in keys if k in d}, indent=2)[:1200])
PY
echo "--- player log tail"
tail -5 /tmp/upvn_player.log 2>/dev/null
pkill -9 -x blenderplayer 2>/dev/null || true
