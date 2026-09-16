"""
UPVN GUI Config — adaptive to any Ren'Py project.

Instead of hardcoding LearnToCodeRPG values in contract.py, this module:
1. At conversion time: parses Ren'Py gui.rpy → upvn_gui.json
2. At runtime: loads upvn_gui.json (or gui.rpy if present) and provides
   dynamic values for contract.py and world_ui.py

This makes UPVN work with ANY Ren'Py project, not just one hardcoded game.

Usage:
    from engine.render.gui_config import get_gui_config, get_world_metrics
    
    config = get_gui_config()  # loads from disk or uses defaults
    world = get_world_metrics()  # returns dialogue_location, etc.

The config search order:
1. ./game/upvn_gui.json (converted project)
2. ./assets/gui_config.json
3. ./upvn_gui.json
4. ./game/gui.rpy (parse directly if JSON not found)
5. Fallback to generic defaults
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .gui_parser import parse_renpy_gui, gui_to_upvn_config, load_upvn_gui_config


# Generic Ren'Py defaults (not LearnToCodeRPG specific)
# These are Ren'Py's default template values, not a specific game
GENERIC_DEFAULTS = {
    "init": (1920, 1080),
    "accent_color": "#ff7f7f",  # Ren'Py default pinkish
    "text_color": "#ffffff",
    "interface_text_color": "#ffffff",
    "idle_color": "#888888",
    "hover_color": "#ff7f7f",
    "text_font": "DejaVuSans.ttf",
    "name_text_font": "DejaVuSans.ttf",
    "interface_text_font": "DejaVuSans.ttf",
    "text_size": 33,
    "name_text_size": 45,
    "interface_text_size": 33,
    "textbox_height": 185,  # Ren'Py default
    "textbox_yalign": 1.0,
    "name_xpos": 240,
    "name_ypos": 0,
    "dialogue_xpos": 268,
    "dialogue_ypos": 50,
    "dialogue_width": 744,
    "choice_button_width": 790,
    "choice_button_height": None,
    "choice_spacing": 22,
}


_cached_config: Optional[Dict[str, Any]] = None
_cached_path: Optional[Path] = None


def _find_config_file(start: Optional[Path] = None) -> Optional[Path]:
    """Search for upvn_gui.json or gui.rpy in likely locations."""
    search_roots = []
    
    if start:
        search_roots.append(Path(start))
    
    # Current working dir and parents
    cwd = Path.cwd()
    search_roots.append(cwd)
    search_roots.append(cwd / "game")
    
    # File location of this module: engine/render/ -> up two levels is project root?
    here = Path(__file__).resolve()
    # engine/render/gui_config.py -> engine/render/ -> engine/ -> project root
    project_root = here.parents[2]
    search_roots.append(project_root)
    search_roots.append(project_root / "game")
    search_roots.append(project_root / "assets")
    
    # Also check for converted project structure: blend/ is sibling to game/
    # If we're in UPVN_LearnToCodeRPG/blend/, game is ../game
    for root in list(search_roots):
        search_roots.append(root.parent)
        search_roots.append(root.parent / "game")
    
    # Deduplicate
    seen = set()
    unique_roots = []
    for r in search_roots:
        try:
            rp = r.resolve()
            if rp not in seen and rp.exists():
                seen.add(rp)
                unique_roots.append(rp)
        except Exception:
            pass
    
    # Check for JSON configs first
    json_names = ["upvn_gui.json", "gui_config.json", "upvn_gui_config.json"]
    for root in unique_roots:
        for name in json_names:
            for sub in ["", "game", "assets"]:
                cand = root / sub / name if sub else root / name
                if cand.exists():
                    return cand
    
    # Check for gui.rpy
    for root in unique_roots:
        for sub in ["", "game"]:
            cand = root / sub / "gui.rpy" if sub else root / "gui.rpy"
            if cand.exists():
                return cand
    
    return None


def load_gui_config(config_path: Optional[Path | str] = None, force_reload: bool = False) -> Dict[str, Any]:
    """
    Load GUI config from disk, with caching.
    
    If config_path is None, auto-discovers upvn_gui.json or gui.rpy.
    Returns UPVN config dict (from gui_to_upvn_config).
    """
    global _cached_config, _cached_path
    
    if not force_reload and _cached_config is not None:
        return _cached_config
    
    # If explicit path given
    if config_path:
        path = Path(config_path)
        if path.exists():
            if path.suffix == ".json":
                loaded = load_upvn_gui_config(path)
                if loaded:
                    _cached_config = loaded
                    _cached_path = path
                    return loaded
            elif path.suffix == ".rpy":
                parsed = parse_renpy_gui(path)
                config = gui_to_upvn_config(parsed)
                _cached_config = config
                _cached_path = path
                return config
    
    # Auto-discover
    found = _find_config_file()
    if found:
        if found.suffix == ".json":
            loaded = load_upvn_gui_config(found)
            if loaded:
                _cached_config = loaded
                _cached_path = found
                return loaded
        elif found.suffix == ".rpy":
            parsed = parse_renpy_gui(found)
            config = gui_to_upvn_config(parsed)
            _cached_config = config
            _cached_path = found
            return config
    
    # Fallback to generic defaults
    config = gui_to_upvn_config(GENERIC_DEFAULTS)
    config["source"] = "generic_defaults"
    _cached_config = config
    _cached_path = None
    return config


def get_gui_config() -> Dict[str, Any]:
    """Get current GUI config (cached)."""
    return load_gui_config()


def get_world_metrics() -> Dict[str, Any]:
    """Get world-space metrics derived from GUI config."""
    config = get_gui_config()
    return config.get("world", {})


def get_colors() -> Dict[str, str]:
    """Get color palette from GUI config."""
    config = get_gui_config()
    return config.get("colors", {})


def get_fonts() -> Dict[str, str]:
    """Get font mapping from GUI config."""
    config = get_gui_config()
    return config.get("fonts", {})


def hex_to_rgba(hex_str: str, alpha: float = 1.0) -> Tuple[float, float, float, float]:
    """Convert #RRGGBB or #RGB to RGBA 0..1."""
    if not hex_str:
        return (1.0, 1.0, 1.0, alpha)
    s = str(hex_str).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c + c for c in s)
    if len(s) != 6:
        return (1.0, 1.0, 1.0, alpha)
    try:
        r = int(s[0:2], 16) / 255.0
        g = int(s[2:4], 16) / 255.0
        b = int(s[4:6], 16) / 255.0
        return (r, g, b, alpha)
    except Exception:
        return (1.0, 1.0, 1.0, alpha)


def clear_cache():
    """Clear cached config (for tests)."""
    global _cached_config, _cached_path
    _cached_config = None
    _cached_path = None


# Convenience: pre-parse common values for contract.py
def _get_with_fallback(config: Dict[str, Any], *keys, default=None):
    """Try multiple keys, return first found."""
    for k in keys:
        if k in config:
            return config[k]
        # Check nested
        if "." in k:
            parts = k.split(".")
            cur = config
            try:
                for p in parts:
                    cur = cur[p]
                return cur
            except Exception:
                pass
    return default
