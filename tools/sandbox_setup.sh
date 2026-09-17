#!/bin/bash
# sandbox_setup.sh — rebuild the whole dev/test environment from scratch.
#
# Re-runnable after ANY workspace reset. Downloads (to /var/tmp, which is NOT
# snapshotted and survives resets):
#   * UPBGE 0.53 alpha (weekly-build-100, 2026-09-13)  -> /var/tmp/upbge
#   * Ren'Py SDK sample games (gui/tutorial/the_question) from the renpy/renpy
#     GitHub repo (complete files; the SDK tarball ships progressive-download
#     stubs)                                            -> $HOME/renpy
# and wires UPVN's addon+engine into the UPBGE addon dir, sets audio=None.
#
# Usage: tools/sandbox_setup.sh           # full setup
#        UPBGE_URL=... tools/sandbox_setup.sh   # custom UPBGE build
set -euo pipefail

UPBGE_URL="${UPBGE_URL:-https://github.com/UPBGE/upbge/releases/download/weekly-build-100/upbge-0.53-alpha-linux-x86_64-2026-09-13.tar.gz}"
UPBGE_DIR="${UPBGE_DIR:-/var/tmp/upbge}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RENPY_GAMES_URL="https://github.com/renpy/renpy"

info(){ echo "▸ $*"; }

# ---------- UPBGE ----------
if [ ! -x "$UPBGE_DIR/bin/blenderplayer" ]; then
    info "Downloading UPBGE 0.53 (~560 MB) to /var/tmp ..."
    curl -sL --retry 3 -o /var/tmp/upbge.tar.gz "$UPBGE_URL"
    rm -rf "$UPBGE_DIR" /var/tmp/upbge-extract
    mkdir -p /var/tmp/upbge-extract
    tar -xzf /var/tmp/upbge.tar.gz -C /var/tmp/upbge-extract
    # tarball root is 'build/'
    mv /var/tmp/upbge-extract/build "$UPBGE_DIR"
    rm -rf /var/tmp/upbge-extract /var/tmp/upbge.tar.gz
fi
info "UPBGE at $UPBGE_DIR"

# ---------- system packages ----------
need=()
for p in sway grim x11-xserver-utils xdotool scrot x11-utils imagemagick mesa-utils libgl1-mesa-dri; do
    dpkg -s "$p" &>/dev/null || need+=("$p")
done
if [ ${#need[@]} -gt 0 ] && sudo -n true 2>/dev/null; then
    info "Installing: ${need[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y -qq "${need[@]}"
fi

# ---------- Ren'Py sample games (complete files from GitHub) ----------
if [ ! -f "$HOME/renpy/tutorial/game/gui.rpy" ]; then
    info "Fetching complete Ren'Py sample games from GitHub ..."
    rm -rf /tmp/renpyrepo
    git clone -q --depth 1 --filter=blob:none --sparse "$RENPY_GAMES_URL" /tmp/renpyrepo
    ( cd /tmp/renpyrepo && git sparse-checkout set gui tutorial the_question )
    mkdir -p "$HOME/renpy"
    for g in gui tutorial the_question; do
        mkdir -p "$HOME/renpy/$g"
        cp -r /tmp/renpyrepo/$g/game "$HOME/renpy/$g/game"
    done
    rm -rf /tmp/renpyrepo
fi
info "Ren'Py games at $HOME/renpy/{gui,tutorial,the_question}"

# ---------- UPVN addon + engine into UPBGE ----------
ADDON_DIR="$HOME/.config/upbge/5.3/scripts/addons/upvn"
mkdir -p "$ADDON_DIR"
cp -f "$REPO/blend/upvn_editor_addon.py" "$ADDON_DIR/__init__.py"
rm -rf "$ADDON_DIR/engine" "$ADDON_DIR/bge_frontend"
cp -rf "$REPO/engine" "$ADDON_DIR/engine"
cp -rf "$REPO/bge_frontend" "$ADDON_DIR/bge_frontend"
cp -rf "$REPO/blend/fonts" "$ADDON_DIR/fonts" 2>/dev/null || true
info "UPVN addon installed to $ADDON_DIR"

# ---------- userprefs: audio=None (BUG-016), scripts auto-execute ----------
export LIBGL_ALWAYS_SOFTWARE=1
"$UPBGE_DIR/bin/blender" --background --python-expr "
import bpy
p = bpy.context.preferences.system
p.audio_device = 'None'
bpy.context.preferences.filepaths.use_scripts_auto_execute = True
bpy.ops.wm.save_userpref()
" >/dev/null 2>&1 || true
info "userprefs saved (audio=None)"

echo "SETUP OK — UPBGE: $UPBGE_DIR  games: $HOME/renpy"
