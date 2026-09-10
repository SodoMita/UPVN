"""
UPVN — Scene Manager (UPBGE + headless)

Handles background planes / 3D stage loading.
Headless: state already set by interpreter; here we record last transition for renderer.
UPBGE: tints BG_Plane via object colour (emission white material) — NO image textures.
       This avoids bge.texture / Vulkan vs GL issues (llvmpipe vs lavapipe) and works
       on pure software GL without image decoding.

Transitions are simple alpha tweens over N frames (fade/dissolve).

In UPBGE:
- Backgrounds are colour planes parented to Orthographic Camera (Layer 0)
- Transitions are alpha tween
- 3D stages load .blend collections via bge.logic.LibLoad (optional)
"""
from __future__ import annotations
try:
    import bge  # type: ignore
    HAS_BGE = True
except ImportError:
    HAS_BGE = False

from ..core.vn_state import VNState
from .contract import BG_PLANE, BG_MATERIAL, bg_color_for
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
            # standalone with — apply to last background
            self._transition_name = event.get("transition")
            self._transition_start = time.time()
            self._transition_duration = TRANSITIONS.get(self._transition_name, 0.5)
        elif t == "load_stage" and HAS_BGE:
            self._load_stage_bge(event["stage"])

    def set_background(self, asset: str, transition: str | None = None):
        self._prev_bg = self.state.scene.background
        # state already updated by interpreter; record transition for visual
        if transition:
            self._transition_name = transition
            self._transition_start = time.time()
            self._transition_duration = TRANSITIONS.get(transition, 0.5)
        else:
            self._transition_name = None
        if HAS_BGE:
            self._apply_bg_color(asset, transition)

    def _apply_bg_color(self, asset: str, transition: str | None):
        if not HAS_BGE:
            return
        try:
            scene = bge.logic.getCurrentScene()  # type: ignore
            plane = scene.objects.get(BG_PLANE)
            if not plane:
                return
            col = bg_color_for(asset)
            # object colour tints the white emission material (contract)
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
            # handle fade/dissolve as alpha tween start
            if transition in ("fade", "dissolve"):
                try:
                    plane["upvn_transition"] = transition
                    plane["upvn_transition_t0"] = time.time()
                    # start from transparent if fade-in
                    if transition == "fade":
                        plane.color = (col[0], col[1], col[2], 0.0)
                        # store target for update
                        plane["upvn_fade_target"] = col
                except Exception:
                    pass
            else:
                # clear old transition markers
                for k in ("upvn_transition", "upvn_transition_t0", "upvn_fade_target"):
                    try:
                        if k in plane:
                            del plane[k]
                    except Exception:
                        pass
            # keep material emission white so object colour is faithful (in case
            # template was built with old coloured material)
            try:
                mat = plane.meshes[0].materials[0] if plane.meshes else None
                if mat is None:
                    # fallback via bpy? not needed at runtime
                    pass
            except Exception:
                pass
        except Exception as e:
            print(f"[SceneManager] bg colour apply failed for {asset}: {e}")

    # backwards compat alias (old name used in contract docstring)
    def _swap_bge_texture(self, asset: str, transition: str | None):
        return self._apply_bg_color(asset, transition)

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
                # stage is optional — no crash if missing (hybrid demo)
                return
            logic.LibLoad(path, "Scene", load_actions=True)  # type: ignore
            print(f"[SceneManager] Loaded stage {stage_name} from {path}")
        except Exception as e:
            print(f"[SceneManager] LibLoad failed for {stage_name}: {e}")

    def current_background(self) -> str | None:
        return self.state.scene.background
