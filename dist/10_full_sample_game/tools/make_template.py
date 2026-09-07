"""
Generate UPVN_Template.blend via bpy (run inside UPBGE/Blender).

Usage:
  ./upbge-0.50-linux-x64/blender --background --python tools/make_template.py

Creates VN_Main scene with cameras, planes, VNController empty.
LLM can extend this to build UI in 3D as requested.
"""
try:
    import bpy

    # Create scene
    scene = bpy.data.scenes.new("VN_Main")
    bpy.context.window.scene = scene

    # Ortho UI camera
    cam_ui_data = bpy.data.cameras.new("Camera_UI")
    cam_ui_data.type = 'ORTHO'
    cam_ui_data.ortho_scale = 10
    cam_ui = bpy.data.objects.new("Camera_UI", cam_ui_data)
    cam_ui.location = (0, -10, 5)
    cam_ui.rotation_euler = (1.5708, 0, 0)
    scene.collection.objects.link(cam_ui)

    # 3D camera
    cam3d_data = bpy.data.cameras.new("Camera_3D")
    cam3d = bpy.data.objects.new("Camera_3D", cam3d_data)
    cam3d.location = (0, -6, 2)
    scene.collection.objects.link(cam3d)
    scene.camera = cam_ui

    # VNController empty
    ctrl = bpy.data.objects.new("VNController", None)
    ctrl.empty_display_type = 'CUBE'
    # Add python logic: Always -> Python (bge_frontend.frontend.main)
    # Note: Logic is added via game properties + python component in UPBGE 0.5+
    # For brevity we just add a custom property for script path
    ctrl["script_path"] = "//game/script.rpy"
    scene.collection.objects.link(ctrl)

    # Create collections
    for name in ["VN_Backgrounds", "VN_Characters", "VN_UI", "VN_Effects", "VN_3DStage"]:
        col = bpy.data.collections.new(name)
        scene.collection.children.link(col)

    # BG plane
    bpy.ops.mesh.primitive_plane_add(size=10, location=(0,0,0))
    bg = bpy.context.active_object
    bg.name = "BG_Plane"
    # move to backgrounds collection
    scene.collection.objects.unlink(bg)
    bpy.data.collections["VN_Backgrounds"].objects.link(bg)

    # Dialogue box plane (UI in 3D)
    bpy.ops.mesh.primitive_plane_add(size=8, location=(0,0,1))
    dlg = bpy.context.active_object
    dlg.name = "Dialogue_Box"
    dlg.scale = (1, 0.3, 1)
    scene.collection.objects.unlink(dlg)
    bpy.data.collections["VN_UI"].objects.link(dlg)

    # Save
    bpy.ops.wm.save_as_mainfile(filepath="blend/UPVN_Template.blend")
    print("Saved blend/UPVN_Template.blend")
except Exception as e:
    print("This script must be run inside Blender/UPBGE with bpy:", e)
    print("For headless CI you can just verify the headless engine; blend generation is manual.")
