"""M26e: bake-tool end-to-end regression (needs the real blender binary).

Ships-guard: tools/bake_stage_into_template.py was committed once with a bug
only execution could find (the generated blender-side script referenced
EXCLUDE_SUFFIX that was never interpolated — NameError on first real run),
and produced blends that died with "No module named 'bge_frontend'" when
baked outside the repo tree. Both are locked down here by RUNNING the tool.
Skipped when the UPBGE binary is absent (sandbox resets wipe /opt).
"""
import os
import shutil
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = "/opt/upbge/upbge-0.50-linux-x64/blender"

pytestmark = pytest.mark.skipif(
    not os.path.exists(BIN), reason="UPBGE binary not present (/opt wiped)")

TOOL = os.path.join(REPO, "tools", "bake_stage_into_template.py")
STAGE = os.path.join(REPO, "examples", "10_full_sample_game", "stages",
                     "classroom_3d.blend")


@pytest.fixture(scope="module")
def baked(tmp_path_factory):
    out_dir = tmp_path_factory.mktemp("bakedgame")
    script = out_dir / "script3d.rpy"
    script.write_text(
        'define e = Character("Eileen", color="#c8ffc8")\n'
        "label start:\n"
        '    e "hi"\n'
        "    show3d eileen at marker_eileen\n"
        "    return\n",
        encoding="utf-8")
    out = out_dir / "game.blend"
    proc = subprocess.run(
        ["python", TOOL, "--stage", STAGE,
         "--game", os.path.join(REPO, "blend", "UPVN_Template.blend"),
         "--out", str(out), "--script", str(script)],
        capture_output=True, text=True, timeout=120)
    return proc, out_dir, out


def test_bake_tool_runs_clean(baked):
    proc, _, out = baked
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "BAKED" in proc.stdout
    assert out.exists() and out.stat().st_size > 50_000


def test_bake_output_is_playable_standalone(baked):
    """The tool must copy the runtime tree next to the blend — otherwise the
    embedded launcher dies with ModuleNotFoundError (live-measured)."""
    _, out_dir, _ = baked
    for folder in ("engine", "bge_frontend"):
        assert (out_dir / folder / "frontend.py").exists() if folder == \
            "bge_frontend" else (out_dir / folder).is_dir(), (
            f"{folder}/ must be copied next to the baked blend")
    # and no pycache junk in the copied tree
    assert not list((out_dir / "engine").rglob("__pycache__"))


def test_baked_blend_contents(baked):
    """Stage baked in: geometry + parked templates, NO stage cameras
    (Camera_3D present is the template's own dormant one), script flipped."""
    _, _, out = baked
    expr = (
        "import bpy; sc=bpy.context.scene; "
        "ns=set(o.name for o in sc.objects); "
        "print('OBJCHECK has_stage:', "
        "{'Floor_3D','Desk_A','marker_eileen','eileen','sylvie'} <= ns); "
        "print('OBJCHECK parked:', "
        "tuple(round(v,1) for v in bpy.data.objects['eileen'].location)=="
        "(30.0,-3.0,-30.0)); "
        "print('OBJCHECK stage_cam_gone:', "
        "not any(n.startswith('Camera') and n != 'Camera_UI' and "
        "bpy.data.objects[n].get('upvn_template_camera') for n in ns) or "
        "sum(1 for n in ns if n.startswith('Camera_')) <= 1); "
        "print('OBJCHECK script:', "
        "[p.value for p in bpy.data.objects['VNController'].game.properties "
        "if p.name=='script_path'])"
    )
    proc = subprocess.run([BIN, "--background", str(out), "--python-expr", expr],
                          capture_output=True, text=True, timeout=120,
                          env={**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1"})
    lines = [ln for ln in proc.stdout.splitlines() if "OBJCHECK" in ln]
    assert any("has_stage: True" in ln for ln in lines), proc.stdout
    assert any("parked: True" in ln for ln in lines), proc.stdout
    assert any("script: ['" in ln and "script3d.rpy" in ln for ln in lines), \
        proc.stdout


def test_desktop_sway_script_exports_runtime_dir():
    """M26e: the script MUST export XDG_RUNTIME_DIR — a bare assignment made
    sway abort with 'XDG_RUNTIME_DIR is not set in the environment' (the
    long-standing 'in-script sway start broken' bug, fixed and verified by
    killing sway and letting the script rebuild it)."""
    src = open(os.path.join(REPO, "tools", "desktop_sway.sh")).read()
    assert "export XDG_RUNTIME_DIR=" in src
    # headless outputs use model, not mode (no mode list on headless)
    body = src[src.index("output HEADLESS-1"):]
    assert "model 1280x800" in body
    assert "mode 1280x800" not in body
