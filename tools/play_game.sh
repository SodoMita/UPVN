#!/bin/bash
# play_game.sh — one-command VN launcher: sets up sway+pixman, downloads UPBGE if
# needed, creates a demo project if none exists, and plays the game.
#
# Usage:
#   tools/play_game.sh                        # play the template
#   tools/play_game.sh game/script.rpy        # play a specific script
#   tools/play_game.sh --wizard "My Story"    # create + play in one click
#
# Requirements: Debian/Ubuntu with apt, ~2 GB RAM (+ 3 GB swap auto-created).
# Everything else is installed automatically.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
UPBGE_DIR="${UPBGE_DIR:-/opt/upbge/upbge-0.50-linux-x64}"
RUNDIR="${UPVN_WL_DIR:-/tmp/wl-upvn}"
WIN="${UPVN_WIN:-1024 576 0 0}"
DURATION="${UPVN_PLAY_SECS:-30}"

# ---------- helpers
die()  { echo "FATAL: $*" >&2; exit 1; }
info() { echo "▸ $*"; }

ensure_packages() {
    local needed=()
    for pkg in sway grim xwayland x11-xserver-utils xdotool imagemagick \
               mesa-utils libgl1-mesa-dri libpulse0 libsndfile1; do
        dpkg -s "$pkg" &>/dev/null || needed+=("$pkg")
    done
    if [ ${#needed[@]} -gt 0 ]; then
        info "Installing: ${needed[*]}"
        sudo apt-get update -qq
        sudo apt-get install -y -qq "${needed[@]}"
    fi
}

ensure_swap() {
    local total_kb
    total_kb=$(awk '/SwapTotal/{print $2}' /proc/meminfo)
    if [ "${total_kb:-0}" -lt 1048576 ]; then
        if sudo -n true 2>/dev/null; then
            info "Adding 3 GB swap (UPBGE needs ~1.2 GB RSS)..."
            sudo fallocate -l 3G /swapfile 2>/dev/null || true
            sudo chmod 600 /swapfile
            sudo mkswap /swapfile >/dev/null 2>&1 || true
            sudo swapon /swapfile 2>/dev/null || true
        else
            echo "warning: <1 GB swap and no sudo — player may OOM"
        fi
    fi
}

ensure_upbge() {
    if [ -x "$UPBGE_DIR/blenderplayer" ]; then
        return
    fi
    info "Downloading UPBGE 0.50 (~408 MB)..."
    sudo mkdir -p /opt/upbge && sudo chown "$(id -un)" /opt/upbge
    local tarball="/tmp/upbge-0.50-linux-x64.tar.xz"
    [ -f "$tarball" ] || curl -L --retry 3 -o "$tarball" \
        "https://github.com/UPBGE/upbge/releases/download/v0.50/upbge-0.50-linux-x64.tar.xz"
    tar -xJf "$tarball" -C /opt/upbge
    info "UPBGE installed at $UPBGE_DIR"
}

ensure_sway() {
    export XDG_RUNTIME_DIR="$RUNDIR"
    mkdir -m 700 -p "$XDG_RUNTIME_DIR"

    if pgrep -x sway >/dev/null 2>&1; then
        info "sway already running"
    else
        info "Starting headless sway+pixman..."
        printf 'default_border none\n' > "$XDG_RUNTIME_DIR/cfg"
        WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 WLR_RENDERER=pixman \
            setsid sway -c "$XDG_RUNTIME_DIR/cfg" \
            >"$XDG_RUNTIME_DIR/sway.log" 2>&1 < /dev/null &
        # Wait for socket
        for _ in $(seq 1 60); do
            [ -n "$(ls "$XDG_RUNTIME_DIR" 2>/dev/null | grep '^wayland-' | grep -v lock || true)" ] && break
            sleep 0.25
        done
        local sock
        sock="$(ls "$XDG_RUNTIME_DIR"/sway-ipc.*.sock 2>/dev/null | head -1)"
        if [ -n "$sock" ]; then
            SWAYSOCK="$sock" swaymsg output HEADLESS-1 mode --custom 1280x800 >/dev/null 2>&1 \
                || SWAYSOCK="$sock" swaymsg output HEADLESS-1 model 1280x800 >/dev/null 2>&1 || true
        fi
    fi

    export WAYLAND_DISPLAY
    WAYLAND_DISPLAY="$(ls "$XDG_RUNTIME_DIR" 2>/dev/null | grep '^wayland-' | grep -v lock | head -1)"
    [ -n "$WAYLAND_DISPLAY" ] || die "sway did not start; see $XDG_RUNTIME_DIR/sway.log"
    export SWAYSOCK
    SWAYSOCK="$(ls "$XDG_RUNTIME_DIR"/sway-ipc.*.sock 2>/dev/null | head -1)"

    # Lazy XWayland nudge
    export DISPLAY=:0
    for i in 0 1 2 3 4 5; do
        if timeout 5 env DISPLAY=":$i" xdpyinfo >/dev/null 2>&1; then
            export DISPLAY=":$i"; break
        fi
    done
}

ensure_userpref() {
    if [ ! -f "$HOME/.config/upbge/5.0/config/userpref.blend" ]; then
        info "Setting up UPBGE userprefs (audio=None)..."
        LIBGL_ALWAYS_SOFTWARE=1 "$UPBGE_DIR/blender" --background --python-expr \
            "import bpy; bpy.context.preferences.system.audio_device='None'; \
             bpy.context.preferences.filepaths.use_scripts_auto_execute=True; \
             bpy.ops.wm.save_userpref()" 2>/dev/null || true
    fi
}

# ---------- mode handling
MODE="play"
BLEND_ARG=""
SCRIPT_ARG=""
WIZARD_TITLE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --wizard)
            MODE="wizard"
            WIZARD_TITLE="${2:-My Visual Novel}"
            shift 2
            ;;
        --setup-only)
            MODE="setup"
            shift
            ;;
        --blend)
            BLEND_ARG="$2"
            shift 2
            ;;
        --script)
            SCRIPT_ARG="$2"
            shift 2
            ;;
        *.blend)
            BLEND_ARG="$1"
            shift
            ;;
        *.rpy)
            SCRIPT_ARG="$1"
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# ---------- main
info "=== UPVN One-Click Launcher ==="

