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


def _unregister_overlay():
    """Drop any leftover blf post_draw callback — UI is 3D objects only."""
    try:
        import bge as _bge
        sc = _bge.logic.getCurrentScene()
        pd = getattr(sc, "post_draw", None)
        if not pd:
            return
        for fn in list(pd):
            name = getattr(fn, "__name__", "")
            if name in ("draw_overlay", "draw_blf"):
                try:
                    pd.remove(fn)
                except Exception:
                    pass
    except Exception:
        pass


def _hide_idle_sprites():
    if not HAS_BGE:
        return
    try:
        import bge as _bge
        sc = _bge.logic.getCurrentScene()
        for ob in sc.objects:
            if str(ob.name).startswith("Sprite_"):
                ob.visible = False
    except Exception:
        pass


def _get_obj(name):
    try:
        import bge as _bge
        return _bge.logic.getCurrentScene().objects.get(name)
    except Exception:
        return None


def _show_mouse():
    if not HAS_BGE:
        return
    try:
        import bge as _bge
        try:
            _bge.render.showMouse(True)
        except Exception:
            pass
        try:
            _bge.logic.mouse.visible = True
        except Exception:
            pass
    except Exception:
        pass


def _sync_world_ui(ctrl):
    if not HAS_BGE or ctrl is None:
        return
    try:
        from engine.ui.world_ui import build_world_ui, apply_world_ui
        from engine.render.contract import CAMERA_UI_ORTHO_SCALE
        payload = build_world_ui(
            getattr(ctrl, "current_event", None),
            ui_mgr=getattr(ctrl, "ui_mgr", None),
            diag=getattr(ctrl, "_load_diag", None),
        )
        ortho = CAMERA_UI_ORTHO_SCALE
        try:
            import bge as _bge
            cam = _bge.logic.getCurrentScene().active_camera
            ortho = float(getattr(cam, "ortho_scale", ortho) or ortho)
        except Exception:
            pass
        apply_world_ui(_get_obj, payload, ortho=ortho)
    except Exception as e:
        # M25 BUG-002: this used to be a bare `except: pass`, which silently
        # swallowed every UI failure every tick (the player also discards
        # Python stdout, so field reports saw a black screen with no clue).
        try:
            import bge as _bge
            if not getattr(_bge.logic, "_upvn_ui_sync_err", False):
                _bge.logic._upvn_ui_sync_err = True
                _bge.logic._last_upvn_error = f"world UI sync: {e}"
                print(f"[UPVN] world UI sync error (shown once): {e}")
        except Exception:
            pass


def _object_under_cursor():
    if not HAS_BGE:
        return None
    try:
        import bge as _bge
        sc = _bge.logic.getCurrentScene()
        cam = sc.active_camera
        x, y = _bge.logic.mouse.position
        hit = None
        try:
            hit = cam.getScreenRay(x, y, 80.0)
        except Exception:
            hit = None
        if hit is None:
            try:
                vect = cam.getScreenVect(x, y)
                origin = cam.worldPosition
                target = origin + vect * 80.0
                hit, _p, _n = cam.rayCast(target, origin, 80.0)
            except Exception:
                hit = None
        if hit is None:
            return None
        return getattr(hit, "name", None)
    except Exception:
        return None


def _tick_pointer(ctrl):
    """LMB over choice_N 3D plane → VNController.choose(i)."""
    if not HAS_BGE or ctrl is None:
        return
    ev = getattr(ctrl, "current_event", None) or {}
    if ev.get("type") != "menu":
        return
    try:
        import bge as _bge
        from engine.core.vn_controller import _bge_just
        from engine.ui.pointer import HotspotMap, PointerTracker
        from engine.ui.world_ui import normalize_hit_name
        logic = _bge.logic
        choices = ev.get("choices") or []
        key = tuple(c.get("id", i) for i, c in enumerate(choices))
        if getattr(logic, "_upvn_ptr_key", None) != key:
            logic._upvn_ptr = PointerTracker(HotspotMap.from_choices(choices))
            logic._upvn_ptr_key = key
        tr = logic._upvn_ptr
        name = normalize_hit_name(_object_under_cursor())
        clicked = _bge_just("mouse", _bge.events.LEFTMOUSE)
        for pe in tr.update(name, clicked=clicked):
            idx = tr.choose(pe)
            if idx is not None:
                ctrl.choose(idx)
                return
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
    _show_mouse()

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
                _unregister_overlay()
                _hide_idle_sprites()
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
            _unregister_overlay()
            _hide_idle_sprites()

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
    try:
        _sync_world_ui(ctrl)
        _tick_pointer(ctrl)
    except Exception:
        pass
    try:
        _render_diag(logic)
    except Exception:
        pass
    # M18 debug/QA keys: F1 state dump, F12 in-game screenshot
    try:
        _debug_keys(logic, ctrl)
    except Exception:
        pass
    # M25 QA: optional per-tick state heartbeat for external harnesses.
    # The standalone player's embedded Python stdout is block-buffered and
    # lost on kill -9, so the smoke walkthrough (tools/smoke_walkthrough.sh)
    # polls this machine-readable file instead of the log. Set the env var
    # UPVN_HEARTBEAT=/path/to.json to enable; unset = zero overhead.
    try:
        _hb = os.environ.get("UPVN_HEARTBEAT")
        if _hb:
            import json as _json
            _st = ctrl.state
            _evt = ctrl.current_event or {}
            _sm = getattr(ctrl, "screen_mgr", None)
            with open(_hb, "w") as _f:
                _f.write(_json.dumps({
                    "label": _st.current_label,
                    "idx": _st.instruction_index,
                    "event": _evt.get("type"),
                    "choices": len(_evt.get("choices") or []),
                    "modal": (None if _sm is None or _sm.active_modal is None
                              else _sm.active_modal.name),
                }))
    except Exception:
        pass


_shot_seq = [0]


def _render_diag(logic):
    """Draw the F1 diagnostic into the existing dialogue FONT objects."""
    if not getattr(logic, "_upvn_diag_on", False):
        return
    from engine.ui.world_ui import set_font_text
    sc = logic.getCurrentScene()
    sp = sc.objects.get("Speaker_Text")
    dt = sc.objects.get("Dialogue_Text")
    box = sc.objects.get("Dialogue_Box")
    for ob in (sp, dt, box):
        if ob is not None:
            ob.visible = True
    set_font_text(sp, "UPVN DIAG (F1 to close)")
    set_font_text(dt, getattr(logic, "_upvn_diag", ""))


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
        # M25: the player discards Python stdout, so a console dump is useless
        # in the field. F1 now also toggles an ON-SCREEN diagnostic using the
        # existing Speaker_Text/Dialogue_Text FONT objects (no new UI system).
        try:
            import bge as _bge
            sc = _bge.logic.getCurrentScene()
            cam = sc.active_camera
            lines = [
                f"label: {st.current_label}  ip: {st.instruction_index}",
                f"mode: {ev.get('type')}  choices: {len(ev.get('choices') or [])}",
                f"script: {getattr(ctrl, 'script_path', '?')}",
                f"camera: {cam.name if cam else None}",
                f"vars: { {k: v for k, v in list(st.variables.items())[:6]} }",
                f"last error: {getattr(_bge.logic, '_last_upvn_error', None)}",
            ]
            _bge.logic._upvn_diag_on = not getattr(_bge.logic, "_upvn_diag_on", False)
            _bge.logic._upvn_diag = "\n".join(lines)
        except Exception:
            pass
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


# blf overlay removed — UI is 3D FONT / choice planes (engine/ui/world_ui.py)
