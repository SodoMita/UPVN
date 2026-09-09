#!/usr/bin/env python3
"""
Headless runner for UPVN scripts — golden-trace generator.

Usage:
  python -m tools.run_headless examples/00_minimal_dialogue/script.rpy
  python -m tools.run_headless examples/03_variables_routes/script.rpy --choices 0
  python -m tools.run_headless the_question/game/script.rpy --choices 0 0 --json

Emits trace events (SAY, MENU, JUMP, etc.) and final VNState.
Use for agent verification without UPBGE.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.core.vn_controller import VNController

def _count_widgets(widgets):
    """Total widgets in a rendered screen tree (containers included)."""
    n = 0
    for w in widgets or []:
        n += 1 + _count_widgets(w.get("children"))
    return n


def main():
    ap = argparse.ArgumentParser(description="UPVN headless runner")
    ap.add_argument("script", help="path to .rpy file or directory")
    ap.add_argument("--choices", nargs="*", type=int, default=[], help="menu choices in order")
    ap.add_argument("--json", action="store_true", help="emit JSON trace")
    ap.add_argument("--state", action="store_true", help="dump final state JSON")
    ap.add_argument("--mode", choices=("safe", "full"), default="safe",
                    help="parse mode: safe declarative subset (default) or full drop-in Ren'Py")
    args = ap.parse_args()

    ctrl = VNController(script_path=args.script, mode=args.mode)
    trace = ctrl.run_headless(choices=args.choices)

    if args.json:
        print(json.dumps(trace, ensure_ascii=False, indent=2))
    else:
        for e in trace:
            t = e.get("type")
            if t == "say":
                who = e.get("who_name") or e.get("who") or "narr"
                loc = e.get("_loc")
                loc_s = f" {loc['file']}:{loc['line']}" if loc else ""
                print(f'SAY {who}: "{e.get("text")}"{loc_s}')
            elif t == "menu":
                cap = f' caption="{e.get("caption")}"' if e.get("caption") else ""
                print(f'MENU{cap}: {[c["text"] for c in e["choices"]]}')
            elif t == "jump":
                print(f'JUMP -> {e["label"]}')
            elif t == "return":
                print(f'RETURN to {e["to"]}')
            elif t == "scene":
                print(f'SCENE {e["asset"]} with {e.get("transition")}')
            elif t == "show":
                print(f'SHOW {e["asset"]} at {e.get("position")}')
            elif t == "assign":
                print(f'ASSIGN {e["target"]} {e["op"]} {e["expr"]} => {e["value"]}')
            elif t in ("show_screen", "call_screen", "hide_screen"):
                # M22: screens render to real widgets, so show what came out
                n = _count_widgets(e.get("widgets"))
                label = {"show_screen": "SHOW SCREEN", "call_screen": "CALL SCREEN",
                         "hide_screen": "HIDE SCREEN"}[t]
                extra = f" -> {n} widgets" if t != "hide_screen" else ""
                errs = e.get("errors") or []
                note = f"  ({errs[0]})" if errs else ""
                print(f'{label} {e.get("screen")}{extra}{note}')
            elif t == "end":
                print(f'END ({e.get("label")})')
            else:
                print(f'{t.upper()}: {e}')

    if args.state:
        print("\n-- STATE --")
        print(ctrl.state.to_json())

if __name__ == "__main__":
    main()
