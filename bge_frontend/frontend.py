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
            # M26: directories are valid script sources — VNController.load()
            # merges every *.rpy/*.urpy inside (multi-file Ren'Py projects,
            # which is what tools/renpy_convert.py points at: '//../game').
            if os.path.isfile(p) or os.path.isdir(p):
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


def _hide_idle_sprites(ctrl=None):
    """Hide Sprite_* planes no story actor currently claims.

    M26 bugfix: this used to hide *every* Sprite_* unconditionally right
    after ctrl.load() — but the load already applied the story's opening
    `show` events, so the opening sprite was made visible and immediately
    hidden again (the field symptom: stage color changed, sprite never
    appeared, no error anywhere). Planes claimed by ctrl.sprite_mgr are kept."""
    if not HAS_BGE:
        return
    keep = set()
    try:
        mgr = getattr(ctrl, "sprite_mgr", None)
        for info in (getattr(mgr, "planes", None) or {}).values():
            ob = info.get("obj")
            if ob is not None:
                keep.add(str(getattr(ob, "name", "")))
    except Exception:
        pass
    try:
        import bge as _bge
        sc = _bge.logic.getCurrentScene()
        for ob in sc.objects:
            if str(ob.name).startswith("Sprite_") and str(ob.name) not in keep:
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


def _sync_world_ui(ctrl, hovered=None):
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
        # hovered comes in as a parameter (set by _tick_pointer) — this
        # function has no `logic` in scope
        ortho = CAMERA_UI_ORTHO_SCALE
        try:
            import bge as _bge
            cam = _bge.logic.getCurrentScene().active_camera
            ortho = float(getattr(cam, "ortho_scale", ortho) or ortho)
        except Exception:
            pass
        apply_world_ui(_get_obj, payload, ortho=ortho, hovered=hovered)
        # expose the last payload so the QA heartbeat can report what the UI
        # actually decided (text, visibility) — not just the story position.
        try:
            import bge as _bge
            _bge.logic._upvn_last_payload = payload
        except Exception:
            pass
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


def _pointer_probe(sc, cam):
    """Env-gated (UPVN_POINTER_PROBE=1) once-per-30-ticks physics probe:
    what does a scene rayCast see along key columns? Answers ray-vs-SENSOR
    questions in the field without touching game code."""
    import bge as _bge
    logic = _bge.logic
    logic._upvn_probe_n = getattr(logic, "_upvn_probe_n", 0) + 1
    if logic._upvn_probe_n % 30 != 1:
        return
    try:
        for label, pz in (("choice0col", 1.97), ("choice1col", 1.41),
                          ("spritecol", 0.0), ("high", 4.0), ("low", -4.0)):
            hit, p, n = cam.rayCast((0.0, cam.worldPosition.y + 5.0, pz),
                                    (0.0, cam.worldPosition.y - 5.0, pz), 20.0)
            print(f"[probe] {label} z={pz}: hit={getattr(hit,'name',None)} at={p}")
    except Exception as e:
        print(f"[probe] failed: {e}")


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
            # M26: getScreenRay is unreliable on orthographic cameras in
            # UPBGE 0.50 (measured in-field: always None on Camera_UI), so
            # shoot an explicit ray straight along the camera's view axis
            # through the frustum point the mouse selects. UPBGE 0.50's
            # mouse.position y is measured from the TOP of the window.
            try:
                w = float(_bge.render.getWindowWidth()) or 1280.0
                h = float(_bge.render.getWindowHeight()) or 800.0
            except Exception:
                w, h = 1280.0, 800.0
            try:
                ortho = float(getattr(cam, "ortho_scale", 0.0) or 0.0)
            except Exception:
                ortho = 0.0
            if ortho <= 0.0:
                ortho = 15.0  # contract CAMERA_UI_ORTHO_SCALE
            nx = float(x) - 0.5
            ny = 0.5 - float(y)                       # top-origin → up-positive
            px = cam.worldPosition.x + nx * ortho
            pz = cam.worldPosition.z + ny * ortho * (h / w)
            py = cam.worldPosition.y
            try:
                # KX_Scene has no rayCast in UPBGE 0.50 — cast from the
                # camera object (KX_GameObject.rayCast, ignores self).
                hit, _p, _n = cam.rayCast((px, py + 5.0, pz),
                                          (px, py - 5.0, pz), 20.0)
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
    try:
        import bge as _bge
        if ev.get("type") != "menu":
            _bge.logic._upvn_hover = None
    except Exception:
        pass
    if ev.get("type") != "menu":
        return
    try:
        import bge as _bge
        import os as _os
        if _os.environ.get("UPVN_POINTER_PROBE"):
            _pointer_probe(_bge.logic.getCurrentScene(),
                           _bge.logic.getCurrentScene().active_camera)
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
        logic._upvn_hover = name if name and str(name).startswith("choice_") \
            else None
        clicked = _bge_just("mouse", _bge.events.LEFTMOUSE)
        # M26 field diagnostics (visible via UPVN_DEBUG_TEE): log whenever the
        # ray's hover target or the click flag changes — a dropped synthetic
        # click or a ray miss is otherwise invisible in the player.
        sig = (name, bool(clicked))
        if getattr(logic, "_upvn_ptr_sig", None) != sig:
            logic._upvn_ptr_sig = sig
            mx, my = (getattr(_bge.logic, "mouse").position or (0.0, 0.0))
            print(f"[pointer] hover={name} clicked={clicked} mouse=({mx:.3f},{my:.3f})")
        for pe in tr.update(name, clicked=clicked):
            idx = tr.choose(pe)
            if idx is not None:
                print(f"[pointer] click → choice {idx}")
                ctrl.choose(idx)
                return
    except Exception as e:
        import traceback
        print(f"[pointer] tick failed: {e}")
        traceback.print_exc()


