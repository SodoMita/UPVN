#!/usr/bin/env bash
# Install a stripped UPBGE blenderplayer for CI / agents who only *run* games.
#
# Prefers the UPVN slim player (~170 MB 7z) published from branch `build` as
# GitHub release tag upbge-player-<UPBGE_VERSION>. Falls back to the official
# ~408 MB tar.xz if that tag is missing (first run, or network blip).
#
# Recreate the slim archive when UPBGE's version changes:
#   python tools/package_template.py dist --player-only --platforms linux \
#       --with-player /path/to/official-upbge-0.xx-linux-x64
#   # merge to branch `build` — runnable.yml republishes the tag
#
# Usage:
#   tools/fetch_upbge.sh [parent_dir]
# Result: $parent/upbge-0.50-linux-x64/blenderplayer
#
# Env:
#   UPBGE_VERSION          default 0.50
#   UPVN_PLAYER_REPO       default SodoMita/UPVN
#   UPVN_UPBGE_CACHE       cache dir for the downloaded archive
#   UPVN_FETCH_OFFICIAL=1  skip slim, use official tarball
set -euo pipefail

VER="${UPBGE_VERSION:-0.50}"
PARENT="${1:-/opt/upbge}"
DEST="$PARENT/upbge-${VER}-linux-x64"
REPO="${UPVN_PLAYER_REPO:-SodoMita/UPVN}"
CACHE="${UPVN_UPBGE_CACHE:-${RUNNER_TEMP:-/tmp}/upbge-cache}"
SLIM_NAME="upvn-upbge-player-${VER}-linux-x64.7z"
SLIM_URL="https://github.com/${REPO}/releases/download/upbge-player-${VER}/${SLIM_NAME}"
OFFICIAL_URL="https://github.com/UPBGE/upbge/releases/download/v${VER}/upbge-${VER}-linux-x64.tar.xz"

info() { echo "▸ $*"; }
die() { echo "FATAL: $*" >&2; exit 1; }

if [ -x "$DEST/blenderplayer" ]; then
    info "UPBGE player already at $DEST/blenderplayer"
    exit 0
fi

mkdir -p "$CACHE" "$PARENT"

have_7z() { command -v 7z >/dev/null 2>&1 || command -v 7za >/dev/null 2>&1; }
zbin() { command -v 7z 2>/dev/null || command -v 7za 2>/dev/null; }

extract_slim() {
    local arc="$1"
    info "Extracting slim player $arc → $PARENT"
    "$(zbin)" x -y -o"$PARENT" "$arc" >/dev/null
    [ -x "$DEST/blenderplayer" ] || die "slim extract did not produce $DEST/blenderplayer"
}

fetch_official() {
    local tar="$CACHE/upbge-${VER}-linux-x64.tar.xz"
    if [ ! -f "$tar" ]; then
        info "Downloading official UPBGE ${VER} (~408 MB)…"
        curl -fL --retry 5 --retry-delay 2 -o "$tar.partial" "$OFFICIAL_URL"
        mv "$tar.partial" "$tar"
    fi
    info "Extracting official tarball → $PARENT"
    tar -xJf "$tar" -C "$PARENT"
    [ -x "$DEST/blenderplayer" ] || die "official extract did not produce $DEST/blenderplayer"
}

if [ "${UPVN_FETCH_OFFICIAL:-0}" != "1" ]; then
    slim="$CACHE/$SLIM_NAME"
    if [ ! -f "$slim" ]; then
        info "Trying slim player $SLIM_URL"
        if curl -fL --retry 3 --retry-delay 1 -o "$slim.partial" "$SLIM_URL"; then
            mv "$slim.partial" "$slim"
        else
            rm -f "$slim.partial"
            info "Slim player not published yet — official tarball fallback"
            slim=""
        fi
    fi
    if [ -n "${slim:-}" ] && [ -f "$slim" ]; then
        if have_7z; then
            extract_slim "$slim"
            info "OK slim player → $DEST"
            exit 0
        fi
        info "7z not installed; cannot extract slim player — official fallback"
    fi
fi

fetch_official
info "OK official UPBGE → $DEST"
