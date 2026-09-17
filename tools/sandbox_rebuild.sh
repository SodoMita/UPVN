#!/bin/bash
# Rebuild the WHOLE visual-QA stack after a sandbox reset.
#
# A reset wipes: apt packages (sway, grim, xwayland…), /var/tmp (UPBGE, Ren'Py
# SDK, converted projects), /tmp (the sway runtime dir) and swap.  Nothing
# inside /home/user survives-safe either — keep big binaries OUT of the
# workspace or the snapshot blows past its ~128 MB cap.
#
#   tools/sandbox_rebuild.sh            # everything, idempotent
#   tools/sandbox_rebuild.sh --no-upbge # skip the 560 MB UPBGE download
#
# Afterwards:
#   source /tmp/wl-upvn/env.sh
#   tools/upvn_shot.sh <blend> out.png "match text"     # real UPBGE frame
#   tools/renpy_reference_shot.sh <proj> script.rpy:34 out.png
set -u
REPO="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
NO_UPBGE=0
[ "${1:-}" = "--no-upbge" ] && NO_UPBGE=1
info() { echo "▸ $*"; }

# 1) swap — blenderplayer peaks at ~1.2 GB RSS; on a 2 GB box the OOM killer
#    kills it before the first frame and the symptom is a black screenshot.
if ! grep -q "/swapfile" /proc/swaps 2>/dev/null; then
    if sudo -n true 2>/dev/null; then
        sudo -n fallocate -l 5G /swapfile 2>/dev/null \
            && sudo -n chmod 600 /swapfile && sudo -n mkswap /swapfile >/dev/null \
            && sudo -n /usr/sbin/swapon /swapfile && info "swap: 5G" \
            || info "swap: could not be added (no CAP_SYS_ADMIN?)"
    fi
fi

# 2) packages — grim (screenshots), sway (compositor), Xwayland (UPBGE 0.53's
#    native Wayland backend segfaults on a seat-less headless sway, so the
#    player must run as an X11 client), audio libs (BUG-016: without them the
#    player SIGSEGVs in AUD_Device_setSpeedOfSound).
PKGS="sway grim xwayland x11-xserver-utils x11-utils xdotool scrot imagemagick \
mesa-utils libgl1-mesa-dri libpulse0 libsndfile1 libjack-jackd2-0 libasound2 gdb"
MISSING=""
for p in $PKGS; do dpkg -s "$p" >/dev/null 2>&1 || MISSING="$MISSING $p"; done
if [ -n "$MISSING" ] && sudo -n true 2>/dev/null; then
    info "apt install:$MISSING"
    sudo -n apt-get update -qq
    sudo -n apt-get install -y -qq $MISSING
fi

# 3) UPBGE 0.53 (weekly build) — the build the player actually runs.
if [ "$NO_UPBGE" = "0" ] && [ ! -x /var/tmp/upbge/bin/blenderplayer ]; then
    info "UPBGE 0.53 -> /var/tmp/upbge (uses tools/sandbox_setup.sh)"
    UPBGE_DIR=/var/tmp/upbge bash "$REPO/tools/sandbox_setup.sh" 2>&1 | tail -3
fi

# 4) Ren'Py SDK + sample games — ground truth for "looks like Ren'Py?".
if [ ! -x /var/tmp/renpy/renpy-8.3.6-sdk/renpy.sh ]; then
    info "Ren'Py SDK -> /var/tmp/renpy"
    mkdir -p /tmp/renpy_dl
    ( cd /tmp/renpy_dl && bash "$REPO/tools/fetch_renpy_sdk.sh" 8.3.6 /tmp/renpy_dl >/dev/null 2>&1 )
    sudo mkdir -p /var/tmp/renpy && sudo chown "$(id -un)" /var/tmp/renpy
    mv /tmp/renpy_dl/renpy-8.3.6-sdk /var/tmp/renpy/ 2>/dev/null
    rm -rf /tmp/renpy_dl
fi
if [ ! -d /var/tmp/renpy/renpy-8.3.6-sdk/the_question/game ]; then
    info "Ren'Py sample games already ship inside the SDK (the_question, tutorial)"
fi

# 5) headless sway + pixman
info "sway up"
UPBGE_DIR=/var/tmp/upbge/bin bash "$REPO/tools/sway_up.sh" up 2>&1 | head -3

info "DONE — source /tmp/wl-upvn/env.sh, then tools/upvn_shot.sh / tools/renpy_reference_shot.sh"
