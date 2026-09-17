"""
Ren'Py GUI parser — extracts UI metrics from any Ren'Py project's gui.rpy

This makes UPVN adaptive to ANY Ren'Py project, not just LearnToCodeRPG.
Instead of hardcoding LearnToCodeRPG values in contract.py, we parse the
source project's gui.rpy at conversion time and generate a JSON config that
the runtime loads.

Supported gui.* variables:
- Colors: accent_color, text_color, interface_text_color, idle_color, hover_color
- Fonts: text_font, name_text_font, interface_text_font, choice_button_text_font
- Sizes: text_size, name_text_size, interface_text_size
- Dialogue: textbox_height, textbox_yalign, name_xpos, name_ypos, dialogue_xpos, dialogue_ypos, dialogue_width
- Choice: choice_button_width, choice_button_height, choice_spacing, choice_button_borders
- File slots, etc.
- Game resolution: gui.init(width, height)

The parser is regex-based (no Ren'Py execution needed) — robust to any project.
"""
from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any, Dict, Optional


# Regex patterns for gui.* defines
# Handles: define gui.var = value  or  define gui.var = u'value'  etc.
# NOTE: We deliberately do NOT strip # comments in the regex, because # inside
# quoted colors like '#002ead' would be mistaken for a comment. Instead we
# capture the whole tail and strip comments respecting quotes in parse_renpy_gui.
DEFINE_RE = re.compile(
    r"""^\s*define\s+gui\.(?P<key>\w+)\s*=\s*(?P<val>.+)\s*$""",
    re.MULTILINE
)

INIT_RE = re.compile(
    r"""gui\.init\(\s*(?P<w>\d+)\s*,\s*(?P<h>\d+)\s*\)""",
    re.MULTILINE
)

# For config.thumbnail_width etc.
CONFIG_RE = re.compile(
    r"""^\s*define\s+config\.(?P<key>\w+)\s*=\s*(?P<val>.+)\s*$""",
    re.MULTILINE
)


def _clean_value(raw: str) -> Any:
    """Parse a Ren'Py literal into Python value."""
    raw = raw.strip()
    # Remove trailing comments already handled, but strip again
    # Handle unicode prefix u'...'
    if raw.startswith("u'") or raw.startswith('u"'):
        raw = raw[1:]
    # Handle string
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        # Strip quotes and unescape simple
        inner = raw[1:-1]
        return inner
    # Handle Borders(...)
    if raw.startswith("Borders("):
        # Extract numbers inside
        m = re.search(r"Borders\(([^)]+)\)", raw)
        if m:
            parts = [p.strip() for p in m.group(1).split(",")]
            try:
                return tuple(int(float(p)) for p in parts)
            except Exception:
                return raw
        return raw
    # Handle None
    if raw == "None":
        return None
    # Handle True/False
    if raw == "True":
        return True
    if raw == "False":
        return False
    # Handle numbers
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except Exception:
        pass
    # Handle references like gui.accent_color, gui.text_font etc.
    # Return as string reference to be resolved later
    if raw.startswith("gui."):
        return raw  # keep as reference
    # Fallback: raw string
    return raw


def parse_renpy_gui(rpy_path: Path | str) -> Dict[str, Any]:
    """
    Parse a Ren'Py gui.rpy file and return dict of gui.* values.
    
    Accepts either a file path or raw gui.rpy text content (for testing).
    Example:
        {
            "init": (1920, 1080),
            "accent_color": "#002ead",
            "text_color": "#404040",
            "text_font": "fonts/lato/Lato-Regular.ttf",
            ...
        }
    """
    # Support raw content string (contains newline or 'define gui')
    if isinstance(rpy_path, str) and ("\n" in rpy_path or "define gui" in rpy_path):
        text = rpy_path
    else:
        path = Path(rpy_path)
        if not path.exists():
            return {}
        text = path.read_text(encoding="utf-8", errors="ignore")
    result: Dict[str, Any] = {}
    
    # Parse gui.init
    m = INIT_RE.search(text)
    if m:
        try:
            result["init"] = (int(m.group("w")), int(m.group("h")))
        except Exception:
            pass
    
    # Parse define gui.*
    for match in DEFINE_RE.finditer(text):
        key = match.group("key")
        raw_val = match.group("val").strip()
        # Remove any trailing comment inside raw_val that wasn't caught
        # Split on # but be careful with colors containing #
        # Colors are like '#002ead' inside quotes, so # inside quotes is not comment
        # Our regex already handles # at end, but let's clean again
        # If raw_val contains # outside quotes, strip it
        # Simple heuristic: if # appears and raw_val doesn't start with u'#' or "#, treat as comment
        if "#" in raw_val:
            # Check if # is inside quotes
            in_single = False
            in_double = False
            cleaned = []
            for i, ch in enumerate(raw_val):
                if ch == "'" and not in_double:
                    in_single = not in_single
                elif ch == '"' and not in_single:
                    in_double = not in_double
                elif ch == "#" and not in_single and not in_double:
                    break
                cleaned.append(ch)
            raw_val = "".join(cleaned).strip()
        
        val = _clean_value(raw_val)
        result[key] = val
    
    # Parse config.* for thumbnail etc.
    for match in CONFIG_RE.finditer(text):
        key = match.group("key")
        raw_val = match.group("val").strip()
        result[f"config_{key}"] = _clean_value(raw_val)
    
    # Resolve references like gui.accent_color -> actual value
    # Do a simple pass: if value is "gui.xxx", replace with result[xxx] if exists
    for k, v in list(result.items()):
        if isinstance(v, str) and v.startswith("gui."):
            ref_key = v[4:]  # strip gui.
            if ref_key in result and not isinstance(result[ref_key], str) or (isinstance(result[ref_key], str) and not result[ref_key].startswith("gui.")):
                result[k] = result[ref_key]
            # else keep as is, will be resolved later or left as reference
    
    # Second pass for any remaining gui. references
    for k, v in list(result.items()):
        if isinstance(v, str) and v.startswith("gui."):
            ref_key = v[4:]
            if ref_key in result:
                result[k] = result[ref_key]
    
    return result


