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
        self.store_dict: Optional[dict] = None  # current python: block namespace (if any)

    def reset(self):
        self.jump_to = None
        self.call_to = None
        self.quit_requested = False


class RenpyNoOp:
    """Stand-in for a ``renpy.*`` member UPVN does not implement (drop-in tier).

    A real Ren'Py game touches hundreds of engine APIs (``renpy.render``,
    ``renpy.display``, ``renpy.TEXT_TEXT`` …). In the drop-in tier we would
    rather keep running the story than abort, so unknown members behave like a
    callable/subscriptable nothing and their names are recorded, which is what
    the compatibility report prints. Dunders stay unreachable, so this is not
    an escape hatch.
    """

    def __init__(self, name: str = "renpy", *args, **kwargs):
        object.__setattr__(self, "_name", name)

    def __mro_entries__(self, bases):
        # lets a real script subclass an engine class we do not model:
        #   class DynamicBlink(renpy.display.layout.DynamicDisplayable): …
        return (object,)

    def __call__(self, *args, **kwargs):
        return None

    def __getattr__(self, item: str):
        if item.startswith("_"):
            raise AttributeError(item)
        return RenpyNoOp(f"{self._name}.{item}")

    def __getitem__(self, key):
        return None

    def __setitem__(self, key, value):
        return None

    def __iter__(self):
        return iter(())

    def __repr__(self):
        return f"<renpy compat no-op: {self._name}>"


class StoreNamespace:
    """Namespace object created by dotted defines (``define gui.accent_color = …``).

    Ren'Py auto-creates ``gui`` / ``config`` / ``build`` objects in the store,
    so ``python:`` blocks can call ``gui.init(1920, 1080)``. UPVN builds the
    same objects from the parsed defines; in the drop-in tier an unknown member
    (``gui.init`` itself is provided by Ren'Py) is a permissive no-op instead
    of a NameError that would stop the story.
    """

    def __init__(self, name: str, values: Optional[dict] = None, permissive: bool = True):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_values", dict(values or {}))
        object.__setattr__(self, "_permissive", permissive)

    def __getattr__(self, item: str):
        if item.startswith("_"):
            raise AttributeError(item)
        values = object.__getattribute__(self, "_values")
        if item in values:
            return values[item]
        if object.__getattribute__(self, "_permissive"):
            return RenpyNoOp(f"{object.__getattribute__(self, '_name')}.{item}")
        raise AttributeError(item)

    def __setattr__(self, item: str, value) -> None:
        if item.startswith("_"):
            raise AttributeError(item)
        object.__getattribute__(self, "_values")[item] = value

    def __contains__(self, item: str) -> bool:
        return item in object.__getattribute__(self, "_values")

    def as_dict(self) -> dict:
        return dict(object.__getattribute__(self, "_values"))

    def __repr__(self) -> str:
        return f"<store namespace {object.__getattribute__(self, '_name')}>"


class RenpyCompat:
    """The ``renpy`` object exposed to full-tier scripts."""

    def __init__(self, runtime: RenpyRuntime, base_dir: Optional[str] = None,
                 permissive: bool = False):
        object.__setattr__(self, "_runtime", runtime)
        object.__setattr__(self, "_base_dir", base_dir)
        object.__setattr__(self, "_random", RandomCompat())
        object.__setattr__(self, "_permissive", permissive)
        object.__setattr__(self, "compat_log", [])

    # ---- allowlist enforcement: nothing else is reachable (strict mode)
    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        if self._permissive:
            self.compat_log.append(name)
            return RenpyNoOp(f"renpy.{name}")
        raise AttributeError(f"renpy.{name} is not available in UPVN")

    # ---- attribute-backed members
    @property
    def random(self) -> RandomCompat:
        return self._random

    @property
    def store(self) -> StoreWrapper:
        d = self._runtime.store_dict
        if d is None:
            interp = self._runtime.interpreter
            d = interp.state.variables if interp else {}
        return StoreWrapper(d)

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


def identity_translation(text="", *args, **kwargs):
    """Stand-in for Ren'Py's ``_()`` / ``_p()``: returns the text unchanged.

    UPVN has no translation catalogue, but almost every real game wraps its
    strings in ``_()``, so the call must work rather than raise NameError.
    """
    return text


class PermissiveEnv(dict):
    """Globals dict for ``python:`` blocks in drop-in compat mode.

    Unknown global names resolve to a recorded no-op instead of raising, so a
    game that needs an engine API (``MusicRoom``, ``FileSave`` …) or a
    third-party module UPVN does not ship still plays through. Entries are NOT
    cached, so the namespace stays clean and only real assignments sync back.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.missing_log: list = []

    def __missing__(self, key: str):
        if key.startswith("__"):
            raise KeyError(key)
        self.missing_log.append(key)
        return RenpyNoOp(key)
