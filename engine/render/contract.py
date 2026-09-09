"""
UPVN — Scene contract: the single source of truth for how interface code maps
to scene objects (naming convention).

Architecture note (why this file exists):
    UPVN's renderers do NOT store object references in the .blend. At runtime
    they look objects up in the current scene BY NAME (fixed identifiers). That
    is simple and robust — the .blend stays a pure data file — but it made the
    connection invisible to editors: "which object does the code expect?".

    Every name below is the authority:
      * scene_manager.py and sprite_renderer.py import from here, so code and
        this spec can never drift apart;
      * the add-on (blend/upvn_editor_addon.py) and tools/make_template.py
        create exactly these objects/materials/collections;
      * the "Check Scene Wiring" operator compares the open scene against
        check_contract() and reports missing/present items by name.

Dialogue note: NO screen-space overlay. Speaker_Text / Dialogue_Text / choice_N
are FONT + plane objects in the scene; engine/ui/world_ui.py writes `.text`
every frame. The Dialogue_Box plane is the panel behind that 3D text.
"""
from __future__ import annotations

import math

# --------------------------------------------------------------------------- identifiers
# background plane + its material (SceneManager._swap_bge_texture)
BG_PLANE = "BG_Plane"
BG_MATERIAL = "MABackground"

# 2D game camera. Planes live in XZ (stand up); camera sits on -Y looking +Y
# (Blender Front). XY ground planes + this camera = edge-on / unused view.
CAMERA_UI = "Camera_UI"
CAMERA_3D = "Camera_3D"
CAMERA_UI_LOCATION = (0.0, -10.0, 0.0)
CAMERA_UI_ROTATION = (math.pi / 2.0, 0.0, 0.0)
CAMERA_UI_ORTHO_SCALE = 15.0
CAMERA_3D_LOCATION = (0.0, -6.0, 2.5)
CAMERA_3D_ROTATION = (1.15, 0.0, 0.0)
PLANE_ROTATION = (math.pi / 2.0, 0.0, 0.0)
DIALOGUE_LOCATION = (0.0, -0.4, -3.2)
DIALOGUE_SCALE = (4.0, 1.2, 1.0)

# sprite planes per position + their material (SpriteRenderer._bge_show)
SPRITE_MATERIAL = "MASprite"
SPRITE_POSITIONS = ("far_left", "left", "center", "right", "far_right")

# fallback lookups when a position plane is missing (SpriteRenderer._bge_show)
SPRITE_FALLBACK_TAG = "Sprite"          # generic plane
SPRITE_TAG_PREFIX = "Sprite_"           # f"Sprite_{tag}" per-actor plane

# 3D UI (no overlay): panel + FONT objects + clickable choice planes
DIALOGUE_PLANE = "Dialogue_Box"
SPEAKER_TEXT = "Speaker_Text"
DIALOGUE_TEXT = "Dialogue_Text"
CHOICE_PREFIX = "choice_"
CHOICE_COUNT = 9
UI_MATERIAL = "MAUI"
SPEAKER_LOCATION = (-3.6, -0.55, -2.55)
DIALOGUE_TEXT_LOCATION = (-3.6, -0.55, -3.15)
SPRITE_SCALE = (1.8, 3.2, 1.0)  # local XY after rot X=90 → world X / Z height

# UPBGE world positions (X = screen X, Y = depth toward camera, Z = screen Y).
# Camera_UI at (0,-10,0) looking +Y, ortho_scale=15.
POSITIONS = {
    "far_left": (-6.0, -0.15, 0.0),
    "left": (-3.5, -0.15, 0.0),
    "center": (0.0, -0.15, 0.0),
    "right": (3.5, -0.15, 0.0),
    "far_right": (6.0, -0.15, 0.0),
}

# collections that make scene order explicit in the editor
COLLECTIONS = ("VN_Backgrounds", "VN_Characters", "VN_UI",
               "VN_Effects", "VN_3DStage")

# controller object carrying script_path / upvn_root / upvn_bricks properties
CONTROLLER = "VNController"

# launcher text datablock referenced by the Always -> Python brick
LAUNCHER_TEXT = "upvn_launcher"

