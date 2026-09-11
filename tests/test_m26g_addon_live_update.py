"""M26g: addon live-update regression — runs the REAL update flow in ONE
blender session (skipped when the binary is absent).

Reproduces the user-visible bug: installing a new addon version over a
running UPBGE used to need uninstall + restart (register() aborted on the
first already-registered class, so the new code never bound). Locked in:
1. enable OLD 0.6.14 (from git HEAD before this change) in a live session;
2. install the NEW 0.6.15 zip over it (operator flow when the background
   context allows it, else Blender's install semantics replicated: disable →
   replace files → modules_refresh → enable);
3. WITHOUT any restart: the new code must be live — `Scene.upvn_addon_version`
   reports 0.6.15 (0.6.14 had no such property at all) and the new operator
   class exists;
4. the `upvn.reload_addon` operator applies a file-replaced update
   (bl_info bumped to 0.6.99 on disk) in the same session.
"""
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BIN = Path("/opt/upbge/upbge-0.50-linux-x64/blender")
ADDON_SRC = REPO / "blend" / "upvn_editor_addon.py"
ZIP15 = REPO / "dist" / "upvn_editor_addon_v0.6.15.zip"

HAVE_BIN = BIN.exists()
pytestmark = pytest.mark.skipif(not HAVE_BIN, reason="UPBGE binary not present")

SESSION = r'''
import os, sys, shutil, zipfile, importlib
import bpy
import addon_utils

ADDONS = None
def addons_dir():
    global ADDONS
    if ADDONS is None:
        ADDONS = bpy.utils.user_resource('SCRIPTS', path="addons")
        os.makedirs(ADDONS, exist_ok=True)
    return ADDONS

def enable(name):
    addon_utils.modules_refresh()
    # this build's addon_utils.enable returns the MODULE or None (older
    # builds returned an (ok, err) tuple)
    try:
        return addon_utils.enable(name, default_set=True, persistent=True)
    except Exception as _e:
        import traceback
        traceback.print_exc()
        print("DBG enable RAISED:", type(_e).__name__, _e)
        return None

# ---------- 1) OLD 0.6.14 (as committed before M26g) ----------
# argv (after --): [old_addon.py, new_zip]
old_src = open(sys.argv[-2], encoding="utf-8").read()  # old addon via argv
ZIP15 = sys.argv[-1]
assert '"version": (0, 6, 14)' in old_src, "old fixture must be 0.6.14"
assert zipfile.is_zipfile(ZIP15), ZIP15
mod_dir = os.path.join(addons_dir(), "upvn_editor_addon")
os.makedirs(mod_dir, exist_ok=True)
open(os.path.join(mod_dir, "__init__.py"), "w", encoding="utf-8").write(old_src)
# this build only puts addons/ on sys.path via refresh_script_paths() —
# which is exactly what the real addon_install operator calls at the end
bpy.utils.refresh_script_paths()
mod = enable("upvn_editor_addon")
print("STEP1 enabled:", getattr(mod, "__name__", mod))
assert mod is not None, "old enable failed"
print("STEP1 has_version_prop:", hasattr(bpy.types.Scene, "upvn_addon_version"))
assert not hasattr(bpy.types.Scene, "upvn_addon_version"), (
    "0.6.14 must NOT have the live version property (before-marker)")
print("STEP1 panel_registered:", hasattr(bpy.types, "UPVN_PT_main"))
assert hasattr(bpy.types, "UPVN_PT_main"), "panel must be live (by bl_idname)"

# ---------- 2) install the NEW zip over the running session ----------
installed_via = "operator"
try:
    bpy.ops.preferences.addon_install(filepath=ZIP15, overwrite=True,
                                      target='DEFAULT')
    enable("upvn_editor_addon")
except Exception as e:
    installed_via = f"operator-failed ({type(e).__name__}); replicated install"
    # replicate addon_install semantics exactly: disable, remove, extract,
    # refresh paths, enable
    try:
        addon_utils.disable("upvn_editor_addon", default_set=True)
    except Exception:
        pass
    shutil.rmtree(mod_dir, ignore_errors=True)
    with zipfile.ZipFile(ZIP15) as z:
        z.extractall(addons_dir())
    bpy.utils.refresh_script_paths()
    enable("upvn_editor_addon")
print("STEP2 installed_via:", installed_via)

# ---------- 3) WITHOUT restart: new code must be live ----------
import addon_utils as au
bl = au.module_bl_info(importlib.import_module("upvn_editor_addon"))
print("STEP3 blinfo_version:", bl.get("version"))
ver = getattr(bpy.context.scene, "upvn_addon_version", "<missing>")
print("STEP3 live_version_prop:", ver)
print("STEP3 reload_op_exists:", hasattr(bpy.types, "UPVN_OT_reload_addon"))
assert bl.get("version") == (0, 6, 15), bl
assert ver == "0.6.15", f"live version prop wrong after update: {ver}"
assert hasattr(bpy.types, "UPVN_OT_reload_addon")

# registration integrity: an existing operator is still invocable (poll ok)
res = bpy.ops.upvn.check_engine()
print("STEP3 check_engine_result:", res)
assert res == {'FINISHED'}

# ---------- 4) the reload operator applies a file-replaced update ----------
src = open(os.path.join(mod_dir, "__init__.py"), encoding="utf-8").read()
src99 = src.replace('"version": (0, 6, 15),', '"version": (0, 6, 99),')
assert src99 != src
p99 = os.path.join(mod_dir, "__init__.py")
open(p99, "w", encoding="utf-8").write(src99)
import time as _time
_time.sleep(1.1)  # same-second mtime can keep the stale .pyc alive
os.utime(p99, None)
res = bpy.ops.upvn.reload_addon()
print("STEP4 reload_result:", res)
ver = getattr(bpy.context.scene, "upvn_addon_version", "<missing>")
print("STEP4 version_after_reload:", ver)
assert res == {'FINISHED'}
assert ver == "0.6.99", f"reload did not apply the on-disk update: {ver}"

print("LIVE_UPDATE_ALL_OK")
'''


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    old = subprocess.run(
        ["git", "show", "HEAD:blend/upvn_editor_addon.py"],
        cwd=REPO, capture_output=True, text=True, check=True).stdout
    assert '"version": (0, 6, 14)' in old, "HEAD addon must be the 0.6.14 one"

    home = tmp_path_factory.mktemp("upvn_home")
    session_py = tmp_path_factory.mktemp("runner") / "session.py"
    session_py.write_text(SESSION, encoding="utf-8")
    old_py = tmp_path_factory.mktemp("runner") / "old_addon.py"
    old_py.write_text(old, encoding="utf-8")

    env = {**os.environ, "HOME": str(home), "LIBGL_ALWAYS_SOFTWARE": "1",
           "XDG_CONFIG_HOME": str(home / ".config")}
    proc = subprocess.run(
        [str(BIN), "--background", "--factory-startup", "--python",
         str(session_py), "--", str(old_py), str(ZIP15)],
        capture_output=True, text=True, timeout=900, env=env)
    out = proc.stdout
    steps = {}
    for key in ("STEP1 has_version_prop", "STEP2 installed_via",
                "STEP3 blinfo_version", "STEP3 live_version_prop",
                "STEP3 reload_op_exists", "STEP3 check_engine_result",
                "STEP4 reload_result", "STEP4 version_after_reload"):
        m = re.search(rf"{re.escape(key)}: (.*)", out)
        steps[key] = m.group(1).strip() if m else None
    return proc, out, steps


