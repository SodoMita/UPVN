UPVN Playable Build — 10_full_sample_game
==============================
Generated: 2026-09-07 21:09:35
Project: /home/user/upvn/examples/10_full_sample_game
Engine: UPVN 0.50 (Blender 5.0 / UPBGE 0.50)

How to play in UPBGE:
  1. Extract upbge-0.50-linux-x64.tar.xz (if not already)
  2. Open blend/UPVN_Template.blend in UPBGE
  3. Scene VN_Main → Empty VNController → property script_path = //game/script.rpy
  4. Press P → Click/Space to advance, H history, Q quick menu, S save (arbitrary slot), Ctrl+S quick save, wheel rollback

How to play headless (no UPBGE):
  python run.py
  python run.py --choices 0 1
  python -m tools.run_headless game/script.rpy --choices 0

Localization:
  locale/template.pot + locale/template.json — 36 strings extracted
  Translate msgstr in locale/<lang>.po and rebuild.

Accessibility:
  See ACCESSIBILITY.md / accessibility.json — keyboard, typewriter 40cps, high contrast, arbitrary saves 1..∞

Saves:
  saves/save_<slot>.json (any integer, e.g. save_42.json, save_500.json) — JSON, not pickle

Showcase:
  This build includes the 30-min showcase (game/script.rpy) exercising:
  say/narration, Character, scene/show/hide, menu/jump, $/if, play music/sound, with fade/dissolve, save/load arbitrary, history/rollback, move/zoom/ATL, 3D stage hybrid, Blender editor tools.

Minimal coding in Blender:
  blend/upvn_editor_addon.py → Install → View3D > Sidebar > UPVN → Create Project / Add Character / etc.
  Or headless: python tools/upvn_game_creator.py

Build info: see build_info.json
