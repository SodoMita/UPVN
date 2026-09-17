#!/usr/bin/env python3
"""Build a 3-plane alpha probe blend so the *player* can tell us which
material mode UPBGE actually renders: OPAQUE / BLEND / CLIP.

  blender --background --python tools/make_alpha_probe.py -- <sprite.png>
  -> /tmp/alpha_probe.blend   (run it in blenderplayer, shoot with grim)

Three copies of the same PNG sit on a bright blue world background at
x = -6 / 0 / +6; a screenshot shows which mode keeps the transparency
instead of drawing an opaque quad (or nothing at all).
"""
img = sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_EEVEE'
sc.world = bpy.data.worlds.new("W"); sc.world.use_nodes = True
bg = sc.world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.05, 0.35, 0.75, 1.0)  # bright blue: transparency is obvious
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 18.0
cam.location = (0, -10, 0); cam.rotation_euler = (math.pi/2, 0, 0)
sc.collection.objects.link(cam); sc.camera = cam
bpy.data.objects.new("L", bpy.data.lights.new("L", 'SUN'))
modes = [("OPAQUE", False), ("BLEND", True), ("CLIP", True)]
for i, (mode, use_alpha) in enumerate(modes):
    bpy.ops.mesh.primitive_plane_add(size=5.0, location=((i-1)*6.0, 0.0, 0.0))
    ob = bpy.context.active_object
    ob.rotation_euler = (math.pi/2, 0, 0)
    ob.name = f"probe_{mode}"
    mat = bpy.data.materials.new(f"probe_{mode}")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(img)
    pr = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(tex.outputs["Color"], pr.inputs["Base Color"])
    nt.links.new(tex.outputs["Color"], pr.inputs["Emission Color"])
    pr.inputs["Emission Strength"].default_value = 1.0
    if use_alpha:
        nt.links.new(tex.outputs["Alpha"], pr.inputs["Alpha"])
    nt.links.new(pr.outputs["BSDF"], out.inputs["Surface"])
    mat.blend_method = mode
    try:
        mat.alpha_threshold = 0.5
        mat.shadow_method = 'NONE'
    except Exception:
        pass
    ob.data.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath="/tmp/alpha_probe.blend")
print("PROBE BLEND OK")
