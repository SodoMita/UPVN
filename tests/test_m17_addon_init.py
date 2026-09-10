"""
M17 — Blender UX hardening (v0.6):
  * engine discovery: repo layout, isolated add-on (not found), zip install
  * self-contained add-on zip: engine importable straight from the archive
  * frontend: script_path property on VNController wins over legacy candidates
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADDON_SRC = ROOT / "blend" / "upvn_editor_addon.py"
FRONTEND_SRC = ROOT / "bge_frontend" / "frontend.py"
PY = sys.executable


def _load_addon(name="upvn_addon_m17"):
    """Import the add-on under an isolated module name (no bpy available)."""
    spec = importlib.util.spec_from_file_location(name, ADDON_SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_m17_discovery_repo_layout():
    mod = _load_addon()
    ok, info = mod.ensure_engine(retry=True)
    assert ok, info
    assert info["status"] == "ok"
    assert Path(info["root"]).resolve() == ROOT
    assert "engine_status_line" in dir(mod)
    assert "OK" in mod.engine_status_line()


def test_m17_engine_missing_is_friendly_not_crash():
    """A lone add-on .py (old install style) must degrade with a helpful message,
    not a bare 'Engine not available'."""
    mod = _load_addon("upvn_addon_m17_missing")
    mod.ENGINE_AVAILABLE = False
    mod._engine_api = None
    mod.ENGINE_INFO = {"status": "not_found", "root": None, "source": None,
                       "message": "no engine/ folder found — install the UPVN zip release",
                       "searched": []}
    with tempfile.TemporaryDirectory() as td:
        b = mod.UPVN_GameBuilder(str(Path(td) / "script.rpy"))
        ok, msg = b.validate()
        assert ok is False
        assert "engine not found" in msg
        assert b.preview_screenshot() is None  # no crash
        assert b.engine_ok() is False


def test_m17_frontend_script_path_resolution():
    spec = importlib.util.spec_from_file_location("upvn_frontend_m17", FRONTEND_SRC)
    fe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fe)

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        (base / "game").mkdir()
        (base / "game" / "script.rpy").write_text("label start:\n    return\n", encoding="utf-8")
        # fake bge.logic whose expandPath resolves // relative to td
        class FakeLogic:
            @staticmethod
            def expandPath(p):
                return str(base / str(p).lstrip("/")) if str(p).startswith("//") else p
        logic = FakeLogic()

        # 1) owner property wins
        owner = {"script_path": "//game/script.rpy"}
        path, tried = fe.resolve_script_path(logic, owner=owner)
        assert path == str(base / "game" / "script.rpy")
        assert path in tried

        # 2) owner points at missing file -> legacy candidates used
        owner2 = {"script_path": "//nowhere/script.rpy"}
        path2, tried2 = fe.resolve_script_path(logic, owner=owner2)
        assert path2 == str(base / "game" / "script.rpy")
        assert any("nowhere" in t for t in tried2)

        # 3) no file at all -> (None, tried) with all candidates
        with tempfile.TemporaryDirectory() as td2:
            base2 = Path(td2)
            class FakeLogic2:
                @staticmethod
                def expandPath(p):
                    return str(base2 / str(p).lstrip("/")) if str(p).startswith("//") else p
            path3, tried3 = fe.resolve_script_path(FakeLogic2(), owner=None, extra_candidates=["//missing.rpy"])
            assert path3 is None
            assert len(tried3) >= len(fe.ENGINE_CANDIDATES) + 1

    # sys.path bootstrap: engine next to bge_frontend's parent (repo layout)
    assert fe.ensure_engine_syspath() is True


def test_m17_package_addon_zip_single_folder():
    """v0.6.9 zip layout: ONE top-level folder (Blender extracts it on install).
    Simulates the install by extracting into a fake add-ons dir and importing
    from there — engine must be discovered right next to the add-on. Also checks
    that a compressed zip WITHOUT extraction yields a helpful message, not a crash."""
    sys.path.insert(0, str(ROOT))
    import tools.package_addon as pkg

    with tempfile.TemporaryDirectory() as td:
        zpath = pkg.build_addon_zip(Path(td), with_template=False)
        assert zpath.exists()
        names = set(zipfile.ZipFile(zpath).namelist())
        # single-folder layout: no zip-root engine/bge_frontend pollution
        assert "upvn_editor_addon/__init__.py" in names
        assert "upvn_editor_addon/engine/script/parser.py" in names
        assert "upvn_editor_addon/bge_frontend/frontend.py" in names
        assert "upvn_editor_addon/README-INSTALL.txt" in names
        assert "engine/script/parser.py" not in names          # no zip-root dup
        assert "bge_frontend/frontend.py" not in names
        assert not any(n.endswith(".pyc") for n in names)
        assert "upvn_editor_addon_v0.6.12.zip" in zpath.name

        # simulate Blender's UI install: extract into a fake addons dir
        addons_dir = Path(td) / "addons"
        addons_dir.mkdir()
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(addons_dir)

        # clean-subprocess proof: import the add-on from the extracted dir
        code = (
            "import sys, tempfile, os\n"
            "sys.path.insert(0, %r)\n"
            "import upvn_editor_addon as addon\n"
            "assert addon.ENGINE_AVAILABLE, addon.engine_diag_text()\n"
            "os.chdir(tempfile.mkdtemp())\n"
            "b = addon.UPVN_GameBuilder('game/script.rpy')\n"
            "b.add_character('e', 'Eileen', '#c8ffc8')\n"
            "b.add_say('e', 'hello from zip')\n"
            "b.write()\n"
            "ok, msg = b.validate()\n"
            "assert ok, msg\n"
            "print('ZIP_ADDON_OK')\n"
        ) % str(addons_dir)
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(Path.home())}
        r = subprocess.run([PY, "-c", code], capture_output=True, text=True, env=env, cwd=td)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "ZIP_ADDON_OK" in r.stdout

        # importing straight from the compressed archive (drop-into-addons):
        # engine is nested, so discovery must fail with a helpful hint, not crash
        code2 = (
            "import sys\n"
            "sys.path.insert(0, %r)\n"
            "import upvn_editor_addon as addon\n"
            "assert not addon.ENGINE_AVAILABLE\n"
            "msg = addon.ENGINE_INFO.get('message', '')\n"
            "assert 'Install from Disk' in msg, msg\n"
            "print('ZIP_HINT_OK')\n"
        ) % str(zpath)
        r2 = subprocess.run([PY, "-c", code2], capture_output=True, text=True, env=env, cwd=td)
        assert r2.returncode == 0, r2.stdout + r2.stderr
        assert "ZIP_HINT_OK" in r2.stdout


def test_m17_template_builder_and_make_template_import():
    """make_template.py must be importable headless and describe a real output."""
    sys.path.insert(0, str(ROOT))
    import tools.make_template as mt  # noqa: F401 (imports add-on module inside)
    # pure module import already proves the add-on import chain works in bpy-less python
    assert mt.ROOT == ROOT
