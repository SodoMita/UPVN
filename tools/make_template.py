"""
Generate UPVN_Template.blend via bpy (run inside UPBGE/Blender).

Usage:
  ./upbge-0.50-linux-x64/blender --background --python tools/make_template.py
  # or with explicit output:
  ./upbge-0.50-linux-x64/blender --background --python tools/make_template.py -- blend/my.blend

v0.6.15: minimal template — only contract objects (BG, Dialogue, 5 Sprites,
9 choices, 2 cameras, VNController + 5 collections). No classroom desks/
board/cylinders. For 3D characters see docs/3D_CHARACTERS.md and
examples/15_3d_stage (load_stage/show3d + marker_center).

Reuses build_vn_scene() so the .blend contains exactly what "Setup Scene"
creates. Data-API only, reliable --background. Always(pulse) -> Python
launcher brick is added when run inside UPBGE UI; --background notes it.
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


# ---------------------------------------------------------------- small data-API helpers
def _mat(name: str, color=(0.5, 0.5, 0.5, 1.0), roughness=0.8):
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
    except Exception:
        pass
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
    # remove factory objects (Cube/Light/Camera) that are not part of contract
    # -- the old unlink-only left them as orphans and they appeared as "random shapes"
    for ob in list(bpy.data.objects):
        if ob.name in ("Cube", "Light", "Camera") or ob.name.startswith("Light.") or ob.name.startswith("Cube."):
            try:
                bpy.data.objects.remove(ob, do_unlink=True)
            except Exception:
                pass
        elif ob.type == "LIGHT":
            # Lights are not part of contract; remove any stray
            try:
                bpy.data.objects.remove(ob, do_unlink=True)
            except Exception:
                pass
    # ensure scene collection is empty before build_vn_scene repopulates it
    for ob in list(scene.collection.objects):
        try:
            scene.collection.objects.unlink(ob)
        except Exception:
            pass
    try:
        bpy.context.window.scene = scene
    except Exception:
        pass
    bpy.data.orphans_purge()

    # ---- core UPVN wiring (same code as the add-on's Setup Scene) ----
    from blend.upvn_editor_addon import build_vn_scene  # engine discovery runs at import
    ctrl = build_vn_scene(bpy, scene_name="VN_Main",
                          script_path="//game/script.rpy")

    # ---- minimal 3D stage — single marker for show3d, no random geometry ----
    # The VN stage is empty by default; add your own 3D characters via
    #   stage MyStage = "stages/my.blend"
    #   load_stage MyStage
    #   show3d MyCharacter at marker_center with fade
    #   anim MyCharacter "ActionName" loop
    # See docs/3D_CHARACTERS.md and examples/15_3d_stage.
    try:
        stage_col = bpy.data.collections.get("VN_3DStage")
        if stage_col is None:
            stage_col = bpy.data.collections.new("VN_3DStage")
            scene.collection.children.link(stage_col)
        # keep VN_3DStage tidy: remove any leftover classroom objects if present
        for ob in list(stage_col.objects):
            if ob.name.startswith(("Desk_", "Floor_", "Blackboard", "Char_", "marker_", "preset_")):
                try:
                    stage_col.objects.unlink(ob)
                except Exception:
                    pass
        # ensure one canonical marker for show3d
        if "marker_center" not in stage_col.objects and "marker_center" not in bpy.data.objects:
            try:
                m = bpy.data.objects.new("marker_center", None)
                m.empty_display_type = 'ARROWS'
                m.empty_display_size = 0.5
                m.location = (0, 0.5, 0)
                stage_col.objects.link(m)
            except Exception:
                pass
    except Exception as e:
        print(f"[make_template] minimal 3D stage setup note: {e}")

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
