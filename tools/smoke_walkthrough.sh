#!/bin/bash
# M25 manual-ish smoke walkthrough — backend-agnostic (Xvfb OR headless Wayland)
# and SELF-VERIFYING: every step is confirmed via the F1 state dump in the
# player log (label/idx/event), with bounded retries, because synthetic input
# (XTest -> XWayland -> client) intermittently drops single keys and chords.
#
# usage: bash tools/smoke_walkthrough.sh [blend_path]
#
# Backends (SMOKE_BACKEND=auto|xvfb|wayland, default auto):
#   wayland : sway/wlroots headless compositor + XWayland (preferred: no Xvfb
#             zombie instability). Needs sway running with WLR_BACKENDS=headless
#             + XDG_RUNTIME_DIR/WAYLAND_DISPLAY (docs/SANDBOX_UPBGE.md), grim
#             for shots, xdotool for input (player is an X11 client).
#   xvfb    : classic Xvfb :99 + imagemagick `import` for shots.
# Also requires: xdotool, UPBGE at $UPBGE_DIR, sandbox prep from
# docs/SANDBOX_UPBGE.md (audio_device None + launcher autoexec userprefs).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Resolve to an ABSOLUTE path before the `cd "$UPBGE"` below — a relative
# blend argument used to resolve against the player dir instead of the
# caller's cwd and the player aborted with "loading ... failed".
BLEND="$(realpath -m "${1:-$ROOT/blend/UPVN_Template.blend}")"
UPBGE="${UPBGE_DIR:-/home/user/upbge/upbge-0.50-linux-x64}"
BACKEND="${SMOKE_BACKEND:-auto}"
OUT="${SMOKE_OUT:-/tmp/smoke_shots}"
LOG=/tmp/smoke_player.log
mkdir -p "$OUT"
rm -f "$OUT"/*.png

if [ "$BACKEND" = auto ]; then
  if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -S "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/wayland-1" ] 2>/dev/null; then
    BACKEND=wayland
  elif [ -S /tmp/.X11-unix/X0 ] && pgrep -x sway >/dev/null 2>&1; then
    BACKEND=wayland; export DISPLAY=:0
  else
    BACKEND=xvfb
  fi
fi

if [ "$BACKEND" = wayland ]; then
  export DISPLAY="${DISPLAY:-:0}"          # XWayland display served by sway
  shot() { grim "$OUT/$1.png" >/dev/null 2>&1; echo "shot $1 (grim)"; }
else
  export DISPLAY=:99
  pgrep -x Xvfb >/dev/null 2>&1 || { Xvfb :99 -screen 0 1280x720x24 >/dev/null 2>&1 & sleep 2; }
  shot() { timeout 8 import -window "$WID" "$OUT/$1.png" >/dev/null 2>&1; echo "shot $1 (import)"; }
fi
echo "== smoke walkthrough backend: $BACKEND (DISPLAY=$DISPLAY) =="

cd "$UPBGE" || exit 1
rm -f saves/save_quick.json
UPVN_HEARTBEAT=/tmp/upvn_hb.json ./blenderplayer -w 1024 576 0 0 "$BLEND" > "$LOG" 2>&1 &
PLAYER=$!
sleep 18

WID=$(timeout 5 xdotool search --name "$(basename "$BLEND" .blend)" 2>/dev/null | head -1)
if [ -z "$WID" ]; then echo "FAIL: no player window"; kill -9 $PLAYER 2>/dev/null; exit 1; fi
timeout 5 xdotool windowfocus --sync "$WID" 2>/dev/null

# State comes from the frontend heartbeat file (UPVN_HEARTBEAT, per-tick JSON:
# label/idx/event/choices/modal). No F1 presses needed (F1 toggles the
# on-screen diag overlay and would dirty the screenshots).
HB=/tmp/upvn_hb.json
rm -f "$HB"
hb() { cat "$HB" 2>/dev/null; }
hb_field() { python3 -c "import json,sys;print(json.load(open('$HB')).get('$1',''))" 2>/dev/null; }
# expect LABEL EVENT IDX [TRIES]: poll the heartbeat until the state matches.
expect() {
  local lab=$1 evt=$2 idx=$3 n=${4:-6} i line
  for i in $(seq 1 "$n"); do
    sleep 1
    line=$(hb)
    case "$line" in *'"label": "'$lab'", "idx": '$idx', "event": "'$evt'"'*)
      echo "  ok: $line"; return 0;; esac
  done
  echo "  EXPECT-FAIL want label=$lab idx=$idx event=$evt got: $line"
  return 1
}
# press_until KEY LABEL EVENT IDX [TRIES]: synthetic input (XTest -> XWayland)
# intermittently drops keys, so resend until the heartbeat confirms the state.
press_until() {
  local k=$1 lab=$2 evt=$3 idx=$4 t
  for t in 1 2 3; do
    timeout 5 xdotool key --window "$WID" --delay 80 "$k"; sleep 2
    if [ "$(hb_field label)" = "$lab" ] && [ "$(hb_field idx)" = "$idx" ]        && [ "$(hb_field event)" = "$evt" ]; then echo "  ok($k): $(hb)"; return 0; fi
  done
  echo "  PRESS-UNTIL-FAIL $k want $lab/$idx/$evt got: $(hb)"
  return 1
}
# press KEY [DELAY]: send one key; chords get a hold delay so both halves land
# inside one logic tick (13-19 fps under llvmpipe).
press() { timeout 5 xdotool key --window "$WID" --delay 80 "$1"; sleep 2; }

shot 01_dialogue_line1
expect start say 2
for t in 1 2 3; do
  xdotool mousemove --window "$WID" 512 400; timeout 5 xdotool click --window "$WID" 1; sleep 2
  [ "$(hb_field idx)" = "3" ] && break
done
expect start say 3
shot 02_after_click_line2
press_until space start menu 4
shot 03_after_space_menu
# BUG-006/010 regression: digit selects a choice
press_until 1 left say 0
shot 04_after_key1_left          # must show "You chose left."
press_until Return save_test say 0
shot 05_save_test_line
# M25 BUG-011: Ctrl+S is a DIRECT quick-save (no modal). Verify via disk file.
for attempt in 1 2 3 4; do
  press ctrl+s
  for w in 1 2 3; do sleep 1; [ -f saves/save_quick.json ] && break; done
  [ -f saves/save_quick.json ] && break
done
if [ -f saves/save_quick.json ]; then echo "  SAVE_OK $(wc -c < saves/save_quick.json) bytes (attempt $attempt)"; else echo "  SAVE_MISSING"; fi
shot 06_after_quicksave            # gameplay continues, nothing blocked
press_until space save_test say 1
shot 07_route_line                 # "Route is left."
# M25 BUG-011: Ctrl+L quick-loads directly; verify by state returning to save point
for attempt in 1 2 3 4; do
  press ctrl+l
  [ "$(hb_field label)" = "save_test" ] && [ "$(hb_field idx)" = "0" ] && break
done
echo "  after quickload (attempt $attempt): $(hb)"
shot 08_after_quickload            # back at the save point (save_test line 1)
press_until space save_test say 1
shot 09_resume_after_load          # "Route is left." again
# NOTE: never send bare Escape — blenderplayer quits on Esc at engine level
# (modal or not); expected engine behaviour, not a UPVN bug.
kill -9 $PLAYER 2>/dev/null
echo "== done: $OUT =="
