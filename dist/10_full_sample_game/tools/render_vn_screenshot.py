import bpy
import os
from pathlib import Path

# Ensure we have a clean scene
def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def create_material(name, color):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs[0].default_value = color  # Base Color
    return mat

def create_plane(name, size, location, material):
    bpy.ops.mesh.primitive_plane_add(size=size, location=location)
    obj = bpy.context.active_object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    return obj

def create_text(name, body, location, size=0.5, color=(1,1,1,1)):
    # Create text object
    bpy.ops.object.text_add(location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.body = body
    obj.data.size = size
    obj.data.align_x = 'CENTER'
    # Material for text
    mat = bpy.data.materials.new(name=f"{name}_Mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs[0].default_value = color
    obj.data.materials.append(mat)
    # Rotate to face camera
    obj.rotation_euler[0] = 1.5708  # 90 deg
    return obj

def setup_camera():
    # Create camera
    cam_data = bpy.data.cameras.new(name="VN_Cam")
    cam_data.lens = 50
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 12
    cam = bpy.data.objects.new("VN_Cam", cam_data)
    cam.location = (0, -10, 5)
    cam.rotation_euler = (1.5708, 0, 0)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam

def setup_light():
    light_data = bpy.data.lights.new(name="VN_Light", type='SUN')
    light_data.energy = 5
    light = bpy.data.objects.new(name="VN_Light", object_data=light_data)
    light.location = (0, 0, 10)
    bpy.context.scene.collection.objects.link(light)

def render_screenshot(output_path, width=1280, height=720):
    scene = bpy.context.scene
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(output_path)
    # Use Workbench for headless software rendering (no GPU needed, avoids EGL)
    scene.render.engine = 'BLENDER_WORKBENCH'
    # Tune workbench for nicer look
    try:
        scene.display.shading.light = 'STUDIO'
        scene.display.shading.color_type = 'MATERIAL'
    except:
        pass
    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)
    print(f"Rendered {output_path}")

def create_vn_scene(scene_name="bg classroom", character="eileen neutral", dialogue="Hello", speaker="Eileen", output="/tmp/vn_screenshot.png"):
    clear_scene()
    setup_camera()
    setup_light()
    
    # Background
    bg_color = {
        "bg classroom": (0.15, 0.22, 0.45, 1),
        "bg hallway": (0.45, 0.32, 0.15, 1),
        "bg lecturehall": (0.2, 0.25, 0.4, 1),
        "bg uni": (0.22, 0.4, 0.2, 1),
        "black": (0.02, 0.02, 0.03, 1),
    }.get(scene_name, (0.1, 0.1, 0.15, 1))
    bg_mat = create_material("BG_Mat", bg_color)
    bg = create_plane("BG_Plane", size=14, location=(0, 0, 0), material=bg_mat)
    
    # Character sprite plane
    if character:
        char_colors = {
            "eileen neutral": (0.6, 0.8, 0.7, 1),
            "eileen happy": (0.7, 0.9, 0.5, 1),
            "sylvie green smile": (0.4, 0.7, 0.5, 1),
            "sylvie green normal": (0.45, 0.65, 0.55, 1),
        }
        char_color = char_colors.get(character, (0.5, 0.6, 0.7, 1))
        char_mat = create_material("Char_Mat", char_color)
        sprite = create_plane("Sprite", size=2.5, location=(0, 0, 0.1), material=char_mat)
        # Add character name on sprite
        create_text("CharLabel", character, location=(0, 0, 0.2), size=0.3, color=(1,1,1,1))
    
    # Dialogue box (plane at bottom)
    box_mat = create_material("Box_Mat", (0.05, 0.08, 0.15, 0.9))
    box = create_plane("DialogueBox", size=12, location=(0, -2.5, 0.2), material=box_mat)
    box.scale.y = 0.3
    # Apply scale
    bpy.context.view_layer.objects.active = box
    bpy.ops.object.transform_apply(scale=True)
    
    # Speaker name
    if speaker:
        create_text("Speaker", speaker, location=(0, -2.2, 0.25), size=0.35, color=(0.6, 1, 1, 1))
    
    # Dialogue text (wrapped manually)
    # For simplicity, split by words to fit
    words = dialogue.split()
    lines = []
    cur = ""
    for w in words:
        test = cur + " " + w if cur else w
        if len(test) > 45:
            lines.append(cur)
            cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    # Limit to 3 lines
    lines = lines[:3]
    y = -2.6
    for line in lines:
        create_text(f"Line_{y}", line, location=(0, y, 0.25), size=0.28, color=(1,1,1,1))
        y -= 0.4
    
    # Render
    render_screenshot(output)

if __name__ == "__main__":
    # Generate multiple screenshots for different beats
    base = Path("/home/user/upvn/screenshots")
    base.mkdir(exist_ok=True, parents=True)
    
    # Example 00: narration
    create_vn_scene("bg classroom", "eileen neutral", "This is narration. The engine is running inside UPBGE (or headless).", None, str(base/"00_narration.png"))
    
    # Example 01: menu
    create_vn_scene("bg lecturehall", "eileen neutral", "Where should we go?", "Eileen", str(base/"01_menu.png"))
    
    # Example 02: sprites
    create_vn_scene("bg classroom", "eileen happy", "Now we have a background and a character.", "Eileen", str(base/"02_sprites.png"))
    
    # Example 03: interpolation after help
    create_vn_scene("bg meadow", "sylvie green smile", "You chose route good and affection is 1.", "Eileen", str(base/"03_good.png"))
    
    # The Question: Sylvie
    create_vn_scene("bg lecturehall", "sylvie green smile", "Hi there! How was class?", "Sylvie", str(base/"q_sylvie.png"))
    
    # 3D hybrid stub (show different background)
    create_vn_scene("black", None, "3D classroom would be loaded behind planes (hybrid mode).", None, str(base/"3d_hybrid.png"))
    
    print("All screenshots rendered to", base)