# asset file layout relative to the .blend file
ASSET_BACKGROUNDS = "assets/backgrounds"     # <asset>.png|jpg|webp
ASSET_SPRITES = "assets/sprites"             # <asset with '/' or '_'>.png


def required_objects() -> list[dict]:
    """Authoritative, ordered list of every named item the code expects.

    kind: 'object' | 'material' | 'collection' | 'text'
    """
    items: list[dict] = []
    for name, purpose, used_by in (
        (BG_PLANE, "background image plane (texture swapped on 'scene')",
         "engine/render/scene_manager.py::SceneManager._swap_bge_texture"),
        (DIALOGUE_PLANE, "3D panel behind Speaker_Text / Dialogue_Text",
         "engine/ui/world_ui.py"),
        (SPEAKER_TEXT, "3D FONT — speaker name",
         "engine/ui/world_ui.py"),
        (DIALOGUE_TEXT, "3D FONT — dialogue body",
         "engine/ui/world_ui.py"),
    ):
        items.append({"kind": "object", "name": name,
                      "purpose": purpose, "used_by": used_by})
    for pos in SPRITE_POSITIONS:
        items.append({"kind": "object",
                      "name": f"Sprite_{pos}",
                      "purpose": f"sprite plane at '{pos}' (texture swapped on 'show')",
                      "used_by": "engine/render/sprite_renderer.py::SpriteRenderer._bge_show"})
    for i in range(CHOICE_COUNT):
        items.append({"kind": "object",
                      "name": f"{CHOICE_PREFIX}{i}",
                      "purpose": f"clickable 3D menu button {i}",
                      "used_by": "engine/ui/world_ui.py + engine/ui/pointer.py"})
    for mat, purpose in (
        (BG_MATERIAL, "material slot of BG_Plane receiving the background texture"),
        (SPRITE_MATERIAL, "material slot of every Sprite_* plane receiving the sprite texture"),
    ):
        items.append({"kind": "material", "name": mat,
                      "purpose": purpose,
                      "used_by": "engine/render/* (bge.texture.materialID)"})
    for name in COLLECTIONS:
        items.append({"kind": "collection", "name": name,
                      "purpose": "scene organisation (backgrounds / characters / UI / effects / 3D stage)",
                      "used_by": "tools/make_template.py, blend/upvn_editor_addon.py::build_vn_scene"})
    items.append({"kind": "object", "name": CAMERA_UI,
                  "purpose": "ortho game camera (Front: XZ planes, looking +Y); runtime binds scene.active_camera",
                  "used_by": "bge_frontend/frontend.py::_bind_camera, blend/upvn_editor_addon.py::build_vn_scene"})
    items.append({"kind": "object", "name": CAMERA_3D,
                  "purpose": "perspective camera for hybrid 3D stages / camera_preset",
                  "used_by": "engine/render/stage_manager.py (optional)"})
    items.append({"kind": "object", "name": CONTROLLER,
                  "purpose": "game object with script_path/upvn_root properties and the Always->Python brick",
                  "used_by": "bge_frontend/frontend.py::main (reads script_path), launcher text"})
    items.append({"kind": "text", "name": LAUNCHER_TEXT,
                  "purpose": "path-bootstrap script executed by the Python controller",
                  "used_by": "blend/upvn_editor_addon.py (SCRIPT mode controller)"})
    return items


def check_contract(object_names, material_names=(), collection_names=(),
                   text_names=()) -> dict:
    """Compare a scene's contents against the contract. Pure function, headless.

    object_names / material_names / collection_names / text_names: iterables of
    names actually present in the scene (e.g. [o.name for o in objects]).

    Returns {"present": [item...], "missing": [item...]} where item is the
    contract dict, with kind filtered appropriately.
    """
    present: list[dict] = []
    missing: list[dict] = []
    for item in required_objects():
        name = item["name"]
        if item["kind"] == "object":
            found = name in set(object_names)
        elif item["kind"] == "material":
            found = name in set(material_names)
        elif item["kind"] == "collection":
            found = name in set(collection_names)
        elif item["kind"] == "text":
            found = name in set(text_names)
        else:
            found = False
        (present if found else missing).append(item)
    return {"present": present, "missing": missing}
