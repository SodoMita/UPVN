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


# Names come from engine/render/contract.py (single source of truth); the
# literals are the fallback for a bare-module import (tests, tooling).
try:                                     # package-relative, like the renderers
    from ..render.contract import HISTORY_PLANE as HISTORY_BOX, HISTORY_TEXT, REWIND_TEXT
except Exception:                        # pragma: no cover - direct module load
    HISTORY_BOX = "History_Box"
    HISTORY_TEXT = "History_Text"
    REWIND_TEXT = "Rewind_Text"
HISTORY_MAX_LINES = 8       # rendered backlog rows the panel can hold
HISTORY_WRAP = 44           # chars per backlog row before wrapping
# Player font metrics, measured from screenshots of the running game — NOT the
# curve numbers the editor reports (bpy's depsgraph says 0.42 em advance /
# 1.117 em pitch, and the *advance* is close, but sizing from the editor's
# numbers while the drawn block behaves differently is what made the backlog
# overrun the panel and slice its own top row off at the window edge):
#   PITCH_EM   row-to-row distance, from an 8-row block spanning 156 px at
#              64 px/unit and em 0.249  -> 0.30 / 0.249
#   ADVANCE_EM widest wrapped row: 44 chars measured 5.6 units at em 0.249
#              -> 0.51 em, with margin for digits and "Name: " prefixes
#   FIT_SLACK  the game window aspect and the engine's render aspect differ by
#              ~9% under XWayland, so the fit keeps that much slack
HISTORY_PITCH_EM = 1.2
HISTORY_ADVANCE_EM = 0.62
HISTORY_FIT_SLACK = 0.85
# The block lives in the upper band: the panel is a full-screen backdrop, but
# the dialogue box owns the lower half, so the backlog must not grow into it.
BACKLOG_TOP = 0.86         # where the FIRST row lands (fraction of half_v)
BACKLOG_BOTTOM = 0.02      # the block may never descend below this


def history_lines(entries, wrap_at: int = HISTORY_WRAP) -> list[str]:
    """Every backlog entry as the wrapped rows the panel will actually draw.

    One row per entry is a lie as soon as a line is longer than `wrap_at`, and
    the row count is what decides both the page budget and the font size — so
    it is computed here once, for the tests and the player alike.
    """
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


