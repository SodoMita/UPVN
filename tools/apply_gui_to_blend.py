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
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import bpy

from engine.render import scene_settings as ss

ORTHO = ss.CAMERA_UI_ORTHO_SCALE


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
    # Ren'Py outputs raw sRGB; Blender's default AgX view transform desaturates
    # and dims emission (white text -> 197, green name -> gray-green).
    # Standard view transform restores 1:1 color parity.
    try:
        scene.view_settings.view_transform = ss.VIEW_TRANSFORM
        scene.view_settings.look = ss.VIEW_LOOK
        scene.view_settings.exposure = ss.VIEW_EXPOSURE
        scene.view_settings.gamma = ss.VIEW_GAMMA
    except Exception as e:
        print(f"[apply_gui] view transform failed: {e}")
    w = float(scene.render.resolution_x or ss.RENDER_RESOLUTION_X)
    h = float(scene.render.resolution_y or ss.RENDER_RESOLUTION_Y)
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
    col = colors.get("dialogue_box") or "#000000cc"
    if col in ("#ffffff", "#ffffffff"):
        # unsampled stock gui: gui/textbox.png is flat black 80%
        # (pixel-sampled from the Ren'Py tutorial, M29 loop)
        col = "#000000cc"
    hx = col.lstrip("#")
    rgba = [int(hx[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    alpha = int(hx[6:8], 16) / 255.0 if len(hx) >= 8 else 0.8
    box = bpy.data.objects.get("Dialogue_Box")
    if box is not None and box.material_slots:
        mat = box.material_slots[0].material
        mat.use_nodes = True
        nt = mat.node_tree
        # Mode knob (UPVN_BOX_MODE): blend | dither | opaque.
        # llvmpipe/EEVEE-Next renders the Transparent BSDF white here, so the
        # default premultiplies the sampled tint over a dark scene estimate
        # (stock tutorial textbox = flat #000000cc; over water it reads
        # near-black) — visually matches the original without alpha blending.
        mode = os.environ.get("UPVN_BOX_MODE", "opaque")
        if mode == "opaque":
            bg_est = (0.02, 0.04, 0.07)
            rgba = [c * alpha + b * (1.0 - alpha)
                    for c, b in zip(rgba[:3], bg_est)]
        if nt is not None:
            nt.nodes.clear()
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            if mode == "opaque":
                em = nt.nodes.new("ShaderNodeEmission")
                em.inputs["Color"].default_value = (*rgba[:3], 1.0)
                em.inputs["Strength"].default_value = 1.0
                nt.links.new(em.outputs[0], out.inputs["Surface"])
            else:
                # Emission + Transparent mixed by the sampled alpha
                em = nt.nodes.new("ShaderNodeEmission")
                em.inputs["Color"].default_value = (*rgba[:3], 1.0)
                em.inputs["Strength"].default_value = 1.0
                tr = nt.nodes.new("ShaderNodeBsdfTransparent")
                mix = nt.nodes.new("ShaderNodeMixShader")
                mix.inputs["Fac"].default_value = alpha
                nt.links.new(tr.outputs[0], mix.inputs[1])
                nt.links.new(em.outputs[0], mix.inputs[2])
                nt.links.new(mix.outputs[0], out.inputs["Surface"])
                try:
                    mat.surface_render_method = ("BLENDED" if mode == "blend"
                                                 else "DITHERED")
                except Exception as e:
                    print(f"[apply_gui] surface_render_method failed: {e}")
            try:
                mat.use_backface_culling = False
            except Exception:
                pass

    # 3b) text objects: single-user emission materials multiplied by the
    # object color so runtime _set_font_color tints show (EEVEE-Next ignores
    # obj.color on plain emission — M29 residual name-tint gap).
    for tname in ("Speaker_Text", "Dialogue_Text"):
        ob = bpy.data.objects.get(tname)
        if ob is None or ob.type != "FONT" or not ob.data.materials:
            continue
        m = ob.data.materials[0].copy()
        m.name = f"MAFont_{tname}"
        m.use_nodes = True
        nt = m.node_tree
        if nt is not None:
            nt.nodes.clear()
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            em = nt.nodes.new("ShaderNodeEmission")
            em.inputs["Strength"].default_value = 1.0
            oi = nt.nodes.new("ShaderNodeObjectInfo")
            mx = nt.nodes.new("ShaderNodeMixRGB")
            mx.blend_type = "MULTIPLY"
            mx.inputs["Fac"].default_value = 1.0
            mx.inputs["Color1"].default_value = (1.0, 1.0, 1.0, 1.0)
            nt.links.new(oi.outputs["Color"], mx.inputs["Color2"])
            nt.links.new(mx.outputs["Color"], em.inputs["Color"])
            nt.links.new(em.outputs[0], out.inputs["Surface"])
        ob.data.materials.clear()
        ob.data.materials.append(m)

    # 3) text sizes px -> world units
    world_h = ORTHO * h / w
    px2wu = world_h / h
    for name, key in (("Speaker_Text", "name"), ("Dialogue_Text", "text")):
        px = sizes.get(key)
        ob = bpy.data.objects.get(name)
        if px and ob is not None and ob.type == "FONT":
            ob.data.size = float(px) * px2wu

    # 4) sprite planes at native full-screen height like Ren'Py's default
    # display (tutorial beat: head near top edge, feet cropped at bottom).
    # Width follows the bound texture aspect; z stays owned by Pos_* empties.
    n_sp = 0
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        is_pool = ob.name == "Sprite_pool"
        is_bank = ob.name.startswith(("SPRIMG_", "Sprite_img_"))
        if not (is_pool or is_bank):
            continue
        img = None
        for slot in ob.material_slots:
            m = slot.material
            if m is not None and m.use_nodes:
                for n in m.node_tree.nodes:
                    if n.type == "TEX_IMAGE" and n.image:
                        img = n.image
                        break
            if img is not None:
                break
        if img is None and is_bank:
            stem = (ob.name[len("SPRIMG_"):]
                    if ob.name.startswith("SPRIMG_")
                    else ob.name[len("Sprite_img_"):])
            for im in bpy.data.images:
                fp = (im.filepath or "").replace("\\", "/")
                if im.name.startswith(stem) or (stem and stem in fp):
                    img = im
                    break
        if img is not None and img.size[0]:
            iw, ih = float(img.size[0]), float(img.size[1])
        elif is_pool:
            iw, ih = 3.0, 4.0   # starter aspect for the pool template
        else:
            continue
        hgt = world_h * 1.02
        wid = hgt * iw / ih
        try:
            ob.dimensions = (wid, hgt, 0.0)
            n_sp += 1
        except Exception as e:
            print(f"[apply_gui] sprite dims failed for {ob.name}: {e}")

    # 5) FONT objects: swap missing packed font paths for the project's or
    # the system DejaVu (tofu glyphs in player frames came from //fonts/
    # paths absent in converted snapshots)
    import os as _os
    bdir = _os.path.dirname(bpy.data.filepath)
    proj = _os.path.dirname(bdir)
    cand = [_os.path.join(proj, "game", "fonts", "DejaVuSans.ttf"),
            _os.path.join(proj, "assets", "fonts", "DejaVuSans.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    fpath = next((p for p in cand if _os.path.isfile(p)), None)
    n_font = 0
    if fpath:
        for ob in bpy.data.objects:
            if ob.type != "FONT":
                continue
            cur = ob.data.font
            cp = bpy.path.abspath(cur.filepath) if cur.filepath else ""
            if cp and _os.path.isfile(cp):
                continue
            try:
                ob.data.font = bpy.data.fonts.load(fpath, check_existing=True)
                n_font += 1
            except Exception as e:
                print(f"[apply_gui] font swap failed on {ob.name}: {e}")

    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    print(f"[apply_gui] OK bgs={n_bg} box={col} alpha={alpha:.2f} "
          f"name_px={sizes.get('name')} text_px={sizes.get('text')} sp={n_sp} "
          f"fonts={n_font}")


main()
