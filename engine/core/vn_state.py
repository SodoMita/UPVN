"""
UPVN — VNState

Single source-of-truth for save/load and rollback.
All mutable gameplay state lives here and is JSON-serialisable
by design (no pickle of object graphs — see criticism #7 in doc).

This mirrors Ren'Py's execution state but intentionally NOT using pickle.
"""
from __future__ import annotations
import copy
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class CharacterDef:
    id: str
    name: str
    color: str = "#ffffff"
    # Ren'Py supports many extras (what_prefix, image, etc.)
    # Keep extensible via dict.
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ShownActor:
    tag: str          # e.g. "eileen" or "sylvie"
    asset: str        # e.g. "sylvie green smile"
    position: str = "center"   # left / center / right / custom marker
    layer: int = 1
    transition: Optional[str] = None
    # M10 ATL-lite move interpolation
    move_from: Optional[str] = None
    move_to: Optional[str] = None
    move_t0: Optional[float] = None
    move_duration: float = 0.5
    move_easing: str = "ease"


@dataclass
class SceneState:
    background: Optional[str] = None  # "bg lecturehall" or "black"
    transition: Optional[str] = None


@dataclass
class AudioState:
    music: Optional[str] = None
    music_volume: float = 1.0
    sound: Optional[str] = None
    voice: Optional[str] = None


@dataclass
class VNState:
    """
    Complete serialisable gameplay state.
    Designed so that `json.dumps(asdict(state))` is save file.
    """
    # execution pointer
    current_label: str = "start"
    instruction_index: int = 0
    call_stack: List[Dict[str, Any]] = field(default_factory=list)

    # variables declared via `default` or `$`
    variables: Dict[str, Any] = field(default_factory=dict)

    # character registry (define)
    characters: Dict[str, CharacterDef] = field(default_factory=dict)

    # presentation
    scene: SceneState = field(default_factory=SceneState)
    shown_actors: Dict[str, ShownActor] = field(default_factory=dict)

    # audio
    audio: AudioState = field(default_factory=AudioState)

    # 3D stage (hybrid mode stub — LLM can populate via python)
    stage: Optional[str] = None          # e.g. "classroom_3d"
    stage_objects: Dict[str, Any] = field(default_factory=dict)  # id -> {marker, anim}
    camera: Dict[str, Any] = field(default_factory=dict)  # preset / pos

    # history / backlog / skip / auto (M07)
    history: List[Dict[str, Any]] = field(default_factory=list)
    seen_history: List[str] = field(default_factory=list)  # hashes of seen lines for skip
    skip: bool = False
    auto: bool = False
    auto_delay: float = 0.7  # seconds per line in auto mode
    # persistent across saves (like Ren'Py persistent)
    persistent: Dict[str, Any] = field(default_factory=dict)

    # metadata
    version: str = "0.1.0"
    script_hash: Optional[str] = None

    def snapshot(self) -> dict:
        """Deep copy for rollback — must be JSON-safe."""
        return copy.deepcopy(asdict(self))

    def restore(self, snap: dict):
        """Restore from snapshot dict."""
        for k, v in snap.items():
            if k == "scene" and isinstance(v, dict):
                self.scene = SceneState(**v)
            elif k == "audio" and isinstance(v, dict):
                self.audio = AudioState(**v)
            elif k == "characters" and isinstance(v, dict):
                self.characters = {cid: CharacterDef(**c) for cid, c in v.items()}
            elif k == "shown_actors" and isinstance(v, dict):
                self.shown_actors = {tag: ShownActor(**a) for tag, a in v.items()}
            else:
                setattr(self, k, v)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, data: str) -> "VNState":
        d = json.loads(data)
        s = cls()
        s.restore(d)
        return s

    # helper -------------------------------------------------------------
    def get_character_name(self, who_id: str) -> str:
        c = self.characters.get(who_id)
        return c.name if c else who_id

    def clone(self) -> "VNState":
        return copy.deepcopy(self)
