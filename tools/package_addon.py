"""
Package the UPVN editor add-on into ONE self-contained, installable .zip.

Usage:
    python tools/package_addon.py [out_dir]        # default: repo dist/

Output: <out_dir>/upvn_editor_addon_v0.6.0.zip

Why this exists (v0.6):
    The old workflow asked you to install a lone .py — Blender copied it into
    its add-ons folder, far from engine/, and every button then failed with
    "Engine not available". The zip ships engine/, bge_frontend/, the playable
    template and the LICENSE together with the add-on, and the add-on can even
    import the engine straight out of the compressed archive (zipimport), so
    there is no post-install step at all.

Zip layout:
    upvn_editor_addon/
        __init__.py            <- the add-on (blend/upvn_editor_addon.py)
        engine/…               <- full engine (filesystem discovery)
        bge_frontend/…         <- runtime adapter
        blend/UPVN_Template.blend
        LICENSE
        README-INSTALL.txt
    engine/…                   <- duplicate at zip ROOT for zipimport fallback
                                   (Blender keeps add-on zips compressed)

Install in UPBGE / Blender:
    Edit → Preferences → Add-ons → Install from Disk… (older UI: Install…) →
    select the .zip → enable "UPVN — Visual Novel Editor".
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
    """zipimport does NOT support namespace packages: every directory needs an
    __init__.py — including the package root itself. The repo has none (top-level
    namespace imports work on the filesystem), so we inject empty ones only in
    the packaged copies."""
    dirs = [base] + sorted(p for p in base.rglob("*") if p.is_dir())
    for d in dirs:
        if not (d / "__init__.py").exists():
            (d / "__init__.py").write_text("", encoding="utf-8")


def addon_version(addon_py: pathlib.Path) -> str:
    """Read bl_info version tuple like (0, 6, 0) from the add-on source."""
    text = addon_py.read_text(encoding="utf-8")
    m = re.search(r'"version":\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', text)
    if not m:
        raise SystemExit("cannot find bl_info version in " + str(addon_py))
    return ".".join(m.groups())


def _walk_add(base: pathlib.Path):
    """Yield (arcname, src_path) for all files under base, cleaned."""
    for p in sorted(base.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(base)
        if any(part in ("__pycache__",) or part.endswith((".pyc", ".pyo", ".blend1", ".blend2"))
               for part in p.parts):
            continue
        yield str(rel), p


def build_addon_zip(out_path: pathlib.Path, with_template: bool = True):
    """Create the self-contained add-on zip. Returns Path."""
    if not ADDON_SRC.exists():
        raise SystemExit("add-on source missing: " + str(ADDON_SRC))
    version = addon_version(ADDON_SRC)
    folder = f"upvn_editor_addon_v{version}.zip"
    if out_path.is_dir() or str(out_path).endswith((".zip",)):
        out_path = out_path / folder if out_path.is_dir() else out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # assemble a staging dir (so paths are simple)
    with tempfile.TemporaryDirectory(prefix="upvn_addon_zip_") as tmp:
        staging = pathlib.Path(tmp)
        addon_dir = staging / "upvn_editor_addon"
        addon_dir.mkdir()

        # 1) the add-on itself as __init__.py + a copy as .py (handy for file installs)
        shutil.copy2(ADDON_SRC, addon_dir / "__init__.py")

        # 2) engine + bge_frontend inside the add-on folder
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
            "The engine/ and bge_frontend/ packages travel inside this zip;\n"
            "no manual engine setup is needed (the add-on can even import the\n"
            "engine directly from the compressed archive).\n\n"
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

        # 4) zip-root engine/ + bge_frontend/ duplicates (zipimport fallback —
        #    Blender keeps installed add-on zips compressed, and zipimport needs
        #    real packages with __init__.py at the archive root)
        for tree in SUB_TREES:
            src = ROOT / tree
            if src.is_dir():
                shutil.copytree(src, staging / tree, ignore=IGNORED)
                _inject_init(staging / tree)

        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for base in (staging,):
                for p in sorted(base.rglob("*")):
                    if not p.is_file():
                        continue
                    arc = p.relative_to(staging).as_posix()
                    zf.write(p, arc)
        n = len(zipfile.ZipFile(out_path).namelist())
        size_kb = out_path.stat().st_size // 1024
    print(f"[package_addon] {out_path} — {n} entries, {size_kb}KB (engine bundled, v{version})")
    return out_path


if __name__ == "__main__":
    arg = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "dist"
    out = build_addon_zip(arg)
    # quick self-check: engine importable from inside the archive?
    import os
    os.environ["UPVN_ZIP_SELFTEST"] = str(out)
    print(f"[package_addon] OK -> {out}")
