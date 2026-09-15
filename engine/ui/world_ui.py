"""
UPVN — 3D-world UI (no screen-space overlay).

Dialogue, speaker and menu choices are FONT / plane objects in the scene.
The frontend calls `build_world_ui` (pure) then `apply_world_ui` (BGE or a
dict-like object map in tests). Headless screenshots stay on Pillow.
"""
from __future__ import annotations

from typing import Any, Callable, Optional


def wrap_text(text: str, width: int = 42) -> str:
    """Word-wrap preserving {tags} and [interpolation] markers.

    M28 audit: original split on whitespace ignored tags — width measured
    included tag chars, causing premature wraps. Now strips tags for measuring
    but preserves them in output.
    """
    if not text:
        return text or ""
    # Try to use strip_tags if available (for accurate width)
    try:
        from ..core.vn_interpreter import strip_tags
        measure = strip_tags(text)
    except Exception:
        measure = text

    # If text has no spaces, return as-is (avoid breaking [var] or tags)
    if " " not in measure.strip():
        return text

    # Split original text into words, but measure using stripped version
    # Simple approach: split stripped for layout, then reconstruct with original tags
    # For now, wrap stripped and return stripped — tags will be re-added by caller if needed
    # Actually preserve original: we wrap the original text by measuring stripped chunks
    words = (text or "").split()
    if not words:
        return text or ""
    lines: list[str] = []
    cur = words[0]
    # Measure cur stripped length
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
    """Wrap after stripping tags — for history/backlog where tags are gone."""
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
# PITCH_EM is 0.99 measured (History_Text `dimensions.y` 2.207 over 8 rows at
# em 0.2789); 1.0 is used so the reserved band always covers what is drawn.
HISTORY_PITCH_EM = 1.0
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
                   history_scroll: int = 0, screen_errors: Optional[list] = None) -> dict:
    """Pure snapshot of what 3D objects should show this frame.
    M28 audit improvements:
    - Preserves interpolation warnings and screen errors for frontend display
    - Handles ui_mgr typewriter properly (revealed_text vs fully_revealed)
    - Validates menu choices before building
    """
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
                # M28: use revealed_text() for typewriter, but fallback to fully_revealed if done
                try:
                    rev = ui_mgr.revealed_text()
                    # If typewriter not started (empty), use current_text
                    if not rev and hasattr(ui_mgr, 'current_text'):
                        rev = ui_mgr.current_text
                    dialogue = wrap_text(rev or "")
                except Exception as e:
                    print(f"[world_ui] ui_mgr.revealed_text() failed: {e} — using event text")
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
            # Collect errors from event
            if event.get("errors"):
                errors.extend(event["errors"])
        elif t == "menu":
            cap = event.get("caption") or event.get("text") or ""
            dialogue = wrap_text(cap)
            dialogue_on = bool(cap)
            if event.get("errors"):
                errors.extend(event["errors"])
        elif t in ("call_screen", "show_screen"):
            # Screens may have errors — surface them
            if event.get("errors"):
                errors.extend(event["errors"])
                # Show first error as dialogue if no other dialogue
                if not dialogue_on and event["errors"]:
                    dialogue = wrap_text(f"[Screen error: {event['errors'][0][:60]}]")
                    dialogue_on = True

    choices = []
    menu = (event or {}).get("choices") if (event or {}).get("type") == "menu" else None
    menu = menu or []
    # M28: validate menu is list
    if menu and not isinstance(menu, list):
        errors.append(f"menu choices not a list: {type(menu).__name__}")
        menu = []

    for i in range(n_choices):
        if i < len(menu) and not history_open:
            try:
                txt = str(menu[i].get("text", ""))
                # Strip tags for choice display (3D FONT can't render inline tags)
                try:
                    from ..core.vn_interpreter import strip_tags
                    txt_stripped = strip_tags(txt)
                except Exception:
                    txt_stripped = txt
                choices.append({"name": f"choice_{i}", "text": f"{i + 1}. {txt_stripped}", "visible": True})
            except Exception as e:
                errors.append(f"choice {i} build failed: {e}")
                choices.append({"name": f"choice_{i}", "text": f"{i+1}. [Error]", "visible": True})
        else:
            choices.append({"name": f"choice_{i}", "text": "", "visible": False})

    history_body = (format_history(history_entries, scroll=history_scroll)
                    if history_open else "")
    rewind_visible = bool(rewind_depth)

    result = {
        "speaker": speaker,
        "speaker_color": parse_hex_color(speaker_color),
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
    # Typewriter state for frontend to know if done
    if ui_mgr is not None:
        try:
            result["typewriter_done"] = bool(ui_mgr.is_done())
            result["typewriter_progress"] = float(getattr(ui_mgr, '_typewriter_progress', 0.0))
        except Exception:
            pass
    return result


def parse_hex_color(value):
    """'#rrggbb' / '#rgb' / 'rrggbb' -> (r, g, b, 1.0) floats, else None.

    Character colors come from the script (`Character("Eileen",
    color="#c8ffc8")`) and are hex strings; the 3D UI needs them as the
    float RGBA that obj.color eats. Anything malformed -> None (caller
    falls back to the neutral template tint) — a bad color must not take
    the dialogue down with it.
    """
    if not value:
        return None
    s = str(value).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c + c for c in s)
    if len(s) != 6:
        return None
    try:
        return (int(s[0:2], 16) / 255.0, int(s[2:4], 16) / 255.0,
                int(s[4:6], 16) / 255.0, 1.0)
    except ValueError:
        return None


