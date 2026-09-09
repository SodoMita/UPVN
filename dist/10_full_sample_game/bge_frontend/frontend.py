"""
UPBGE Frontend — thin adapter (M01/M02 complete, v0.6 hardened)

v0.6 changes (2026-09-08) — "it never starts / wrong script":
  * script_path is now read FIRST from the VNController object property
    (`obj["script_path"]`, the one the editor add-on writes), so the game you
    build with the UPVN panel is the game that plays.  Legacy candidates
    (//game/script.rpy, //examples/..., //script.rpy) are kept as fallbacks.
  * sys.path is bootstrapped from this file's location so `import engine…`
    works no matter where the .blend lives (repo layout and bundled add-on
    layout both resolve to the same parent-of-bge_frontend folder).
  * If nothing is found the console says exactly which paths were tried
    instead of silently falling back.

Blend file wiring (press "Setup Scene" in the UPVN tab to get this):
    VNController (empty, props: script_path="//game/script.rpy", upvn_root)
      └ Always sensor (pulse) → Python controller (launcher text or module)
          └ runs bge_frontend.frontend.main(cont) every frame

fake-bge: for headless/CI we provide stubs so imports don't crash.
    pip install fake-bge-module  (or rely on the built-in _Fake fallback)
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
import os
import sys
import time

_last_time: float = 0.0

# relative candidates, tried from the .blend directory and up to 2 parent
# levels — covers repo layout (<repo>/blend + <repo>/game), packaged layout
# (<pkg>/blend + <pkg>/game) and 'save the blend next to your game' layouts
ENGINE_CANDIDATES = ["//game/script.rpy", "//script.rpy",
                     "//examples/10_full_sample_game/script.rpy",
                     "//examples/00_minimal_dialogue/script.rpy",
                     "//../game/script.rpy",
                     "//../../game/script.rpy"]


def ensure_engine_syspath():
    """Make `import engine…` resolve: the engine/ folder sits next to the
    parent of bge_frontend/ in both the repo layout and the bundled add-on
    layout. Returns True when engine/script/parser.py is reachable."""
    try:
        root = Path(__file__).resolve().parent.parent
    except Exception:
        return False
    if (root / "engine" / "script" / "parser.py").is_file():
        s = str(root)
        if s not in sys.path:
            sys.path.insert(0, s)
        return True
    return False


def resolve_script_path(logic, owner=None, extra_candidates=None):
    """Return (path|None, tried) — first existing, expanded script path.

    Order:
      1. owner["script_path"]  (VNController property set by the add-on)
      2. engine candidates relative to the .blend (expandPath '//' prefix)
      3. extra_candidates passed in
    """
    tried = []
    candidates = []
    if owner is not None:
        try:
            if isinstance(owner, dict):
                val = owner.get("script_path")
            else:
                val = owner["script_path"] if "script_path" in owner else None
            if val:
                candidates.append(str(val))
        except Exception:
            pass
    for c in list(ENGINE_CANDIDATES) + list(extra_candidates or []):
        if c not in candidates:
            candidates.append(c)
    for c in candidates:
        try:
            p = logic.expandPath(c)
        except Exception:
            p = c
        tried.append(p)
        try:
            if os.path.isfile(p):
                return os.path.abspath(p), tried
        except Exception:
            pass
    return None, tried


def _owner_script_prop(cont):
    """dict-like access to the object's script_path property (no bge import)."""
    if cont is None:
        return None
    try:
        owner = cont.owner
    except Exception:
        return None
    return owner


def _register_overlay():
    """Append the blf overlay to the current scene's post_draw (once per scene)."""
    try:
        import bge as _bge
        sc = _bge.logic.getCurrentScene()
        if draw_overlay not in sc.post_draw:
            sc.post_draw.append(draw_overlay)
    except Exception:
        pass


