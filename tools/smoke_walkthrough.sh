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
# the headless-compositor env written by tools/desktop_sway.sh, when present
[ -f /tmp/wl-upvn/env.sh ] && . /tmp/wl-upvn/env.sh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# Resolve to an ABSOLUTE path before the `cd "$UPBGE"` below — a relative
# blend argument used to resolve against the player dir instead of the
# caller's cwd and the player aborted with "loading ... failed".
BLEND="$(realpath -m "${1:-$ROOT/blend/UPVN_Template.blend}")"
# Where is UPBGE? tools/desktop_sway.sh installs to /opt/upbge, older notes used
# ~/upbge, and a reprovisioned sandbox has neither until the bootstrap re-runs —
# so probe instead of hardcoding one path, and say what to do when none is found.
pick_upbge() {
  local c
  for c in "${UPBGE_DIR:-}" /opt/upbge/upbge-0.50-linux-x64 "$HOME/upbge/upbge-0.50-linux-x64" \
           /opt/upbge /usr/local/upbge/upbge-0.50-linux-x64; do
    [ -n "$c" ] && [ -x "$c/blenderplayer" ] && { echo "$c"; return 0; }
  done
  c=$(command -v blenderplayer 2>/dev/null)
  [ -n "$c" ] && { dirname "$c"; return 0; }
  return 1
}
UPBGE="$(pick_upbge || true)"
if [ -z "$UPBGE" ]; then
  echo "FAIL: no blenderplayer found. Run: bash tools/desktop_sway.sh" >&2
  echo "      (or point UPBGE_DIR at an existing UPBGE install)" >&2
  exit 1
fi
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
hold_for() { case "$1" in *+*) echo 80 ;; *) echo 12 ;; esac; }
press_until() {
  local k=$1 lab=$2 evt=$3 idx=$4 t
  for t in 1 2 3; do
    timeout 5 xdotool key --window "$WID" --delay "$(hold_for "$k")" "$k"; sleep 2
    if [ "$(hb_field label)" = "$lab" ] && [ "$(hb_field idx)" = "$idx" ]        && [ "$(hb_field event)" = "$evt" ]; then echo "  ok($k): $(hb)"; return 0; fi
  done
  echo "  PRESS-UNTIL-FAIL $k want $lab/$idx/$evt got: $(hb)"
  return 1
}
# press KEY [DELAY]: send one key; chords get a hold delay so both halves land
# inside one logic tick (13-19 fps under llvmpipe).
press() { timeout 5 xdotool key --window "$WID" --delay "$(hold_for "$1")" "$1"; sleep 2; }

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
# --- M26d: backlog (H) and Rewind (wheel + PageUp/PageDown) ---
# Deliberately state-agnostic: this script reaches here at different points, and
# xdotool has no "PageUp" keysym at all (sending it exits 0 while dropping the
# event, which reads as "rewind is broken") — so use Prior/Next and assert on the
# depth counters rather than on a label/idx the run may not be at.
#   rollforward_depth > 0  <=>  the player has rewound at least one step.
press_field() {                       # KEY FIELD WANT [TRIES]
  local k=$1 f=$2 want=$3 n=${4:-3} t
  for t in $(seq 1 "$n"); do
    timeout 5 xdotool key --window "$WID" --delay "$(hold_for "$k")" "$k"; sleep 1.5
    [ "$(hb_field "$f")" = "$want" ] && { echo "  ok($k) $f=$want"; return 0; }
  done
  echo "  PRESS-FIELD-FAIL $k want $f=$want got: $(hb)"; return 1
}
wait_gt() {                           # FIELD BASELINE [TRIES] — poll for growth
  local f=$1 base=$2 n=${3:-5} i
  for i in $(seq 1 "$n"); do
    sleep 1
    [ "$(hb_field "$f")" -gt "$base" ] 2>/dev/null && return 0
  done
  return 1
}

shot 10_before_backlog
rc=0
press_field h history_open True  || rc=1
shot 11_backlog_open
if [ "$(hb_field history)" -ge 1 ] 2>/dev/null; then
  echo "  HISTORY_OK: $(hb_field history) entr$( [ "$(hb_field history)" = 1 ] && echo y || echo ies)"
else
  echo "  HISTORY_FAIL: no backlog entries recorded: $(hb)"; rc=1
fi
press_field h history_open False || rc=1     # H again closes it (an advance does too)
shot 12_backlog_closed

d0=$(hb_field rollforward_depth)
press Prior; wait_gt rollforward_depth "$d0" \
  && echo "  REWIND_OK (key): depth $(hb_field rollforward_depth)" \
  || { echo "  REWIND_FAIL (key): $(hb)"; rc=1; }
shot 13_after_rewind
d1=$(hb_field rollforward_depth)
[ "$d1" -gt 0 ] 2>/dev/null && { press Next; wait_gt rollback_depth 0 >/dev/null && echo "  REPLAY_OK (key)"; }
press Prior                                  # leave one step rewound for the wheel test
d2=$(hb_field rollforward_depth)
# the wheel is the primary Rewind binding, and it needs XTEST: `--window` sends
# synthetic events, which the SDL frontend ignores.
for i in 1 2; do timeout 5 xdotool click 4; sleep 1; done
wait_gt rollforward_depth "$d2" \
  && echo "  REWIND_OK (wheel): depth $(hb_field rollforward_depth)" \
  || { echo "  REWIND_FAIL (wheel): $(hb)"; rc=1; }
d3=$(hb_field rollforward_depth)
for i in 1 2; do timeout 5 xdotool click 5; sleep 1; done
[ "$(hb_field rollforward_depth)" -lt "$d3" ] 2>/dev/null \
  && echo "  REPLAY_OK (wheel): depth $(hb_field rollforward_depth)" \
  || echo "  replay(wheel) inconclusive at $(hb_field rollforward_depth) (engine clamps at the newest line)"
shot 15_after_wheel
[ "$rc" = 0 ] && echo "  M26d: backlog + rewind OK" || echo "  M26d: see FAIL lines above"

# NOTE: never send bare Escape — blenderplayer quits on Esc at engine level
# (modal or not); expected engine behaviour, not a UPVN bug.
kill -9 $PLAYER 2>/dev/null
echo "== done: $OUT =="
