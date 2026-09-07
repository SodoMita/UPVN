"""
Audio Manager — wraps UPBGE `aud` module

Ren'Py has channels: music, sound, voice, ambient. We mirror with aud handles.
Stub for headless; real implementation uses aud.Factory, aud.Handle.

Example:
    factory = aud.Factory(path)
    handle = aud.device().play(factory)
    handle.volume = 0.8
    handle.loop_count = -1  # music
"""
from __future__ import annotations
try:
    import aud  # type: ignore
    import bge
    HAS_AUD = True
except ImportError:
    HAS_AUD = False

from ..core.vn_state import VNState

class AudioManager:
    def __init__(self, state: VNState):
        self.state = state
        self.handles = {}  # channel -> handle

    def apply_event(self, event: dict):
        t = event.get("type")
        if t == "play_music":
            self.play_music(event["asset"], event.get("fadein"))
        elif t == "stop_music":
            self.stop_music(event.get("fadeout"))
        elif t == "play_sound":
            self.play_sound(event["asset"])
        elif t == "play_voice":
            self.play_voice(event["asset"])

    def play_music(self, asset: str, fadein: float | None = None):
        if HAS_AUD:
            # factory = aud.Factory(bge.logic.expandPath(f"//audio/music/{asset}"))
            # h = aud.device().play(factory); h.loop_count = -1
            pass

    def stop_music(self, fadeout: float | None = None):
        if HAS_AUD and "music" in self.handles:
            # fade logic
            pass

    def play_sound(self, asset: str):
        if HAS_AUD:
            pass

    def play_voice(self, asset: str):
        if HAS_AUD:
            pass