def _bind_camera():
    """Force scene.active_camera = Camera_UI once (editor camera is not the game camera)."""
    if not HAS_BGE:
        return
    try:
        import bge as _bge
        logic = _bge.logic
        if getattr(logic, "_upvn_cam_bound", False):
            return
        sc = logic.getCurrentScene()
        cam = sc.objects.get("Camera_UI")
        if cam is None:
            return
        sc.active_camera = cam
        logic._upvn_cam_bound = True
        print("[UPVN] active_camera bound to Camera_UI")
    except Exception:
        pass


def main(cont=None):
    """Entry for UPBGE Python controller. Called every frame."""
    if not HAS_BGE:
        print("[UPVN] Not running inside UPBGE — frontend.main is a no-op headlessly")
        return
    import bge as _bge
    logic = _bge.logic
    ensure_engine_syspath()
    _bind_camera()

    if not hasattr(logic, "_upvn_ctrl"):
        from engine.core.vn_controller import VNController
        from engine.script.parser import parse_string
        owner = _owner_script_prop(cont)
        # 1) explicit property on the controller object (add-on's project path)
        path, tried = resolve_script_path(logic, owner=owner)
        logic._upvn_tried = tried
        if path:
            try:
                ctrl = VNController(script_path=path)
                ctrl.load()
                logic._upvn_ctrl = ctrl
                _register_overlay()
                print(f"[UPVN] Loaded script {path} (from {'VNController.script_path' if owner is not None else 'candidate'})")
            except Exception as e:
                print(f"[UPVN] failed to load {path}: {e}")
                logic._last_upvn_error = f"{path}: {e}"
        if not hasattr(logic, "_upvn_ctrl"):
            # 2) fallback: embedded minimal script that explains itself on the
            #    screen (a console-only warning is invisible to players)
            diag = ["UPVN: game script not found.",
                    "The scene searched these paths:"]
            tried_list = getattr(logic, "_upvn_tried", [])
            for t in tried_list[:6]:
                diag.append("  - " + os.path.basename(os.path.dirname(t)) + "/" + os.path.basename(t))
            diag.append("")
            diag.append("Fix in the UPVN panel (View3D > N):")
            diag.append("1. Create Project  2. Setup Scene  3. press P")
            print("[UPVN] WARNING: no game script found — tried: " +
                  ", ".join(tried_list or ["<none>"]) +
                  ". Set project_path in the UPVN panel and press Setup Scene.")
            script = parse_string('label start:\n    "UPVN — press P after Create Project + Setup Scene in the UPVN panel."\n    return\n')
            ctrl = VNController(script_dict=script)
            ctrl.load()
            ctrl._load_diag = diag
            logic._upvn_ctrl = ctrl
            _register_overlay()

    # per-frame tick with dt
    global _last_time
    now = time.time()
    dt = now - _last_time if _last_time else 0.016
    _last_time = now
    # clamp dt
    dt = min(0.05, max(0.0, dt))
    ctrl = logic._upvn_ctrl
    try:
        ctrl.update(dt=dt)
    except Exception as e:
        # one missing asset must never spam the console every frame nor kill the game
        if not getattr(logic, "_upvn_tick_error", False):
            logic._upvn_tick_error = True
            print(f"[UPVN] tick error (shown once, game keeps running): {e}")
            try:
                import traceback
                traceback.print_exc()
            except Exception:
                pass
    # also tick sub-managers for transitions
    try:
        if ctrl.sprite_mgr:
            ctrl.sprite_mgr.update(dt)
        if ctrl.scene_mgr and hasattr(ctrl.scene_mgr, "transition_alpha"):
            # no-op, just for logging
            pass
    except Exception:
        pass
    # M18 debug/QA keys: F1 state dump, F12 in-game screenshot
    try:
        _debug_keys(logic, ctrl)
    except Exception:
        pass


_shot_seq = [0]


