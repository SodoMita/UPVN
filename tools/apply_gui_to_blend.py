"""Static parity pass: bake upvn_gui.json visuals into a converted .blend.

Runtime bpy edits (scale/materials) do not reach the UPBGE player's rendered
frame, so converted projects must carry the original's look in the .blend:
  * BGIMG_* bank planes scaled to cover the ortho viewport (Ren'Py fills the
    screen with screen-sized backgrounds),
  * MAUI (Dialogue_Box) emission replaced by Emission+Transparent mix using
    the sampled textbox.png color (stock Ren'Py gui = dark translucent),
  * Speaker/Dialogue text object sizes from gui sizes (px -> world units).

Usage:
  <blender> --background <blend> --python tools/apply_gui_to_blend.py -- \
      <upvn_gui.json>
Idempotent.
"""
import json
import sys

import bpy

ORTHO = 15.0


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    json_path = argv[0] if argv else None
    cfg = {}
    if json_path:
        try:
            cfg = json.load(open(json_path, encoding="utf-8")) or {}
        except Exception as e:
            print(f"[apply_gui] json load failed ({e})")
    colors = cfg.get("colors") or {}
    sizes = cfg.get("sizes") or {}

    # 1) bank backgrounds cover the viewport: 15 x 15*h/w world units
    scene = bpy.context.scene
    w = float(scene.render.resolution_x or 1280)
    h = float(scene.render.resolution_y or 720)
    # vertical overscan + drop: the player's view centre for these banks sits
    # ~1.1 world units above the plane origin (measured on sway, M29), so a
    # bare viewport-height plane leaves a band of world colour at the bottom.
    target = (ORTHO / 2.0, (ORTHO * h / w) * 0.675, 1.0)
    n_bg = 0
    for ob in bpy.data.objects:
        if ob.name.startswith("BGIMG_") and ob.type == "MESH":
            ob.scale = target
            ob.location.z = -1.09
            n_bg += 1

    # 2) textbox tint: Emission+Transparent mixed by sampled alpha
    col = colors.get("dialogue_box") or "#000000a0"
    hx = col.lstrip("#")
    rgba = [int(hx[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    alpha = int(hx[6:8], 16) / 255.0 if len(hx) >= 8 else 0.8
    box = bpy.data.objects.get("Dialogue_Box")
    if box is not None and box.material_slots:
        mat = box.material_slots[0].material
        mat.use_nodes = True
        nt = mat.node_tree
        if nt is not None:
            # rebuild from scratch. Tried, on llvmpipe/EEVEE-Next (M29):
            #   * Principled + Alpha, BLENDED  -> whole frame black
            #   * Principled + Alpha, DITHERED -> whole frame black
            #   * Emission + Transparent Mix   -> box stayed light gray
            # Opaque emission in the sampled tint is the only robust result;
            # stock Ren'Py textbox over a dark scene reads near-black too.
            nt.nodes.clear()
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            em = nt.nodes.new("ShaderNodeEmission")
            em.inputs["Color"].default_value = (*rgba[:3], 1.0)
            em.inputs["Strength"].default_value = 1.0
            nt.links.new(em.outputs[0], out.inputs["Surface"])

    # 3) text sizes px -> world units
    world_h = ORTHO * h / w
    px2wu = world_h / h
    for name, key in (("Speaker_Text", "name"), ("Dialogue_Text", "text")):
        px = sizes.get(key)
        ob = bpy.data.objects.get(name)
        if px and ob is not None and ob.type == "FONT":
            ob.data.size = float(px) * px2wu

    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    print(f"[apply_gui] OK bgs={n_bg} box={col} alpha={alpha:.2f} "
          f"name_px={sizes.get('name')} text_px={sizes.get('text')}")


main()
