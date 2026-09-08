"""
UPVN — `renpy` compatibility namespace (full .rpy tier only)

Real Ren'Py scripts call ``renpy.*`` functions inside `if` conditions and
`python:` blocks (The Question uses ``renpy.loadable(...)``). For the
drop-in tier we provide a small, safe stand-in object that exposes the most
common functions. It is intentionally NOT a real module import:

- every attribute is on an explicit allowlist (``__getattr__`` rejects the rest),
- dunder names are blocked by the expression evaluator anyway,
- state access goes through the interpreter's runtime, so `renpy.jump(...)`
  from a `python:` block can redirect the interpreter.

This object is only injected in full mode — never in the safe subset or
.urpy tiers.
"""
from __future__ import annotations
import random as _random_module
from typing import Any, Optional


class StoreWrapper:
    """Exposes the variables dict as ``store.attr`` (no dunder access)."""

    def __init__(self, variables: dict):
        object.__setattr__(self, "_vars", variables)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._vars.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            raise AttributeError(name)
        self._vars[name] = value

    def __contains__(self, name: str) -> bool:
        return name in self._vars


class RandomCompat:
    """A bounded random source for ``renpy.random.*``."""

    def __init__(self):
        self._rng = _random_module.Random()

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def choice(self, seq):
        return self._rng.choice(seq)

    def random(self) -> float:
        return self._rng.random()

    def uniform(self, a: float, b: float) -> float:
        return self._rng.uniform(a, b)


class RenpyRuntime:
    """Per-interpreter runtime shared with the `renpy` compat object."""

    def __init__(self, interpreter=None):
        self.interpreter = interpreter
        self.jump_to: Optional[str] = None
        self.call_to: Optional[str] = None
        self.quit_requested: bool = False

    def reset(self):
        self.jump_to = None
        self.call_to = None
        self.quit_requested = False


class RenpyCompat:
    """The ``renpy`` object exposed to full-tier scripts."""

    def __init__(self, runtime: RenpyRuntime, base_dir: Optional[str] = None):
        object.__setattr__(self, "_runtime", runtime)
        object.__setattr__(self, "_base_dir", base_dir)
        object.__setattr__(self, "_random", RandomCompat())

    # ---- allowlist enforcement: nothing else is reachable
    def __getattr__(self, name: str):
        raise AttributeError(f"renpy.{name} is not available in UPVN")

    # ---- attribute-backed members
    @property
    def random(self) -> RandomCompat:
        return self._random

    @property
    def store(self) -> StoreWrapper:
        interp = self._runtime.interpreter
        return StoreWrapper(interp.state.variables if interp else {})

    # ---- files / labels
    def loadable(self, path: str) -> bool:
        import os
        if self._base_dir:
            candidates = [os.path.join(self._base_dir, path)]
            for sub in ("game", "images", "audio", "assets"):
                candidates.append(os.path.join(self._base_dir, sub, path))
            return any(os.path.exists(c) for c in candidates)
        return True

    def has_label(self, name: str) -> bool:
        interp = self._runtime.interpreter
        return bool(interp and name in interp.labels)

    # ---- audio state
    def get_playing(self, channel: str = "music"):
        interp = self._runtime.interpreter
        if not interp:
            return None
        if channel == "music":
            return interp.state.audio.music
        if channel == "sound":
            return interp.state.audio.sound
        if channel == "voice":
            return interp.state.audio.voice
        return None

    # ---- control flow (used from python: blocks)
    def jump(self, label: str):
        self._runtime.jump_to = label

    def call(self, label: str):
        self._runtime.call_to = label

    def quit(self):
        self._runtime.quit_requested = True

    # ---- harmless no-ops commonly called by real scripts
    def end_replay(self):
        pass

    def notify(self, message: str):
        pass

    def pause(self, delay: float = 0.0):
        pass

    def mark_seen(self, *args):
        pass

    def seen_label(self, name: str) -> bool:
        return False

    def say(self, who, what: str, *args, **kwargs):
        interp = self._runtime.interpreter
        if interp is not None:
            interp.state.history.append({
                "who": who if isinstance(who, str) else getattr(who, "id", None),
                "who_name": who if isinstance(who, str) else None,
                "raw": what, "text": what, "display_text": what, "stripped": what,
                "label": interp.state.current_label, "index": interp.state.instruction_index,
            })