def history_pages(entries, max_lines: int = HISTORY_MAX_LINES,
                  wrap_at: int = HISTORY_WRAP) -> tuple[int, int]:
    """(rows_per_page, page_count) for this backlog."""
    rows = history_lines(entries, wrap_at)
    budget = max(1, max_lines - 1) if len(rows) > max_lines else max_lines
    return budget, max(1, -(-len(rows) // budget))      # ceil


def history_max_scroll(entries, max_lines: int = HISTORY_MAX_LINES,
                       wrap_at: int = HISTORY_WRAP) -> int:
    """Highest page index the backlog can scroll to (0 when it all fits)."""
    return history_pages(entries, max_lines, wrap_at)[1] - 1


def format_history(entries, max_lines: int = HISTORY_MAX_LINES,
                   wrap_at: int = HISTORY_WRAP, scroll: int = 0) -> str:
    """Backlog body for the 3D font object: newest row last, tags stripped.

    Pure (no bge) so the same text is asserted by the headless tests and drawn
    by the player. Entries are the dicts recorded in `VNState.history`.

    `scroll` is a PAGE index (0 = the newest page), because the panel is a
    fixed-capacity viewport over a script that can run to thousands of rows and
    one wheel notch should move a screen, not a row. The "rows a-b of n" footer
    only appears when something is above the window and costs one row, which is
    what `history_pages` accounts for.
    """
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
        body = body + [f"— rows {start + 1}-{end} of {total}  ·  "
                       f"page {page + 1}/{pages} (wheel) —"]
    return "\n".join(body)


def build_world_ui(event: Optional[dict], ui_mgr=None, diag=None,
                   n_choices: int = 9, history_entries=None,
                   history_open: bool = False, rewind_depth: int = 0,
                   history_scroll: int = 0) -> dict:
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
    # While the backlog is open it owns the screen: plates are hidden so the
    # number keys cannot resolve a menu the player cannot see (BUG-007 class).
    for i in range(n_choices):
        if i < len(menu) and not history_open:
            txt = str(menu[i].get("text", ""))
            choices.append({"name": f"choice_{i}", "text": f"{i + 1}. {txt}", "visible": True})
        else:
            choices.append({"name": f"choice_{i}", "text": "", "visible": False})
    history_body = (format_history(history_entries, scroll=history_scroll)
                    if history_open else "")
    rewind_visible = bool(rewind_depth)
    return {
        "speaker": speaker,
        "dialogue": dialogue,
        "dialogue_visible": dialogue_on,
        "choices": choices,
        "history_visible": bool(history_open),
        "history": history_body or ("(no backlog yet)" if history_open else ""),
        "rewind_visible": rewind_visible,
        "rewind": (f"« rewound {rewind_depth} — Page Down resumes"
                   if rewind_visible else ""),
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
            # M26d: assign only on change. The layout runs every tick, and
            # writing `body` rebuilds the curve's glyph mesh — a backlog that
            # is merely being *shown* was rebuilt 15-60×/s, and a frame caught
            # mid-rebuild drew the previous page's lines on top of the new
            # ones (visible as doubled, half-torn rows after a wheel page).
            if getattr(data, "body", None) == text:
                return
            try:
                data.body = text
                return
            except Exception:
                pass
    # fallback paths also skip redundant writes (obj["Text"] style bindings)
    _cached = getattr(obj, "_upvn_text", None)
    if _cached is not None and _cached == text:
        return
    for attr in ("text", "Text"):
        try:
            setattr(obj, attr, text)
            try:
                obj._upvn_text = text
            except Exception:
                pass
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

# Camera-space margins (world units, Camera_UI ortho is 15 wide). The player
# draws every VN plane as a flat quad, so "who is in front" is decided by Y
# alone and coplanar-ish quads lose text to depth precision (measured with the
# backlog). Kept as named constants so the dialogue box and the overlay share
# one rule.
# (BACKLOG_TOP / BACKLOG_BOTTOM, the backlog's vertical band, are up by the
# other HISTORY_* constants — defining them twice here is what silently pinned
# the block back to 0.45 and clipped its first row at the window edge.)
UI_DEPTH = 0.12      # panel in front of the story planes
TEXT_FRONT = 0.45    # text in front of its own panel


_font_scale_cache: dict = {}


def set_font_size(obj: Any, em: float) -> None:
    """Make a FONT object `em` world units tall (one em, cap height ≈ 0.7·em).

    M26d bug: this used to be `obj.size = x`, which on a KX_GameObject only
    creates a python attribute — the transform never changed, so every text
    object in the player drew at whatever the authoring file happened to have
    (dialogue looked tiny inside a huge box).

    The shipped template also bakes a per-object curve size (0.20…0.32) which
    multiplies the object scale, so the curve em size is normalised to 1.0
    first: after that the object scale is the single authority and the runtime
    text size is exactly what `layout_screen_ui` asked for. Cached per object —
    touching a curve every tick is not free, and the layout writes one value.
    """
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
        for attr in ("size", "font_size"):      # Curve em size (5.0 renamed it)
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
            obj["scale"] = s                    # dict-like test doubles
        except Exception:
            pass
    if bo is not None:
        try:
            bo.scale = s                        # keep the editor in sync
        except Exception:
            pass


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
    # text is anchored at its origin and grows right/up, so the block needs the
    # box's inner margin or the first glyph sits on the border
    _set_pos(sp, (-half * 0.80, y_ui, -half_v * 0.55))
    _set_pos(dt, (-half * 0.80, y_ui, -half_v * 0.72))
    set_font_size(sp, half * 0.055)
    set_font_size(dt, half * 0.048)
    # --- backlog + rewind indicator (M26d) ---
    # Two depth margins matter and they are not the same thing: a panel has to
    # clear the STORY planes behind it (UI_DEPTH), while text has to clear its
    # OWN panel (TEXT_FRONT).  A text curve a few hundredths in front of a big
    # flat quad is not drawn at all - silently, with a correct body, non-zero
    # dimensions and visible=True; that is how the backlog was invisible for a
    # whole debug round.  The dialogue box gets away with 0.05 only because
    # nothing is ever drawn on top of it.
    #
    # BACKLOG_TOP is the first line's height above the centre as a fraction of
    # the vertical half-extent.  The panel is deliberately taller than the
    # text so the list reads as being inside it; 0.45 is the value confirmed to
    # draw in the player (0.74 pushed the glyphs onto the panel's own edge).
    hbox = get_obj(HISTORY_BOX)
    htext = get_obj(HISTORY_TEXT)
    rtext = get_obj(REWIND_TEXT)
    panel_h = half_v * 0.92
    first_row_z = half_v * BACKLOG_TOP
    # The em is the smaller of the height bound (the rows must fit the band
    # above the dialogue box) and the width bound (a wrapped row must fit
    # between the panel's edges). See HISTORY_PITCH_EM / HISTORY_ADVANCE_EM for
    # where the per-row numbers come from.
    band = half_v * (BACKLOG_TOP - BACKLOG_BOTTOM)
    by_height = band / (HISTORY_MAX_LINES * HISTORY_PITCH_EM)
    by_width = (half * 1.72) / (HISTORY_WRAP * HISTORY_ADVANCE_EM)
    hist_em = min(by_height, by_width) * HISTORY_FIT_SLACK
    # A FONT curve draws *upward* from its origin in the player — `align_y=TOP`
    # is set on the curve and ignored at runtime (measured: an 8-row block
    # anchored at +0.45 had its top row cut by the window edge, its footer
    # landing at the anchor). So the origin is the block's BOTTOM, derived from
    # the row count the payload actually produced.
    body = payload.get("history") or ""
    n_rows = len(body.split("\n")) if body else 0
    block_h = max(1, n_rows) * hist_em * HISTORY_PITCH_EM
    backlog_z = first_row_z - block_h
    if hbox:
        _set_pos(hbox, (0.0, y_ui + UI_DEPTH, 0.0))
        _set_scale(hbox, (half * 0.94, panel_h, 1.0))
    # FONT text grows down from its origin (align_y TOP), so the block is
    # anchored at the top and the panel's top edge is its padding.
    if htext:
        _set_pos(htext, (-half * 0.86, y_ui + UI_DEPTH - TEXT_FRONT, backlog_z))
    set_font_size(htext, hist_em)
    # The rewind marker shares the backlog text's depth plane and height on
    # purpose: the two are never visible at once, so they cannot fight, and the
    # marker reuses the margin that was measured instead of a second guess.
    if rtext:
        _set_pos(rtext, (-half * 0.86, y_ui + UI_DEPTH - TEXT_FRONT,
                         first_row_z - hist_em * HISTORY_PITCH_EM))
    set_font_size(rtext, half * 0.030)
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
        _set_pos(text_obj, (-half * 0.60, y_ui, z + half_v * 0.01))
        set_font_size(text_obj, half * 0.042)
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
    # backlog overlay (M26d): without these two writes H opened a screen the
    # player never drew — headless traces had history, the GUI never did.
    # Order matters twice over: a KX FONT rebuilds its glyph mesh when `body`
    # changes, and writing while the object is still hidden left an empty mesh
    # that never refreshed on reveal (measured in the player: dark panel, no
    # text). So unhide first, then write. And the body is never blanked while
    # hidden — an invisible stale body costs nothing, while a per-toggle clear
    # forces a rebuild on the exact tick it must not miss.
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
