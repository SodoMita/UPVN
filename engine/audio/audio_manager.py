"""
Audio Manager — wraps UPBGE `aud` module

Ren'Py has channels: music, sound, voice, ambient. We mirror with aud handles.

M26c: play_music/play_sound actually play now (they were `pass` stubs, so
`play music "theme"` in a script did nothing in the player). Everything is
guarded: without the aud/bge modules (headless) or with the 'None' audio
device (sandbox recipe, BUG-016) playback degrades to a one-time log line
and the story continues — a missing audio file can never stop a game.

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


def _dbg(msg: str):
    print(f"[AudioManager] {msg}")


class AudioManager:
    # relative search prefixes for audio files (mirrors the renderers)
    AUDIO_PREFIXES = ("//", "//game/", "//audio/", "//game/audio/",
                      "//../", "//../game/", "//../game/audio/")

    def __init__(self, state: VNState):
        self.state = state
        self.handles = {}  # channel -> handle
        self._device = None
        self._warned = set()

    # ------------------------------------------------------------ internals
    def _warn_once(self, key: str, msg: str):
        if key not in self._warned:
            self._warned.add(key)
            _dbg(msg)

    def _get_device(self):
        if self._device is None:
            self._device = aud.device()
        return self._device

    def _resolve(self, asset: str) -> str | None:
        """Find an audio file for `asset` (name with or without extension),
        relative to the .blend — same prefix conventions as the renderers."""
        import os
        if not asset:
            return None
        names = [asset]
        stem = asset.rsplit(".", 1)[0] if "." in asset else asset
        if stem != asset:
            names.append(stem)
        for name in names:
            for ext in ("", ".ogg", ".wav", ".mp3"):
                for prefix in self.AUDIO_PREFIXES:
                    try:
                        p = bge.logic.expandPath(f"{prefix}{name}{ext}")
                    except Exception:
                        p = f"{prefix}{name}{ext}"
                    try:
                        if os.path.isfile(p):
                            return p
                    except Exception:
                        continue
        return None

    def _play(self, channel: str, asset: str, loop: int = 0,
              fadein: float | None = None) -> bool:
        if not HAS_AUD:
            return False
        path = self._resolve(asset)
        if not path:
            self._warn_once(f"missing:{asset}",
                            f"audio '{asset}' not found — continuing silent")
            return False
        try:
            factory = aud.Factory(path)
            handle = self._get_device().play(factory)
            handle.loop_count = loop
            if fadein:
                try:
                    handle.volume = 0.0
                    # aud has no built-in fade-in; ramp is out of scope for a
                    # first working version — set the requested low start and
                    # jump to full on the next tick via the handle volume.
                    self._fadeins = getattr(self, "_fadeins", {})
                    self._fadeins[channel] = (handle, fadein, __import__("time").time())
                except Exception:
                    pass
            old = self.handles.get(channel)
            if old is not None:
                try:
                    old.stop()
                except Exception:
                    pass
            self.handles[channel] = handle
            _dbg(f"{channel}: playing {path} (loop={loop})")
            return True
        except Exception as e:
            self._warn_once(f"fail:{channel}:{asset}",
                            f"playback failed for {asset}: {e}")
            return False

    def update(self, dt: float):
        """Ramp fade-ins; keep handles alive. Called from the frontend tick."""
        fadeins = getattr(self, "_fadeins", None)
        if not fadeins:
            return
        import time
        for channel, (handle, dur, t0) in list(fadeins.items()):
            try:
                t = (time.time() - t0) / max(0.001, dur)
                if t >= 1.0:
                    handle.volume = 1.0
                    fadeins.pop(channel, None)
                else:
                    handle.volume = t
            except Exception:
                fadeins.pop(channel, None)

    # ------------------------------------------------------------ events
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
        # loop_count -1 = forever
        self._play("music", asset, loop=-1, fadein=fadein)

    def stop_music(self, fadeout: float | None = None):
        handle = self.handles.pop("music", None)
        if handle is not None:
            try:
                handle.stop()
            except Exception:
                pass

    def play_sound(self, asset: str):
        self._play("sound", asset, loop=0)

    def play_voice(self, asset: str):
        self._play("voice", asset, loop=0)
