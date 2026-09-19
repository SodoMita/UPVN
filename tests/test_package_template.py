"""Per-OS game-template zips produced by tools/package_template.py."""
from __future__ import annotations

import os
import stat
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.package_addon import addon_version
from tools import package_template as pkg


def test_builds_three_os_zips(tmp_path):
    zips = pkg.build_all(tmp_path, ["linux", "windows", "macos"])
    names = {p.name for p in zips}
    assert names == {
        "upvn-game-template-linux-x64.zip",
        "upvn-game-template-windows-x64.zip",
        "upvn-game-template-macos-arm64.zip",
    }
    version = addon_version(ROOT / "blend" / "upvn_editor_addon.py")
    for zpath in zips:
        with zipfile.ZipFile(zpath) as zf:
            members = set(zf.namelist())
        top = "upvn-game-template/"
        assert top + "blend/UPVN_Template.blend" in members
        assert top + "engine/script/parser.py" in members
        assert top + "bge_frontend/frontend.py" in members
        assert top + "game/script.rpy" in members
        assert top + "LICENSE" in members
        assert top + "README.txt" in members
        assert not any("__pycache__" in n or n.endswith(".pyc") for n in members)
        readme = zipfile.ZipFile(zpath).read(top + "README.txt").decode("utf-8")
        assert version in readme
        assert "UPBGE 0.50" in readme
        script = zipfile.ZipFile(zpath).read(top + "game/script.rpy").decode("utf-8")
        assert "label start:" in script


def test_linux_launcher_is_executable(tmp_path):
    zpath = pkg.build_platform_zip(tmp_path, "linux")
    with zipfile.ZipFile(zpath) as zf:
        info = zf.getinfo("upvn-game-template/play.sh")
        mode = (info.external_attr >> 16) & 0o777
        assert mode & stat.S_IXUSR
        body = zf.read(info).decode("utf-8")
    assert "blenderplayer" in body
    assert "unset WAYLAND_DISPLAY" in body
    assert "play.bat" not in {n.rsplit("/", 1)[-1] for n in zipfile.ZipFile(zpath).namelist()}


def test_windows_bat_has_crlf(tmp_path):
    zpath = pkg.build_platform_zip(tmp_path, "windows")
    with zipfile.ZipFile(zpath) as zf:
        names = zf.namelist()
        bat = zf.read("upvn-game-template/play.bat")
    assert "upvn-game-template/play.bat" in names
    assert b"\r\n" in bat
    assert b"blenderplayer.exe" in bat
    assert not any(n.endswith("play.sh") for n in names)


def test_macos_has_play_command(tmp_path):
    zpath = pkg.build_platform_zip(tmp_path, "macos")
    with zipfile.ZipFile(zpath) as zf:
        names = zf.namelist()
        cmd = zf.read("upvn-game-template/play.command").decode("utf-8")
        url = zf.read("upvn-game-template/UPBGE_DOWNLOAD.txt").decode("utf-8")
    assert "play.command" in "\n".join(names)
    assert "blenderplayer" in cmd
    assert "macos-arm64" in url
    assert url.startswith("https://github.com/UPBGE/upbge/releases/")


def test_unknown_platform_exits():
    with pytest.raises(SystemExit):
        pkg.build_platform_zip(Path("/tmp"), "amiga")


