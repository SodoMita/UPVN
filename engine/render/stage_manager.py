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
        if t == "load_stage":
            self.load_stage(event["stage"])
        elif t == "show3d":
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
                    import time
                    cam["upvn_zoom_t0"] = time.time()
                    cam["upvn_zoom_from"] = getattr(cam, "ortho_scale", 15.0)
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

    def load_stage(self, stage_name: str):
        self.state.stage = stage_name
        if HAS_BGE:
            try:
                import bge.logic as logic
                # try multiple stage locations (project stages/ or blend template)
                for cand in [f"//stages/{stage_name}.blend", f"//blend/stages/{stage_name}.blend", f"//assets/stages/{stage_name}.blend"]:
                    path = logic.expandPath(cand)
                    import os
                    if os.path.exists(path):
                        logic.LibLoad(path, "Scene", load_actions=True)  # type: ignore
                        print(f"[StageManager] LibLoad stage {stage_name} from {path}")
                        break
                else:
                    # fallback: stage already in template collection VN_3DStage
                    print(f"[StageManager] stage {stage_name} assumed in VN_3DStage collection (template)")
            except Exception as e:
                print(f"[StageManager] load_stage failed {e}")

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
                        from .contract import CAMERA_UI_ORTHO_SCALE
                        target = cam["upvn_target_zoom"]
                        if hasattr(cam, "ortho_scale"):
                            cam.ortho_scale = CAMERA_UI_ORTHO_SCALE / max(0.05, float(target))
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
                if cam and hasattr(cam, "ortho_scale"):
                    from .contract import CAMERA_UI_ORTHO_SCALE
                    cam.ortho_scale = CAMERA_UI_ORTHO_SCALE / max(0.05, float(cur))
            except: pass

    def spawn(self, asset: str, marker: str | None):
        if HAS_BGE:
            try:
                import bge.logic as logic
                scene = logic.getCurrentScene()
                marker_obj = scene.objects.get(marker) if marker else None
                # Special: object already in scene (e.g. Car_Rig directly in VN_3DStage)
                # In that case just move it to marker instead of addObject
                existing = scene.objects.get(asset)
                if existing is not None and marker_obj is not None:
                    try:
                        existing.worldPosition = marker_obj.worldPosition.copy()
                        # also copy orientation if needed? keep rig upright
                    except Exception:
                        pass
                    # ensure visibility
                    try:
                        existing.visible = True
                    except Exception:
                        pass
                    self.state.stage_objects[asset] = {"marker": marker, "anim": "idle", "bge_obj": existing.name}
                    print(f"[StageManager] spawn (move existing) {asset} at {marker} -> {existing.name}")
                    return
                # asset could be an object name in stage collection, e.g. Char_Eileen_placeholder or eileen
                # try to find template object
                template = None
                for cand in [asset, f"Char_{asset}_placeholder", f"Char_{asset.capitalize()}_placeholder", asset.capitalize()]:
                    if cand in scene.objectsInactive:
                        template = cand
                        break
                    if cand in scene.objects:
                        template = cand
                        break
                if template and marker_obj:
                    obj = scene.addObject(template, marker_obj, 0)
                    # store for later anim
                    self.state.stage_objects[asset] = {"marker": marker, "anim": "idle", "bge_obj": obj.name}
                    print(f"[StageManager] spawn {asset} at {marker} -> {obj.name}")
                elif template:
                    # spawn at origin if no marker
                    obj = scene.addObject(template, scene.objects.get("Floor_classroom") or marker_obj, 0)
                    print(f"[StageManager] spawn {asset} (no marker) -> {obj.name}")
                else:
                    # fallback: asset itself might be a child like Wheel_FL, try direct
                    print(f"[StageManager] spawn template not found {asset}@{marker}, candidates checked")
            except Exception as e:
                print(f"[StageManager] spawn failed {asset}@{marker}: {e}")
        else:
            # headless already handled via VNState.stage_objects in interpreter
            pass

    def play_anim(self, target: str, anim: str):
        if HAS_BGE:
            try:
                import bge.logic as logic
                scene = logic.getCurrentScene()
                info = self.state.stage_objects.get(target)
                # resolve object — prefer stage_objects bge_obj, fallback to direct scene object (e.g. Car_Rig already visible)
                obj = None
                if info and "bge_obj" in info:
                    obj = scene.objects.get(info["bge_obj"])
                if obj is None:
                    obj = scene.objects.get(target)
                if obj:
                    # choose loop for idle and car actions
                    loop_anims = {"idle", "Car_Drive", "Car_WheelSpin"}
                    mode = logic.KX_ACTION_MODE_LOOP if anim in loop_anims else logic.KX_ACTION_MODE_PLAY
                    try:
                        obj.playAction(anim, 0, 60, 0, 0, 5, mode)
                    except Exception as e:
                        print(f"[StageManager] playAction {target} {anim} failed {e}, trying fallback range")
                        # try 0-60 fallback regardless
                        try:
                            obj.playAction(anim, 0, 60, 0, 0, 5, mode)
                        except Exception:
                            pass
                    if info is not None:
                        info["anim"] = anim
                    else:
                        # track directly-spawned car
                        self.state.stage_objects[target] = {"marker": None, "anim": anim, "bge_obj": obj.name}
                    print(f"[StageManager] play_anim {target} {anim} mode={'LOOP' if mode==logic.KX_ACTION_MODE_LOOP else 'PLAY'} -> {obj.name}")
                    # car special: when driving rig, also spin wheels
                    if target == "Car_Rig" and anim == "Car_Drive":
                        for wname in ("Wheel_FL","Wheel_FR","Wheel_RL","Wheel_RR"):
                            wobj = scene.objects.get(wname)
                            # wheels may be children of Car_Rig with instance suffix after addObject, try to find by prefix
                            if wobj is None:
                                # find any object starting with wheel name
                                for o in scene.objects:
                                    if o.name.startswith(wname):
                                        wobj = o
                                        break
                            if wobj is not None:
                                try:
                                    wobj.playAction("Car_WheelSpin", 0, 60, 0, 0, 5, logic.KX_ACTION_MODE_LOOP)
                                    print(f"[StageManager] auto wheel {wname} spin")
                                except Exception as e:
                                    print(f"[StageManager] wheel spin {wname} failed {e}")
                else:
                    print(f"[StageManager] play_anim object not found {target} -> {info}")
            except Exception as e:
                print(f"[StageManager] play_anim failed {target} {anim}: {e}")
        else:
            if target in self.state.stage_objects:
                self.state.stage_objects[target]["anim"] = anim

    def camera_preset(self, name: str):
        if HAS_BGE:
            try:
                import bge.logic as logic
                scene = logic.getCurrentScene()
                cam = scene.objects.get("Camera_3D") or scene.active_camera
                if cam is not None and getattr(cam, "name", "") == "Camera_UI":
                    print("[StageManager] camera_preset skipped — would move Camera_UI")
                    return
                preset = scene.objects.get(name) or scene.objects.get(f"preset_{name}") or scene.objects.get(f"Preset_{name}")
                if cam and preset:
                    # store lerp target for smooth transition (1 sec)
                    cam["upvn_cam_target"] = preset.name
                    cam["upvn_cam_t0"] = __import__("time").time()
                    # immediate for now; interpolator could be in frontend
                    cam.worldPosition = preset.worldPosition.copy()
                    cam.worldOrientation = preset.worldOrientation.copy()
                    print(f"[StageManager] camera_preset {name} -> {preset.name}")
            except Exception as e:
                print(f"[StageManager] camera_preset failed {name}: {e}")
        # state already set by interpreter
