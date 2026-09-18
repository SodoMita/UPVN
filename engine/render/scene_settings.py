"""UPVN scene-generator settings — the single place to edit the default scene.

Every tool that *builds* a VN .blend (Setup Scene, ``tools/make_template.py``,
``tools/add_template_ui_objects.py``, ``tools/update_template_materials.py``,
``tools/wire_converted_blend.py``, ``tools/apply_gui_to_blend.py``) reads from
this module. The default template does **not** invent a 3D classroom — put a
real scene in the ``VN_3DStage`` collection. Change a value here, then either:

* press **Setup Scene** in the UPVN panel, or
* regenerate the template:
  ``blender --background --python tools/make_template.py``

Do **not** scatter the same numbers across those scripts. Identifiers
(object/material *names*) still live in ``engine/render/contract.py``.

Values that match Blender's factory defaults are listed on purpose so they
can be changed later without hunting bpy docs. Each block notes the factory
value when it differs from (or equals) what UPVN writes.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Scene identity
# ---------------------------------------------------------------------------
SCENE_NAME = "VN_Main"
WORLD_NAME = "UPVN_World"
COLLECTIONS: tuple[str, ...] = (
    "VN_Backgrounds",
    "VN_Characters",
    "VN_UI",
    "VN_Effects",
    "VN_3DStage",
)

# ---------------------------------------------------------------------------
# Render — Blender factory is 1920×1080 @ 24 fps, engine EEVEE, AgX.
# Pin every knob even when we keep the factory value.
# ---------------------------------------------------------------------------
RENDER_ENGINE = "BLENDER_EEVEE"          # factory: BLENDER_EEVEE (5.0) / BLENDER_EEVEE_NEXT (4.2)
RENDER_ENGINE_FALLBACKS: tuple[str, ...] = (
    "BLENDER_EEVEE",
    "BLENDER_EEVEE_NEXT",
    "BLENDER_WORKBENCH",
)
RENDER_RESOLUTION_X = 1920               # factory 1920 — explicit so we can switch to 1280
RENDER_RESOLUTION_Y = 1080               # factory 1080 — explicit so we can switch to 720
RENDER_RESOLUTION_PERCENTAGE = 100       # factory 100
RENDER_PIXEL_ASPECT_X = 1.0              # factory 1.0
RENDER_PIXEL_ASPECT_Y = 1.0              # factory 1.0
RENDER_FPS = 24                          # factory 24
RENDER_FPS_BASE = 1.0                    # factory 1.0
RENDER_FRAME_START = 1                   # factory 1
RENDER_FRAME_END = 250                   # factory 250
RENDER_FRAME_CURRENT = 1                 # factory 1
RENDER_USE_BORDER = False                # factory False
RENDER_USE_CROP_TO_BORDER = False        # factory False
RENDER_FILTER_SIZE = 1.5                 # factory 1.5
RENDER_DITHER_INTENSITY = 1.0            # factory 1.0
RENDER_FILM_TRANSPARENT = False          # factory False
RENDER_USE_MOTION_BLUR = False           # factory False
RENDER_USE_COMPOSITING = True            # factory True
RENDER_USE_SEQUENCER = True              # factory True
RENDER_THREADS_MODE = "AUTO"             # factory AUTO
IMAGE_FILE_FORMAT = "PNG"                # factory PNG
IMAGE_COLOR_MODE = "RGBA"                # factory RGB in some versions; we pin RGBA
IMAGE_COLOR_DEPTH = "8"                  # factory 8
IMAGE_COMPRESSION = 15                   # factory 15 (PNG)

# Color management — factory view transform is AgX (Blender 4+/5), which
# desaturates emission (white UI → grey). UPVN pins Standard for Ren'Py sRGB.
VIEW_TRANSFORM = "Standard"              # factory "AgX"
VIEW_LOOK = "None"                       # factory "None"
VIEW_EXPOSURE = 0.0                      # factory 0.0
VIEW_GAMMA = 1.0                         # factory 1.0
VIEW_USE_CURVE_MAPPING = False           # factory False
SEQUENCER_COLORSPACE = "sRGB"            # factory sRGB

# EEVEE / EEVEE Next — factory samples. Written when the attribute exists.
EEVEE_TAA_RENDER_SAMPLES = 64            # factory 64
EEVEE_TAA_SAMPLES = 16                   # factory 16 (viewport)
EEVEE_USE_GTAO = False                   # factory False
EEVEE_USE_BLOOM = False                  # factory False (removed in EEVEE Next)
EEVEE_USE_SSR = False                    # factory False
EEVEE_USE_MOTION_BLUR = False            # factory False
EEVEE_USE_VOLUMETRIC = False             # factory False

# ---------------------------------------------------------------------------
# Units / gravity — factory metric, 1.0 scale, −9.81 Z.
# ---------------------------------------------------------------------------
UNIT_SYSTEM = "METRIC"                   # factory METRIC
UNIT_SCALE_LENGTH = 1.0                  # factory 1.0
UNIT_SYSTEM_ROTATION = "DEGREES"         # factory DEGREES
UNIT_LENGTH = "METERS"                   # factory METERS
UNIT_MASS = "KILOGRAMS"                  # factory KILOGRAMS
UNIT_TIME = "SECONDS"                    # factory SECONDS
UNIT_TEMPERATURE = "KELVIN"              # factory KELVIN
USE_GRAVITY = True                       # factory True
GRAVITY = (0.0, 0.0, -9.81)              # factory (0, 0, -9.81)

# ---------------------------------------------------------------------------
# World — factory background ~0.05 grey, strength 1.0.
# UPVN uses a dark navy so unlit UI reads against a near-black void.
# ---------------------------------------------------------------------------
WORLD_USE_NODES = True                   # factory True
WORLD_BACKGROUND_COLOR = (0.015, 0.018, 0.032, 1.0)  # factory ~ (0.05, 0.05, 0.05, 1)
WORLD_BACKGROUND_STRENGTH = 0.6          # factory 1.0
WORLD_COLOR = (0.015, 0.018, 0.032)      # non-node fallback; factory ~0.05 grey

# ---------------------------------------------------------------------------
# Cameras — optics that Blender would leave at factory values are listed too.
# ---------------------------------------------------------------------------
CAMERA_UI = "Camera_UI"
CAMERA_3D = "Camera_3D"

# Pose (UPVN, not a Blender default)
CAMERA_UI_LOCATION = (0.0, -10.0, 0.0)
CAMERA_UI_ROTATION = (math.pi / 2.0, 0.0, 0.0)   # X=90°, looking +Y at XZ planes
CAMERA_UI_ORTHO_SCALE = 15.0             # factory ortho_scale is 6.0
CAMERA_UI_TYPE = "ORTHO"                 # factory PERSP

CAMERA_3D_LOCATION = (0.0, -6.0, 2.5)
CAMERA_3D_ROTATION = (1.15, 0.0, 0.0)
CAMERA_3D_TYPE = "PERSP"                 # factory PERSP
CAMERA_3D_LENS = 50.0                    # factory 50.0 mm

# Shared camera datablock knobs (factory values, now editable)
CAMERA_CLIP_START = 0.1                  # factory 0.1
CAMERA_CLIP_END = 1000.0                 # factory 1000.0
CAMERA_SENSOR_FIT = "AUTO"               # factory AUTO
CAMERA_SENSOR_WIDTH = 36.0               # factory 36.0 mm
CAMERA_SENSOR_HEIGHT = 24.0              # factory 24.0 mm
CAMERA_SHIFT_X = 0.0                     # factory 0.0
CAMERA_SHIFT_Y = 0.0                     # factory 0.0
CAMERA_LENS_UNIT = "MILLIMETERS"         # factory MILLIMETERS
CAMERA_DISPLAY_SIZE = 1.0                # factory 1.0
CAMERA_SHOW_PASSEPARTOUT = True          # factory True
CAMERA_PASSEPARTOUT_ALPHA = 0.5          # factory 0.5
CAMERA_SHOW_LIMITS = False               # factory False
CAMERA_SHOW_MIST = False                 # factory False
CAMERA_SHOW_SENSOR = False               # factory False
CAMERA_SHOW_NAME = False                 # factory False
CAMERA_DOF_USE = False                   # factory False
CAMERA_DOF_APERTURE_FSTOP = 2.8          # factory 2.8
CAMERA_DOF_FOCUS_DISTANCE = 10.0         # factory 10.0

# ---------------------------------------------------------------------------
# UPBGE game / physics (written when Scene.game_settings exists)
# Factory-ish UPBGE values, pinned so they can be changed in one place.
# ---------------------------------------------------------------------------
GAME_FPS = 60                            # typical UPBGE factory 60
GAME_LOGIC_STEP_MAX = 5                  # factory 5
GAME_PHYSICS_ENGINE = "BULLET"           # factory BULLET
GAME_PHYSICS_GRAVITY = 9.8               # factory 9.8
GAME_USE_FRAME_RATE = True               # factory True
GAME_USE_OCCLUSION_CULLING = False       # factory False
GAME_SHOW_DEBUG_PROPERTIES = False       # factory False
GAME_SHOW_FRAMERATE_PROFILE = False      # factory False
GAME_SHOW_PHYSICS_VISUALIZATION = False  # factory False
GAME_STEREO = "NONE"                     # factory NONE
GAME_USE_AUTO_START = False              # factory False
GAME_MATERIAL_MODE = "GPU"               # factory GPU (name varies by build)

# Generated-object physics (not a Blender scene default — UPVN plates)
PHYSICS_TYPE_MESH = "STATIC"             # SENSOR is invisible to rayCast in 0.50
PHYSICS_BOUNDS_TYPE = "TRIANGLE_MESH"    # precise hit; BOX is the fallback
PHYSICS_BOUNDS_FALLBACK = "BOX"
PHYSICS_USE_COLLISION_BOUNDS = True
PHYSICS_USE_GHOST = True
PHYSICS_TYPE_TEXT = "NO_COLLISION"       # FONT must not steal choice rays
PHYSICS_TYPE_EMPTY = None                # leave empties alone

# ---------------------------------------------------------------------------
# Lights
# ---------------------------------------------------------------------------
SUN_NAME = "SUN_Soft"
SUN_TYPE = "SUN"
SUN_ENERGY = 0.8                         # factory sun energy is 1.0
SUN_COLOR = (0.9, 0.92, 1.0)             # factory (1, 1, 1)
SUN_LOCATION = (2.0, -3.0, 4.0)
SUN_ROTATION = (0.8, 0.1, 0.5)
SUN_ANGLE = 0.526                        # factory ~0.526 rad (30°)
SUN_SPECULAR_FACTOR = 1.0                # factory 1.0
SUN_DIFFUSE_FACTOR = 1.0                 # factory 1.0
OTHER_LIGHT_ENERGY = 0.3                 # leftover factory lights, dimmed

# ---------------------------------------------------------------------------
# Geometry convention: every VN plane is a ±1 quad in local XY.
# worldScale is therefore the HALF extent (see world_ui.layout_screen_ui).
# ---------------------------------------------------------------------------
PLANE_ROTATION = (math.pi / 2.0, 0.0, 0.0)  # stand in XZ, facing the UI camera
UNIT_QUAD_VERTS = ((-1.0, -1.0, 0.0), (1.0, -1.0, 0.0),
                   (1.0, 1.0, 0.0), (-1.0, 1.0, 0.0))
UNIT_QUAD_FACES = ((0, 1, 2, 3),)
UNIT_QUAD_UVS = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
UV_LAYER_NAME = "UVMap"

# Backdrop depth. Measured: y=10 is not rendered by the player at all;
# y=0 / y=6 are. Keep at 0.0 unless you have a reason.
BACKGROUND_LAYER = 0.0
BG_FIT_COVER_MARGIN = 1.02               # 2 % overscan when fitting to the view
TRANSITIONS = {"fade": 0.6, "dissolve": 0.45, None: 0.0}

# ---------------------------------------------------------------------------
# 2D stage layout (baked by Setup Scene / make_template)
# ---------------------------------------------------------------------------
BG_PLANE_SIZE = 18.0                     # constructor size; scale is size/2
BG_PLANE_LOCATION = (0.0, 0.0, 0.0)
BG_PLANE_COLOR = (0.95, 0.95, 0.95, 1.0)
BG_PLANE_TINT = (0.95, 0.95, 0.95, 1.0)

DIALOGUE_PLANE_SIZE = 8.0
DIALOGUE_LOCATION = (0.0, -2.0, -3.2)
DIALOGUE_SCALE = (4.0, 1.2, 1.0)
DIALOGUE_PLANE_COLOR = (0.05, 0.05, 0.12, 1.0)
DIALOGUE_TINT = (1.0, 1.0, 1.0, 0.8)
DIALOGUE_BOX_COLOR = (0.07, 0.08, 0.10, 1.0)

SPRITE_POOL_SIZE = 4.0
SPRITE_SCALE = (1.8, 3.2, 1.0)
SPRITE_POOL_COLOR = (0.62, 0.78, 0.55, 1.0)
SPRITE_POOL_TINT = (0.62, 0.78, 0.55, 1.0)
SPRITE_POSITIONS = ("far_left", "left", "center", "right", "far_right")
POSITIONS = {
    "far_left": (-6.0, -1.0, 0.0),
    "left": (-3.5, -1.0, 0.0),
    "center": (0.0, -1.0, 0.0),
    "right": (3.5, -1.0, 0.0),
    "far_right": (6.0, -1.0, 0.0),
}
POSITION_EMPTY_DISPLAY = "PLAIN_AXES"
POSITION_EMPTY_SIZE = 0.6

# History / rewind (initial bake; runtime may re-lay)
HISTORY_PLANE_SIZE = 10.0
HISTORY_LOCATION = (0.0, -7.0, 0.9)
HISTORY_SCALE = (6.6, 3.0, 1.0)
HISTORY_COLOR = (0.02, 0.03, 0.08, 1.0)
HISTORY_TEXT_LOCATION = (-6.0, -8.0, 3.4)
HISTORY_TEXT_SIZE = 0.20
REWIND_TEXT_LOCATION = (-6.0, -9.0, 4.4)
REWIND_TEXT_SIZE = 0.17
REWIND_SHEAR = 0.18

# Speaker / dialogue FONT bake
SPEAKER_LOCATION = (-3.6, -3.0, -2.55)
SPEAKER_TEXT_SIZE = 0.30
DIALOGUE_TEXT_LOCATION = (-3.6, -4.0, -3.15)
DIALOGUE_TEXT_SIZE = 0.26
TEXT_ALIGN_X_DEFAULT = "LEFT"            # factory LEFT
TEXT_ALIGN_Y_DEFAULT = "TOP"             # factory TOP (Blender FONT default is TOP_BASELINE in some builds)
TEXT_ALIGN_X_CHOICE = "CENTER"
TEXT_ALIGN_Y_CHOICE = "CENTER"
TEXT_EXTRUDE = 0.0                       # factory 0.0 — Ren'Py is flat
TEXT_BEVEL = 0.0                         # factory 0.0
TEXT_BEVEL_RESOLUTION = 0                # factory 0
FONT_MATERIAL_COLOR = (1.0, 1.0, 1.0, 1.0)

# Choices (bake). Runtime auto-layout may resize; these are the defaults
# written into a fresh scene. Keep the plate small so BOX collision cannot
# fire outside the visible mesh when auto-layout is OFF.
CHOICE_COUNT = 9
CHOICE_PLANE_SIZE = 2.0
CHOICE_PLANE_SCALE = (1.0, 0.22, 1.0)
CHOICE_LOCATION_X = 0.0
CHOICE_LOCATION_Y = -5.0
CHOICE_TEXT_LOCATION_Y = -6.0
CHOICE_TEXT_Z_OFFSET = 0.08
CHOICE_TEXT_SIZE = 0.22
CHOICE_BASE_Z = 1.05
CHOICE_SPACING = 0.66
CHOICE_IDLE_COLOR = (1.0, 1.0, 1.0, 1.0)
CHOICE_PLANE_COLOR = (1.0, 1.0, 1.0, 0.8)
CHOICE_TEXT_IDLE = (0.251, 0.251, 0.251, 1.0)
CHOICE_HOVER_COLOR = (0.0, 0.094, 0.616, 1.0)
CHOICE_TEXT_HOVER = (1.0, 1.0, 1.0, 1.0)
CHOICE_WIDTH_FACTOR = 0.617
CHOICE_HEIGHT_FACTOR = 0.096
CHOICE_SPACING_EM = 0.38

# Materials (emission graph fallback colors)
MAT_BG_COLOR = (0.95, 0.95, 0.95, 1.0)
MAT_SPRITE_COLOR = (0.62, 0.78, 0.55, 1.0)
MAT_UI_COLOR = (0.07, 0.08, 0.10, 1.0)
MAT_CHOICE_COLOR = (1.0, 1.0, 1.0, 1.0)
MAT_FONT_COLOR = (1.0, 1.0, 1.0, 1.0)
MAT_BLEND_OPAQUE = "OPAQUE"
MAT_BLEND_CLIP = "CLIP"
MAT_BLEND_BLEND = "BLEND"
MAT_ALPHA_THRESHOLD = 0.5                # CLIP cutout; factory 0.5
MAT_SHADOW_METHOD = "NONE"
MAT_USE_BACKFACE_CULLING = False         # factory True on some engines
MAT_EMISSION_STRENGTH = 1.0              # factory n/a (we build Emission)
MAT_EMISSION_STRENGTH_HQ = 1.2
MAT_HQ_FRESNEL_IOR = 1.4
MAT_HQ_FRESNEL_MIX = 0.15
MAT_USE_FAKE_USER = True
TEX_INTERPOLATION = "Closest"            # factory Linear — crisp VN pixels
WHITE_IMAGE_PIXELS = (1.0, 1.0, 1.0, 1.0)

# Object tints (KX_GameObject.color / Object Info → Emission)
OBJECT_TINTS = {
    "BG_Plane": BG_PLANE_TINT,
    "Dialogue_Box": DIALOGUE_BOX_COLOR,
    "History_Box": HISTORY_COLOR,
}
SPRITE_TINT_DEFAULT = SPRITE_POOL_TINT
CHOICE_TINT_DEFAULT = CHOICE_IDLE_COLOR
FONT_TINT_DEFAULT = (0.92, 0.93, 1.0, 1.0)

# Unlit rewrite defaults
UNLIT_TEX_CAPABLE = ("MABackground", "MASprite")
UNLIT_MATERIALS = {
    "MABackground": MAT_BG_COLOR,
    "MASprite": MAT_SPRITE_COLOR,
    "MAUI": MAT_UI_COLOR,
    "MAChoice": MAT_CHOICE_COLOR,
    "MAFont": MAT_FONT_COLOR,
}

# ---------------------------------------------------------------------------
# Controller / runtime props written by the generator
# ---------------------------------------------------------------------------
CONTROLLER_NAME = "VNController"
CONTROLLER_EMPTY_DISPLAY = "CUBE"
CONTROLLER_EMPTY_SIZE = 1.0              # factory empty size 1.0
SCRIPT_PATH_DEFAULT = "//game/script.rpy"
IMAGE_MODE_DEFAULT = "color"
PARSE_MODE_DEFAULT = "safe"
AUTO_LAYOUT_DEFAULT = True
DEBUG_RAY_DEFAULT = False
LAUNCHER_TEXT_NAME = "upvn_launcher"
CONTROLLER_MODULE_DEFAULT = "upvn_launcher"

# Converted-project wiring
CONVERTED_SCRIPT_PATH = "//../game"
CONVERTED_IMAGE_MODE = "auto"
CONVERTED_PARSE_MODE = "full"
IMAGE_BANK_BG_SIZE = 10.0
IMAGE_BANK_SPRITE_SIZE = 4.0
IMAGE_BANK_SPRITE_SCALE = (1.5, 2.4, 1.0)
IMAGE_BANK_SPRITE_LOCATION = (0.0, -0.15, 0.0)
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")

# Bake-stage parking (tools/bake_stage_into_template.py)
STAGE_TEMPLATE_PARK = (30.0, -3.0, -30.0)  # outside Camera_UI frustum
STAGE_TEMPLATE_NAMES = ("eileen", "sylvie")

# Default text colors (bake). Runtime Character(color=) overrides speaker.
SPEAKER_DEFAULT_COLOR = (0.0, 0.18, 0.678, 1.0)
DEFAULT_TEXT_COLOR = (0.251, 0.251, 0.251, 1.0)


# ---------------------------------------------------------------------------
# Apply helpers — generators call these instead of copying bpy assignments
# ---------------------------------------------------------------------------
def _try_set(obj: Any, attr: str, value: Any) -> bool:
    try:
        setattr(obj, attr, value)
        return True
    except Exception:
        return False


def _try_set_path(root: Any, dotted: str, value: Any) -> bool:
    obj = root
    try:
        parts = dotted.split(".")
        for p in parts[:-1]:
            obj = getattr(obj, p)
        setattr(obj, parts[-1], value)
        return True
    except Exception:
        return False


def apply_camera_optics(cam_data: Any, *, ortho: bool, ortho_scale: float | None = None,
                        lens: float | None = None) -> None:
    """Write every camera-datablock knob, including factory-equal ones."""
    if cam_data is None:
        return
    if ortho:
        _try_set(cam_data, "type", CAMERA_UI_TYPE)
        _try_set(cam_data, "ortho_scale",
                 CAMERA_UI_ORTHO_SCALE if ortho_scale is None else ortho_scale)
    else:
        _try_set(cam_data, "type", CAMERA_3D_TYPE)
        _try_set(cam_data, "lens", CAMERA_3D_LENS if lens is None else lens)
        _try_set(cam_data, "lens_unit", CAMERA_LENS_UNIT)
    for attr, val in (
        ("clip_start", CAMERA_CLIP_START),
        ("clip_end", CAMERA_CLIP_END),
        ("sensor_fit", CAMERA_SENSOR_FIT),
        ("sensor_width", CAMERA_SENSOR_WIDTH),
        ("sensor_height", CAMERA_SENSOR_HEIGHT),
        ("shift_x", CAMERA_SHIFT_X),
        ("shift_y", CAMERA_SHIFT_Y),
        ("display_size", CAMERA_DISPLAY_SIZE),
        ("show_passepartout", CAMERA_SHOW_PASSEPARTOUT),
        ("passepartout_alpha", CAMERA_PASSEPARTOUT_ALPHA),
        ("show_limits", CAMERA_SHOW_LIMITS),
        ("show_mist", CAMERA_SHOW_MIST),
        ("show_sensor", CAMERA_SHOW_SENSOR),
        ("show_name", CAMERA_SHOW_NAME),
    ):
        _try_set(cam_data, attr, val)
    _try_set_path(cam_data, "dof.use_dof", CAMERA_DOF_USE)
    _try_set_path(cam_data, "dof.aperture_fstop", CAMERA_DOF_APERTURE_FSTOP)
    _try_set_path(cam_data, "dof.focus_distance", CAMERA_DOF_FOCUS_DISTANCE)


def apply_world(scene: Any, bpy_module: Any = None) -> Any:
    """Create/refresh the world and pin background colour + strength."""
    world = getattr(scene, "world", None)
    if world is None and bpy_module is not None:
        try:
            world = bpy_module.data.worlds.get(WORLD_NAME)
            if world is None:
                world = bpy_module.data.worlds.new(WORLD_NAME)
            scene.world = world
        except Exception:
            return None
    if world is None:
        return None
    _try_set(world, "use_nodes", WORLD_USE_NODES)
    try:
        world.color = WORLD_COLOR
    except Exception:
        pass
    try:
        nt = world.node_tree
        bg_n = nt.nodes.get("Background") if nt is not None else None
        if bg_n is None and nt is not None:
            bg_n = next((n for n in nt.nodes if n.type == "BACKGROUND"), None)
        if bg_n is not None:
            try:
                bg_n.inputs[0].default_value = WORLD_BACKGROUND_COLOR
            except Exception:
                pass
            try:
                bg_n.inputs[1].default_value = WORLD_BACKGROUND_STRENGTH
            except Exception:
                pass
    except Exception:
        pass
    return world


def apply_scene_environment(scene: Any, bpy_module: Any = None) -> dict:
    """Write render / color-management / units / gravity / world / game knobs.

    Missing attributes (Blender vs UPBGE, EEVEE vs EEVEE Next) are skipped.
    Returns a dict of {dotted.path: applied_bool} so tests can assert coverage.
    """
    log: dict[str, bool] = {}
    if scene is None:
        return log

    def rec(path: str, ok: bool) -> None:
        log[path] = ok

    rnd = getattr(scene, "render", None)
    if rnd is not None:
        engine_ok = False
        for eng in (RENDER_ENGINE,) + tuple(
            e for e in RENDER_ENGINE_FALLBACKS if e != RENDER_ENGINE
        ):
            if _try_set(rnd, "engine", eng):
                engine_ok = True
                break
        rec("render.engine", engine_ok)
        rec("render.resolution_x", _try_set(rnd, "resolution_x", RENDER_RESOLUTION_X))
        rec("render.resolution_y", _try_set(rnd, "resolution_y", RENDER_RESOLUTION_Y))
        rec("render.resolution_percentage",
            _try_set(rnd, "resolution_percentage", RENDER_RESOLUTION_PERCENTAGE))
        rec("render.pixel_aspect_x", _try_set(rnd, "pixel_aspect_x", RENDER_PIXEL_ASPECT_X))
        rec("render.pixel_aspect_y", _try_set(rnd, "pixel_aspect_y", RENDER_PIXEL_ASPECT_Y))
        rec("render.fps", _try_set(rnd, "fps", RENDER_FPS))
        rec("render.fps_base", _try_set(rnd, "fps_base", RENDER_FPS_BASE))
        rec("render.use_border", _try_set(rnd, "use_border", RENDER_USE_BORDER))
        rec("render.use_crop_to_border",
            _try_set(rnd, "use_crop_to_border", RENDER_USE_CROP_TO_BORDER))
        rec("render.filter_size", _try_set(rnd, "filter_size", RENDER_FILTER_SIZE))
        rec("render.dither_intensity",
            _try_set(rnd, "dither_intensity", RENDER_DITHER_INTENSITY))
        rec("render.film_transparent",
            _try_set(rnd, "film_transparent", RENDER_FILM_TRANSPARENT))
        rec("render.use_motion_blur",
            _try_set(rnd, "use_motion_blur", RENDER_USE_MOTION_BLUR))
        rec("render.use_compositing",
            _try_set(rnd, "use_compositing", RENDER_USE_COMPOSITING))
        rec("render.use_sequencer",
            _try_set(rnd, "use_sequencer", RENDER_USE_SEQUENCER))
        rec("render.threads_mode", _try_set(rnd, "threads_mode", RENDER_THREADS_MODE))
        rec("render.image_settings.file_format",
            _try_set_path(rnd, "image_settings.file_format", IMAGE_FILE_FORMAT))
        rec("render.image_settings.color_mode",
            _try_set_path(rnd, "image_settings.color_mode", IMAGE_COLOR_MODE))
        rec("render.image_settings.color_depth",
            _try_set_path(rnd, "image_settings.color_depth", IMAGE_COLOR_DEPTH))
        rec("render.image_settings.compression",
            _try_set_path(rnd, "image_settings.compression", IMAGE_COMPRESSION))

    rec("frame_start", _try_set(scene, "frame_start", RENDER_FRAME_START))
    rec("frame_end", _try_set(scene, "frame_end", RENDER_FRAME_END))
    rec("frame_current", _try_set(scene, "frame_current", RENDER_FRAME_CURRENT))

    rec("view_settings.view_transform",
        _try_set_path(scene, "view_settings.view_transform", VIEW_TRANSFORM))
    rec("view_settings.look",
        _try_set_path(scene, "view_settings.look", VIEW_LOOK))
    rec("view_settings.exposure",
        _try_set_path(scene, "view_settings.exposure", VIEW_EXPOSURE))
    rec("view_settings.gamma",
        _try_set_path(scene, "view_settings.gamma", VIEW_GAMMA))
    rec("view_settings.use_curve_mapping",
        _try_set_path(scene, "view_settings.use_curve_mapping", VIEW_USE_CURVE_MAPPING))
    rec("sequencer_colorspace_settings.name",
        _try_set_path(scene, "sequencer_colorspace_settings.name", SEQUENCER_COLORSPACE))

    eevee = getattr(scene, "eevee", None)
    if eevee is not None:
        rec("eevee.taa_render_samples",
            _try_set(eevee, "taa_render_samples", EEVEE_TAA_RENDER_SAMPLES))
        rec("eevee.taa_samples", _try_set(eevee, "taa_samples", EEVEE_TAA_SAMPLES))
        rec("eevee.use_gtao", _try_set(eevee, "use_gtao", EEVEE_USE_GTAO))
        rec("eevee.use_bloom", _try_set(eevee, "use_bloom", EEVEE_USE_BLOOM))
        rec("eevee.use_ssr", _try_set(eevee, "use_ssr", EEVEE_USE_SSR))
        rec("eevee.use_motion_blur",
            _try_set(eevee, "use_motion_blur", EEVEE_USE_MOTION_BLUR))
        rec("eevee.use_volumetric_lights",
            _try_set(eevee, "use_volumetric_lights", EEVEE_USE_VOLUMETRIC))

    units = getattr(scene, "unit_settings", None)
    if units is not None:
        rec("unit_settings.system", _try_set(units, "system", UNIT_SYSTEM))
        rec("unit_settings.scale_length",
            _try_set(units, "scale_length", UNIT_SCALE_LENGTH))
        rec("unit_settings.system_rotation",
            _try_set(units, "system_rotation", UNIT_SYSTEM_ROTATION))
        rec("unit_settings.length_unit", _try_set(units, "length_unit", UNIT_LENGTH))
        rec("unit_settings.mass_unit", _try_set(units, "mass_unit", UNIT_MASS))
        rec("unit_settings.time_unit", _try_set(units, "time_unit", UNIT_TIME))
        rec("unit_settings.temperature_unit",
            _try_set(units, "temperature_unit", UNIT_TEMPERATURE))

    rec("use_gravity", _try_set(scene, "use_gravity", USE_GRAVITY))
    rec("gravity", _try_set(scene, "gravity", GRAVITY))

    apply_world(scene, bpy_module)
    rec("world", getattr(scene, "world", None) is not None)

    gs = getattr(scene, "game_settings", None)
    if gs is None:
        gs = getattr(scene, "game", None)
    if gs is not None:
        rec("game.fps", _try_set(gs, "fps", GAME_FPS))
        rec("game.logic_step_max", _try_set(gs, "logic_step_max", GAME_LOGIC_STEP_MAX))
        rec("game.physics_engine", _try_set(gs, "physics_engine", GAME_PHYSICS_ENGINE))
        rec("game.physics_gravity", _try_set(gs, "physics_gravity", GAME_PHYSICS_GRAVITY))
        rec("game.use_frame_rate", _try_set(gs, "use_frame_rate", GAME_USE_FRAME_RATE))
        rec("game.use_occlusion_culling",
            _try_set(gs, "use_occlusion_culling", GAME_USE_OCCLUSION_CULLING))
        rec("game.show_debug_properties",
            _try_set(gs, "show_debug_properties", GAME_SHOW_DEBUG_PROPERTIES))
        rec("game.show_framerate_profile",
            _try_set(gs, "show_framerate_profile", GAME_SHOW_FRAMERATE_PROFILE))
        rec("game.show_physics_visualization",
            _try_set(gs, "show_physics_visualization", GAME_SHOW_PHYSICS_VISUALIZATION))
        rec("game.stereo", _try_set(gs, "stereo", GAME_STEREO))
        rec("game.use_auto_start", _try_set(gs, "use_auto_start", GAME_USE_AUTO_START))
        rec("game.material_mode", _try_set(gs, "material_mode", GAME_MATERIAL_MODE))
    return log


def apply_mesh_physics(obj: Any, *, is_text: bool = False) -> None:
    """STATIC+bounds for ray-hittable plates; no collision on FONT."""
    if obj is None:
        return
    try:
        g = obj.game
    except Exception:
        return
    if is_text:
        _try_set(g, "physics_type", PHYSICS_TYPE_TEXT)
        _try_set(g, "use_collision_bounds", False)
        _try_set(g, "use_ghost", True)
        _try_set(obj, "collisionGroup", 0)
        _try_set(obj, "collisionMask", 0)
        return
    _try_set(g, "physics_type", PHYSICS_TYPE_MESH)
    _try_set(g, "use_collision_bounds", PHYSICS_USE_COLLISION_BOUNDS)
    if not _try_set(g, "collision_bounds_type", PHYSICS_BOUNDS_TYPE):
        _try_set(g, "collision_bounds_type", PHYSICS_BOUNDS_FALLBACK)
    _try_set(g, "use_ghost", PHYSICS_USE_GHOST)


def choice_location(index: int) -> tuple[float, float, float]:
    z = CHOICE_BASE_Z - index * CHOICE_SPACING
    return (CHOICE_LOCATION_X, CHOICE_LOCATION_Y, z)


def choice_text_location(index: int) -> tuple[float, float, float]:
    loc = choice_location(index)
    return (loc[0], CHOICE_TEXT_LOCATION_Y, loc[2] + CHOICE_TEXT_Z_OFFSET)


def public_constants() -> dict[str, Any]:
    """All UPPER_SNAKE settings (for tests / docs). Callables excluded."""
    out = {}
    for name, val in globals().items():
        if not name.isupper() or name.startswith("_"):
            continue
        if callable(val):
            continue
        out[name] = val
    return out


def iter_blender_default_pins() -> Iterable[tuple[str, Any, str]]:
    """(name, value, factory_note) — knobs we pin even when equal to factory."""
    return (
        ("RENDER_RESOLUTION_X", RENDER_RESOLUTION_X, "factory 1920"),
        ("RENDER_RESOLUTION_Y", RENDER_RESOLUTION_Y, "factory 1080"),
        ("RENDER_FPS", RENDER_FPS, "factory 24"),
        ("RENDER_FRAME_START", RENDER_FRAME_START, "factory 1"),
        ("RENDER_FRAME_END", RENDER_FRAME_END, "factory 250"),
        ("VIEW_EXPOSURE", VIEW_EXPOSURE, "factory 0.0"),
        ("VIEW_GAMMA", VIEW_GAMMA, "factory 1.0"),
        ("CAMERA_CLIP_START", CAMERA_CLIP_START, "factory 0.1"),
        ("CAMERA_CLIP_END", CAMERA_CLIP_END, "factory 1000.0"),
        ("CAMERA_SENSOR_WIDTH", CAMERA_SENSOR_WIDTH, "factory 36.0"),
        ("CAMERA_3D_LENS", CAMERA_3D_LENS, "factory 50.0"),
        ("CAMERA_SHIFT_X", CAMERA_SHIFT_X, "factory 0.0"),
        ("GRAVITY", GRAVITY, "factory (0, 0, -9.81)"),
        ("UNIT_SCALE_LENGTH", UNIT_SCALE_LENGTH, "factory 1.0"),
        ("EEVEE_TAA_RENDER_SAMPLES", EEVEE_TAA_RENDER_SAMPLES, "factory 64"),
        ("TEXT_EXTRUDE", TEXT_EXTRUDE, "factory 0.0"),
        ("MAT_ALPHA_THRESHOLD", MAT_ALPHA_THRESHOLD, "factory 0.5"),
    )