def set_font_text(obj: Any, text: str):
    """Set text on a FONT object. Returns True on success, False on failure, None if obj is None (legacy compat).
    M28 audit: previously swallowed all exceptions silently — now logs failures.
    """
    if obj is None:
        print("[world_ui] set_font_text called with None obj — skipping")
        return None
    # M25 BUG-004: in the UPBGE 0.50 player a FONT game object is a
    # KX_FontObject with no .text/.body/.data — the only runtime handle on the
    # curve is `blenderObject`. Without this the dialogue/choice glyphs never
    # appear (silent no-op), which looked like "dialogue offscreen" in field
    # reports.
    bo = getattr(obj, "blenderObject", None)
    if bo is not None:
        data = getattr(bo, "data", None)
        if data is not None and hasattr(data, "body"):
            if getattr(data, "body", None) == text:
                return True
            try:
                data.body = text
                return True
            except Exception as e:
                print(f"[world_ui] set_font_text blenderObject.data.body failed for {getattr(obj, 'name', '?')}: {e} — trying fallbacks")
    # fallback paths also skip redundant writes (obj["Text"] style bindings)
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
        except Exception as e:
            print(f"[world_ui] set_font_text attr {attr} failed for {getattr(obj, 'name', '?')}: {e}")
    try:
        obj["Text"] = text
        return True
    except Exception as e:
        print(f"[world_ui] set_font_text dict ['Text'] failed for {getattr(obj, 'name', '?')}: {e}")
    try:
        data = getattr(obj, "data", None)
        if data is not None and hasattr(data, "body"):
            data.body = text
            return True
    except Exception as e:
        print(f"[world_ui] set_font_text data.body fallback failed for {getattr(obj, 'name', '?')}: {e}")
    print(f"[world_ui] set_font_text FAILED for {getattr(obj, 'name', '?')} — all paths exhausted")
    return False


def _set_visible(obj: Any, vis: bool) -> bool:
    if obj is None:
        # M28: log missing object — previously silent no-op caused choice never hiding
        # Only log when trying to hide/show visible choices (reduce spam for optional objects)
        return False
    try:
        obj.visible = vis
        return True
    except Exception as e:
        # Try alternative attribute
        try:
            obj["visible"] = vis
            return True
        except Exception:
            pass
        print(f"[world_ui] _set_visible failed for {getattr(obj, 'name', '?')}: {e}")
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
        except Exception as e:
            print(f"[world_ui] _set_pos failed for {getattr(obj, 'name', '?')} to {loc}: {e}")
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
        except Exception as e:
            print(f"[world_ui] _set_scale failed for {getattr(obj, 'name', '?')} to {scl}: {e}")
            return False


