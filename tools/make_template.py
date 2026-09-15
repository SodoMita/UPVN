"""
Generate UPVN_Template.blend via bpy (run inside UPBGE/Blender).

Usage:
  ./upbge-0.50-linux-x64/blender --background --python tools/make_template.py
  # or with explicit output:
  ./upbge-0.50-linux-x64/blender --background --python tools/make_template.py -- blend/my.blend

v0.6 (2026-09-08): fully data-API (no bpy.ops/context → reliable --background),
reuses the add-on's build_vn_scene() so the produced .blend contains the exact
same wiring as "Setup Scene" in the UPVN panel:
    VN_Main scene, Camera_UI (ortho) + Camera_3D, five VN_* collections,
    BG_Plane + Dialogue_Box, VNController empty with script_path + upvn_root,
    Always(pulse) -> Python launcher brick (path-bootstrap text datablock),
plus the richer 3D classroom stage (floor, desks, board, markers, presets,
placeholder capsules) used by load_stage/show3d examples.
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import bpy  # noqa: F401
except ImportError:
    bpy = None  # module stays importable headless; main() explains


# ---------------------------------------------------------------- small data-API helpers — M27 HQ
def _mat(name: str, color=(0.5, 0.5, 0.5, 1.0), roughness=0.8, emission=False, emission_strength=0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    try:
        principled = mat.node_tree.nodes.get("Principled BSDF")
        if principled:
            principled.inputs["Base Color"].default_value = color
            try:
                principled.inputs["Roughness"].default_value = roughness
            except Exception:
                pass
            # HQ: slight metallic for wood, less for walls
            try:
                if "Wood" in name or "Desk" in name:
                    principled.inputs["Metallic"].default_value = 0.0
                    principled.inputs["Specular"].default_value = 0.3
            except Exception:
                pass
        if emission and emission_strength > 0:
            # mix emission for UI planes
            nt = mat.node_tree
            try:
                em = nt.nodes.new("ShaderNodeEmission")
                em.inputs["Color"].default_value = color
                em.inputs["Strength"].default_value = emission_strength
                out = nt.nodes.get("Material Output")
                if out:
                    # keep principled but add emission via mix? Simplify: use emission only for UI
                    pass
            except Exception:
                pass
    except Exception:
        pass
    return mat

def _mat_hq(name: str, color, hq_type="ui"):
    """HQ material with improved node graph for better visuals."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nt = mat.node_tree
    try:
        nt.nodes.clear()
    except Exception:
        pass
    if hq_type == "ui":
        # Emission-only for VN UI (unlit, high quality)
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        objinfo = nt.nodes.new("ShaderNodeObjectInfo")
        try:
            em.inputs["Color"].default_value = color
            em.inputs["Strength"].default_value = 1.2
            nt.links.new(objinfo.outputs["Color"], em.inputs["Color"])
        except Exception:
            pass
        nt.links.new(em.outputs[0], out.inputs[0])
        try:
            mat.blend_method = "OPAQUE"
            mat.shadow_method = "NONE"
        except Exception:
            pass
    else:
        # PBR for 3D stage — Principled with better settings
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        principled = nt.nodes.new("ShaderNodeBsdfPrincipled")
        try:
            principled.inputs["Base Color"].default_value = color
            principled.inputs["Roughness"].default_value = 0.7 if hq_type == "wood" else 0.9
            if hq_type == "wood":
                try:
                    principled.inputs["Specular"].default_value = 0.25
                except Exception:
                    pass
        except Exception:
            pass
        nt.links.new(principled.outputs[0], out.inputs[0])
    return mat


