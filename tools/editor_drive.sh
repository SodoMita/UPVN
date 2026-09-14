#!/bin/bash
# tools/editor_drive.sh — send one command to a live UPBGE editor session
# driven by tools/editor_queue_driver.py, force the redraws that pump the
# driver's draw handler, wait, and print the latest result line.
#
# usage: tools/editor_drive.sh '<json command>' [wait_seconds]
#   tools/editor_drive.sh '{"id":"v","op":"eval","kwargs":{"expr":"1+1"}}'
#
# Requires DISPLAY pointing at the desktop stack (source /tmp/wl-upvn/env.sh)
# and the editor window active (it is, when the editor is the only window).
set -u
Q="${UPVN_DRV_QUEUE:-/tmp/upvn_cmd_queue.json}"
R="${UPVN_DRV_RESULTS:-/tmp/upvn_cmd_results.jsonl}"
echo "$1" > "$Q"
# harmless view keys: each causes a viewport redraw -> the driver polls
xdotool key KP_0 2>/dev/null; sleep 0.3
xdotool key KP_5 2>/dev/null; sleep 0.3
xdotool key KP_0 2>/dev/null
sleep "${2:-1.5}"
tail -1 "$R" 2>/dev/null || echo "(no result yet — is the editor redrawing?)"
