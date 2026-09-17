#!/bin/bash
# Download + unpack a Ren'Py SDK (for parity work against original projects).
#
#   tools/fetch_renpy_sdk.sh [VERSION] [DEST_DIR]
#     VERSION  default 8.3.6
#     DEST_DIR default $RENPY_DEST or /home/user/ext   (kept OUT of the repo)
#
# Idempotent: reuses existing zip / unpacked dir. Prints the sdk path at the end.
set -e
V="${1:-${RENPY_VERSION:-8.3.6}}"
DEST="${2:-${RENPY_DEST:-/home/user/ext}}"
SDK="$DEST/renpy-$V-sdk"

mkdir -p "$DEST"
cd "$DEST"
if [ ! -x "$SDK/renpy.sh" ]; then
    if [ ! -f "renpy-$V-sdk.zip" ]; then
        echo "[fetch] downloading Ren'Py $V SDK ..."
        curl -fL --retry 3 -o "renpy-$V-sdk.zip" \
            "https://www.renpy.org/dl/$V/renpy-$V-sdk.zip"
    fi
    echo "[fetch] unpacking ..."
    unzip -q "renpy-$V-sdk.zip"
fi
echo "[fetch] Ren'Py $V ready: $SDK"
echo "$SDK"
