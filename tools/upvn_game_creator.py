#!/usr/bin/env python3
"""upvn_game_creator.py — standalone one-click game creation (no bpy needed).

Usage:
    python tools/upvn_game_creator.py --title "My Story" --theme fantasy --out game/script.rpy
    python tools/upvn_game_creator.py --title "My Story" --theme school --out game/script.rpy --preview

Themes: school, fantasy, scifi, mystery
Each theme generates a unique branching story with characters, state, and scenes.
"""
import argparse
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _REPO)

from blend.upvn_editor_addon import UPVN_GameBuilder


def main():
    ap = argparse.ArgumentParser(description="UPVN one-click game creator")
    ap.add_argument("--title", default="My Visual Novel", help="Game title")
    ap.add_argument("--theme", default="school", choices=["school", "fantasy", "scifi", "mystery"])
    ap.add_argument("--out", default="game/script.rpy", help="Output .rpy path")
    ap.add_argument("--preview", action="store_true", help="Generate headless preview screenshots")
    args = ap.parse_args()

    builder = UPVN_GameBuilder(args.out, use_declarative=True)
    builder.create_quick_wizard(title=args.title, theme=args.theme)

    # Ensure asset directories
    out = os.path.abspath(args.out)
    root = os.path.dirname(os.path.dirname(out)) if os.path.basename(os.path.dirname(out)) == "game" else os.path.dirname(out)
    for sub in ["backgrounds", "sprites", "audio", "stages"]:
        os.makedirs(os.path.join(root, "assets", sub), exist_ok=True)
    os.makedirs(os.path.join(root, "screenshots"), exist_ok=True)

    path = builder.write()

    # Validate
    ok, msg = builder.validate()
    print(f"Created: {path}")
    print(f"Theme: {args.theme}")
    print(f"Validation: {'PASS' if ok else 'WARN'} -- {msg}")
    print(f"\nCharacters: {list(builder.characters.keys())}")
    print(f"State vars: {list(builder.state_vars.keys())}")
    print(f"Labels: {list(builder.labels.keys())}")

    # Preview screenshots
    if args.preview:
        from engine.script.parser import parse_string
        from engine.core.vn_state import VNState
        from engine.core.vn_interpreter import VNInterpreter
        from engine.render.headless_renderer import render_state
        from pathlib import Path as _P
        preview_dir = os.path.join(root, "screenshots", f"preview_{args.theme}")
        os.makedirs(preview_dir, exist_ok=True)
        rpy = builder.build_rpy()
        script = parse_string(rpy)
        state = VNState()
        interp = VNInterpreter(script, state)
        gen = interp.run()
        step = 0
        try:
            ev = next(gen)
            while step < 6:
                if ev.get("wait"):
                    render_state(state, ev, _P(os.path.join(preview_dir, f"step{step}.png")))
                    step += 1
                    if ev.get("type") == "menu":
                        ev = gen.send(0)
                    else:
                        ev = gen.send(None)
                else:
                    ev = next(gen)
        except StopIteration:
            pass
        print(f"\nPreview: {step} screenshots saved to {preview_dir}/")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
