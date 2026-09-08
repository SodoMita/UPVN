"""
UPVN — Scene Manager (UPBGE + headless)

Handles background planes / 3D stage loading.
Headless: state already set by interpreter; here we record last transition for renderer.
UPBGE: swaps bge.texture on BG_Plane, handles fade/dissolve via shader/alpha tween.

In UPBGE:
- Backgrounds are textured planes parented to Orthographic Camera (Layer 0)
- Transitions are shader-based or alpha tween over N frames (fade/dissolve)
- 3D stages load .blend collections via bge.logic.LibLoad

This module is the thin adapter between interpreter events and bge API.
"""
from __future__ import annotations
try:
    import bge  # type: ignore
    HAS_BGE = True
except ImportError:
    HAS_BGE = False

from ..core.vn_state import VNState
from .contract import BG_PLANE, BG_MATERIAL, ASSET_BACKGROUNDS
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
            self._swap_bge_texture(asset, transition)

    def _swap_bge_texture(self, asset: str, transition: str | None):
        if not HAS_BGE:
            return
        try:
            scene = bge.logic.getCurrentScene()  # type: ignore
            plane = scene.objects.get(BG_PLANE)
            if not plane:
                return
            # Use bge.texture to swap image
            import bge.texture as vt
            mat_id = vt.materialID(plane, BG_MATERIAL)
            if mat_id < 0:
                mat_id = 0  # first material slot fallback
            tex_path = bge.logic.expandPath(f"//{ASSET_BACKGROUNDS}/{asset}.png")
            # fallback to jpg
            import os
            if not os.path.exists(tex_path):
                for ext in (".jpg", ".png", ".webp"):
                    alt = bge.logic.expandPath(f"//{ASSET_BACKGROUNDS}/{asset}{ext}")
                    if os.path.exists(alt):
                        tex_path = alt
                        break
            if os.path.exists(tex_path):
                img = vt.ImageFFmpeg(tex_path)
                img.scale = False
                tex = vt.Texture(plane, mat_id)
                tex.source = img
                plane["upvn_tex"] = tex
                if transition in ("fade", "dissolve"):
                    plane["upvn_transition"] = transition
                    plane["upvn_transition_t0"] = time.time()
        except Exception as e:
            # headless or missing assets — not fatal
            print(f"[SceneManager] bge texture swap failed for {asset}: {e}")

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
        # ease out
        return t

    def _load_stage_bge(self, stage_name: str):
        if not HAS_BGE:
            return
        try:
            import bge.logic as logic
            path = logic.expandPath(f"//stages/{stage_name}.blend")
            # LibLoad merges collections
            logic.LibLoad(path, "Scene", load_actions=True)  # type: ignore
            print(f"[SceneManager] Loaded stage {stage_name} from {path}")
        except Exception as e:
            print(f"[SceneManager] LibLoad failed for {stage_name}: {e}")

    # headless helper for screenshot verification
    def current_background(self) -> str | None:
        return self.state.scene.background
