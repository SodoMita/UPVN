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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import bpy  # noqa: E402

from engine.render import scene_settings as ss

IMAGE_EXTS = ss.IMAGE_EXTS


def _slug(name: str) -> str:
    stem = Path(name).stem.strip().lower()
    out = []
    for ch in stem:
        out.append(ch if (ch.isalnum() or ch in "-_") else "_")
    return "".join(out)


def _plane(name, size=10.0):
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(list(ss.UNIT_QUAD_VERTS), [], list(ss.UNIT_QUAD_FACES))
    mesh.update()
    # The rasterizer samples TexImage through UVs — from_pydata creates no UV
    # layer and the texture then renders black in the player.
    try:
        uv = mesh.uv_layers.new(name=ss.UV_LAYER_NAME)
        for i, (u, v) in enumerate(ss.UNIT_QUAD_UVS):
            uv.data[i].uv = (u, v)
    except Exception as e:
        print(f"[wire] uv layer failed on {name}: {e}")
    ob = bpy.data.objects.new(name, mesh)
    ob.scale = (size / 2, size / 2, 1)
    ob.rotation_euler = ss.PLANE_ROTATION
    return ob


def _image_material(name, img_path, alpha: bool = False):
    """Unlit image material for the converted image bank.

    Every variant here is measured in the **player**, not guessed:

    * Principled(Base Color + Emission) — renders correctly in UPBGE 0.53
      (frame mean luminance 0.34).
    * Emission-only — the historical graph: fine in Blender, but the player
      draws it nearly black (measured 0.075-0.18). Do not go back.
    * `alpha=True` (character sprites) also wires the PNG's Alpha into the
      surface with `blend_method = "CLIP"`. Measured with
      tools/make_alpha_probe.py: OPAQUE = opaque quad around the character,
      BLEND = the plane washes into the background, CLIP = sharp and correct.
      Backgrounds stay OPAQUE.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(str(img_path))
    try:
        img.pack()   # self-contained blend — survives moves between machines
    except Exception:
        pass
    tex.image = img
    pr = nt.nodes.new("ShaderNodeBsdfPrincipled")
    try:
        nt.links.new(tex.outputs["Color"], pr.inputs["Base Color"])
    except Exception:
        pass
    for cname in ("Emission Color", "Emission Colour"):
        if cname in pr.inputs:
            try:
                nt.links.new(tex.outputs["Color"], pr.inputs[cname])
            except Exception:
                pass
            break
    if "Emission Strength" in pr.inputs:
        pr.inputs["Emission Strength"].default_value = 1.0
    if alpha:
        try:
            nt.links.new(tex.outputs["Alpha"], pr.inputs["Alpha"])
        except Exception:
            pass
    nt.links.new(pr.outputs["BSDF"], out.inputs["Surface"])
    try:
        mat.blend_method = ss.MAT_BLEND_CLIP if alpha else ss.MAT_BLEND_OPAQUE
        mat.alpha_threshold = ss.MAT_ALPHA_THRESHOLD
        mat.shadow_method = ss.MAT_SHADOW_METHOD
        mat.use_backface_culling = ss.MAT_USE_BACKFACE_CULLING
    except Exception:
        pass
    return mat


BACKGROUND_LAYER = ss.BACKGROUND_LAYER   # backdrop depth — edit scene_settings.py


def img_w_h(path):
    """Image pixel size without Pillow (bpy already knows how)."""
    try:
        import bpy
        im = bpy.data.images.load(str(path))
        return float(im.size[0]), float(im.size[1])
    except Exception:
        return 0.0, 0.0


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
        set_runtime_prop(ctrl, "script_path", ss.CONVERTED_SCRIPT_PATH)
        set_runtime_prop(ctrl, "image_mode", ss.CONVERTED_IMAGE_MODE)
        # A converted project IS Ren'Py source, so it needs the full parse tier
        # (extend / init / screen). Without this the runtime parses it with the
        # declarative subset and refuses to start.
        set_runtime_prop(ctrl, "parse_mode", ss.CONVERTED_PARSE_MODE)
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
            ob = _plane(name, size=ss.IMAGE_BANK_BG_SIZE)
            # BACKGROUND_LAYER: the backdrop sits 10 units BEHIND the stage
            # (camera at y=-10, stage/sprites around y=-1..0), so 3D characters
            # and camera moves have room instead of clipping into the backdrop.
            # Ortho projection makes distance irrelevant to apparent size, and
            # SceneManager._fit_bg_to_view() re-covers the frame at runtime.
            ob.location = (0.0, float(BACKGROUND_LAYER), 0.0)
            ss.apply_mesh_physics(ob, is_text=False)
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
            ob.data.materials.append(_image_material(name + "_mat", f, alpha=True))
            ss.apply_mesh_physics(ob, is_text=False)
            scene.collection.objects.link(ob)
            n_sp += 1
    print(f"[wire] image bank: {n_bg} backgrounds, {n_sp} sprites")

    bpy.ops.wm.save_mainfile()
    print("UPVN_WIRE_OK")


main()
