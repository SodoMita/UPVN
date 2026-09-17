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
            if c.startswith("//"):
                # M29 fix: bge.logic.expandPath('//…') can yield a relative
                # path in the standalone player (bpy.data.filepath handling
                # differs from the editor), which made every converted game
                # fall through to the "script not found" screen. Anchor '//'
                # to the .blend directory ourselves; where bpy is unavailable
                # (unit tests) or filepath empty, keep expandPath behaviour.
                base = ""
                try:
                    import bpy as _bpy
                    bp = getattr(getattr(_bpy, "data", None), "filepath", "") or ""
                    base = os.path.dirname(os.path.abspath(bp)) if bp else ""
                except Exception:
                    base = ""
                p = (os.path.normpath(os.path.join(base, c[2:])) if base
                     else logic.expandPath(c))
            else:
                p = logic.expandPath(c)
        except Exception:
            p = c
        if not getattr(logic, "_upvn_resolve_logged", False):
            try:
                import bpy as _bpy_dbg
                _bp = getattr(getattr(_bpy_dbg, "data", None), "filepath", "")
            except Exception:
                _bp = "<no bpy>"
            print(f"[UPVN] resolve try {c!r} -> {p!r} (blend={_bp!r})")
        tried.append(p)
        try:
            # M26: directories are valid script sources — VNController.load()
            # merges every *.rpy/*.urpy inside (multi-file Ren'Py projects,
            # which is what tools/renpy_convert.py points at: '//../game').
            if os.path.isfile(p) or os.path.isdir(p):
                return os.path.abspath(p), tried
        except Exception:
            pass
    logic._upvn_resolve_logged = True
    return None, tried


def _prop(owner, name):
    """Read a game property from either representation (dict or KX object)."""
    if owner is None:
        return None
    try:
        if isinstance(owner, dict):
            return owner.get(name)
        return owner[name] if name in owner else None
    except Exception:
        return None


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


def _hide_idle_ui():
    """Hide UI pieces that must not show until story state opens them.

    M29 parity (SDK tutorial comparison): converted blends shipped with
    choice planes, the backlog panel and stray default Cube/Light visible
    from frame one, drawing slabs over the scene.
    """
    if not HAS_BGE:
        return
    try:
        import bge as _bge
        sc = _bge.logic.getCurrentScene()
        for ob in sc.objects:
            n = str(ob.name)
            if (n.startswith("choice_")
                    or n in ("History_Box", "History_Text", "Rewind_Text",
                             "Cube", "Light")):
                ob.visible = False
    except Exception:
        pass


def _gui_json_path():
    """Locate upvn_gui.json next to/above the .blend (player-safe)."""
    try:
        import bpy as _bpy
        import os
        bp = getattr(getattr(_bpy, "data", None), "filepath", "") or ""
        if not bp:
            return None
        bdir = os.path.dirname(os.path.abspath(bp))
        for cand in (os.path.join(bdir, os.pardir, "game", "upvn_gui.json"),
                     os.path.join(bdir, os.pardir, "assets", "gui",
                                  "upvn_gui.json"),
                     os.path.join(bdir, "game", "upvn_gui.json")):
            p = os.path.abspath(cand)
            if os.path.isfile(p):
                return p
    except Exception:
        pass
    return None


