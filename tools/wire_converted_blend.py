"""Wire a converted UPVN blend: script_path, image_mode and the image bank.

Called by tools/renpy_convert.py with the UPBGE/Blender binary:
    blender --background <blend> --python tools/wire_converted_blend.py -- <assets_dir>

bge.texture cannot bind textures to node-based materials in UPBGE 0.50
("Texture is not available", measured in-field), so converted games get their
art via an IMAGE BANK instead: one plane per asset, textures assigned in the
editor (plain TexImage → Emission, which rasterizes fine), all hidden. The
runtime (scene_manager/sprite_renderer, image_mode=auto) shows the matching
`BGIMG_<stem>` / `SPRIMG_<stem>` plane; anything missing falls back to the
palette on BG_Plane / Sprite_*.
"""
import sys
from pathlib import Path

import bpy  # noqa: E402

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def _slug(name: str) -> str:
    stem = Path(name).stem.strip().lower()
    out = []
    for ch in stem:
        out.append(ch if (ch.isalnum() or ch in "-_") else "_")
    return "".join(out)


def _plane(name, size=10.0):
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], [],
                     [(0, 1, 2, 3)])
    mesh.update()
    # The rasterizer samples TexImage through UVs — from_pydata creates no UV
    # layer and the texture then renders black in the player.
    try:
        uv = mesh.uv_layers.new(name="UVMap")
        uvs = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
        for i, (u, v) in enumerate(uvs):
            uv.data[i].uv = (u, v)
    except Exception as e:
        print(f"[wire] uv layer failed on {name}: {e}")
    ob = bpy.data.objects.new(name, mesh)
    ob.scale = (size / 2, size / 2, 1)
    ob.rotation_euler = (1.5707963267948966, 0.0, 0.0)
    return ob


def _image_material(name, img_path):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tex = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(str(img_path))
    try:
        img.pack()   # self-contained blend — survives moves between machines
    except Exception:
        pass
    tex.image = img
    try:
        em.inputs["Strength"].default_value = 1.0
    except Exception:
        pass
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs[0])
    try:
        mat.blend_method = "OPAQUE"
        mat.shadow_method = "NONE"
        mat.use_backface_culling = False
    except Exception:
        pass
    return mat


def set_runtime_prop(obj, name, value):
    obj[name] = value
    props = getattr(getattr(obj, "game", None), "properties", None)
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
            print(f"[wire] game_property_new failed for {name}: {e}")
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
        print(f"[wire] value failed for {name}: {e}")


def main():
    assets = Path(sys.argv[-1])
    if not assets.is_dir():
        print(f"[wire] assets dir missing: {assets} — wiring props only")

    scene = bpy.context.scene
    ctrl = bpy.data.objects.get("VNController")
    if ctrl is not None:
        set_runtime_prop(ctrl, "script_path", "//../game")
        set_runtime_prop(ctrl, "image_mode", "auto")
        # A converted project IS Ren'Py source, so it needs the full parse tier
        # (extend / init / screen). Without this the runtime parses it with the
        # declarative subset and refuses to start.
        set_runtime_prop(ctrl, "parse_mode", "full")
        print("[wire] script_path=//../game image_mode=auto parse_mode=full")

    # hide the palette fallback planes' default state stays as-is; add banks
    n_bg = n_sp = 0
    bg_dir = assets / "backgrounds"
    sp_dir = assets / "sprites"
    if bg_dir.is_dir():
        prev = None
        for f in sorted(bg_dir.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in IMAGE_EXTS:
                continue
            name = f"BGIMG_{_slug(f.name)}"
            if bpy.data.objects.get(name):
                continue
            ob = _plane(name, size=10.0)
            ob.location = (0.0, 0.0, 0.0)
            ob.data.materials.append(_image_material(name + "_mat", f))
            ob.game.physics_type = "STATIC"
            ob.hide_render = False
            scene.collection.objects.link(ob)
            n_bg += 1
            prev = ob
        # first bank plane visible initially (engine re-syncs on 'scene')
    if sp_dir.is_dir():
        for f in sorted(sp_dir.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in IMAGE_EXTS:
                continue
            name = f"Sprite_img_{_slug(f.name)}"
            if bpy.data.objects.get(name):
                continue
            ob = _plane(name, size=4.0)
            ob.scale = (1.5, 2.4, 1.0)
            ob.location = (0.0, -0.15, 0.0)
            ob.data.materials.append(_image_material(name + "_mat", f))
            ob.game.physics_type = "STATIC"
            scene.collection.objects.link(ob)
            n_sp += 1
    print(f"[wire] image bank: {n_bg} backgrounds, {n_sp} sprites")

    bpy.ops.wm.save_mainfile()
    print("UPVN_WIRE_OK")


main()
