"""
UPVN Blender Editor Tools — create visual novel inside Blender with minimal coding
v0.6 (2026-09-08): self-contained engine discovery — no more "Engine not available"

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
        dist/upvn_editor_addon_v0.6.zip  → Edit → Preferences → Add-ons →
           Install from Disk… (or Install…) → select the .zip → enable "UPVN".
     Engine, frontend and template travel inside the zip; nothing else needed.
  B. Repo checkout:
        File → Open  <repo>/blend/UPVN_Template.blend
        Edit → Preferences → Add-ons → Install… → <repo>/blend/upvn_editor_addon.py
        (or install from the zip produced by tools/package_addon.py)

Then in 3D Viewport or Text Editor sidebar (N) find tab "UPVN".

Minimal-coding workflow (no .rpy typing):
    1. Create Project → writes //game/script.rpy starter
    2. (UPBGE only) Setup Scene → wires the running scene once
    3. Add Character / Scene / Dialogue / Show / Menu → appended to script.rpy
    4. Validate → parser, line/col + hint;  Preview → headless screenshot
    5. Press P to play. Saves: arbitrary slots 1..∞, pagination.

Headless fallback: when bpy unavailable (CI), the module still imports and exposes
`UPVN_GameBuilder` Python API used by tools/upvn_game_creator.py and tests.
"""

