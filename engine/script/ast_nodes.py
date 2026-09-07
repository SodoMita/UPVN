"""
UPVN — AST node definitions

We keep Ren'Py-like authoring comfort but compile to a typed, explicit AST.
No YAML/JSON is the *source* — .rpy is. The AST is the intermediate
that can be serialised to JSON for caching/tracing (see doc §9).

Ren'Py itself does NOT use YAML/JSON internally — it lexes .rpy directly
via renpy/lexer.py + parser.py and pickles to .rpyc. We follow the same
direct path: .rpy → lexer → parser → AST → interpreter.
The AST here is deliberately JSON-serialisable (list[dict]).
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, List, Optional, Literal
import json


# Command types — subset for Tier1 + The Question parity + hybrid stubs
Cmd = Literal[
    "say",            # character dialogue or narration
    "scene",          # background change
    "show",           # 2D sprite show
    "hide",           # hide sprite
    "with",           # transition applied to previous
    "play_music",
    "stop_music",
    "play_sound",
    "play_voice",
    "menu",           # branching
    "jump",
    "call",
    "return",
    "label",          # only in raw AST, then removed to mapping
    "define_character",
    "default",
    "assign",         # $ var = expr
    "if",
    "elif",
    "else",
    # 3D / hybrid stubs (python-driven, LLM can extend)
    "load_stage",
    "show3d",
    "hide3d",
    "anim",
    "camera_preset",
    "camera_zoom",
    "pause",
]


@dataclass
class SourceLocation:
    file: str
    line: int
    col: int = 1

    def to_dict(self):
        return asdict(self)


@dataclass
class ASTNode:
    cmd: str
    args: dict = field(default_factory=dict)
    loc: Optional[SourceLocation] = None

    def to_dict(self) -> dict:
        d = {"cmd": self.cmd, **self.args}
        if self.loc:
            d["_loc"] = self.loc.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ASTNode":
        loc = None
        if "_loc" in d:
            loc = SourceLocation(**d["_loc"])
        cmd = d.pop("cmd")
        d.pop("_loc", None)
        return cls(cmd=cmd, args=d, loc=loc)


def nodes_to_json(nodes: List[ASTNode]) -> str:
    return json.dumps([n.to_dict() for n in nodes], ensure_ascii=False, indent=2)


def nodes_from_json(s: str) -> List[ASTNode]:
    return [ASTNode.from_dict(d) for d in json.loads(s)]
