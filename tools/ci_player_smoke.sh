#!/usr/bin/env bash
# GitHub Actions / sandbox: create a fresh UPVN project and run blenderplayer
# under headless sway (XWayland) for a few seconds.
#
# Fails the job on:
#   - sway / UPBGE missing
#   - player crash (segfault, abort, traceback)
#   - UPVN errors/warnings in the log
#   - missing heartbeat (engine never ticked)
#
# Success is: timeout-KILL after SECS (exit 137) WITH a heartbeat and a clean log.
# Never `pkill -f` a path that appears in this command line.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
SECS="${UPVN_SMOKE_SECS:-20}"
WL="${UPVN_WL_DIR:-/tmp/wl-upvn}"
UPBGE="${UPBGE_DIR:-/opt/upbge/upbge-0.50-linux-x64}"
WORK="${UPVN_SMOKE_DIR:-${RUNNER_TEMP:-/tmp}/upvn_ci_project}"
LOG="${UPVN_LOG:-/tmp/upvn_ci_player.log}"
HB="${UPVN_HEARTBEAT:-/tmp/upvn_ci_hb.json}"
TEE="${UPVN_DEBUG_TEE:-/tmp/upvn_ci_debug.log}"
die() { echo "FATAL: $*" >&2; exit 1; }
info() { echo "▸ $*"; }

ensure_upbge() {
    if [ -x "$UPBGE/blenderplayer" ]; then
        info "UPBGE player: $UPBGE/blenderplayer"
        return
    fi
    mkdir -p "$(dirname "$UPBGE")"
    bash "$SCRIPT_DIR/fetch_upbge.sh" "$(dirname "$UPBGE")"
    [ -x "$UPBGE/blenderplayer" ] || die "fetch_upbge.sh did not produce $UPBGE/blenderplayer"
}

ensure_desktop() {
    # desktop_sway.sh is idempotent: apt + sway + userpref.
    export UPBGE_DIR="$UPBGE"
    export UPVN_WL_DIR="$WL"
    bash "$REPO/tools/desktop_sway.sh"
    # shellcheck disable=SC1091
    [ -f "$WL/env.sh" ] && . "$WL/env.sh"
    [ -n "${DISPLAY:-}" ] || die "sway did not export DISPLAY (see $WL/sway.log)"
}

make_project() {
    rm -rf "$WORK"
    mkdir -p "$WORK/blend" "$WORK/game"
    cp -a "$REPO/blend/UPVN_Template.blend" "$WORK/blend/"
    if [ -d "$REPO/blend/fonts" ]; then
        cp -a "$REPO/blend/fonts" "$WORK/blend/"
    fi
    cp -a "$REPO/engine" "$WORK/engine"
    cp -a "$REPO/bge_frontend" "$WORK/bge_frontend"
    info "Creating project via tools/upvn_game_creator.py"
    python3 "$REPO/tools/upvn_game_creator.py" \
        --title "CI Smoke" --theme school \
        --out "$WORK/game/script.rpy"
    [ -f "$WORK/game/script.rpy" ] || die "creator did not write script.rpy"

    # Bake script_path so the player loads //../game/script.rpy (repo layout:
    # blend/ next to game/). Slim player has no editor — skip bpy and use
    # the file-next-to-blend fallback.
    if [ -x "$UPBGE/blender" ]; then
        info "Baking VNController.script_path → //../game/script.rpy"
        LIBGL_ALWAYS_SOFTWARE=1 "$UPBGE/blender" --background \
            "$WORK/blend/UPVN_Template.blend" --python-expr \
            "import bpy; ob=bpy.data.objects.get('VNController');
props=[p for p in (ob.game.properties if ob else []) if p.name=='script_path'];
props and setattr(props[0],'value','//../game/script.rpy');
ob and ob.__setitem__('script_path','//../game/script.rpy');
print('FLIPPED','//../game/script.rpy'); bpy.ops.wm.save_mainfile()" \
            >/tmp/upvn_ci_flip.log 2>&1 || true
        if ! grep -q FLIPPED /tmp/upvn_ci_flip.log; then
            echo "WARN: blend flip did not print FLIPPED (see /tmp/upvn_ci_flip.log)"
            tail -30 /tmp/upvn_ci_flip.log || true
            mkdir -p "$WORK/blend/game"
            cp "$WORK/game/script.rpy" "$WORK/blend/game/script.rpy"
        fi
        rm -f "$WORK/blend/UPVN_Template.blend1"
    else
        info "No blender editor (slim player) — script next to blend"
        mkdir -p "$WORK/blend/game"
        cp "$WORK/game/script.rpy" "$WORK/blend/game/script.rpy"
    fi
}

run_player() {
    rm -f "$HB" "$LOG" "$TEE"
    export DISPLAY="${DISPLAY:-:0}"
    export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-$WL}"
    export LIBGL_ALWAYS_SOFTWARE=1
    export SDL_AUDIODRIVER=dummy
    export LP_NUM_THREADS="${LP_NUM_THREADS:-1}"
    export GALLIUM_DRIVER="${GALLIUM_DRIVER:-llvmpipe}"
    export UPVN_HEARTBEAT="$HB"
    export UPVN_DEBUG_TEE="$TEE"
    unset UPVN_POINTER_PROBE || true
    # UPBGE 0.53 native Wayland SIGSEGVs on headless sway — force X11.
    unset WAYLAND_DISPLAY WAYLAND_SOCKET || true

    info "Playing $WORK/blend/UPVN_Template.blend for ${SECS}s"
    set +e
    timeout -s KILL "$SECS" "$UPBGE/blenderplayer" \
        -w 1024 576 0 0 "$WORK/blend/UPVN_Template.blend" \
        >"$LOG" 2>&1
    local rc=$?
    set -e
    echo "player exit=$rc log=$LOG hb=$HB"
    # 137 = SIGKILL from timeout (expected). 124 = SIGTERM (timeout without -s KILL).
    # 0 = player quit on its own (unusual for a looping Always brick — still OK
    #     if heartbeat exists). Anything else is a crash.
    if [ "$rc" -ne 137 ] && [ "$rc" -ne 124 ] && [ "$rc" -ne 0 ]; then
        echo "FAIL: blenderplayer exited $rc (not timeout-KILL)"
        tail -80 "$LOG" || true
        python3 "$REPO/tools/scan_player_log.py" "$LOG" --heartbeat "$HB" --require-heartbeat || true
        exit 1
    fi
}

scan() {
    info "Scanning player log + heartbeat"
    if [ -f "$TEE" ]; then
        echo "----- debug tee (tail) -----"
        tail -40 "$TEE" || true
    fi
    echo "----- player log (tail) -----"
    tail -60 "$LOG" || true
    if [ -f "$HB" ]; then
        echo "----- heartbeat -----"
        python3 -m json.tool "$HB" 2>/dev/null | head -40 || cat "$HB"
    fi
    python3 "$REPO/tools/scan_player_log.py" "$LOG" \
        --heartbeat "$HB" --require-heartbeat
}

info "=== UPVN CI player smoke ==="
ensure_upbge
ensure_desktop
make_project
run_player
scan
info "OK"
