"""Convert a Ren'Py project into a playable UPVN project — Adaptive.

M28 Adaptive: Instead of hardcoding LearnToCodeRPG values, this tool now
parses ANY Ren'Py project's gui.rpy and generates upvn_gui.json that makes
UPVN automatically adapt its UI to match the source project's look.

What it does
------------
1. Finds the Ren'Py script dir (game/) via check_renpy_project.find_script_dir.
2. Parses game/gui.rpy via engine/render/gui_parser.py:
   - Extracts colors, fonts, sizes, dialogue positions, choice metrics
   - Generates UPVN adaptive config (world-space + colors + fonts)
   - Saves as game/upvn_gui.json AND assets/gui_config.json
3. Creates a self-contained UPVN project:
       <out>/game/                    all *.rpy + upvn_gui.json
       <out>/game/audio/              copied when source has audio
       <out>/assets/backgrounds/      images named bg* 
       <out>/assets/sprites/          every other image
       <out>/assets/gui/              copied gui images (textbox.png, etc.) + gui_config.json
       <out>/assets/fonts/            copied fonts from game/fonts/
       <out>/blend/UPVN_Template.blend + fonts/
       <out>/engine/, <out>/bge_frontend/   runtime snapshot (includes gui_parser)
       <out>/README_PLAY.txt
       <out>/conversion_report.json   includes gui_config
4. Wires the template: script_path=//../game, image_mode=auto, parse_mode=full
5. Runs parser/checker and prints summary.

The adaptive system:
- Ren'Py gui.rpy defines textbox_height, name_xpos, dialogue_xpos, choice_button_width, etc. in 1920x1080 pixels
- gui_parser converts those to UPVN ortho 15 world space
- contract.py and world_ui.py load upvn_gui.json at runtime, so ANY project looks identical
- No hardcoded LearnToCodeRPG values — works with any Ren'Py game

Usage
-----
    python tools/renpy_convert.py <renpy_project_dir> --out <out_dir>
    python tools/renpy_convert.py <src> --out <out> --blender /path/to/blender
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

try:
    from engine.render.gui_parser import find_and_parse_gui, parse_renpy_gui, gui_to_upvn_config, save_upvn_gui_config
    HAS_GUI_PARSER = True
except ImportError:
    HAS_GUI_PARSER = False
    print("[convert] WARNING: gui_parser not available, using generic defaults")

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

    # 1b) Adaptive GUI parsing — the key to not hardcoding
    gui_config = None
    if HAS_GUI_PARSER:
        try:
            gui_config = find_and_parse_gui(src)
            print(f"[convert] adaptive GUI: parsed from {src}/game/gui.rpy")
            print(f"  resolution: {gui_config['resolution']}")
            print(f"  colors: accent={gui_config['colors']['accent']} text={gui_config['colors']['text']}")
            print(f"  fonts: text={gui_config['fonts']['text']} name={gui_config['fonts']['name']}")
            print(f"  dialogue: textbox_height={gui_config['dialogue']['textbox_height']} name_xpos={gui_config['dialogue']['name_xpos']}")
            print(f"  choice: width={gui_config['choice']['button_width']} spacing={gui_config['choice']['spacing']}")
            # Save as JSON for runtime
            save_upvn_gui_config(gui_config, out / "game" / "upvn_gui.json")
            save_upvn_gui_config(gui_config, out / "assets" / "gui_config.json")
            (out / "assets" / "gui").mkdir(parents=True, exist_ok=True)
            save_upvn_gui_config(gui_config, out / "assets" / "gui" / "upvn_gui.json")
            _apply_textbox_sample(out, gui_config)
            print(f"[convert] saved adaptive config: game/upvn_gui.json + assets/gui_config.json")
        except Exception as e:
            print(f"[convert] GUI parsing failed: {e}, using generic defaults")
            import traceback
            traceback.print_exc()
            gui_config = None
    else:
        print("[convert] gui_parser not available, skipping adaptive config")

    # 2) audio — copy next to the scripts
    audio_src = game_dir / "audio"
    if audio_src.is_dir():
        shutil.copytree(audio_src, out / "game" / "audio", dirs_exist_ok=True)
        n_audio = sum(1 for _ in (out / "game" / "audio").rglob("*") if _.is_file())
        print(f"[convert] audio files: {n_audio}")

    # 2b) fonts — copy for adaptive font support
    fonts_src = game_dir / "fonts"
    n_fonts = 0
    if fonts_src.is_dir():
        fonts_dst = out / "assets" / "fonts"
        fonts_dst.mkdir(parents=True, exist_ok=True)
        for f in sorted(fonts_src.rglob("*")):
            if f.is_file() and f.suffix.lower() in (".ttf", ".otf"):
                dest = fonts_dst / f.relative_to(fonts_src)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
                n_fonts += 1
        # Also copy to game/fonts for Ren'Py path compat
        game_fonts_dst = out / "game" / "fonts"
        if not game_fonts_dst.exists():
            try:
                shutil.copytree(fonts_src, game_fonts_dst, dirs_exist_ok=True)
            except Exception:
                pass
        print(f"[convert] fonts: {n_fonts} copied to assets/fonts/ + game/fonts/")

    # 2c) gui images — textbox.png, namebox.png, etc.
    gui_src = game_dir / "gui"
    n_gui = 0
    if gui_src.is_dir():
        gui_dst = out / "assets" / "gui"
        gui_dst.mkdir(parents=True, exist_ok=True)
        for f in sorted(gui_src.rglob("*")):
            if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
                # Keep relative structure, but also flatten common ones
                dest = gui_dst / f.relative_to(gui_src)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
                n_gui += 1
        print(f"[convert] gui images: {n_gui} copied to assets/gui/")

    # 3) images — Ren'Py keeps them in game/images/**
    images_src = game_dir / "images"
    n_bg = n_sp = 0
    if images_src.is_dir():
        bg_dir = out / "assets" / "backgrounds"
        sp_dir = out / "assets" / "sprites"
        bg_dir.mkdir(parents=True, exist_ok=True)
        sp_dir.mkdir(parents=True, exist_ok=True)
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
          + (" (none found — palette paints every stage)" if (n_bg + n_sp) == 0 else ""))

    # 4) runtime snapshot
    (out / "blend").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "blend" / "UPVN_Template.blend", out / "blend" / "UPVN_Template.blend")
    # Copy fonts to blend/fonts for template
    blend_fonts = out / "blend" / "fonts"
    blend_fonts.mkdir(exist_ok=True)
    for f in (ROOT / "blend" / "fonts").glob("*.ttf"):
        shutil.copy2(f, blend_fonts / f.name)
    # Also copy converted fonts if any
    if (out / "assets" / "fonts").exists():
        for f in (out / "assets" / "fonts").rglob("*.ttf"):
            try:
                shutil.copy2(f, blend_fonts / f.name)
            except Exception:
                pass
    
    shutil.copytree(ROOT / "engine", out / "engine",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "bge_frontend", out / "bge_frontend",
                    ignore=shutil.ignore_patterns("__pycache__"))
    (out / "tools").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "tools" / "check_renpy_project.py", out / "tools")
    if HAS_GUI_PARSER:
        # Ensure gui_parser is included (it is in engine/)
        pass
    print("[convert] runtime snapshot: engine/ + bge_frontend/ + blend/ + fonts")

    # 5) wire the template
    wiring = {"ok": False, "reason": "blender binary not provided"}
    if blender is None:
        guess = Path.home() / "upbge" / "upbge-0.50-linux-x64" / "blender"
        if guess.is_file():
            blender = guess
        else:
            # Also try /opt
            opt_guess = Path("/opt/upbge/upbge-0.50-linux-x64/blender")
            if opt_guess.is_file():
                blender = opt_guess
    if blender is not None and Path(blender).is_file():
        wiring = wire_blend(out / "blend" / "UPVN_Template.blend", Path(blender),
                            out / "assets")
        print(f"[convert] blend wiring: {'OK' if wiring.get('ok') else wiring}")
    else:
        print("[convert] WARNING: no blender binary — open blend in UPBGE, run Setup Scene, set script_path=//../game image_mode=auto")

    # 6) parse report
    report = check_project(out)
    report["converted_from"] = str(src)
    report["wiring"] = wiring
    report["assets"] = {"backgrounds": n_bg, "sprites": n_sp, "fonts": n_fonts, "gui": n_gui}
    if gui_config:
        report["gui_config"] = {
            "resolution": gui_config.get("resolution"),
            "colors": gui_config.get("colors"),
            "fonts": gui_config.get("fonts"),
            "dialogue": gui_config.get("dialogue"),
            "choice": gui_config.get("choice"),
            "world": gui_config.get("world"),
        }
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
    print(f"[convert] play: blenderplayer /opt/upbge/upbge-0.50-linux-x64/blenderplayer {out}/blend/UPVN_Template.blend")
    if gui_config:
        print(f"[convert] adaptive: YES — UI will match original Ren'Py project via upvn_gui.json")
    else:
        print(f"[convert] adaptive: NO — using generic defaults")
    return report


def _apply_textbox_sample(out: Path, gui_config: dict) -> None:
    """M29: Ren'Py's stock textbox.png is a dark translucent band, but the
    generic '#ffffff' default made UPVN draw a white slab over the scene
    (SDK tutorial parity). Sample the copied gui image's mean RGBA and store
    it as colors.dialogue_box — only when the project did not define an
    explicit box color in gui.rpy."""
    colors = (gui_config or {}).get("colors") or {}
    if colors.get("dialogue_box") not in (None, "#ffffff"):
        return
    png = out / "assets" / "gui" / "textbox.png"
    if not png.is_file():
        return
    try:
        from PIL import Image
        im = Image.open(png).convert("RGBA")
        px = list(im.getdata())
        n = max(1, len(px))
        mean = tuple(sum(p[i] for p in px) // n for i in range(4))
        hexes = "#%02x%02x%02x%02x" % mean
        for jpath in (out / "game" / "upvn_gui.json",
                      out / "assets" / "gui" / "upvn_gui.json"):
            if jpath.is_file():
                data = json.loads(jpath.read_text(encoding="utf-8"))
                data.setdefault("colors", {})["dialogue_box"] = hexes
                jpath.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"[convert] textbox sampled → dialogue_box {hexes}")
    except Exception as e:
        print(f"[convert] textbox sample failed ({e})")


def wire_blend(blend: Path, blender: Path, assets: Path | None = None) -> dict:
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


README = """UPVN — converted Ren'Py project (Adaptive)
========================================

