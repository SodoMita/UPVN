"""
UPVN — 3D-world UI (no screen-space overlay).

Dialogue, speaker and menu choices are FONT / plane objects in the scene.
The frontend calls `build_world_ui` (pure) then `apply_world_ui` (BGE or a
dict-like object map in tests). Headless screenshots stay on Pillow.
"""
from __future__ import annotations

from typing import Any, Callable, Optional


def wrap_text(text: str, width: int = 42) -> str:
    words = (text or "").split()
    if not words:
        return text or ""
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        if len(cur) + 1 + len(w) <= width:
            cur = cur + " " + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return "\n".join(lines)


def build_world_ui(event: Optional[dict], ui_mgr=None, diag=None,
                   n_choices: int = 9) -> dict:
    """Pure snapshot of what 3D objects should show this frame."""
    speaker = ""
    dialogue = ""
    dialogue_on = False
    if diag:
        speaker = "UPVN"
        dialogue = "\n".join(str(x) for x in list(diag)[:8])
        dialogue_on = True
    elif event:
        t = event.get("type")
        if t == "say":
            if ui_mgr is not None:
                speaker = ui_mgr.current_who or ""
                dialogue = wrap_text(ui_mgr.revealed_text() or "")
            else:
                speaker = event.get("who_name") or event.get("who") or ""
                dialogue = wrap_text(event.get("display_text") or event.get("text") or "")
            dialogue_on = True
        elif t == "menu":
            cap = event.get("caption") or event.get("text") or ""
            dialogue = wrap_text(cap)
            dialogue_on = bool(cap)
    choices = []
    menu = (event or {}).get("choices") if (event or {}).get("type") == "menu" else None
    menu = menu or []
    for i in range(n_choices):
        if i < len(menu):
            txt = str(menu[i].get("text", ""))
            choices.append({"name": f"choice_{i}", "text": f"{i + 1}. {txt}", "visible": True})
        else:
            choices.append({"name": f"choice_{i}", "text": "", "visible": False})
    return {
        "speaker": speaker,
        "dialogue": dialogue,
        "dialogue_visible": dialogue_on,
        "choices": choices,
    }


def set_font_text(obj: Any, text: str) -> None:
    if obj is None:
        return
    # M25 BUG-004: in the UPBGE 0.50 player a FONT game object is a
    # KX_FontObject with no .text/.body/.data — the only runtime handle on the
    # curve is `blenderObject`. Without this the dialogue/choice glyphs never
    # appear (silent no-op), which looked like "dialogue offscreen" in field
    # reports.
    bo = getattr(obj, "blenderObject", None)
    if bo is not None:
        data = getattr(bo, "data", None)
        if data is not None and hasattr(data, "body"):
            try:
                data.body = text
                return
            except Exception:
                pass
    for attr in ("text", "Text"):
        try:
            setattr(obj, attr, text)
            return
        except Exception:
            pass
    try:
        obj["Text"] = text
        return
    except Exception:
        pass
    try:
        data = getattr(obj, "data", None)
        if data is not None and hasattr(data, "body"):
            data.body = text
    except Exception:
        pass


def _set_visible(obj: Any, vis: bool) -> None:
    if obj is None:
        return
    try:
        obj.visible = vis
    except Exception:
        pass


def _set_pos(obj: Any, loc) -> None:
    if obj is None:
        return
    try:
        obj.worldPosition = loc
    except Exception:
        try:
            obj.location = loc
        except Exception:
            pass


def _set_scale(obj: Any, scl) -> None:
    if obj is None:
        return
    try:
        obj.worldScale = scl
    except Exception:
        try:
            obj.localScale = scl
        except Exception:
            pass


def aspect_wh() -> float:
    """Window width/height; falls back to 16:9 when bge is unavailable."""
    try:
        import bge  # type: ignore

        w = float(bge.render.getWindowWidth())
        h = float(bge.render.getWindowHeight())
        if w > 0.0 and h > 0.0:
            return max(0.5, w / h)
    except Exception:
        pass
    return 16.0 / 9.0


