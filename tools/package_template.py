#!/usr/bin/env python3
"""Build per-OS UPVN game-template zips, optionally with a bundled player.

Default (no player): small zips that need an UPBGE 0.50 install on PATH.

``--with-player /path/to/upbge-0.50-linux-x64`` copies a *stripped*
blenderplayer runtime into the linux zip so unzip + ``./play.sh`` runs
with nothing else to download. The editor binary, Cycles add-on, locales
and other editor-only files are left out.

Usage:
    python tools/package_template.py dist
    python tools/package_template.py dist --platforms linux \\
        --with-player /var/tmp/upbge/upbge-0.50-linux-x64
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.package_addon import ADDON_SRC, IGNORED, addon_version  # noqa: E402

BLEND_SRC = ROOT / "blend" / "UPVN_Template.blend"
LICENSE_SRC = ROOT / "LICENSE"
SUB_TREES = ("engine", "bge_frontend")

UPBGE_URLS = {
    "linux": (
        "https://github.com/UPBGE/upbge/releases/download/v0.50/"
        "upbge-0.50-linux-x64.tar.xz"
    ),
    "windows": (
        "https://github.com/UPBGE/upbge/releases/download/v0.50/"
        "upbge-0.50-windows-x64.7z"
    ),
    "macos": (
        "https://github.com/UPBGE/upbge/releases/download/v0.50/"
        "upbge-0.50-macos-arm64.dmg"
    ),
}

PLATFORM_SLUG = {
    "linux": "linux-x64",
    "windows": "windows-x64",
    "macos": "macos-arm64",
}

TOP = "upvn-game-template"

# Editor-only / optional GPU denoise — blenderplayer does not need these.
_PLAYER_DROP_TOP = {
    "blender", "blender-launcher", "blender-softwaregl",
    "blender-system-info.sh", "blender-thumbnailer",
    "org.upbge.UPBGE.desktop", "org.upbge.UPBGE.metainfo.xml",
    "org.upbge.UPBGE.svg", "org.upbge.UPBGE-symbolic.svg",
    "readme.html",
}
_PLAYER_DROP_DIR_PARTS = {
    "addons_core", "addons", "locale", "studiolights", "assets",
    "icons", "ensurepip", "idlelib", "turtledemo", "pip", "setuptools",
    "Cython", "mesa",
}
_PLAYER_DROP_NAME_PREFIX = (
    "libhiprt", "libOpenImageDenoise_device_",
)
_PLAYER_DROP_SUFFIX = (".a",)
_PLAYER_DROP_NAME_CONTAINS = ("config-3.",)


def _inject_init(base: pathlib.Path) -> None:
    dirs = [base] + sorted(p for p in base.rglob("*") if p.is_dir())
    for d in dirs:
        if not (d / "__init__.py").exists():
            (d / "__init__.py").write_text("", encoding="utf-8")


def _write_starter(dest: pathlib.Path) -> None:
    from blend.upvn_editor_addon import UPVN_GameBuilder

    dest.parent.mkdir(parents=True, exist_ok=True)
    b = UPVN_GameBuilder(str(dest), use_declarative=True)
    b.create_starter_declarative()
    b.write()
    ok, msg = b.validate()
    if not ok:
        raise SystemExit(f"starter script failed to validate: {msg}")


def _readme(platform: str, version: str, bundled: bool) -> str:
    url = UPBGE_URLS[platform]
    if bundled:
        return (
            f"UPVN runnable game v{version} ({PLATFORM_SLUG[platform]})\n"
            "======================================================\n"
            "Self-contained: unzip and run. No extra download.\n"
            "\n"
            "  unzip upvn-runnable-linux-x64.zip\n"
            "  cd upvn-game-template\n"
            "  ./play.sh\n"
            "\n"
            "Contents:\n"
            "  play.sh                     — launcher\n"
            "  player/blenderplayer        — stripped UPBGE 0.50 player\n"
            "  blend/UPVN_Template.blend   — pre-wired scene\n"
            "  engine/  bge_frontend/      — UPVN runtime\n"
            "  game/script.rpy             — starter story (edit this)\n"
            "\n"
            "The editor binary is not included (this is a player-only build).\n"
            "UPBGE is GPL; its licenses are in player/license/.\n"
            "UPVN is MIT (see LICENSE).\n"
            "\n"
            "System libraries the player still expects from the OS:\n"
            "  libX11, libGL (or Mesa llvmpipe), libpulse0 (audio; we set\n"
            "  audio=None in the bundled userpref so a missing Pulse server\n"
            "  should not crash).\n"
            f"Full UPBGE (if you want the editor): {url}\n"
        )
    if platform == "linux":
        play = "  ./play.sh"
        extra = (
            "  Extract the UPBGE tarball somewhere (e.g. ~/upbge) and either\n"
            "  put blenderplayer on PATH or set UPBGE_DIR to that folder.\n"
        )
    elif platform == "windows":
        play = "  play.bat"
        extra = (
            "  Extract the UPBGE .7z (7-Zip) and either add blenderplayer.exe\n"
            "  to PATH or set the UPBGE_DIR environment variable.\n"
        )
    else:
        play = "  double-click play.command  (or:  chmod +x play.command && ./play.command)"
        extra = (
            "  Open the UPBGE .dmg, copy UPBGE.app, then either put\n"
            "  blenderplayer on PATH or set UPBGE_DIR to the .app/Contents/MacOS\n"
            "  folder (or the extracted UPBGE directory).\n"
        )
    return (
        f"UPVN game template v{version} ({PLATFORM_SLUG[platform]})\n"
        "======================================================\n"
        "This zip is a playable visual-novel project skeleton:\n"
        "  blend/UPVN_Template.blend   — pre-wired UPBGE scene (empty VN_3DStage)\n"
        "  engine/  bge_frontend/      — runtime\n"
        "  game/script.rpy             — starter story (edit this)\n"
        "\n"
        "It does NOT include the UPBGE player binary (GPL, 300–650 MB).\n"
        "Download UPBGE 0.50 for this OS:\n"
        f"  {url}\n"
        "\n"
        "Play:\n"
        f"{extra}"
        f"{play}\n"
        "\n"
        "Or, after installing UPBGE:\n"
        "  blenderplayer -w 1280 720 0 0 blend/UPVN_Template.blend\n"
        "\n"
        "Authoring: open the .blend in UPBGE, enable the UPVN editor add-on\n"
        "(separate zip: upvn_editor_addon_v*.zip), press P to play.\n"
        "VN_3DStage is empty on purpose — drop your own 3D scene in.\n"
        "\n"
        "License: MIT (see LICENSE). UPBGE has its own licenses.\n"
    )


def _play_sh() -> str:
    return """#!/usr/bin/env bash
