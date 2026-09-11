"""M26f: package_game end-to-end regression (blend flip needs the binary).

The packager is the ship path — it went unexecuted after the M26d tree-copy
change until this test existed. Locked in:
- the WHOLE project tree ships (assets/, stages/ — *.rpy-only lost them);
- the packaged blend has script_path pre-baked to //game/script.rpy (the
  "set the property by hand" README step is gone; graceful NOTE + manual
  fallback when no blender binary is present);
- no .blend1 backup junk survives the flip;
- the zip excludes nothing it should and exists.
"""
import os
import subprocess
import zipfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = "/opt/upbge/upbge-0.50-linux-x64/blender"
TOOL = os.path.join(REPO, "tools", "package_game.py")
PROJECT = os.path.join(REPO, "examples", "10_full_sample_game")

HAVE_BIN = os.path.exists(BIN)
pytestmark = [
    pytest.mark.skipif(
        not os.path.exists(PROJECT.replace("stages", "stages") if False else PROJECT),
        reason="sample project missing"),
]


@pytest.fixture(scope="module")
def packaged(tmp_path_factory):
    out = tmp_path_factory.mktemp("dist")
    proc = subprocess.run(
        ["python", TOOL, "--project", PROJECT, "--out", str(out)],
        capture_output=True, text=True, timeout=600,
        env={**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1"},
        cwd=REPO,
    )
    return proc, out


def test_packager_runs_clean(packaged):
    proc, out = packaged
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "FAIL" not in proc.stdout
    assert "Playable check" in proc.stdout  # headless self-check inside
    assert "Zip:" in proc.stdout
    assert (out / "10_full_sample_game.zip").exists()


def test_whole_project_tree_ships(packaged):
    """M26d fix: assets/ AND stages/ must survive packaging (was *.rpy only)."""
    _, out = packaged
    game = out / "10_full_sample_game" / "game"
    assert (game / "script.rpy").exists()
    assert any((game / "assets" / "backgrounds").glob("*.png"))
    assert (game / "stages" / "classroom_3d.blend").exists(), (
        "stages/ must ship — StageManager resolves //../game/stages/")
    # engine runtime next to the blend
    assert (out / "10_full_sample_game" / "engine" / "core").exists()
    assert (out / "10_full_sample_game" / "blend" / "UPVN_Template.blend").exists()


@pytest.mark.skipif(not HAVE_BIN, reason="UPBGE binary not present (/opt wiped)")
def test_blend_script_path_baked_and_clean(packaged):
    proc, out = packaged
    assert "script_path baked as //game/script.rpy" in proc.stdout, proc.stdout
    blend = out / "10_full_sample_game" / "blend" / "UPVN_Template.blend"
    # no .blend1 backup junk in the packaged build
    assert not (blend.parent / "UPVN_Template.blend1").exists()
    # and the property really reads //game/script.rpy
    expr = ("import bpy; print('PROPS:', [p.value for p in "
            "bpy.data.objects['VNController'].game.properties "
            "if p.name == 'script_path'])")
    p2 = subprocess.run([BIN, "--background", str(blend), "--python-expr", expr],
                        capture_output=True, text=True, timeout=180,
                        env={**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1"})
    assert any("PROPS: ['//game/script.rpy']" in ln
               for ln in p2.stdout.splitlines()), p2.stdout


def test_packaged_zip_is_healthy(packaged):
    _, out = packaged
    z = zipfile.ZipFile(out / "10_full_sample_game.zip")
    names = z.namelist()
    assert any(n.endswith("game/script.rpy") for n in names)
    assert any(n.endswith("game/stages/classroom_3d.blend") for n in names)
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names), \
        "zip must exclude bytecode (I-2)"
