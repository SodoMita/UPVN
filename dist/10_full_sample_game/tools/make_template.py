"""
Generate UPVN_Template.blend via bpy (run inside UPBGE/Blender).

Usage:
  ./upbge-0.50-linux-x64/blender --background --python tools/make_template.py

Creates VN_Main scene with cameras, planes, VNController empty, 3D stage markers + desks.
LLM can extend this to build UI in 3D as requested. v0.5 polish: richer classroom_3d stage with markers.
"""
try:
    import bpy

    # Clean existing scenes if any
    bpy.ops.wm.read_factory_settings(use_empty=True)

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
    cam3d.location = (0, -6, 2.5)
    cam3d.rotation_euler = (1.15, 0, 0)
    scene.collection.objects.link(cam3d)
    scene.camera = cam_ui

    # VNController empty
    ctrl = bpy.data.objects.new("VNController", None)
    ctrl.empty_display_type = 'CUBE'
    ctrl["script_path"] = "//game/script.rpy"
    ctrl["upvn_version"] = "0.5.0"
    scene.collection.objects.link(ctrl)

    # Create collections
    for name in ["VN_Backgrounds", "VN_Characters", "VN_UI", "VN_Effects", "VN_3DStage"]:
        col = bpy.data.collections.new(name)
        scene.collection.children.link(col)

    # BG plane
    bpy.ops.mesh.primitive_plane_add(size=10, location=(0,0,0))
    bg = bpy.context.active_object
    bg.name = "BG_Plane"
    # add material MABackground for texture swapping
    mat = bpy.data.materials.new(name="MABackground")
    mat.use_nodes = True
    bg.data.materials.append(mat)
    scene.collection.objects.unlink(bg)
    bpy.data.collections["VN_Backgrounds"].objects.link(bg)

    # Dialogue box plane (UI in 3D)
    bpy.ops.mesh.primitive_plane_add(size=8, location=(0,0,1))
    dlg = bpy.context.active_object
    dlg.name = "Dialogue_Box"
    dlg.scale = (1, 0.3, 1)
    scene.collection.objects.unlink(dlg)
    bpy.data.collections["VN_UI"].objects.link(dlg)

    # === 3D Stage: classroom_3d with markers and desks ===
    stage_col = bpy.data.collections["VN_3DStage"]

    # Floor
    bpy.ops.mesh.primitive_plane_add(size=12, location=(0,0,0))
    floor = bpy.context.active_object
    floor.name = "Floor_classroom"
    floor.scale = (1, 1, 1)
    scene.collection.objects.unlink(floor)
    stage_col.objects.link(floor)

    # Markers as empties
    for mname, pos in [("marker_eileen", (-1.6, 1.2, 0)), ("marker_sylvie", (1.6, 1.2, 0)), ("marker_center", (0, 0.5, 0))]:
        empty = bpy.data.objects.new(mname, None)
        empty.empty_display_type = 'ARROWS'
        empty.empty_display_size = 0.5
        empty.location = pos
        stage_col.objects.link(empty)

    # Camera presets as empties (targets for lerp)
    for pname, pos, rot in [("preset_closeup_eileen", (-1.6, -1.5, 1.4), (1.1, 0, 0)),
                            ("preset_closeup_sylvie", (1.6, -1.5, 1.4), (1.1, 0, 0)),
                            ("preset_wide", (0, -5, 2.2), (1.05, 0, 0))]:
        pe = bpy.data.objects.new(pname, None)
        pe.empty_display_type = 'SPHERE'
        pe.empty_display_size = 0.3
        pe.location = pos
        pe.rotation_euler = rot
        stage_col.objects.link(pe)

    # Desks (simple cubes)
    desk_positions = [(-2.2, 0.2, 0.25), (-0.7, 0.2, 0.25), (0.8, 0.2, 0.25), (2.3, 0.2, 0.25),
                      (-2.2, -0.4, 0.25), (-0.7, -0.4, 0.25), (0.8, -0.4, 0.25), (2.3, -0.4, 0.25),
                      (-1.4, 0.9, 0.35)]  # teacher desk
    for i, pos in enumerate(desk_positions):
        bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
        desk = bpy.context.active_object
        desk.name = f"Desk_{i:02d}"
        desk.scale = (0.9, 0.55, 0.5) if i < 8 else (1.1, 0.6, 0.6)
        # simple brown material
        dmat = bpy.data.materials.new(name=f"MatDesk_{i:02d}")
        dmat.use_nodes = True
        # color via principled
        try:
            principled = dmat.node_tree.nodes.get("Principled BSDF")
            if principled:
                principled.inputs["Base Color"].default_value = (0.49, 0.37, 0.25, 1) if i < 8 else (0.55, 0.42, 0.30, 1)
        except: pass
        desk.data.materials.append(dmat)
        scene.collection.objects.unlink(desk)
        stage_col.objects.link(desk)

    # Blackboard
    bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 2.0, 1.2))
    board = bpy.context.active_object
    board.name = "Blackboard"
    board.scale = (1.5, 1, 1)
    board.rotation_euler = (1.5708, 0, 0)
    bmat = bpy.data.materials.new(name="MatBoard")
    bmat.use_nodes = True
    try:
        principled = bmat.node_tree.nodes.get("Principled BSDF")
        if principled:
            principled.inputs["Base Color"].default_value = (0.12, 0.22, 0.13, 1)
    except: pass
    board.data.materials.append(bmat)
    scene.collection.objects.unlink(board)
    stage_col.objects.link(board)

    # Simple character placeholders (capsules as cylinders) at markers for preview
    for cname, pos in [("Char_Eileen_placeholder", (-1.6, 1.2, 0.9)), ("Char_Sylvie_placeholder", (1.6, 1.2, 0.9))]:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=1.4, location=pos)
        cap = bpy.context.active_object
        cap.name = cname
        cmat = bpy.data.materials.new(name=f"Mat{cname}")
        cmat.use_nodes = True
        try:
            principled = cmat.node_tree.nodes.get("Principled BSDF")
            if principled:
                col = (0.55, 0.8, 0.55, 1) if "Eileen" in cname else (0.55, 0.55, 0.9, 1)
                principled.inputs["Base Color"].default_value = col
        except: pass
        cap.data.materials.append(cmat)
        scene.collection.objects.unlink(cap)
        stage_col.objects.link(cap)

    # Save
    bpy.ops.wm.save_as_mainfile(filepath="blend/UPVN_Template.blend")
    print("Saved blend/UPVN_Template.blend with VN_3DStage markers+desks+board+camera presets (v0.5)")

except Exception as e:
    import traceback
    traceback.print_exc()
    print("This script must be run inside Blender/UPBGE with bpy:", e)
    print("For headless CI you can just verify the headless engine; blend generation is manual.")
