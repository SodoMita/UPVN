#!/usr/bin/env python3
"""Add the backlog/rewind UI objects to a UPVN .blend (idempotent, headless).

M26d: `H` and the « rewind marker are drawn by engine/ui/world_ui.py onto three
named objects (History_Box / History_Text / Rewind_Text). Templates authored
before M26d do not have them, so the overlay opened into thin air — headless
traces had a backlog, the player never showed one.

Run it from the UPBGE/Blender binary (bpy is only available there):

    /opt/upbge/upbge-0.50-linux-x64/blender --background \\
        blend/UPVN_Template.blend --python tools/add_template_ui_objects.py -- \\
        [--save blend/UPVN_Template.blend]

The object recipe mirrors blend/upvn_editor_addon.py::build_vn_scene so
"Setup Scene" in the editor and this tool converge on the same scene contract.
Existing objects are reused, never duplicated; nothing else is touched (running
the whole Setup Scene headless is not supported — its logic-brick operators need
the UI context).
"""
import sys

HISTORY_PLANE = "History_Box"
HISTORY_TEXT = "History_Text"
REWIND_TEXT = "Rewind_Text"
PLANE_ROT = (1.5707963267948966, 0.0, 0.0)
UI_MATERIAL = "MAUI"


def _args():
    argv = sys.argv
    tail = argv[argv.index("--") + 1:] if "--" in argv else []
    save_to = None
    if "--save" in tail:
        i = tail.index("--save")
        save_to = tail[i + 1] if i + 1 < len(tail) else None
    return save_to


def ensure_plane(scene, name, color):
    import bpy
    ob = bpy.data.objects.get(name)
    if ob is None:
        mesh = bpy.data.meshes.new(name)
        ob = bpy.data.objects.new(name, mesh)
        # a 1x1 quad in XY; the engine scales/positions it every tick
        verts = [(-0.5, -0.5, 0.0), (0.5, -0.5, 0.0), (0.5, 0.5, 0.0), (-0.5, 0.5, 0.0)]
        mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
        mesh.update()
        try:
            scene.collection.objects.link(ob)
        except Exception:
            pass
        ui_col = bpy.data.collections.get("VN_UI")
        if ui_col is not None:
            try:
                ui_col.objects.link(ob)
            except Exception:
                pass
        ob.location = (0.0, -0.45, 0.9)
        ob.rotation_euler = PLANE_ROT
        ob.scale = (6.6, 3.0, 1.0)
    mat = bpy.data.materials.get(UI_MATERIAL) or bpy.data.materials.get("MABackground")
    if mat is not None and not ob.data.materials:
        ob.data.materials.append(mat)
    try:
        ob["upvn_layout_custom"] = True
    except Exception:
        pass
    _ghost(ob)
    return ob


def _ghost(ob):
    """Static + BOX collision like the other plates (ray-hittable, immovable)."""
    try:
        g = ob.game
        g.physics_type = "STATIC"
        g.use_collision_bounds = True
        g.collision_bounds_type = "BOX"
    except Exception:
        pass


def ensure_font(scene, name, loc, em):
    import bpy
    ob = bpy.data.objects.get(name)
    if ob is None:
        curve = bpy.data.curves.new(name + "_font", "FONT")
        curve.body = ""
        try:
            curve.size = em
            curve.align_x = "LEFT"
            curve.align_y = "TOP"     # backlog text grows down from its origin
        except Exception:
            pass
        ob = bpy.data.objects.new(name, curve)
        try:
            scene.collection.objects.link(ob)
        except Exception:
            pass
        ui_col = bpy.data.collections.get("VN_UI")
        if ui_col is not None:
            try:
                ui_col.objects.link(ob)
            except Exception:
                pass
        ob.location = loc
        ob.rotation_euler = PLANE_ROT
        mat = bpy.data.materials.get("MAFont") or bpy.data.materials.get(UI_MATERIAL)
        if mat is not None and ob.data is not None:
            try:
                ob.data.materials.append(mat)
            except Exception:
                pass
        _ghost(ob)
    return ob


def main():
    import bpy
    save_to = _args()
    scene = bpy.context.scene
    made = []
    if bpy.data.objects.get(HISTORY_PLANE) is None:
        ensure_plane(scene, HISTORY_PLANE, (0.03, 0.04, 0.09, 1.0))
        made.append(HISTORY_PLANE)
    for name, loc, em in ((HISTORY_TEXT, (-6.0, -0.5, 3.4), 0.20),
                          (REWIND_TEXT, (-6.0, -0.5, 4.4), 0.17)):
        if bpy.data.objects.get(name) is None:
            ensure_font(scene, name, loc, em)
            made.append(name)
    print("UPVN_UI_OBJECTS_ADDED " + (",".join(made) if made else "none (already present)"))
    if save_to:
        bpy.ops.wm.save_as_mainfile(filepath=save_to)
        print("UPVN_UI_OBJECTS_SAVED " + save_to)


main()
