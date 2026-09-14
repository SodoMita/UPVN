"""Convert a Ren'Py project into a playable UPVN project.

M26 requirement: "There still should be the way to take a Ren'Py project and
convert it to this engine project."

What it does
------------
1. Finds the Ren'Py script dir (`game/`, or the project root itself) via
   tools/check_renpy_project.find_script_dir.
2. Creates a self-contained UPVN project:
       <out>/game/                    all *.rpy (the runtime merges the dir)
       <out>/game/audio/              copied when the source has audio
       <out>/assets/backgrounds/      images named `bg *` / `bg_*`
       <out>/assets/sprites/          every other image
       <out>/blend/UPVN_Template.blend
       <out>/engine/, <out>/bge_frontend/   runtime snapshot (repo layout)
       <out>/README_PLAY.txt          how to play + controls
       <out>/conversion_report.json   parse report for the merged project
3. Wires the copied template: game property script_path = `//../game` (the
   directory — VNController.load() merges every .rpy inside) and
   image_mode = `auto` (converted games use their PNGs when present and fall
   back to the palette otherwise).
4. Runs the parser/checker over the project and prints a human summary.

Usage
-----
    python tools/renpy_convert.py <renpy_project_dir> --out <out_dir>
    # wire + play headless-verified:
    python tools/renpy_convert.py <src> --out <out> \
        --blender /path/to/upbge-0.50-linux-x64/blender

The converted project plays with:
    <upbge>/blenderplayer -w 1024 576 0 0 <out>/blend/UPVN_Template.blend
or by opening <out>/blend/UPVN_Template.blend in UPBGE and pressing P.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.check_renpy_project import check_project, find_script_dir  # noqa: E402

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def _is_background(name: str) -> bool:
    stem = name.lower()
    return stem.startswith("bg ") or stem.startswith("bg_") or stem.startswith("bg-")


def convert(src: Path, out: Path, blender: Path | None = None) -> dict:
    src = src.resolve()
    if not src.is_dir():
        raise SystemExit(f"source Ren'Py project not found: {src}")
    game_dir = find_script_dir(src)
    scripts = sorted(set(game_dir.rglob("*.rpy")))
    if not scripts:
        raise SystemExit(f"no .rpy scripts under {game_dir}")
    rpym = sorted(set(game_dir.rglob("*.rpym")))

    if out.exists():
        print(f"[convert] removing previous {out}")
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "game").mkdir()

    # 1) scripts — copied as-is; the engine merges the directory
    for f in scripts:
        rel = f.relative_to(game_dir)
        dest = out / "game" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
    print(f"[convert] scripts: {len(scripts)} .rpy"
          + (f" (+{len(rpym)} .rpym ignored)" if rpym else ""))

    # 2) audio — copy next to the scripts so relative paths keep working
    audio_src = game_dir / "audio"
    if audio_src.is_dir():
        shutil.copytree(audio_src, out / "game" / "audio", dirs_exist_ok=True)
        n_audio = sum(1 for _ in (out / "game" / "audio").rglob("*") if _.is_file())
        print(f"[convert] audio files: {n_audio}")

    # 3) images — Ren'Py keeps them in game/images/**; UPVN looks in
    #    assets/backgrounds (bg-prefixed) and assets/sprites (the rest).
    images_src = game_dir / "images"
    n_bg = n_sp = 0
    if images_src.is_dir():
        bg_dir = out / "assets" / "backgrounds"
        sp_dir = out / "assets" / "sprites"
        bg_dir.mkdir(parents=True)
        sp_dir.mkdir(parents=True)
        for f in sorted(images_src.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in IMAGE_EXTS:
                continue
            rel = f.relative_to(images_src)
            if _is_background(f.name):
                shutil.copy2(f, bg_dir / rel.name)
                n_bg += 1
            else:
                dest = sp_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
                n_sp += 1
    print(f"[convert] images: {n_bg} backgrounds, {n_sp} sprites"
          + (" (none found — the palette paints every stage)" if (n_bg + n_sp) == 0 else ""))

    # 4) runtime snapshot (repo layout: blend/ + engine/ + bge_frontend/ + game/)
    (out / "blend").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "blend" / "UPVN_Template.blend", out / "blend" / "UPVN_Template.blend")
    shutil.copytree(ROOT / "engine", out / "engine",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "bge_frontend", out / "bge_frontend",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (out / "tools").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "tools" / "check_renpy_project.py", out / "tools")
    print("[convert] runtime snapshot: engine/ + bge_frontend/ + blend/")

    # 5) wire the template: script dir + image policy
    wiring = {"ok": False, "reason": "blender binary not provided"}
    if blender is None:
        guess = Path.home() / "upbge" / "upbge-0.50-linux-x64" / "blender"
        if guess.is_file():
            blender = guess
    if blender is not None and Path(blender).is_file():
        wiring = wire_blend(out / "blend" / "UPVN_Template.blend", Path(blender),
                            out / "assets")
        print(f"[convert] blend wiring: {'OK' if wiring.get('ok') else wiring}")
    else:
        print("[convert] WARNING: no blender binary — open the blend in UPBGE, "
              "run Setup Scene, then set script_path=//../game image_mode=auto")

    # 6) parse report
    report = check_project(out)
    report["converted_from"] = str(src)
    report["wiring"] = wiring
    report["assets"] = {"backgrounds": n_bg, "sprites": n_sp}
    (out / "conversion_report.json").write_text(json.dumps(report, indent=2))

    (out / "README_PLAY.txt").write_text(README.format(out=out))

    errs = report.get("parse_errors") or []
    unresolved = (report.get("unresolved_jumps") or []) + (report.get("unresolved_calls") or [])
    print(f"[convert] parse: {len(report.get('files') or [])} files, "
          f"{len(report.get('labels') or {})} labels, "
          f"{len(errs)} parse errors, {len(unresolved)} unresolved targets")
    for e in errs[:8]:
        print(f"  ! {e.get('file')}:{e.get('line')}: {e.get('error')}")
    print(f"[convert] project ready: {out}")
    print(f"[convert] play: blenderplayer <upbge>/blenderplayer "
          f"{out}/blend/UPVN_Template.blend")
    return report


def wire_blend(blend: Path, blender: Path, assets: Path | None = None) -> dict:
    """Wire props + image bank via tools/wire_converted_blend.py.

    bge.texture cannot bind node materials in UPBGE 0.50, so converted
    projects get one plane per asset with the texture assigned in the editor;
    the runtime (image_mode=auto) shows the matching plane and falls back to
    the palette when an asset is missing."""
    wire_script = ROOT / "tools" / "wire_converted_blend.py"
    cmd = [str(blender), "--background", str(blend),
           "--python", str(wire_script)]
    if assets is not None:
        cmd += ["--", str(assets)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as e:
        return {"ok": False, "reason": f"blender run failed: {e}"}
    out = (proc.stdout or "")
    ok = "UPVN_WIRE_OK" in out
    return {"ok": ok, "blender": str(blender),
            "log": [l for l in out.splitlines() if l.startswith("[wire]")][:8],
            "stderr": (proc.stderr or "")[-400:] if not ok else ""}


README = """UPVN — converted Ren'Py project
================================

