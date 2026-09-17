"""
UPVN Blender Editor Tools — create visual novel inside Blender with minimal coding
v0.7.1 (2026-09-15): Creator Quality & No-Code Workflow — declarative builder, quick wizard, HQ scene

Why v0.6 exists
    Installing the old add-on copied this single .py into Blender's add-ons folder,
    far away from the engine/ package, so every tool button failed with a bare
    "Engine not available". v0.6 locates the engine automatically:

     1. engine_path set in Add-on Preferences (explicit, Locate Engine… button)
     2. engine/ folder next to this file  (repo layout: <repo>/blend/…, or
        extracted zip layout: <addon_dir>/engine)
     3. engine/ inside the .zip this add-on was installed from (Blender zip
        installs stay compressed — we add the archive to sys.path via zipimport)
     4. parent folders of the current .blend (repo layout when the project file
        sits inside the repo)

    It also adds a one-button **Setup Scene** operator for UPBGE that wires a
    complete playable scene (camera, planes, VNController object, logic bricks,
    path-bootstrap launcher text) so nothing can be mis-initialised by hand.

Install (two supported ways)
  A. Dist zip (recommended):
        dist/upvn_editor_addon_v0.7.1.zip  → Edit → Preferences → Add-ons →
           Install from Disk… (or Install…) → select the .zip → enable "UPVN".
     Engine, frontend and template travel inside the zip; nothing else needed.
  B. Repo checkout:
        File → Open  <repo>/blend/UPVN_Template.blend
        Edit → Preferences → Add-ons → Install… → <repo>/blend/upvn_editor_addon.py
        (or install from the zip produced by tools/package_addon.py)

Then in 3D Viewport or Text Editor sidebar (N) find tab "UPVN".

Minimal-coding workflow (no .rpy typing):
    1. Create Project → writes //game/script.rpy starter (declarative)
    2. Quick Wizard → full branching story with 2 endings, variables, 3D stage
    3. (UPBGE only) Setup Scene → wires the running scene once (HQ materials)
    4. Add Character / Variable / Scene / Dialogue / Show / Menu / If / Jump → appended to script.rpy
    5. Validate → parser, line/col + hint;  Preview → headless screenshot
    6. Export Package → playable zip
    7. Press P to play. Saves: arbitrary slots 1..∞, pagination.

Headless fallback: when bpy unavailable (CI), the module still imports and exposes
`UPVN_GameBuilder` Python API used by tools/upvn_game_creator.py and tests.
"""

bl_info = {
    "name": "UPVN — Visual Novel Editor",
    "author": "UPVN",
    "version": (0, 7, 1),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > UPVN, Text Editor > Sidebar > UPVN",
    "description": "Create Ren'Py-like visual novel inside UPBGE with minimal coding — declarative builder, quick wizard, HQ scene, no Python required",
    "category": "Game Engine",
}

# ---------------------------------------------------------------- headless-safe imports
try:
    import bpy
    HAS_BPY = True
except ImportError:
    bpy = None
    HAS_BPY = False

import os
import sys
import pathlib
import json
import textwrap
import shutil
import re
import zipfile
import ast as _ast

# --------------------------------------------------- contract names (module scope)
try:
    from engine.render.contract import TEX_NODE_NAME, MIX_NODE_NAME, WHITE_IMAGE_NAME
except Exception:                      # engine not on sys.path yet — fallback
    TEX_NODE_NAME, MIX_NODE_NAME = "UPVN Tex Image", "UPVN Tex Mix"
    WHITE_IMAGE_NAME = "UPVN_White1px"

# ---------------------------------------------------------------------------
# Engine discovery (v0.6) — finds engine/ wherever the add-on was installed from.
# ---------------------------------------------------------------------------

ENGINE_INFO = {
    "status": "unknown",        # ok | not_found | error
    "root": None,               # filesystem dir containing engine/, or zip path
    "source": None,             # 'prefs' | 'module_dir' | 'zip' | 'repo' | 'blend_file'
    "message": "",
    "searched": [],             # human list of tried candidates
}

_PREF_OVERRIDE = None           # set by Locate Engine / prefs operator


def _engine_candidates():
    """Ordered list of (kind, path_string, description) candidates to check."""
    out = []
    try:
        here = pathlib.Path(__file__).resolve().parent
    except Exception:
        here = pathlib.Path.cwd()

    # 0) explicit preference
    if _PREF_OVERRIDE and os.path.isdir(_PREF_OVERRIDE):
        out.append(("dir", os.path.abspath(_PREF_OVERRIDE), "preferences engine_path"))
    # 1) engine/ right next to this module (repo layout <root>/blend, extracted
    #    add-on folder, or copied bundle)
    out.append(("dir", str(here), "folder of this file"))
    if here.name == "blend":                      # <repo>/blend/upvn_editor_addon.py
        out.append(("dir", str(here.parent), "repo root (blend/…)"))
    else:
        out.append(("dir", str(here.parent), "parent folder"))
    # 2) installed from a .zip (Blender keeps add-on zips compressed)
    try:
        s = str(pathlib.Path(__file__))
        idx = s.find(".zip")
        if idx > 0:
            zpath = s[: idx + 4]
            if os.path.isfile(zpath):
                out.append(("zip", zpath, "add-on zip archive"))
    except Exception:
        pass
    # 3) next to the open .blend file (project lives inside a repo/checkout)
    if HAS_BPY and bpy is not None and getattr(bpy, "data", None):
        try:
            fp = getattr(bpy.data, "filepath", "") or ""
        except Exception:
            fp = ""
        if fp:
            try:
                bdir = os.path.dirname(os.path.abspath(bpy.path.abspath(fp)))
            except Exception:
                bdir = None
            if bdir:
                out.append(("dir", bdir, "blend file folder"))
                if os.path.basename(bdir) in ("blend", "blends"):
                    out.append(("dir", os.path.dirname(bdir), "blend file parent"))
    return out


def _zip_namelist_norm(path):
    """Normalised member names of a zip ('/' separators), or None."""
    try:
        with zipfile.ZipFile(path) as zf:
            return {n.replace("\\", "/") for n in zf.namelist()}
    except Exception:
        return None


def _zip_engine_member(path):
    """Member path of engine/script/parser.py inside the zip, or None."""
    names = _zip_namelist_norm(path)
    if names is None:
        return None
    if "engine/script/parser.py" in names:
        return "engine/script/parser.py"
    hits = sorted(n for n in names if n.endswith("/engine/script/parser.py"))
    return hits[0] if hits else None


def _candidate_is_engine(kind, path):
    if kind == "dir":
        return os.path.isfile(os.path.join(path, "engine", "script", "parser.py"))
    if kind == "zip":
        return _zip_engine_member(path) == "engine/script/parser.py"
    return False


def _add_to_syspath(kind, path):
    """Make `import engine…` resolve: dir root, or zip archive via zipimport."""
    if kind == "dir":
        if path not in sys.path:
            sys.path.insert(0, path)
        return True
    if kind == "zip":
        if path not in sys.path:
            sys.path.insert(0, path)
        return True
    return False


def _import_engine_api():
    """Import the engine symbols used by the builder + operators."""
    from engine.script.parser import parse_string, parse_file        # noqa: F401
    from engine.core.vn_controller import VNController               # noqa: F401
    from engine.save.save_manager import SaveManager                 # noqa: F401
    import engine.script.parser as _p
    import engine.core.vn_controller as _vc
    import engine.save.save_manager as _sm
    return _p, _vc, _sm


def ensure_engine(retry=False):
    """Locate and import the engine. Idempotent; retry=True re-scans."""
    global ENGINE_INFO, _engine_api, ENGINE_AVAILABLE
    if ENGINE_AVAILABLE and not retry:
        return True, ENGINE_INFO
    ENGINE_AVAILABLE = False
    _engine_api = None
    searched = []
    info = {"status": "not_found", "root": None, "source": None,
            "message": "", "searched": searched}
    nested_zip_hint = None
    try:
        candidates = _engine_candidates()
    except Exception as exc:
        info.update(status="error", message=f"discovery failed: {exc}")
        ENGINE_INFO = info
        return False, info
    for kind, path, desc in candidates:
        searched.append(f"{desc}: {path}")
        try:
            if kind == "zip":
                member = _zip_engine_member(path)
                if member is None:
                    continue
                if member != "engine/script/parser.py":
                    nested_zip_hint = nested_zip_hint or path
                    continue
            if not _candidate_is_engine(kind, path):
                continue
        except Exception:
            continue
        try:
            _add_to_syspath(kind, path)
            _p, _vc, _sm = _import_engine_api()
            info.update(status="ok", root=path, source=desc,
                        message=f"engine found via {desc}")
            _engine_api = (_p, _vc, _sm)
            ENGINE_AVAILABLE = True
        except Exception as exc:
            info.update(status="error", root=path, source=desc,
                        message=f"engine found at {path} but import failed: {exc}")
            ENGINE_INFO = info
            return False, info
        break
    if not ENGINE_AVAILABLE:
        if nested_zip_hint:
            info["message"] = ("engine is inside the add-on zip but not at its root — "
                               "install via Preferences → Add-ons → Install from Disk… "
                               "(extracts the folder) instead of unpacking by hand")
        else:
            info["message"] = ("no engine/ folder found — install the UPVN zip release "
                               "(bundles engine) or set the engine folder in "
                               "Preferences → Add-ons → UPVN (Locate Engine…)")
    ENGINE_INFO = info
    return ENGINE_AVAILABLE, info


# module-level symbols used by UPVN_GameBuilder / operators (bound lazily)
_engine_api = None
ENGINE_AVAILABLE = False
try:
    ensure_engine()
except Exception:
    ENGINE_AVAILABLE = False


def engine_status_line():
    """Short human line for panels/reports: '✓ Engine 0.6.x (repo root)' or ✗ …"""
    ok, info = ENGINE_AVAILABLE, ENGINE_INFO
    if ok:
        return f"Engine: OK ({info.get('source', '?')})"
    return "Engine: NOT FOUND — see console / press 'Check Engine'"


def engine_diag_text():
    """Multi-line diagnosis for operator reports + console."""
    ok, info = ENGINE_AVAILABLE, ENGINE_INFO
    lines = [f"UPVN engine status: {info['status']}"]
    if ok:
        lines.append(f"  root:   {info.get('root')}")
        lines.append(f"  source: {info.get('source')}")
    else:
        lines.append(f"  reason: {info['message']}")
        for s in info.get("searched", []):
            lines.append(f"  looked: {s}")
    return "\n".join(lines)


def engine_parser_available():
    """(parse_string, parse_file) or (None, None) once engine is bound."""
    if not ENGINE_AVAILABLE or _engine_api is None:
        return None, None
    _p, _vc, _sm = _engine_api
    return _p.parse_string, _p.parse_file


def bundle_engine_to_addon_dir():
    """Copy engine/ + bge_frontend/ next to this file so the add-on is fully self-contained."""
    if not ENGINE_AVAILABLE or ENGINE_INFO.get("root") is None:
        raise RuntimeError("engine not found — cannot bundle")
    src_root = ENGINE_INFO["root"]
    dest = pathlib.Path(__file__).resolve().parent
    if not os.access(str(dest), os.W_OK):
        raise RuntimeError(f"add-on folder not writable: {dest}")
    copied = []
    for sub in ("engine", "bge_frontend"):
        src = os.path.join(src_root, sub)
        if not os.path.isdir(src):
            continue
        dst = dest / sub
        if os.path.abspath(dst) == os.path.abspath(src):
            continue
        if dst.exists():
            shutil.rmtree(str(dst))
        shutil.copytree(src, str(dst),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        copied.append(sub)
    if not copied:
        raise RuntimeError("nothing to copy (engine already local?)")
    return f"Bundled {', '.join(copied)} into {dest} — engine now travels with the add-on."


# ---------------------------------------------------------------- Python API for minimal coding (works without bpy)
# M27: declarative-first builder — less Python, higher quality starter, reliable

def _infer_type_from_value(val_str: str):
    """Infer UPVN state type from a literal string."""
    s = val_str.strip()
    if s in ("True", "False"):
        return "bool"
    if s == "None":
        return "str"
    if s.startswith(("[", "(")):
        return "list"
    if s.startswith(('"', "'")):
        return "str"
    try:
        int(s)
        return "int"
    except Exception:
        pass
    try:
        float(s)
        return "float"
    except Exception:
        pass
    return "str"

def _format_literal_py(value):
    """Format a Python value as UPVN literal."""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, str):
        # if already quoted, keep
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            return value
        # try to detect if it's already a literal like 0 or True
        return f'"{value}"'
    if isinstance(value, list):
        return repr(value)
    return repr(value)