This project was converted from Ren'Py with ADAPTIVE GUI parsing.
It will look identical to the original Ren'Py project because
game/upvn_gui.json captures the original's textbox, colors, fonts, etc.

Source: {out}/conversion_report.json has parse report + gui_config.

Play (UPBGE 0.50):
    /opt/upbge/upbge-0.50-linux-x64/blenderplayer -w 1280 720 0 0 {out}/blend/UPVN_Template.blend
or open {out}/blend/UPVN_Template.blend in UPBGE and press P.

Controls:
    click / Space / Enter  advance
    1..9 or mouse click    pick a menu choice
    H history · Q quick menu · S skip · A auto
    Ctrl+S quick-save · Ctrl+L quick-load · mouse wheel rollback
    F1 state dump · F12 screenshot (//screenshots/)

Adaptive GUI:
    game/upvn_gui.json — parsed from original gui.rpy, loaded by engine/render/gui_config.py
    contract.py and world_ui.py use it automatically, so UI matches original.
    No hardcoded LearnToCodeRPG values — works with ANY Ren'Py project.

Images:
    image_mode=auto — PNGs from Ren'Py game's images/ folder are used when present
    assets/backgrounds, assets/sprites; missing falls back to color palette.
    Set image_mode=color on VNController to force palette.

Fonts:
    assets/fonts/ — copied from original game/fonts/, used if available.
    Blend also has blend/fonts/ with Lato, Hack, DejaVu for fallback.

To test adaptability with another project:
    python tools/renpy_convert.py /path/to/other_renpy_game --out /tmp/other_upvn
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ren'Py project → UPVN project (Adaptive)")
    ap.add_argument("source", help="Ren'Py project directory (containing game/)")
    ap.add_argument("--out", required=True, help="output UPVN project directory")
    ap.add_argument("--blender", default=None,
                    help="blender binary used to wire template blend")
    args = ap.parse_args(argv)
    convert(Path(args.source), Path(args.out),
            Path(args.blender) if args.blender else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