HOVER_SCALE = 1.08   # M26c: choice plate grows 8% under the cursor


def layout_screen_ui(get_obj: Callable[[str], Any], payload: dict, ortho: float = 15.0,
                     hovered: str | None = None) -> None:
    """Place UI as a fraction of the current ortho frustum so zoom leaves text on screen.

    M25 BUG-003: `ortho_scale` spans the *width* of the window, so the vertical
    half-extent is half_width / aspect. Using the width for Z pushed the whole
    dialogue box below the frame on any non-square window (read as "black
    screen / missing UI" in the player).
    """
    half = max(1.0, float(ortho) / 2.0)          # horizontal half-extent
    half_v = max(0.5, half / aspect_wh())        # vertical half-extent
    y_ui = -0.55
    box = get_obj("Dialogue_Box")
    sp = get_obj("Speaker_Text")
    dt = get_obj("Dialogue_Text")
    _set_pos(box, (0.0, y_ui + 0.05, -half_v * 0.72))
    _set_scale(box, (half * 0.92, half * 0.14, 1.0))
    _set_pos(sp, (-half * 0.85, y_ui, -half_v * 0.62))
    _set_pos(dt, (-half * 0.85, y_ui, -half_v * 0.70))
    try:
        if sp is not None:
            sp.size = half * 0.045
    except Exception:
        pass
    try:
        if dt is not None:
            dt.size = half * 0.040
    except Exception:
        pass
    vis_n = sum(1 for c in payload.get("choices", []) if c.get("visible"))
    for i, ch in enumerate(payload.get("choices", [])):
        plane = get_obj(ch["name"])
        text_obj = get_obj(ch["name"] + "_text")
        if not ch.get("visible"):
            continue
        z = half_v * 0.42 - i * (half_v * 0.12)
        _set_pos(plane, (0.0, y_ui + 0.02, z))
        # M26c: scale-on-hover is applied HERE — layout owns choice-plane
        # scale, so the multiplier survives camera zoom/ortho changes and
        # cannot go stale (a cached base scale would). Re-applied each frame.
        bump = HOVER_SCALE if (hovered and ch["name"] == hovered) else 1.0
        _set_scale(plane, (half * 0.70 * bump, half * 0.045 * bump, 1.0))
        _set_pos(text_obj, (-half * 0.62, y_ui, z + half_v * 0.01))
        try:
            if text_obj is not None:
                text_obj.size = half * 0.038
        except Exception:
            pass
    _ = vis_n


def apply_world_ui(get_obj: Callable[[str], Any], payload: dict, ortho: float | None = None,
                   hovered: str | None = None) -> None:
    """Write payload onto named scene objects. `get_obj(name) -> obj|None`."""
    speaker_obj = get_obj("Speaker_Text")
    dialogue_obj = get_obj("Dialogue_Text")
    box = get_obj("Dialogue_Box")
    set_font_text(speaker_obj, payload.get("speaker") or "")
    set_font_text(dialogue_obj, payload.get("dialogue") or "")
    vis = bool(payload.get("dialogue_visible"))
    _set_visible(speaker_obj, vis)
    _set_visible(dialogue_obj, vis)
    _set_visible(box, vis or any(c.get("visible") for c in payload.get("choices", [])))
    for ch in payload.get("choices", []):
        plane = get_obj(ch["name"])
        text_obj = get_obj(ch["name"] + "_text")
        on = bool(ch.get("visible"))
        _set_visible(plane, on)
        _set_visible(text_obj, on)
        set_font_text(text_obj, ch.get("text") or "")
    if ortho is not None:
        layout_screen_ui(get_obj, payload, ortho=ortho, hovered=hovered)


def normalize_hit_name(name: Optional[str]) -> Optional[str]:
    """choice_0_text → choice_0 so FONT children still resolve as hotspots."""
    if not name:
        return name
    if name.endswith("_text"):
        return name[: -len("_text")]
    return name
