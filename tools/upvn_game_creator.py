#!/usr/bin/env python3
"""upvn_game_creator.py — standalone one-click game creation (no bpy needed).

Usage:
    python tools/upvn_game_creator.py --title "My Story" --theme fantasy --out game/script.rpy
    python tools/upvn_game_creator.py --title "My Story" --theme school --out game/script.rpy

Themes: school, fantasy, scifi, mystery
Each theme generates a unique branching story with characters, state, and scenes.
"""
import argparse
import sys
import os

# Ensure engine is importable
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _REPO)

from blend.upvn_editor_addon import UPVN_GameBuilder


def main():
    ap = argparse.ArgumentParser(description="UPVN one-click game creator")
    ap.add_argument("--title", default="My Visual Novel", help="Game title")
    ap.add_argument("--theme", default="school", choices=["school", "fantasy", "scifi", "mystery"])
    ap.add_argument("--out", default="game/script.rpy", help="Output .rpy path")
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
    print(f"Validation: {'PASS' if ok else 'WARN'} — {msg}")
    print(f"\nCharacters: {list(builder.characters.keys())}")
    print(f"State vars: {list(builder.state_vars.keys())}")
    print(f"Labels: {list(builder.labels.keys())}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
