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

# ---------------------------------------------------------------------------
# Texture-free palette (M26).
#
# The shipped template and every sample game play WITHOUT image textures:
# stages and sprites are solid colors driven by KX_GameObject.color, which the
# template materials wire through Object Info → Emission (see
# blend/upvn_editor_addon.py::_rewrite_unlit). PNG/JPG loading is still
# supported for real projects ("auto" image mode — e.g. a converted Ren'Py
# game), but it is best-effort: when nothing loads, the palette below paints
# the plane so a missing image never equals a missing stage/sprite.
#
# Policy resolution (image_mode_from, first match wins):
#   1. env UPVN_IMAGES            ("color" | "auto")
#   2. controller prop image_mode (game property or custom property)
#   3. IMAGE_MODE_DEFAULT
# The shipped template and sample scenes use "color" — zero texture lookups.
# tools/renpy_convert.py writes "auto" into converted projects so their
# assets/ images are used when present.
IMAGE_MODE_DEFAULT = "color"
_IMAGE_MODES = ("color", "auto")

# curated stage colors for the sample worlds (bg <name> → RGB 0..1)
COLOR_STAGES = {
    "classroom": (0.87, 0.78, 0.60),      # warm tan walls
    "lecturehall": (0.55, 0.62, 0.78),    # cool slate
    "meadow": (0.55, 0.78, 0.45),         # summer green
    "uni": (0.72, 0.50, 0.42),            # brick
    "room": (0.62, 0.52, 0.44),           # dorm wood
    "black": (0.02, 0.02, 0.03),
    "white": (0.95, 0.95, 0.95),
    "night": (0.07, 0.08, 0.16),
    "sakura": (0.95, 0.78, 0.84),
}

# per-character sprite tints for the sample cast (tag → RGB 0..1)
SPRITE_TINTS = {
    "eileen": (0.98, 0.62, 0.35),         # warm silhouette
    "sylvie": (0.45, 0.65, 0.95),         # cool silhouette
    "lucy": (0.55, 0.90, 0.65),
}

# fallback sprite silhouette when neither a tint nor an image exists
SPRITE_FALLBACK_COLOR = (0.75, 0.70, 0.90, 1.0)


def hash_color(name: str) -> tuple:
    """Deterministic, pleasant color for an arbitrary asset name (0..1 RGBA).

    Stable across runs/platforms (hash() is not — it is seeded per process)."""
    import hashlib
    digest = hashlib.md5((name or "asset").encode("utf-8")).digest()
    hue = digest[0] / 255.0
    sat = 0.45 + (digest[1] / 255.0) * 0.25      # 0.45..0.70
    val = 0.55 + (digest[2] / 255.0) * 0.25      # 0.55..0.80
    # HSV → RGB (h in [0,1))
    i = int(hue * 6.0) % 6
    f = hue * 6.0 - int(hue * 6.0)
    p = val * (1.0 - sat)
    q = val * (1.0 - f * sat)
    t = val * (1.0 - (1.0 - f) * sat)
    r, g, b = (
        (val, t, p), (q, val, p), (p, val, t),
        (p, q, val), (t, p, val), (val, p, q),
    )[i]
    return (r, g, b, 1.0)


def stage_color(asset: str) -> tuple:
    """Palette color for a `bg <name>` stage asset (RGBA 0..1).

    Curated COLOR_STAGES first (match on any whitespace-separated token, so
    'bg classroom' and 'bg classroom day' both hit), deterministic hash
    fallback for anything else."""
    tokens = [t.lower().strip(" \t-_") for t in (asset or "").split()]
    for token in tokens:
        if token in COLOR_STAGES:
            rgb = COLOR_STAGES[token]
            return (rgb[0], rgb[1], rgb[2], 1.0)
    return hash_color("stage:" + (asset or ""))


def sprite_color(tag: str) -> tuple:
    """Palette tint for a character tag (RGBA 0..1), hash fallback."""
    import re
    key = (tag or "").lower().strip()
    if key in SPRITE_TINTS:
        rgb = SPRITE_TINTS[key]
        return (rgb[0], rgb[1], rgb[2], 1.0)
    for token in re.split(r"[\s_/-]+", key):
        if token in SPRITE_TINTS:
            rgb = SPRITE_TINTS[token]
            return (rgb[0], rgb[1], rgb[2], 1.0)
    return hash_color("sprite:" + key)


def _prop_str(owner, key: str) -> str | None:
    """Read a property from a KX_GameObject / dict / bpy object, or None.

    Covers both runtime shapes (game properties expose __getitem__/__contains__)
    and editor shapes (bpy objects carry custom properties the same way)."""
    if owner is None:
        return None
    try:
        if key in owner:
            val = owner[key]
            if val is not None:
                return str(val)
    except Exception:
        pass
    try:
        val = owner.get(key)
        if val is not None:
            return str(val)
    except Exception:
        pass
    return None


def image_mode_from(owner=None, env=None) -> str:
    """Resolve the image policy: "color" (texture-free palette) or "auto"
    (use a PNG/JPG/WebP when one is found, palette otherwise).

    Order: env UPVN_IMAGES → owner property image_mode → IMAGE_MODE_DEFAULT.
    Unknown values fail closed to "color" (the robust path)."""
    modes = {"color": "color", "auto": "auto",
             "0": "color", "off": "color", "none": "color",
             "1": "auto", "images": "auto", "on": "auto"}
    import os
    env_val = env if env is not None else os.environ.get("UPVN_IMAGES")
    if env_val:
        resolved = modes.get(str(env_val).strip().lower())
        if resolved:
            return resolved
    prop = _prop_str(owner, "image_mode")
    if prop:
        resolved = modes.get(prop.strip().lower())
        if resolved:
            return resolved
    return IMAGE_MODE_DEFAULT


def apply_object_color(obj, color) -> bool:
    """Set a runtime object tint (KX_GameObject.color / fallback .color).

    The template materials multiply Object Info → Color into Emission, so this
    is the texture-free way everything gets painted. Returns True on success."""
    if obj is None:
        return False
    try:
        obj.color = color
        return True
    except Exception:
        pass
    try:
        obj.color = color
        return True
    except Exception:
        return False


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
