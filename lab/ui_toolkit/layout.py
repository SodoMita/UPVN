"""
UPVN UI toolkit — **static** layout resolver (PHASE 1).

Prototype. Lives in `lab/` on purpose: `engine/` must not import this until
phase 1 has been proven against real UPBGE screenshots (see `lab/README.md`).

What "static layout" means here
-------------------------------
A widget's rectangle is decided **entirely** by the numbers the theme carries:

    x      from Style.x            (pixels, or a fraction when marked)
    y      from Style.y
    width  from Style.width        (fallback: Style.min_width, then text metrics)
    height from Style.height       (fallback: Style.min_height, then line count)

No flow, no stacking of siblings, no stretching to fit a parent, and
**no padding / margin / spacing arithmetic** — those fields already exist in
`Style`, but phase 1 leaves them inert and says so on every emitted box
(`padding_applied=False`).  Phase 2 (auto layout) may only *add* behaviour; the
diff must be visible in the draw list, never silent.

`anchor` (and fractional coordinates) are applied because they are part of
*interpreting one explicit coordinate*, not of laying siblings out — Ren'Py
itself does this (`xpos 0.5` + `xanchor 0.5` centres a widget).  They do not
depend on any other widget.

Cascade (highest priority last, same ladder as `Style` docs):

    theme.styles["default"] → styles["<kind>"] → styles["<kind>.<role>"]
    → styles["<kind>.<role>:<state>"] → widget.style (per instance)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .style import Padding, Style, Theme, get_theme

__all__ = [
    "Widget", "Box", "TextMetrics", "estimate_metrics",
    "resolve_layout", "draw_list",
    "build_say_screen", "build_menu_screen", "build_input_screen",
]

# --------------------------------------------------------------- text metrics


class TextMetrics:
    """How big is a string?  Injected by the backend; phase 1 never guesses
    more than a monospace-ish estimate, and only when the theme gives no size.
    """

    def __init__(self, measure: Optional[Callable[[str, float, bool], Tuple[float, float]]] = None,
                 advance_em: float = 0.55, line_height_em: float = 1.15):
        self._measure = measure
        self.advance_em = advance_em
        self.line_height_em = line_height_em

    def size(self, text: str, font_size: float, bold: bool = False) -> Tuple[float, float]:
        if self._measure is not None:
            w, h = self._measure(text, font_size, bold)
            return float(w), float(h)
        return estimate_metrics(text, font_size, self.advance_em, self.line_height_em)

    def wrap(self, text: str, font_size: float, max_width: float,
             bold: bool = False) -> List[str]:
        """Greedy word wrap inside a width the *theme* chose (not auto-layout)."""
        if max_width <= 0:
            return list(text.splitlines()) or [""]
        out: List[str] = []
        for para in str(text).splitlines() or [""]:
            words = para.split()
            if not words:
                out.append("")
                continue
            line = words[0]
            for word in words[1:]:
                trial = line + " " + word
                if self.size(trial, font_size, bold)[0] <= max_width:
                    line = trial
                else:
                    out.append(line)
                    line = word
            out.append(line)
        return out or [""]


def estimate_metrics(text: str, font_size: float, advance_em: float = 0.55,
                     line_height_em: float = 1.15) -> Tuple[float, float]:
    lines = [l for l in str(text).splitlines()] or [""]
    width = max(len(l) for l in lines) * font_size * advance_em
    height = len(lines) * font_size * line_height_em
    return (width, height)


# -------------------------------------------------------------------- widgets


@dataclass
class Widget:
    """One node of a screen tree.  Pure data — no backend, no engine."""

    kind: str                                  # panel | label | button | input | image | bar
    role: str = ""                             # speaker | dialogue | choice | prompt | ...
    text: str = ""
    style: Optional[Style] = None              # per-instance override (highest priority)
    state: Optional[str] = None                # hover | selected | disabled
    id: str = ""
    value: str = ""                            # input field content
    caret: bool = False                        # draw a caret in the input
    children: List["Widget"] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def style_key(self) -> str:
        key = self.kind
        if self.role:
            key = f"{self.kind}.{self.role}"
        if self.state:
            key = f"{key}:{self.state}"
        return key


@dataclass
class Box:
    """A resolved rectangle + resolved style.  This is what a backend draws."""

    id: str
    kind: str
    role: str
    state: Optional[str]
    x: float
    y: float
    w: float
    h: float
    style: Style
    text: str = ""
    lines: List[str] = field(default_factory=list)
    value: str = ""
    caret: bool = False
    # phase-1 bookkeeping — makes a future auto-layout diff auditable
    sized_by: Dict[str, str] = field(default_factory=dict)   # {"width": "explicit"|"min"|"text"}
    padding_applied: bool = False
    anchor_applied: bool = False
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def rect(self) -> Tuple[float, float, float, float]:
        return (self.x, self.y, self.w, self.h)

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "kind": self.kind, "role": self.role, "state": self.state,
            "x": self.x, "y": self.y, "w": self.w, "h": self.h,
            "text": self.text, "lines": list(self.lines),
            "value": self.value, "caret": self.caret,
            "sized_by": dict(self.sized_by),
            "padding_applied": self.padding_applied,
            "anchor_applied": self.anchor_applied,
            "style": self.style.to_dict(),
            "meta": dict(self.meta),
        }


_ANCHORS = {
    "topleft": (0.0, 0.0), "lefttop": (0.0, 0.0),
    "top": (0.5, 0.0), "topcenter": (0.5, 0.0), "centertop": (0.5, 0.0),
    "topright": (1.0, 0.0), "righttop": (1.0, 0.0),
    "left": (0.0, 0.5), "centerleft": (0.0, 0.5), "middleleft": (0.0, 0.5),
    "center": (0.5, 0.5), "middle": (0.5, 0.5), "middlecenter": (0.5, 0.5),
    "right": (1.0, 0.5), "centerright": (1.0, 0.5),
    "bottomleft": (0.0, 1.0), "leftbottom": (0.0, 1.0),
    "bottom": (0.5, 1.0), "bottomcenter": (0.5, 1.0), "centerbottom": (0.5, 1.0),
    "bottomright": (1.0, 1.0), "rightbottom": (1.0, 1.0),
}


def _anchor_fractions(anchor: Optional[str]) -> Tuple[float, float]:
    if not anchor:
        return (0.0, 0.0)
    return _ANCHORS.get(str(anchor).strip().lower().replace("-", "").replace("_", ""),
                        (0.0, 0.0))


# ------------------------------------------------------------------ resolver


def resolve_layout(widgets: Sequence[Widget], theme: Optional[Theme] = None,
                   metrics: Optional[TextMetrics] = None,
                   parent: Optional[Box] = None) -> List[Box]:
    """Resolve a widget tree into flat, absolute rectangles.

    Phase 1 contract:
      * geometry comes only from the style cascade — never from siblings;
      * `padding`, `margin` and `spacing` are carried through but **not applied**;
      * children are offset by their parent's origin (explicit coordinates only).
    """
    theme = theme or get_theme()
    metrics = metrics or TextMetrics()
    boxes: List[Box] = []

    for i, w in enumerate(widgets):
        resolved = (w.style or Style()).merge(theme.style(w.style_key))
        resolved = resolved.for_state(w.state)

        p_x = parent.x if parent else 0.0
        p_y = parent.y if parent else 0.0
        p_w = parent.w if parent else theme.width
        p_h = parent.h if parent else theme.height

        # --- position -----------------------------------------------------
        x_raw = resolved.x if resolved.x is not None else 0.0
        y_raw = resolved.y if resolved.y is not None else 0.0
        x_frac = bool(resolved.extra.get("x_frac"))
        y_frac = bool(resolved.extra.get("y_frac"))
        x = x_raw * p_w if x_frac else x_raw
        y = y_raw * p_h if y_frac else y_raw

        # --- size ---------------------------------------------------------
        font_size = float(resolved.font_size or 0.0)
        bold = bool(resolved.bold)
        lines: List[str] = []
        sized: Dict[str, str] = {}

        if resolved.width is not None:
            w_box = float(resolved.width)
            sized["width"] = "explicit"
        elif resolved.min_width is not None:
            w_box = float(resolved.min_width)
            sized["width"] = "min"
        elif w.text:
            w_box, _ = metrics.size(w.text, font_size, bold)
            sized["width"] = "text"
        else:
            w_box = 0.0
            sized["width"] = "none"

        # wrapping is content shaping inside an explicit width, not auto-layout
        if w.text and resolved.wrap is not False:
            wrap_w = w_box if sized["width"] != "none" and w_box > 0 else p_w
            lines = metrics.wrap(w.text, font_size, wrap_w, bold)
        elif w.text:
            lines = list(w.text.splitlines()) or [""]

        if resolved.height is not None:
            h_box = float(resolved.height)
            sized["height"] = "explicit"
        elif resolved.min_height is not None:
            h_box = float(resolved.min_height)
            sized["height"] = "min"
        elif w.text:
            line_h = font_size * metrics.line_height_em * float(resolved.line_spacing or 1.0)
            h_box = max(1, len(lines)) * line_h
            sized["height"] = "text"
        else:
            h_box = 0.0
            sized["height"] = "none"

        # --- anchor -------------------------------------------------------
        ax, ay = _anchor_fractions(resolved.anchor)
        anchor_applied = bool(ax or ay)
        x -= ax * w_box
        y -= ay * h_box

        box = Box(
            id=w.id or f"{w.kind}.{w.role or 'generic'}{'.' + str(i) if not w.id else ''}",
            kind=w.kind, role=w.role, state=w.state,
            x=p_x + x, y=p_y + y, w=w_box, h=h_box,
            style=resolved, text=w.text, lines=lines,
            value=w.value, caret=w.caret,
            sized_by=sized,
            padding_applied=False,          # PHASE 1 — inert on purpose
            anchor_applied=anchor_applied,
            meta=dict(w.meta),
        )
        boxes.append(box)
        if w.children:
            boxes.extend(resolve_layout(w.children, theme=theme, metrics=metrics,
                                        parent=box))
    return boxes


def draw_list(boxes: Sequence[Box]) -> List[Dict[str, Any]]:
    """Backend-facing draw list: z-sorted plain dicts (no engine imports)."""
    ordered = sorted(boxes, key=lambda b: (int(b.style.zorder or 0), b.y))
    return [b.to_dict() for b in ordered]


# ---------------------------------------------------------- screen builders
#
# These mirror Ren'Py's own screen geometry, which is *static*: every position
# is a constant from gui.rpy (gui.textbox_height, gui.choice_ypos, …).  Nothing
# here measures a sibling.


def build_say_screen(theme: Theme, speaker: str = "", text: str = "",
                     state: str = "") -> List[Widget]:
    """Ren'Py `screen say`: bottom-anchored textbox + name + dialogue."""
    w, h = theme.width, theme.height
    box_h = theme.metric("textbox_height", 278.0)
    top = h - box_h
    name_y = top + theme.metric("name_ypos", 0.0)
    text_y = name_y + theme.metric("name_to_text_gap", 66.0)

    panel = Widget(
        kind="panel", role="textbox", id="textbox",
        style=Style(x=0.0, y=top, width=w, height=box_h),
    )
    children: List[Widget] = []
    if speaker:
        children.append(Widget(
            kind="label", role="speaker", id="speaker", text=speaker,
            style=Style(x=theme.metric("name_xpos", 155.0), y=name_y - top),
        ))
    children.append(Widget(
        kind="label", role="dialogue", id="dialogue", text=text,
        style=Style(x=theme.metric("text_xpos", 155.0), y=text_y - top,
                    width=theme.metric("text_width", w - 2 * theme.metric("text_xpos", 155.0))),
    ))
    panel.children = children
    return [panel]