def _set_font_color(obj: Any, rgba) -> None:
    """Tint a text object (M26i: colored speaker names, dark shadows).

    The M26 material graph multiplies obj.color into emission, so this is
    the same mechanism the panels use — no material juggling. Guarded like
    set_font_text: change-cached (the layout ticks every frame) and a
    no-op on doubles. Also mirrors onto blenderObject so the EDITOR viewport
    shows the same tint the player will.
    """
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


HOVER_SCALE = 1.12   # M27 HQ: choice plate grows 12% under cursor + edge glow (more visible)

# M27 HQ: improved choice spacing and layout for better readability
CHOICE_SPACING_EM = 0.78  # was 0.75 — slightly more breathing room
CHOICE_WIDTH_FACTOR = 0.74  # wider buttons
CHOICE_HEIGHT_FACTOR = 0.052  # taller for easier clicking

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
        # M27 HQ: better spacing
        z = half_v * 0.44 - i * (half_v * CHOICE_SPACING_EM * 0.16)
        _set_pos(plane, (0.0, y_ui + 0.02, z))
        bump = HOVER_SCALE if (hovered and ch["name"] == hovered) else 1.0
        _set_scale(plane, (half * CHOICE_WIDTH_FACTOR * bump, half * CHOICE_HEIGHT_FACTOR * bump, 1.0))
        _set_pos(text_obj, (-half * 0.62, y_ui, z + half_v * 0.012))
        set_font_size(text_obj, half * 0.044)
    # --- M26i drop shadows: same text, offset behind, fixed dark tint -----
    # The offset is screen-space (x right, z down) plus a small +Y step so
    # the shadow never z-fights its own main text ("coplanar quads lose
    # text to depth precision" — the measured backlog lesson).
    try:
        from engine.render.contract import (SPEAKER_SHADOW, DIALOGUE_SHADOW,
                                            CHOICE_SHADOW_SUFFIX, SHADOW_OFFSET)
    except Exception:
        SPEAKER_SHADOW, DIALOGUE_SHADOW = "Speaker_Shadow", "Dialogue_Shadow"
        CHOICE_SHADOW_SUFFIX, SHADOW_OFFSET = "_shadow", (0.045, 0.04, -0.05)
    ox, oy, oz = SHADOW_OFFSET
    ssp = get_obj(SPEAKER_SHADOW)
    sdt = get_obj(DIALOGUE_SHADOW)
    if ssp is not None:
        _set_pos(ssp, (-half * 0.80 + ox, y_ui + oy, -half_v * 0.55 + oz))
        set_font_size(ssp, half * 0.055)
    if sdt is not None:
        _set_pos(sdt, (-half * 0.80 + ox, y_ui + oy, -half_v * 0.72 + oz))
        set_font_size(sdt, half * 0.048)
    for i, ch in enumerate(payload.get("choices", [])):
        if not ch.get("visible"):
            continue
        z = half_v * 0.42 - i * (half_v * 0.12)
        stext = get_obj(ch["name"] + CHOICE_SHADOW_SUFFIX)
        if stext is not None:
            _set_pos(stext, (-half * 0.60 + ox, y_ui + oy, z + half_v * 0.01 + oz))
            set_font_size(stext, half * 0.042)
    _ = vis_n


