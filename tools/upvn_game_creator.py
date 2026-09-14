#!/usr/bin/env python3
"""
UPVN Game Creator — minimal-coding CLI (works inside or outside Blender)

Create a complete visual novel with Python API, no manual .rpy typing:

    from tools.upvn_game_creator import quick_game

    quick_game(
        project="game",
        title="My VN",
        characters=[("e","Eileen","#c8ffc8"), ("s","Sylvie","#c8c8ff")],
        scenes=["bg classroom", "bg lecturehall"],
        dialogues=[("e","Hello!"), (None,"Narration..."), ("s","Hi there!")],
        menu=("What next?", [("Ask","ask_label"), ("Wait","wait_label")])
    )

Also exposes UPVN_GameBuilder for programmatic use (same as Blender addon).
For Blender UI, see blend/upvn_editor_addon.py (View3D > Sidebar > UPVN).

Arbitrary save slots: SaveManager supports 1..∞, pagination in screen_manager.
"""
from pathlib import Path
import sys

# ensure project root in path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blend.upvn_editor_addon import UPVN_GameBuilder

def quick_game(project: str = "game", title: str = "UPVN Quick Game", characters=None, scenes=None, dialogues=None, menu=None, preview: bool = True):
    """
    One-call game creator — minimal coding.
    Example:
        quick_game(project="my_game", characters=[("e","Eileen","#c8ffc8")], dialogues=[("e","Hi")])
    """
    script_path = Path(project) / "script.rpy"
    builder = UPVN_GameBuilder(str(script_path))
    # characters
    for cid, name, color in (characters or [("e","Eileen","#c8ffc8")]):
        builder.add_character(cid, name, color)
    builder.ensure_label("start")
    # scenes
    for bg in (scenes or ["bg classroom"]):
        builder.add_scene(bg)
        break  # only first scene at start
    # dialogues
    for who, text in (dialogues or [(None, "This game was created with minimal coding — no .rpy typing!"), ("e","Hello from UPVN!")]):
        builder.add_say(who, text)
    # menu
    if menu:
        caption, choices = menu
        builder.add_menu(caption, choices)
    else:
        # demo menu
        builder.add_menu("What will you do?", [("Continue","continue_label"), ("End","end_label")])
        builder.ensure_label("continue_label")
        builder.add_say("e", "You continued!")
        builder.add_jump("end_label")
        builder.ensure_label("end_label")
        builder.add_say(None, "The end. Created with UPVN_GameBuilder (minimal coding).")
        builder.labels["end_label"].append("    return")
        builder.ensure_label("start")
    ok, msg = builder.validate()
    print(f"[creator] validate: {msg}")
    path = builder.write()
    print(f"[creator] wrote {path} ({path.stat().st_size} bytes)")
    if preview:
        out = builder.preview_screenshot()
        if out:
            print(f"[creator] preview: {out}")
    return path

def demo_arbitrary_saves():
    """Demo that save slots are arbitrary (1..∞), not 6."""
    from engine.core.vn_state import VNState
    from engine.save.save_manager import SaveManager
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    state = VNState()
    sm = SaveManager(state, save_dir=tmp)
    # save to arbitrary slots: 1, 7, 42, 100, 1000
    for slot in [1, 7, 42, 100, 1000]:
        state.variables["slot"] = slot
        state.current_label = "start"
        state.instruction_index = slot
        sm.save(slot)
        print(f"  saved slot {slot}")
    ids = sm.list_slot_ids()
    print(f"[arbitrary] slots: {ids} (not limited to 6)")
    # pagination demo via ScreenManager
    from engine.ui.screen_manager import ScreenManager
    mgr = ScreenManager(state, save_manager=sm)
    save_screen = mgr.screens["save"]
    print(f"[arbitrary] SaveScreen page_size {save_screen.page_size}, total slots property {save_screen.slots}")
    for pg in range(2):
        save_screen.page = pg
        lst = save_screen.list_page_slots()
        print(f"  page {pg}: {lst}")
    # also load
    for slot in [42, 1000]:
        sm.load(slot)
        print(f"  loaded slot {slot} -> idx {state.instruction_index}")
    print("[arbitrary] arbitrary slots work — any int 1..∞")

if __name__ == "__main__":
    print("=== UPVN Game Creator — minimal coding demo ===")
    # clean demo
    demo_arbitrary_saves()
    print()
    print("=== quick_game demo ===")
    quick_game(project="examples/99_creator_demo", title="Creator Demo",
               characters=[("e","Eileen","#c8ffc8"), ("s","Sylvie","#c8c8ff")],
               scenes=["bg classroom"],
               dialogues=[("e","This game was built with 3 lines of Python, no .rpy typing!"), (None,"UPVN Blender tools let you click to create.")],
               menu=("Try arbitrary saves?", [("Yes, save to slot 99","save_demo"), ("No, end","end_label")])
    )
    print("Done. Open in Blender: Text Editor → UPVN → Validate/Preview, or 3D View → Sidebar → UPVN")
