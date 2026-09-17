"""
Run inside UPBGE (--background mode) to capture screenshots of LearnToCodeRPG
at various stages: main menu, first dialogue, first choice.
"""
import bpy
import sys, os

UPVN_ROOT = "/home/user/UPVN"
sys.path.insert(0, UPVN_ROOT)

# Use the headless renderer to generate screenshots
from engine.render.headless_renderer import render_frame

# Parse the script
from engine.core.parser import parse_script

script_path = "/home/user/LearnToCodeRPG/game/script.rpy"
with open(script_path, "r") as f:
    source = f.read()

events, errors = parse_script(source, compat_mode=True)
print(f"Parsed: {len(events)} events, {len(errors)} errors")

# Render each stage
stages = [
    ("main_menu", {"type": "menu_screen", "items": ["Start Game", "Load Game", "Preferences", "Quit"]}),
    ("dialogue_1", {"type": "say", "who": "interviewer", "text": "So - are you feeling excited?", "scene": "bg laptop_screen"}),
    ("dialogue_2", {"type": "say", "who": "player", "text": "U-um... I definitely am. I'm just a bit nervous...", "scene": "bg laptop_screen"}),
    ("choices", {"type": "menu", "caption": "Great! We'll start whenever you're ready.", "choices": [
        {"text": "Guess I have no other options. Let's start!", "name": "choice_0", "visible": True},
        {"text": "I've been preparing for this moment my whole life!", "name": "choice_1", "visible": True},
    ]}),
]

out_dir = "/home/user/screenshots"
os.makedirs(out_dir, exist_ok=True)

for name, state in stages:
    try:
        img = render_frame(state)
        path = os.path.join(out_dir, f"upvn_{name}.png")
        img.save(path)
        print(f"Saved: {path} ({img.size})")
    except Exception as e:
        print(f"Error rendering {name}: {e}")
        import traceback
        traceback.print_exc()

print("Done")
