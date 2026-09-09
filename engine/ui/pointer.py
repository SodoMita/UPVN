"""
UPVN — pointer & hotspot events for editor-built UI (no screen DSL)

The UPVN UI is authored in the Blender editor as named objects — planes,
meshes, buttons — laid out over the stage. Python's only job at runtime is
to turn "what is under the cursor" into semantic events, exactly as the
frontend already does for keyboard input.

This module is pure Python (no `bge` import) so it is testable headlessly.
The UPBGE frontend pumps it every frame:

    tracker.update(object_under_cursor, clicked=left_mouse_just_pressed)

and forwards `click` events on choices to `VNController.choose(index)`.

Menu choices carry a stable `id` (see vn_interpreter.py), and by convention
the editor names the choice objects `choice_<id>` — so the mapping is
automatic via `HotspotMap.from_choices(...)`.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


@dataclass
class Hotspot:
    """One editor object the pointer can hover over / click."""

    name: str                                  # editor object name
    action: str = "choice"                     # semantic action kind
    choice_index: Optional[int] = None         # for action == "choice"
    enabled: bool = True

    def matches(self, object_name: Optional[str]) -> bool:
        return object_name == self.name


@dataclass
class PointerEvent:
    """A semantic pointer event produced for the frontend."""

    kind: str                                  # "enter" | "leave" | "click"
    object: str
    action: str = "choice"
    choice_index: Optional[int] = None


class HotspotMap:
    """Editor object name -> semantic hotspot (built once per menu)."""

    def __init__(self, hotspots: Sequence[Hotspot] = ()):
        self._by_name: Dict[str, Hotspot] = {}
        for h in hotspots:
            self._by_name[h.name] = h

    def add(self, hotspot: Hotspot) -> "HotspotMap":
        self._by_name[hotspot.name] = hotspot
        return self

    def resolve(self, object_name: Optional[str]) -> Optional[Hotspot]:
        if object_name is None:
            return None
        return self._by_name.get(object_name)

    @classmethod
    def from_choices(cls, choices: Sequence[dict], prefix: str = "choice") -> "HotspotMap":
        """Build a map for a menu event's choices (each has an `id`).

        Choice i maps to editor object named f"{prefix}_{i}".
        """
        m = cls()
        for i, _c in enumerate(choices):
            m.add(Hotspot(name=f"{prefix}_{i}", action="choice", choice_index=i))
        return m


class PointerTracker:
    """Stateful hover/click tracking, driven by the frontend each frame."""

    def __init__(self, hotspots: HotspotMap):
        self.hotspots = hotspots
        self.hovered: Optional[str] = None

    def update(self, object_under_cursor: Optional[str], clicked: bool = False) -> List[PointerEvent]:
        """Feed the object currently under the cursor + a click flag.

        Returns the list of semantic events that happened this frame
        (enter/leave on hover change, click when pressed over a hotspot).
        """
        events: List[PointerEvent] = []

        # hover change
        if object_under_cursor != self.hovered:
            if self.hovered is not None:
                events.append(self._event("leave", self.hovered))
            if object_under_cursor is not None:
                events.append(self._event("enter", object_under_cursor))
            self.hovered = object_under_cursor

        # click — only fires over an enabled hotspot
        if clicked and object_under_cursor is not None:
            events.append(self._event("click", object_under_cursor))

        return events

    def _event(self, kind: str, object_name: str) -> PointerEvent:
        h = self.hotspots.resolve(object_name)
        return PointerEvent(
            kind=kind,
            object=object_name,
            action=h.action if h else "none",
            choice_index=h.choice_index if h else None,
        )

    def choose(self, event: PointerEvent) -> Optional[int]:
        """Return the choice index for a click event (None if not a choice)."""
        if event.kind != "click":
            return None
        h = self.hotspots.resolve(event.object)
        if h is None or not h.enabled:
            return None
        return h.choice_index
