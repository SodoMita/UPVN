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
    from ..render.contract import HISTORY_PLANE as HISTORY_BOX, HISTORY_TEXT, REWIND_TEXT
except Exception:
    HISTORY_BOX = "History_Box"
    HISTORY_TEXT = "History_Text"
    REWIND_TEXT = "Rewind_Text"

HISTORY_MAX_LINES = 8
HISTORY_WRAP = 44
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
    DIALOGUE_BOX_COLOR = (1.0, 1.0, 1.0, 0.8)
    CHOICE_IDLE_COLOR = (0.533, 0.533, 0.533, 0.8)
    CHOICE_HOVER_COLOR = (1.0, 0.498, 0.498, 0.95)
    CHOICE_TEXT_IDLE = (1.0, 1.0, 1.0, 1.0)
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
HOVER_SCALE = 1.02  # tiny, Ren'Py hover is color not scale
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
                    dialogue = wrap_text(rev or "")
                except Exception:
                    dialogue = wrap_text(event.get("display_text") or event.get("text") or "")
                speaker_color = getattr(ui_mgr, "current_color", None)
                interp_warnings = getattr(ui_mgr, '_interp_warnings', []) or event.get("interp_warnings", []) or []
            else:
                speaker = event.get("who_name") or event.get("who") or ""
                raw_text = event.get("display_text") or event.get("text") or ""
                dialogue = wrap_text(raw_text)
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


def _set_pos(obj: Any, loc) -> bool:
    if obj is None:
        return False
    try:
        obj.worldPosition = loc
        return True
    except Exception:
        try:
            obj.location = loc
            return True
        except Exception:
            return False


def _set_scale(obj: Any, scl) -> bool:
    if obj is None:
        return False
    try:
        obj.worldScale = scl
        return True
    except Exception:
        try:
            obj.localScale = scl
            return True
        except Exception:
            return False


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


def _set_object_color(obj: Any, rgba) -> None:
    """Set object color (for UI planes — adaptive white/blue)."""
    if obj is None or rgba is None:
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
    try:
        import bge
        w = float(bge.render.getWindowWidth())
        h = float(bge.render.getWindowHeight())
        if w > 0.0 and h > 0.0:
            return max(0.5, w / h)
    except Exception:
        pass
    return 16.0 / 9.0


_font_scale_cache: dict = {}


def set_font_size(obj: Any, em: float) -> None:
    if obj is None:
        return
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