# Step 1: system setup
ensure_packages
ensure_swap
ensure_upbge
ensure_userpref

# Step 2: desktop
ensure_sway

# Step 3: project
if [ "$MODE" = "wizard" ]; then
    info "Creating wizard game: $WIZARD_TITLE"
    python3 "$REPO/tools/upvn_game_creator.py" --title "$WIZARD_TITLE" --theme school \
        --out "$REPO/game/script.rpy" 2>/dev/null || {
        # Fallback: use the builder directly
        python3 -c "
import sys; sys.path.insert(0, '$REPO')
sys.path.insert(0, '$REPO/engine')
from blend.upvn_editor_addon import UPVN_GameBuilder
b = UPVN_GameBuilder('$REPO/game/script.rpy')
b.create_quick_wizard(title='$WIZARD_TITLE', theme='school')
b.write()
print('Created: $REPO/game/script.rpy')
" 2>/dev/null || info "Script already exists or builder not available"
    fi
fi

# Step 4: determine blend
BLEND="${BLEND_ARG:-$REPO/blend/UPVN_Template.blend}"
case "$BLEND" in
    /*) ;;
    *)  BLEND="$REPO/$BLEND" ;;
esac
[ -f "$BLEND" ] || die "No such blend: $BLEND"

# Step 5: heartbeat
export UPVN_HEARTBEAT="${UPVN_HEARTBEAT:-/tmp/upvn_hb.json}"
export LIBGL_ALWAYS_SOFTWARE=1
export SDL_AUDIODRIVER=dummy
export LP_NUM_THREADS=1
rm -f "$UPVN_HEARTBEAT"

info "Playing: $BLEND"
info "  Window: $WIN  Duration: ${DURATION}s"
info "  Controls: click/Space/Enter=advance, 1-9=choices, H=history, Ctrl+S=save"

read -r -a WIN_A <<< "$WIN"
timeout -s KILL "$DURATION" "$UPBGE_DIR/blenderplayer" \
    -w "${WIN_A[0]}" "${WIN_A[1]}" "${WIN_A[2]}" "${WIN_A[3]}" \
    "$BLEND" 2>&1 | tail -50

rc=$?
info "Player exited ($rc). Heartbeat: $UPVN_HEARTBEAT"
[ -f "$UPVN_HEARTBEAT" ] && cat "$UPVN_HEARTBEAT" | python3 -m json.tool 2>/dev/null || true
exit $rc