def gui_to_upvn_config(gui_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert parsed Ren'Py gui dict to UPVN adaptive config.
    
    This is the bridge that makes UPVN work with ANY Ren'Py project.
    It normalizes Ren'Py's 1920x1080 pixel metrics into UPVN's ortho 15 world space,
    and extracts colors, fonts, sizes.
    
    Returns UPVN config dict that can be saved as JSON and loaded at runtime.
    """
    # Default resolution
    init_w, init_h = gui_dict.get("init", (1920, 1080))
    if isinstance(init_w, tuple):
        init_w, init_h = init_w
    
    # Colors with fallbacks to GENERIC Ren'Py template defaults (not a specific game)
    # These are intentionally NOT LearnToCodeRPG values — generic template uses pinkish accent
    accent = gui_dict.get("accent_color", "#ff7f7f")
    text_color = gui_dict.get("text_color", "#ffffff")
    interface_text_color = gui_dict.get("interface_text_color", text_color)
    idle_color = gui_dict.get("idle_color", "#888888")
    hover_color = gui_dict.get("hover_color", accent)
    choice_idle = gui_dict.get("choice_button_text_idle_color", "#888888")
    choice_hover = gui_dict.get("choice_button_text_hover_color", "#ffffff")
    
    # Fonts — generic fallback DejaVu, but real project provides its own
    text_font = gui_dict.get("text_font", "DejaVuSans.ttf")
    name_font = gui_dict.get("name_text_font", text_font)
    interface_font = gui_dict.get("interface_text_font", text_font)
    choice_font = gui_dict.get("choice_button_text_font", text_font)
    
    # Sizes — generic Ren'Py defaults
    text_size = gui_dict.get("text_size", 33)
    name_size = gui_dict.get("name_text_size", 45)
    interface_size = gui_dict.get("interface_text_size", 33)
    
    # Dialogue — generic Ren'Py template defaults (185 height, etc.), NOT LTCR's 278
    textbox_height = gui_dict.get("textbox_height", 185)
    textbox_yalign = gui_dict.get("textbox_yalign", 1.0)
    name_xpos = gui_dict.get("name_xpos", 240)
    name_ypos = gui_dict.get("name_ypos", 0)
    dialogue_xpos = gui_dict.get("dialogue_xpos", 268)
    dialogue_ypos = gui_dict.get("dialogue_ypos", 50)
    dialogue_width = gui_dict.get("dialogue_width", 744)
    
    # Choice — generic defaults
    choice_width = gui_dict.get("choice_button_width", 790)
    choice_height = gui_dict.get("choice_button_height")  # None means auto
    choice_spacing = gui_dict.get("choice_spacing", 22)
    choice_borders = gui_dict.get("choice_button_borders", (150, 8, 150, 8))
    
    # Build UPVN config
    config = {
        "source": "renpy_gui",
        "resolution": {"width": init_w, "height": init_h},
        "colors": {
            "accent": accent,
            "text": text_color,
            "interface_text": interface_text_color,
            "idle": idle_color,
            "hover": hover_color,
            "choice_idle": choice_idle,
            "choice_hover": choice_hover,
            "dialogue_box": gui_dict.get("dialogue_box_color", "#ffffff"),
        },
        "fonts": {
            "text": text_font,
            "name": name_font,
            "interface": interface_font,
            "choice": choice_font,
        },
        "sizes": {
            "text": text_size,
            "name": name_size,
            "interface": interface_size,
        },
        "dialogue": {
            "textbox_height": textbox_height,
            "textbox_yalign": textbox_yalign,
            "name_xpos": name_xpos,
            "name_ypos": name_ypos,
            "dialogue_xpos": dialogue_xpos,
            "dialogue_ypos": dialogue_ypos,
            "dialogue_width": dialogue_width,
        },
        "choice": {
            "button_width": choice_width,
            "button_height": choice_height,
            "spacing": choice_spacing,
            "borders": choice_borders,
        },
        # Raw gui dict for debugging
        "raw": gui_dict,
    }
    
    # Compute UPVN world-space metrics (ortho 15)
    # These are derived, not stored, but useful for contract.py
    # total visible height = ortho 15 * (720/1280) = 8.4375 for 16:9, but use actual aspect from resolution
    # For simplicity, use 1920x1080 aspect = 16:9, height = 15 * (1080/1920) = 8.4375
    # Actually ortho_scale is width, height = width * (h/w)
    aspect = init_h / init_w if init_w else 9/16
    ortho = 15.0
    total_h = ortho * aspect
    half_v = total_h / 2
    
    # Textbox: height in pixels → world units
    textbox_h_world = (textbox_height / init_h) * total_h if init_h else 2.168
    # yalign 1.0 = bottom, so center = -half_v + textbox_h_world/2
    dialogue_z = -half_v + textbox_h_world / 2
    # For yalign 0.0 top, 0.5 center, 1.0 bottom
    if textbox_yalign == 1.0:
        dialogue_z = -half_v + textbox_h_world / 2
    elif textbox_yalign == 0.0:
        dialogue_z = half_v - textbox_h_world / 2
    else:
        dialogue_z = 0  # center
    
    # Name/dialogue xpos: pixels from left → world X
    # Left edge = -ortho/2 = -7.5, right = +7.5
    # xpos 450px from left → world X = -7.5 + (450/1920)*15
    name_x_world = -ortho/2 + (name_xpos / init_w) * ortho if init_w else -3.99
    dialogue_x_world = -ortho/2 + (dialogue_xpos / init_w) * ortho if init_w else -3.99
    
    # ypos inside textbox: 12px from top of textbox
    # Top of textbox = dialogue_z + textbox_h_world/2
    # name_y = top - (12/1080)*total_h - small offset
    name_y_offset = (name_ypos / init_h) * total_h if init_h else 0.093
    dialogue_y_offset = (dialogue_ypos / init_h) * total_h if init_h else 0.585
    
    # Compute final world positions
    # These match the hardcoded LearnToCodeRPG values when that project is parsed
    config["world"] = {
        "ortho": ortho,
        "total_h": total_h,
        "half_v": half_v,
        "dialogue_location": [0.0, -2.0, dialogue_z],
        "dialogue_scale": [ortho/2, textbox_h_world/2, 1.0],
        "speaker_location": [name_x_world, -3.0, dialogue_z + textbox_h_world/2 - name_y_offset - 0.1],
        "dialogue_text_location": [dialogue_x_world, -4.0, dialogue_z + textbox_h_world/2 - dialogue_y_offset - 0.1],
        "choice_width_factor": (choice_width / init_w) if init_w else 0.617,
        "choice_height_factor": 0.048,  # 52px default, computed below if height given
        "choice_spacing_em": 0.38,  # will be computed from spacing
    }
    
    # Choice height: if given, convert, else default 52px
    if choice_height:
        ch_h_world = (choice_height / init_h) * total_h
        config["world"]["choice_height_factor"] = ch_h_world / half_v / 2  # approximate
    else:
        # Default 52px for 1080p
        config["world"]["choice_height_factor"] = (52 / init_h) * total_h / half_v if init_h else 0.048
    
    # Choice spacing: 33px → world
    spacing_world = (choice_spacing / init_h) * total_h if init_h else 0.257
    config["world"]["choice_spacing_em"] = spacing_world / 0.68  # normalize to em like old code
    
    # Choice ypos: from top of screen → world Z (stock screens.rpy hardcodes
    # `ypos 270` on the 1280x720 frame = 0.375 from top; 405/1080 is the same
    # ratio at 1080p — default must be RATIO-based or a 720p project lands
    # the menu below center). Z = half_v - (ypos/init_h)*total_h = half_v*0.25
    choice_ypos = gui_dict.get("choice_ypos", 0.375 * init_h)
    if isinstance(choice_ypos, (int, float)):
        choice_z = half_v - (choice_ypos / init_h) * total_h if init_h else half_v * 0.25
    else:
        choice_z = half_v * 0.25
    config["world"]["choice_base_z"] = choice_z
    
    return config


def save_upvn_gui_config(config: Dict[str, Any], out_path: Path | str):
    """Save UPVN gui config as JSON."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_upvn_gui_config(config_path: Path | str) -> Optional[Dict[str, Any]]:
    """Load UPVN gui config from JSON."""
    path = Path(config_path)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def find_and_parse_gui(project_root: Path | str) -> Dict[str, Any]:
    """
    Find gui.rpy in a Ren'Py project and parse it.
    
    Search order:
    - <project_root>/game/gui.rpy
    - <project_root>/gui.rpy
    - <project_root>/game/gui/*.rpy (first found)
    """
    root = Path(project_root)
    candidates = [
        root / "game" / "gui.rpy",
        root / "gui.rpy",
        root / "game" / "gui.rpy",
    ]
    # Also check for any gui.rpy in game/
    for p in root.rglob("gui.rpy"):
        if p not in candidates:
            candidates.append(p)
    
    for cand in candidates:
        if cand.exists():
            parsed = parse_renpy_gui(cand)
            if parsed:
                return gui_to_upvn_config(parsed)
    
    # Fallback: generic Ren'Py defaults
    return gui_to_upvn_config({})
