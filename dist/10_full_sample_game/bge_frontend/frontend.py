"""
UPBGE Frontend — thin adapter (M01/M02 complete)

For Tier1 this is minimal: it creates VNController and hooks update().
LLM can extend UI creation in python (per user request: "No need to implement
dsl for it, llm can build that using python").

Blend file wiring:
    Always sensor (True pulse, skip) -> Python Controller -> frontend.main

    # frontend.py
    from upvn.bge_frontend.frontend import main
    def main(cont):
        if not hasattr(bge.logic, "_upvn"):
            bge.logic._upvn = VNController("//game/script.rpy")
            bge.logic._upvn.load()
        bge.logic._upvn.update()

Hybrid rendering: 2D sprites are planes on orthographic camera; 3D stage is
separate scene with perspective camera. Both driven via vn_state.

fake-bge: for headless/CI we provide stubs so imports don't crash.
    pip install fake-bge-module  (or our vendored stub)
"""
from __future__ import annotations

try:
    import bge  # type: ignore
    HAS_BGE = True
except ImportError:
    HAS_BGE = False
    class _Fake:
        logic = type("obj", (), {"expandPath": lambda self, p: p})()
        events = {}
    bge = _Fake()  # type: ignore

from pathlib import Path
import time

_last_time: float = 0.0

def main(cont=None):
    """Entry for UPBGE Python controller. Called every frame."""
    if not HAS_BGE:
        print("[UPVN] Not running inside UPBGE — frontend.main is a no-op headlessly")
        return
    import bge as _bge
    logic = _bge.logic
    if not hasattr(logic, "_upvn_ctrl"):
        from upvn.engine.core.vn_controller import VNController
        found = False
        for candidate in ["//game/script.rpy", "//examples/00_minimal_dialogue/script.rpy", "//script.rpy"]:
            try:
                p = logic.expandPath(candidate)
                if Path(p).exists():
                    ctrl = VNController(script_path=p)
                    ctrl.load()
                    logic._upvn_ctrl = ctrl
                    # register post_draw for blf
                    try:
                        sc = _bge.logic.getCurrentScene()
                        sc.post_draw.append(draw_overlay)
                    except Exception:
                        pass
                    print(f"[UPVN] Loaded script {p}")
                    found = True
                    break
            except Exception as e:
                print(f"[UPVN] failed to load {candidate}: {e}")
        if not found:
            from upvn.engine.script.parser import parse_string
            script = parse_string('label start:\n    "Hello from UPVN inside UPBGE."\n    return\n')
            from upvn.engine.core.vn_controller import VNController
            ctrl = VNController(script_dict=script)
            ctrl.load()
            logic._upvn_ctrl = ctrl
            print("[UPVN] Loaded fallback minimal script")

    # per-frame tick with dt
    global _last_time
    now = time.time()
    dt = now - _last_time if _last_time else 0.016
    _last_time = now
    # clamp dt
    dt = min(0.05, max(0.0, dt))
    ctrl = logic._upvn_ctrl
    ctrl.update(dt=dt)
    # also tick sub-managers for transitions
    try:
        if ctrl.sprite_mgr:
            ctrl.sprite_mgr.update(dt)
        if ctrl.scene_mgr and hasattr(ctrl.scene_mgr, "transition_alpha"):
            # no-op, just for logging
            pass
    except Exception:
        pass


def draw_overlay():
    if not HAS_BGE:
        return
    try:
        import bge  # type: ignore
        import blf  # type: ignore
        import bge.render as br
        logic = bge.logic
        ctrl = getattr(logic, "_upvn_ctrl", None)
        if not ctrl or not ctrl.current_event:
            return
        ev = ctrl.current_event
        # dark bar at bottom for UI (fallback if no 3D plane)
        width = br.getWindowWidth()
        height = br.getWindowHeight()
        # This is a minimal blf overlay; the real UI is planes (Dialogue_Box) which already shows text.
        # We only draw if DialogueBox visible and typewriter not done
        ui = getattr(ctrl, "ui_mgr", None)
        if ui and ui.visible:
            text = ui.revealed_text()
            who = ui.current_who or ""
            # draw speaker
            blf.position(0, 50, 50, 0)
            blf.size(0, 18)
            blf.color(0, 0.72, 0.76, 1)
            blf.draw(0, who)
            # draw dialogue
            blf.position(0, 50, 30, 0)
            blf.size(0, 20)
            blf.color(0, 0.92, 0.93, 1)
            # wrap manually for blf (simple)
            blf.draw(0, text[:80])
        # menu: draw choices as blf clickable areas
        if ev.get("type") == "menu":
            y = height // 2
            for i, ch in enumerate(ev.get("choices", [])):
                blf.position(0, width//2 - 100, y - i*40, 0)
                blf.size(0, 20)
                blf.color(0, 0.85, 0.95, 1)
                blf.draw(0, f"{i+1}. {ch['text']}")
    except Exception as e:
        # blf errors are non-fatal
        print(f"[frontend draw_overlay] {e}")
