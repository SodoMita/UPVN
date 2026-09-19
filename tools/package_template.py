#!/usr/bin/env python3
"""Build per-OS UPVN *game template* zips (Linux / Windows / macOS).

These are playable project skeletons — blend + engine + frontend + a starter
``game/script.rpy`` + an OS launcher. They do **not** redistributable-bundle
UPBGE (GPL, 300–650 MB); each README points at the matching official
UPBGE 0.50 download. Launchers look for ``blenderplayer`` on PATH /
``UPBGE_DIR`` / common install locations.

Usage:
    python tools/package_template.py [out_dir]
    python tools/package_template.py dist --platforms linux,windows,macos

Output (default ``dist/``):
    upvn-game-template-linux-x64.zip
    upvn-game-template-windows-x64.zip
    upvn-game-template-macos-arm64.zip
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import stat
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


def _inject_init(base: pathlib.Path) -> None:
    dirs = [base] + sorted(p for p in base.rglob("*") if p.is_dir())
    for d in dirs:
        if not (d / "__init__.py").exists():
            (d / "__init__.py").write_text("", encoding="utf-8")


def _write_starter(dest: pathlib.Path) -> None:
    """Write a short declarative starter (no bpy)."""
    from blend.upvn_editor_addon import UPVN_GameBuilder

    dest.parent.mkdir(parents=True, exist_ok=True)
    b = UPVN_GameBuilder(str(dest), use_declarative=True)
    b.create_starter_declarative()
    b.write()
    ok, msg = b.validate()
    if not ok:
        raise SystemExit(f"starter script failed to validate: {msg}")


def _readme(platform: str, version: str) -> str:
    url = UPBGE_URLS[platform]
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
# UPVN game-template launcher (Linux).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
pick() {
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
  echo "Install UPBGE 0.50 and set UPBGE_DIR, or put blenderplayer on PATH." >&2
  echo "Download: ${UPBGE_URL:-see README.txt}" >&2
  exit 2
}
cd "$HERE"
# UPBGE 0.53+ native Wayland can SIGSEGV headless; X11/XWayland is the
# supported player path. Harmless on a normal desktop.
unset WAYLAND_DISPLAY WAYLAND_SOCKET || true
exec "$PLAYER" -w 1280 720 0 0 "$HERE/blend/UPVN_Template.blend"
"""


def _play_bat() -> str:
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        "set HERE=%~dp0\r\n"
        "set PLAYER=\r\n"
        "if defined UPBGE_DIR if exist \"%UPBGE_DIR%\\blenderplayer.exe\" "
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


def _add_platform_files(root: pathlib.Path, platform: str, version: str) -> None:
    (root / "README.txt").write_text(_readme(platform, version), encoding="utf-8")
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


def _zip_dir(src: pathlib.Path, dest: pathlib.Path) -> pathlib.Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src.rglob("*")):
            if not p.is_file():
                continue
            if "__pycache__" in p.parts or p.suffix in {".pyc", ".pyo"}:
                continue
            arc = p.relative_to(src).as_posix()
            # Preserve +x on launchers inside the zip (Unix unzip).
            info = zipfile.ZipInfo(arc)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if p.suffix in {".sh", ".command"} or p.name in {
                "play.sh", "play.command",
            } else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.date_time = (2026, 1, 1, 0, 0, 0)
            zf.writestr(info, p.read_bytes())
    return dest


def build_platform_zip(out_dir: pathlib.Path, platform: str,
                       version: str | None = None) -> pathlib.Path:
    if platform not in PLATFORM_SLUG:
        raise SystemExit(f"unknown platform {platform!r}")
    version = version or addon_version(ADDON_SRC)
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"upvn-game-template-{PLATFORM_SLUG[platform]}.zip"
    dest = out_dir / name
    with tempfile.TemporaryDirectory(prefix="upvn_tmpl_") as tmp:
        staging = pathlib.Path(tmp)
        _stage_common(staging)
        _add_platform_files(staging / TOP, platform, version)
        _zip_dir(staging, dest)
    n = len(zipfile.ZipFile(dest).namelist())
    print(f"[package_template] {dest} — {n} entries, "
          f"{dest.stat().st_size // 1024}KB")
    return dest


def build_all(out_dir: pathlib.Path, platforms: list[str]) -> list[pathlib.Path]:
    version = addon_version(ADDON_SRC)
    return [build_platform_zip(out_dir, p, version=version) for p in platforms]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Package UPVN game templates per OS")
    ap.add_argument("out_dir", nargs="?", default=str(ROOT / "dist"))
    ap.add_argument(
        "--platforms",
        default="linux,windows,macos",
        help="comma-separated: linux,windows,macos",
    )
    args = ap.parse_args(argv)
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    built = build_all(pathlib.Path(args.out_dir), platforms)
    for p in built:
        print(f"[package_template] OK -> {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
