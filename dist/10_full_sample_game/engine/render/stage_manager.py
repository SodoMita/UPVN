"""
Stage Manager — 3D hybrid (Tier5 superpower)

VN dialogue driving 3D cameras, armature animations, markers.

Per user preference: UI is created in 3D scene, no DSL for it — LLM can
build that using Python (so this manager exposes python API, not script commands).

API:
    stage_manager.load("classroom_3d")
    stage_manager.spawn("eileen", marker="marker_eileen")
    stage_manager.play_anim("eileen", "wave")
    stage_manager.camera("closeup_eileen")

In script files, minimal stubs are parsed:
    load_stage classroom_3d
    show3d eileen at marker_eileen
    anim eileen wave
    camera preset closeup_eileen
"""
from __future__ import annotations
try:
    import bge
    HAS_BGE = True
except ImportError:
    HAS_BGE = False

from ..core.vn_state import VNState

class StageManager:
    def __init__(self, state: VNState):
        self.state = state

    def apply_event(self, event: dict):
        t = event.get("type")
        if t == "show3d":
            self.spawn(event["asset"], event.get("marker"))
        elif t == "anim":
            self.play_anim(event["target"], event["animation"])
        elif t == "camera_preset":
            self.camera_preset(event["name"])
        elif t == "camera_zoom":
            self.camera_zoom(event["zoom"], event.get("duration",1.0), event.get("easing","ease"))

    def camera_zoom(self, zoom: float, duration: float = 1.0, easing: str = "ease"):
        # state already updated by interpreter; for BGE lerp camera
        if HAS_BGE:
            try:
                import bge
                scene = bge.logic.getCurrentScene()
                cam = scene.active_camera
                if cam:
                    # store target in BGE object properties for update lerp
                    cam["upvn_target_zoom"] = zoom
                    cam["upvn_zoom_ease"] = easing
                    # we handle actual scale via lens or ortho_scale; for now use cam.lens interpolation
                    # Simplified: cam.ortho_scale lerped
                    if not "upvn_zoom_t0" in cam:
                        import time
                        cam["upvn_zoom_t0"] = time.time()
                        cam["upvn_zoom_from"] = getattr(cam, "ortho_scale", 10.0)
                        cam["upvn_zoom_dur"] = duration
            except Exception as e:
                print(f"[StageManager] camera_zoom failed {e}")

    def get_current_zoom(self, now: float | None = None) -> float:
        import time as _t
        if now is None:
            now = _t.time()
        cam = self.state.camera
        if "_zoom_t0" not in cam:
            return cam.get("zoom", 1.0 if "preset" not in cam else 1.0)
        t0 = cam["_zoom_t0"]
        dur = cam.get("_zoom_dur", 1.0)
        if dur <= 0:
            return cam.get("_zoom_to", cam.get("zoom",1.0))
        t_raw = (now - t0)/dur
        t_raw = max(0.0, min(1.0, t_raw))
        if t_raw >= 1.0:
            return cam.get("_zoom_to", cam.get("zoom",1.0))
        try:
            from ..atl.easing import get_easing
            ease = get_easing(cam.get("_zoom_ease","ease"))
        except:
            ease = lambda x: x
        t = ease(t_raw)
        f = cam.get("_zoom_from", 1.0)
        to = cam.get("_zoom_to", f)
        return f + (to - f)*t

    def is_zoom_done(self, now: float | None = None) -> bool:
        import time as _t
        if now is None:
            now = _t.time()
        cam = self.state.camera
        if "_zoom_t0" not in cam:
            return True
        return (now - cam["_zoom_t0"]) >= cam.get("_zoom_dur",1.0)

    def update(self, dt: float):
        if not HAS_BGE:
            return
        # BGE per-frame zoom lerp
        import time as _t
        now = _t.time()
        cam_st = self.state.camera
        if "_zoom_t0" in cam_st:
            dur = cam_st.get("_zoom_dur",1.0)
            t_raw = (now - cam_st["_zoom_t0"])/dur if dur>0 else 1.0
            t_raw = max(0.0, min(1.0, t_raw))
            if t_raw >= 1.0:
                # done — snap and clear
                try:
                    import bge
                    scene = bge.logic.getCurrentScene()
                    cam = scene.active_camera
                    if cam and "upvn_target_zoom" in cam:
                        # apply final zoom: ortho_scale = 10/zoom? For perspective, lens
                        target = cam["upvn_target_zoom"]
                        if hasattr(cam, "ortho_scale"):
                            cam.ortho_scale = 10.0 / target
                        elif hasattr(cam, "lens"):
                            cam.lens = 35.0 * target
                except: pass
                return
            # interpolate
            try:
                from ..atl.easing import get_easing
                ease = get_easing(cam_st.get("_zoom_ease","ease"))
            except:
                ease = lambda x: x
            t = ease(t_raw)
            f = cam_st.get("_zoom_from",1.0)
            to = cam_st.get("_zoom_to",1.0)
            cur = f + (to - f)*t
            try:
                import bge
                scene = bge.logic.getCurrentScene()
                cam = scene.active_camera
                if cam and hasattr(cam,"ortho_scale"):
                    base = 10.0
                    cam.ortho_scale = base / cur
            except: pass

    def spawn(self, asset: str, marker: str | None):
        if HAS_BGE:
            # scene.addObject(asset, marker_object)
            pass

    def play_anim(self, target: str, anim: str):
        if HAS_BGE:
            # obj.playAction(anim, 0, 60)
            pass

    def camera_preset(self, name: str):
        if HAS_BGE:
            # lerp camera to preset empty
            pass