def build_menu_screen(theme: Theme, caption: str = "",
                      choices: Sequence[str] = (),
                      hovered: Optional[int] = None) -> List[Widget]:
    """Ren'Py `screen choice`: N fixed-size buttons at fixed y offsets.

    Ren'Py places the block with `gui.choice_ypos` and steps by
    `gui.choice_button_height + gui.choice_spacing`.  That is a constant
    stride from the theme — still static, because no button is measured.
    """
    btn_h = theme.metric("choice_button_height", 52.0)
    btn_w = theme.metric("choice_button_width", 1185.0)
    stride = btn_h + theme.metric("choice_spacing", 33.0)
    y0 = theme.metric("choice_ypos", 405.0)

    widgets: List[Widget] = []
    if caption:
        widgets.append(Widget(
            kind="label", role="caption", id="menu_caption", text=caption,
            style=Style(x=theme.metric("caption_xpos", theme.width / 2.0),
                        y=max(0.0, y0 - stride), anchor="center",
                        extra={"x_frac": False, "y_frac": False}),
        ))
    for i, label in enumerate(choices):
        widgets.append(Widget(
            kind="button", role="choice", id=f"choice_{i}", text=str(label),
            state="hover" if (hovered is not None and i == int(hovered)) else None,
            meta={"index": i},
            style=Style(x=theme.metric("choice_xpos", 0.5), y=y0 + i * stride,
                        width=btn_w, height=btn_h, anchor="center",
                        extra={"x_frac": True, "y_frac": False}),
        ))
    return widgets


def build_input_screen(theme: Theme, prompt: str = "", value: str = "",
                       caret: bool = True, ok_label: str = "OK") -> List[Widget]:
    """Ren'Py `renpy.input()` prompt screen: prompt + one-line text field."""
    w, h = theme.width, theme.height
    field_h = max(56.0, theme.size("interface", 26.0) * 2.0)
    field_w = max(420.0, w * 0.42)
    cx = w / 2.0
    cy = h * 0.45

    widgets: List[Widget] = []
    if prompt:
        widgets.append(Widget(
            kind="label", role="prompt", id="input_prompt", text=prompt,
            style=Style(x=cx, y=cy - field_h, width=field_w, anchor="center"),
        ))
    widgets.append(Widget(
        kind="input", role="text", id="input_field", value=value, caret=caret,
        style=Style(x=cx, y=cy, width=field_w, height=field_h, anchor="center"),
    ))
    if ok_label:
        widgets.append(Widget(
            kind="button", role="quick", id="input_ok", text=ok_label,
            style=Style(x=cx, y=cy + field_h * 1.6, width=min(field_w, 260.0),
                        height=44.0, anchor="center"),
        ))
    return widgets