def apply_world_ui(get_obj: Callable[[str], Any], payload: dict, ortho: float | None = None,
                   hovered: str | None = None) -> dict:
    """Write payload onto named scene objects. `get_obj(name) -> obj|None`.
    M28 audit: returns status dict with errors, logs failures instead of silent no-ops,
    checks for screen/render errors and surfaces them.
    """
    try:
        from engine.render.contract import (SPEAKER_SHADOW, DIALOGUE_SHADOW,
                                            CHOICE_SHADOW_SUFFIX, SHADOW_COLOR,
                                            DEFAULT_TEXT_COLOR)
    except Exception:
        SPEAKER_SHADOW, DIALOGUE_SHADOW = "Speaker_Shadow", "Dialogue_Shadow"
        CHOICE_SHADOW_SUFFIX = "_shadow"
        SHADOW_COLOR = (0.02, 0.03, 0.08, 1.0)
        DEFAULT_TEXT_COLOR = (0.92, 0.93, 1.0, 1.0)

    status = {"applied": 0, "failed": 0, "errors": []}

    # Surface payload errors (screen render failures, etc.) — M28
    if payload.get("errors"):
        for err in payload["errors"][:3]:  # show first 3
            print(f"[world_ui] payload error: {err}")
        status["errors"].extend(payload["errors"])
    if payload.get("interp_warnings"):
        for w in payload["interp_warnings"][:3]:
            print(f"[world_ui] interp warning: {w}")
        status["errors"].extend(payload["interp_warnings"])

    speaker_obj = get_obj("Speaker_Text")
    dialogue_obj = get_obj("Dialogue_Text")
    box = get_obj("Dialogue_Box")
    speaker_shadow = get_obj(SPEAKER_SHADOW)
    dialogue_shadow = get_obj(DIALOGUE_SHADOW)

    # Track success
    if set_font_text(speaker_obj, payload.get("speaker") or ""):
        status["applied"] += 1
    else:
        status["failed"] += 1
        status["errors"].append("Speaker_Text not found or set failed")

    if set_font_text(dialogue_obj, payload.get("dialogue") or ""):
        status["applied"] += 1
    else:
        status["failed"] += 1
        status["errors"].append("Dialogue_Text not found or set failed")

    _set_font_color(speaker_obj, payload.get("speaker_color") or DEFAULT_TEXT_COLOR)
    vis = bool(payload.get("dialogue_visible"))
    _set_visible(speaker_obj, vis)
    _set_visible(dialogue_obj, vis)
    # Box visibility — ensure at least box shows if any choice visible
    has_visible_choices = any(c.get("visible") for c in payload.get("choices", []))
    if not _set_visible(box, vis or has_visible_choices):
        # Box missing is common in minimal test scenes — don't count as failure
        pass

    if speaker_shadow is not None:
        set_font_text(speaker_shadow, payload.get("speaker") or "")
        _set_font_color(speaker_shadow, SHADOW_COLOR)
        _set_visible(speaker_shadow, vis)
    if dialogue_shadow is not None:
        set_font_text(dialogue_shadow, payload.get("dialogue") or "")
        _set_font_color(dialogue_shadow, SHADOW_COLOR)
        _set_visible(dialogue_shadow, vis)

    hist_on = bool(payload.get("history_visible"))
    hbox = get_obj(HISTORY_BOX)
    htext = get_obj(HISTORY_TEXT)
    _set_visible(hbox, hist_on)
    _set_visible(htext, hist_on)
    if hist_on:
        if not set_font_text(htext, payload.get("history") or ""):
            status["errors"].append("History_Text set failed")

    rtext = get_obj(REWIND_TEXT)
    _set_visible(rtext, bool(payload.get("rewind_visible")))
    if payload.get("rewind_visible"):
        set_font_text(rtext, payload.get("rewind") or "")

    for ch in payload.get("choices", []):
        plane = get_obj(ch["name"])
        text_obj = get_obj(ch["name"] + "_text")
        shadow_obj = get_obj(ch["name"] + CHOICE_SHADOW_SUFFIX)
        on = bool(ch.get("visible"))
        if not _set_visible(plane, on):
            if on:
                status["errors"].append(f"Choice plane {ch['name']} not found")
                status["failed"] += 1
        else:
            if on:
                status["applied"] += 1
        if not _set_visible(text_obj, on):
            if on:
                status["errors"].append(f"Choice text {ch['name']}_text not found")
                status["failed"] += 1
        else:
            if on:
                if set_font_text(text_obj, ch.get("text") or ""):
                    status["applied"] += 1
                else:
                    status["failed"] += 1
        if shadow_obj is not None:
            set_font_text(shadow_obj, ch.get("text") or "")
            _set_font_color(shadow_obj, SHADOW_COLOR)
            _set_visible(shadow_obj, on)

    if ortho is not None:
        try:
            layout_screen_ui(get_obj, payload, ortho=ortho, hovered=hovered)
        except Exception as e:
            print(f"[world_ui] layout_screen_ui failed: {e}")
            status["errors"].append(f"layout failed: {e}")
            status["failed"] += 1

    return status


def normalize_hit_name(name: Optional[str]) -> Optional[str]:
    """choice_0_text → choice_0 so FONT children still resolve as hotspots."""
    if not name:
        return name
    if name.endswith("_text"):
        return name[: -len("_text")]
    return name
