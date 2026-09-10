"""
UPVN — Scene Manager (UPBGE + headless)

Handles background planes / 3D stage loading.
Headless: state already set by interpreter; here we record last transition for renderer.
UPBGE: tries bge.texture (real PNG) first; falls back to palette colour (object.color)
       when no file or texture unavailable — textures essential but palette keeps
       software GL (llvmpipe/lavapipe) usable without assets.

Transitions are simple alpha tweens over N frames (fade/dissolve).
"""
from __future__ import annotations
try:
    import bge  # type: ignore
    HAS_BGE = True
except ImportError:
    HAS_BGE = False

from ..core.vn_state import VNState
from .contract import BG_PLANE, BG_MATERIAL, ASSET_BACKGROUNDS, bg_color_for
import time

BACKGROUND_LAYER = 0
TRANSITIONS = {"fade": 0.6, "dissolve": 0.45, None: 0.0}

class SceneManager:
    def __init__(self, state: VNState):
        self.state = state
        self._bg_object = None
        self._prev_bg: str | None = None
        self._transition_start: float | None = None
        self._transition_duration: float = 0.0
        self._transition_name: str | None = None

    def apply_event(self, event: dict):
        t = event.get("type")
        if t == "scene":
            self.set_background(event["asset"], event.get("transition"))
        elif t == "with":
            self._transition_name = event.get("transition")
            self._transition_start = time.time()
            self._transition_duration = TRANSITIONS.get(self._transition_name, 0.5)
        elif t == "load_stage" and HAS_BGE:
            self._load_stage_bge(event["stage"])

    def set_background(self, asset: str, transition: str | None = None):
        self._prev_bg = self.state.scene.background
        if transition:
            self._transition_name = transition
            self._transition_start = time.time()
            self._transition_duration = TRANSITIONS.get(transition, 0.5)
        else:
            self._transition_name = None
        if HAS_BGE:
            self._apply_bg(asset, transition)

    def _apply_bg(self, asset: str, transition: str | None):
        if not HAS_BGE:
            return
        # try texture first
        if self._try_texture(asset, transition):
            return
        # fallback to palette colour
        self._apply_bg_color(asset, transition)

    def _try_texture(self, asset: str, transition: str | None) -> bool:
        try:
            import bge.texture as vt
            import os
            scene = bge.logic.getCurrentScene()  # type: ignore
            plane = scene.objects.get(BG_PLANE)
            if not plane:
                return False
            stems = [asset, asset.replace(" ", "_"), asset.replace(" ", "/")]
            tex_path = None
            for stem in stems:
                for ext in (".png", ".jpg", ".webp"):
                    for prefix in (f"//{ASSET_BACKGROUNDS}/", f"//game/{ASSET_BACKGROUNDS}/", f"//assets/backgrounds/"):
                        alt = bge.logic.expandPath(f"{prefix}{stem}{ext}")
                        if os.path.exists(alt):
                            tex_path = alt
                            break
                    if tex_path:
                        break
                if tex_path:
                    break
            if not tex_path or not os.path.exists(tex_path):
                return False
            try:
                mat_id = vt.materialID(plane, BG_MATERIAL)
            except Exception:
                mat_id = -1
            if mat_id < 0:
                mat_id = 0
            try:
                img = vt.ImageFFmpeg(tex_path)
                img.scale = False
                tex = vt.Texture(plane, mat_id)
                tex.source = img
                try:
                    tex.refresh(True)
                except Exception:
                    try:
                        tex.refresh(False)
                    except Exception:
                        pass
                plane["upvn_tex"] = tex
                plane["upvn_bg"] = asset
                plane.visible = True
                # ensure object colour is white so texture shows true
                try:
                    plane.color = (1,1,1,1)
                except Exception:
                    pass
                if transition in ("fade", "dissolve"):
                    plane["upvn_transition"] = transition
                    plane["upvn_transition_t0"] = time.time()
                return True
            except Exception as e:
                print(f"[SceneManager] texture bind failed for {asset} ({tex_path}): {e}")
                return False
        except Exception as e:
            # print once
            try:
                import bge
                if not getattr(bge.logic, "_upvn_bg_tex_err", False):
                    bge.logic._upvn_bg_tex_err = True
                    print(f"[SceneManager] texture path error: {e}")
            except Exception:
                pass
            return False

    def _apply_bg_color(self, asset: str, transition: str | None):
        try:
            import bge
            scene = bge.logic.getCurrentScene()  # type: ignore
            plane = scene.objects.get(BG_PLANE)
            if not plane:
                return
            col = bg_color_for(asset)
            try:
                plane.color = col
            except Exception:
                pass
            plane.visible = True
            try:
                plane["upvn_bg"] = asset
                plane["upvn_bg_color"] = col
            except Exception:
                pass
            if transition in ("fade", "dissolve"):
                try:
                    plane["upvn_transition"] = transition
                    plane["upvn_transition_t0"] = time.time()
                    if transition == "fade":
                        plane.color = (col[0], col[1], col[2], 0.0)
                        plane["upvn_fade_target"] = col
                except Exception:
                    pass
        except Exception as e:
            print(f"[SceneManager] bg colour apply failed for {asset}: {e}")

    def _swap_bge_texture(self, asset: str, transition: str | None):
        return self._apply_bg(asset, transition)

    def is_transition_done(self) -> bool:
        if not self._transition_start:
            return True
        return (time.time() - self._transition_start) >= self._transition_duration

    def transition_alpha(self) -> float:
        if not self._transition_start or not self._transition_name:
            return 1.0
        elapsed = time.time() - self._transition_start
        dur = self._transition_duration or 0.5
        t = min(1.0, max(0.0, elapsed / dur))
        return t

    def _load_stage_bge(self, stage_name: str):
        if not HAS_BGE:
            return
        try:
            import bge.logic as logic
            import os
            path = logic.expandPath(f"//stages/{stage_name}.blend")
            if not os.path.exists(path):
                return
            logic.LibLoad(path, "Scene", load_actions=True)  # type: ignore
            print(f"[SceneManager] Loaded stage {stage_name} from {path}")
        except Exception as e:
            print(f"[SceneManager] LibLoad failed for {stage_name}: {e}")

    def current_background(self) -> str | None:
        return self.state.scene.background
