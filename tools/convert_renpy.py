#!/usr/bin/env python3
"""
UPVN — Ren'Py project → UPVN project converter (no image textures)

Takes a real Ren'Py project (a folder containing `game/` with .rpy/.rpym)
and produces a UPVN project that can be opened in Blender/UPBGE and played
headlessly.

Key design: **no image textures required**. Ren'Py `image` / `scene` / `show`
statements reference PNG/WebP files; UPVN now renders all planes as solid
emission colours via the palette in engine/render/contract.py (object.color
on white materials). This makes the converted game run identically on
llvmpipe (GL) and lavapipe (Vulkan) software renderers — no GPU, no image
decoding, no `bge.texture` `Texture is not available` failure.

Usage:
    python -m tools.convert_renpy /path/to/RenPyGame /path/to/UPVN_Out [--overwrite] [--blend]
    python -m tools.convert_renpy /path/to/RenPyGame/game /tmp/out

What it does:
  1. Discovers the Ren'Py `game/` dir (tools.check_renpy_project.find_script_dir)
  2. Parses every .rpy/.rpym in full tier — validates parse, collects labels,
     reports unresolved jumps (same as check_renpy_project)
  3. Copies every .rpy/.rpym verbatim into <out>/game/ preserving relative paths.
     Copy is correct because UPVN full tier already understands Ren'Py syntax;
     image declarations that pointed at PNGs will now render as palette colours.
  4. Writes <out>/game/script.rpy shim when the source has no top-level script.rpy
     (multi-file projects) — just an include-like shim is unnecessary because
     VNController loads a directory with all .rpy; we instead ensure a single
     entry file exists for editor convenience.
  5. Validates the result headlessly (VNController run_headless in compat mode)
  6. Optionally generates <out>/blend/UPVN_Template.blend via the add-on's
     build_vn_scene when run inside Blender/UPBGE (or prints instructions).

Result is a standard UPVN project: open <out>/blend/UPVN_Template.blend in
UPBGE → UPVN tab shows script_path → Setup Scene → P to play.
"""
from __future__ import annotations
import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.check_renpy_project import find_script_dir, check_project  # noqa: E402


def _copy_scripts(src_game: Path, dst_game: Path) -> list[Path]:
    copied: list[Path] = []
    for p in sorted(set(list(src_game.rglob("*.rpy")) + list(src_game.rglob("*.rpym")))):
        # skip Ren'Py translation folder tl/ (same as checker)
        try:
            rel = p.relative_to(src_game)
        except Exception:
            rel = Path(p.name)
        if "tl" in rel.parts:
            continue
        dst = dst_game / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)
        copied.append(dst)
    return copied


