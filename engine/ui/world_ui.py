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


def apply_world_ui(get_obj: Callable[[str], Any], payload: dict) -> None:
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


def normalize_hit_name(name: Optional[str]) -> Optional[str]:
    """choice_0_text → choice_0 so FONT children still resolve as hotspots."""
    if not name:
        return name
    if name.endswith("_text"):
        return name[: -len("_text")]
    return name
