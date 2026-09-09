"""
Package the UPVN editor add-on into ONE self-contained, installable .zip.

Usage:
    python tools/package_addon.py [out_dir]        # default: repo dist/

Output: <out_dir>/upvn_editor_addon_v0.6.5.zip

Why this exists (v0.6):
    The old workflow asked you to install a lone .py — Blender copied it into
    its add-ons folder, far from engine/, and every button then failed with
    "Engine not available". The zip ships engine/, bge_frontend/, the playable
    template and the LICENSE together with the add-on.

Zip layout (v0.6.5, single top-level folder):
    upvn_editor_addon/
        __init__.py            <- the add-on (blend/upvn_editor_addon.py)
        engine/…               <- full engine (filesystem discovery after extract)
        bge_frontend/…         <- runtime adapter
        blend/UPVN_Template.blend
        LICENSE
        README-INSTALL.txt

Why no zip-root duplicates anymore: v0.6.0 also placed engine/ + bge_frontend/
at the archive root for zipimport, but when the zip was installed Blender
EXTRACTED them into the add-ons folder, where they were scanned as add-ons and
spammed "add-on missing 'bl_info'" warnings every startup. Blender's normal zip
install extracts the archive, so filesystem discovery is enough. (Dropping the
compressed zip straight into the add-ons folder still works for the panel —
engine discovery reports a clear hint if the engine cannot be imported from
inside the archive.)

Install in UPBGE / Blender:
    Edit → Preferences → Add-ons → Install from Disk… (older UI: Install…) →
    select the .zip → enable "UPVN — Visual Novel Editor".
If you previously installed v0.6.0 by unpacking by hand, remove the leftover
    addons/engine and addons/bge_frontend folders (they were zip-root duplicates
    and are not needed anymore).
Open the UPVN tab (View3D → N → UPVN): Create Project, then (in UPBGE) press
Setup Scene once, then P to play.
"""
from __future__ import annotations

import pathlib
import re
import shutil
import sys
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
ADDON_SRC = ROOT / "blend" / "upvn_editor_addon.py"
BLEND_SRC = ROOT / "blend" / "UPVN_Template.blend"
LICENSE_SRC = ROOT / "LICENSE"

# entries relative to the add-on folder inside the zip
SUB_TREES = ["engine", "bge_frontend"]

IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.blend1", "*.blend2")


def _inject_init(base: pathlib.Path):
    """Make packaged trees regular packages (needed for any zipimport use and
    harmless after extraction)."""
    dirs = [base] + sorted(p for p in base.rglob("*") if p.is_dir())
    for d in dirs:
        if not (d / "__init__.py").exists():
            (d / "__init__.py").write_text("", encoding="utf-8")


def addon_version(addon_py: pathlib.Path) -> str:
    """Read bl_info version tuple like (0, 6, 2) from the add-on source."""
    text = addon_py.read_text(encoding="utf-8")
    m = re.search(r'"version":\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', text)
    if not m:
        raise SystemExit("cannot find bl_info version in " + str(addon_py))
    return ".".join(m.groups())


def build_addon_zip(out_path: pathlib.Path, with_template: bool = True):
    """Create the self-contained add-on zip. Returns Path."""
    if not ADDON_SRC.exists():
        raise SystemExit("add-on source missing: " + str(ADDON_SRC))
    version = addon_version(ADDON_SRC)
    folder = f"upvn_editor_addon_v{version}.zip"
    if out_path.is_dir() or str(out_path).endswith((".zip",)):
        out_path = out_path / folder if out_path.is_dir() else out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="upvn_addon_zip_") as tmp:
        staging = pathlib.Path(tmp)
        addon_dir = staging / "upvn_editor_addon"
        addon_dir.mkdir()

        # 1) the add-on itself as __init__.py
        shutil.copy2(ADDON_SRC, addon_dir / "__init__.py")

        # 2) engine + bge_frontend inside the add-on folder (single-folder zip)
        for tree in SUB_TREES:
            src = ROOT / tree
            if src.is_dir():
                shutil.copytree(src, addon_dir / tree, ignore=IGNORED)
                _inject_init(addon_dir / tree)

        # 3) template + license + readme
        if with_template and BLEND_SRC.exists():
            (addon_dir / "blend").mkdir(parents=True, exist_ok=True)
            shutil.copy2(BLEND_SRC, addon_dir / "blend" / "UPVN_Template.blend")
        shutil.copy2(LICENSE_SRC, addon_dir / "LICENSE")
        readme = (
            "UPVN editor add-on v%s — self-contained install zip\n"
            "====================================================\n"
            "Install:\n"
            "  UPBGE/Blender -> Edit -> Preferences -> Add-ons ->\n"
            "  Install from Disk... -> select this .zip -> enable\n"
            "  \"UPVN — Visual Novel Editor\".\n\n"
            "The engine/ and bge_frontend/ packages travel inside this zip\n"
            "(inside the upvn_editor_addon folder); Blender extracts the zip on\n"
            "install, so no manual engine setup is needed.\n\n"
            "If you previously installed v0.6.0 by unpacking it by hand, remove\n"
            "the leftover  addons/engine  and  addons/bge_frontend  folders —\n"
            "they were zip-root duplicates and are not needed anymore.\n\n"
            "First steps (see README.md in the repo):\n"
            "  1. UPVN tab (View3D sidebar) -> Create Project\n"
            "  2. (UPBGE only) Setup Scene — wires the running scene once\n"
            "  3. Add characters / scenes / dialogue / menus with clicks\n"
            "  4. Validate -> checks your script;  Preview -> screenshot\n"
            "  5. Press P to play.\n\n"
            "Template blend inside: blend/UPVN_Template.blend\n"
            "License: MIT (see LICENSE).\n"
        ) % version
        (addon_dir / "README-INSTALL.txt").write_text(readme, encoding="utf-8")

        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(staging.rglob("*")):
                if not p.is_file():
                    continue
                zf.write(p, p.relative_to(staging).as_posix())
        n = len(zipfile.ZipFile(out_path).namelist())
        size_kb = out_path.stat().st_size // 1024
    print(f"[package_addon] {out_path} — {n} entries, {size_kb}KB (single-folder, v{version})")
    return out_path


if __name__ == "__main__":
    arg = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "dist"
    out = build_addon_zip(arg)
    print(f"[package_addon] OK -> {out}")