# UPVN launcher — prefers a bundled player/ tree (no extra download).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
pick() {
  if [ -x "$HERE/player/blenderplayer" ]; then
    echo "$HERE/player/blenderplayer"
    return 0
  fi
  local c
  for c in \\
      "${UPBGE_DIR:-}/blenderplayer" \\
      "${UPBGE_DIR:-}/upbge-0.50-linux-x64/blenderplayer" \\
      /opt/upbge/upbge-0.50-linux-x64/blenderplayer \\
      "$HOME/upbge/upbge-0.50-linux-x64/blenderplayer" \\
      "$(command -v blenderplayer 2>/dev/null || true)"; do
    [ -n "$c" ] && [ -x "$c" ] && { echo "$c"; return 0; }
  done
  return 1
}
PLAYER="$(pick)" || {
  echo "FATAL: blenderplayer not found." >&2
  echo "This zip has no bundled player — install UPBGE 0.50 or rebuild with --with-player." >&2
  exit 2
}
if [ -d "$HERE/player/lib" ]; then
  export LD_LIBRARY_PATH="$HERE/player/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
cd "$HERE"
unset WAYLAND_DISPLAY WAYLAND_SOCKET || true
export SDL_AUDIODRIVER="${SDL_AUDIODRIVER:-dummy}"
exec "$PLAYER" -w 1280 720 0 0 "$HERE/blend/UPVN_Template.blend"
"""


def _play_bat() -> str:
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        "set HERE=%~dp0\r\n"
        "set PLAYER=\r\n"
        "if exist \"%HERE%player\\blenderplayer.exe\" set PLAYER=%HERE%player\\blenderplayer.exe\r\n"
        "if not defined PLAYER if defined UPBGE_DIR if exist \"%UPBGE_DIR%\\blenderplayer.exe\" "
        "set PLAYER=%UPBGE_DIR%\\blenderplayer.exe\r\n"
        "if not defined PLAYER if exist \"%UPBGE_DIR%\\upbge-0.50-windows-x64\\"
        "blenderplayer.exe\" set PLAYER=%UPBGE_DIR%\\upbge-0.50-windows-x64\\"
        "blenderplayer.exe\r\n"
        "if not defined PLAYER where blenderplayer.exe >nul 2>&1 && "
        "set PLAYER=blenderplayer.exe\r\n"
        "if not defined PLAYER (\r\n"
        "  echo FATAL: blenderplayer.exe not found.\r\n"
        "  echo Install UPBGE 0.50 and set UPBGE_DIR, or add it to PATH.\r\n"
        "  echo See README.txt for the download URL.\r\n"
        "  exit /b 2\r\n"
        ")\r\n"
        "cd /d \"%HERE%\"\r\n"
        "\"%PLAYER%\" -w 1280 720 0 0 \"%HERE%blend\\UPVN_Template.blend\"\r\n"
    )


def _play_command() -> str:
    return """#!/bin/bash
