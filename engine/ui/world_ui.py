"""
UPVN — 3D-world UI (no screen-space overlay) — Adaptive to any Ren'Py project.

Dialogue, speaker and menu choices are FONT / plane objects in the scene.
Frontend calls `build_world_ui` (pure) then `apply_world_ui` (BGE or dict-like).

M28 Adaptive: Instead of hardcoding LearnToCodeRPG values, this module loads
GUI metrics from ANY Ren'Py project's gui.rpy via gui_config.py.

- Textbox: full-width white 255,255,255,204 at bottom, height from gui.textbox_height
- Name: font from gui.name_text_font, color from gui.accent_color, pos from gui.name_xpos/ypos
- Dialogue: font from gui.text_font, color from gui.text_color, pos from gui.dialogue_xpos/ypos
- Choice: width from gui.choice_button_width, spacing from gui.choice_spacing, etc.
- Flat text, NO extrusion, NO shadow for Ren'Py parity (configurable)

The adaptive system:
1. At conversion time: tools/renpy_convert.py parses gui.rpy → game/upvn_gui.json
2. At runtime: gui_config.py loads upvn_gui.json or gui.rpy → contract.py uses it
3. This file (world_ui.py) uses contract.py's adaptive values, so it automatically
   matches ANY Ren'Py project's UI without hardcoding.

Fallback to generic Ren'Py defaults if no config found.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

# History constants
try:
    from ..render.contract import (HISTORY_PLANE as HISTORY_BOX, HISTORY_TEXT,
                                   REWIND_TEXT, CHOICE_PREFIX, CHOICE_COUNT)
except Exception:
    HISTORY_BOX = "History_Box"
    HISTORY_TEXT = "History_Text"
    REWIND_TEXT = "Rewind_Text"
    CHOICE_PREFIX = "choice_"
    CHOICE_COUNT = 9

HISTORY_MAX_LINES = 8
HISTORY_WRAP = 44
# char width of a stock 1280px Ren'Py gui dialogue column (~700px at 22px);
# 42-char wraps made converted projects look narrow next to the original
DIALOGUE_WRAP = 66
HISTORY_PITCH_EM = 1.0
HISTORY_ADVANCE_EM = 0.62
HISTORY_FIT_SLACK = 0.85
BACKLOG_TOP = 0.86
BACKLOG_BOTTOM = 0.02

# Adaptive UI metrics — loaded from contract.py which itself loads from gui_config.py
# This makes the whole system adaptive to any Ren'Py project
try:
    from ..render.contract import (
        DIALOGUE_LOCATION, DIALOGUE_SCALE,
        SPEAKER_LOCATION, DIALOGUE_TEXT_LOCATION,
        DIALOGUE_BOX_COLOR, CHOICE_IDLE_COLOR, CHOICE_HOVER_COLOR,
        CHOICE_TEXT_IDLE, CHOICE_TEXT_HOVER,
        DEFAULT_TEXT_COLOR, SPEAKER_DEFAULT_COLOR,
        SPEAKER_SHADOW, DIALOGUE_SHADOW, CHOICE_SHADOW_SUFFIX,
        SHADOW_COLOR, SHADOW_OFFSET,
        CHOICE_WIDTH_FACTOR, CHOICE_HEIGHT_FACTOR, CHOICE_SPACING_EM, CHOICE_BASE_Z,
        UI_FONT_REGULAR, UI_FONT_BOLD, UI_FONT_NAME, UI_FONT_INTERFACE,
    )
    # Try to get adaptive config for more details
    try:
        from ..render.gui_config import get_gui_config
        _gui_config = get_gui_config()
        _choice_base_z = _gui_config.get("world", {}).get("choice_base_z", CHOICE_BASE_Z)
    except Exception:
        _gui_config = {}
        _choice_base_z = CHOICE_BASE_Z
except Exception:
    # Fallback to generic defaults (not LearnToCodeRPG specific) — generic Ren'Py template
    DIALOGUE_LOCATION = (0.0, -0.4, -3.496)
    DIALOGUE_SCALE = (7.5, 0.722, 1.0)
    SPEAKER_LOCATION = (-5.625, -0.55, -2.873)
    DIALOGUE_TEXT_LOCATION = (-5.406, -0.55, -3.264)
    DIALOGUE_BOX_COLOR = (0.07, 0.08, 0.10, 1.0)  # dark box (opaque: BGE drops alpha)
    CHOICE_IDLE_COLOR = (1.0, 1.0, 1.0, 1.0)
    CHOICE_HOVER_COLOR = (0.0, 0.094, 0.616, 1.0)
    CHOICE_TEXT_IDLE = (0.12, 0.13, 0.15, 1.0)
    CHOICE_TEXT_HOVER = (1.0, 1.0, 1.0, 1.0)
    DEFAULT_TEXT_COLOR = (1.0, 1.0, 1.0, 1.0)
    SPEAKER_DEFAULT_COLOR = (1.0, 0.498, 0.498, 1.0)
    SPEAKER_SHADOW = "Speaker_Shadow"
    DIALOGUE_SHADOW = "Dialogue_Shadow"
    CHOICE_SHADOW_SUFFIX = "_shadow"
    SHADOW_COLOR = (0.0, 0.0, 0.0, 0.0)
    SHADOW_OFFSET = (0.0, 0.0, 0.0)
    CHOICE_WIDTH_FACTOR = 0.411
    CHOICE_HEIGHT_FACTOR = 0.096
    CHOICE_SPACING_EM = 0.252
    CHOICE_BASE_Z = 1.054
    _choice_base_z = CHOICE_BASE_Z
    UI_FONT_REGULAR = "DejaVuSans.ttf"
    UI_FONT_BOLD = "DejaVuSans-Bold.ttf"
    UI_FONT_NAME = "DejaVuSans.ttf"
    UI_FONT_INTERFACE = "DejaVuSans.ttf"
    _gui_config = {}

# Ren'Py identical UI metrics — now adaptive via contract
HOVER_SCALE = 1.02  # tiny, Ren'Py hover is color not scale; physics stays base to avoid outside trigger
# These are now loaded from contract which loads from gui_config
# But keep for backward compat, will be overridden by contract values
CHOICE_SPACING_EM = CHOICE_SPACING_EM
CHOICE_WIDTH_FACTOR = CHOICE_WIDTH_FACTOR
CHOICE_HEIGHT_FACTOR = CHOICE_HEIGHT_FACTOR
UI_DEPTH = 0.12
TEXT_FRONT = 0.45


def wrap_text(text: str, width: int = 42) -> str:
    if not text:
        return text or ""
    try:
        from ..core.vn_interpreter import strip_tags
        measure = strip_tags(text)
    except Exception:
        measure = text
    if " " not in measure.strip():
        return text
    words = (text or "").split()
    if not words:
        return text or ""
    lines: list[str] = []
    cur = words[0]

    def stripped_len(s):
        try:
            from ..core.vn_interpreter import strip_tags
            return len(strip_tags(s))
        except Exception:
            return len(s)

    for w in words[1:]:
        if stripped_len(cur) + 1 + stripped_len(w) <= width:
            cur = cur + " " + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return "\n".join(lines)


def wrap_text_stripped(text: str, width: int = 42) -> str:
    if not text:
        return ""
    words = text.split()
    if not words:
        return text
    lines = []
    cur = words[0]
    for w in words[1:]:
        if len(cur) + 1 + len(w) <= width:
            cur = cur + " " + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return "\n".join(lines)


def history_lines(entries, wrap_at: int = HISTORY_WRAP) -> list[str]:
    rows: list[str] = []
    for e in list(entries or []):
        if not isinstance(e, dict):
            continue
        who = e.get("who_name") or e.get("who") or ""
        body = (e.get("stripped") or e.get("display_text") or e.get("text") or "").strip()
        wrapped = wrap_text(body, width=wrap_at)
        if who:
            first, *rest = wrapped.split("\n")
            wrapped = "\n".join([f"{who}: {first}"] + rest)
        rows.extend(wrapped.split("\n"))
    return rows


def history_pages(entries, max_lines: int = HISTORY_MAX_LINES, wrap_at: int = HISTORY_WRAP) -> tuple[int, int]:
    rows = history_lines(entries, wrap_at)
    budget = max(1, max_lines - 1) if len(rows) > max_lines else max_lines
    return budget, max(1, -(-len(rows) // budget))


def history_max_scroll(entries, max_lines: int = HISTORY_MAX_LINES, wrap_at: int = HISTORY_WRAP) -> int:
    return history_pages(entries, max_lines, wrap_at)[1] - 1


def format_history(entries, max_lines: int = HISTORY_MAX_LINES, wrap_at: int = HISTORY_WRAP, scroll: int = 0) -> str:
    rows = history_lines(entries, wrap_at)
    if not rows:
        return ""
    total = len(rows)
    budget, pages = history_pages(entries, max_lines, wrap_at)
    page = max(0, min(int(scroll or 0), pages - 1))
    end = total - page * budget
    start = max(0, end - budget)
    body = rows[start:end]
    if pages > 1:
        body = body + [f"— rows {start + 1}-{end} of {total}  ·  page {page + 1}/{pages} (wheel) —"]
    return "\n".join(body)


def build_world_ui(event: Optional[dict], ui_mgr=None, diag=None,
                   n_choices: int = 9, history_entries=None,
                   history_open: bool = False, rewind_depth: int = 0,
                   history_scroll: int = 0, screen_errors: Optional[list] = None) -> dict:
    speaker = ""
    dialogue = ""
    dialogue_on = False
    speaker_color = None
    interp_warnings = []
    errors = list(screen_errors or [])

    if diag:
        speaker = "UPVN"
        dialogue = "\n".join(str(x) for x in list(diag)[:8])
        dialogue_on = True
        if len(diag) > 8:
            errors.append(f"diagnostic truncated: {len(diag)} lines")
    elif event:
        t = event.get("type")
        if t == "say":
            if ui_mgr is not None:
                speaker = ui_mgr.current_who or ""
                try:
                    rev = ui_mgr.revealed_text()
                    if not rev and hasattr(ui_mgr, 'current_text'):
                        rev = ui_mgr.current_text
                    dialogue = wrap_text(rev or "", width=DIALOGUE_WRAP)
                except Exception:
                    dialogue = wrap_text(event.get("display_text") or event.get("text") or "",
                                         width=DIALOGUE_WRAP)
                speaker_color = getattr(ui_mgr, "current_color", None)
                interp_warnings = getattr(ui_mgr, '_interp_warnings', []) or event.get("interp_warnings", []) or []
            else:
                speaker = event.get("who_name") or event.get("who") or ""
                raw_text = event.get("display_text") or event.get("text") or ""
                dialogue = wrap_text(raw_text, width=DIALOGUE_WRAP)
                speaker_color = event.get("color")
                interp_warnings = event.get("interp_warnings", []) or []
            dialogue_on = True
            if event.get("errors"):
                errors.extend(event["errors"])
        elif t == "menu":
            cap = event.get("caption") or event.get("text") or ""
            dialogue = wrap_text(cap)
            dialogue_on = bool(cap)
            if event.get("errors"):
                errors.extend(event["errors"])
        elif t in ("call_screen", "show_screen"):
            if event.get("errors"):
                errors.extend(event["errors"])
                if not dialogue_on and event["errors"]:
                    dialogue = wrap_text(f"[Screen error: {event['errors'][0][:60]}]")
                    dialogue_on = True

    choices = []
    menu = (event or {}).get("choices") if (event or {}).get("type") == "menu" else None
    menu = menu or []
    if menu and not isinstance(menu, list):
        errors.append(f"menu choices not a list: {type(menu).__name__}")
        menu = []

    for i in range(n_choices):
        if i < len(menu) and not history_open:
            try:
                txt = str(menu[i].get("text", ""))
                try:
                    from ..core.vn_interpreter import strip_tags
                    txt_stripped = strip_tags(txt)
                except Exception:
                    txt_stripped = txt
                # M28 Adaptive: no hardcoded numbering, use raw text like Ren'Py
                # The numbering was old UPVN behavior, Ren'Py shows raw text
                choices.append({"name": f"choice_{i}", "text": txt_stripped, "visible": True})
            except Exception as e:
                errors.append(f"choice {i} build failed: {e}")
                choices.append({"name": f"choice_{i}", "text": f"{i+1}. [Error]", "visible": True})
        else:
            choices.append({"name": f"choice_{i}", "text": "", "visible": False})

    history_body = (format_history(history_entries, scroll=history_scroll) if history_open else "")
    rewind_visible = bool(rewind_depth)

    result = {
        "speaker": speaker,
        "speaker_color": parse_hex_color(speaker_color) or SPEAKER_DEFAULT_COLOR,
        "dialogue": dialogue,
        "dialogue_visible": dialogue_on,
        "choices": choices,
        "history_visible": bool(history_open),
        "history": history_body or ("(no backlog yet)" if history_open else ""),
        "rewind_visible": rewind_visible,
        "rewind": (f"« rewound {rewind_depth} — Page Down resumes" if rewind_visible else ""),
    }
    if interp_warnings:
        result["interp_warnings"] = interp_warnings
    if errors:
        result["errors"] = errors
    if ui_mgr is not None:
        try:
            result["typewriter_done"] = bool(ui_mgr.is_done())
            result["typewriter_progress"] = float(getattr(ui_mgr, '_typewriter_progress', 0.0))
        except Exception:
            pass
    return result


def parse_hex_color(value):
    if not value:
        return None
    s = str(value).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c + c for c in s)
    if len(s) != 6:
        return None
    try:
        return (int(s[0:2], 16) / 255.0, int(s[2:4], 16) / 255.0, int(s[4:6], 16) / 255.0, 1.0)
    except ValueError:
        return None


def set_font_text(obj: Any, text: str):
    if obj is None:
        return None
    bo = getattr(obj, "blenderObject", None)
    if bo is not None:
        data = getattr(bo, "data", None)
        if data is not None and hasattr(data, "body"):
            if getattr(data, "body", None) == text:
                return True
            try:
                data.body = text
                return True
            except Exception:
                pass
    _cached = getattr(obj, "_upvn_text", None)
    if _cached is not None and _cached == text:
        return True
    for attr in ("text", "Text"):
        try:
            setattr(obj, attr, text)
            try:
                obj._upvn_text = text
            except Exception:
                pass
            return True
        except Exception:
            pass
    try:
        obj["Text"] = text
        return True
    except Exception:
        pass
    try:
        data = getattr(obj, "data", None)
        if data is not None and hasattr(data, "body"):
            data.body = text
            return True
    except Exception:
        pass
    return False


def _set_visible(obj: Any, vis: bool) -> bool:
    if obj is None:
        return False
    try:
        obj.visible = vis
        return True
    except Exception:
        try:
            obj["visible"] = vis
            return True
        except Exception:
            return False


def _is_custom_layout(obj: Any) -> bool:
    """Check if an object has custom layout — the engine should not override its position/scale."""
    if obj is None:
        return False
    try:
        if obj.get("upvn_layout_custom"):
            return True
    except Exception:
        pass
    bo = getattr(obj, "blenderObject", None)
    if bo is not None:
        try:
            if bo.get("upvn_layout_custom"):
                return True
        except Exception:
            pass
    return False


def _set_pos(obj: Any, loc) -> bool:
    if obj is None:
        return False
    if _is_custom_layout(obj):
        return True  # user positioned this object — don't override
    try:
        obj.worldPosition = loc
        # keep physics in sync for accurate ray picking
        try:
            if hasattr(obj, "reinstancePhysicsMesh"):
                obj.reinstancePhysicsMesh()
        except Exception:
            pass
        return True
    except Exception:
        try:
            obj.location = loc
            try:
                if hasattr(obj, "reinstancePhysicsMesh"):
                    obj.reinstancePhysicsMesh()
            except Exception:
                pass
            return True
        except Exception:
            return False


def _set_scale(obj: Any, scl, reinstance: bool = True) -> bool:
    if obj is None:
        return False
    if _is_custom_layout(obj):
        return True  # user scaled this object — don't override
    try:
        obj.worldScale = scl
        # critical: update BOX collision bounds after scale change so
        # hover/click hitbox matches the visual size (fixes outside/inside mismatch)
        # but for hover bump we keep physics at base size to avoid outside trigger
        if reinstance:
            try:
                if hasattr(obj, "reinstancePhysicsMesh"):
                    obj.reinstancePhysicsMesh()
            except Exception:
                pass
        return True
    except Exception:
        try:
            obj.localScale = scl
            if reinstance:
                try:
                    if hasattr(obj, "reinstancePhysicsMesh"):
                        obj.reinstancePhysicsMesh()
                except Exception:
                    pass
            return True
        except Exception:
            return False


def _disable_obj(obj: Any) -> bool:
    """Make an object non-interactive and invisible — used to delete shadows."""
    if obj is None:
        return False
    # try to end the object (BGE)
    try:
        if hasattr(obj, "endObject"):
            obj.endObject()
            return True
    except Exception:
        pass
    # fallback: hide and disable collision
    try:
        obj.visible = False
    except Exception:
        pass
    try:
        # disable physics picking
        if hasattr(obj, "suspendDynamics"):
            obj.suspendDynamics()
    except Exception:
        pass
    try:
        # zero collision mask so rayCast skips it
        obj.collisionGroup = 0
        obj.collisionMask = 0
    except Exception:
        pass
    try:
        obj.worldScale = (0.0, 0.0, 0.0)
        if hasattr(obj, "reinstancePhysicsMesh"):
            obj.reinstancePhysicsMesh()
    except Exception:
        pass
    return True


def _set_font_color(obj: Any, rgba) -> None:
    if obj is None or rgba is None:
        return
    rgba = tuple(round(float(c), 4) for c in rgba)
    cached = getattr(obj, "_upvn_color", None)
    if cached is not None and tuple(cached) == rgba:
        return
    try:
        obj.color = rgba
        obj._upvn_color = rgba
    except Exception:
        return
    bo = getattr(obj, "blenderObject", None)
    if bo is not None:
        try:
            bo.color = rgba
        except Exception:
            pass
        # EEVEE-Next on llvmpipe reads ObjectInfo.Color as white, so tint the
        # emission node of the object's single-user font material directly
        # (parity loop: name who-color must match the character color)
        try:
            for slot in bo.material_slots:
                nt = getattr(slot.material, "node_tree", None)
                if nt is None:
                    continue
                for n in nt.nodes:
                    if n.type == "EMISSION":
                        n.inputs["Color"].default_value = (*rgba[:3], 1.0)
        except Exception:
            pass


def _set_object_color(obj: Any, rgba) -> None:
    """Set object color (for UI planes — adaptive white/blue).
    
    Skipped if obj has upvn_layout_custom set (user controls color via drivers/etc).
    """
    if obj is None or rgba is None:
        return
    if _is_custom_layout(obj):
        return
    try:
        obj.color = rgba
    except Exception:
        pass
    bo = getattr(obj, "blenderObject", None)
    if bo is not None:
        try:
            bo.color = rgba
        except Exception:
            pass


def aspect_wh() -> float:
    # REMOVED: responsive layout — was dynamic aspect from bge.render window, returned w/h or 16/9
    # Now fixed 16/9 for compatibility, responsive deleted per user request
    return 16.0 / 9.0


def view_metrics(ortho: float) -> tuple[float, float, float, float, float]:
    # REMOVED: responsive layout — was complex calculation of half, half_v, wpp, proj_w, proj_h
    # from ortho, aspect_wh(), gui_config resolution, left-anchored virtual frame model
    # wpp = (ortho*H/W)/proj_h, x_world(px) = -half+px*wpp, z_world(py)=half_v-py*wpp
    # This tried to match Ren'Py 8.5 window model but never worked reliably, distracted agents
    # Now fixed values for compatibility
    half = max(1.0, float(ortho) / 2.0)
    half_v = half * 9.0 / 16.0
    proj_w, proj_h = 1280.0, 720.0
    wpp = (2.0 * half_v) / proj_h if proj_h else 0.01
    return half, half_v, wpp, proj_w, proj_h



_font_scale_cache: dict = {}


def set_font_size(obj: Any, em: float) -> None:
    if obj is None:
        return
    if _is_custom_layout(obj):
        return  # user controls font size via drivers/constraints
    try:
        target = round(float(em), 5)
    except Exception:
        return
    if target <= 0.0:
        return
    key = getattr(obj, "name", None) or id(obj)
    if _font_scale_cache.get(key) == target:
        return
    _font_scale_cache[key] = target
    s = (target, target, target)
    bo = getattr(obj, "blenderObject", None)
    if bo is not None:
        data = getattr(bo, "data", None)
        for attr in ("size", "font_size"):
            if data is not None and hasattr(data, attr):
                try:
                    setattr(data, attr, 1.0)
                    break
                except Exception:
                    continue
    applied = False
    for attr in ("worldScale", "scale"):
        try:
            setattr(obj, attr, s)
            applied = True
            try:
                if hasattr(obj, "reinstancePhysicsMesh"):
                    obj.reinstancePhysicsMesh()
            except Exception:
                pass
            break
        except Exception:
            continue
    if not applied:
        try:
            obj["scale"] = s
        except Exception:
            pass
    if bo is not None:
        try:
            bo.scale = s
        except Exception:
            pass
    try:
        if hasattr(obj, "reinstancePhysicsMesh"):
            obj.reinstancePhysicsMesh()
    except Exception:
        pass


def _is_auto_layout_enabled(get_obj: Callable[[str], Any]) -> bool:
    """Check if auto layout is enabled — respects VNController upvn_auto_layout property and per-object upvn_custom.
    
    User requested radio button to toggle remaining auto layout. When OFF, choices keep custom layout.
    """
    try:
        ctrl = get_obj("VNController")
        if ctrl is not None:
            # Check custom property
            try:
                if "upvn_auto_layout" in ctrl:
                    return bool(ctrl["upvn_auto_layout"])
            except Exception:
                pass
            try:
                # Check game property
                gp = getattr(ctrl, "game", None)
                if gp is not None:
                    prop = gp.properties.get("upvn_auto_layout")
                    if prop is not None:
                        return bool(prop.value)
            except Exception:
                pass
            # Also check direct attribute
            try:
                if hasattr(ctrl, "upvn_auto_layout"):
                    return bool(getattr(ctrl, "upvn_auto_layout"))
            except Exception:
                pass
    except Exception:
        pass
    # Default: auto layout ON for backward compat
    return True


def layout_screen_ui(get_obj: Callable[[str], Any], payload: dict, ortho: float = 15.0,
                     hovered: str | None = None, auto_layout: bool | None = None) -> None:
    """
    FIXED layout — no responsive, no aspect adaptation, no gui_config scaling.
    Positions are constant world coordinates, works for any mesh anywhere for buttons.

    REMOVED responsive code that was here:
    - half, half_v, wpp, proj_w, proj_h = view_metrics(ortho)
    - x_of(px) = -half + px*wpp, z_of(py) = half_v - py*wpp
    - borders, pad_x, pad_y, em, gap, btn_w_fixed from wpp and gui_config
    - x_center = x_of(proj_w/2), z_center = z_of(0.375*proj_h)
    - band_top/band_bot clamping for long menus
    All replaced by fixed simple stack.
    """
    # Auto layout toggle — user requested radio button to toggle remaining auto layout
    # When OFF, choices don't stretch/translate, allowing custom layout
    # Check param first, then VNController property, default ON
    if auto_layout is None:
        auto_layout = _is_auto_layout_enabled(get_obj)
    # If auto layout is OFF, skip all auto positioning/scaling for choices
    # (but still handle hover color and generic buttons)

    # Fixed depths: 1 m apart (user directive, avoids draw-order fights)
    y_box = -2.0
    y_speaker = -3.0
    y_text = -4.0
    y_choice = -5.0
    y_choice_text = -6.0
    y_hist = -7.0
    y_hist_text = -8.0

    bg = get_obj("BG_Plane")
    box = get_obj("Dialogue_Box")
    sp = get_obj("Speaker_Text")
    dt = get_obj("Dialogue_Text")

    # Background: keep simple, don't try to cover visible frame responsively
    # (REMOVED: old code tried to scale BG to cover half/half_v)

    # Dialogue box: fixed position from contract (no NDC scaling)
    loc = tuple(DIALOGUE_LOCATION)
    _set_pos(box, (loc[0], y_box, loc[2]))
    _set_scale(box, DIALOGUE_SCALE)
    _set_object_color(box, DIALOGUE_BOX_COLOR)

    # Speaker and dialogue at fixed positions
    spl = tuple(SPEAKER_LOCATION)
    dtl = tuple(DIALOGUE_TEXT_LOCATION)
    _set_pos(sp, (spl[0], y_speaker, spl[2]))
    _set_pos(dt, (dtl[0], y_text, dtl[2]))
    # Fixed font sizes — no adaptive mapping from gui_config pixel sizes
    # (REMOVED: cfg.get("sizes") -> name_size/text_size -> half * factor)
    # Keep simple: use fixed em based on ortho for readability, but not wpp
    # Perspective fix: when camera is perspective, ortho=0, half would be 1 -> tiny buttons
    # User reports perspective triggers outside, ortho OK — because perspective had tiny visual but large collision or mismatched ray
    # Use default ortho 15 for perspective to keep button size reasonable and consistent
    ortho_for_layout = float(ortho) if float(ortho) > 0.001 else 15.0
    half = max(1.0, ortho_for_layout / 2.0)
    set_font_size(sp, half * 0.065)
    set_font_size(dt, half * 0.055)

    # History / rewind — keep original logic for payload but fixed positions for panel
    # Original had panel_h = half_v*0.92 etc., now fixed but still uses payload for text
    hbox = get_obj(HISTORY_BOX)
    htext = get_obj(HISTORY_TEXT)
    rtext = get_obj(REWIND_TEXT)
    # Use fixed half_v for history calculations (was from view_metrics)
    half_v = half * 9.0 / 16.0
    panel_h = half_v * 0.92
    first_row_z = half_v * BACKLOG_TOP
    band = half_v * (BACKLOG_TOP - BACKLOG_BOTTOM)
    by_height = band / (HISTORY_MAX_LINES * HISTORY_PITCH_EM)
    by_width = (half * 1.72) / (HISTORY_WRAP * HISTORY_ADVANCE_EM)
    hist_em = min(by_height, by_width) * HISTORY_FIT_SLACK
    body = payload.get("history") or ""
    n_rows = len(body.split("\n")) if body else 0
    block_h = max(1, n_rows) * hist_em * HISTORY_PITCH_EM
    backlog_z = first_row_z - block_h
    if hbox:
        _set_pos(hbox, (0.0, y_hist, 0.0))
        _set_scale(hbox, (half * 0.94, panel_h, 1.0))
        _set_object_color(hbox, (0.05, 0.05, 0.08, 0.9))
    if htext:
        _set_pos(htext, (-half * 0.86, y_hist_text, backlog_z))
    set_font_size(htext, hist_em)
    if rtext:
        _set_pos(rtext, (-half * 0.86, y_hist_text,
                         first_row_z - hist_em * HISTORY_PITCH_EM))
    set_font_size(rtext, half * 0.030)

    # Choices — FIXED simple vertical stack, centered at x=0, no virtual pixels
    # REMOVED: chc = cfg.get("choice"), borders, pad_x/wpp, em/wpp, gap/wpp,
    # btn_w_fixed/wpp, x_center = x_of(proj_w/2), z_center = z_of(0.375*proj_h),
    # db_z, band_top/band_bot, etc.
    # Now fixed but still respects visible choices and hover
    x_center = 0.0
    # Fixed button metrics — use ortho_for_layout for perspective too
    em = half * 0.04  # half already uses ortho_for_layout
    char_w = em * 0.56
    gap = em * 1.2
    pad_x = em * 2.0
    pad_y = em * 0.2
    btn_h = em + 2 * pad_y
    # vbox centered at z=1.0 fixed
    z_center = 1.0
    visible = [ch for ch in payload.get("choices", []) if ch.get("visible")]
    n_vis = max(1, len(visible))
    block_h = n_vis * btn_h + (n_vis - 1) * gap
    z_top = z_center + block_h / 2.0

    # Boundary fix: ensure choices stay within visible frame (half_v)
    # User reported: when buttons not within some boundary, choice not render and dialogue box disappear, but rewinding reappears
    # This was because fixed layout with z_center=1.0 could place block outside half_v when many choices or large em
    # Now clamp to stay inside visible frame, never hide dialogue box
    # half_v is visible vertical half-extent (from view_metrics)
    try:
        # Ensure block stays within [-half_v*0.9, half_v*0.9] to leave margin for dialogue box
        max_top = half_v * 0.85
        min_bottom = -half_v * 0.5  # leave bottom for dialogue box at -3.496
        # If block too tall, shrink gap first
        if block_h > (max_top - min_bottom):
            # Shrink gap to fit
            gap = max(em * 0.2, (max_top - min_bottom - n_vis * btn_h) / max(1, n_vis - 1))
            block_h = n_vis * btn_h + (n_vis - 1) * gap
            z_top = (max_top + min_bottom) / 2.0 + block_h / 2.0
        # Clamp top
        if z_top > max_top:
            z_top = max_top
        # Clamp bottom
        if z_top - block_h < min_bottom:
            z_top = min_bottom + block_h
    except Exception:
        pass

    for i, ch in enumerate(payload.get("choices", [])):
        plane = get_obj(ch["name"])
        text_obj = get_obj(ch["name"] + "_text")
        if not ch.get("visible"):
            continue

        # If auto layout OFF, don't translate, but still ensure scale matches text to avoid outside trigger
        # User said choices still stretch and translate and don't allow custom layout — now toggle
        # When OFF, respect custom position, but still fix scale to match text width to avoid huge BOX
        # This fixes perspective outside trigger where default 1.0 scale (2.0 world) larger than text
        if not auto_layout:
            is_hover = hovered and ch["name"] == hovered
            bump = HOVER_SCALE if is_hover else 1.0
            is_custom_plane = _is_custom_layout(plane) if plane else False
            if not is_custom_plane and plane is not None:
                # Still set scale to match text to avoid outside trigger, but not position
                try:
                    text = ch.get("text") or ""
                    lines = [l for l in str(text).split("\n") if l] or [""]
                    text_w = max(len(l) for l in lines) * char_w
                    btn_w = text_w + 2 * pad_x
                    btn_w = max(btn_w, 4.0 * em)
                    _set_scale(plane, (btn_w / 2.0 * bump, btn_h / 2.0 * bump, 0.01), reinstance=True)
                except Exception:
                    pass
                _set_object_color(plane, CHOICE_HOVER_COLOR if is_hover else CHOICE_IDLE_COLOR)
            else:
                if is_hover:
                    if plane and not _is_custom_layout(plane):
                        _set_object_color(plane, CHOICE_HOVER_COLOR)
                else:
                    if plane and not _is_custom_layout(plane):
                        _set_object_color(plane, CHOICE_IDLE_COLOR)
            if text_obj:
                _set_font_color(text_obj, CHOICE_TEXT_HOVER if is_hover else CHOICE_TEXT_IDLE)
            continue

        # Auto layout ON: fixed simple vertical stack
        # Check per-object custom layout — if upvn_custom set, skip stretch/translate for that object
        # This allows custom layout per-object even when auto layout is ON
        is_custom_plane = _is_custom_layout(plane) if plane else False
        is_custom_text = _is_custom_layout(text_obj) if text_obj else False

        text = ch.get("text") or ""
        lines = [l for l in str(text).split("\n") if l] or [""]
        text_w = max(len(l) for l in lines) * char_w
        btn_w = text_w + 2 * pad_x
        btn_w = max(btn_w, 4.0 * em)  # min width scales with ortho/em, not fixed
        z = z_top - i * (btn_h + gap) - btn_h / 2.0
        is_hover = hovered and ch["name"] == hovered
        bump = HOVER_SCALE if is_hover else 1.0

        # Only stretch/translate if not custom
        # Physics collision fix: always reinstance so collision matches visual exactly
        # Previously reinstance=False when hovered to avoid outside trigger, but that caused visual larger than collision (fails to trigger on button)
        # Now always reinstance, so collision = visual, no outside trigger, no miss
        # User reported buttons triggered outside visible mesh — due to stale collision from _data_plane 9.26 width and text collision
        # Fixed by disabling text collision and always reinstance plane to match btn_w/btn_h
        if not is_custom_plane:
            _set_scale(plane, (btn_w / 2.0 * bump, btn_h / 2.0 * bump, 0.01), reinstance=True)
            _set_pos(plane, (x_center, y_choice, z))
            _set_object_color(plane, CHOICE_IDLE_COLOR if not is_hover else CHOICE_HOVER_COLOR)
        else:
            # Custom layout: only handle hover color, not scale/pos, but ensure collision is correct
            # For custom, we should still reinstance once to ensure collision matches custom scale from Blender
            try:
                if hasattr(plane, "reinstancePhysicsMesh"):
                    plane.reinstancePhysicsMesh()
            except Exception:
                pass
            if is_hover:
                _set_object_color(plane, CHOICE_HOVER_COLOR)
            else:
                _set_object_color(plane, CHOICE_IDLE_COLOR)

        if not is_custom_text:
            # Choice text now has Middle vertical alignment CENTER/CENTER per user request
            # For CENTER alignment, position should be at x_center, not x_center - text_w/2
            # x_center - text_w/2 was for LEFT alignment to center block, now CENTER needs x_center
            _set_pos(text_obj, (x_center, y_choice_text, z))
            set_font_size(text_obj, em)
            # Ensure Middle alignment at runtime too
            try:
                bo = getattr(text_obj, "blenderObject", None)
                if bo is not None and hasattr(bo, "data"):
                    if hasattr(bo.data, "align_x"):
                        bo.data.align_x = "CENTER"
                    if hasattr(bo.data, "align_y"):
                        bo.data.align_y = "CENTER"
                # Also try direct
                if hasattr(text_obj, "data"):
                    if hasattr(text_obj.data, "align_x"):
                        text_obj.data.align_x = "CENTER"
                    if hasattr(text_obj.data, "align_y"):
                        text_obj.data.align_y = "CENTER"
            except Exception:
                pass
        # Always set font color for hover feedback
        _set_font_color(text_obj, CHOICE_TEXT_HOVER if is_hover else CHOICE_TEXT_IDLE)

    # Generic button support: button can be any mesh anywhere in the world
    if hovered and not hovered.startswith(CHOICE_PREFIX):
        try:
            gen = get_obj(hovered)
            if gen is not None:
                try:
                    vis = getattr(gen, "visible", True)
                except Exception:
                    vis = True
                if vis:
                    if not _is_custom_layout(gen):
                        _set_object_color(gen, CHOICE_HOVER_COLOR)
        except Exception:
            pass

    # Shadows deleted — they have no visual meaning and were ray-blocking
    try:
        ssp = get_obj(SPEAKER_SHADOW)
        sdt = get_obj(DIALOGUE_SHADOW)
        if ssp:
            _disable_obj(ssp)
        if sdt:
            _disable_obj(sdt)
        for ch in payload.get("choices", []):
            stext = get_obj(ch["name"] + CHOICE_SHADOW_SUFFIX)
            if stext:
                _disable_obj(stext)
        for i in range(CHOICE_COUNT):
            sh = get_obj(f"{CHOICE_PREFIX}{i}{CHOICE_SHADOW_SUFFIX}")
            if sh:
                _disable_obj(sh)
    except Exception:
        pass


def apply_world_ui(get_obj: Callable[[str], Any], payload: dict, ortho: float | None = None,
                   hovered: str | None = None, auto_layout: bool | None = None) -> dict:
    status = {"applied": 0, "failed": 0, "errors": []}

    if payload.get("errors"):
        for err in payload["errors"][:3]:
            print(f"[world_ui] payload error: {err}")
        status["errors"].extend(payload["errors"])
    if payload.get("interp_warnings"):
        for w in payload["interp_warnings"][:3]:
            print(f"[world_ui] interp warning: {w}")
        status["errors"].extend(payload["interp_warnings"])

    speaker_obj = get_obj("Speaker_Text")
    dialogue_obj = get_obj("Dialogue_Text")
    box = get_obj("Dialogue_Box")

    if set_font_text(speaker_obj, payload.get("speaker") or ""):
        status["applied"] += 1
    else:
        status["failed"] += 1

    if set_font_text(dialogue_obj, payload.get("dialogue") or ""):
        status["applied"] += 1
    else:
        status["failed"] += 1

    _set_font_color(speaker_obj, payload.get("speaker_color") or SPEAKER_DEFAULT_COLOR)
    _set_font_color(dialogue_obj, DEFAULT_TEXT_COLOR)

    vis = bool(payload.get("dialogue_visible"))
    _set_visible(speaker_obj, vis)
    _set_visible(dialogue_obj, vis)
    has_visible_choices = any(c.get("visible") for c in payload.get("choices", []))
    # Boundary fix: dialogue box should always be visible when dialogue or choices visible
    # Previously, when buttons outside boundary, box disappeared — ensure it stays
    _set_visible(box, vis or has_visible_choices)
    # Also ensure box is not hidden by custom layout check — force visible if needed
    if (vis or has_visible_choices) and box is not None:
        try:
            # If box was hidden due to custom layout, force visible
            if not getattr(box, "visible", True):
                # Only force if not explicitly custom hidden
                if not _is_custom_layout(box):
                    box.visible = True
        except Exception:
            pass
    if box:
        _set_object_color(box, DIALOGUE_BOX_COLOR)

    try:
        ssp = get_obj(SPEAKER_SHADOW)
        sdt = get_obj(DIALOGUE_SHADOW)
        if ssp:
            _disable_obj(ssp)
        if sdt:
            _disable_obj(sdt)
    except Exception:
        pass

    hist_on = bool(payload.get("history_visible"))
    hbox = get_obj(HISTORY_BOX)
    htext = get_obj(HISTORY_TEXT)
    _set_visible(hbox, hist_on)
    _set_visible(htext, hist_on)
    if hist_on:
        set_font_text(htext, payload.get("history") or "")

    rtext = get_obj(REWIND_TEXT)
    _set_visible(rtext, bool(payload.get("rewind_visible")))
    if payload.get("rewind_visible"):
        set_font_text(rtext, payload.get("rewind") or "")

    for ch in payload.get("choices", []):
        plane = get_obj(ch["name"])
        text_obj = get_obj(ch["name"] + "_text")
        shadow_obj = get_obj(ch["name"] + CHOICE_SHADOW_SUFFIX)
        on = bool(ch.get("visible"))
        _set_visible(plane, on)
        _set_visible(text_obj, on)
        # Disable collision for text objects to avoid outside trigger — only button plane should be hittable
        # User reported buttons triggered outside visible mesh, text collision was part of it
        if text_obj is not None:
            try:
                # Try to disable collision for text at runtime
                if hasattr(text_obj, "collisionGroup"):
                    text_obj.collisionGroup = 0
                if hasattr(text_obj, "collisionMask"):
                    text_obj.collisionMask = 0
            except Exception:
                pass
        if shadow_obj:
            _disable_obj(shadow_obj)
        if on:
            set_font_text(text_obj, ch.get("text") or "")

    if not payload.get("choices"):
        # non-menu events carry no choice entries: hide stale menu planes
        # (blend-initial visibility or leftovers from a previous menu)
        for i in range(CHOICE_COUNT):
            _set_visible(get_obj(f"{CHOICE_PREFIX}{i}"), False)
            _set_visible(get_obj(f"{CHOICE_PREFIX}{i}_text"), False)

    if ortho is not None:
        try:
            layout_screen_ui(get_obj, payload, ortho=ortho, hovered=hovered, auto_layout=auto_layout)
        except Exception as e:
            print(f"[world_ui] layout_screen_ui failed: {e}")
            status["errors"].append(f"layout failed: {e}")
            status["failed"] += 1

    return status


def normalize_hit_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return name
    # strip known UI suffixes iteratively: _text and _shadow (and combos)
    # e.g. choice_0_text -> choice_0, choice_0_shadow -> choice_0,
    #      choice_0_text_shadow -> choice_0
    # This fixes ray hits on text or (now-deleted) shadow objects still
    # returning a name that doesn't match the hotspot map.
    # Also supports generic buttons: any mesh ending with those suffixes
    # is normalized to its base name.
    changed = True
    while changed:
        changed = False
        for suf in ("_text", "_shadow"):
            if name.endswith(suf):
                name = name[: -len(suf)]
                changed = True
    return name