def _fake_upbge(root: Path) -> Path:
    """Minimal UPBGE-shaped tree for strip tests (no real binary)."""
    root.mkdir(parents=True)
    (root / "lib").mkdir()
    (root / "lib" / "mesa").mkdir()
    (root / "license").mkdir()
    (root / "5.0" / "scripts" / "addons_core" / "cycles").mkdir(parents=True)
    (root / "5.0" / "scripts" / "modules").mkdir(parents=True)
    (root / "5.0" / "datafiles" / "locale").mkdir(parents=True)
    (root / "5.0" / "datafiles" / "colormanagement").mkdir(parents=True)
    (root / "5.0" / "python" / "lib" / "python3.11" / "site-packages" / "pxr").mkdir(parents=True)
    (root / "5.0" / "python" / "bin").mkdir(parents=True)
    (root / "5.0" / "datafiles" / "fonts").mkdir(parents=True)
    (root / "blenderplayer").write_text("#!/bin/sh\necho fake\n", encoding="utf-8")
    (root / "blenderplayer").chmod(0o755)
    (root / "blender").write_text("#!/bin/sh\necho editor\n", encoding="utf-8")
    (root / "lib" / "liboslexec.so.1.13").write_bytes(b"osl-real")
    (root / "lib" / "liboslexec.so").symlink_to("liboslexec.so.1.13")
    (root / "lib" / "libtbb.so.12").write_bytes(b"so")
    (root / "lib" / "mesa" / "libGL.so").write_bytes(b"mesa")
    (root / "lib" / "libhiprt64.so").write_bytes(b"hip")
    (root / "license" / "gpl.txt").write_text("GPL\n", encoding="utf-8")
    (root / "5.0" / "scripts" / "addons_core" / "cycles" / "x.py").write_text("x\n")
    (root / "5.0" / "scripts" / "modules" / "bge.py").write_text("# bge\n")
    (root / "5.0" / "datafiles" / "locale" / "x.mo").write_bytes(b"mo")
    (root / "5.0" / "datafiles" / "colormanagement" / "config.ocio").write_text("ocio\n")
    (root / "5.0" / "python" / "lib" / "libpython3.11.a").write_bytes(b"ar")
    (root / "5.0" / "python" / "lib" / "python3.11" / "site-packages" / "pxr" / "Usd.py").write_text("usd\n")
    (root / "5.0" / "python" / "bin" / "python3.11").write_bytes(b"elf")
    (root / "5.0" / "datafiles" / "fonts" / "droidsans.ttf").write_bytes(b"ttf")
    return root


def test_copy_stripped_player_drops_editor_and_cycles(tmp_path):
    src = _fake_upbge(tmp_path / "upbge")
    dest = tmp_path / "player"
    pkg.copy_stripped_player(src, dest)
    assert (dest / "blenderplayer").is_file()
    assert not (dest / "blender").exists()
    assert (dest / "lib" / "libtbb.so.12").is_file()
    assert not (dest / "lib" / "mesa" / "libGL.so").exists()
    assert not (dest / "lib" / "libhiprt64.so").exists()
    assert not (dest / "5.0" / "scripts" / "addons_core").exists()
    assert (dest / "5.0" / "scripts" / "modules" / "bge.py").is_file()
    assert not (dest / "5.0" / "datafiles" / "locale" / "x.mo").exists()
    assert (dest / "5.0" / "datafiles" / "colormanagement" / "config.ocio").is_file()
    assert not (dest / "5.0" / "python" / "lib" / "libpython3.11.a").exists()
    assert (dest / "license" / "gpl.txt").is_file()
    assert (dest / "lib" / "liboslexec.so").is_symlink()
    assert os.readlink(dest / "lib" / "liboslexec.so") == "liboslexec.so.1.13"
    assert (dest / "lib" / "liboslexec.so.1.13").is_file()
    assert (dest / "lib" / "liboslexec.so").lstat().st_size < 40
    assert not (dest / "5.0" / "python" / "lib" / "python3.11" / "site-packages" / "pxr").exists()
    assert not (dest / "5.0" / "python" / "bin").exists()
    assert not (dest / "5.0" / "datafiles" / "fonts").exists()


def test_runnable_linux_zip_embeds_player(tmp_path):
    src = _fake_upbge(tmp_path / "upbge")
    zpath = pkg.build_platform_zip(tmp_path / "out", "linux", player_src=src)
    assert zpath.name == "upvn-runnable-linux-x64.zip"
    with zipfile.ZipFile(zpath) as zf:
        names = set(zf.namelist())
        play = zf.read("upvn-game-template/play.sh").decode("utf-8")
        readme = zf.read("upvn-game-template/README.txt").decode("utf-8")
    assert "upvn-game-template/player/blenderplayer" in names
    assert "upvn-game-template/player/lib/libtbb.so.12" in names
    assert not any("addons_core" in n for n in names)
    assert not any(n.endswith("/blender") for n in names)
    assert "player/blenderplayer" in play
    assert "No extra download" in readme
    assert "upvn-game-template/game/script.rpy" in names