def _debug_keys(logic, ctrl):
    """F1 prints current story state; F12 saves an in-game screenshot PNG."""
    if not HAS_BGE:
        return
    try:
        from engine.core.vn_controller import _bge_just
        import bge as _bge
        f1 = getattr(_bge.events, "F1KEY")
        f12 = getattr(_bge.events, "F12KEY")
    except Exception:
        return
    if _bge_just("keyboard", f1):
        st = ctrl.state
        ev = ctrl.current_event or {}
        print(f"[UPVN] F1 state: label={st.current_label} idx={st.instruction_index} "
              f"event={ev.get('type')} vars={ {k: v for k, v in list(st.variables.items())[:12]} }")
    if _bge_just("keyboard", f12):
        _shot_seq[0] += 1
        import os as _os
        base = _os.path.dirname(_bge.logic.expandPath("//"))
        d = _os.path.join(base, "screenshots")
        _os.makedirs(d, exist_ok=True)
        out = _os.path.join(d, f"upvn_ingame_{int(time.time())}_{_shot_seq[0]}.png")
        try:
            _bge.render.makeScreenshot(out)
            print(f"[UPVN] F12 screenshot saved: {out}")
        except Exception as e:
            print(f"[UPVN] F12 screenshot failed: {e}")


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
        # load-failure diagnostic: prominent, on-screen (players never read
        # the console). Red lines in the upper half.
        diag = getattr(ctrl, "_load_diag", None)
        if diag:
            y = height - 90
            blf.size(0, 22)
            for i, line in enumerate(diag):
                blf.color(0, 1.0, 0.32, 0.32, 1.0)
                blf.position(0, 60, y - i * 30, 0)
                blf.draw(0, line)
            return
        # This is a minimal blf overlay; the real UI is planes (Dialogue_Box) which already shows text.
        # We only draw if DialogueBox visible and typewriter not done
        ui = getattr(ctrl, "ui_mgr", None)
        if ui and ui.visible:
            text = ui.revealed_text()
            who = ui.current_who or ""
            # draw speaker
            blf.position(0, 50, 50, 0)
            blf.size(0, 18)
            blf.color(0, 0.72, 0.76, 1, 1.0)
            blf.draw(0, who)
            # draw dialogue
            blf.position(0, 50, 30, 0)
            blf.size(0, 20)
            blf.color(0, 0.92, 0.93, 1, 1.0)
            # wrap manually for blf (simple)
            blf.draw(0, text[:80])
        # menu: draw choices as blf clickable areas
        if ev.get("type") == "menu":
            y = height // 2
            for i, ch in enumerate(ev.get("choices", [])):
                blf.position(0, width // 2 - 100, y - i * 40, 0)
                blf.size(0, 20)
                blf.color(0, 0.85, 0.95, 1, 1.0)
                blf.draw(0, f"{i + 1}. {ch['text']}")
            # footer hint (M18: number keys select)
            blf.position(0, width // 2 - 100, y - len(ev.get("choices", [])) * 40 - 30, 0)
            blf.size(0, 14)
            blf.color(0, 0.6, 0.6, 0.6, 1.0)
            blf.draw(0, "Press 1-9 to choose")
        # modal screens (save/load/history/quick menu): text fallback until the
        # 3D plane UI is wired — lets S/L/H/Q be usable without extra objects
        sm = getattr(ctrl, "screen_mgr", None)
        if sm is not None and sm.is_modal_active():
            scr = sm.active_modal
            title = str(getattr(scr, "title", None) or getattr(scr, "name", "screen"))
            y = height - 60
            blf.position(0, width // 2 - 150, y, 0)
            blf.size(0, 24)
            blf.color(0, 0.95, 0.85, 0.4, 1.0)
            blf.draw(0, title)
            page = getattr(scr, "page", None)
            if page is not None:
                blf.position(0, width // 2 - 150, y - 30, 0)
                blf.size(0, 16)
                blf.color(0, 0.8, 0.8, 0.8, 1.0)
                blf.draw(0, f"page {int(page) + 1} — ←/→ to page, ESC to close")
    except Exception as e:
        # blf errors are non-fatal
        print(f"[frontend draw_overlay] {e}")