def _apply_gui_par():
    """Runtime parity layer (M29): make the player frame match the original.

    Wired blends bake generic defaults (white textbox, template text sizes)
    and converted projects can carry stray stage meshes; the per-project
    upvn_gui.json only reaches runtime consumers partially, so apply the
    visible deltas here: textbox tint, json text sizes, stray-mesh hide.
    """
    if not HAS_BGE:
        return
    try:
        import bge as _bge
        import json
        logic = _bge.logic
        sc = logic.getCurrentScene()
        cfg = {}
        jp = _gui_json_path()
        if jp:
            try:
                cfg = json.load(open(jp, encoding="utf-8")) or {}
            except Exception:
                cfg = {}
        colors = cfg.get("colors") or {}
        col = colors.get("dialogue_box")
        if col in (None, "#ffffff", "#ffffffff"):
            # unsampled stock gui: gui/textbox.png is flat black 80%
            # (pixel-sampled in the parity loop); without this fallback the
            # white default would be re-tinted into MAUI's emission at
            # runtime, overwriting the baked dark box
            col = "#000000cc"
        print(f"[UPVN] gui_par: json={jp} dialogue_box={col!r}")
        _box = sc.objects.get("Dialogue_Box")
        print("[UPVN] gui_par: box color now",
              tuple(round(c, 2) for c in _box.color) if _box else None)
        if col:
            hx = col.lstrip("#")
            rgba = [int(hx[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
            rgba.append(int(hx[6:8], 16) / 255.0 if len(hx) >= 8 else 0.8)
            box = sc.objects.get("Dialogue_Box")
            if box is not None:
                box.color = rgba
                # MAUI is an emission-based unlit material: object color does
                # not multiply it — tint the emission node directly.
                try:
                    bo = getattr(box, "blenderObject", None)
                    mat = (bo.material_slots[0].material
                           if bo is not None and bo.material_slots else None)
                    nt = getattr(mat, "node_tree", None)
                    if nt is not None:
                        for n in nt.nodes:
                            if n.type == "EMISSION":
                                # llvmpipe reads ObjectInfo.Color as white: an
                                # emission linked from ObjectInfo would stay
                                # white no matter what we set (M30 font fix,
                                # same class of bug for the box).
                                for lk in list(n.inputs["Color"].links):
                                    nt.links.remove(lk)
                                n.inputs["Color"].default_value = rgba
                            if n.type == "BSDF_PRINCIPLED":
                                n.inputs["Base Color"].default_value = rgba
                                if "Alpha" in n.inputs:
                                    n.inputs["Alpha"].default_value = rgba[3]
                except Exception:
                    pass
        sizes = cfg.get("sizes") or {}
        ortho = 15.0
        cam = (getattr(sc, "active_camera", None)
               or getattr(sc, "camera", None))
        if cam is not None:
            ortho = float(getattr(cam, "ortho_scale", 15.0) or 15.0)
        w = float(_bge.render.getWindowWidth() or 1280)
        h = float(_bge.render.getWindowHeight() or 720)
        world_h = ortho * h / w
        px2wu = world_h / h
        for obj_name, key in (("Speaker_Text", "name"),
                              ("Dialogue_Text", "text")):
            px = sizes.get(key)
            ob = sc.objects.get(obj_name)
            if px and ob is not None:
                try:
                    ob.size = float(px) * px2wu
                except Exception:
                    pass
        # --- project fonts (Ren'Py parity): the converted project ships the
        # original's typefaces in assets/fonts|game/fonts (copied by
        # renpy_convert.py) and names them in upvn_gui.json["fonts"]. The
        # wired template blend only knows //fonts/Lato|Hack (absent), so
        # without this the player renders tofu/DejaVu instead of the
        # project's face. Load once per process; check_existing dedupes.
        fonts = cfg.get("fonts") or {}
        if fonts and not getattr(logic, "_upvn_fonts_applied", False):
            logic._upvn_fonts_applied = True
            import bpy as _bpy
            bdir = os.path.dirname(os.path.abspath(
                getattr(getattr(_bpy, "data", None), "filepath", "") or "."))

            def _load_font(fname):
                if not fname:
                    return None
                base = os.path.basename(str(fname))
                for rel in (os.path.join("..", "assets", "fonts", base),
                            os.path.join("..", "game", "fonts", base),
                            os.path.join("fonts", base),
                            os.path.join("..", "blend", "fonts", base)):
                    p = os.path.abspath(os.path.join(bdir, rel))
                    try:
                        if os.path.isfile(p):
                            return _bpy.data.fonts.load(p, check_existing=True)
                    except Exception:
                        continue
                # projects that reference a face without shipping it (stock
                # gui.rpy names DejaVuSans.ttf): fall back to system fonts via
                # the same resolver the baker uses
                try:
                    from engine.render.contract import find_ui_font
                    fn = find_ui_font(base)
                    if fn:
                        return _bpy.data.fonts.load(fn, check_existing=True)
                except Exception:
                    pass
                return None

            f_text = _load_font(fonts.get("text"))
            f_name = _load_font(fonts.get("name")) or f_text
            applied = []
            for obj_name, fnt in (("Dialogue_Text", f_text),
                                  ("Dialogue_Shadow", f_text),
                                  ("Speaker_Text", f_name),
                                  ("Speaker_Shadow", f_name)):
                ob = sc.objects.get(obj_name)
                if ob is None or fnt is None:
                    continue
                # player: KX_GameObject wraps the bpy object; the FONT curve
                # lives on blenderObject.data (editor: ob.data directly)
                for holder in (getattr(ob, "blenderObject", None), ob):
                    cur = getattr(holder, "data", None)
                    if cur is not None and hasattr(cur, "font"):
                        try:
                            cur.font = fnt
                            applied.append(obj_name)
                        except Exception:
                            pass
                        break
            print(f"[UPVN] gui_par: project fonts text={fonts.get('text')!r} "
                  f"name={fonts.get('name')!r} applied_to={applied}")
        keep = ("BGIMG_", "Sprite_img_", "Sprite_", "Dialogue_Box",
                "Speaker_Text", "Dialogue_Text", "choice_", "History_",
                "Rewind_", "Camera", "VNController", "Pos_", "marker_",
                "preset_")
        for ob in sc.objects:
            n = str(ob.name)
            if ob.visible and getattr(ob, "type", "") == "MESH" and \
                    not n.startswith(keep):
                ob.visible = False
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
        _sm = getattr(ctrl, "screen_mgr", None)
        history_open = False
        history_entries = None
        if _sm is not None:
            try:
                history_open = bool(_sm.is_overlay_visible("history"))
            except Exception:
                history_open = False
            try:
                history_entries = _sm.get_history_entries(strip=True)
            except Exception:
                history_entries = None
        if history_entries is None:
            history_entries = getattr(getattr(ctrl, "state", None), "history", [])
        # M28: collect compat errors and screen errors for display
        interp = getattr(ctrl, "interp", None)
        compat_errors = []
        if interp is not None:
            try:
                compat_errors = list(getattr(interp, "init_errors", []) or []) + list(getattr(interp, "python_errors", []) or [])
            except Exception:
                pass
        current_event = getattr(ctrl, "current_event", None)
        payload = build_world_ui(
            current_event,
            ui_mgr=getattr(ctrl, "ui_mgr", None),
            diag=getattr(ctrl, "_load_diag", None),
            history_entries=history_entries,
            history_open=history_open,
            rewind_depth=getattr(ctrl, "rewind_depth", lambda: 0)(),
            history_scroll=int(getattr(ctrl, "_history_scroll", 0) or 0),
            screen_errors=compat_errors if compat_errors else None,
        )
        # M28: if current event has errors, log them visibly
        if current_event and current_event.get("errors"):
            for err in current_event["errors"][:2]:
                print(f"[UPVN] event error at {current_event.get('_loc')}: {err}")
        ortho = CAMERA_UI_ORTHO_SCALE
        try:
            import bge as _bge
            cam = _bge.logic.getCurrentScene().active_camera
            ortho_raw = float(getattr(cam, "ortho_scale", ortho) or ortho)
            # Perspective fix: if ortho is 0 (perspective camera), use 15 for layout so buttons not tiny
            # User reports perspective triggers outside, ortho OK — tiny buttons in perspective caused mismatch
            ortho = ortho_raw if ortho_raw > 0.001 else 15.0
        except Exception:
            pass
        status = apply_world_ui(_get_obj, payload, ortho=ortho, hovered=hovered)
        # Log UI apply failures once
        if status and status.get("failed", 0) > 0:
            try:
                import bge as _bge
                if not getattr(_bge.logic, "_upvn_ui_failed_logged", False):
                    _bge.logic._upvn_ui_failed_logged = True
                    print(f"[UPVN] world UI apply: {status['applied']} ok, {status['failed']} failed, errors={status['errors'][:3]}")
            except Exception:
                pass
        try:
            import bge as _bge
            _bge.logic._upvn_last_payload = payload
            _bge.logic._upvn_last_ui_status = status
        except Exception:
            pass
    except Exception as e:
        import traceback
        traceback.print_exc()
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


def _debug_draw_ray(origin, target, hit_point=None, hit_name=None, color_hit=(0,1,0), color_miss=(1,0,0)):
    """Debug ray render — draws ray from origin to target/hit_point for one frame.
    
    User requested debug ray render because buttons triggered outside visible mesh,
    likely ray being in wrong place when mesh modified/translated.
    """
    try:
        import bge as _bge
        # Check if debug enabled via VNController property or env var
        try:
            sc = _bge.logic.getCurrentScene()
            ctrl = sc.objects.get("VNController")
            debug_enabled = False
            if ctrl is not None:
                try:
                    if "upvn_debug_ray" in ctrl:
                        debug_enabled = bool(ctrl["upvn_debug_ray"])
                    elif "upvn_debug" in ctrl:
                        debug_enabled = bool(ctrl["upvn_debug"])
                except Exception:
                    pass
            # Also check env var or logic flag
            if not debug_enabled:
                try:
                    import os
                    if os.environ.get("UPVN_DEBUG_RAY") or os.environ.get("UPVN_DEBUG"):
                        debug_enabled = True
                except Exception:
                    pass
            try:
                if getattr(_bge.logic, "_upvn_debug_ray", False):
                    debug_enabled = True
            except Exception:
                pass
            if not debug_enabled:
                # Always draw when hover changes? For now, only when debug enabled
                # But we can enable via game property upvn_debug_ray on VNController
                return
        except Exception:
            return

        try:
            # Draw main ray
            if hit_point is not None:
                # Hit — green
                _bge.render.drawLine(origin, hit_point, color_hit)
                # Draw small cross at hit point
                s = 0.1
                _bge.render.drawLine((hit_point[0]-s, hit_point[1], hit_point[2]), (hit_point[0]+s, hit_point[1], hit_point[2]), (1,1,0))
                _bge.render.drawLine((hit_point[0], hit_point[1]-s, hit_point[2]), (hit_point[0], hit_point[1]+s, hit_point[2]), (1,1,0))
                _bge.render.drawLine((hit_point[0], hit_point[1], hit_point[2]-s), (hit_point[0], hit_point[1], hit_point[2]+s), (1,1,0))
                # Draw line from hit to target (faint)
                _bge.render.drawLine(hit_point, target, (0.5,0.5,0.5))
            else:
                # Miss — red
                _bge.render.drawLine(origin, target, color_miss)
            
            # Also draw camera frustum boundary for debugging outside trigger
            # Draw visible frame bounds at y=0 plane
            try:
                cam = sc.active_camera
                ortho = float(getattr(cam, "ortho_scale", 15.0) or 15.0)
                if ortho > 0.001:
                    w = float(_bge.render.getWindowWidth() or 1280.0)
                    h = float(_bge.render.getWindowHeight() or 720.0)
                    half = ortho / 2.0
                    half_v = half * h / w if w > 0 else half * 9.0/16.0
                    # Draw boundary box at y=0
                    cx, cy, cz = cam.worldPosition
                    # Boundary in XZ plane at y=0
                    # Use camera axes for generic
                    try:
                        x_axis = cam.getAxisVect((1,0,0))
                        y_axis = cam.getAxisVect((0,1,0))
                    except Exception:
                        x_axis = (1,0,0)
                        y_axis = (0,0,1)
                    # For Camera_UI at (0,-10,0) rot 90X, x_axis=(1,0,0), y_axis=(0,0,1)
                    # Boundary corners at y=0 plane
                    # We approximate with world X/Z
                    bx_min = -half
                    bx_max = half
                    bz_min = -half_v
                    bz_max = half_v
                    # Draw rectangle at y=0
                    p1 = (bx_min, 0.0, bz_min)
                    p2 = (bx_max, 0.0, bz_min)
                    p3 = (bx_max, 0.0, bz_max)
                    p4 = (bx_min, 0.0, bz_max)
                    _bge.render.drawLine(p1, p2, (0,0,1))
                    _bge.render.drawLine(p2, p3, (0,0,1))
                    _bge.render.drawLine(p3, p4, (0,0,1))
                    _bge.render.drawLine(p4, p1, (0,0,1))
            except Exception:
                pass
        except Exception as e:
            # Don't break main logic for debug failure
            print(f"[debug_ray] draw failed: {e}")
    except Exception:
        pass


def _object_under_cursor():
    """Return the name of the object under the mouse cursor.

    Generic implementation that works for any mesh anywhere in the world,
    both orthographic (Camera_UI) and perspective (Camera_3D) cameras.

    Fixes:
    - Old code cast only 5 units in front of the camera (py+5), so buttons
      placed beyond that (e.g. BG at y=0, or any mesh at y> -5) were missed.
      New code casts 100 units forward.
    - Old code returned the first hit even if it was invisible or a shadow
      (Speaker_Shadow, choice_N_shadow) — those are STATIC+BOX but invisible,
      so hover would trigger outside or fail to trigger on the button.
      New code loops and skips invisible / _shadow objects.
    - Ortho handling now correctly offsets the ray origin by the mouse's
      frustum position (px, pz) and uses the camera's forward axis
      (getAxisVect((0,0,-1))) instead of assuming +Y.
      FIXED: Now uses camera's X and Y axis vectors (getAxisVect((1,0,0)) and (0,1,0))
      for generic calculation, not just world X/Z — handles any camera rotation.
      This fixes ray being in wrong place when mesh modified/translated.
    - For perspective, uses getScreenVect but also loops to skip ignored hits.
    - Button can be any mesh anywhere: we no longer assume XZ planes at
      fixed Y layers; we raycast generically.
    - Added debug ray render per user request — draws ray when upvn_debug_ray enabled.
    """
    if not HAS_BGE:
        return None
    try:
        import bge as _bge
        sc = _bge.logic.getCurrentScene()
        cam = sc.active_camera
        mx, my = _bge.logic.mouse.position

        def _ignore(obj):
            if obj is None:
                return True
            try:
                if not getattr(obj, "visible", True):
                    return True
            except Exception:
                pass
            name = str(getattr(obj, "name", ""))
            if not name:
                return False
            # shadows are deleted at runtime but keep guard for old blends
            if name.endswith("_shadow"):
                return True
            # Ignore text objects — only button plane should be hittable to avoid outside trigger
            # Text has Middle alignment now, but its collision could still cause outside trigger if positioned offset
            # By ignoring text, ray passes through to hit button plane behind
            if name.endswith("_text") or "_text" in name:
                # Check if it's a choice text or generic text — ignore for ray, we want plane
                # But keep speaker/dialogue text ignored too? Those are not buttons, so ignore is fine
                # For choice text, we want to hit plane behind, so ignore text
                return True
            # also ignore the template Cube/Light if they somehow remain
            if name in ("Cube", "Light"):
                return True
            return False

        try:
            ortho = float(getattr(cam, "ortho_scale", 0.0) or 0.0)
        except Exception:
            ortho = 0.0
        is_ortho = ortho > 0.001

        try:
            fwd = cam.getAxisVect((0.0, 0.0, -1.0))
            import math as _math
            l = _math.sqrt(fwd[0]*fwd[0]+fwd[1]*fwd[1]+fwd[2]*fwd[2])
            if l > 1e-6:
                fwd = (fwd[0]/l, fwd[1]/l, fwd[2]/l)
            else:
                fwd = (0.0, 1.0, 0.0)
        except Exception:
            fwd = (0.0, 1.0, 0.0)

        # ortho: compute mouse world X,Z on camera plane — FIXED to use camera axis vectors
        # Previously used world X/Z directly, which failed when camera rotated or mesh translated
        # Now uses getAxisVect for X and Y to be generic for any camera rotation
        if is_ortho:
            try:
                w = float(_bge.render.getWindowWidth() or 1280.0)
                h = float(_bge.render.getWindowHeight() or 720.0)
            except Exception:
                w, h = 1280.0, 720.0
            nx = float(mx) - 0.5
            ny = 0.5 - float(my)
            # Generic: use camera's local X and Y axes for ray origin offset
            try:
                x_axis = cam.getAxisVect((1.0, 0.0, 0.0))
                y_axis = cam.getAxisVect((0.0, 1.0, 0.0))
                # Normalize axes (should already be unit, but ensure)
                import math as _math
                lx = _math.sqrt(x_axis[0]*x_axis[0]+x_axis[1]*x_axis[1]+x_axis[2]*x_axis[2])
                ly = _math.sqrt(y_axis[0]*y_axis[0]+y_axis[1]*y_axis[1]+y_axis[2]*y_axis[2])
                if lx > 1e-6:
                    x_axis = (x_axis[0]/lx, x_axis[1]/lx, x_axis[2]/lx)
                if ly > 1e-6:
                    y_axis = (y_axis[0]/ly, y_axis[1]/ly, y_axis[2]/ly)
            except Exception:
                # Fallback to world X/Z for Camera_UI at (0,-10,0) rot 90X
                x_axis = (1.0, 0.0, 0.0)
                y_axis = (0.0, 0.0, 1.0)
            # Ortho scale is width, height = width * h/w
            # Origin = cam.pos + x_axis * (nx*ortho) + y_axis * (ny*ortho*h/w)
            try:
                cam_pos = cam.worldPosition
                # cam.worldPosition is Vector, need to handle
                cx, cy, cz = float(cam_pos.x), float(cam_pos.y), float(cam_pos.z)
            except Exception:
                try:
                    cx, cy, cz = cam.worldPosition
                except Exception:
                    cx, cy, cz = (0.0, -10.0, 0.0)
            # Calculate offset using axis vectors
            off_x = nx * ortho
            off_y = ny * ortho * (h / w)
            origin = (cx + x_axis[0]*off_x + y_axis[0]*off_y,
                      cy + x_axis[1]*off_x + y_axis[1]*off_y,
                      cz + x_axis[2]*off_x + y_axis[2]*off_y)
            # far target 100 units forward
            target = (origin[0] + fwd[0]*100.0,
                      origin[1] + fwd[1]*100.0,
                      origin[2] + fwd[2]*100.0)
            cur_from = origin
            cur_to = target
            # loop to skip ignored (invisible/shadow)
            for _ in range(12):
                try:
                    hit, pt, _n = cam.rayCast(cur_to, cur_from, 100.0)
                except Exception:
                    hit = None
                    pt = None
                if hit is None:
                    # Debug ray for miss
                    _debug_draw_ray(cur_from, cur_to, hit_point=None, hit_name=None)
                    return None
                if _ignore(hit):
                    if pt is not None:
                        cur_from = (pt[0] + fwd[0]*0.05,
                                    pt[1] + fwd[1]*0.05,
                                    pt[2] + fwd[2]*0.05)
                    else:
                        cur_from = (cur_from[0] + fwd[0]*0.1,
                                    cur_from[1] + fwd[1]*0.1,
                                    cur_from[2] + fwd[2]*0.1)
                    continue
                # Debug ray for hit
                _debug_draw_ray(origin, cur_to, hit_point=pt, hit_name=getattr(hit, "name", None))
                return getattr(hit, "name", None)
            _debug_draw_ray(origin, cur_to, hit_point=None, hit_name=None)
            return None
        else:
            # perspective — FIXED for outside trigger bug
            # Previously used getScreenVect only, which could be inaccurate for perspective
            # Now tries getScreenRay first (more accurate, returns start/end), fallback to getScreenVect
            # Also uses axis vectors and proper origin
            vect = None
            origin = None
            target = None
            use_screen_ray = False
            try:
                # Try getScreenRay which is more accurate for perspective in UPBGE
                if hasattr(cam, "getScreenRay"):
                    # getScreenRay returns (origin, target, direction) or (from, to)?
                    # In UPBGE, getScreenRay(x,y,dist) returns tuple of 2 or 3 vectors
                    ray = cam.getScreenRay(mx, my, 100.0)
                    if ray is not None and len(ray) >= 2:
                        # ray[0] is origin, ray[1] is target
                        try:
                            o = ray[0]
                            t = ray[1]
                            origin = (float(o[0]), float(o[1]), float(o[2])) if hasattr(o, "__len__") else (float(o.x), float(o.y), float(o.z))
                            target = (float(t[0]), float(t[1]), float(t[2])) if hasattr(t, "__len__") else (float(t.x), float(t.y), float(t.z))
                            # Calculate vect from origin to target
                            import math as _math
                            vx = target[0]-origin[0]
                            vy = target[1]-origin[1]
                            vz = target[2]-origin[2]
                            l = _math.sqrt(vx*vx+vy*vy+vz*vz)
                            if l > 1e-6:
                                vect = (vx/l, vy/l, vz/l)
                            else:
                                vect = fwd
                            use_screen_ray = True
                        except Exception:
                            pass
            except Exception:
                pass
            
            if not use_screen_ray:
                try:
                    vect = cam.getScreenVect(mx, my)
                    import math as _math
                    l = _math.sqrt(vect[0]*vect[0]+vect[1]*vect[1]+vect[2]*vect[2])
                    if l > 1e-6:
                        vect = (vect[0]/l, vect[1]/l, vect[2]/l)
                except Exception:
                    vect = fwd
                try:
                    cam_pos = cam.worldPosition
                    origin = (float(cam_pos.x), float(cam_pos.y), float(cam_pos.z))
                except Exception:
                    try:
                        origin = cam.worldPosition
                    except Exception:
                        origin = (0.0, -10.0, 0.0)
                target = (origin[0]+vect[0]*100.0,
                          origin[1]+vect[1]*100.0,
                          origin[2]+vect[2]*100.0)
            
            cur_from = origin
            cur_to = target
            for _ in range(12):
                try:
                    hit, pt, _n = cam.rayCast(cur_to, cur_from, 100.0)
                except Exception:
                    hit = None
                    pt = None
                if hit is None:
                    _debug_draw_ray(cur_from, cur_to, hit_point=None, hit_name=None)
                    return None
                if _ignore(hit):
                    if pt is not None:
                        cur_from = (pt[0]+vect[0]*0.05,
                                    pt[1]+vect[1]*0.05,
                                    pt[2]+vect[2]*0.05)
                    else:
                        cur_from = (cur_from[0]+vect[0]*0.1,
                                    cur_from[1]+vect[1]*0.1,
                                    cur_from[2]+vect[2]*0.1)
                    continue
                _debug_draw_ray(origin, cur_to, hit_point=pt, hit_name=getattr(hit, "name", None))
                return getattr(hit, "name", None)
            _debug_draw_ray(origin, cur_to, hit_point=None, hit_name=None)
            return None
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
        # generic button support: any mesh anywhere can be a choice button if
        # it carries a choice_index property. Extend the hotspot map with such
        # objects each time the menu changes (or every tick for simplicity).
        try:
            sc = _bge.logic.getCurrentScene()
            from engine.ui.pointer import Hotspot
            for ob in sc.objects:
                try:
                    idx = None
                    # explicit property mapping
                    if "choice_index" in ob:
                        idx = int(ob["choice_index"])
                    elif "upvn_choice" in ob:
                        idx = int(ob["upvn_choice"])
                    elif "choice" in ob:
                        # allow generic 'choice' property
                        try:
                            idx = int(ob["choice"])
                        except Exception:
                            idx = None
                    if idx is not None and 0 <= idx < len(choices):
                        # add/override hotspot for this mesh name
                        tr.hotspots.add(Hotspot(name=ob.name, action="choice", choice_index=idx))
                except Exception:
                    continue
        except Exception:
            pass

        name = normalize_hit_name(_object_under_cursor())
        # generic hover: any hotspot (including any mesh anywhere) is hoverable,
        # not just choice_ prefix. This supports the user directive that button
        # can be any mesh anywhere in the world.
        hover_candidate = None
        if name:
            try:
                # if it's a known hotspot, it's hoverable
                if tr.hotspots.resolve(name) is not None:
                    hover_candidate = name
                elif str(name).startswith("choice_"):
                    hover_candidate = name
            except Exception:
                if str(name).startswith("choice_"):
                    hover_candidate = name
        logic._upvn_hover = hover_candidate
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


def zoom_ortho_scale(base, zoom_from, zoom_to, duration, easing, t_raw):
    """M26c pure zoom math (unit-tested without bge): eased zoom factor →
    ortho scale. Ortho = base / zoom, clamped to ≥1.0; zoom factor clamped
    to ≥0.05 so a 0/1.0 zoom can't divide by zero. Returns the scale only;
    the caller decides tween completion from the same t_raw.
    `easing` is an engine.atl name resolved lazily (e.g. "ease", "linear").
    """
    zoom_from = float(zoom_from)
    zoom_to = float(zoom_to)
    t = min(1.0, max(0.0, float(t_raw)))
    try:
        from engine.atl.easing import get_easing
        ease = get_easing(easing or "ease")
    except Exception:
        ease = lambda x: x
    zoom = zoom_from + (zoom_to - zoom_from) * ease(t)
    return max(1.0, float(base) / max(0.05, zoom))


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
        t_raw = 1.0
        if t0 is not None and dur > 0:
            t_raw = (_t.time() - t0) / dur
        if t_raw >= 1.0:
            # tween finished — drop the transient keys so this stays cheap
            for k in ("_zoom_from", "_zoom_to", "_zoom_dur",
                      "_zoom_ease", "_zoom_t0"):
                cam_state.pop(k, None)
        cam = logic.getCurrentScene().active_camera
        if cam is not None and getattr(cam, "ortho_scale", None) is not None:
            # M26c: the contract constant is the single source of truth for
            # the un-zoomed base. Two live-measured traps with "capture the
            # current ortho" schemes: the interpreter sets zoom before this
            # function's first tick (inflated base ×1.2 → zoom-in ended
            # unchanged), and calm ticks BETWEEN tweens carry the previous
            # zoom's ortho (compounding base 12.5 → authored 1.5× played as
            # 1.8×). Setup Scene enforces CAMERA_UI_ORTHO_SCALE;
            # upvn_camera_custom cameras accept zooms relative to it.
            cam.ortho_scale = zoom_ortho_scale(
                CAMERA_UI_ORTHO_SCALE,
                cam_state.get("_zoom_from", cam_state.get("zoom", zoom_to)),
                zoom_to,
                dur,
                cam_state.get("_zoom_ease"),
                t_raw,
            )
    except Exception as e:
        try:
            if not logic._upvn_cam_err:
                logic._upvn_cam_err = True
                print(f"[UPVN] camera zoom apply failed: {e}")
        except Exception:
            pass


def _bind_camera():
    """Force scene.active_camera = Camera_UI. M26d: this ran ONCE with a
    sticky guard, but a live-verified run proved that is not enough — a
    merged 3D stage brought its own Camera_3D and the viewport rendered from
    it (perspective, no UI planes, pointer rays hit stage geometry) even
    though the boot bind had printed. Re-assert every tick; the check is one
    attribute compare."""
    if not HAS_BGE:
        return
    try:
        import bge as _bge
        logic = _bge.logic
        sc = logic.getCurrentScene()
        cam = sc.active_camera
        want = sc.objects.get("Camera_UI")
        if want is None:
            return
        # force-set every tick: this build's viewport camera selection is not
        # fully explained by active_camera read-back, and one extra camera in
        # the scene (dormant template Camera_3D) coincided with perspective
        # rendering. The write is a no-op when already correct.
        sc.active_camera = want
        if cam is not None and getattr(cam, "name", "") == "Camera_UI":
            logic._upvn_cam_bound = True
            return
        if not getattr(logic, "_upvn_cam_bound", False):
            logic._upvn_cam_bound = True
            print("[UPVN] active_camera bound to Camera_UI")
        else:
            print("[UPVN] active_camera re-bound to Camera_UI "
                  f"(was {getattr(cam, 'name', '?')})")
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
    # M29 parity: in the standalone player bge.logic.expandPath('//…') and
    # every relative asset/gui lookup resolve against the process cwd, which
    # is wherever the player was launched from. Anchor the process to the
    # .blend directory once so relative paths behave like the editor's.
    try:
        import bpy as _bpy_cd
        bp = getattr(getattr(_bpy_cd, "data", None), "filepath", "") or ""
        if bp:
            os.chdir(os.path.dirname(os.path.abspath(bp)))
    except Exception:
        pass
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
        # M26d: the parse tier is a project property, because a converted
        # Ren'Py project is real .rpy source ("full" tier: init offset, extend,
        # screen …) while the declarative samples stay on "safe".  Before this,
        # every tool-converted game failed to load and the player showed the
        # "script not found" screen even though the .rpy files were there.
        parse_mode = _prop(owner, "parse_mode") or "safe"

        def _load_with(mode):
            # M29: converted/drop-in projects (full tier) run real Ren'Py
            # python blocks that the safe sandbox cannot execute; compat mode
            # collects those failures instead of aborting the whole load.
            comp = _prop(owner, "compat")
            if comp in (None, ""):
                comp = (mode == "full")
            elif isinstance(comp, str):
                comp = comp.strip().lower() in ("1", "true", "yes")
            ctrl = VNController(script_path=path, mode=mode, compat=bool(comp))
            ctrl.load()
            logic._upvn_ctrl = ctrl
            _unregister_overlay()
            _hide_idle_sprites(ctrl)
            _hide_idle_ui()
            _apply_gui_par()
            print(f"[UPVN] Loaded script {path} (mode={mode}, from "
                  f"{'VNController.script_path' if owner is not None else 'candidate'})")

        if path:
            try:
                _load_with(parse_mode)
            except Exception as e:
                # One automatic retry at the full tier: it is a superset, so a
                # blend whose property was never wired still plays instead of
                # showing a diagnostic screen.
                if parse_mode != "full":
                    print(f"[UPVN] load with mode={parse_mode} failed ({e}); "
                          f"retrying with mode=full")
                    try:
                        _load_with("full")
                    except Exception as e2:
                        print(f"[UPVN] failed to load {path}: {e2}")
                        logic._last_upvn_error = f"{path}: {e2}"
                else:
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
            _hide_idle_ui()
            _apply_gui_par()

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
            _ortho = None
            try:
                _cam = _bge.logic.getCurrentScene().active_camera
                _ortho = (round(float(_cam.ortho_scale), 3)
                          if getattr(_cam, "ortho_scale", None) is not None
                          else None)
            except Exception:
                pass
            _payload = getattr(logic, "_upvn_last_payload", None) or {}
            _interp = getattr(ctrl, "interp", None)
            _hb_data = {
                "label": _st.current_label,
                "idx": _st.instruction_index,
                "event": _evt.get("type"),
                "choices": len(_evt.get("choices") or []),
                "modal": (None if _sm is None or _sm.active_modal is None
                          else _sm.active_modal.name),
                "ortho": _ortho,
                "speaker": _payload.get("speaker"),
                "dialogue": _payload.get("dialogue"),
                "speaker_color": (list(_payload.get("speaker_color"))
                                  if _payload.get("speaker_color") else None),
                "dialogue_visible": bool(_payload.get("dialogue_visible")),
                "history": len(getattr(_st, "history", []) or []),
                "history_open": bool(_sm and _sm.is_overlay_visible("history"))
                if _sm is not None else False,
                "history_scroll": int(getattr(ctrl, "_history_scroll", 0) or 0),
                "rollback_depth": len(getattr(_interp, "rollback_stack", []) or [])
                if _interp is not None else 0,
                "rollforward_depth": len(getattr(ctrl, "_forward_stack", []) or []),
                "skipping": bool(getattr(_st, "skip", False)),
                "auto": bool(getattr(_st, "auto", False)),
                # M28: compat mode errors and payload errors for QA
                "init_errors": list(getattr(_interp, "init_errors", []) or [])[:5] if _interp else [],
                "python_errors": list(getattr(_interp, "python_errors", []) or [])[:5] if _interp else [],
                "payload_errors": list(_payload.get("errors", []) or [])[:5],
                "interp_warnings": list(_payload.get("interp_warnings", []) or [])[:5],
                "typewriter_done": bool(_payload.get("typewriter_done", True)),
                "ui_status": getattr(logic, "_upvn_last_ui_status", None),
            }
            try:
                _sc = logic.getCurrentScene()
                for _n, _k in (("Dialogue_Text", "font_body"),
                               ("Speaker_Text", "font_speaker"),
                               ("History_Text", "history_body"),
                               ("History_Box", "history_box"),
                               ("Rewind_Text", "rewind_body")):
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
                            _hb_data[_k + "_font"] = round(float(getattr(_d, "size", 1.0)), 4) if _d is not None else None
                            _hb_data[_k + "_wpos"] = [round(float(v), 3) for v in _bo.location]
                            # M26i: what the object is actually tinted with
                            # (colored speaker / dark shadows assertions).
                            try:
                                _hb_data[_k + "_color"] = [round(float(c), 3) for c in _bo.color]
                            except Exception:
                                pass
                            # dims==0 with a non-empty body = the curve produced
                            # no geometry (invisible text, no error anywhere)
                            _hb_data[_k + "_dim"] = [round(float(v), 3) for v in _bo.dimensions]
                            _hb_data[_k + "_hide"] = bool(getattr(_bo, "hide_viewport", False)) or bool(getattr(_bo, "hide_render", False))
                        elif _o is not None:
                            _hb_data[_k + "_scale"] = [round(float(v), 4) for v in _o.worldScale]
                        if _o is not None:
                            _hb_data[_k + "_vis"] = bool(getattr(_o, "visible", False))
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