class UPVN_GameBuilder:
    """Headless Python API — also used by Blender operators. Generates .rpy with minimal coding.
    
    M27: declarative-first (character:, state:, set, choice). Legacy define/$ still parsed
    for backward compat, but new projects emit canonical forms. Less Python coding required.
    """

    def __init__(self, script_path: str = "game/script.rpy", use_declarative: bool = True):
        self.script_path = pathlib.Path(script_path)
        self.use_declarative = use_declarative
        self.last_error: str | None = None
        self.characters = {}  # id -> {name, color}
        self.state_vars = {}  # name -> {type, literal}
        self.images = {}  # name -> path
        self.audios = {}  # name -> path
        self.stages = {}  # name -> path
        self.labels = {"start": []}  # label -> list of lines (already indented)
        self.current_label = "start"
        self._label_indent = {"start": 4}  # current indent per label (for if/else nesting)
        self._indent_stack = {"start": [4]}  # stack per label
        self._lines = []
        self.script_path.parent.mkdir(parents=True, exist_ok=True)
        self._existing_text = None
        if self.script_path.exists():
            try:
                self._existing_text = self.script_path.read_text(encoding="utf-8")
                if ENGINE_AVAILABLE and _engine_api is not None:
                    try:
                        _p, _vc, _sm = _engine_api
                        data = _p.parse_string(self._existing_text, filename=str(self.script_path))
                        for cid, cdata in data.get("characters", {}).items():
                            self.characters[cid] = {"name": cdata["name"], "color": cdata.get("color", "#ffffff")}
                        # populate labels structure for internal use (keep existing)
                        self.labels = {}
                        self._label_indent = {}
                        self._indent_stack = {}
                        for lbl, nodes in data.get("labels", {}).items():
                            self.labels[lbl] = []
                            self._label_indent[lbl] = 4
                            self._indent_stack[lbl] = [4]
                        if "start" not in self.labels:
                            self.labels["start"] = []
                            self._label_indent["start"] = 4
                            self._indent_stack["start"] = [4]
                        # state vars from defaults + types
                        for k, v in data.get("defaults", {}).items():
                            t = data.get("types", {}).get(k, _infer_type_from_value(repr(v)))
                            self.state_vars[k] = {"type": t, "literal": repr(v)}
                        for k, t in data.get("types", {}).items():
                            if k not in self.state_vars:
                                from engine.script.literals import type_default
                                try:
                                    dv = type_default(t)
                                    self.state_vars[k] = {"type": t, "literal": repr(dv)}
                                except Exception:
                                    self.state_vars[k] = {"type": t, "literal": "0" if t=="int" else '""'}
                        # assets
                        for kind in ("images", "audio", "stages"):
                            for n, p in data.get("assets", {}).get(kind, {}).items():
                                if kind == "images":
                                    self.images[n] = p
                                elif kind == "audio":
                                    self.audios[n] = p
                                else:
                                    self.stages[n] = p
                    except Exception:
                        pass
            except Exception:
                pass

    # ---------------- indent management
    def _cur_indent(self):
        return self._label_indent.get(self.current_label, 4)

    def _push_indent(self):
        cur = self._cur_indent()
        self._label_indent[self.current_label] = cur + 4
        self._indent_stack[self.current_label].append(cur + 4)

    def _pop_indent(self):
        stack = self._indent_stack.get(self.current_label, [4])
        if len(stack) > 1:
            stack.pop()
            self._label_indent[self.current_label] = stack[-1]
        else:
            self._label_indent[self.current_label] = 4

    def _line(self, text: str, indent: int | None = None):
        ind = indent if indent is not None else self._cur_indent()
        return " " * ind + text

    def ensure_label(self, label: str):
        if label not in self.labels:
            self.labels[label] = []
            self._label_indent[label] = 4
            self._indent_stack[label] = [4]
        else:
            # M27: if label currently only has auto-placeholder, clear it so real content replaces it
            cur = self.labels[label]
            if len(cur) <= 2 and any("chosen" in c for c in cur):
                self.labels[label] = []
        self.current_label = label
        return self

    # ---------------- declarative definitions
    def add_character(self, cid: str, name: str, color: str = "#ffffff"):
        self.characters[cid] = {"name": name, "color": color}
        return self

    def add_state_var(self, name: str, type_str: str = "int", value: str = "0"):
        # normalize type
        t = type_str.strip().lower()
        if t == "string":
            t = "str"
        if t not in ("int", "float", "str", "bool", "list"):
            t = _infer_type_from_value(value)
        # ensure literal is valid
        lit = value.strip()
        # if value is python value not literal string, format
        try:
            # try ast.literal_eval to validate
            _ast.literal_eval(lit)
        except Exception:
            # if not literal, keep as is if it's already quoted or number
            pass
        self.state_vars[name] = {"type": t, "literal": lit}
        return self

    def add_image(self, name: str, path: str):
        self.images[name] = path
        return self

    def add_audio(self, name: str, path: str):
        self.audios[name] = path
        return self

    def add_stage_asset(self, name: str, path: str):
        self.stages[name] = path
        return self

    # ---------------- scene / show / dialogue
    def add_scene(self, bg: str, transition: str | None = None):
        line = self._line(f"scene {bg}" + (f" with {transition}" if transition else ""))
        self.labels[self.current_label].append(line)
        return self

    def add_show(self, asset: str, position: str = "center", transition: str | None = None):
        line = self._line(f"show {asset} at {position}" + (f" with {transition}" if transition else ""))
        self.labels[self.current_label].append(line)
        return self

    def add_hide(self, tag: str, transition: str | None = None):
        line = self._line(f"hide {tag}" + (f" with {transition}" if transition else ""))
        self.labels[self.current_label].append(line)
        return self

    def add_say(self, who: str | None, text: str):
        esc = text.replace('"', '\\"')
        if who:
            line = self._line(f'{who} "{esc}"')
        else:
            line = self._line(f'"{esc}"')
        self.labels[self.current_label].append(line)
        return self

    def add_set(self, target: str, op: str = "=", expr: str = "0"):
        # canonical set
        line = self._line(f"set {target} {op} {expr}")
        self.labels[self.current_label].append(line)
        return self

    def add_if(self, cond: str):
        line = self._line(f"if {cond}:")
        self.labels[self.current_label].append(line)
        self._push_indent()
        return self

    def add_elif(self, cond: str):
        self._pop_indent()
        line = self._line(f"elif {cond}:")
        self.labels[self.current_label].append(line)
        self._push_indent()
        return self

    def add_else(self):
        self._pop_indent()
        line = self._line("else:")
        self.labels[self.current_label].append(line)
        self._push_indent()
        return self

    def add_end(self):
        self._pop_indent()
        line = self._line("end")
        self.labels[self.current_label].append(line)
        return self

    def add_menu(self, caption: str | None, choices: list[tuple[str, str]]):
        """choices: list of (text, jump_label) — emits declarative choice form
        M27: creates placeholder labels for jump targets so they are always
        reachable even if not later filled. create_quick_wizard overwrites
        these placeholders with real content (no early return issue).
        """
        lines = []
        base = self._cur_indent()
        lines.append(" " * base + "menu:")
        if caption:
            lines.append(" " * (base + 4) + f'"{caption}"')
        for txt, jump in choices:
            if self.use_declarative:
                lines.append(" " * (base + 4) + f'choice "{txt}":')
                lines.append(" " * (base + 8) + f"jump {jump}")
            else:
                lines.append(" " * (base + 4) + f'"{txt}":')
                lines.append(" " * (base + 8) + f"jump {jump}")
            if jump not in self.labels:
                self.labels[jump] = [f'    "{txt} chosen."', "    return"]
                self._label_indent[jump] = 4
                self._indent_stack[jump] = [4]
        self.labels[self.current_label].extend(lines)
        return self

    def add_choice(self, text: str, jump_label: str, condition: str | None = None):
        base = self._cur_indent()
        cond_str = f" if {condition}" if condition else ""
        if self.use_declarative:
            line = " " * base + f'choice "{text}"{cond_str}:'
        else:
            line = " " * base + f'"{text}"{cond_str}:'
        self.labels[self.current_label].append(line)
        self.labels[self.current_label].append(" " * (base + 4) + f"jump {jump_label}")
        if jump_label not in self.labels:
            self.labels[jump_label] = [f'    "{text} chosen."', "    return"]
            self._label_indent[jump_label] = 4
            self._indent_stack[jump_label] = [4]
        return self

    def _clear_placeholder_label(self, label: str):
        """Clear auto-generated placeholder (e.g. '"X chosen." return') so real content can replace it."""
        if label in self.labels:
            # if only contains placeholder, clear it
            content = self.labels[label]
            if len(content) <= 2 and any("chosen" in c for c in content):
                self.labels[label] = []
                self._label_indent[label] = 4
                self._indent_stack[label] = [4]

    def add_jump(self, label: str):
        self.labels[self.current_label].append(self._line(f"jump {label}"))
        return self

    def add_call(self, label: str):
        self.labels[self.current_label].append(self._line(f"call {label}"))
        return self

    def add_return(self):
        self.labels[self.current_label].append(self._line("return"))
        return self

    def add_pause(self, duration: float = 0.5):
        self.labels[self.current_label].append(self._line(f"pause {duration}"))
        return self

    def add_play_music(self, asset: str, fadein: float | None = None):
        extra = f" fadein {fadein}" if fadein else ""
        self.labels[self.current_label].append(self._line(f'play music "{asset}"{extra}'))
        return self

    def add_play_sound(self, asset: str):
        self.labels[self.current_label].append(self._line(f'play sound "{asset}"'))
        return self

    def add_camera_zoom(self, zoom: float, duration: float = 1.0, easing: str = "ease"):
        self.labels[self.current_label].append(self._line(f"camera zoom {zoom} duration {duration} with {easing}"))
        return self

    def add_camera_preset(self, preset: str):
        self.labels[self.current_label].append(self._line(f"camera preset {preset}"))
        return self

    def add_stage(self, stage: str):
        self.labels[self.current_label].append(self._line(f"load_stage {stage}"))
        return self

    def add_show3d(self, asset: str, marker: str = "center"):
        self.labels[self.current_label].append(self._line(f"show3d {asset} at {marker}"))
        return self

    def add_side_image(self, who: str, image: str, side: str = "left"):
        line = self._line(f"show {who} {image} at {side}")
        self.labels[self.current_label].append(line)
        return self

    def add_narration(self, text: str):
        return self.add_say(None, text)

    # ---------------- quick wizard — one-click full game
    def create_quick_wizard(self, title: str = "My Visual Novel", theme: str = "school"):
        """One-click high-quality branching story with variables, 2 endings, 3D stage.
        
        No Python coding required — generates declarative script.
        """
        # reset
        self.characters = {}
        self.state_vars = {}
        self.images = {}
        self.audios = {}
        self.stages = {}
        self.labels = {}
        self._label_indent = {}
        self._indent_stack = {}
        # characters
        self.add_character("e", "Eileen", "#c8ffc8")
        self.add_character("s", "Sylvie", "#c8c8ff")
        # state
        self.add_state_var("affection", "int", "0")
        self.add_state_var("route", "str", '"none"')
        self.add_state_var("has_book", "bool", "False")
        # assets (manifest, optional)
        self.add_image("bg classroom", "backgrounds/bg_classroom.png")
        self.add_image("bg library", "backgrounds/bg_lecturehall.png")
        self.add_image("bg meadow", "backgrounds/bg_meadow.png")
        self.add_stage_asset("classroom_3d", "stages/classroom_3d.blend")

        # start
        self.ensure_label("start")
        self.add_scene("bg classroom", "fade")
        self.add_show("eileen", "center", "dissolve")
        self.add_say("e", f"Welcome to {title}! This game was built with one click — no coding.")
        self.add_say(None, "You can create your own story from the UPVN panel without typing .rpy.")
        self.add_camera_zoom(1.2, 0.8, "ease")
        self.add_say("e", "Let's make a choice that matters.")
        self.add_menu("What will you do?", [("Help Eileen", "help_eileen"), ("Explore library", "explore_library")])

        # help branch
        self.ensure_label("help_eileen")
        self.add_set("affection", "+=", "1")
        self.add_set("route", "=", '"help"')
        self.add_scene("bg classroom", "dissolve")
        self.add_show("eileen happy", "center", "move")
        self.add_say("e", "Thank you! You are so kind.")
        self.add_say("e", "I was looking for my book...")
        self.add_menu("Do you have it?", [("Give her the book", "give_book"), ("Say you don't", "no_book")])

        self.ensure_label("give_book")
        self.add_set("has_book", "=", "True")
        self.add_set("affection", "+=", "2")
        self.add_show("eileen happy", "center", "dissolve")
        self.add_say("e", "You found it! I knew I could count on you.")
        self.add_jump("classroom_3d_scene")

        self.ensure_label("no_book")
        self.add_say("e", "Oh... maybe I left it in the library.")
        self.add_jump("explore_library")

        # library branch
        self.ensure_label("explore_library")
        self.add_set("route", "=", '"library"')
        self.add_scene("bg library", "fade")
        self.add_camera_zoom(1.5, 1.0, "ease")
        self.add_say(None, "The library is quiet. Rows of books stretch into the distance.")
        self.add_show("sylvie", "right", "move")
        self.add_say("s", "Oh, hello! Are you looking for something?")
        self.add_say("e", "Hi Sylvie! Have you seen my book?")
        self.add_say("s", "I think I saw one near the back...")
        self.add_menu("Search for the book", [("Search together", "search_together"), ("Search alone", "search_alone")])

        self.ensure_label("search_together")
        self.add_set("affection", "+=", "1")
        self.add_say("s", "Let's look together!")
        self.add_say(None, "You and Sylvie search through the shelves...")
        self.add_pause(0.5)
        self.add_say("e", "Found it!")
        self.add_set("has_book", "=", "True")
        self.add_jump("classroom_3d_scene")

        self.ensure_label("search_alone")
        self.add_say(None, "You search alone, but can't find it.")
        self.add_say("s", "Need help?")
        self.add_jump("search_together")

        # 3D stage
        self.ensure_label("classroom_3d_scene")
        self.add_scene("bg classroom", "fade")
        self.add_stage("classroom_3d")
        self.add_show3d("eileen", "marker_eileen")
        self.add_camera_preset("wide")
        self.add_say(None, "You return to the classroom. The 3D stage shows your characters in space.")
        self.add_if("has_book")
        self.add_say("e", "Now I can finally study! Thank you so much!")
        self.add_set("affection", "+=", "1")
        self.add_else()
        self.add_say("e", "I still can't find my book... but thanks for trying.")
        self.add_end()
        self.add_if("affection >= 3")
        self.add_jump("good_ending")
        self.add_else()
        self.add_jump("neutral_ending")
        self.add_end()

        self.ensure_label("good_ending")
        self.add_scene("bg meadow", "fade")
        self.add_camera_zoom(1.0, 1.0, "ease")
        self.add_show("eileen happy", "center", "dissolve")
        self.add_show("sylvie", "right", "dissolve")
        self.add_say("e", "This is the best day ever!")
        self.add_say("s", "I'm glad everything worked out.")
        self.add_say(None, "Good Ending — Affection [affection], Route [route]")
        self.add_return()

        self.ensure_label("neutral_ending")
        self.add_scene("bg classroom", "fade")
        self.add_show("eileen", "center")
        self.add_say("e", "Well, it was an okay day.")
        self.add_say(None, "Neutral Ending — Try to get more affection next time!")
        self.add_return()

        return self

    def create_starter_declarative(self):
        """High-quality starter using declarative forms."""
        self.characters = {}
        self.state_vars = {}
        self.labels = {"start": []}
        self._label_indent = {"start": 4}
        self._indent_stack = {"start": [4]}
        self.images = {}
        self.audios = {}
        self.stages = {}
        self.add_character("e", "Eileen", "#c8ffc8")
        self.add_character("s", "Sylvie", "#c8c8ff")
        self.add_state_var("affection", "int", "0")
        self.add_state_var("route", "str", '"none"')
        self.ensure_label("start")
        self.add_scene("bg classroom", "fade")
        self.add_show("eileen", "center", "dissolve")
        self.add_say("e", "Hello from Blender! This game was created with clicks, not code.")
        self.add_say(None, "You can add more dialogue, menus, and 3D stages from the UPVN panel.")
        self.add_camera_zoom(1.2, 1.0, "ease")
        self.add_menu("What do you do?", [("Ask her", "ask"), ("Wait", "wait")])
        self.ensure_label("ask")
        self.add_set("affection", "+=", "1")
        self.add_say("e", "You asked! Affection is now [affection].")
        self.add_return()
        self.ensure_label("wait")
        self.add_say("e", "You waited.")
        self.add_return()
        self.ensure_label("start")
        return self

    def _build_rpy_legacy(self) -> str:
        out = []
        for cid, data in self.characters.items():
            out.append(f'define {cid} = Character("{data["name"]}", color="{data["color"]}")')
        out.append("")
        for label, lines in self.labels.items():
            out.append(f"label {label}:")
            if not lines:
                out.append('    "Empty label."')
                out.append("    return")
            else:
                out.extend(lines)
                last = lines[-1].strip()
                if not last.startswith("jump ") and last != "return" and not last.startswith("return"):
                    out.append("    return")
            out.append("")
        return "\n".join(out)

    def build_rpy(self) -> str:
        if not self.use_declarative:
            return self._build_rpy_legacy()
        out = []
        # state block
        if self.state_vars:
            out.append("state:")
            for name, info in self.state_vars.items():
                t = info.get("type", "int")
                lit = info.get("literal", "0")
                out.append(f"    {name}: {t} = {lit}")
            out.append("")
        # characters declarative
        for cid, data in self.characters.items():
            out.append(f"character {cid}:")
            out.append(f'    name "{data["name"]}"')
            out.append(f'    color "{data["color"]}"')
            out.append("")
        # assets
        for name, path in self.images.items():
            # quote name if contains space
            n = f'"{name}"' if " " in name else name
            out.append(f'image {n} = "{path}"')
        if self.images:
            out.append("")
        for name, path in self.audios.items():
            out.append(f'audio {name} = "{path}"')
        if self.audios:
            out.append("")
        for name, path in self.stages.items():
            out.append(f'stage {name} = "{path}"')
        if self.stages:
            out.append("")
        # labels
        for label, lines in self.labels.items():
            out.append(f"label {label}:")
            if not lines:
                out.append('    "Empty label."')
                out.append("    return")
            else:
                out.extend(lines)
                last = lines[-1].strip()
                if not last.startswith("jump ") and last != "return" and not last.startswith("return") and last != "end" and not last.startswith("end"):
                    out.append("    return")
            out.append("")
        return "\n".join(out)

    def write(self):
        """Write the project script. STRICTLY non-destructive (M26g) with declarative support."""
        fresh = self._existing_text is None or not self.script_path.exists()
        if fresh:
            self.script_path.parent.mkdir(parents=True, exist_ok=True)
            self.script_path.write_text(self.build_rpy(), encoding="utf-8")
            return self.script_path

        existing = self.script_path.read_text(encoding="utf-8")
        lines = existing.splitlines()

        # 1) new characters only (detect both define and character block)
        new_char_lines = []
        for cid, data in self.characters.items():
            has_define = f"define {cid} =" in existing
            has_char_block = re.search(rf'^\s*character\s+{cid}\s*:', existing, re.M) is not None
            if not has_define and not has_char_block:
                if self.use_declarative:
                    new_char_lines.append(f"character {cid}:")
                    new_char_lines.append(f'    name "{data["name"]}"')
                    new_char_lines.append(f'    color "{data["color"]}"')
                    new_char_lines.append("")
                else:
                    new_char_lines.append(f'define {cid} = Character("{data["name"]}", color="{data["color"]}")')

        # 1b) new state vars
        new_state_vars = []
        has_state_block = re.search(r'^\s*state\s*:\s*$', existing, re.M) is not None
        for var, info in self.state_vars.items():
            # check if var already declared
            if re.search(rf'^\s*{re.escape(var)}\s*[:=]', existing, re.M):
                continue
            if re.search(rf'^\s*default\s+{re.escape(var)}\s*=', existing, re.M):
                continue
            t = info.get("type", "int")
            lit = info.get("literal", "0")
            if has_state_block and self.use_declarative:
                new_state_vars.append(f"    {var}: {t} = {lit}")
            else:
                # will create state block later
                new_state_vars.append(f"    {var}: {t} = {lit}")

        # 1c) new assets
        new_assets = []
        for name, path in self.images.items():
            if name not in existing and f'image "{name}"' not in existing and f"image {name}" not in existing:
                n = f'"{name}"' if " " in name else name
                new_assets.append(f'image {n} = "{path}"')
        for name, path in self.audios.items():
            if f"audio {name}" not in existing:
                new_assets.append(f'audio {name} = "{path}"')
        for name, path in self.stages.items():
            if f"stage {name}" not in existing:
                new_assets.append(f'stage {name} = "{path}"')

        # 2) label block bounds
        label_re = re.compile(r'^\s*label\s+(\w+)\s*:')
        starts = [(label_re.match(l).group(1), i)
                  for i, l in enumerate(lines) if label_re.match(l)]
        bounds = {}
        for bi, (name, start) in enumerate(starts):
            bounds[name] = (start, starts[bi + 1][1] if bi + 1 < len(starts) else len(lines))

        insertions = []
        new_label_blocks = []
        for label, new_lines in self.labels.items():
            wanted = [l for l in new_lines if l.strip()]
            if not wanted:
                continue
            if label in bounds:
                start, end = bounds[label]
                block_lines = set(l.strip() for l in lines[start + 1:end])
                to_insert = [l for l in wanted if l.strip() not in block_lines]
                if not to_insert:
                    continue
                at = end
                for j in range(end - 1, start, -1):
                    s = lines[j].strip()
                    if s:
                        if s == "return":
                            at = j
                        break
                placeholder_idx = [j for j in range(start + 1, end)
                                   if lines[j].strip() in ('"Empty label."',
                                                           "'Empty label.'")]
                insertions.append((at, to_insert, placeholder_idx))
            else:
                body = [f"label {label}:"] + wanted
                last = wanted[-1].strip()
                if last != "return" and not last.startswith("jump ") and last != "end":
                    body.append("    return")
                new_label_blocks.append("\n".join(body))

        # check if anything to do
        if not new_char_lines and not new_state_vars and not new_assets and not insertions and not new_label_blocks:
            return self.script_path

        # apply label insertions bottom-up
        for at, to_insert, placeholder_idx in sorted(insertions, key=lambda t: -t[0]):
            for d in sorted(placeholder_idx, reverse=True):
                del lines[d]
            shift = sum(1 for d in placeholder_idx if d < at)
            lines[at - shift:at - shift] = to_insert

        if new_label_blocks:
            while lines and not lines[-1].strip():
                lines.pop()
            for blk in new_label_blocks:
                lines += ["", blk]

        # handle characters and assets and state vars insertion at top
        # find last define/character/state block
        if new_char_lines or new_assets:
            # insert after last define/character/image block or at top
            last_def = -1
            for k, l in enumerate(lines):
                s = l.strip()
                if s.startswith("define ") or s.startswith("character ") or s.startswith("image ") or s.startswith("audio ") or s.startswith("stage ") or s.startswith("state:"):
                    last_def = k
            # if we have state block and new_state_vars, we need to insert inside state block, not after
            if last_def >= 0:
                # if we have assets/chars, insert after last_def block
                # for simplicity, insert after last_def
                insert_at = last_def + 1
                # skip any blank lines and indented lines belonging to that block
                while insert_at < len(lines) and (not lines[insert_at].strip() or lines[insert_at].startswith("    ")):
                    insert_at += 1
                lines[insert_at:insert_at] = new_char_lines + new_assets
            else:
                lines = new_char_lines + new_assets + [""] + lines

        # handle state vars
        if new_state_vars:
            if has_state_block:
                # find state block bounds
                state_start = None
                for i, l in enumerate(lines):
                    if re.match(r'^\s*state\s*:\s*$', l):
                        state_start = i
                        break
                if state_start is not None:
                    # find end of state block (next non-indented or empty)
                    end = state_start + 1
                    while end < len(lines) and (lines[end].startswith("    ") or not lines[end].strip()):
                        if lines[end].strip() and not lines[end].startswith("    "):
                            break
                        end += 1
                    # insert before end, after last var
                    lines[end:end] = [v for v in new_state_vars if v.strip()]
            else:
                # create new state block at top
                state_block = ["state:"] + new_state_vars + [""]
                # insert at top before characters
                lines = state_block + lines

        self.script_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return self.script_path

    def validate(self):
        """Returns (ok: bool, message). Never raises when engine is missing."""
        if not ENGINE_AVAILABLE or _engine_api is None:
            return False, "engine not found — " + ENGINE_INFO.get("message", "see console")
        _p, _vc, _sm = _engine_api
        if self.script_path.exists():
            try:
                _p.parse_file(str(self.script_path))
                return True, "OK (file)"
            except Exception as e:
                return False, str(e)
        rpy = self.build_rpy()
        try:
            _p.parse_string(rpy)
            return True, "OK"
        except Exception as e:
            return False, str(e)

    def engine_ok(self):
        return bool(ENGINE_AVAILABLE)


