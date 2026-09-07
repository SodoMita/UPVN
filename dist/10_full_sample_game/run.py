#!/usr/bin/env python3
"""Playable build — headless or UPBGE
Headless: python run.py [--choices 0 1] (works from any cwd)
UPBGE: open blend/UPVN_Template.blend → set script_path to //game/script.rpy → Press P
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from engine.core.vn_controller import VNController

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--choices", nargs="*", type=int, default=[])
    args = ap.parse_args()
    _here = Path(__file__).parent
    _script = _here / "game" / "script.rpy"
    # fallback: first .rpy in game/ if script.rpy missing (multi-file projects)
    if not _script.exists():
        _found = list((_here / "game").rglob("*.rpy"))
        if _found:
            _script = _found[0]
    c = VNController(script_path=str(_script))
    trace = c.run_headless(choices=args.choices)
    for e in trace:
        if e.get("type")=="say":
            print(f'{e.get("who_name") or "narr"}: {e.get("text")}')
    print(f"Done — {len(trace)} events, history {len(c.state.history)}")
    # demo arbitrary saves
    from engine.save.save_manager import SaveManager
    sm = SaveManager(c.state, save_dir=str(_here / "saves"))
    slot = sm.next_available_slot()
    sm.save(slot)
    print(f"Auto-saved to arbitrary slot {slot} → saves/save_{slot}.json")