def _apply_camera_state(logic, ctrl):
    """M26c: apply the interpreter's camera_zoom tween to the ortho game
    camera. `camera zoom 1.2 duration 1.0 with ease` used to set state only —
    nothing in the player applied it. Ortho scale = base / zoom, so zoom>1
    moves closer. UI layout re-reads ortho each frame, so dialogue/choices
    stay framed (M24 zoom-stable UI holds)."""
    try:
        cam_state = getattr(ctrl.state, "camera", None) or {}
        zoom_to = cam_state.get("_zoom_to")
        if zoom_to is None:
            return
        import time as _t
        t0 = cam_state.get("_zoom_t0")
        dur = float(cam_state.get("_zoom_dur", 0.0) or 0.0)
        if t0 is not None and dur > 0:
            t_raw = (_t.time() - t0) / dur
            if t_raw < 1.0:
                from engine.atl.easing import get_easing
                ease = get_easing(cam_state.get("_zoom_ease") or "ease")
                frm = float(cam_state.get("_zoom_from", 1.0))
                zoom = frm + (float(zoom_to) - frm) * ease(min(1.0, max(0.0, t_raw)))
            else:
                zoom = float(zoom_to)
                # tween finished — drop the transient keys so this stays cheap
                for k in ("_zoom_from", "_zoom_to", "_zoom_dur",
                          "_zoom_ease", "_zoom_t0"):
                    cam_state.pop(k, None)
        else:
            zoom = float(zoom_to)
        cam = logic.getCurrentScene().active_camera
        if cam is not None and getattr(cam, "ortho_scale", None) is not None:
            from engine.render.contract import CAMERA_UI_ORTHO_SCALE
            base = CAMERA_UI_ORTHO_SCALE
            try:
                marker = logic._upvn_ortho_base
            except Exception:
                marker = None
            if marker is None:
                # first run: remember the un-zoomed base the template set
                logic._upvn_ortho_base = float(cam.ortho_scale) *                     float(cam_state.get("zoom", 1.0) or 1.0)
                marker = logic._upvn_ortho_base
            base = marker
            cam.ortho_scale = max(1.0, base / max(0.05, zoom))
    except Exception as e:
        try:
            if not logic._upvn_cam_err:
                logic._upvn_cam_err = True
                print(f"[UPVN] camera zoom apply failed: {e}")
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


