"""Update blend/UPVN_Template.blend in place — M26 texture-free materials.

Runs offline (blender --background): rewrites the five VN materials to the
Object Info -> Emission graph so runtime palette code paints everything via
KX_GameObject.color, seeds each object's default tint, and writes the
image_mode policy property. Logic bricks and existing game properties are
left untouched (make_template cannot rebuild them headless).

Usage:
  blender --background blend/UPVN_Template.blend --python tools/update_template_materials.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import bpy  # noqa: E402

# material name -> fallback color (used when an object never sets a tint)
MATERIALS = {
    "MABackground": (0.12, 0.14, 0.22, 1.0),
    "MASprite": (0.62, 0.78, 0.55, 1.0),
    "MAUI": (0.05, 0.06, 0.14, 1.0),
    "MAChoice": (0.12, 0.18, 0.32, 1.0),
    "MAFont": (0.92, 0.93, 1.0, 1.0),
}

# object name -> default object tint (what the rasterizer multiplies in)
OBJECT_TINTS = {
    "BG_Plane": (0.12, 0.14, 0.22, 1.0),
    "Dialogue_Box": (0.05, 0.06, 0.14, 1.0),
}


def rewrite_unlit(mat, color):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    objinfo = nt.nodes.new("ShaderNodeObjectInfo")
    em.inputs["Color"].default_value = color
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(objinfo.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs[0])
    for attr, val in (("blend_method", "OPAQUE"), ("shadow_method", "NONE"),
                      ("use_backface_culling", False)):
        try:
            setattr(mat, attr, val)
        except Exception:
            pass


def set_runtime_prop(obj, name, value):
    """Mirror the add-on's dual representation (custom + game property)."""
    obj[name] = value
    props = getattr(obj, "game", None)
    props = getattr(props, "properties", None) if props is not None else None
    if props is None:
        return
    p = props.get(name)
    if p is None:
        try:
            with bpy.context.temp_override(active_object=obj, object=obj,
                                           selected_objects=[obj],
                                           selected_editable_objects=[obj]):
                bpy.ops.object.game_property_new()
        except Exception as e:
            print(f"[update_template] game_property_new failed for {name}: {e}")
            return
        p = props[-1]
        p.name = name
        p = props.get(name) or p
    if p.type != "STRING":
        p.type = "STRING"
        p = props.get(name) or p
    try:
        p.value = value
    except Exception as e:
        print(f"[update_template] value failed for {name}: {e}")


def fix_physics():
    """SENSOR objects are not ray-detectable in UPBGE 0.50 — STATIC + BOX."""
    n = 0
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        if ob.name.startswith(("choice_", "Sprite_", "BG_", "Dialogue_")) and \
                not ob.name.endswith("_text"):
            try:
                ob.game.physics_type = "STATIC"
                ob.game.use_collision_bounds = True
                ob.game.collision_bounds_type = "BOX"
                n += 1
            except Exception:
                pass
    print(f"[update_template] STATIC physics on {n} ray targets")


def main():
    fix_physics()
    for name, color in MATERIALS.items():
        mat = bpy.data.materials.get(name)
        if mat is None:
            mat = bpy.data.materials.new(name)
        rewrite_unlit(mat, color)
        print(f"[update_template] material rewritten: {name}")

    tinted = 0
    for ob in bpy.data.objects:
        color = OBJECT_TINTS.get(ob.name)
        if color is None:
            if ob.name.startswith("Sprite_"):
                color = (0.62, 0.78, 0.55, 1.0)
            elif ob.name.startswith("choice_") and not ob.name.endswith("_text"):
                color = (0.12, 0.18, 0.32, 1.0)
            elif ob.type == "FONT":
                color = (0.92, 0.93, 1.0, 1.0)
        if color:
            try:
                ob.color = color
                tinted += 1
            except Exception:
                pass
    print(f"[update_template] object tints set: {tinted}")

    ctrl = bpy.data.objects.get("VNController")
    if ctrl is not None:
        set_runtime_prop(ctrl, "image_mode", "color")
        print("[update_template] image_mode=color written to VNController")

    bpy.ops.wm.save_mainfile()
    print("[update_template] saved")


main()
