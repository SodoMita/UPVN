"""
UPVN UI toolkit — styles and themes (M32).

The UI system is **general purpose**: a widget tree is laid out in a virtual
pixel space (default 1280x720, exactly Ren'Py's `config.screen_width/height`)
and then handed to a backend (3D UPBGE objects, headless draw list, PIL
preview…).  Nothing in here knows about `bge`, Blender or `.rpy` — the theme is
plain data and can be authored by hand, generated from a Ren'Py `gui.rpy`
(`Theme.from_renpy`) or loaded from JSON (`Theme.load`).

Customisation ladder (each level overrides the one above):
    1. `Theme.styles["default"]`                    — base for every widget
    2. `Theme.styles["<family>"]`                   — e.g. "label", "button"
    3. `Theme.styles["<family>.<role>"]`            — e.g. "label.speaker"
    4. `Theme.styles["<family>.<role>:<state>"]`    — e.g. "button.choice:hover"
    5. `widget.style`                               — per-instance override
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, fields as dataclass_fields
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

Color = Tuple[float, float, float, float]

# --------------------------------------------------------------------- colors


def parse_color(value: Any, default: Optional[Color] = None) -> Optional[Color]:
    """Accept '#rgb', '#rrggbb', '#rrggbbaa', 'r,g,b[,a]' (0-255) or a sequence."""
    if value is None:
        return default
    if isinstance(value, (list, tuple)):
        vals = [float(v) for v in value]
        if len(vals) == 3:
            vals.append(1.0)
        if len(vals) != 4:
            return default
        # a 0-255 tuple is also accepted
        if any(v > 1.0 for v in vals):
            vals = [v / 255.0 for v in vals]
        return (vals[0], vals[1], vals[2], vals[3])
    s = str(value).strip().lstrip("#")
    if s.lower() in ("", "none", "transparent"):
        return default
    if len(s) == 3:
        s = "".join(c + c for c in s)
    if len(s) in (6, 8):
        try:
            r = int(s[0:2], 16) / 255.0
            g = int(s[2:4], 16) / 255.0
            b = int(s[4:6], 16) / 255.0
            a = int(s[6:8], 16) / 255.0 if len(s) == 8 else 1.0
            return (r, g, b, a)
        except ValueError:
            return default
    if "," in s:
        parts = [p.strip() for p in s.split(",")]
        try:
            nums = [float(p) for p in parts[:4]]
        except ValueError:
            return default
        while len(nums) < 4:
            nums.append(1.0)
        if any(n > 1.0 for n in nums[:3]):
            nums = [n / 255.0 for n in nums]
        return (nums[0], nums[1], nums[2], nums[3])
    return default


def color_to_hex(rgba: Sequence[float]) -> str:
    vals = [max(0, min(255, int(round(float(v) * 255)))) for v in list(rgba)[:4]]
    while len(vals) < 4:
        vals.append(255)
    return "#%02x%02x%02x%02x" % tuple(vals)  # noqa: E501


# --------------------------------------------------------------------- style


@dataclass
class Padding:
    """left, top, right, bottom — in virtual pixels."""

    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0

    @classmethod
    def coerce(cls, value: Any) -> "Padding":
        if value is None:
            return cls()
        if isinstance(value, Padding):
            return value
        if isinstance(value, dict):
            return cls(float(value.get("left", 0)), float(value.get("top", 0)),
                       float(value.get("right", 0)), float(value.get("bottom", 0)))
        seq = list(value)  # type: ignore[arg-type]
        if len(seq) == 1:
            return cls(float(seq[0]), float(seq[0]), float(seq[0]), float(seq[0]))
        if len(seq) == 2:
            return cls(float(seq[0]), float(seq[1]), float(seq[0]), float(seq[1]))
        if len(seq) == 4:
            return cls(*(float(v) for v in seq))
        raise ValueError(f"padding needs 1, 2 or 4 values, got {value!r}")

    def to_list(self) -> List[float]:
        return [self.left, self.top, self.right, self.bottom]


@dataclass
class Style:
    """A bag of optional visual properties; `None` means 'inherit'."""

    # geometry (virtual pixels; None = auto-size / auto-place)
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    min_width: Optional[float] = None
    min_height: Optional[float] = None
    anchor: str = "topleft"                    # placement inside the parent box
    align: Optional[str] = None                # horizontal text alignment
    vertical_align: Optional[str] = None       # top | center | bottom
    padding: Optional[Padding] = None
    margin: Optional[Padding] = None
    spacing: Optional[float] = None            # gap between children (containers)
    # typography
    font: Optional[str] = None
    font_size: Optional[float] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    underline: Optional[bool] = None
    color: Optional[Color] = None
    line_spacing: Optional[float] = None
    wrap: Optional[bool] = None
    outline: Optional[Color] = None
    outline_width: Optional[float] = None
    shadow: Optional[Color] = None
    shadow_offset: Optional[Tuple[float, float]] = None
    # box
    background: Optional[Color] = None
    border_color: Optional[Color] = None
    border_width: Optional[float] = None
    radius: Optional[float] = None
    opacity: Optional[float] = None
    # interaction states
    hover_background: Optional[Color] = None
    hover_color: Optional[Color] = None
    selected_background: Optional[Color] = None
    selected_color: Optional[Color] = None
    disabled_color: Optional[Color] = None
    # misc
    zorder: Optional[int] = None
    visible: Optional[bool] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    # ---------------------------------------------------------------- merge
    def merge(self, other: Optional["Style"], _in_place: bool = False) -> "Style":
        """Return a copy where every `None` field is filled from `other`."""
        if other is None:
            return self if _in_place else _copy_style(self)
        target = self if _in_place else _copy_style(self)
        for f in dataclass_fields(Style):
            name = f.name
            value = getattr(target, name)
            if value is None:
                setattr(target, name, getattr(other, name))
            elif name == "extra":
                merged = dict(getattr(other, name) or {})
                merged.update(value or {})
                setattr(target, name, merged)
        return target

    def override(self, **props: Any) -> "Style":
        out = _copy_style(self)
        for key, value in props.items():
            if not hasattr(out, key):
                out.extra[key] = value
            else:
                if key in ("color", "background", "hover_color", "hover_background",
                           "selected_color", "selected_background", "disabled_color",
                           "outline", "shadow"):
                    value = parse_color(value)
                if key in ("padding", "margin"):
                    value = Padding.coerce(value)
                setattr(out, key, value)
        return out

    def for_state(self, state: Optional[str]) -> "Style":
        """Apply hover/selected/disabled colours for an interaction state."""
        if not state:
            return self
        out = _copy_style(self)
        if state == "hover":
            if self.hover_background is not None:
                out.background = self.hover_background
            if self.hover_color is not None:
                out.color = self.hover_color
        elif state in ("selected", "focus", "active"):
            if self.selected_background is not None:
                out.background = self.selected_background
            if self.selected_color is not None:
                out.color = self.selected_color
        elif state == "disabled" and self.disabled_color is not None:
            out.color = self.disabled_color
        return out

    # ---------------------------------------------------------------- io
    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for f in dataclass_fields(Style):
            value = getattr(self, f.name)
            if value is None:
                continue
            if isinstance(value, Padding):
                out[f.name] = value.to_list()
            elif isinstance(value, tuple):
                out[f.name] = list(value)
            else:
                out[f.name] = value
        return out

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "Style":
        data = dict(data or {})
        color_keys = ("color", "background", "hover_color", "hover_background",
                      "selected_color", "selected_background", "disabled_color",
                      "outline", "shadow")
        for key in color_keys:
            if key in data:
                data[key] = parse_color(data[key])
        for key in ("padding", "margin"):
            if key in data:
                data[key] = Padding.coerce(data[key])
        known = {f.name for f in dataclass_fields(cls)}
        extra = {k: v for k, v in data.items() if k not in known}
        kwargs = {k: v for k, v in data.items() if k in known and k != "extra"}
        style = cls(**kwargs)
        style.extra.update(data.get("extra") or {})
        style.extra.update(extra)
        return style


def _copy_style(style: Style) -> Style:
    out = Style(**{f.name: getattr(style, f.name) for f in dataclass_fields(Style)})
    out.extra = dict(style.extra or {})
    return out


# --------------------------------------------------------------------- theme

# Ren'Py's own default template values (gui.rpy) — the reference look.
_RENPY_DEFAULT_METRICS: Dict[str, float] = {
    "textbox_height": 278.0,
    "textbox_yalign": 1.0,
    "name_xpos": 155.0,
    "name_ypos": 0.0,                     # from the top of the textbox band
    "text_xpos": 155.0,
    "text_width": 1110.0,
    "choice_button_width": 1185.0,
    "choice_button_height": 52.0,
    "choice_spacing": 33.0,
    "choice_xpos": 0.5,
    "choice_ypos": 405.0,
    "margin_left": 60.0,
    "margin_right": 60.0,
    "margin_top": 60.0,
    "margin_bottom": 60.0,
}


@dataclass
class Theme:
    """A complete, serialisable look-and-feel for the UPVN UI."""

    name: str = "renpy-default"
    width: float = 1280.0
    height: float = 720.0
    palette: Dict[str, Optional[Color]] = field(default_factory=dict)
    fonts: Dict[str, str] = field(default_factory=dict)
    sizes: Dict[str, float] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)
    styles: Dict[str, Style] = field(default_factory=dict)

    # ------------------------------------------------------------- lookups
    def color(self, name: str, default: Any = "#ffffff") -> Optional[Color]:
        value = self.palette.get(name)
        return parse_color(value, parse_color(default))

    def font(self, role: str, default: Optional[str] = None) -> Optional[str]:
        return self.fonts.get(role, self.fonts.get("text", default))

    def size(self, role: str, default: float = 24.0) -> float:
        return float(self.sizes.get(role, default))

    def metric(self, name: str, default: float = 0.0) -> float:
        return float(self.metrics.get(name, default))

    # -------------------------------------------------------------- styles
    def style(self, key: str, base: Optional[Style] = None) -> Style:
        """Resolve `family[.role][:state]` against the theme cascade."""
        chain: List[Style] = []
        if base is not None:
            chain.append(base)
        default_style = self.styles.get("default")
        if default_style is not None:
            chain.append(default_style)
        family = key.split(":", 1)[0]
        parts = family.split(".")
        for i in range(len(parts)):
            sub = ".".join(parts[: i + 1])
            s = self.styles.get(sub)
            if s is not None:
                chain.append(s)
        state_style = self.styles.get(key) if ":" in key else None
        if state_style is not None:
            chain.append(state_style)
        out = Style()
        for s in chain:
            out = out.merge(s)
        return out

    # ------------------------------------------------------------------ io
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "palette": {k: (color_to_hex(v) if v else None) for k, v in self.palette.items()},
            "fonts": dict(self.fonts),
            "sizes": dict(self.sizes),
            "metrics": dict(self.metrics),
            "styles": {k: v.to_dict() for k, v in self.styles.items()},
        }

    def save(self, path) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=False), encoding="utf-8")
        return str(p)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Theme":
        data = dict(data or {})
        styles = {k: Style.from_dict(v) for k, v in (data.get("styles") or {}).items()}
        palette = {k: parse_color(v) for k, v in (data.get("palette") or {}).items()}
        return cls(
            name=data.get("name", "custom"),
            width=float(data.get("width", 1280.0)),
            height=float(data.get("height", 720.0)),
            palette=palette,
            fonts=dict(data.get("fonts") or {}),
            sizes={k: float(v) for k, v in (data.get("sizes") or {}).items()},
            metrics={k: float(v) for k, v in (data.get("metrics") or {}).items()},
            styles=styles,
        )

    @classmethod
    def load(cls, path) -> "Theme":
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        theme = cls.from_dict(data)
        return theme

    # ------------------------------------------------------- Ren'Py import
    @classmethod
    def from_renpy(cls, cfg: Dict[str, Any], name: str = "converted") -> "Theme":
        """Build a theme from parsed Ren'Py gui values.

        `cfg` is either the dict produced by `engine.render.gui_parser`
        (`{"colors": {...}, "fonts": {...}, "sizes": {...}, "world": {...}}`)
        or a raw `{gui.<name>: value}` mapping.
        """
        colors = dict(cfg.get("colors") or {})
        fonts = dict(cfg.get("fonts") or {})
        sizes = {k: float(v) for k, v in (cfg.get("sizes") or {}).items()}
        world = dict(cfg.get("world") or {})
        raw = dict(cfg.get("raw") or {})
        width = float(raw.get("config.screen_width") or cfg.get("width") or 1280.0)
        height = float(raw.get("config.screen_height") or cfg.get("height") or 720.0)

        text_color = parse_color(colors.get("text"), (1, 1, 1, 1))
        accent = parse_color(colors.get("accent"), (0.78, 0.50, 0.50, 1))
        idle = parse_color(colors.get("choice_idle"), (1, 1, 1, 1))
        hover = parse_color(colors.get("choice_hover"), (0.0, 0.094, 0.616, 1))
        # Ren'Py's default textbox is a dark translucent band; BGE drops alpha
        # so the box is opaque.  Keep light text readable on it.
        lum = sum(text_color[:3]) / 3.0 if text_color else 1.0
        box = parse_color(colors.get("dialogue_box"),
                          (0.07, 0.08, 0.10, 1.0) if lum > 0.5 else (1.0, 1.0, 1.0, 1.0))

        metrics = dict(_RENPY_DEFAULT_METRICS)
        for key, value in (cfg.get("metrics") or {}).items():
            try:
                metrics[key] = float(value)
            except (TypeError, ValueError):
                continue
        # gui.rpy raw values win when present
        _map_raw_metrics(raw, metrics, height)

        theme = cls(
            name=name,
            width=width,
            height=height,
            palette={
                "text": text_color,
                "accent": accent,
                "panel": box,
                "choice_idle": idle,
                "choice_hover": hover,
                "choice_text_idle": parse_color(colors.get("choice_idle_text"), (0.12, 0.13, 0.15, 1.0)),
                "choice_text_hover": parse_color(colors.get("choice_hover_text"), (1, 1, 1, 1)),
                "caret": text_color,
                "muted": parse_color(colors.get("muted"), (0.6, 0.6, 0.65, 1.0)),
            },
            fonts={
                "text": fonts.get("text") or "DejaVuSans.ttf",
                "name": fonts.get("name") or fonts.get("text") or "DejaVuSans.ttf",
                "interface": fonts.get("interface") or fonts.get("text") or "DejaVuSans.ttf",
                "choice": fonts.get("choice") or fonts.get("interface") or fonts.get("text") or "DejaVuSans.ttf",
            },
            sizes={
                "text": sizes.get("text", 28.0),
                "name": sizes.get("name", 34.0),
                "interface": sizes.get("interface", 26.0),
                "choice": sizes.get("choice", sizes.get("interface", 26.0)),
                "history": sizes.get("history", 24.0),
            },
            metrics=metrics,
        )
        theme.styles = _default_styles(theme)
        # world-space hints produced by the converter (optional, BGE backend only)
        if world:
            theme.metrics.update({f"world.{k}": float(v)
                                  for k, v in world.items()
                                  if isinstance(v, (int, float))})
        return theme


def _map_raw_metrics(raw: Dict[str, Any], metrics: Dict[str, float], height: float) -> None:
    """Copy `gui.xxx` values from a raw gui.rpy mapping into theme metrics."""
    simple = {
        "gui.textbox_height": "textbox_height",
        "gui.text_xpos": "text_xpos",
        "gui.text_width": "text_width",
        "gui.name_xpos": "name_xpos",
        "gui.name_ypos": "name_ypos",
        "gui.dialogue_xpos": "text_xpos",
        "gui.dialogue_width": "text_width",
        "gui.choice_button_width": "choice_button_width",
        "gui.choice_button_height": "choice_button_height",
        "gui.choice_spacing": "choice_spacing",
        "gui.choice_ypos": "choice_ypos",
    }
    for src, dst in simple.items():
        value = raw.get(src)
        try:
            metrics[dst] = float(value)
        except (TypeError, ValueError):
            continue
    # Ren'Py writes name_ypos in *gui* space measured from the top of the
    # window; keep it verbatim so a converted project reproduces its own
    # geometry, but clamp it into the virtual canvas so nothing lands offscreen.
    nyp = metrics.get("name_ypos")
    if nyp is not None:
        metrics["name_ypos"] = float(min(float(nyp), height + 400.0))


def _default_styles(theme: "Theme") -> Dict[str, Style]:
    """Ren'Py-like defaults expressed in the theme's virtual pixels."""
    w, h = theme.width, theme.height
    box_h = theme.metric("textbox_height", 278.0)
    text_color = theme.color("text")
    accent = theme.color("accent")
    pad = Padding(24.0, 12.0, 24.0, 12.0)
    return {
        "default": Style(
            font=theme.font("text"),
            font_size=theme.size("text"),
            color=text_color,
            align="left",
            vertical_align="top",
            line_spacing=1.15,
            wrap=True,
            padding=Padding(),
            margin=Padding(),
            spacing=0.0,
            opacity=1.0,
            visible=True,
        ),
        "panel": Style(background=None, padding=Padding(), radius=0.0),
        "panel.textbox": Style(
            x=0.0, y=h - box_h, width=w, height=box_h,
            background=theme.color("panel"),
            padding=Padding(theme.metric("margin_left", 60.0), 30.0,
                            theme.metric("margin_right", 60.0), 30.0),
        ),
        "panel.overlay": Style(
            x=0.0, y=0.0, width=w, height=h,
            background=(0.02, 0.02, 0.04, 0.88),
            padding=Padding(60.0, 60.0, 60.0, 60.0),
        ),
        "panel.frame": Style(background=(0.05, 0.06, 0.09, 0.92), padding=pad,
                             border_color=(0.3, 0.32, 0.38, 1.0), border_width=2.0),
        # ---- labels
        "label": Style(background=None),
        "label.speaker": Style(
            font=theme.font("name"),
            font_size=theme.size("name"),
            color=accent,
            bold=True,
            x=theme.metric("name_xpos", 155.0),
            y=(h - box_h) + 40.0,
        ),
        "label.dialogue": Style(
            font=theme.font("text"),
            font_size=theme.size("text"),
            color=text_color,
            x=theme.metric("text_xpos", 155.0),
            y=(h - box_h) + 100.0,
            width=theme.metric("text_width", 1110.0),
        ),
        "label.caption": Style(font_size=theme.size("text"), color=text_color, bold=True),
        "label.prompt": Style(
            font=theme.font("interface"),
            font_size=theme.size("interface"),
            color=text_color,
            align="center",
            vertical_align="center",
        ),
        "label.hint": Style(font_size=theme.size("interface") * 0.8,
                            color=theme.color("muted"), align="center"),
        "label.history": Style(font=theme.font("text"), font_size=theme.size("history"),
                               color=text_color),
        "label.rewind": Style(font=theme.font("interface"),
                              font_size=theme.size("interface") * 0.72,
                              color=theme.color("muted"), italic=True),
        # ---- buttons
        "button": Style(
            background=theme.color("choice_idle"),
            color=theme.color("choice_text_idle"),
            hover_background=theme.color("choice_hover"),
            hover_color=theme.color("choice_text_hover"),
            font=theme.font("choice"),
            font_size=theme.size("choice"),
            align="center",
            vertical_align="center",
            padding=Padding(24.0, 8.0, 24.0, 8.0),
            height=theme.metric("choice_button_height", 52.0),
            width=theme.metric("choice_button_width", 1185.0),
        ),
        "button.choice": Style(align="center"),
        "button.quick": Style(
            width=None, height=44.0,
            background=(0.12, 0.13, 0.16, 0.85),
            color=theme.color("text"),
            hover_background=theme.color("choice_hover"),
        ),
        # ---- text input
        "input": Style(
            font=theme.font("interface"),
            font_size=theme.size("interface"),
            color=text_color,
            background=(0.10, 0.11, 0.14, 1.0),
            border_color=(0.45, 0.47, 0.55, 1.0),
            border_width=2.0,
            align="left",
            vertical_align="center",
            padding=Padding(18.0, 10.0, 18.0, 10.0),
            width=max(420.0, w * 0.42),
            height=max(56.0, theme.size("interface") * 2.0),
        ),
        "input.caret": Style(color=theme.color("caret"), width=3.0),
        # ---- images / bars
        "image": Style(background=None, align="center", vertical_align="center"),
        "bar": Style(background=(0.15, 0.16, 0.2, 1.0), height=18.0, radius=4.0),
        "bar.fill": Style(background=accent, height=18.0, radius=4.0),
        # ---- containers
        "vbox": Style(spacing=theme.metric("choice_spacing", 33.0), background=None),
        "hbox": Style(spacing=24.0, background=None),
    }


# ------------------------------------------------------------------ registry

_THEMES: Dict[str, Theme] = {}
_DEFAULT_THEME_NAME: Optional[str] = None


def register_theme(theme: Theme, default: bool = False) -> Theme:
    _THEMES[theme.name] = theme
    global _DEFAULT_THEME_NAME
    if default or _DEFAULT_THEME_NAME is None:
        _DEFAULT_THEME_NAME = theme.name
    return theme


def get_theme(name: Optional[str] = None) -> Theme:
    if name and name in _THEMES:
        return _THEMES[name]
    if _DEFAULT_THEME_NAME and _DEFAULT_THEME_NAME in _THEMES:
        return _THEMES[_DEFAULT_THEME_NAME]
    return register_theme(make_renpy_default_theme(), default=True)


def set_default_theme(name: str) -> Theme:
    if name not in _THEMES:
        raise KeyError(f"theme {name!r} is not registered (have: {sorted(_THEMES)})")
    global _DEFAULT_THEME_NAME
    _DEFAULT_THEME_NAME = name
    return _THEMES[name]


def list_themes() -> List[str]:
    return sorted(_THEMES)


def clear_themes() -> None:
    _THEMES.clear()
    global _DEFAULT_THEME_NAME
    _DEFAULT_THEME_NAME = None


def make_renpy_default_theme() -> Theme:
    """The reference look: Ren'Py's stock template at 1280x720."""
    theme = Theme(name="renpy-default")
    theme.styles = _default_styles(theme)
    return theme


register_theme(make_renpy_default_theme(), default=True)
