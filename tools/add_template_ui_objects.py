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


_CHANGES: list[str] = []


def _note(tag, name):
    _CHANGES.append(f"{tag}:{name}")


def _tint(ob, color):
    """Seed the object color the M26 material graph multiplies into emission
    (Object Info -> Color) — same helper blend/upvn_editor_addon.py uses. The
    player reads this, not the material base color, so a panel without it draws
    template-white and swallows the white text on top of it."""
    try:
        cur = tuple(round(float(c), 3) for c in ob.color)
    except Exception:
        return ob
    want = tuple(round(float(c), 3) for c in color)
    if cur != want:
        try:
            ob.color = color
            _note("retinted", ob.name)
        except Exception:
            pass
    return ob


def _unit_quad(mesh):
    """The VN-plane convention: a 2x2 quad (verts +/-1) in local XY.

    engine/ui/world_ui.py::layout_screen_ui writes worldScale as the HALF
    extent, because every shipped plane (BG_Plane, Dialogue_Box, choice_N) is
    +/-1. A +/-0.5 mesh therefore renders at exactly half size — measured in
    the player: the backlog panel came out 7 units wide instead of 14 and its
    text landed outside it, which read as "the history box is empty".
    """
    try:
        # from_pydata only appends: on a mesh that already has geometry (the
        # repair path) it must be emptied first, else foreach_set raises
        # "internal error setting the array"
        mesh.clear_geometry()
    except Exception:
        pass
    mesh.from_pydata([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)],
                     [], [(0, 1, 2, 3)])
    mesh.update()
    if not mesh.uv_layers:            # TexImage nodes sample through UVs
        try:
            uv = mesh.uv_layers.new(name="UVMap")
            for i, (u, v) in enumerate(((0.0, 0.0), (1.0, 0.0),
                                         (1.0, 1.0), (0.0, 1.0))):
                uv.data[i].uv = (u, v)
        except Exception:
            pass


def _is_unit_quad(ob):
    try:
        vs = ob.data.vertices
        if len(vs) != 4:
            return False
        return all(abs(abs(v.co.x) - 1.0) < 1e-4 and abs(abs(v.co.y) - 1.0) < 1e-4
                   for v in vs)
    except Exception:
        return False


def ensure_plane(scene, name, color):
    import bpy
    ob = bpy.data.objects.get(name)
    created = ob is None
    if created:
        mesh = bpy.data.meshes.new(name + "_mesh")
        _unit_quad(mesh)
        ob = bpy.data.objects.new(name, mesh)
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
    elif not _is_unit_quad(ob):
        # repair a plane authored at the wrong local size (idempotent fix)
        _unit_quad(ob.data)
        _note("mesh", name)
    if created:
        _note("added", name)
    mat = bpy.data.materials.get(UI_MATERIAL) or bpy.data.materials.get("MABackground")
    if mat is not None and not ob.data.materials:
        ob.data.materials.append(mat)
    _tint(ob, color)
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
    # Always run the helpers, even when the objects exist: half the point of
    # this tool is repairing templates authored by an earlier version (wrong
    # mesh size, missing tint) — both are invisible failures in the player.
    ensure_plane(scene, HISTORY_PLANE, (0.03, 0.04, 0.09, 1.0))
    for name, loc, em in ((HISTORY_TEXT, (-6.0, -0.5, 3.4), 0.20),
                          (REWIND_TEXT, (-6.0, -0.5, 4.4), 0.17)):
        ob = ensure_font(scene, name, loc, em)
        _tint(ob, (0.92, 0.93, 1.0, 1.0))
    if _CHANGES:
        print("UPVN_UI_OBJECTS_CHANGED " + ",".join(_CHANGES))
    else:
        print("UPVN_UI_OBJECTS_CLEAN nothing to write")
    if save_to:
        if _CHANGES:
            bpy.ops.wm.save_as_mainfile(filepath=save_to)
            print("UPVN_UI_OBJECTS_SAVED " + save_to)
        else:
            print("UPVN_UI_OBJECTS_SKIPPED_SAVE no changes")


main()
