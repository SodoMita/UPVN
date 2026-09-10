#!/bin/bash
# Run the UPVN game in blenderplayer on the headless Wayland desktop (XWayland).
# Usage: tools/desktop_run.sh <blend> [seconds]
set -u
export DISPLAY=:0
export LIBGL_ALWAYS_SOFTWARE=1
export SDL_AUDIODRIVER=dummy
export UPVN_HEARTBEAT=/tmp/upvn_hb.json
export UPVN_DEBUG_TEE=/tmp/upvn_debug.log
export UPVN_POINTER_PROBE=1
UPBGE="${UPBGE_DIR:-/home/user/upbge/upbge-0.50-linux-x64}"
BLEND="${1:-/home/user/UPVN/blend/UPVN_Template.blend}"
SECS="${2:-25}"
rm -f /tmp/upvn_hb.json
cd /home/user/UPVN
timeout -s KILL "$SECS" "$UPBGE/blenderplayer" -w 1024 576 0 0 "$BLEND" > /tmp/player_run.log 2>&1
echo "exit=$?"