def convert_renpy_project(src: Path, dst: Path, overwrite: bool = False, generate_blend: bool = False) -> dict:
    src = Path(src).resolve()
    dst = Path(dst).resolve()
    if not src.exists():
        raise FileNotFoundError(f"source not found: {src}")
    game_dir = find_script_dir(src)
    if not game_dir.is_dir():
        raise FileNotFoundError(f"no game dir found in {src}")
    # 1) validate source
    report = check_project(src, verbose=False)

    if dst.exists() and not overwrite:
        raise FileExistsError(f"destination exists: {dst} (use --overwrite)")
    dst_game = dst / "game"
    dst_game.mkdir(parents=True, exist_ok=True)

    # 2) copy scripts verbatim (no texture assets needed)
    copied = _copy_scripts(game_dir, dst_game)

    # 3) ensure a top-level entry exists for editor's default path //game/script.rpy
    # If the source had game/script.rpy already, it's copied. Otherwise create a tiny shim.
    if not (dst_game / "script.rpy").exists():
        # create shim that just defines start if missing (VNController will merge all files,
        # but the editor's project_path expects a file)
        shim = dst_game / "script.rpy"
        # collect labels from report to know if start exists
        has_start = report.get("totals", {}).get("start_label", False)
        if has_start:
            shim.write_text("# UPVN shim — source had multiple files; all are merged at load time.\n# Original start lives in another file.\nlabel start:\n    \"Converted Ren'Py project — start label found in another file.\"\n    return\n", encoding="utf-8")
        else:
            shim.write_text("label start:\n    \"Converted Ren'Py project — no start label found in source.\"\n    return\n", encoding="utf-8")
        copied.append(shim)

    # 4) write conversion readme
    readme = dst / "README_CONVERTED.md"
    readme.write_text(
        f"# Converted from Ren'Py — {src.name}\n\n"
        f"Source: `{src}`\n"
        f"Game dir: `{game_dir}`\n"
        f"Scripts copied: {len(copied)}\n"
        f"Parse errors: {len(report.get('parse_errors', []))}\n"
        f"Duplicate labels: {len(report.get('duplicate_labels', []))}\n"
        f"Unresolved jumps: {report.get('unresolved_jumps')}\n"
        f"Unresolved calls: {report.get('unresolved_calls')}\n"
        f"Notes:\n"
        f"- Images/audio from the original project are NOT required. UPVN's palette\n"
        f"  in `engine/render/contract.py` renders `scene bg X` / `show Y` as solid\n"
        f"  colours (object.color on white emission). Works on llvmpipe and lavapipe.\n"
        f"- To play in UPBGE: open `blend/UPVN_Template.blend` (generated with --blend\n"
        f"  or via Setup Scene), set UPVN panel `project_path` to `//game/script.rpy`\n"
        f"  (or keep directory mode), press P.\n"
        f"- Headless test: `python -m tools.run_headless {dst_game} --mode full`\n",
        encoding="utf-8",
    )

    # 5) headless smoke run (compat mode, up to 200 steps)
    smoke = None
    try:
        from engine.core.vn_controller import VNController
        ctrl = VNController(script_path=dst_game, mode="full", compat=True)
        ctrl.load()
        trace = ctrl.run_headless(choices=[0] * 6)
        smoke = {"ok": True, "events": len(trace), "error": None}
    except Exception as e:
        smoke = {"ok": False, "events": 0, "error": str(e)[:500]}

    # 6) optional blend generation
    blend_info = None
    if generate_blend:
        try:
            import bpy  # type: ignore
            from blend.upvn_editor_addon import build_vn_scene

            dst_blend_dir = dst / "blend"
            dst_blend_dir.mkdir(parents=True, exist_ok=True)
            out_blend = dst_blend_dir / "UPVN_Template.blend"
            # build scene in current bpy context, then save as
            ctrl_obj = build_vn_scene(bpy, scene_name=None, script_path="//game/script.rpy")
            bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
            blend_info = f"generated {out_blend}"
        except Exception as e:
            blend_info = f"blend generation skipped/failed: {e}"

    return {
        "src": str(src),
        "game_dir": str(game_dir),
        "dst": str(dst),
        "copied": [str(p.relative_to(dst)) for p in copied],
        "report": report,
        "smoke": smoke,
        "blend": blend_info,
    }


def main():
    ap = argparse.ArgumentParser(description="Convert Ren'Py project → UPVN project (no textures)")
    ap.add_argument("src", help="Ren'Py project dir (or game/ subdir)")
    ap.add_argument("dst", help="Destination UPVN project dir (will contain game/ + blend/)")
    ap.add_argument("--overwrite", action="store_true", help="allow existing dst")
    ap.add_argument("--blend", action="store_true", help="generate blend/UPVN_Template.blend (needs bpy)")
    ap.add_argument("--json", help="write report JSON to path")
    args = ap.parse_args()
    res = convert_renpy_project(Path(args.src), Path(args.dst), overwrite=args.overwrite, generate_blend=args.blend)
    print(f"Source: {res['src']}  ->  {res['dst']}")
    print(f"Scripts copied: {len(res['copied'])}")
    for p in res["copied"][:12]:
        print(f"  {p}")
    if len(res["copied"]) > 12:
        print(f"  ... and {len(res['copied'])-12} more")
    pe = res["report"].get("parse_errors", [])
    print(f"Parse errors: {len(pe)}")
    for e in pe[:6]:
        print(f"  {e}")
    print(f"Unresolved jumps: {res['report'].get('unresolved_jumps')}")
    print(f"Smoke: {res['smoke']}")
    if res["blend"]:
        print(f"Blend: {res['blend']}")
    if args.json:
        import json
        Path(args.json).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Report JSON: {args.json}")
    # exit code 1 if parse errors
    sys.exit(1 if pe else 0)


if __name__ == "__main__":
    main()