def _plane(name: str, size: float, pos, rot=None, mat=None, collection=None):
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], [],
                     [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.scale = (size / 2, size / 2, 1)
    obj.location = pos
    if rot:
        obj.rotation_euler = rot
    if mat:
        obj.data.materials.append(mat)
    if collection:
        collection.objects.link(obj)
    else:
        bpy.context.scene.collection.objects.link(obj)
    return obj


def _cube(name: str, scale, pos, mat):
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(
        [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
         (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)],
        [], [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.scale = scale
    obj.location = pos
    obj.data.materials.append(mat)
    return obj


def _cylinder(name: str, radius, depth, pos, mat, collection):
    import math
    segs = 24
    verts, faces = [], []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        verts.append((math.cos(a) * radius, math.sin(a) * radius, -depth / 2))
    base = len(verts)
    for i in range(segs):
        a = 2 * math.pi * i / segs
        verts.append((math.cos(a) * radius, math.sin(a) * radius, depth / 2))
    for i in range(segs):
        faces.append((i, (i + 1) % segs, base + (i + 1) % segs, base + i))
    faces.append(tuple(range(segs)))
    faces.append(tuple(range(base, base + segs)))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = pos
    obj.data.materials.append(mat)
    collection.objects.link(obj)
    return obj


def _empty(name: str, pos, display="ARROWS", size=0.5, rot=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = display
    e.empty_display_size = size
    e.location = pos
    if rot:
        e.rotation_euler = rot
    return e


# ---------------------------------------------------------------- build
def main(out_path: Path | None = None):
    if bpy is None:
        raise SystemExit("This script must be run inside Blender/UPBGE with bpy.")
    out_path = out_path or (ROOT / "blend" / "UPVN_Template.blend")

    # clean slate: end up with exactly one scene, VN_Main (Blender forbids
    # removing the last local scene, so rename the factory 'Scene' when alone)
    scene = bpy.data.scenes.get("VN_Main")
    if scene is None:
        if len(bpy.data.scenes) == 1:
            scene = bpy.data.scenes[0]
            scene.name = "VN_Main"
        else:
            scene = bpy.data.scenes.new("VN_Main")
    for sc in list(bpy.data.scenes):
        if sc is not scene:
            bpy.data.scenes.remove(sc, do_unlink=True)
    # empty master collection of leftover factory objects
    for ob in list(scene.collection.objects):
        scene.collection.objects.unlink(ob)
    try:
        bpy.context.window.scene = scene
    except Exception:
        pass
    bpy.data.orphans_purge()

    # ---- core UPVN wiring (same code as the add-on's Setup Scene) ----
    from blend.upvn_editor_addon import build_vn_scene  # engine discovery runs at import
    ctrl = build_vn_scene(bpy, scene_name="VN_Main",
                          script_path="//game/script.rpy")

    # ---- 3D classroom stage (HQ) — load_stage classroom_3d content ----
    stage_col = bpy.data.collections["VN_3DStage"]
    # M27 HQ materials — more polished, PBR for 3D
    wood = _mat_hq("MatDesk", (0.52, 0.38, 0.26, 1.0), hq_type="wood")
    wood_dark = _mat_hq("MatDeskTeacher", (0.58, 0.44, 0.32, 1.0), hq_type="wood")
    green = _mat_hq("MatBoard", (0.10, 0.20, 0.12, 1.0), hq_type="wall")
    grey = _mat_hq("MatFloor", (0.28, 0.28, 0.32, 1.0), hq_type="floor")
    wall_mat = _mat_hq("MatWall", (0.85, 0.84, 0.80, 1.0), hq_type="wall")
    window_mat = _mat_hq("MatWindow", (0.6, 0.8, 1.0, 0.3), hq_type="ui")
    light_mat = _mat_hq("MatLight", (1.0, 0.95, 0.8, 1.0), hq_type="ui")
    eileen_c = _mat_hq("MatChar_Eileen_placeholder", (0.55, 0.85, 0.55, 1.0), hq_type="char")
    sylvie_c = _mat_hq("MatChar_Sylvie_placeholder", (0.55, 0.55, 0.92, 1.0), hq_type="char")

    # Floor — HQ larger
    floor = _plane("Floor_classroom", 14.0, (0, 0, 0), mat=grey, collection=stage_col)

    # Walls — HQ addition: back wall and side walls for depth
    back_wall = _plane("Wall_back", 12.0, (0, 2.5, 1.5), rot=(1.5708, 0, 0), mat=wall_mat, collection=stage_col)
    back_wall.scale = (2.0 * 12 / 2, 1.2 * 12 / 2, 1)
    left_wall = _plane("Wall_left", 10.0, (-6.0, 0, 1.5), rot=(0, 1.5708, 0), mat=wall_mat, collection=stage_col)
    left_wall.scale = (1.2 * 10 / 2, 1.0 * 10 / 2, 1)
    right_wall = _plane("Wall_right", 10.0, (6.0, 0, 1.5), rot=(0, -1.5708, 0), mat=wall_mat, collection=stage_col)
    right_wall.scale = (1.2 * 10 / 2, 1.0 * 10 / 2, 1)

    # Windows — HQ addition
    for i, x in enumerate([-4.5, 4.5]):
        win = _plane(f"Window_{i}", 2.0, (x, 2.48, 1.8), rot=(1.5708, 0, 0), mat=window_mat, collection=stage_col)
        win.scale = (0.8 * 2 / 2, 1.0 * 2 / 2, 1)

    # Ceiling lights — HQ
    for i, pos in enumerate([(0, 0, 3.0), (-2.5, -0.5, 3.0), (2.5, -0.5, 3.0)]):
        light = _cube(f"Light_{i}", (0.6, 0.2, 0.05), pos, light_mat)
        stage_col.objects.link(light)

    # Markers (spawn targets for show3d)
    for mname, pos in [("marker_eileen", (-1.6, 1.2, 0)), ("marker_sylvie", (1.6, 1.2, 0)),
                       ("marker_center", (0, 0.5, 0)), ("marker_left", (-2.5, 0.8, 0)),
                       ("marker_right", (2.5, 0.8, 0))]:
        e = _empty(mname, pos, "ARROWS", 0.5)
        stage_col.objects.link(e)

    # Camera presets (lerp targets) — HQ: more presets
    for pname, pos, rot in [("preset_closeup_eileen", (-1.6, -1.5, 1.4), (1.1, 0, 0)),
                            ("preset_closeup_sylvie", (1.6, -1.5, 1.4), (1.1, 0, 0)),
                            ("preset_wide", (0, -5, 2.2), (1.05, 0, 0)),
                            ("preset_dramatic", (0, -2, 2.8), (1.2, 0, 0)),
                            ("preset_low", (0, -3, 0.5), (0.9, 0, 0))]:
        pe = _empty(pname, pos, "SPHERE", 0.3, rot=rot)
        stage_col.objects.link(pe)

    # Desks: 4 + 4 students + 1 teacher + 2 extra for HQ
    desk_positions = [(-2.2, 0.2, 0.25), (-0.7, 0.2, 0.25), (0.8, 0.2, 0.25), (2.3, 0.2, 0.25),
                      (-2.2, -0.4, 0.25), (-0.7, -0.4, 0.25), (0.8, -0.4, 0.25), (2.3, -0.4, 0.25),
                      (-1.4, 0.9, 0.35), (-3.5, 0.8, 0.25), (3.5, 0.8, 0.25)]
    for i, pos in enumerate(desk_positions):
        d = _cube(f"Desk_{i:02d}", (0.9, 0.55, 0.5) if i < 8 else (1.1, 0.6, 0.6), pos,
                  wood if i < 8 else wood_dark)
        stage_col.objects.link(d)

    # Chairs — HQ addition
    chair_mat = _mat_hq("MatChair", (0.3, 0.3, 0.32, 1.0), hq_type="floor")
    for i, pos in enumerate([(-2.2, -0.1, 0.2), (-0.7, -0.1, 0.2), (0.8, -0.1, 0.2), (2.3, -0.1, 0.2)]):
        c = _cube(f"Chair_{i:02d}", (0.4, 0.4, 0.45), pos, chair_mat)
        stage_col.objects.link(c)

    # Blackboard — HQ larger
    board = _plane("Blackboard", 4.5, (0, 2.45, 1.4), rot=(1.5708, 0, 0), mat=green,
                   collection=stage_col)
    board.scale = (1.6 * 4.5 / 2, 1.1 * 4.5 / 2, 1)

    # Blackboard frame — HQ
    frame_mat = _mat_hq("MatBoardFrame", (0.4, 0.3, 0.2, 1.0), hq_type="wood")
    for side, spos, sscale in [("top", (0, 2.44, 2.0), (1.7*4.5/2, 0.05, 0.05)),
                               ("bottom", (0, 2.44, 0.8), (1.7*4.5/2, 0.05, 0.05)),
                               ("left", (-1.7*4.5/2, 2.44, 1.4), (0.05, 0.05, 1.1*4.5/2)),
                               ("right", (1.7*4.5/2, 2.44, 1.4), (0.05, 0.05, 1.1*4.5/2))]:
        f = _cube(f"BoardFrame_{side}", sscale, spos, frame_mat)
        stage_col.objects.link(f)

    # Placeholder capsule characters — HQ taller, better colors
    _cylinder("Char_Eileen_placeholder", 0.28, 1.5, (-1.6, 1.2, 0.95), eileen_c, stage_col)
    _cylinder("Char_Sylvie_placeholder", 0.28, 1.5, (1.6, 1.2, 0.95), sylvie_c, stage_col)

    # ---- save ----
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_path))
    size_kb = out_path.stat().st_size // 1024
    bricks = ctrl.get("upvn_bricks", "no")
    n_ctrl = len(ctrl.game.controllers) if hasattr(ctrl, "game") else 0
    n_sens = len(ctrl.game.sensors) if hasattr(ctrl, "game") else 0
    print(f"[make_template] Saved {out_path} ({size_kb}KB) — VNController bricks: "
          f"{n_ctrl} controller, {n_sens} sensors, "
          f"script_path={ctrl.get('script_path')}, upvn_root={ctrl.get('upvn_root')}")
    if n_ctrl == 0:
        print("[make_template] NOTE: no logic bricks in --background mode (bpy.ops.logic "
              "needs the UPBGE UI). Open the .blend in UPBGE, enable the UPVN add-on and "
              "press 'Setup Scene' once — it adds the Always→Python brick and saves.")
    # interactive runs (xvfb/UI): quit so the calling shell can proceed
    if not getattr(bpy.app, "background", True):
        try:
            bpy.ops.wm.quit_blender()
        except Exception:
            pass
    return out_path


if __name__ == "__main__":
    args = [a for a in sys.argv if not a.startswith("-") and a != "python" and a != "blender"]
    out = Path(args[-1]) if args and args[-1].endswith(".blend") else None
    main(out)