# UPVN game-template launcher (macOS). Double-clickable.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
pick() {
  if [ -x "$HERE/player/blenderplayer" ]; then
    echo "$HERE/player/blenderplayer"
    return 0
  fi
  local c
  for c in \\
      "${UPBGE_DIR:-}/blenderplayer" \\
      "${UPBGE_DIR:-}/upbge-0.50-macos-arm64/blenderplayer" \\
      /Applications/UPBGE.app/Contents/MacOS/blenderplayer \\
      "$HOME/Applications/UPBGE.app/Contents/MacOS/blenderplayer" \\
      "$(command -v blenderplayer 2>/dev/null || true)"; do
    [ -n "$c" ] && [ -x "$c" ] && { echo "$c"; return 0; }
  done
  return 1
}
PLAYER="$(pick)" || {
  echo "FATAL: blenderplayer not found." >&2
  echo "Install UPBGE 0.50 (macOS arm64) and set UPBGE_DIR." >&2
  exit 2
}
cd "$HERE"
unset WAYLAND_DISPLAY WAYLAND_SOCKET || true
exec "$PLAYER" -w 1280 720 0 0 "$HERE/blend/UPVN_Template.blend"
"""


def _chmod_exec(path: pathlib.Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _drop_player_path(rel: pathlib.Path) -> bool:
    parts = set(rel.parts)
    if parts & _PLAYER_DROP_DIR_PARTS:
        return True
    name = rel.name
    if name in _PLAYER_DROP_TOP:
        return True
    if name.startswith(_PLAYER_DROP_NAME_PREFIX):
        return True
    if name.endswith(_PLAYER_DROP_SUFFIX):
        return True
    if any(s in name for s in _PLAYER_DROP_NAME_CONTAINS):
        return True
    return False


def copy_stripped_player(src: pathlib.Path, dest: pathlib.Path) -> pathlib.Path:
    """Copy a playable blenderplayer tree, dropping editor-only files."""
    src = pathlib.Path(src)
    dest = pathlib.Path(dest)
    player_bin = src / "blenderplayer"
    if not player_bin.is_file():
        raise SystemExit(f"no blenderplayer in {src}")
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    n_keep = 0
    for p in src.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(src)
        if _drop_player_path(rel):
            continue
        if "__pycache__" in rel.parts:
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
        n_keep += 1
    if not (dest / "blenderplayer").is_file():
        raise SystemExit("strip dropped blenderplayer — refuse to ship")
    _chmod_exec(dest / "blenderplayer")
    # Pulse is DT_NEEDED; copy the system .so if present so a Pulse-less
    # host still *loads* (userpref audio=None avoids talking to a server).
    libdir = dest / "lib"
    libdir.mkdir(exist_ok=True)
    for cand in (
        "/usr/lib/x86_64-linux-gnu/libpulse.so.0",
        "/lib/x86_64-linux-gnu/libpulse.so.0",
    ):
        if os.path.isfile(cand):
            shutil.copy2(cand, libdir / "libpulse.so.0")
            # companions
            parent = pathlib.Path(cand).parent
            for extra in parent.glob("libpulsecommon-*.so"):
                shutil.copy2(extra, libdir / extra.name)
            for extra in parent.glob("libpulse.so.0.*"):
                shutil.copy2(extra, libdir / extra.name)
            break
    print(f"[package_template] stripped player: {n_keep} files → {dest}")
    return dest


def write_portable_userpref(upbge_dir: pathlib.Path, dest_player: pathlib.Path) -> bool:
    """Bake audio_device=None into player/portable so the zip is crash-free."""
    blender = pathlib.Path(upbge_dir) / "blender"
    if not blender.is_file():
        return False
    cfg = dest_player / "portable" / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    expr = (
        "import bpy; bpy.context.preferences.system.audio_device='None'; "
        "bpy.context.preferences.filepaths.use_scripts_auto_execute=True; "
        "bpy.ops.wm.save_userpref()"
    )
    env = dict(os.environ)
    env["BLENDER_USER_CONFIG"] = str(cfg)
    env["LIBGL_ALWAYS_SOFTWARE"] = "1"
    env["SDL_AUDIODRIVER"] = "dummy"
    try:
        proc = subprocess.run(
            [str(blender), "--background", "--python-expr", expr],
            capture_output=True, text=True, timeout=180, env=env,
        )
    except Exception as exc:
        print(f"[package_template] userpref bake skipped: {exc}")
        return False
    pref = cfg / "userpref.blend"
    if pref.is_file():
        print(f"[package_template] portable userpref → {pref}")
        return True
    print("[package_template] userpref bake produced no file; "
          f"stdout={proc.stdout[-200:]!r} stderr={proc.stderr[-200:]!r}")
    return False


def _stage_common(staging: pathlib.Path) -> None:
    root = staging / TOP
    root.mkdir(parents=True)
    (root / "blend").mkdir()
    if not BLEND_SRC.exists():
        raise SystemExit(f"template blend missing: {BLEND_SRC}")
    shutil.copy2(BLEND_SRC, root / "blend" / "UPVN_Template.blend")
    fonts_src = ROOT / "blend" / "fonts"
    if fonts_src.is_dir():
        (root / "blend" / "fonts").mkdir()
        for f in fonts_src.iterdir():
            if f.is_file():
                shutil.copy2(f, root / "blend" / "fonts" / f.name)
    for tree in SUB_TREES:
        src = ROOT / tree
        if not src.is_dir():
            raise SystemExit(f"missing {src}")
        shutil.copytree(src, root / tree, ignore=IGNORED)
        _inject_init(root / tree)
    if LICENSE_SRC.exists():
        shutil.copy2(LICENSE_SRC, root / "LICENSE")
    _write_starter(root / "game" / "script.rpy")


def _add_platform_files(root: pathlib.Path, platform: str, version: str,
                        bundled: bool) -> None:
    (root / "README.txt").write_text(
        _readme(platform, version, bundled), encoding="utf-8"
    )
    if not bundled:
        (root / "UPBGE_DOWNLOAD.txt").write_text(
            UPBGE_URLS[platform] + "\n", encoding="utf-8"
        )
    if platform == "linux":
        p = root / "play.sh"
        p.write_text(_play_sh(), encoding="utf-8")
        _chmod_exec(p)
    elif platform == "windows":
        (root / "play.bat").write_text(_play_bat(), encoding="utf-8")
    else:
        p = root / "play.command"
        p.write_text(_play_command(), encoding="utf-8")
        _chmod_exec(p)


def _zip_exec_mode(path: pathlib.Path) -> int:
    name = path.name
    if name in {"play.sh", "play.command", "blenderplayer", "blenderplayer.exe"}:
        return 0o755
    if path.suffix in {".sh", ".command", ".so"} or ".so." in name:
        return 0o755
    try:
        if path.stat().st_mode & stat.S_IXUSR:
            return 0o755
    except Exception:
        pass
    return 0o644


def _zip_dir(src: pathlib.Path, dest: pathlib.Path) -> pathlib.Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for p in sorted(src.rglob("*")):
            if not p.is_file():
                continue
            if "__pycache__" in p.parts or p.suffix in {".pyc", ".pyo"}:
                continue
            arc = p.relative_to(src).as_posix()
            # zf.write streams from disk — do not slurp blenderplayer (228 MB)
            # into RAM on a 2 GB sandbox.
            zf.write(p, arc)
            info = zf.getinfo(arc)
            info.external_attr = (stat.S_IFREG | _zip_exec_mode(p)) << 16
    return dest


def build_platform_zip(out_dir: pathlib.Path, platform: str,
                       version: str | None = None,
                       player_src: pathlib.Path | None = None) -> pathlib.Path:
    if platform not in PLATFORM_SLUG:
        raise SystemExit(f"unknown platform {platform!r}")
    if player_src is not None and platform != "linux":
        raise SystemExit("--with-player is implemented for linux only "
                         "(this is the smallest runnable experiment)")
    version = version or addon_version(ADDON_SRC)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    bundled = player_src is not None
    name = (f"upvn-runnable-{PLATFORM_SLUG[platform]}.zip" if bundled
            else f"upvn-game-template-{PLATFORM_SLUG[platform]}.zip")
    dest = out_dir / name
    with tempfile.TemporaryDirectory(prefix="upvn_tmpl_") as tmp:
        staging = pathlib.Path(tmp)
        _stage_common(staging)
        root = staging / TOP
        _add_platform_files(root, platform, version, bundled=bundled)
        if bundled:
            copy_stripped_player(pathlib.Path(player_src), root / "player")
            write_portable_userpref(pathlib.Path(player_src), root / "player")
        _zip_dir(staging, dest)
    n = len(zipfile.ZipFile(dest).namelist())
    print(f"[package_template] {dest} — {n} entries, "
          f"{dest.stat().st_size // 1024}KB")
    return dest


def build_all(out_dir: pathlib.Path, platforms: list[str],
              player_src: pathlib.Path | None = None) -> list[pathlib.Path]:
    version = addon_version(ADDON_SRC)
    out = []
    for p in platforms:
        src = player_src if p == "linux" else None
        out.append(build_platform_zip(out_dir, p, version=version, player_src=src))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Package UPVN game templates per OS")
    ap.add_argument("out_dir", nargs="?", default=str(ROOT / "dist"))
    ap.add_argument(
        "--platforms",
        default="linux,windows,macos",
        help="comma-separated: linux,windows,macos",
    )
    ap.add_argument(
        "--with-player",
        default=None,
        help="path to extracted UPBGE 0.50 linux tree (bundles blenderplayer)",
    )
    args = ap.parse_args(argv)
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    player = pathlib.Path(args.with_player) if args.with_player else None
    built = build_all(pathlib.Path(args.out_dir), platforms, player_src=player)
    for p in built:
        print(f"[package_template] OK -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
