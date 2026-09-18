"""Scene generator settings live in ONE module.

Edit engine/render/scene_settings.py (including knobs that match Blender's
factory defaults). Generators must import from there instead of carrying
their own copies — otherwise changing a value means hunting every script
AND regenerating the template.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.render import scene_settings as ss  # noqa: E402
from engine.render import contract  # noqa: E402


GENERATORS = (
    "tools/make_template.py",
    "tools/add_template_ui_objects.py",
    "tools/update_template_materials.py",
    "tools/wire_converted_blend.py",
    "tools/apply_gui_to_blend.py",
    "tools/bake_stage_into_template.py",
    "blend/upvn_editor_addon.py",
)


def test_scene_settings_importable_without_bpy():
    assert ss.CAMERA_UI_ORTHO_SCALE == 15.0
    assert ss.VIEW_TRANSFORM == "Standard"
    assert ss.GRAVITY == (0.0, 0.0, -9.81)
    assert ss.RENDER_FPS == 24
    assert ss.CAMERA_CLIP_START == 0.1
    assert ss.CAMERA_3D_LENS == 50.0
    assert ss.SCENE_NAME == "VN_Main"


def test_blender_factory_equals_are_still_named():
    """Values identical to Blender's factory file must still be variables."""
    pins = list(ss.iter_blender_default_pins())
    names = {n for n, _v, _note in pins}
    for required in (
        "RENDER_RESOLUTION_X",
        "RENDER_FPS",
        "CAMERA_CLIP_START",
        "CAMERA_SENSOR_WIDTH",
        "GRAVITY",
        "UNIT_SCALE_LENGTH",
        "VIEW_EXPOSURE",
        "VIEW_GAMMA",
        "TEXT_EXTRUDE",
        "EEVEE_TAA_RENDER_SAMPLES",
    ):
        assert required in names, required
    consts = ss.public_constants()
    assert "VIEW_TRANSFORM" in consts
    assert "SUN_ANGLE" in consts
    assert "CHOICE_PLANE_SCALE" in consts
    assert "STAGE_FLOOR_SIZE" not in consts


def test_apply_scene_environment_is_safe_without_bpy():
    assert ss.apply_scene_environment(None) == {}
    ss.apply_camera_optics(None, ortho=True)
    ss.apply_mesh_physics(None)


def test_contract_reexports_generator_knobs():
    assert contract.CAMERA_UI_ORTHO_SCALE == ss.CAMERA_UI_ORTHO_SCALE
    assert contract.CAMERA_UI_LOCATION == ss.CAMERA_UI_LOCATION
    assert contract.SPRITE_SCALE == ss.SPRITE_SCALE
    assert contract.SPRITE_POSITIONS == ss.SPRITE_POSITIONS
    assert set(contract.POSITIONS) == set(ss.POSITIONS)
    assert contract.CHOICE_COUNT == ss.CHOICE_COUNT
    assert contract.IMAGE_MODE_DEFAULT == ss.IMAGE_MODE_DEFAULT
    assert contract.COLLECTIONS == ss.COLLECTIONS


def test_generators_import_scene_settings():
    missing = []
    for rel in GENERATORS:
        src = (ROOT / rel).read_text(encoding="utf-8")
        if "scene_settings" not in src:
            missing.append(rel)
    assert missing == [], f"generators must import scene_settings: {missing}"


def test_generators_do_not_redefine_ortho_scale():
    """CAMERA_UI_ORTHO_SCALE must be assigned only in scene_settings.py."""
    offenders = []
    for rel in GENERATORS + ("engine/render/scene_manager.py",
                             "bge_frontend/frontend.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "CAMERA_UI_ORTHO_SCALE":
                        # allow `CAMERA_UI_ORTHO_SCALE = ss.CAMERA_UI_ORTHO_SCALE`
                        # or `CAMERA_UI_ORTHO_SCALE = 15.0` only as last-ditch except
                        offenders.append(f"{rel}:{node.lineno}")
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.target.id == "CAMERA_UI_ORTHO_SCALE":
                    offenders.append(f"{rel}:{node.lineno}")
    # fallback `CAMERA_UI_ORTHO_SCALE = 15.0` inside except is tolerated in
    # the frontend (engine may be missing) and the addon (same).
    real = []
    for off in offenders:
        rel, line = off.rsplit(":", 1)
        src_line = (ROOT / rel).read_text(encoding="utf-8").splitlines()[int(line) - 1]
        if "ss." in src_line or "_ss." in src_line:
            continue
        real.append(f"{off}: {src_line.strip()}")
    # frontend/addon except-fallbacks are the only remaining 15.0 assigns
    for item in real:
        assert "15.0" in item, item


def test_choice_helpers_match_spacing():
    loc0 = ss.choice_location(0)
    loc1 = ss.choice_location(1)
    assert loc0[0] == ss.CHOICE_LOCATION_X
    assert loc0[1] == ss.CHOICE_LOCATION_Y
    assert abs((loc0[2] - loc1[2]) - ss.CHOICE_SPACING) < 1e-9


def test_make_template_does_not_build_a_classroom():
    src = (ROOT / "tools" / "make_template.py").read_text(encoding="utf-8")
    for banned in ("Floor_classroom", "Desk_", "Blackboard", "Char_Eileen",
                   "STAGE_FLOOR", "STAGE_DESK", "STAGE_MAT_"):
        assert banned not in src, banned
    assert "build_vn_scene" in src