Source: {out}/../conversion_report.json has the parse report.

Play (UPBGE 0.50):
    <upbge>/blenderplayer -w 1024 576 0 0 {out}/blend/UPVN_Template.blend
or open {out}/blend/UPVN_Template.blend in UPBGE and press P.

Controls:
    click / Space / Enter  advance
    1..9 or mouse click    pick a menu choice
    H history · Q quick menu · S skip · A auto
    Ctrl+S quick-save · Ctrl+L quick-load · mouse wheel rollback
    F1 state dump · F12 screenshot (//screenshots/)

Images: image_mode=auto — PNGs from the Ren'Py game's images/ folder are used
when present (assets/backgrounds, assets/sprites); anything missing falls back
to the built-in color palette. Set image_mode=color on the VNController game
property to force the texture-free palette.
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ren'Py project → UPVN project")
    ap.add_argument("source", help="Ren'Py project directory (containing game/)")
    ap.add_argument("--out", required=True, help="output UPVN project directory")
    ap.add_argument("--blender", default=None,
                    help="blender binary used to wire the template blend "
                         "(default: ~/upbge/upbge-0.50-linux-x64/blender)")
    args = ap.parse_args(argv)
    convert(Path(args.source), Path(args.out),
            Path(args.blender) if args.blender else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