def layout_screen_ui(get_obj: Callable[[str], Any], payload: dict, ortho: float = 15.0,
                     hovered: str | None = None) -> None:
    """
    Adaptive layout — reads from contract.py which reads from gui_config.py
    which was generated from ANY Ren'Py project's gui.rpy.
    
    This means UPVN automatically adapts to any Ren'Py project's UI without hardcoding.
    """
    half = max(1.0, float(ortho) / 2.0)
    half_v = max(0.5, half / aspect_wh())
    y_ui = -0.55

    box = get_obj("Dialogue_Box")
    sp = get_obj("Speaker_Text")
    dt = get_obj("Dialogue_Text")

    # Dialogue box: adaptive position/scale from contract (which comes from gui_config)
    _set_pos(box, DIALOGUE_LOCATION)
    _set_scale(box, DIALOGUE_SCALE)
    _set_object_color(box, DIALOGUE_BOX_COLOR)

    # Speaker and dialogue at adaptive positions
    _set_pos(sp, SPEAKER_LOCATION)
    _set_pos(dt, DIALOGUE_TEXT_LOCATION)
    # Font sizes from config: name 40px, dialogue 33px mapped to world scale
    # Use adaptive sizes if available from gui_config
    try:
        from ..render.gui_config import get_gui_config
        cfg = get_gui_config()
        name_size = cfg.get("sizes", {}).get("name", 40)
        text_size = cfg.get("sizes", {}).get("text", 33)
        # Map pixel sizes to world scale: 40px/1080*half_v*~2, etc.
        # Keep simple: use contract's logic but allow override
        set_font_size(sp, half * (0.065 * name_size / 40))
        set_font_size(dt, half * (0.055 * text_size / 33))
    except Exception:
        set_font_size(sp, half * 0.065)
        set_font_size(dt, half * 0.055)

    # History / rewind
    hbox = get_obj(HISTORY_BOX)
    htext = get_obj(HISTORY_TEXT)
    rtext = get_obj(REWIND_TEXT)
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
        _set_pos(hbox, (0.0, y_ui + UI_DEPTH, 0.0))
        _set_scale(hbox, (half * 0.94, panel_h, 1.0))
        _set_object_color(hbox, (0.05, 0.05, 0.08, 0.9))
    if htext:
        _set_pos(htext, (-half * 0.86, y_ui + UI_DEPTH - TEXT_FRONT, backlog_z))
    set_font_size(htext, hist_em)
    if rtext:
        _set_pos(rtext, (-half * 0.86, y_ui + UI_DEPTH - TEXT_FRONT,
                         first_row_z - hist_em * HISTORY_PITCH_EM))
    set_font_size(rtext, half * 0.030)

    # Choices — adaptive: uses CHOICE_WIDTH_FACTOR, etc. from contract (from gui_config)
    # base_z from config if available (ypos 405 etc.)
    try:
        base_z = _choice_base_z
    except NameError:
        base_z = half_v * 0.25

    for i, ch in enumerate(payload.get("choices", [])):
        plane = get_obj(ch["name"])
        text_obj = get_obj(ch["name"] + "_text")
        if not ch.get("visible"):
            continue
        # Adaptive spacing from contract
        z = base_z - i * (half_v * CHOICE_SPACING_EM * 0.16 + half_v * 0.06)
        _set_pos(plane, (0.0, y_ui + 0.02, z))
        is_hover = hovered and ch["name"] == hovered
        bump = HOVER_SCALE if is_hover else 1.0
        _set_scale(plane, (half * CHOICE_WIDTH_FACTOR * bump, half * CHOICE_HEIGHT_FACTOR * bump, 1.0))
        _set_object_color(plane, CHOICE_HOVER_COLOR if is_hover else CHOICE_IDLE_COLOR)
        _set_pos(text_obj, (-half * 0.28, y_ui, z + half_v * 0.008))
        set_font_size(text_obj, half * 0.042)
        _set_font_color(text_obj, CHOICE_TEXT_HOVER if is_hover else CHOICE_TEXT_IDLE)

    # Shadows disabled for Ren'Py parity
    try:
        ssp = get_obj(SPEAKER_SHADOW)
        sdt = get_obj(DIALOGUE_SHADOW)
        if ssp:
            _set_visible(ssp, False)
        if sdt:
            _set_visible(sdt, False)
        for ch in payload.get("choices", []):
            if not ch.get("visible"):
                continue
            stext = get_obj(ch["name"] + CHOICE_SHADOW_SUFFIX)
            if stext:
                _set_visible(stext, False)
    except Exception:
        pass


def apply_world_ui(get_obj: Callable[[str], Any], payload: dict, ortho: float | None = None,
                   hovered: str | None = None) -> dict:
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
    _set_visible(box, vis or has_visible_choices)
    if box:
        _set_object_color(box, DIALOGUE_BOX_COLOR)

    try:
        ssp = get_obj(SPEAKER_SHADOW)
        sdt = get_obj(DIALOGUE_SHADOW)
        if ssp:
            _set_visible(ssp, False)
        if sdt:
            _set_visible(sdt, False)
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
        if shadow_obj:
            _set_visible(shadow_obj, False)
        if on:
            set_font_text(text_obj, ch.get("text") or "")

    if ortho is not None:
        try:
            layout_screen_ui(get_obj, payload, ortho=ortho, hovered=hovered)
        except Exception as e:
            print(f"[world_ui] layout_screen_ui failed: {e}")
            status["errors"].append(f"layout failed: {e}")
            status["failed"] += 1

    return status


def normalize_hit_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return name
    if name.endswith("_text"):
        return name[: -len("_text")]
    return name