# ---------------------------------------------------------------- Blender operators (only if HAS_BPY)

if HAS_BPY:

    # ---------------- add-on preferences: engine folder ----------------
    class UPVN_Prefs(bpy.types.AddonPreferences):
        bl_idname = __name__

        engine_path: bpy.props.StringProperty(
            name="Engine folder (optional)",
            default="",
            subtype="DIR_PATH",
            description="Folder that contains engine/ (repo root or extracted add-on). Leave empty for automatic discovery.",
        )

        def draw(self, context):
            layout = self.layout
            ok, info = ENGINE_AVAILABLE, ENGINE_INFO
            row = layout.row()
            if ok:
                row.label(text="✓ Engine available", icon="CHECKMARK")
            else:
                row.label(text="✗ Engine NOT found", icon="ERROR")
                layout.label(text="Install the UPVN .zip release (dist/upvn_editor_addon_v0.7.zip) — engine is bundled.")
            if ok:
                layout.label(text=f"Root: {info.get('root')}   (via {info.get('source')})")
            else:
                for s in info.get("searched", []):
                    layout.label(text=f"  looked: {s}", icon="INFO")
            layout.prop(self, "engine_path")
            row = layout.row(align=True)
            row.operator("upvn.locate_engine", text="Locate Engine…", icon="FILE_FOLDER")
            row.operator("upvn.check_engine", text="Check", icon="FILE_REFRESH")
            row.operator("upvn.bundle_engine", text="Copy engine next to add-on", icon="COPYDOWN")

    class UPVN_OT_LocateEngine(bpy.types.Operator):
        bl_idname = "upvn.locate_engine"
        bl_label = "Locate UPVN Engine Folder"
        bl_description = "Point at the folder that contains engine/ (repo root)"
        directory: bpy.props.StringProperty(subtype="DIR_PATH", options={"HIDDEN"})

        def invoke(self, context, event):
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}

        def execute(self, context):
            global _PREF_OVERRIDE
            d = self.directory or getattr(context.window_manager, "upvn_locate_dir", "")
            _PREF_OVERRIDE = d
            ok, info = ensure_engine(retry=True)
            prefs = context.preferences.addons.get(__name__)
            if prefs is not None:
                prefs.preferences.engine_path = d
            self.report({"INFO" if ok else "ERROR"}, "Engine: " + ("OK " + str(info.get("root")) if ok else "not found there"))
            return {"FINISHED"}

    class UPVN_OT_CheckEngine(bpy.types.Operator):
        bl_idname = "upvn.check_engine"
        bl_label = "Check Engine"
        bl_description = "Re-run engine discovery and report the result"

        def execute(self, context):
            ok, info = ensure_engine(retry=True)
            print("[UPVN] " + engine_diag_text())
            if ok:
                self.report({"INFO"}, "Engine OK — " + str(info.get("root")))
            else:
                self.report({"ERROR"}, "Engine not found: " + str(info.get("message"))[:150])
            return {"FINISHED"}

    class UPVN_OT_BundleEngine(bpy.types.Operator):
        bl_idname = "upvn.bundle_engine"
        bl_label = "Copy Engine Next to Add-on"
        bl_description = "Copy engine/ + bge_frontend/ into the add-on folder so the add-on is self-contained"

        def execute(self, context):
            try:
                msg = bundle_engine_to_addon_dir()
            except Exception as e:
                self.report({"ERROR"}, str(e))
                return {"FINISHED"}
            ensure_engine(retry=True)
            self.report({"INFO"}, msg)
            return {"FINISHED"}

    class UPVN_SceneProps(bpy.types.PropertyGroup):
        project_path: bpy.props.StringProperty(name="Script Path", default="//game/script.rpy", subtype='FILE_PATH')
        def _update_auto_layout(self, context):
            try:
                # Update VNController property immediately when toggled in UI
                import bpy
                ctrl = None
                try:
                    ctrl = bpy.context.scene.objects.get("VNController")
                except Exception:
                    pass
                if ctrl is not None:
                    auto = (self.auto_layout_mode == "ON") if hasattr(self, "auto_layout_mode") else bool(self.auto_layout)
                    try:
                        ctrl["upvn_auto_layout"] = auto
                        # Also set game property if available
                        try:
                            gp = ctrl.game.properties.get("upvn_auto_layout")
                            if gp is not None:
                                gp.value = auto
                            else:
                                ctrl.game.properties["upvn_auto_layout"] = auto
                        except Exception:
                            pass
                    except Exception:
                        pass
                    # Debug ray toggle
                    try:
                        debug = (self.debug_ray_mode == "ON") if hasattr(self, "debug_ray_mode") else bool(getattr(self, "debug_ray", False))
                        ctrl["upvn_debug_ray"] = debug
                        try:
                            gp = ctrl.game.properties.get("upvn_debug_ray")
                            if gp is not None:
                                gp.value = debug
                            else:
                                ctrl.game.properties["upvn_debug_ray"] = debug
                        except Exception:
                            pass
                        # Also set logic flag for frontend
                        try:
                            import bge
                            bge.logic._upvn_debug_ray = debug
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception:
                pass

        auto_layout: bpy.props.BoolProperty(name="Auto Layout", default=True, description="Toggle auto layout for choices/dialogue — when OFF, choices keep custom position/scale (no stretch/translate)", update=_update_auto_layout)
        # Radio button for UI (ON/OFF) — user requested radio button to toggle remaining auto layout
        auto_layout_mode: bpy.props.EnumProperty(name="Auto Layout Mode", items=[("ON", "Auto ON", "Auto layout enabled — choices stretch/translate automatically"), ("OFF", "Auto OFF", "Auto layout disabled — custom layout preserved")], default="ON", update=_update_auto_layout)
        # Debug ray toggle — user requested debug ray render for outside trigger bug
        debug_ray: bpy.props.BoolProperty(name="Debug Ray", default=False, description="Show debug ray from camera to mouse hit — helps diagnose buttons triggered outside visible mesh")
        debug_ray_mode: bpy.props.EnumProperty(name="Debug Ray Mode", items=[("OFF", "Debug OFF", "No debug ray"), ("ON", "Debug ON", "Show debug ray")], default="OFF")
        char_id: bpy.props.StringProperty(name="ID", default="e")
        char_name: bpy.props.StringProperty(name="Name", default="Eileen")
        char_color: bpy.props.FloatVectorProperty(name="Color", subtype='COLOR', size=4, default=(0.78, 1.0, 0.78, 1.0), min=0, max=1)
        bg_name: bpy.props.StringProperty(name="Background", default="bg classroom")
        bg_image: bpy.props.StringProperty(name="BG Image (optional)", default="", subtype='FILE_PATH')
        speaker: bpy.props.StringProperty(name="Speaker (empty=narration)", default="e")
        dialogue: bpy.props.StringProperty(name="Text", default="Hello from Blender!")
        show_asset: bpy.props.StringProperty(name="Asset", default="eileen")
        show_pos: bpy.props.EnumProperty(name="Position", items=[("left", "Left", ""), ("center", "Center", ""), ("right", "Right", ""), ("far_left", "Far Left", ""), ("far_right", "Far Right", "")], default="center")
        show_trans: bpy.props.StringProperty(name="With (move/dissolve/fade)", default="move")
        sprite_image: bpy.props.StringProperty(name="Sprite Image (optional)", default="", subtype='FILE_PATH')
        side_image: bpy.props.StringProperty(name="Side Image Tag", default="")
        menu_caption: bpy.props.StringProperty(name="Menu Caption", default="What do you do?")
        menu_choice1: bpy.props.StringProperty(name="Choice 1", default="Ask her")
        menu_jump1: bpy.props.StringProperty(name="Jump 1", default="ask")
        menu_choice2: bpy.props.StringProperty(name="Choice 2", default="Wait")
        menu_jump2: bpy.props.StringProperty(name="Jump 2", default="wait")
        stage_name: bpy.props.StringProperty(name="3D Stage", default="classroom_3d")
        arbitrary_slot: bpy.props.IntProperty(name="Arbitrary Slot", default=1, min=1, max=999999, description="Any slot 1..∞ (pagination 6/page)")
        # M27 new fields
        var_name: bpy.props.StringProperty(name="Variable", default="affection")
        var_type: bpy.props.EnumProperty(name="Type", items=[("int", "Int", ""), ("float", "Float", ""), ("str", "String", ""), ("bool", "Bool", ""), ("list", "List", "")], default="int")
        var_value: bpy.props.StringProperty(name="Value", default="0")
        if_cond: bpy.props.StringProperty(name="If Condition", default="affection >= 1")
        jump_target: bpy.props.StringProperty(name="Jump To", default="good_ending")
        label_name: bpy.props.StringProperty(name="Label", default="new_scene")
        pause_duration: bpy.props.FloatProperty(name="Duration", default=0.5, min=0.1, max=10.0)
        audio_name: bpy.props.StringProperty(name="Audio Asset", default="theme")
        audio_file: bpy.props.StringProperty(name="Audio File (optional)", default="", subtype='FILE_PATH')
        camera_zoom: bpy.props.FloatProperty(name="Zoom", default=1.2, min=0.1, max=5.0)
        camera_duration: bpy.props.FloatProperty(name="Duration", default=1.0, min=0.1, max=10.0)
        camera_easing: bpy.props.EnumProperty(name="Easing", items=[("linear", "Linear", ""), ("ease", "Ease", ""), ("easein", "Ease In", ""), ("easeout", "Ease Out", ""), ("easeinout", "Ease In Out", "")], default="ease")
        wizard_title: bpy.props.StringProperty(name="Game Title", default="My Visual Novel")
        wizard_theme: bpy.props.EnumProperty(name="Theme", items=[("school", "School", ""), ("fantasy", "Fantasy", ""), ("scifi", "Sci-Fi", ""), ("mystery", "Mystery", "")], default="school")
        set_target: bpy.props.StringProperty(name="Set Variable", default="affection")
        set_op: bpy.props.EnumProperty(name="Op", items=[("=", "=", ""), ("+=", "+=", ""), ("-=", "-=", ""), ("*=", "*=", ""), ("/=", "/=", "")], default="+=")
        set_expr: bpy.props.StringProperty(name="Expression", default="1")
        controller_module: bpy.props.StringProperty(
            name="Python Controller", default="bge_frontend.frontend",
            description="Module ticked by the logic brick (only used in MODULE mode)",
        )

    # ------------------------------------------------------------------
    # v0.7 HQ scene — improved materials and lighting
    # ------------------------------------------------------------------

    _UPVN_LAUNCHER_TEXT = """# UPVN launcher (auto-generated by 'Setup Scene', v0.7).
# Runs on every tick from the Always -> Python brick of the VNController object.
# It bootstraps sys.path so the engine is importable no matter where this .blend
# lives, then ticks the frontend. You normally never need to edit this.
import bge, sys, os
# __UPVN_SETUP_ROOTS__

_cont = bge.logic.getCurrentController()
_owner = _cont.owner

_bfp = ''
try:
    import bpy as _bpy_lp
    _bfp = getattr(getattr(_bpy_lp, 'data', None), 'filepath', '') or ''
except Exception:
    _bfp = ''
if _bfp:
    _bdir = os.path.dirname(os.path.abspath(_bfp))
    _proj = os.path.dirname(_bdir)
    for _r in (_proj, _bdir):
        if _r and _r not in sys.path:
            sys.path.insert(0, _r)
if '_upvn_booted' not in bge.logic.__dict__:
    _roots = []
    if 'upvn_root' in _owner:
        _roots.append(bge.logic.expandPath(str(_owner['upvn_root'])))
    _base = os.path.dirname(bge.logic.expandPath('//'))
    _roots += [_base, os.path.normpath(os.path.join(_base, os.pardir))]
    for _r in _roots:
        if _r and os.path.isdir(os.path.join(_r, 'engine')) and _r not in sys.path:
            sys.path.append(_r)
    bge.logic._upvn_booted = True

try:
    import bge_frontend.frontend as _upvn_frontend
    _upvn_frontend.main(_cont)
except Exception:
    import traceback
    if '_upvn_launch_error' not in bge.logic.__dict__:
        bge.logic._upvn_launch_error = True
        traceback.print_exc()
        print('[UPVN] launcher error (shown once) - is the engine/ folder next to '
              'this .blend or inside the installed add-on?')
"""

    def _engine_root_relative(blend_dir):
        """Nearest ancestor of blend_dir that holds engine/, as a '//…' path."""
        d = blend_dir
        seen = set()
        while d and d not in seen:
            seen.add(d)
            if os.path.isdir(os.path.join(d, "engine")):
                rel = os.path.relpath(d, blend_dir)
                return "//" + ("" if rel == "." else "/" + rel.replace(os.sep, "/"))
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
        return "//"

    def _data_plane(name, size=10.0, color=(0.06, 0.06, 0.09, 1.0), rot=None):
        """Plane mesh + material via data API (no bpy.ops). Default rot = stand in XZ."""
        mesh = bpy.data.meshes.new(name + "_mesh")
        mesh.from_pydata([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)],
                         [], [(0, 1, 2, 3)])
        mesh.update()
        mesh.name = name + "_mesh"
        try:
            uv = mesh.uv_layers.new(name="UVMap")
            for i, (u, v) in enumerate(((0.0, 0.0), (1.0, 0.0),
                                        (1.0, 1.0), (0.0, 1.0))):
                uv.data[i].uv = (u, v)
        except Exception:
            pass
        mat = bpy.data.materials.new(name="MA" + name)
        mat.use_nodes = True
        try:
            principled = mat.node_tree.nodes.get("Principled BSDF")
            if principled:
                principled.inputs["Base Color"].default_value = color
        except Exception:
            pass
        obj = bpy.data.objects.new(name, mesh)
        obj.scale = (size / 2, size / 2, 1)
        if rot is None:
            rot = (1.5707963267948966, 0.0, 0.0)
        obj.rotation_euler = rot
        obj.data.materials.append(mat)
        return obj

    try:
        from engine.render.contract import (TEX_NODE_NAME, MIX_NODE_NAME,
                                            WHITE_IMAGE_NAME)
    except Exception:
        TEX_NODE_NAME = "UPVN Tex Image"
        MIX_NODE_NAME = "UPVN Tex Mix"
        WHITE_IMAGE_NAME = "UPVN_White1px"

    def _ensure_white_image(_b):
        """1×1 white PNG, packed into the blend."""
        try:
            from engine.render.contract import WHITE_IMAGE_NAME
        except Exception:
            WHITE_IMAGE_NAME = "UPVN_White1px"
        img = _b.data.images.get(WHITE_IMAGE_NAME)
        if img is None:
            img = _b.data.images.new(WHITE_IMAGE_NAME, 1, 1, alpha=True)
            try:
                img.pixels = [1.0, 1.0, 1.0, 1.0]
            except Exception:
                pass
        try:
            if not img.packed_file:
                img.file_format = "PNG"
                img.pack()
        except Exception:
            pass
        return img

    def _rewrite_unlit(mat, color, _b=None, tex_capable=False, hq=False, renpy_parity=False):
        """Emission-only, texture-free — Ren'Py identical (M28) + HQ + error logging.

        M28 Ren'Py parity: white semi-transparent textbox (1,1,1,0.8) like textbox.png,
        choice idle white, hover blue #00189d, flat text no extrusion, no shadow.
        Alpha blending: when color alpha <1, set blend_method BLEND and transparent shadows.
        M27 HQ: edge glow when hq=True, but disabled for Ren'Py parity (flat).
        """
        try:
            from engine.render.contract import TEX_NODE_NAME, MIX_NODE_NAME
        except Exception:
            TEX_NODE_NAME, MIX_NODE_NAME = "UPVN Tex Image", "UPVN Tex Mix"
        try:
            mat.use_nodes = True
            nt = mat.node_tree
        except Exception as e:
            print(f"[UPVN] _rewrite_unlit: material {getattr(mat, 'name', '?')} use_nodes failed: {e}")
            return mat
        try:
            nt.nodes.clear()
        except Exception as e:
            print(f"[UPVN] _rewrite_unlit: nodes.clear failed for {mat.name}: {e}")
        try:
            out = nt.nodes.new("ShaderNodeOutputMaterial")
            em = nt.nodes.new("ShaderNodeEmission")
            objinfo = nt.nodes.new("ShaderNodeObjectInfo")
            src_color = objinfo.outputs["Color"]
        except Exception as e:
            print(f"[UPVN] _rewrite_unlit: core nodes creation failed for {mat.name}: {e}")
            return mat

        if tex_capable and _b is not None:
            try:
                tex = nt.nodes.new("ShaderNodeTexImage")
                tex.name = TEX_NODE_NAME
                try:
                    tex.interpolation = "Closest"
                except Exception:
                    pass
                tex.image = _ensure_white_image(_b)
                mix = nt.nodes.new("ShaderNodeMix")
                mix.name = MIX_NODE_NAME
                try:
                    mix.data_type = "RGBA"
                    mix.inputs[0].default_value = 0.0
                    nt.links.new(objinfo.outputs["Color"], mix.inputs[6])
                    nt.links.new(tex.outputs["Color"], mix.inputs[7])
                    nt.links.new(mix.outputs[2], em.inputs["Color"])
                except Exception as e:
                    print(f"[UPVN] _rewrite_unlit: tex mix link failed for {mat.name}: {e} — fallback to object color")
                    nt.links.new(objinfo.outputs["Color"], em.inputs["Color"])
                src_color = None
            except Exception as e:
                print(f"[UPVN] _rewrite_unlit: tex capable setup failed for {mat.name}: {e}")

        # Ren'Py parity: disable HQ fresnel for flat UI (Ren'Py has no edge glow)
        if hq and not renpy_parity:
            try:
                fresnel = nt.nodes.new("ShaderNodeFresnel")
                fresnel.inputs[0].default_value = 1.4
                mix_hq = nt.nodes.new("ShaderNodeMix")
                mix_hq.data_type = "RGBA"
                mix_hq.inputs[0].default_value = 0.15
                bright = (min(1.0, color[0]*1.3), min(1.0, color[1]*1.3), min(1.0, color[2]*1.3), 1.0)
                mix_hq.inputs[6].default_value = color
                mix_hq.inputs[7].default_value = bright
                nt.links.new(fresnel.outputs[0], mix_hq.inputs[0])
                if src_color is not None:
                    mix2 = nt.nodes.new("ShaderNodeMix")
                    mix2.data_type = "RGBA"
                    mix2.inputs[0].default_value = 0.5
                    nt.links.new(src_color, mix2.inputs[6])
                    nt.links.new(mix_hq.outputs[2], mix2.inputs[7])
                    nt.links.new(mix2.outputs[2], em.inputs["Color"])
                    src_color = None
                else:
                    nt.links.new(mix_hq.outputs[2], em.inputs["Color"])
                    src_color = None
            except Exception as e:
                print(f"[UPVN] _rewrite_unlit: HQ fresnel setup failed for {mat.name}: {e}")

        try:
            em.inputs["Color"].default_value = color
            # Ren'Py: flat white, strength 1.0, not 1.2 glow
            em.inputs["Strength"].default_value = 1.0 if renpy_parity else (1.2 if hq else 1.0)
        except Exception as e:
            print(f"[UPVN] _rewrite_unlit: emission inputs failed for {mat.name}: {e}")
        if src_color is not None:
            try:
                nt.links.new(src_color, em.inputs["Color"])
            except Exception as e:
                print(f"[UPVN] _rewrite_unlit: object color link failed for {mat.name}: {e}")
        try:
            nt.links.new(em.outputs[0], out.inputs[0])
        except Exception as e:
            print(f"[UPVN] _rewrite_unlit: output link failed for {mat.name}: {e}")
        # Alpha handling: Ren'Py textbox.png is 80% opaque, so need BLEND
        is_transparent = False
        try:
            if len(color) >= 4 and float(color[3]) < 0.99:
                is_transparent = True
        except Exception:
            pass
        # For Ren'Py identical UI, always allow transparency for white boxes
        if renpy_parity or is_transparent or "UI" in mat.name or "Choice" in mat.name or "MAUI" in mat.name or "MAChoice" in mat.name:
            blend_mode = "BLEND"
            shadow_mode = "NONE"
        else:
            blend_mode = "OPAQUE"
            shadow_mode = "NONE"
        for attr, val in (("blend_method", blend_mode), ("shadow_method", shadow_mode),
                          ("use_backface_culling", False)):
            try:
                setattr(mat, attr, val)
            except Exception as e:
                print(f"[UPVN] _rewrite_unlit: set {attr} failed for {mat.name}: {e}")
        return mat

    def _data_text(name, body="", size=0.32, loc=(0, -0.55, -3.0), rot=None):
        curve = bpy.data.curves.new(name + "_font", "FONT")
        curve.body = body
        curve.size = size
        try:
            # Default alignment LEFT/TOP, but choice text should be Middle vertical
            # per user request: choices text in default scene created by Setup Scene have Middle vertical alignment
            if "choice_" in name and "_text" in name:
                curve.align_x = "CENTER"
                curve.align_y = "CENTER"
                # Middle vertical alignment for choice text
            else:
                curve.align_x = "LEFT"
                curve.align_y = "TOP"
        except Exception:
            pass
        obj = bpy.data.objects.new(name, curve)
        obj.location = loc
        obj.rotation_euler = rot if rot is not None else (1.5707963267948966, 0.0, 0.0)
        return obj

    def _static_ghost(obj):
        """Static, ray-hittable physics for VN plates."""
        try:
            g = obj.game
            try:
                g.physics_type = "STATIC"
            except Exception:
                g.use_ghost = True
            try:
                g.use_collision_bounds = True
                g.collision_bounds_type = "BOX"
            except Exception:
                pass
        except Exception:
            pass

    def _link_ob(scene, ob, col=None):
        try:
            if ob.name not in scene.collection.objects:
                scene.collection.objects.link(ob)
        except Exception:
            pass
        if col is not None:
            try:
                if ob.name not in col.objects:
                    col.objects.link(ob)
            except Exception:
                pass

    def _get_or_create(scene, name, factory):
        """Reuse exact name from this scene or bpy.data (never name.001)."""
        ob = scene.objects.get(name)
        if ob is not None:
            return ob
        existing = bpy.data.objects.get(name)
        if existing is not None:
            _link_ob(scene, existing)
            return existing
        ob = factory()
        if ob.name != name:
            taken = bpy.data.objects.get(name)
            if taken is not None and taken is not ob:
                try:
                    bpy.data.objects.remove(ob, do_unlink=True)
                except Exception:
                    pass
                _link_ob(scene, taken)
                return taken
            try:
                ob.name = name
            except Exception:
                pass
        _link_ob(scene, ob)
        return ob

    def _data_camera(name, ortho=True, size=10.0, loc=(0.0, -10.0, 0.0), rot=(1.5707963267948966, 0.0, 0.0)):
        cam_data = bpy.data.cameras.new(name)
        if ortho:
            cam_data.type = "ORTHO"
            cam_data.ortho_scale = size
        obj = bpy.data.objects.new(name, cam_data)
        obj.location = loc
        obj.rotation_euler = rot
        return obj

    def _load_adaptive_for_blend(blend_dir=None):
        """M28 Adaptive: try to load upvn_gui.json from project to get real colors/metrics."""
        try:
            import json as _json
            search_roots = []
            if blend_dir:
                search_roots.append(pathlib.Path(blend_dir))
                search_roots.append(pathlib.Path(blend_dir).parent)
                search_roots.append(pathlib.Path(blend_dir).parent / "game")
            try:
                here = pathlib.Path(__file__).resolve().parent
                search_roots.append(here.parent)
                search_roots.append(here.parent / "game")
                search_roots.append(here.parent / "assets")
            except Exception:
                pass
            for root in list(search_roots):
                for name in ["upvn_gui.json", "gui_config.json", "assets/gui_config.json", "game/upvn_gui.json", "assets/gui/upvn_gui.json"]:
                    cand = pathlib.Path(root) / name
                    if cand.exists():
                        try:
                            data = _json.loads(cand.read_text(encoding="utf-8"))
                            print(f"[UPVN] Adaptive blend: loaded {cand}")
                            return data
                        except Exception as e:
                            print(f"[UPVN] Adaptive blend: failed {cand}: {e}")
            try:
                from engine.render.gui_parser import find_and_parse_gui
                for root in search_roots:
                    try:
                        cfg = find_and_parse_gui(root)
                        if cfg and cfg.get("source") != "generic_defaults":
                            print(f"[UPVN] Adaptive blend: parsed gui.rpy from {root}")
                            return cfg
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception as e:
            print(f"[UPVN] Adaptive blend load failed: {e}")
        return None

    def _hex_to_rgba_adaptive(hex_str, alpha=1.0):
        try:
            s = str(hex_str).strip().lstrip("#")
            if len(s) == 3:
                s = "".join(c+c for c in s)
            if len(s) != 6:
                return (1.0,1.0,1.0,alpha)
            r = int(s[0:2],16)/255.0
            g = int(s[2:4],16)/255.0
            b = int(s[4:6],16)/255.0
            return (r,g,b,alpha)
        except Exception:
            return (1.0,1.0,1.0,alpha)

    def build_vn_scene(bpy_module=None, *, scene_name=None,
                       script_path="//game/script.rpy",
                       controller_module="upvn_launcher",
                       install_launcher=True):
        """Create/refresh a complete playable UPVN scene (data API, idempotent).
        
        M27 HQ improvements:
        - Better world lighting (dark gradient, not pure black)
        - Improved dialogue box material (darker, more readable)
        - Choice buttons with HQ edge glow and better spacing
        - Better sprite plane colors and positions
        - Soft lighting for 3D stage (sun with low energy, not hidden)
        - Improved backlog/history visuals
        """
        _b = bpy_module or bpy
        has_game = _has_game_support()

        scene = None
        if scene_name:
            scene = _b.data.scenes.get(scene_name)
            if scene is None:
                scene = _b.data.scenes.new(scene_name)
        if scene is None:
            try:
                scene = _b.context.scene
            except Exception:
                scene = None
        if scene is None:
            scene = _b.data.scenes[0]
        if getattr(_b.context, "window", None) is not None:
            try:
                _b.context.window.scene = scene
            except Exception:
                pass

        # collections
        collections = {}
        for name in ["VN_Backgrounds", "VN_Characters", "VN_UI", "VN_Effects", "VN_3DStage"]:
            col = _b.data.collections.get(name)
            if col is None:
                col = _b.data.collections.new(name)
            if col.name not in scene.collection.children:
                scene.collection.children.link(col)
            collections[name] = col

        # camera
        try:
            from engine.render.contract import (
                CAMERA_UI, CAMERA_3D,
                CAMERA_UI_LOCATION, CAMERA_UI_ROTATION, CAMERA_UI_ORTHO_SCALE,
                CAMERA_3D_LOCATION, CAMERA_3D_ROTATION, PLANE_ROTATION,
                DIALOGUE_LOCATION, DIALOGUE_SCALE, SPRITE_SCALE,
            )
        except Exception:
            CAMERA_UI, CAMERA_3D = "Camera_UI", "Camera_3D"
            CAMERA_UI_LOCATION = (0.0, -10.0, 0.0)
            CAMERA_UI_ROTATION = (1.5707963267948966, 0.0, 0.0)
            CAMERA_UI_ORTHO_SCALE = 15.0
            CAMERA_3D_LOCATION = (0.0, -6.0, 2.5)
            CAMERA_3D_ROTATION = (1.15, 0.0, 0.0)
            PLANE_ROTATION = (1.5707963267948966, 0.0, 0.0)
            DIALOGUE_LOCATION = (0.0, -2.0, -3.2)
            DIALOGUE_SCALE = (4.0, 1.2, 1.0)
            SPRITE_SCALE = (1.5, 2.4, 1.0)

        cam_ui = scene.objects.get(CAMERA_UI)
        if cam_ui is None:
            cam_ui = _data_camera(CAMERA_UI, ortho=True, size=CAMERA_UI_ORTHO_SCALE,
                                  loc=CAMERA_UI_LOCATION, rot=CAMERA_UI_ROTATION)
            scene.collection.objects.link(cam_ui)
        elif not cam_ui.get("upvn_camera_custom"):
            cam_ui.location = CAMERA_UI_LOCATION
            cam_ui.rotation_euler = CAMERA_UI_ROTATION
            try:
                cam_ui.data.type = "ORTHO"
                cam_ui.data.ortho_scale = CAMERA_UI_ORTHO_SCALE
            except Exception:
                pass
        cam3d = scene.objects.get(CAMERA_3D)
        if cam3d is None:
            cam3d = _data_camera(CAMERA_3D, ortho=False,
                                  loc=CAMERA_3D_LOCATION, rot=CAMERA_3D_ROTATION)
            scene.collection.objects.link(cam3d)
        scene.camera = cam_ui
        for ob in list(scene.objects):
            try:
                if ob.type == "CAMERA" and ob.name not in (CAMERA_UI, CAMERA_3D):
                    ob.hide_viewport = True
                    ob.hide_render = True
            except Exception:
                pass
        try:
            win = getattr(_b.context, "window", None)
            screen = getattr(win, "screen", None) if win is not None else None
            if screen is not None:
                for area in screen.areas:
                    if area.type == "VIEW_3D":
                        space = area.spaces.active
                        space.camera = cam_ui
                        space.region_3d.view_perspective = "CAMERA"
        except Exception:
            pass

        # M28 Adaptive: try to load upvn_gui.json for true project colors
        _adaptive_cfg = None
        try:
            # blend_dir from context or bpy_module
            _blend_dir = None
            try:
                import bpy as _bpy_tmp
                if _bpy_tmp.data.filepath:
                    _blend_dir = pathlib.Path(_bpy_tmp.data.filepath).parent
            except Exception:
                pass
            _adaptive_cfg = _load_adaptive_for_blend(_blend_dir)
        except Exception as e:
            print(f"[UPVN] Adaptive cfg load in build_vn_scene failed: {e}")

        # placeholder planes
        try:
            from engine.render.contract import (BG_PLANE, BG_MATERIAL,
                                                SPRITE_MATERIAL, SPRITE_POSITIONS,
                                                POSITIONS, DIALOGUE_PLANE,
                                                IMAGE_MODE_DEFAULT, SPRITE_POOL,
                                                POSITION_EMPTY_PREFIX)
        except Exception:
            BG_PLANE, BG_MATERIAL = "BG_Plane", "MABackground"
            SPRITE_MATERIAL, DIALOGUE_PLANE = "MASprite", "Dialogue_Box"
            IMAGE_MODE_DEFAULT = "color"
            SPRITE_POOL, POSITION_EMPTY_PREFIX = "Sprite_pool", "Pos_"
            SPRITE_POSITIONS = ("far_left", "left", "center", "right", "far_right")
            POSITIONS = {p: ({"far_left": -5.0, "left": -3.0, "center": 0.0,
                              "right": 3.0, "far_right": 5.0}[p], -1.0, 0.0)
                         for p in SPRITE_POSITIONS}

        def _ensure_material(_b, name, color, tex_capable=False, hq=False, renpy_parity=False):
            mat = _b.data.materials.get(name)
            if mat is None:
                mat = _b.data.materials.new(name)
            _rewrite_unlit(mat, color, _b=_b, tex_capable=tex_capable, hq=hq, renpy_parity=renpy_parity)
            try:
                mat.use_fake_user = True
            except Exception:
                pass
            return mat

        # M28 Adaptive: colors from upvn_gui.json if present, else Ren'Py identical defaults
        # BG: neutral, but will be textured with actual bg images in converted projects
        _bg_color = (0.95, 0.95, 0.95, 1.0)
        # Ren'Py default theme: white text on a DARK textbox. Opaque: BGE drops
        # material alpha, so translucent PNG looks are approximated with solid colors.
        _ui_color = (0.07, 0.08, 0.10, 1.0)
        _choice_color = (1.0, 1.0, 1.0, 1.0)
        try:
            if _adaptive_cfg:
                cols = _adaptive_cfg.get("colors", {})
                # dialogue_box is usually white, but respect if different
                if "dialogue_box" in cols:
                    _ui_color = _hex_to_rgba_adaptive(cols["dialogue_box"], 0.8)
                if "choice_idle" in cols or "idle" in cols:
                    _choice_color = _hex_to_rgba_adaptive(cols.get("choice_idle") or cols.get("idle") or "#ffffff", 0.8)
        except Exception as e:
            print(f"[UPVN] Adaptive colors failed: {e}")

        mat_bg = _ensure_material(_b, BG_MATERIAL, _bg_color,
                                  tex_capable=True, renpy_parity=True)
        mat_sprite = _ensure_material(_b, SPRITE_MATERIAL, (0.62, 0.78, 0.55, 1.0), tex_capable=True)
        # Ren'Py identical: white semi-transparent textbox (255,255,255,204) like gui/textbox.png — adaptive if config has it
        mat_ui = _ensure_material(_b, "MAUI", _ui_color, renpy_parity=True)
        # Ren'Py identical: choice idle white, hover blue #00189d — adaptive
        mat_choice = _ensure_material(_b, "MAChoice", _choice_color, renpy_parity=True)
        # Font material: white emission so obj.color tint (dark gray, blue) works
        mat_font = _ensure_material(_b, "MAFont", (1.0, 1.0, 1.0, 1.0), renpy_parity=True)

        def _single_material(ob, mat):
            try:
                ob.data.materials.clear()
            except Exception:
                pass
            ob.data.materials.append(mat)

        def _apply_2d_layout(ob, loc, scale=None):
            if ob.get("upvn_layout_custom"):
                return
            ob.location = loc
            ob.rotation_euler = PLANE_ROTATION
            if scale is not None:
                ob.scale = scale

        def _tint(ob, color):
            try:
                ob.color = color
            except Exception:
                pass
            return ob

        bg = scene.objects.get(BG_PLANE)
        if bg is None:
            bg = _data_plane(BG_PLANE, size=18.0, rot=PLANE_ROTATION)
            _single_material(bg, mat_bg)
            scene.collection.objects.link(bg)
            collections["VN_Backgrounds"].objects.link(bg)
        _apply_2d_layout(bg, (0.0, 0.0, 0.0))
        _single_material(bg, mat_bg)
        _tint(bg, (0.95, 0.95, 0.95, 1.0))
        dlg = scene.objects.get(DIALOGUE_PLANE)
        if dlg is None:
            dlg = _data_plane(DIALOGUE_PLANE, size=8.0, color=(0.05, 0.05, 0.12, 1.0),
                              rot=PLANE_ROTATION)
            scene.collection.objects.link(dlg)
            collections["VN_UI"].objects.link(dlg)
        _apply_2d_layout(dlg, DIALOGUE_LOCATION, DIALOGUE_SCALE)
        _single_material(dlg, mat_ui)
        _tint(dlg, (1.0, 1.0, 1.0, 0.8))
        _static_ghost(bg)
        _static_ghost(dlg)

        try:
            from engine.render.contract import (SPEAKER_TEXT, DIALOGUE_TEXT,
                                                SPEAKER_LOCATION, DIALOGUE_TEXT_LOCATION,
                                                CHOICE_COUNT, CHOICE_PREFIX)
        except Exception:
            SPEAKER_TEXT, DIALOGUE_TEXT = "Speaker_Text", "Dialogue_Text"
            SPEAKER_LOCATION = (-3.6, -3.0, -2.55)
            DIALOGUE_TEXT_LOCATION = (-3.6, -4.0, -3.15)
            CHOICE_COUNT, CHOICE_PREFIX = 9, "choice_"

        def _ensure_font(name, loc, size=0.32, bold=False, shear=None,
                         shadow=None, renpy_color=None, font_file=None):
            # shadow param is now ignored/deleted per user directive
            # (shadow objects made no sense and blocked ray picking)
            try:
                from engine.render.contract import UI_FONT_NAME as _UI_FONT_NAME_FALLBACK
            except Exception:
                _UI_FONT_NAME_FALLBACK = "Hack-Regular.ttf"
            ob = scene.objects.get(name)
            if ob is None:
                ob = _data_text(name, body="", size=size, loc=loc, rot=PLANE_ROTATION)
                scene.collection.objects.link(ob)
                collections["VN_UI"].objects.link(ob)
            if not ob.get("upvn_layout_custom"):
                ob.location = loc
                ob.rotation_euler = PLANE_ROTATION
            try:
                if not ob.data.materials:
                    ob.data.materials.append(mat_font)
            except Exception:
                pass
            # Ensure Middle vertical alignment for choice text (user request)
            try:
                if "choice_" in name and "_text" in name:
                    if hasattr(ob.data, "align_y"):
                        ob.data.align_y = "CENTER"
                    if hasattr(ob.data, "align_x"):
                        # Keep CENTER for choice text to be middle aligned
                        ob.data.align_x = "CENTER"
            except Exception:
                pass
            try:
                from engine.render.contract import style_font_curve
                style_font_curve(ob.data, bold=bold, shear=shear, font_name=getattr(ob, 'upvn_font_name', None) or (_UI_FONT_NAME_FALLBACK if 'Speaker' in name or 'speaker' in name.lower() else None))
            except Exception:
                pass
            # Ren'Py identical colors: speaker #002ead blue, dialogue #404040 dark gray
            if renpy_color:
                _tint(ob, renpy_color)
            else:
                # default fallback — dark gray for dialogue, will be overridden by world_ui
                _tint(ob, (0.251, 0.251, 0.251, 1.0))
            if font_file:
                try:
                    ob['upvn_font_name']=font_file
                    from engine.render.contract import style_font_curve, find_ui_font
                    import bpy as _bpy
                    fn = find_ui_font(font_file)
                    if fn:
                        fnt = _bpy.data.fonts.load(fn, check_existing=True)
                        if fnt:
                            ob.data.font = fnt
                except Exception:
                    pass
            _static_ghost(ob)
            # delete any existing shadow object (old blends / previous runs)
            if shadow is not None:
                try:
                    sh = scene.objects.get(shadow)
                    if sh is not None:
                        _b.data.objects.remove(sh, do_unlink=True)
                except Exception:
                    try:
                        sh = scene.objects.get(shadow)
                        if sh is not None:
                            sh.hide_viewport = True
                            sh.hide_render = True
                    except Exception:
                        pass
            return ob

        # M28 Adaptive: speaker/dialogue colors & fonts from contract (which loads upvn_gui.json) or fallback
        try:
            from engine.render.contract import SPEAKER_DEFAULT_COLOR, DEFAULT_TEXT_COLOR, UI_FONT_NAME, UI_FONT_REGULAR, UI_FONT_INTERFACE
        except Exception:
            SPEAKER_DEFAULT_COLOR = (0.0, 0.18, 0.678, 1.0)
            DEFAULT_TEXT_COLOR = (0.251, 0.251, 0.251, 1.0)
            UI_FONT_NAME = "Hack-Regular.ttf"
            UI_FONT_REGULAR = "Lato-Regular.ttf"
            UI_FONT_INTERFACE = "saxmono.ttf"
        # Override with adaptive config if present (for projects where engine not yet imported or generic blend)
        try:
            if _adaptive_cfg:
                cols = _adaptive_cfg.get("colors", {})
                if "accent" in cols:
                    SPEAKER_DEFAULT_COLOR = _hex_to_rgba_adaptive(cols["accent"], 1.0)
                if "text" in cols:
                    DEFAULT_TEXT_COLOR = _hex_to_rgba_adaptive(cols["text"], 1.0)
                fonts = _adaptive_cfg.get("fonts", {})
                if "name" in fonts:
                    import os as _os
                    UI_FONT_NAME = _os.path.basename(fonts["name"])
                if "text" in fonts:
                    UI_FONT_REGULAR = _os.path.basename(fonts["text"])
                if "interface" in fonts or "choice" in fonts:
                    UI_FONT_INTERFACE = _os.path.basename(fonts.get("interface") or fonts.get("choice") or UI_FONT_INTERFACE)
        except Exception as e:
            print(f"[UPVN] Adaptive font/color override failed: {e}")

        _ensure_font(SPEAKER_TEXT, SPEAKER_LOCATION, size=0.30, bold=True,
                     shadow="Speaker_Shadow", renpy_color=SPEAKER_DEFAULT_COLOR, font_file=UI_FONT_NAME)
        _ensure_font(DIALOGUE_TEXT, DIALOGUE_TEXT_LOCATION, size=0.26,
                     shadow="Dialogue_Shadow", renpy_color=DEFAULT_TEXT_COLOR, font_file=UI_FONT_REGULAR)

        try:
            from engine.render.contract import (HISTORY_PLANE, HISTORY_TEXT,
                                                REWIND_TEXT)
        except Exception:
            HISTORY_PLANE, HISTORY_TEXT, REWIND_TEXT = ("History_Box", "History_Text",
                                                         "Rewind_Text")
        hb = scene.objects.get(HISTORY_PLANE)
        if hb is None:
            def _mk_hist():
                return _data_plane(HISTORY_PLANE, size=10.0,
                                   color=(0.02, 0.03, 0.08, 1.0), rot=PLANE_ROTATION)
            hb = _get_or_create(scene, HISTORY_PLANE, _mk_hist)
            _link_ob(scene, hb, collections["VN_UI"])
            _apply_2d_layout(hb, (0.0, -7.0, 0.9), (6.6, 3.0, 1.0))
            _single_material(hb, mat_ui)
            _tint(hb, (0.02, 0.03, 0.08, 1.0))
            _static_ghost(hb)
        _ensure_font(HISTORY_TEXT, (-6.0, -8.0, 3.4), size=0.20)
        _ensure_font(REWIND_TEXT, (-6.0, -9.0, 4.4), size=0.17, shear=0.18)

        # M28 Adaptive choice layout — uses config if present, else LearnToCodeRPG parity
        # Ren'Py: gui.choice_button_width=1185 (61.7% screen), height 52px, ypos 405 centered, spacing 33px
        # Base Z = half_v*0.25 (405px from top), spacing 0.2578 world — adaptive via _adaptive_cfg world
        try:
            from engine.render.contract import CHOICE_IDLE_COLOR, CHOICE_TEXT_IDLE, CHOICE_WIDTH_FACTOR, CHOICE_BASE_Z, CHOICE_SPACING_EM
            # Use adaptive metrics from contract if available
            _choice_width_factor = CHOICE_WIDTH_FACTOR
            _choice_base_z = CHOICE_BASE_Z
            _choice_spacing = CHOICE_SPACING_EM
        except Exception:
            CHOICE_IDLE_COLOR = (1.0, 1.0, 1.0, 0.8)
            CHOICE_TEXT_IDLE = (0.251, 0.251, 0.251, 1.0)
            _choice_width_factor = 0.617
            _choice_base_z = 1.05
            _choice_spacing = 0.38
        # Further override with _adaptive_cfg if present
        try:
            if _adaptive_cfg:
                cols = _adaptive_cfg.get("colors", {})
                if "choice_idle" in cols:
                    CHOICE_IDLE_COLOR = _hex_to_rgba_adaptive(cols["choice_idle"], 0.8)
                elif "idle" in cols:
                    CHOICE_IDLE_COLOR = _hex_to_rgba_adaptive(cols["idle"], 0.8)
                if "choice_idle" in cols or "text" in cols:
                    # choice text idle is usually text color
                    CHOICE_TEXT_IDLE = _hex_to_rgba_adaptive(cols.get("choice_idle") or cols.get("text") or "#404040", 1.0)
                world = _adaptive_cfg.get("world", {})
                if "choice_width_factor" in world:
                    _choice_width_factor = float(world["choice_width_factor"])
                if "choice_base_z" in world:
                    _choice_base_z = float(world["choice_base_z"])
                if "choice_spacing_em" in world:
                    _choice_spacing = float(world["choice_spacing_em"])
        except Exception as e:
            print(f"[UPVN] Adaptive choice override failed: {e}")
        for i in range(CHOICE_COUNT):
            # Adaptive: ypos 405 centered, then each choice below — use _choice_base_z and _choice_spacing
            try:
                z = _choice_base_z - i * (_choice_spacing * 0.16 + 0.5 * 0.12 + 0.54)  # approx 0.66 for default
                # More precise: if we have spacing, use it directly
                # For default 0.38 em -> 0.66 world, so scale factor ~1.736
                z = _choice_base_z - i * (0.66 if _choice_spacing==0.38 else _choice_spacing * 1.736)
            except Exception:
                z = 1.05 - i * 0.66
            loc = (0.0, -5.0, z)
            cname = f"{CHOICE_PREFIX}{i}"
            try:
                def _mk(cname=cname):
                    return _data_plane(cname, size=6.0, color=(1.0, 1.0, 1.0, 0.8),
                                       rot=PLANE_ROTATION)
                ch = _get_or_create(scene, cname, _mk)
                _link_ob(scene, ch, collections["VN_UI"])
                # Adaptive width: 1185 => 4.63 scale for 0.617 factor, scale = factor * 7.5
                try:
                    _w_scale = _choice_width_factor * 7.5
                except Exception:
                    _w_scale = 4.63
                _apply_2d_layout(ch, loc, (_w_scale, 0.22, 1.0))
                _single_material(ch, mat_choice)
                _tint(ch, CHOICE_IDLE_COLOR)
                _static_ghost(ch)
                tname = cname + "_text"
                # Text centered (Ren'Py xalign 0.5) at -2.1 offset to center 1185 width
                _ensure_font(tname, (loc[0] - 2.1, -6.0, loc[2] + 0.08),
                             size=0.22, bold=False,
                             shadow=cname + "_shadow", renpy_color=CHOICE_TEXT_IDLE, font_file=UI_FONT_INTERFACE)
            except Exception as exc:
                print(f"[UPVN] choice {cname} create failed: {exc}")

        # M27 HQ: world setup — dark gradient, not pure black
        try:
            world = scene.world
            if world is None:
                world = _b.data.worlds.new("UPVN_World")
                scene.world = world
            world.use_nodes = True
            bg_n = world.node_tree.nodes.get("Background")
            if bg_n:
                bg_n.inputs[0].default_value = (0.015, 0.018, 0.032, 1.0)
                bg_n.inputs[1].default_value = 0.6
        except Exception:
            pass

        # M27 HQ: soft lighting for 3D stage — keep one sun, hide others
        # Previous code hid ALL lights, which made 3D stage flat. Keep a soft sun for depth.
        try:
            # ensure at least one sun for 3D stage depth
            sun_name = "SUN_Soft"
            sun = _b.data.objects.get(sun_name)
            if sun is None and _b.data.lights:
                # try to reuse existing sun
                for ob in list(scene.objects):
                    if ob.type == "LIGHT" and ob.data.type == "SUN":
                        sun = ob
                        break
            if sun is None:
                light_data = _b.data.lights.new(name="SUN_Soft", type='SUN')
                light_data.energy = 0.8
                light_data.color = (0.9, 0.92, 1.0)
                sun_obj = _b.data.objects.new(name=sun_name, object_data=light_data)
                sun_obj.location = (2.0, -3.0, 4.0)
                sun_obj.rotation_euler = (0.8, 0.1, 0.5)
                scene.collection.objects.link(sun_obj)
                collections["VN_3DStage"].objects.link(sun_obj)
            else:
                try:
                    sun.hide_viewport = False
                    sun.hide_render = False
                    sun.data.energy = 0.8
                except Exception:
                    pass
            # hide other harsh lights
            for ob in list(scene.objects):
                try:
                    if ob.type == "LIGHT" and ob.name != sun_name and ob.name != "SUN_Soft":
                        # keep but dim
                        if ob.data:
                            ob.data.energy = 0.3
                except Exception:
                    pass
        except Exception:
            pass

        # sprite stage: Pos_<pos> empties own the layout; a single pool plane
        # is duplicated per tag at runtime (position-empties refactor)
        for pos in SPRITE_POSITIONS:
            ename = f"{POSITION_EMPTY_PREFIX}{pos}"
            emp = scene.objects.get(ename)
            if emp is None:
                emp = _b.data.objects.new(ename, None)
                emp.empty_display_type = "PLAIN_AXES"
                emp.empty_display_size = 0.6
                scene.collection.objects.link(emp)
                try:
                    collections["VN_Characters"].objects.link(emp)
                except Exception:
                    pass
            emp.location = POSITIONS.get(pos, (0.0, -0.15, 0.0))
        pool = scene.objects.get(SPRITE_POOL)
        if pool is None:
            pool = _data_plane(SPRITE_POOL, size=4.0,
                               color=(0.62, 0.78, 0.55, 1.0),
                               rot=PLANE_ROTATION)
            scene.collection.objects.link(pool)
            try:
                collections["VN_Characters"].objects.link(pool)
            except Exception:
                pass
        _apply_2d_layout(pool, POSITIONS.get("center", (0.0, -0.15, 0.0)),
                         SPRITE_SCALE)
        _single_material(pool, mat_sprite)
        _tint(pool, (0.62, 0.78, 0.55, 1.0))
        _static_ghost(pool)
        try:
            pool.hide_render = False
        except Exception:
            pass
        # legacy per-position planes are superseded by the empties
        for pos in SPRITE_POSITIONS:
            old = scene.objects.get(f"Sprite_{pos}")
            if old is not None and old.name != SPRITE_POOL:
                _b.data.objects.remove(old, do_unlink=True)

        ctrl = scene.objects.get("VNController")
        created = ctrl is None
        if ctrl is None:
            ctrl = _b.data.objects.new("VNController", None)
            ctrl.empty_display_type = "CUBE"
            scene.collection.objects.link(ctrl)
        effective_script_path = script_path
        try:
            if script_path in (None, "", "//game/script.rpy"):
                cur = ctrl.get("script_path")
                if not cur:
                    try:
                        pp = ctrl.game.properties.get("script_path")
                        cur = pp.value if pp is not None else None
                    except Exception:
                        cur = None
                if cur:
                    effective_script_path = str(cur)
        except Exception:
            pass
        _set_runtime_prop(_b, ctrl, "script_path", effective_script_path)
        _set_runtime_prop(_b, ctrl, "image_mode", IMAGE_MODE_DEFAULT)
        try:
            if "parse_mode" not in ctrl:
                _set_runtime_prop(_b, ctrl, "parse_mode", "safe")
        except Exception:
            pass
        try:
            blend_dir = os.path.dirname(os.path.abspath(_b.path.abspath("//"))) if _b.data.filepath else None
        except Exception:
            blend_dir = None
        _set_runtime_prop(_b, ctrl, "upvn_root", _engine_root_relative(blend_dir))
        # Auto layout toggle — respects custom layout when OFF
        try:
            auto = True
            debug = False
            try:
                import bpy as _bpy_auto
                sc = _bpy_auto.context.scene
                if hasattr(sc, "upvn_props"):
                    pp = sc.upvn_props
                    if hasattr(pp, "auto_layout_mode"):
                        auto = (pp.auto_layout_mode == "ON")
                    elif hasattr(pp, "auto_layout"):
                        auto = bool(pp.auto_layout)
                    if hasattr(pp, "debug_ray_mode"):
                        debug = (pp.debug_ray_mode == "ON")
                    elif hasattr(pp, "debug_ray"):
                        debug = bool(pp.debug_ray)
            except Exception:
                pass
            _set_runtime_prop(_b, ctrl, "upvn_auto_layout", auto)
            ctrl["upvn_auto_layout"] = auto
            _set_runtime_prop(_b, ctrl, "upvn_debug_ray", debug)
            ctrl["upvn_debug_ray"] = debug
        except Exception as e:
            print(f"[UPVN] auto_layout/debug prop set failed: {e}")

        _set_runtime_prop(_b, ctrl, "upvn_bricks", "no")
        if has_game and install_launcher:
            launcher = _b.data.texts.get("upvn_launcher")
            if launcher is None:
                launcher = _b.data.texts.new("upvn_launcher")
            launcher.clear()
            _lt = _UPVN_LAUNCHER_TEXT
            try:
                _here = os.path.dirname(os.path.abspath(__file__))
                _roots = [r for r in (os.path.dirname(_here), _here)
                          if os.path.isdir(os.path.join(r, "bge_frontend"))]
                _ins = ("for _r in %r:\n"
                        "    if _r and _r not in sys.path:\n"
                        "        sys.path.insert(0, _r)\n" % (_roots,))
                _lt = _lt.replace("# __UPVN_SETUP_ROOTS__", _ins)
            except Exception:
                _lt = _lt.replace("# __UPVN_SETUP_ROOTS__", "")
            launcher.write(_lt)
            try:
                sensor_names = {s.name for s in ctrl.game.sensors}
                controller_names = {c.name for c in ctrl.game.controllers}
            except Exception:
                sensor_names, controller_names = set(), set()
            need_sensor = "Always" not in sensor_names
            need_controller = "UPVN_Main" not in controller_names
            need_keys = "AllKeys" not in sensor_names
            need_mouse = "Mouse" not in sensor_names
            if not any((need_sensor, need_controller, need_keys, need_mouse)):
                _set_runtime_prop(_b, ctrl, "upvn_bricks", "existing")
            else:
                brick_state = _add_logic_bricks(
                    _b, ctrl, launcher, controller_module,
                    need_sensor=need_sensor, need_controller=need_controller,
                    need_keys=need_keys, need_mouse=need_mouse)
                _set_runtime_prop(_b, ctrl, "upvn_bricks", brick_state)
        return ctrl


    # Properties that should be ENUM (dropdown) instead of STRING (free text)
    _ENUM_PROPS = {
        "image_mode": [("color", "Color", "Palette only, no image files"),
                       ("auto", "Auto", "Use images when available, palette fallback")],
        "parse_mode": [("safe", "Safe", "Declarative subset only"),
                       ("full", "Full", "Full Ren'Py-compatible parsing")],
    }

    def _set_runtime_prop(_b, obj, name, value):
        obj[name] = value
        try:
            props = obj.game.properties
        except Exception:
            return
        p = None
        try:
            p = props.get(name)
        except Exception:
            p = None
        if p is None:
            try:
                with _b.context.temp_override(active_object=obj, object=obj,
                                              selected_objects=[obj],
                                              selected_editable_objects=[obj]):
                    _b.ops.object.game_property_new()
            except Exception:
                return
            p = obj.game.properties[-1]
            p.name = name
            p = obj.game.properties.get(name) or p
        # Use ENUM for known dropdown properties. UPBGE 0.50 (Blender 5.0)
        # removed the ENUM game-property type — fall back to STRING so
        # Setup Scene survives; dropdowns degrade to plain text fields.
        if name in _ENUM_PROPS:
            try:
                if p.type != "ENUM":
                    p.type = "ENUM"
                    p = obj.game.properties.get(name) or p
            except TypeError:
                if p.type != "STRING":
                    p.type = "STRING"
                    p = obj.game.properties.get(name) or p
            try:
                enum_items = _ENUM_PROPS[name]
                p.enum_items = enum_items
                p.enum_flag = False  # single select
            except Exception:
                pass
            try:
                p.value = value
            except Exception:
                pass
        else:
            typ = ("STRING" if isinstance(value, str) else
                   "BOOL" if isinstance(value, bool) else
                   "INT" if isinstance(value, int) else "FLOAT")
            if p.type != typ:
                p.type = typ
                p = obj.game.properties.get(name) or p
            try:
                p.value = value
            except Exception:
                pass


    def _add_logic_bricks(_b, obj, launcher_text, controller_module,
                          need_sensor=True, need_controller=True,
                          need_keys=False, need_mouse=False):
        if not any((need_sensor, need_controller, need_keys, need_mouse)):
            return "already"
        if getattr(_b.app, "background", True):
            return ("skipped-background: run 'Setup Scene' from the UPVN panel "
                    "inside the UPBGE UI (bpy.ops.logic needs an interactive context)")
        try:
            _b.context.view_layer.objects.active = obj
        except Exception:
            pass
        try:
            if need_sensor:
                _b.ops.logic.sensor_add(type="ALWAYS", object=obj.name, name="Always")
            if need_keys:
                _b.ops.logic.sensor_add(type="KEYBOARD", object=obj.name, name="AllKeys")
            if need_mouse:
                _b.ops.logic.sensor_add(type="MOUSE", object=obj.name, name="Mouse")
            if need_controller:
                _b.ops.logic.controller_add(type="PYTHON", object=obj.name, name="UPVN_Main")
        except Exception as e:
            return f"error: {e}"
        try:
            sensors = {s.name: s for s in obj.game.sensors}
            controllers = list(obj.game.controllers)
            if not sensors or not controllers:
                return "error: brick created but pair incomplete"
            con = None
            for c in controllers:
                if c.name == "UPVN_Main":
                    con = c
                    break
            if con is None:
                con = controllers[-1]
            always = sensors.get("Always") or list(sensors.values())[0]
            try:
                always.use_pulse_true_level = True
                always.frequency = 0
            except Exception:
                pass
            keys = sensors.get("AllKeys")
            if keys is not None:
                try:
                    keys.use_all_keys = True
                    keys.use_pulse_true_level = True
                    keys.frequency = 0
                except Exception:
                    pass
            mouse = sensors.get("Mouse")
            if mouse is not None:
                try:
                    mouse.mouse_type = "LEFTCLICK"
                    mouse.use_pulse_true_level = True
                except Exception:
                    pass
            if need_controller and launcher_text is not None:
                try:
                    con.text = launcher_text
                except Exception:
                    try:
                        con.mode = "MODULE"
                        con.module = controller_module
                    except Exception:
                        pass
            for sen in (always, keys, mouse):
                if sen is None:
                    continue
                try:
                    con.link(sensor=sen)
                except TypeError:
                    try:
                        con.link(sensor=sen, actuator=None)
                    except Exception:
                        pass
                except Exception:
                    pass
            return "yes"
        except Exception as e:
            return f"error: {e}"

    def _has_game_support():
        probe = None
        try:
            probe = bpy.data.objects.new("__upvn_probe__", None)
            gs = probe.game
            return gs is not None
        except Exception:
            return False
        finally:
            if probe is not None:
                try:
                    bpy.data.objects.remove(probe, do_unlink=True)
                except Exception:
                    pass

    class UPVN_OT_SetupScene(bpy.types.Operator):
        bl_idname = "upvn.setup_scene"
        bl_label = "Setup Scene (one click HQ)"
        bl_description = "Wire the current .blend for UPVN with HQ materials, lighting, and logic bricks. Press P to play afterwards."

        @classmethod
        def poll(cls, context):
            return _has_game_support()

        def execute(self, context):
            p = context.scene.upvn_props
            try:
                existing = context.scene.objects.get("VNController")
                if existing is not None:
                    cur = None
                    gp = existing.get("script_path")
                    if gp:
                        cur = str(gp)
                    else:
                        try:
                            pp = existing.game.properties.get("script_path")
                            cur = str(pp.value) if pp is not None else None
                        except Exception:
                            cur = None
                    if cur and (not p.project_path
                                or p.project_path == "//game/script.rpy"):
                        p.project_path = cur
                        print("[UPVN] Setup Scene: adopting blend script_path:", cur)
            except Exception as e:
                print("[UPVN] Setup Scene: script_path sync skipped:", e)
            try:
                ctrl = build_vn_scene(script_path=p.project_path,
                                      scene_name=context.scene.name)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.report({"ERROR"}, f"Setup failed: {e}")
                return {"CANCELLED"}
            present = {ob.name for ob in context.scene.objects}
            missing = [f"choice_{i}" for i in range(9) if f"choice_{i}" not in present]
            for n in ("Speaker_Text", "Dialogue_Text", "BG_Plane", "Dialogue_Box",
                      "Camera_UI", "VNController"):
                if n not in present:
                    missing.append(n)
            if missing:
                print("[UPVN] Setup Scene still missing on", context.scene.name, ":", missing)
                self.report({"WARNING"},
                            f"Scene '{context.scene.name}' still missing: {', '.join(missing[:8])}")
            bricks = ctrl.get("upvn_bricks", "no")
            if bricks == "yes":
                self.report({"INFO"},
                            "HQ Scene wired: VNController + Always→Python launcher brick + HQ materials. Press P to play.")
            elif bricks == "existing":
                self.report({"INFO"},
                            "Scene wiring already present and intact (HQ materials refreshed). Press P to play.")
            elif isinstance(bricks, str) and bricks.startswith("skipped"):
                self.report({"WARNING"},
                            "Scene objects created with HQ materials, but logic bricks need the UPBGE UI: run Setup Scene again from this panel.")
            elif isinstance(bricks, str) and bricks.startswith("error"):
                self.report({"ERROR"}, f"Brick wiring failed: {bricks}")
            else:
                self.report({"INFO"},
                            "HQ Scene objects refreshed. Press P to play.")
            print("[UPVN] Setup Scene HQ done. script_path=", p.project_path, "| bricks:", bricks)
            return {"FINISHED"}

    class UPVN_OT_CheckWiring(bpy.types.Operator):
        bl_idname = "upvn.check_wiring"
        bl_label = "Check Scene Wiring"
        bl_description = ("Compare the open scene against the engine's object contract and report missing items")

        def execute(self, context):
            ok, _info = ensure_engine(retry=True)
            if not ok:
                self.report({"ERROR"}, "Engine not found — " + str(ENGINE_INFO.get("message", ""))[:150])
                return {"FINISHED"}
            try:
                from engine.render.contract import check_contract
            except Exception as e:
                self.report({"ERROR"}, f"contract import failed: {e}")
                return {"FINISHED"}
            scene = context.scene
            try:
                obj_names = {ob.name for ob in scene.objects}
            except Exception:
                obj_names = {ob.name for ob in bpy.data.objects}
            print(f"[UPVN] Check Wiring scene={scene.name} objects={len(obj_names)}")
            mats = {m.name for m in bpy.data.materials}
            cols = {c.name for c in bpy.data.collections}
            txts = {t.name for t in bpy.data.texts}
            res = check_contract(obj_names, mats, cols, txts)
            total = len(res["present"]) + len(res["missing"])
            missing = [it["name"] for it in res["missing"]]
            lines = [f"UPVN wiring report — {len(res['present'])}/{total} items present"]
            if missing:
                lines.append("Missing (run Setup Scene to create):")
                for it in res["missing"]:
                    lines.append(f"  - {it['kind']} '{it['name']}': {it['purpose']}")
                for it in res["missing"]:
                    lines.append(f"    expected by: {it['used_by']}")
            else:
                lines.append("All objects, materials, collections and texts required by the engine are present.")
            tb = bpy.data.texts.get("UPVN_WIRING")
            if tb is None:
                tb = bpy.data.texts.new("UPVN_WIRING")
            tb.clear()
            tb.write("\n".join(lines) + "\n")
            print("[UPVN] " + "\n".join(lines))
            if missing:
                self.report({"WARNING"},
                            f"{len(missing)} item(s) missing: {', '.join(missing[:6])} — report in Text editor > UPVN_WIRING")
            else:
                self.report({"INFO"}, "Wiring OK — all scene items required by the engine are present.")
            return {"FINISHED"}

    # REMOVED: UPVN_OT_CreateProject — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_CreateProject operator to edit script.rpy via Blender panel, with bl_idname upvn.createproject, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~30 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_QuickWizard — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_QuickWizard operator to edit script.rpy via Blender panel, with bl_idname upvn.quickwizard, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~31 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddCharacter — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddCharacter operator to edit script.rpy via Blender panel, with bl_idname upvn.addcharacter, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~13 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddVariable — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddVariable operator to edit script.rpy via Blender panel, with bl_idname upvn.addvariable, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~13 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddScene — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddScene operator to edit script.rpy via Blender panel, with bl_idname upvn.addscene, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~23 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddDialogue — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddDialogue operator to edit script.rpy via Blender panel, with bl_idname upvn.adddialogue, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~12 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddShow — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddShow operator to edit script.rpy via Blender panel, with bl_idname upvn.addshow, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~26 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddMenu — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddMenu operator to edit script.rpy via Blender panel, with bl_idname upvn.addmenu, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~11 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddStage — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddStage operator to edit script.rpy via Blender panel, with bl_idname upvn.addstage, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~12 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddSet — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddSet operator to edit script.rpy via Blender panel, with bl_idname upvn.addset, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~13 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddIf — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddIf operator to edit script.rpy via Blender panel, with bl_idname upvn.addif, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~13 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddElse — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddElse operator to edit script.rpy via Blender panel, with bl_idname upvn.addelse, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~11 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddEnd — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddEnd operator to edit script.rpy via Blender panel, with bl_idname upvn.addend, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~11 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddJump — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddJump operator to edit script.rpy via Blender panel, with bl_idname upvn.addjump, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~11 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddLabel — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddLabel operator to edit script.rpy via Blender panel, with bl_idname upvn.addlabel, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~12 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddPause — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddPause operator to edit script.rpy via Blender panel, with bl_idname upvn.addpause, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~11 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddAudio — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddAudio operator to edit script.rpy via Blender panel, with bl_idname upvn.addaudio, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~24 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_AddCamera — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_AddCamera operator to edit script.rpy via Blender panel, with bl_idname upvn.addcamera, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~11 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_Validate — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_Validate operator to edit script.rpy via Blender panel, with bl_idname upvn.validate, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~19 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_SaveSlotDemo — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_SaveSlotDemo operator to edit script.rpy via Blender panel, with bl_idname upvn.saveslotdemo, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~21 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_ExportPackage — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_ExportPackage operator to edit script.rpy via Blender panel, with bl_idname upvn.exportpackage, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~24 lines, deleted per user request. Leave comment what was there.


    # REMOVED: UPVN_OT_ScriptOutline — Blender UI button to edit rpy, never worked, distracts other agents
    # What was here: UPVN_OT_ScriptOutline operator to edit script.rpy via Blender panel, with bl_idname upvn.scriptoutline, bl_label, execute() that appended to file via UPVN_GameBuilder
    # Original had ~36 lines, deleted per user request. Leave comment what was there.


    def _get_project_asset_dir(script_path: str, category: str) -> pathlib.Path:
        p = pathlib.Path(script_path)
        root = p.parent.parent if p.parent.name == "game" else p.parent
        dest = root / "assets" / category
        dest.mkdir(parents=True, exist_ok=True)
        return dest

    def _get_script_text(context, path: str) -> str:
        if hasattr(context, "edit_text") and context.edit_text:
            return context.edit_text.as_string()
        fname = pathlib.Path(path).name
        tb = bpy.data.texts.get(fname)
        if tb is not None:
            return tb.as_string()
        p = pathlib.Path(path)
        if p.exists():
            return p.read_text(encoding="utf-8")
        return ""

    def _builder_from_file(path: str) -> UPVN_GameBuilder:
        """Load existing script.rpy into builder preserving labels (v0.5 fix)."""
        b = UPVN_GameBuilder(path, use_declarative=True)
        try:
            p = pathlib.Path(path)
            if p.exists():
                txt = p.read_text(encoding="utf-8")
                m = list(re.finditer(r'^\s*label\s+(\w+)\s*:', txt, flags=re.M))
                if m:
                    last_label = m[-1].group(1)
                    b.ensure_label(last_label)
        except Exception:
            pass
        return b

    class UPVN_PT_MainPanel(bpy.types.Panel):
        bl_label = "UPVN — Visual Novel (HQ No-Code)"
        bl_idname = "UPVN_PT_main"
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = "UPVN"
        def draw(self, context):
            layout = self.layout
            props = context.scene.upvn_props
            ok, info = ENGINE_AVAILABLE, ENGINE_INFO
            if ok:
                row = layout.row()
                row.label(text="✓ " + engine_status_line(), icon='CHECKMARK')
                if info.get("root"):
                    layout.label(text=str(info["root"])[:60], icon='FILE_FOLDER')
            else:
                box = layout.box()
                box.label(text="✗ Engine not found", icon='ERROR')
                box.label(text="Install dist/upvn_editor_addon_v0.7.zip", icon='INFO')
                box.operator("upvn.check_engine", text="Re-check", icon='FILE_REFRESH')
                box.operator("upvn.locate_engine", text="Locate engine folder…", icon='FILE_FOLDER')
            layout.separator()
            layout.operator("upvn.reload_addon", icon='FILE_REFRESH')
            layout.separator()

            # Project path (kept minimal)
            box = layout.box()
            box.label(text="Project", icon='FILE_FOLDER')
            box.prop(props, "project_path")

            # Auto Layout toggle — user requested radio button to toggle remaining auto layout
            # When OFF, choices don't stretch/translate, allowing custom layout
            box = layout.box()
            box.label(text="Layout Control — Auto Layout Toggle", icon='OBJECT_DATA')
            # Radio buttons (ON/OFF)
            row = box.row()
            row.prop(props, "auto_layout_mode", expand=True)
            # Also show checkbox for clarity
            box.prop(props, "auto_layout")
            box.label(text="ON = auto stretch/translate (default)", icon='INFO')
            box.label(text="OFF = custom layout preserved", icon='INFO')
            box.label(text="Set per-object upvn_custom to keep", icon='INFO')
            box.label(text="individual objects custom", icon='INFO')

            # Debug ray toggle — user requested debug ray render for outside trigger bug
            box = layout.box()
            box.label(text="Debug — Ray Outside Trigger", icon='HIDE_OFF')
            row = box.row()
            row.prop(props, "debug_ray_mode", expand=True)
            box.prop(props, "debug_ray")
            box.label(text="Shows ray from camera to hit", icon='INFO')
            box.label(text="Helps diagnose outside mesh trigger", icon='INFO')

            if _has_game_support():
                box = layout.box()
                box.label(text="Play in UPBGE — HQ Scene", icon='PLAY')
                row = box.row(align=True)
                row.operator("upvn.setup_scene", icon='WINDOW')
                row.operator("upvn.check_wiring", icon='VIEWZOOM')
                box.label(text="HQ materials + soft lighting + edge glow", icon='INFO')
                box.label(text="Then press P in the 3D Viewport", icon='INFO')
                layout.separator()
            else:
                layout.label(text="Run inside UPBGE for play (Setup Scene HQ)", icon='INFO')
                layout.separator()

            # REMOVED: Characters, Variables, Scene & Sprites, Dialogue, Logic, Menu, Extras, Tools & QA boxes
            # What was here:
            # - Characters: char_id, char_name, char_color, add_character
            # - Variables: var_name, var_type, var_value, add_variable
            # - Scene & Sprites: bg_name, bg_image, add_scene, show_asset/pos/trans, sprite_image/side_image, add_show, stage_name, add_stage
            # - Dialogue: speaker, dialogue, add_dialogue
            # - Logic: set_target/op/expr, add_set, if_cond, add_if/else/end, jump_target, add_jump/label, label_name
            # - Menu: menu_caption, menu_choice1/2, menu_jump1/2, add_menu
            # - Extras: pause_duration, add_pause, audio_name/file, add_audio, camera_zoom/duration/easing, add_camera
            # - Tools & QA: validate, check_wiring, save_demo, arbitrary_slot, etc.
            # All deleted per user request — never worked, distracted other agents.

            box = layout.box()
            box.label(text="Tools — Minimal", icon='TOOL_SETTINGS')
            box.label(text="Saves: arbitrary slots 1..∞ (←→ pagination)", icon='INFO')
            box.label(text="H: history  Q: quick menu  Ctrl+S/L: save/load", icon='INFO')


    class UPVN_PT_TextPanel(bpy.types.Panel):
        bl_label = "UPVN — Script (HQ)"
        bl_idname = "UPVN_PT_text"
        bl_space_type = 'TEXT_EDITOR'
        bl_region_type = 'UI'
        bl_category = "UPVN"
        def draw(self, context):
            layout = self.layout
            ok, info = ENGINE_AVAILABLE, ENGINE_INFO
            if ok:
                layout.label(text="✓ " + engine_status_line(), icon='CHECKMARK')
            else:
                layout.label(text="✗ Engine not found", icon='ERROR')
                layout.operator("upvn.check_engine", text="Re-check", icon='FILE_REFRESH')
            layout.separator()
            layout.label(text="Declarative — No Python Coding")
            # REMOVED: validate, script_outline, export_package buttons (never worked)


    class UPVN_OT_ReloadAddon(bpy.types.Operator):
        """Apply an add-on update WITHOUT restarting UPBGE."""
        bl_idname = "upvn.reload_addon"
        bl_label = "Apply Update (reload add-on)"
        bl_options = {'REGISTER'}

        def execute(self, context):
            import sys
            import importlib
            mod = sys.modules.get(__name__)

            def _do_reload():
                try:
                    new = importlib.reload(mod)
                    reg = getattr(new, "register", None)
                    if reg is not None:
                        reg()
                    scn = getattr(bpy.context, "scene", None)
                    ver = getattr(scn, "upvn_addon_version", "?") if scn else "?"
                    print(f"[UPVN] add-on reloaded live — now v{ver} (no restart needed)")
                except Exception as e:
                    print(f"[UPVN] add-on reload failed: {e}")
                    try:
                        import traceback
                        traceback.print_exc()
                    except Exception:
                        pass
                return None

            if bpy.app.background:
                _do_reload()
            else:
                bpy.app.timers.register(_do_reload, first_interval=0.1)
                self.report({'INFO'}, "Reloading UPVN add-on…")
            return {'FINISHED'}

    classes = (UPVN_Prefs,
               UPVN_SceneProps, UPVN_OT_LocateEngine, UPVN_OT_CheckEngine, UPVN_OT_BundleEngine,
               UPVN_OT_ReloadAddon,
               UPVN_OT_SetupScene, UPVN_OT_CheckWiring,
               UPVN_PT_MainPanel, UPVN_PT_TextPanel)

    def _purge_stale_registrations():
        for cls in classes:
            for nm in (getattr(cls, "bl_idname", None),
                       getattr(cls, "__name__", None)):
                if not nm or "." in nm:
                    continue
                live = getattr(bpy.types, nm, None)
                if live is not None:
                    try:
                        bpy.utils.unregister_class(live)
                    except Exception:
                        pass
        for prop in ("upvn_props", "upvn_addon_version"):
            if hasattr(bpy.types.Scene, prop):
                try:
                    delattr(bpy.types.Scene, prop)
                except Exception:
                    pass

    def register():
        # M28 audit fix: reset module-level caches on (re-)register so stale values don't survive
        # a second reload without Blender restart, and so Locate Engine override is re-evaluated.
        global _PREF_OVERRIDE, _engine_api, ENGINE_AVAILABLE, ENGINE_INFO
        # Don't clear _PREF_OVERRIDE if it was set via Locate Engine — but reset engine cache
        # Actually we keep _PREF_OVERRIDE (user choice) but reset ENGINE_AVAILABLE and _engine_api
        # to force re-discovery on every register.
        _engine_api = None
        ENGINE_AVAILABLE = False
        # ENGINE_INFO will be overwritten by ensure_engine
        # If user set engine_path in prefs, respect it as override
        try:
            # Try to read prefs engine_path if available (for persistence across reloads)
            if HAS_BPY and bpy is not None:
                try:
                    # bpy.context may not be available during register, try addon prefs directly
                    import bpy as _bpy
                    # Don't access context, just keep existing _PREF_OVERRIDE
                    pass
                except Exception:
                    pass
        except Exception:
            pass

        _purge_stale_registrations()
        try:
            for cls in classes:
                bpy.utils.register_class(cls)
            bpy.types.Scene.upvn_props = bpy.props.PointerProperty(type=UPVN_SceneProps)
            bpy.types.Scene.upvn_addon_version = bpy.props.StringProperty(
                name="UPVN addon version",
                description="Version of the UPVN editor add-on currently registered",
                default=".".join(str(x) for x in bl_info.get("version", ())),
            )
            # M28: if prefs has engine_path, use it as _PREF_OVERRIDE for this session
            try:
                # After classes registered, prefs are accessible via context
                # but during register context may not have scene — try to read from addon prefs
                prefs = None
                try:
                    # In some Blender versions, preferences are available via bpy.context.preferences
                    ctx = getattr(bpy, 'context', None)
                    if ctx is not None and hasattr(ctx, 'preferences'):
                        addon = ctx.preferences.addons.get(__name__)
                        if addon is not None:
                            ep = getattr(addon.preferences, 'engine_path', '') or ''
                            if ep and os.path.isdir(ep):
                                _PREF_OVERRIDE = ep
                                print(f"[UPVN] Using engine_path from prefs: {ep}")
                except Exception:
                    pass
            except Exception:
                pass

            ok, info = ensure_engine(retry=True)
            ver = ".".join(str(x) for x in bl_info.get("version", ()))
            print(f"[UPVN] Editor addon v{ver} registered — engine: {'OK via ' + str(info['source']) if ok else 'NOT FOUND (' + str(info['message'])[:120] + ')'}")
            print("[UPVN] Panels: View3D > Sidebar > UPVN | Text Editor > Sidebar > UPVN — HQ No-Code v0.7.1 (M28 audit fixes)")
            if not ok:
                print(f"[UPVN] Engine search details: {info.get('searched', [])}")
        except Exception as exc:
            print(f"[UPVN] register() error (add-on partially enabled): {exc}")
            try:
                import traceback
                traceback.print_exc()
            except Exception:
                pass

    def unregister():
        _purge_stale_registrations()
        print("[UPVN] Editor addon unregistered")

    if __name__ == "__main__":
        register()

# expose builder for headless tests
__all__ = ["UPVN_GameBuilder", "ensure_engine", "engine_diag_text", "engine_status_line",
           "ENGINE_AVAILABLE", "ENGINE_INFO", "bundle_engine_to_addon_dir"]
