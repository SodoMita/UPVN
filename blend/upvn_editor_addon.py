"""
UPVN Blender Editor Tools — create visual novel inside Blender with minimal coding
v0.6.11 (2026-09-09): mouse visible, ortho 15, zoom-stable UI, placeholder art, no LibLoad crash

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
        dist/upvn_editor_addon_v0.6.11.zip  → Edit → Preferences → Add-ons →
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
    "version": (0, 6, 12),
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
    #    NB: some UPBGE builds expose no bpy.data.filepath during startup
    #    (AttributeError seen in the field) — never let this crash discovery.
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
    """Member path of engine/script/parser.py inside the zip, or None.

    Returns 'engine/script/parser.py' when the engine sits at the zip root
    (importable via zipimport), or e.g. 'upvn_editor_addon/engine/script/parser.py'
    when it is nested in the add-on folder (needs extraction to import)."""
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
    """Locate and import the engine. Idempotent; retry=True re-scans.
    NEVER raises — returns (ok: bool, ENGINE_INFO dict) in every case.
    Public API used by tests + operators."""
    global ENGINE_INFO, _engine_api, ENGINE_AVAILABLE
    if ENGINE_AVAILABLE and not retry:
        return True, ENGINE_INFO
    # forget previous partial state when retrying
    ENGINE_AVAILABLE = False
    _engine_api = None
    searched = []
    info = {"status": "not_found", "root": None, "source": None,
            "message": "", "searched": searched}
    nested_zip_hint = None
    try:
        candidates = _engine_candidates()
    except Exception as exc:          # discovery itself must never crash
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
                    continue          # nested engine: only importable after extraction
            if not _candidate_is_engine(kind, path):
                continue
        except Exception:
            continue                  # a broken candidate must not stop the scan
        try:
            _add_to_syspath(kind, path)
            _p, _vc, _sm = _import_engine_api()
            info.update(status="ok", root=path, source=desc,
                        message=f"engine found via {desc}")
            _engine_api = (_p, _vc, _sm)
            ENGINE_AVAILABLE = True
        except Exception as exc:      # engine present but broken (missing dep…)
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
        lines.append(f"  root:   {info['root']}")
        lines.append(f"  source: {info['source']}")
    else:
        lines.append(f"  reason: {info['message']}")
        for s in info.get("searched", []):
            lines.append(f"  looked: {s}")
    return "\n".join(lines)


def pil_live_available():
    """Live probe for Pillow in the CURRENT interpreter. A static HAS_PIL flag
    goes stale when the user installs Pillow mid-session (Python caches failed
    imports at module level), so every preview attempt re-checks with a real
    import. Returns True/False, never raises."""
    try:
        import PIL  # noqa: F401
        return True
    except Exception:
        return False


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
        self.last_error: str | None = None
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
        """Headless screenshot via headless_renderer. Returns Path or None;
        on failure the reason is stored in self.last_error."""
        self.last_error = None
        if not ENGINE_AVAILABLE or _engine_api is None:
            self.last_error = "engine not found"
            return None
        try:
            from engine.render.headless_renderer import render_state
        except ImportError as e:
            self.last_error = f"headless renderer import failed: {e}"
            return None
        if not pil_live_available():
            self.last_error = ("Pillow (PIL) is not visible to this Python "
                               "interpreter — press 'Install Pillow' in the UPVN panel "
                               "(if you already did, restart Blender/UPBGE once)")
            return None
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
                self.last_error = f"script parse failed: {e}"
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
        try:
            img = render_state(state, ev, pathlib.Path(out_path))
        except Exception as e:
            self.last_error = f"rendering failed: {e}"
            return None
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

    def _upbge_python_path():
        """Path to the Python interpreter bundled with UPBGE/Blender, or None."""
        import glob as _glob
        if bpy is None:
            return None
        try:
            base = pathlib.Path(bpy.app.binary_path).resolve().parent
        except Exception:
            return None
        for rel in ("5.0", "4.5", "4.6", "python"):
            for name in ("python3.11", "python3.10", "python3.9"):
                c = base / rel / "python" / "bin" / name
                if c.exists():
                    return str(c)
        for rel in ("5.0", "python"):
            hits = sorted(_glob.glob(str(base / rel / "python" / "bin" / "python3*")))
            if hits:
                return hits[-1]
        return None

    class UPVN_OT_InstallPillow(bpy.types.Operator):
        bl_idname = "upvn.install_pillow"
        bl_label = "Install Pillow (Preview)"
        bl_description = ("Install Pillow into UPBGE's bundled Python so 'Preview' can render "
                          "PNG screenshots (Preview needs Pillow; the game itself does not)")

        def execute(self, context):
            py = _upbge_python_path()
            if not py:
                self.report({"ERROR"}, "Bundled Python of UPBGE not found next to " +
                            str(getattr(bpy.app, "binary_path", "")))
                return {"FINISHED"}
            import subprocess
            # Install into the site-packages of the RUNNING interpreter (already
            # on sys.path), so the package becomes visible without a restart.
            target = None
            try:
                import sysconfig
                target = sysconfig.get_paths().get("purelib")
            except Exception:
                target = None
            cmd = [py, "-m", "pip", "install", "pillow"]
            if target:
                cmd += ["--target", target]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            except Exception as e:
                self.report({"ERROR"}, f"pip failed: {e}")
                return {"FINISHED"}
            if r.returncode == 0:
                # verify: does the RUNNING interpreter see it now?
                if pil_live_available():
                    self.report({"INFO"}, "Pillow installed and visible — Preview should work now.")
                else:
                    self.report({"WARNING"},
                                "Pillow installed into the bundled Python, but this Blender "
                                "session does not see it yet — restart Blender/UPBGE once, then Preview.")
            else:
                tail = (r.stderr or r.stdout or "").strip().splitlines()
                self.report({"ERROR"}, "pip install failed: " + ("; ".join(tail[-3:]) if tail else "?"))
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

    def _data_plane(name, size=10.0, color=(0.06, 0.06, 0.09, 1.0), rot=None):
        """Plane mesh + material via data API (no bpy.ops). Default rot = stand in XZ."""
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
        if rot is None:
            rot = (1.5707963267948966, 0.0, 0.0)
        obj.rotation_euler = rot
        obj.data.materials.append(mat)
        return obj

    def _rewrite_unlit(mat, color):
        """Emission-only, texture-free — VN planes must not pick up scene
        lights, and their color is driven at runtime via KX_GameObject.color.

        M26: the node graph is Output ← Emission ← Object Info *Color*. The
        rasterizer multiplies the object's color into the emission, so
        palette code (engine/render/contract.py::apply_object_color) paints
        every stage/sprite/plate without any image texture. `color` seeds the
        matching object's default tint (build_vn_scene assigns it) and also
        stays as the material's fallback if an object never sets a color.
        The old TexImage node is gone on purpose: UPBGE 0.50's bge.texture
        cannot bind node materials ("Texture is not available"), an unassigned
        TexImage evaluated black (BUG-005), and the palette makes images
        optional (image_mode="color" for the template and all samples)."""
        mat.use_nodes = True
        nt = mat.node_tree
        try:
            nt.nodes.clear()
        except Exception:
            pass
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        objinfo = nt.nodes.new("ShaderNodeObjectInfo")
        try:
            em.inputs["Color"].default_value = color
            em.inputs["Strength"].default_value = 1.0
        except Exception:
            pass
        try:
            nt.links.new(objinfo.outputs["Color"], em.inputs["Color"])
        except Exception:
            pass
        nt.links.new(em.outputs[0], out.inputs[0])
        for attr, val in (("blend_method", "OPAQUE"), ("shadow_method", "NONE"),
                          ("use_backface_culling", False)):
            try:
                setattr(mat, attr, val)
            except Exception:
                pass
        return mat

    def _data_text(name, body="", size=0.32, loc=(0, -0.55, -3.0), rot=None):
        curve = bpy.data.curves.new(name + "_font", "FONT")
        curve.body = body
        curve.size = size
        try:
            curve.align_x = "LEFT"
            curve.align_y = "TOP"
        except Exception:
            pass
        obj = bpy.data.objects.new(name, curve)
        obj.location = loc
        obj.rotation_euler = rot if rot is not None else (1.5707963267948966, 0.0, 0.0)
        return obj

    def _static_ghost(obj):
        """Static, ray-hittable physics for VN plates.

        M26: physics_type "SENSOR" objects are NOT detected by
        KX_GameObject.rayCast in UPBGE 0.50 (measured in-field: every choice
        click missed). STATIC + BOX collision bounds makes choice plates,
        sprites and planes hittable for the pointer ray while staying
        immovable."""
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

    def build_vn_scene(bpy_module=None, *, scene_name=None,
                       script_path="//game/script.rpy",
                       controller_module="upvn_launcher",
                       install_launcher=True):
        """Create/refresh a complete playable UPVN scene (data API, idempotent).

        Default scene_name=None uses the OPEN scene (context.scene). Creating a
        separate VN_Main left the template Scene without choice_* (field: 18/27).

        Safe to press repeatedly. Returns the controller object.
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

        # camera — always re-apply the Front/ortho transform unless the user
        # tagged the object upvn_camera_custom. Existing Camera_UI at the old
        # (0,-10,5) pose looked at XY planes edge-on and was never bound.
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
            DIALOGUE_LOCATION = (0.0, -0.4, -3.2)
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
        # hide leftover factory cameras so P cannot pick the wrong one
        for ob in list(scene.objects):
            try:
                if ob.type == "CAMERA" and ob.name not in (CAMERA_UI, CAMERA_3D):
                    ob.hide_viewport = True
                    ob.hide_render = True
            except Exception:
                pass
        # 3D view → camera (so the editor matches what P will show)
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

        # placeholder planes (only when missing — don't destroy user art)
        # names/materials follow engine/render/contract.py (single source)
        try:
            from engine.render.contract import (BG_PLANE, BG_MATERIAL,
                                                SPRITE_MATERIAL, SPRITE_POSITIONS,
                                                POSITIONS, DIALOGUE_PLANE,
                                                IMAGE_MODE_DEFAULT)
        except Exception:
            BG_PLANE, BG_MATERIAL = "BG_Plane", "MABackground"
            SPRITE_MATERIAL, DIALOGUE_PLANE = "MASprite", "Dialogue_Box"
            IMAGE_MODE_DEFAULT = "color"
            SPRITE_POSITIONS = ("far_left", "left", "center", "right", "far_right")
            POSITIONS = {p: ({"far_left": -5.0, "left": -3.0, "center": 0.0,
                              "right": 3.0, "far_right": 5.0}[p], -0.15, 0.0)
                         for p in SPRITE_POSITIONS}

        def _ensure_material(_b, name, color):
            mat = _b.data.materials.get(name)
            if mat is None:
                mat = _b.data.materials.new(name)
            _rewrite_unlit(mat, color)
            return mat

        mat_bg = _ensure_material(_b, BG_MATERIAL, (0.12, 0.14, 0.22, 1.0))
        mat_sprite = _ensure_material(_b, SPRITE_MATERIAL, (0.62, 0.78, 0.55, 1.0))
        mat_ui = _ensure_material(_b, "MAUI", (0.05, 0.06, 0.14, 1.0))
        mat_choice = _ensure_material(_b, "MAChoice", (0.12, 0.18, 0.32, 1.0))
        mat_font = _ensure_material(_b, "MAFont", (0.92, 0.93, 1.0, 1.0))

        def _single_material(ob, mat):
            """Replace the plane's default material with the contract one so the
            object exposes exactly one material slot, named per the contract."""
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
            """Seed the object color that M26 materials multiply into emission
            (Object Info -> Color). Runtime palette code overwrites it freely."""
            try:
                ob.color = color
            except Exception:
                pass
            return ob

        bg = scene.objects.get(BG_PLANE)
        if bg is None:
            bg = _data_plane(BG_PLANE, size=10.0, rot=PLANE_ROTATION)
            _single_material(bg, mat_bg)
            scene.collection.objects.link(bg)
            collections["VN_Backgrounds"].objects.link(bg)
        _apply_2d_layout(bg, (0.0, 0.0, 0.0))
        _single_material(bg, mat_bg)
        _tint(bg, (0.12, 0.14, 0.22, 1.0))
        dlg = scene.objects.get(DIALOGUE_PLANE)
        if dlg is None:
            dlg = _data_plane(DIALOGUE_PLANE, size=8.0, color=(0.05, 0.05, 0.12, 1.0),
                              rot=PLANE_ROTATION)
            scene.collection.objects.link(dlg)
            collections["VN_UI"].objects.link(dlg)
        _apply_2d_layout(dlg, DIALOGUE_LOCATION, DIALOGUE_SCALE)
        _single_material(dlg, mat_ui)
        _tint(dlg, (0.05, 0.06, 0.14, 1.0))
        _static_ghost(bg)
        _static_ghost(dlg)

        try:
            from engine.render.contract import (SPEAKER_TEXT, DIALOGUE_TEXT,
                                                SPEAKER_LOCATION, DIALOGUE_TEXT_LOCATION,
                                                CHOICE_COUNT, CHOICE_PREFIX)
        except Exception:
            SPEAKER_TEXT, DIALOGUE_TEXT = "Speaker_Text", "Dialogue_Text"
            SPEAKER_LOCATION = (-3.6, -0.55, -2.55)
            DIALOGUE_TEXT_LOCATION = (-3.6, -0.55, -3.15)
            CHOICE_COUNT, CHOICE_PREFIX = 9, "choice_"

        def _ensure_font(name, loc, size=0.32):
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
            _tint(ob, (0.92, 0.93, 1.0, 1.0))
            _static_ghost(ob)
            return ob

        _ensure_font(SPEAKER_TEXT, SPEAKER_LOCATION, size=0.28)
        _ensure_font(DIALOGUE_TEXT, DIALOGUE_TEXT_LOCATION, size=0.26)

        for i in range(CHOICE_COUNT):
            z = 2.4 - i * 0.7
            loc = (0.0, -0.5, z)
            cname = f"{CHOICE_PREFIX}{i}"
            try:
                def _mk(cname=cname):
                    return _data_plane(cname, size=6.0, color=(0.12, 0.18, 0.32, 1.0),
                                       rot=PLANE_ROTATION)
                ch = _get_or_create(scene, cname, _mk)
                _link_ob(scene, ch, collections["VN_UI"])
                _apply_2d_layout(ch, loc, (3.2, 0.28, 1.0))
                _single_material(ch, mat_choice)
                _tint(ch, (0.12, 0.18, 0.32, 1.0))
                _static_ghost(ch)
                tname = cname + "_text"
                _ensure_font(tname, (loc[0] - 2.8, loc[1] - 0.05, loc[2] + 0.08), size=0.24)
            except Exception as exc:
                print(f"[UPVN] choice {cname} create failed: {exc}")

        for ob in list(scene.objects):
            try:
                if ob.type == "LIGHT":
                    ob.hide_viewport = True
                    ob.hide_render = True
            except Exception:
                pass
        try:
            world = scene.world
            if world is not None and getattr(world, "use_nodes", False):
                bg_n = world.node_tree.nodes.get("Background")
                if bg_n:
                    bg_n.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
                    bg_n.inputs[1].default_value = 0.0
        except Exception:
            pass

        # sprite planes per position (SpriteRenderer looks these up by name)
        for pos in SPRITE_POSITIONS:
            name = f"Sprite_{pos}"
            loc = POSITIONS.get(pos, (0.0, -0.15, 0.0))
            sp = scene.objects.get(name)
            if sp is None:
                sp = _data_plane(name, size=4.0, color=(0.62, 0.78, 0.55, 1.0),
                                 rot=PLANE_ROTATION)
                _single_material(sp, mat_sprite)
                scene.collection.objects.link(sp)
                collections["VN_Characters"].objects.link(sp)
            _apply_2d_layout(sp, loc, SPRITE_SCALE)
            _single_material(sp, mat_sprite)
            _tint(sp, (0.62, 0.78, 0.55, 1.0))
            _static_ghost(sp)
            try:
                sp.hide_render = False
            except Exception:
                pass

        # VNController empty — reuse the existing object when present (UPBGE's
        # brick collections have no .remove(), so deleting/recreating the object
        # is impossible without the logic UI operators; reuse keeps it simple and
        # idempotent)
        ctrl = scene.objects.get("VNController")
        created = ctrl is None
        if ctrl is None:
            ctrl = _b.data.objects.new("VNController", None)
            ctrl.empty_display_type = "CUBE"
            scene.collection.objects.link(ctrl)
        # M26: never clobber a configured script_path with the default —
        # keep the blend's existing value when the caller passes the default
        # (panel default / API default). See UPVN_OT_SetupScene.execute.
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
        # M26: image policy for the renderers — "color" (texture-free palette,
        # template + samples) or "auto" (converted Ren'Py projects).
        _set_runtime_prop(_b, ctrl, "image_mode", IMAGE_MODE_DEFAULT)
        # relative root to the folder that contains engine/ (launcher falls back
        # to the blend dir + parents when this is empty/stale)
        try:
            blend_dir = os.path.dirname(os.path.abspath(_b.path.abspath("//"))) if _b.data.filepath else None
        except Exception:
            blend_dir = None
        _set_runtime_prop(_b, ctrl, "upvn_root", _engine_root_relative(blend_dir))

        # --- logic bricks (UPBGE only) ---
        # UPBGE 0.50 exposes brick editing through bpy.ops.logic.* (the same
        # operators UPBGE's own add-ons use) — the RNA collections themselves are
        # read-only and lack .remove(). bpy.ops.logic requires an interactive
        # UI/GL context, so in --background mode we skip adding bricks and say so
        # loudly. Existing bricks are never touched: Setup Scene is idempotent and
        # preserves a working wiring when the object already has it.
        _set_runtime_prop(_b, ctrl, "upvn_bricks", "no")
        if has_game and install_launcher:
            launcher = _b.data.texts.get("upvn_launcher")
            if launcher is None:
                launcher = _b.data.texts.new("upvn_launcher")
            launcher.clear()
            launcher.write(_UPVN_LAUNCHER_TEXT)
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


    def _set_runtime_prop(_b, obj, name, value):
        """Write a property that is visible in the editor AND at game runtime.

        M25 BUG-009: in UPBGE 0.50 the player's KX_GameObject only exposes
        entries of obj.game.properties ("Game Properties"); plain ID custom
        properties (obj[name]) are invisible at runtime, so a blend carrying
        script_path as a bare custom property silently fell back to the
        candidate list and never loaded the project's script. The editor UI
        keeps reading the custom property, so write both representations.
        """
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
        """Wire Always(pulse)+AllKeys+Mouse -> Python(launcher) via bpy.ops.logic.*.

        AllKeys is required in the embedded player (P): without it Blender eats
        keystrokes while LMB still reaches bge.logic.mouse.

        Returns 'yes' | 'skipped-background' | 'error: …' | 'already'.
        """
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
                    con.text = launcher_text      # SCRIPT mode, Text datablock
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
            # M26: the blend's own VNController.script_path is the source of
            # truth ("the game you build is the game that plays"). When the
            # panel still carries the default, adopt the blend's value instead
            # of overwriting it — Setup Scene used to clobber a configured
            # path (e.g. '//../examples/20_smoke_game/script.rpy') back to
            # '//game/script.rpy', and pressing P then played the fallback
            # demo. The panel field is synced so both stay consistent.
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
                            "Scene wired: VNController + Always→Python launcher brick. Press P to play.")
            elif bricks == "existing":
                self.report({"INFO"},
                            "Scene wiring already present and intact (nothing changed). "
                            "script_path set — press P to play.")
            elif isinstance(bricks, str) and bricks.startswith("skipped"):
                self.report({"WARNING"},
                            "Scene objects created, but logic bricks need the UPBGE UI: "
                            "run Setup Scene again from this panel (not --background).")
            elif isinstance(bricks, str) and bricks.startswith("error"):
                self.report({"ERROR"}, f"Brick wiring failed: {bricks}")
            else:
                self.report({"INFO"},
                            "Scene objects refreshed. Press P to play (or run Setup Scene "
                            "inside the UPBGE UI for the full brick wiring).")
            print("[UPVN] Setup Scene done. script_path=", p.project_path, "| bricks:", bricks)
            return {"FINISHED"}

    class UPVN_OT_CheckWiring(bpy.types.Operator):
        bl_idname = "upvn.check_wiring"
        bl_label = "Check Scene Wiring"
        bl_description = ("Compare the open scene against the engine's object contract "
                          "(engine/render/contract.py) and report missing items by name")

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
                reason = getattr(builder, "last_error", None)
                ok, _info = ensure_engine()
                if not ok:
                    self.report({'ERROR'}, "Engine not found — install the UPVN .zip release or set engine folder in add-on preferences.")
                elif reason:
                    self.report({'ERROR'}, "Preview failed: " + str(reason)[:250])
                    print("[UPVN] preview error:", reason)
                else:
                    self.report({'ERROR'}, "Preview failed — see console.")
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
            except ImportError as e:
                self.report({'ERROR'}, f"headless renderer import failed: {e}")
                return {'FINISHED'}
            if not pil_live_available():
                self.report({'ERROR'},
                            "Pillow (PIL) is not visible to this Python — press 'Install Pillow' "
                            "in the UPVN panel (restart Blender/UPBGE after installing).")
                return {'FINISHED'}
            try:
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
                row = box.row(align=True)
                row.operator("upvn.setup_scene", icon='WINDOW')
                row.operator("upvn.check_wiring", icon='VIEWZOOM')
                box.label(text="Setup Scene creates every object the engine expects by name", icon='INFO')
                box.label(text="Check Wiring compares the scene with engine/render/contract.py", icon='INFO')
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
            row.operator("upvn.check_wiring", icon='VIEWZOOM')
            layout.operator("upvn.save_demo", icon='FILE_TICK')
            layout.operator("upvn.install_pillow", icon='CONSOLE',
                            text="Install Pillow (for Preview)")
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
               UPVN_OT_InstallPillow,
               UPVN_OT_CreateProject, UPVN_OT_AddCharacter, UPVN_OT_AddScene,
               UPVN_OT_AddDialogue, UPVN_OT_AddShow, UPVN_OT_AddMenu, UPVN_OT_AddStage,
               UPVN_OT_SetupScene, UPVN_OT_CheckWiring, UPVN_OT_Validate,
               UPVN_OT_Preview, UPVN_OT_SaveSlotDemo, UPVN_OT_QuickPreviewArbitrary,
               UPVN_PT_MainPanel, UPVN_PT_TextPanel)

    def register():
        try:
            for cls in classes:
                bpy.utils.register_class(cls)
            bpy.types.Scene.upvn_props = bpy.props.PointerProperty(type=UPVN_SceneProps)
            ok, info = ensure_engine(retry=True)
            ver = ".".join(str(x) for x in bl_info.get("version", ()))
            print(f"[UPVN] Editor addon v{ver} registered — engine: {'OK via ' + str(info['source']) if ok else 'NOT FOUND (' + str(info['message'])[:120] + ')'}")
            print("[UPVN] Panels: View3D > Sidebar > UPVN | Text Editor > Sidebar > UPVN")
        except Exception as exc:      # never let an add-on enable crash Blender startup
            print(f"[UPVN] register() error (add-on partially enabled): {exc}")
            try:
                import traceback
                traceback.print_exc()
            except Exception:
                pass

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