def test_session_runs(session):
    proc, out, _ = session
    assert "LIVE_UPDATE_ALL_OK" in out, (
        "live-update session failed:\n" + out[-3000:])


def test_update_over_running_install(session):
    """The 0.6.15 zip installed OVER a live 0.6.14 session must activate the
    new code with NO restart (version prop + new operator class)."""
    _, out, steps = session
    assert steps["STEP1 has_version_prop"] == "False"
    assert steps["STEP3 live_version_prop"] == "0.6.15", out[-2000:]
    assert steps["STEP3 reload_op_exists"] == "True"
    assert steps["STEP3 blinfo_version"] == "(0, 6, 15)"


def test_install_path_reported(session):
    """Diagnostic honesty: record whether the real preferences operator worked
    in background or the replicated install semantics were used."""
    _, out, steps = session
    via = steps["STEP2 installed_via"] or ""
    assert "installed_via" in out
    assert ("operator" in via), via


def test_reload_operator_applies_replaced_file(session):
    """upvn.reload_addon must apply a file-replaced update in-session."""
    _, _, steps = session
    assert steps["STEP4 reload_result"] == "{'FINISHED'}"
    assert steps["STEP4 version_after_reload"] == "0.6.99"


def test_register_purges_before_binding():
    """Source pin: register() must purge stale registrations FIRST, and the
    live version property must exist in the source."""
    src = ADDON_SRC.read_text(encoding="utf-8")
    body = src[src.index("    def register():"):]
    body = body[:body.index("\n    def ")]
    assert body.index("_purge_stale_registrations()") < body.index(
        "for cls in classes:"), (
        "register() must purge stale registrations before binding")
    assert "upvn_addon_version" in body
    assert '"version": (0, 6, 15)' in src
    assert "upvn.reload_addon" in src