bl_info = {
    "name": "UPVN — Visual Novel Editor",
    "author": "UPVN",
    "version": (0, 6, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > UPVN, Text Editor > Sidebar > UPVN",
    "description": "Create Ren'Py-like visual novel inside UPBGE with minimal coding — self-contained engine, one-click scene setup, characters, scenes, dialogue, menus, arbitrary saves, preview",
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
        fp = bpy.data.filepath
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


def _candidate_is_engine(kind, path):
    if kind == "dir":
        return os.path.isfile(os.path.join(path, "engine", "script", "parser.py"))
    if kind == "zip":
        try:
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
            return any(n.startswith("engine/script/parser.py") or n.startswith("engine\\script\\parser.py") for n in names)
        except Exception:
            return False
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
    """Locate and import the engine. Idempotent; retry=True re-scans.

    Returns (ok: bool, ENGINE_INFO dict). Public API used by tests + operators.
    """
    global ENGINE_INFO, _engine_api, ENGINE_AVAILABLE
    if ENGINE_AVAILABLE and not retry:
        return True, ENGINE_INFO
    # forget previous partial state when retrying
    ENGINE_AVAILABLE = False
    _engine_api = None
    searched = []
    info = {"status": "not_found", "root": None, "source": None,
            "message": "", "searched": searched}
    for kind, path, desc in _engine_candidates():
        searched.append(f"{desc}: {path}")
        if _candidate_is_engine(kind, path):
            try:
                _add_to_syspath(kind, path)
                _p, _vc, _sm = _import_engine_api()
                info.update(status="ok", root=path, source=desc,
                            message=f"engine found via {desc}")
                _engine_api = (_p, _vc, _sm)
                ENGINE_AVAILABLE = True
            except Exception as exc:  # engine present but broken (missing dep…)
                info.update(status="error", root=path, source=desc,
                            message=f"engine found at {path} but import failed: {exc}")
                ENGINE_INFO = info
                return False, info
            break
    if not ENGINE_AVAILABLE:
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
        lines.append(f"  root:   {info['root']}")
        lines.append(f"  source: {info['source']}")
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
    """Copy engine/ + bge_frontend/ next to this file so the add-on is fully
    self-contained (works even after the repo is moved/deleted).

    Returns message string. Raises RuntimeError when engine is not found or the
    add-on folder is not writable.
    """
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
            continue  # already there
        if dst.exists():
            shutil.rmtree(str(dst))
        shutil.copytree(src, str(dst),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        copied.append(sub)
    if not copied:
        raise RuntimeError("nothing to copy (engine already local?)")
    return f"Bundled {', '.join(copied)} into {dest} — engine now travels with the add-on."


# ---------------------------------------------------------------- Python API for minimal coding (works without bpy)

class UPVN_GameBuilder:
    """Headless Python API — also used by Blender operators. Generates .rpy with minimal coding."""

    def __init__(self, script_path: str = "game/script.rpy"):
        self.script_path = pathlib.Path(script_path)
        self.characters = {}  # id -> {name, color}
        self.labels = {"start": []}  # label -> list of lines
        self.current_label = "start"
        self._lines = []  # raw lines for current label
        # ensure project dirs
        self.script_path.parent.mkdir(parents=True, exist_ok=True)
        self._existing_text = None
        # if file exists, load it for preservation
        if self.script_path.exists():
            try:
                self._existing_text = self.script_path.read_text(encoding="utf-8")
                # try parse to populate characters/labels for preview
                if ENGINE_AVAILABLE and _engine_api is not None:
                    try:
                        _p, _vc, _sm = _engine_api
                        data = _p.parse_string(self._existing_text, filename=str(self.script_path))
                        for cid, cdata in data.get("characters", {}).items():
                            self.characters[cid] = {"name": cdata["name"], "color": cdata.get("color", "#ffffff")}
                        # populate labels structure for internal use (keep existing)
                        self.labels = {}
                        for lbl, nodes in data.get("labels", {}).items():
                            self.labels[lbl] = []  # we keep as empty placeholders; actual lines preserved via _existing_text
                        if "start" not in self.labels:
                            self.labels["start"] = []
                    except Exception:
                        pass
            except Exception:
                pass

    def ensure_label(self, label: str):
        if label not in self.labels:
            self.labels[label] = []
        self.current_label = label
        # if existing text has this label, we will append to it on write
        return self

    def add_character(self, cid: str, name: str, color: str = "#ffffff"):
        self.characters[cid] = {"name": name, "color": color}
        return self

    def add_scene(self, bg: str, transition: str | None = None):
        line = f"    scene {bg}" + (f" with {transition}" if transition else "")
        self.labels[self.current_label].append(line)
        return self

    def add_show(self, asset: str, position: str = "center", transition: str | None = None):
        line = f"    show {asset} at {position}" + (f" with {transition}" if transition else "")
        self.labels[self.current_label].append(line)
        return self

    def add_hide(self, tag: str, transition: str | None = None):
        line = f"    hide {tag}" + (f" with {transition}" if transition else "")
        self.labels[self.current_label].append(line)
        return self

    def add_say(self, who: str | None, text: str):
        esc = text.replace('"', '\\"')
        if who:
            line = f'    {who} "{esc}"'
        else:
            line = f'    "{esc}"'
        self.labels[self.current_label].append(line)
        return self

    def add_menu(self, caption: str | None, choices: list[tuple[str, str]]):
        """choices: list of (text, jump_label)"""
        lines = []
        lines.append("    menu:")
        if caption:
            lines.append(f'        "{caption}"')
        for txt, jump in choices:
            lines.append(f'        "{txt}":')
            lines.append(f'            jump {jump}')
            # ensure jump target exists
            if jump not in self.labels:
                self.labels[jump] = [f'    "{txt} chosen."', "    return"]
        self.labels[self.current_label].extend(lines)
        return self

    def add_jump(self, label: str):
        self.labels[self.current_label].append(f"    jump {label}")
        return self

    def add_camera_zoom(self, zoom: float, duration: float = 1.0, easing: str = "ease"):
        self.labels[self.current_label].append(f"    camera zoom {zoom} duration {duration} with {easing}")
        return self

    def add_stage(self, stage: str):
        self.labels[self.current_label].append(f"    load_stage {stage}")
        return self

    def add_show3d(self, asset: str, marker: str = "center"):
        self.labels[self.current_label].append(f"    show3d {asset} at {marker}")
        return self

    def add_side_image(self, who: str, image: str, side: str = "left"):
        """Side image helper — shows side portrait via show with position alias"""
        # side image convention: show <who> side at <side>
        line = f"    show {who} {image} at {side}"
        self.labels[self.current_label].append(line)
        return self

    def build_rpy(self) -> str:
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
                # ensure return if no jump/return at end
                last = lines[-1].strip()
                if not last.startswith("jump ") and last != "return" and "menu:" not in "\n".join(lines[-3:]):
                    pass
            out.append("")
        return "\n".join(out)

    def write(self):
        # Preserve mode: if _existing_text exists, merge new additions rather than overwrite cleanly?
        # New logic: if file existed and we have _existing_text, we merge by appending new label lines
        # and inserting new defines at top after last define.
        if self._existing_text is not None and self.script_path.exists():
            existing = self.script_path.read_text(encoding="utf-8")
            # collect new defines that are not already in existing
            new_defines = []
            for cid, data in self.characters.items():
                define_line = f'define {cid} = Character("{data["name"]}", color="{data["color"]}")'
                if define_line not in existing and f'define {cid} =' not in existing:
                    new_defines.append(define_line)
            # collect new label lines (those in self.labels[current] that are not in existing)
            # Simpler: just append new lines for current_label to the end of that label's block in existing file
            # Find label block for current_label and insert before next label or end
            if self.current_label in existing:
                # find label occurrence
                lines = existing.splitlines()
                # locate label line
                label_idx = None
                for i, l in enumerate(lines):
                    if re.match(rf'^\s*label\s+{re.escape(self.current_label)}\s*:', l):
                        label_idx = i
                        break
                if label_idx is not None:
                    # find next label after
                    next_idx = None
                    for j in range(label_idx + 1, len(lines)):
                        if re.match(r'^\s*label\s+\w+\s*:', lines[j]):
                            next_idx = j
                            break
                    # insert new lines before next_idx or at end
                    insert_at = next_idx if next_idx is not None else len(lines)
                    # new lines to insert are those in self.labels[current_label] that are not already in block
                    block = lines[label_idx + 1:insert_at] if insert_at else []
                    block_text = "\n".join(block)
                    to_insert = []
                    for nl in self.labels[self.current_label]:
                        if nl.strip() not in block_text:
                            to_insert.append(nl)
                    if to_insert:
                        # insert
                        new_lines = lines[:insert_at] + to_insert + lines[insert_at:]
                        # insert new defines at top after last define or after imports
                        if new_defines:
                            last_define_idx = -1
                            for k, l in enumerate(new_lines):
                                if l.strip().startswith("define "):
                                    last_define_idx = k
                            if last_define_idx >= 0:
                                for nd in reversed(new_defines):
                                    new_lines.insert(last_define_idx + 1, nd)
                            else:
                                # insert at top
                                new_lines = new_defines + [""] + new_lines
                        self.script_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                        return self.script_path
            # fallback: if we couldn't merge cleanly, append new defines at top and new lines at end
            if new_defines:
                existing = "\n".join(new_defines) + "\n" + existing
            # append new label blocks that don't exist yet
            new_rpy = self.build_rpy()
            # For simplicity, if current_label lines were not merged, append them
            # Check if any new lines not in existing, append at end of current label block via simple append
            # We'll just write merged via appending to_insert if exists else fallback to overwrite prevention: append at end
            # Last resort: overwrite with build_rpy but preserve original defines+labels that were not in builder
            # To avoid data loss, we append to existing file directly for new lines
            if to_insert if 'to_insert' in locals() else []:
                # already handled
                pass
            else:
                # no merge, just append new lines for current label at end of file
                extra = "\n".join(self.labels[self.current_label])
                if extra.strip() and extra.strip() not in existing:
                    # append inside current label: find label and append before next label
                    # simple: append at end of file
                    self.script_path.write_text(existing.rstrip() + "\n" + extra + "\n", encoding="utf-8")
                    return self.script_path
            # if still not written, fall through to full write
        rpy = self.build_rpy()
        self.script_path.write_text(rpy, encoding="utf-8")
        return self.script_path

    def validate(self):
        """Returns (ok: bool, message). Never raises when engine is missing."""
        if not ENGINE_AVAILABLE or _engine_api is None:
            return False, "engine not found — " + ENGINE_INFO.get("message", "see console")
        _p, _vc, _sm = _engine_api
        # if we have existing file, validate that file, not just built
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

    def preview_screenshot(self, out_path: str = "screenshots/upvn_preview.png"):
        """Headless screenshot via headless_renderer. Returns Path or None."""
        if not ENGINE_AVAILABLE or _engine_api is None:
            return None
        from engine.render.headless_renderer import render_state
        from engine.core.vn_state import VNState
        from engine.core.vn_interpreter import VNInterpreter
        _p, _vc, _sm = _engine_api
        # prefer file on disk if exists
        if self.script_path.exists():
            try:
                script = _p.parse_file(str(self.script_path))
            except Exception:
                rpy = self.build_rpy()
                script = _p.parse_string(rpy)
        else:
            rpy = self.build_rpy()
            try:
                script = _p.parse_string(rpy)
            except Exception as e:
                return None
        state = VNState()
        interp = VNInterpreter(script, state)
        gen = interp.run()
        try:
            ev = next(gen)
            while not ev.get("wait"):
                ev = next(gen)
        except StopIteration:
            ev = {"type": "say", "who": None, "text": "Preview"}
        img = render_state(state, ev, pathlib.Path(out_path))
        return pathlib.Path(out_path)

    # ------------------------------------------------------------------
    # v0.6 — self-checks usable from the UI (no bpy needed)
    # ------------------------------------------------------------------
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
            description="Folder that contains engine/ (repo root or extracted add-on). "
                        "Leave empty for automatic discovery.",
        )

        def draw(self, context):
            layout = self.layout
            ok, info = ENGINE_AVAILABLE, ENGINE_INFO
            row = layout.row()
            if ok:
                row.label(text="✓ Engine available", icon="CHECKMARK")
            else:
                row.label(text="✗ Engine NOT found", icon="ERROR")
                layout.label(text="Install the UPVN .zip release (dist/upvn_editor_addon_v0.6.zip) — engine is bundled.")
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

    # properties
    class UPVN_SceneProps(bpy.types.PropertyGroup):
        project_path: bpy.props.StringProperty(name="Script Path", default="//game/script.rpy", subtype='FILE_PATH')
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
        controller_module: bpy.props.StringProperty(
            name="Python Controller", default="bge_frontend.frontend",
            description="Module ticked by the logic brick (only used in MODULE mode)",
        )

    # ------------------------------------------------------------------
    # v0.6 — one-click scene setup (UPBGE). Pure data-API: works in the
    # UI and in --background runs, no bpy.ops, no context dependencies.
    # ------------------------------------------------------------------

    _UPVN_LAUNCHER_TEXT = """# UPVN launcher (auto-generated by 'Setup Scene', v0.6).
# Runs on every tick from the Always -> Python brick of the VNController object.
# It bootstraps sys.path so the engine is importable no matter where this .blend
# lives, then ticks the frontend. You normally never need to edit this.
import bge, sys, os

_cont = bge.logic.getCurrentController()
_owner = _cont.owner

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

import bge_frontend.frontend as _upvn_frontend
_upvn_frontend.main(_cont)
"""

    def _engine_root_relative(blend_dir):
        """Nearest ancestor of blend_dir that holds engine/, as a '//…' path
        (empty string when none found — launcher then auto-searches)."""
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

    def _data_plane(name, size=10.0, color=(0.06, 0.06, 0.09, 1.0)):
        """Plane mesh + material via data API (no bpy.ops)."""
        mesh = bpy.data.meshes.new(name + "_mesh")
        mesh.from_pydata([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)],
                         [], [(0, 1, 2, 3)])
        mesh.update()
        mesh.name = name + "_mesh"
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
        obj.data.materials.append(mat)
        return obj

    def _data_camera(name, ortho=True, size=10.0, loc=(0, -10, 5), rot=(1.5708, 0, 0)):
        cam_data = bpy.data.cameras.new(name)
        if ortho:
            cam_data.type = "ORTHO"
            cam_data.ortho_scale = size
        obj = bpy.data.objects.new(name, cam_data)
        obj.location = loc
        obj.rotation_euler = rot
        return obj

    def build_vn_scene(bpy_module=None, *, scene_name="VN_Main",
                       script_path="//game/script.rpy",
                       controller_module="upvn_launcher",
                       install_launcher=True):
        """Create/refresh a complete playable UPVN scene (data API, idempotent).

        - scene VN_Main (or scene_name) with ortho camera + 3D camera
        - collections VN_Backgrounds/VN_Characters/VN_UI/VN_Effects/VN_3DStage
        - BG_Plane + Dialogue_Box placeholders
        - object VNController (empty) with script_path / upvn_root properties
        - logic bricks on VNController: Always(pulse) -> Python(launcher)

        Safe to press repeatedly: existing objects/bricks are replaced.
        Returns the controller object. Runs headless (no bpy.ops).
        """
        _b = bpy_module or bpy
        has_game = _has_game_support()

        scene = _b.data.scenes.get(scene_name)
        if scene is None:
            scene = _b.data.scenes.new(scene_name)
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

        # remove previous controller object (idempotent re-run)
        old = scene.objects.get("VNController")
        if old is not None:
            for c in list(old.game.controllers) if has_game else []:
                old.game.controllers.remove(c)
            for s in list(old.game.sensors) if has_game else []:
                old.game.sensors.remove(s)
            scene.collection.objects.unlink(old)
            _b.data.objects.remove(old, do_unlink=True)

        # cameras (keep user cameras, add missing defaults)
        cam_ui = scene.objects.get("Camera_UI")
        if cam_ui is None:
            cam_ui = _data_camera("Camera_UI")
            scene.collection.objects.link(cam_ui)
        cam3d = scene.objects.get("Camera_3D")
        if cam3d is None:
            cam3d = _data_camera("Camera_3D", ortho=False, loc=(0, -6, 2.5), rot=(1.15, 0, 0))
            scene.collection.objects.link(cam3d)
        scene.camera = cam_ui

        # placeholder planes (only when missing — don't destroy user art)
        bg = scene.objects.get("BG_Plane")
        if bg is None:
            bg = _data_plane("BG_Plane", size=10.0)
            scene.collection.objects.link(bg)
            collections["VN_Backgrounds"].objects.link(bg)
        dlg = scene.objects.get("Dialogue_Box")
        if dlg is None:
            dlg = _data_plane("Dialogue_Box", size=8.0, color=(0.05, 0.05, 0.12, 1.0))
            dlg.scale = (8 / 2, 8 / 2 * 0.3, 1)
            scene.collection.objects.link(dlg)
            collections["VN_UI"].objects.link(dlg)

        # VNController empty
        ctrl = _b.data.objects.new("VNController", None)
        ctrl.empty_display_type = "CUBE"
        ctrl["script_path"] = script_path
        # relative root to the folder that contains engine/ (launcher falls back
        # to the blend dir + parents when this is empty/stale)
        try:
            blend_dir = os.path.dirname(os.path.abspath(_b.path.abspath("//"))) if _b.data.filepath else None
        except Exception:
            blend_dir = None
        ctrl["upvn_root"] = _engine_root_relative(blend_dir)

        scene.collection.objects.link(ctrl)

        # --- logic bricks (UPBGE only) ---
        # UPBGE 0.50 exposes brick editing through bpy.ops.logic.* (the same
        # operators UPBGE's own add-ons use) — the RNA collections themselves are
        # read-only. bpy.ops.logic requires an interactive UI/GL context, so in
        # --background mode we skip bricks and say so loudly (no silent half-wired
        # scenes: the object + launcher text are still created, so the user can
        # press "Setup Scene" once in the UPBGE UI to finish).
        ctrl["upvn_bricks"] = "no"
        if has_game and install_launcher:
            launcher = _b.data.texts.get("upvn_launcher")
            if launcher is None:
                launcher = _b.data.texts.new("upvn_launcher")
            launcher.clear()
            launcher.write(_UPVN_LAUNCHER_TEXT)
            brick_state = _add_logic_bricks(_b, ctrl, launcher, controller_module)
            ctrl["upvn_bricks"] = brick_state
        return ctrl


    def _add_logic_bricks(_b, obj, launcher_text, controller_module):
        """Wire Always(pulse) -> Python(launcher text) on obj via bpy.ops.logic.*.

        Returns 'yes' | 'skipped-background' | 'error: …'.
        """
        if getattr(_b.app, "background", True):
            return ("skipped-background: run 'Setup Scene' from the UPVN panel "
                    "inside the UPBGE UI (bpy.ops.logic needs an interactive context)")
        try:
            _b.context.view_layer.objects.active = obj
        except Exception:
            pass
        try:
            _b.ops.logic.sensor_add(type="ALWAYS", object=obj.name, name="Always")
            _b.ops.logic.controller_add(type="PYTHON", object=obj.name, name="UPVN_Main")
        except Exception as e:
            return f"error: {e}"
        try:
            sen = obj.game.sensors[-1]
            con = obj.game.controllers[-1]
            try:
                sen.use_pulse_true_level = True
                sen.frequency = 0
            except Exception:
                pass
            if launcher_text is not None:
                try:
                    con.text = launcher_text      # SCRIPT mode, Text datablock
                except Exception:
                    try:
                        con.mode = "MODULE"
                        con.module = controller_module
                    except Exception:
                        pass
            try:
                con.link(sensor=sen)
            except TypeError:
                con.link(sensor=sen, actuator=None)
            return "yes"
        except Exception as e:
            return f"error: {e}"

    def _has_game_support():
        """True when the running build exposes game logic settings (UPBGE).

        Note: UPBGE 0.50 answers hasattr(bpy.types.Object, 'game') with False
        even though every instance has .game — so probe through a real object.
        """
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
        bl_label = "Setup Scene (one click)"
        bl_description = "Wire the current .blend for UPVN: cameras, collections, VNController + Always→Python brick, path-bootstrap launcher. Press P to play afterwards."

        @classmethod
        def poll(cls, context):
            return _has_game_support()

        def execute(self, context):
            p = context.scene.upvn_props
            try:
                ctrl = build_vn_scene(script_path=p.project_path)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.report({"ERROR"}, f"Setup failed: {e}")
                return {"CANCELLED"}
            bricks = ctrl.get("upvn_bricks", "no")
            if bricks == "yes":
                self.report({"INFO"}, "Scene wired: VNController + Always→Python launcher brick. Press P to play.")
            elif isinstance(bricks, str) and bricks.startswith("skipped"):
                self.report({"WARNING"},
                            "Scene objects created, but logic bricks need the UPBGE UI: "
                            "run Setup Scene again from this panel (not --background).")
            else:
                self.report({"WARNING"}, f"Brick wiring issue: {bricks} — see console.")
                print("[UPVN] Setup Scene done, but bricks:", bricks)
            print("[UPVN] Setup Scene done. script_path=", p.project_path)
            return {"FINISHED"}

    class UPVN_OT_CreateProject(bpy.types.Operator):
        bl_idname = "upvn.create_project"
        bl_label = "Create UPVN Project"
        bl_description = "Create //game/script.rpy with starter template (no coding)"
        def execute(self, context):
            props = context.scene.upvn_props
            path = bpy.path.abspath(props.project_path)
            builder = UPVN_GameBuilder(path)
            builder.add_character("e", "Eileen", "#c8ffc8")
            builder.add_character("s", "Sylvie", "#c8c8ff")
            builder.ensure_label("start")
            builder.add_scene("bg classroom")
            builder.add_show("eileen", "center")
            builder.add_say("e", "Hello from Blender! This game was created with clicks, not code.")
            builder.add_say(None, "You can add more dialogue, menus, and 3D stages from the UPVN panel.")
            builder.write()
            self.report({'INFO'}, f"Created {path}")
            return {'FINISHED'}

    class UPVN_OT_AddCharacter(bpy.types.Operator):
        bl_idname = "upvn.add_character"
        bl_label = "Add Character"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            builder = _builder_from_file(path)
            col = p.char_color
            hexcol = "#{:02x}{:02x}{:02x}".format(int(col[0] * 255), int(col[1] * 255), int(col[2] * 255))
            builder.add_character(p.char_id, p.char_name, hexcol)
            builder.write()
            self.report({'INFO'}, f"Added character {p.char_id}={p.char_name} (preserved labels)")
            return {'FINISHED'}

    class UPVN_OT_AddScene(bpy.types.Operator):
        bl_idname = "upvn.add_scene"
        bl_label = "Add Scene"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            builder = _builder_from_file(path)
            # asset browser: if bg_image picked, copy to assets and use basename
            bg = p.bg_name
            if p.bg_image:
                try:
                    src = pathlib.Path(bpy.path.abspath(p.bg_image))
                    if src.exists():
                        dest_dir = pathlib.Path(path).parent.parent / "assets" / "backgrounds"
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest = dest_dir / src.name
                        shutil.copy2(src, dest)
                        bg = f"bg {src.stem}"
                        self.report({'INFO'}, f"Copied BG {src.name} → {dest}")
                except Exception as e:
                    self.report({'WARNING'}, f"BG copy failed {e}")
            builder.add_scene(bg)
            builder.write()
            self.report({'INFO'}, f"Added scene {bg} (with asset browser)")
            return {'FINISHED'}

    class UPVN_OT_AddDialogue(bpy.types.Operator):
        bl_idname = "upvn.add_dialogue"
        bl_label = "Add Dialogue"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            builder = _builder_from_file(path)
            who = p.speaker.strip() or None
            builder.add_say(who, p.dialogue)
            builder.write()
            self.report({'INFO'}, f"Added say {who or 'Narration'}: {p.dialogue[:30]}")
            return {'FINISHED'}

    class UPVN_OT_AddShow(bpy.types.Operator):
        bl_idname = "upvn.add_show"
        bl_label = "Add Show"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            builder = _builder_from_file(path)
            trans = p.show_trans.strip() or None
            asset = p.show_asset
            if p.sprite_image:
                try:
                    src = pathlib.Path(bpy.path.abspath(p.sprite_image))
                    if src.exists():
                        dest_dir = pathlib.Path(path).parent.parent / "assets" / "sprites"
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        dest = dest_dir / src.name
                        shutil.copy2(src, dest)
                        asset = src.stem
                        self.report({'INFO'}, f"Copied sprite {src.name} → {dest}")
                except Exception as e:
                    self.report({'WARNING'}, f"Sprite copy failed {e}")
            builder.add_show(asset, p.show_pos, trans)
            # side image support
            if p.side_image.strip():
                builder.add_side_image(asset, p.side_image.strip(), p.show_pos)
            builder.write()
            self.report({'INFO'}, f"Added show {asset} at {p.show_pos} with {trans}")
            return {'FINISHED'}

    class UPVN_OT_AddMenu(bpy.types.Operator):
        bl_idname = "upvn.add_menu"
        bl_label = "Add Menu"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            builder = _builder_from_file(path)
            builder.add_menu(p.menu_caption, [(p.menu_choice1, p.menu_jump1), (p.menu_choice2, p.menu_jump2)])
            builder.write()
            self.report({'INFO'}, f"Added menu {p.menu_caption} (preserved)")
            return {'FINISHED'}

    class UPVN_OT_AddStage(bpy.types.Operator):
        bl_idname = "upvn.add_stage"
        bl_label = "Add 3D Stage"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            builder = _builder_from_file(path)
            builder.add_stage(p.stage_name)
            builder.add_show3d("eileen", "marker_eileen")
            builder.write()
            self.report({'INFO'}, f"Added 3D stage {p.stage_name} + show3d")
            return {'FINISHED'}

    class UPVN_OT_Validate(bpy.types.Operator):
        bl_idname = "upvn.validate"
        bl_label = "Validate Script"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            ok, _info = ensure_engine(retry=True)
            if not ok:
                print("[UPVN] " + engine_diag_text())
                self.report({'ERROR'}, "Engine not found. " + str(ENGINE_INFO.get("message", ""))[:200])
                return {'FINISHED'}
            text = pathlib.Path(path).read_text(encoding="utf-8") if pathlib.Path(path).exists() else ""
            try:
                _p, _vc, _sm = _engine_api
                _p.parse_string(text, filename=path)
                self.report({'INFO'}, "Validate OK — no errors")
            except Exception as e:
                self.report({'ERROR'}, str(e).splitlines()[0][:200])
            return {'FINISHED'}

    class UPVN_OT_Preview(bpy.types.Operator):
        bl_idname = "upvn.preview"
        bl_label = "Preview Screenshot"
        def execute(self, context):
            p = context.scene.upvn_props
            path = bpy.path.abspath(p.project_path)
            builder = _builder_from_file(path)
            out = builder.preview_screenshot()
            if out and out.exists():
                self.report({'INFO'}, f"Preview at {out} ({out.stat().st_size // 1024}KB)")
                try:
                    img = bpy.data.images.load(str(out), check_existing=True)
                    for area in bpy.context.screen.areas:
                        if area.type == 'IMAGE_EDITOR':
                            area.spaces.active.image = img
                except Exception:
                    pass
            else:
                ok, _info = ensure_engine()
                if not ok:
                    self.report({'ERROR'}, "Engine not found — install the UPVN .zip release or set engine folder in add-on preferences.")
                else:
                    self.report({'ERROR'}, "Preview failed — see console (script may not parse / Pillow missing in this Blender python).")
                    print("[UPVN] " + engine_diag_text())
            return {'FINISHED'}

    class UPVN_OT_SaveSlotDemo(bpy.types.Operator):
        bl_idname = "upvn.save_demo"
        bl_label = "Save Demo (arbitrary slot)"
        bl_description = "Demo arbitrary save slots: saves to next available slot or chosen slot"
        def execute(self, context):
            ok, _info = ensure_engine(retry=True)
            if not ok:
                self.report({'ERROR'}, "Engine not found — " + str(ENGINE_INFO.get("message", ""))[:200])
                return {'FINISHED'}
            p = context.scene.upvn_props
            from engine.core.vn_state import VNState
            from engine.save.save_manager import SaveManager
            state = VNState()
            state.variables["demo"] = 1
            sm = SaveManager(state)
            slot = int(p.arbitrary_slot) if p.arbitrary_slot else sm.next_available_slot()
            # if slot exists, next available to avoid overwrite? Use chosen
            sm.save(slot)
            self.report({'INFO'}, f"Saved to arbitrary slot {slot} (1..∞)")
            ids = sm.list_slot_ids()
            self.report({'INFO'}, f"Slots now: {ids} — pagination 6/page, page {(slot - 1) // 6 + 1}")
            return {'FINISHED'}

    class UPVN_OT_QuickPreviewArbitrary(bpy.types.Operator):
        bl_idname = "upvn.preview_arbitrary"
        bl_label = "Preview Arbitrary Saves"
        def execute(self, context):
            ok, _info = ensure_engine(retry=True)
            if not ok:
                self.report({'ERROR'}, "Engine not found — " + str(ENGINE_INFO.get("message", ""))[:200])
                return {'FINISHED'}
            p = context.scene.upvn_props
            # generate a preview screenshot of save overlay pagination
            try:
                from engine.render.headless_renderer import render_state
                from engine.core.vn_state import VNState
                from engine.save.save_manager import SaveManager
                from engine.ui.screen_manager import ScreenManager
                from engine.ui.screen_manager import SaveScreen
                state = VNState()
                state.history.append({"who": None, "who_name": "Narrator", "text": "Arbitrary save demo", "stripped": "Arbitrary save demo"})
                sm = SaveManager(state, save_dir=str(pathlib.Path(bpy.path.abspath(p.project_path)).parent / "saves"))
                # create dummy saves up to chosen slot for pagination demo
                for i in [1, 2, 7, 42, 100, 500]:
                    try:
                        state.variables["slot_test"] = i
                        sm.save(i)
                    except Exception:
                        pass
                mgr = ScreenManager(state, sm)
                save_screen = SaveScreen(sm)
                save_screen.page = (int(p.arbitrary_slot) - 1) // 6
                mgr.show("save", save_screen)
                from pathlib import Path
                out = Path("screenshots/upvn_arbitrary_preview.png")
                render_state(state, {"type": "say", "who": None, "text": "Arbitrary preview"}, out, screen_mgr=mgr)
                self.report({'INFO'}, f"Arbitrary preview at {out} page {save_screen.page + 1}")
            except Exception as e:
                self.report({'ERROR'}, f"Arbitrary preview failed {e}")
            return {'FINISHED'}

    def _builder_from_file(path: str) -> UPVN_GameBuilder:
        """Load existing script.rpy into builder preserving labels (v0.5 fix)."""
        # Use UPVN_GameBuilder's own preservation logic (it loads _existing_text)
        b = UPVN_GameBuilder(path)
        # ensure current label is last label in file if exists, so new ops append to correct place
        # Try to detect last label in file
        try:
            p = pathlib.Path(path)
            if p.exists():
                txt = p.read_text(encoding="utf-8")
                # find last label
                m = list(re.finditer(r'^\s*label\s+(\w+)\s*:', txt, flags=re.M))
                if m:
                    last_label = m[-1].group(1)
                    b.ensure_label(last_label)
                # also try to load characters already parsed (b already did)
        except Exception:
            pass
        return b

    class UPVN_PT_MainPanel(bpy.types.Panel):
        bl_label = "UPVN — Visual Novel"
        bl_idname = "UPVN_PT_main"
        bl_space_type = 'VIEW_3D'
        bl_region_type = 'UI'
        bl_category = "UPVN"
        def draw(self, context):
            layout = self.layout
            props = context.scene.upvn_props
            # engine status row
            ok, info = ENGINE_AVAILABLE, ENGINE_INFO
            if ok:
                row = layout.row()
                row.label(text="✓ " + engine_status_line(), icon='CHECKMARK')
                if info.get("root"):
                    layout.label(text=str(info["root"]), icon='FILE_FOLDER')
            else:
                box = layout.box()
                box.label(text="✗ Engine not found", icon='ERROR')
                box.label(text="Install dist/upvn_editor_addon_v0.6.zip", icon='INFO')
                box.operator("upvn.check_engine", text="Re-check", icon='FILE_REFRESH')
                box.operator("upvn.locate_engine", text="Locate engine folder…", icon='FILE_FOLDER')
            layout.separator()
            layout.label(text="Project", icon='FILE_FOLDER')
            layout.prop(props, "project_path")
            layout.operator("upvn.create_project", icon='ADD')
            layout.separator()
            if _has_game_support():
                box = layout.box()
                box.label(text="Play in UPBGE — run once per project", icon='PLAY')
                box.operator("upvn.setup_scene", icon='WINDOW')
                box.label(text="Then press P in the 3D Viewport", icon='INFO')
                layout.separator()
            else:
                layout.label(text="Run inside UPBGE for play (Setup Scene)", icon='INFO')
                layout.separator()
            layout.label(text="Characters (no coding)", icon='USER')
            layout.prop(props, "char_id")
            layout.prop(props, "char_name")
            layout.prop(props, "char_color")
            layout.operator("upvn.add_character", icon='ADD')
            layout.separator()
            layout.label(text="Scene & Sprites (asset browser)", icon='IMAGE_DATA')
            layout.prop(props, "bg_name")
            layout.prop(props, "bg_image")
            layout.operator("upvn.add_scene", icon='SCENE_DATA')
            layout.prop(props, "show_asset")
            layout.prop(props, "show_pos")
            layout.prop(props, "show_trans")
            layout.prop(props, "sprite_image")
            layout.prop(props, "side_image")
            layout.operator("upvn.add_show", icon='OBJECT_DATA')
            layout.operator("upvn.add_stage", icon='MESH_CUBE')
            layout.prop(props, "stage_name")
            layout.separator()
            layout.label(text="Dialogue", icon='SPEAKER')
            layout.prop(props, "speaker")
            layout.prop(props, "dialogue")
            layout.operator("upvn.add_dialogue", icon='ADD')
            layout.separator()
            layout.label(text="Menu (branching)", icon='QUESTION')
            layout.prop(props, "menu_caption")
            layout.prop(props, "menu_choice1")
            layout.prop(props, "menu_jump1")
            layout.prop(props, "menu_choice2")
            layout.prop(props, "menu_jump2")
            layout.operator("upvn.add_menu", icon='ADD')
            layout.separator()
            layout.label(text="Tools", icon='TOOL_SETTINGS')
            row = layout.row(align=True)
            row.operator("upvn.validate", icon='CHECKMARK')
            row.operator("upvn.preview", icon='RENDER_RESULT')
            layout.operator("upvn.save_demo", icon='FILE_TICK')
            layout.prop(props, "arbitrary_slot")
            layout.operator("upvn.preview_arbitrary", icon='IMAGE_REFERENCE')
            layout.label(text="Saves: arbitrary slots 1..∞ (←→ pagination)", icon='INFO')
            layout.label(text="H: history  Q: quick menu  Preserved labels", icon='INFO')

    class UPVN_PT_TextPanel(bpy.types.Panel):
        bl_label = "UPVN — Script"
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
            layout.label(text="Edit script.rpy inside Blender")
            layout.operator("upvn.validate", icon='CHECKMARK')
            layout.operator("upvn.preview", icon='RENDER_RESULT')

    classes = (UPVN_SceneProps, UPVN_OT_LocateEngine, UPVN_OT_CheckEngine, UPVN_OT_BundleEngine,
               UPVN_OT_CreateProject, UPVN_OT_AddCharacter, UPVN_OT_AddScene,
               UPVN_OT_AddDialogue, UPVN_OT_AddShow, UPVN_OT_AddMenu, UPVN_OT_AddStage,
               UPVN_OT_SetupScene, UPVN_OT_Validate,
               UPVN_OT_Preview, UPVN_OT_SaveSlotDemo, UPVN_OT_QuickPreviewArbitrary,
               UPVN_PT_MainPanel, UPVN_PT_TextPanel)

    def register():
        for cls in classes:
            bpy.utils.register_class(cls)
        bpy.types.Scene.upvn_props = bpy.props.PointerProperty(type=UPVN_SceneProps)
        ok, info = ensure_engine(retry=True)
        print(f"[UPVN] Editor addon v0.6 registered — engine: {'OK via ' + str(info['source']) if ok else 'NOT FOUND (' + str(info['message'])[:120] + ')'}")
        print("[UPVN] Panels: View3D > Sidebar > UPVN | Text Editor > Sidebar > UPVN")

    def unregister():
        for cls in reversed(classes):
            try:
                bpy.utils.unregister_class(cls)
            except Exception:
                pass
        try:
            del bpy.types.Scene.upvn_props
        except Exception:
            pass
        print("[UPVN] Editor addon unregistered")

    if __name__ == "__main__":
        register()

# expose builder for headless tests
__all__ = ["UPVN_GameBuilder", "ensure_engine", "engine_diag_text", "engine_status_line",
           "ENGINE_AVAILABLE", "ENGINE_INFO", "bundle_engine_to_addon_dir"]