def _install_debug_tee(logic):
    """Mirror Python stdout/stderr into a file when UPVN_DEBUG_TEE is set.

    The standalone player's stdout is block-buffered and lost on kill -9, so
    field diagnostics printed with print() were unobservable (M26). With the
    tee set — UPVN_DEBUG_TEE=/tmp/upvn_debug.log — every engine print (script
    load, asset decisions, errors) lands in the file line-buffered, next to
    the UPVN_HEARTBEAT state file."""
    if getattr(logic, "_upvn_tee_installed", False):
        return
    logic._upvn_tee_installed = True
    path = os.environ.get("UPVN_DEBUG_TEE")
    if not path:
        return
    try:
        f = open(path, "a", buffering=1)

        class _Tee:
            def __init__(self, *streams):
                self._streams = streams

            def write(self, data):
                for s in self._streams:
                    try:
                        s.write(data)
                    except Exception:
                        pass
                return len(data)

            def flush(self):
                for s in self._streams:
                    try:
                        s.flush()
                    except Exception:
                        pass

        sys.stdout = _Tee(sys.stdout, f)
        sys.stderr = _Tee(sys.stderr, f)
        print(f"[UPVN] debug tee active → {path}")
    except Exception as e:
        print(f"[UPVN] debug tee failed ({path}): {e}")


def main(cont=None):
    """Entry for UPBGE Python controller. Called every frame."""
    if not HAS_BGE:
        print("[UPVN] Not running inside UPBGE — frontend.main is a no-op headlessly")
        return
    import bge as _bge
    logic = _bge.logic
    ensure_engine_syspath()
    _install_debug_tee(logic)
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
                _hide_idle_sprites(ctrl)
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
            _hide_idle_sprites(ctrl)

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
        if ctrl.audio_mgr is not None and hasattr(ctrl.audio_mgr, "update"):
            ctrl.audio_mgr.update(dt)
        if ctrl.sprite_mgr:
            ctrl.sprite_mgr.update(dt)
        if ctrl.scene_mgr and hasattr(ctrl.scene_mgr, "transition_alpha"):
            # no-op, just for logging
            pass
    except Exception:
        pass
    try:
        import bge as _bge
        _sync_world_ui(ctrl,
                       hovered=getattr(_bge.logic, "_upvn_hover", None))
        _tick_pointer(ctrl)
        _apply_camera_state(logic, ctrl)
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
            _payload = getattr(logic, "_upvn_last_payload", None) or {}
            _interp = getattr(ctrl, "interp", None)
            _hb_data = {
                "label": _st.current_label,
                "idx": _st.instruction_index,
                "event": _evt.get("type"),
                "choices": len(_evt.get("choices") or []),
                "modal": (None if _sm is None or _sm.active_modal is None
                          else _sm.active_modal.name),
                # --- M26d: what the UI layer actually decided this tick, plus
                # the rewind/history counters a harness needs to assert on.
                "speaker": _payload.get("speaker"),
                "dialogue": _payload.get("dialogue"),
                "dialogue_visible": bool(_payload.get("dialogue_visible")),
                "history": len(getattr(_st, "history", []) or []),
                "history_open": bool(_sm and _sm.is_overlay_visible("history"))
                if _sm is not None else False,
                "rollback_depth": len(getattr(_interp, "rollback_stack", []) or [])
                if _interp is not None else 0,
                "rollforward_depth": len(getattr(ctrl, "_forward_stack", []) or []),
                "skipping": bool(getattr(_st, "skip", False)),
                "auto": bool(getattr(_st, "auto", False)),
            }
            try:
                _sc = logic.getCurrentScene()
                for _n, _k in (("Dialogue_Text", "font_body"),
                               ("Speaker_Text", "font_speaker"),
                               ("History_Text", "history_body")):
                    try:
                        _o = _sc.objects.get(_n)
                        _bo = getattr(_o, "blenderObject", None) if _o is not None else None
                        _d = getattr(_bo, "data", None) if _bo is not None else None
                        _hb_data[_k] = getattr(_d, "body", None) if _d is not None else None
                        # world scale + curve font size decide how big the text
                        # actually draws; `.size` on a KX object is not the
                        # transform (it silently creates a python property).
                        if _bo is not None:
                            _hb_data[_k + "_scale"] = [round(float(v), 4) for v in _bo.scale]
                            _hb_data[_k + "_font"] = round(float(getattr(_d, "font_size", 1.0)), 4) if _d is not None else None
                        elif _o is not None:
                            _hb_data[_k + "_scale"] = [round(float(v), 4) for v in _o.worldScale]
                    except Exception:
                        pass
            except Exception:
                pass
            with open(_hb, "w") as _f:
                _f.write(_json.dumps(_hb_data))
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
