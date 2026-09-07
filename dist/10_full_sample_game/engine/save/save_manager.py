"""
Save Manager — JSON save files, not pickle (see doc §6)

Save file contents (versioned):
{
  "version": "0.1",
  "current_label": "start",
  "instruction_index": 12,
  "variables": {...},
  "scene": {...},
  "history": [...],
  "rollback_stack": [...]  # optional, not saved by default
}

Ren'Py uses Python pickle for saves — we deliberately avoid that
(criticism: save incompatibility when script changes). We store
only JSON/MessagePack-compatible data plus stable statement IDs.

Rollback-lite: snapshot VNState at every interaction (say/menu).
Mouse wheel up restores previous snapshot.
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Optional

from ..core.vn_state import VNState

SAVE_DIR = Path("saves")

class SaveManager:
    def __init__(self, state: VNState, save_dir: str | Path = SAVE_DIR):
        self.state = state
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def save(self, slot: int | str, screenshot_path: str | None = None) -> Path:
        data = {
            "version": self.state.version,
            "current_label": self.state.current_label,
            "instruction_index": self.state.instruction_index,
            "variables": self.state.variables,
            "scene": {
                "background": self.state.scene.background,
                "actors": {k: {"asset": v.asset, "position": v.position} for k, v in self.state.shown_actors.items()},
            },
            "audio": {
                "music": self.state.audio.music,
            },
            "history": self.state.history[-50:],  # last 50 lines
            "timestamp": time.time(),
            "screenshot": screenshot_path,
        }
        path = self.save_dir / f"save_{slot}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, slot: int | str) -> dict:
        path = self.save_dir / f"save_{slot}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        # restore core fields
        self.state.current_label = data["current_label"]
        self.state.instruction_index = data["instruction_index"]
        self.state.variables = data["variables"]
        # scene
        from ..core.vn_state import SceneState, ShownActor
        self.state.scene.background = data["scene"]["background"]
        self.state.shown_actors = {
            k: ShownActor(tag=k, asset=v["asset"], position=v.get("position", "center"))
            for k, v in data["scene"].get("actors", {}).items()
        }
        self.state.history = data.get("history", [])
        return data

    def list_slots(self):
        return sorted(self.save_dir.glob("save_*.json"))

    def list_slot_ids(self):
        """Return sorted list of slot ids (int or str) that are saves. Arbitrary number."""
        ids = []
        for p in self.save_dir.glob("save_*.json"):
            stem = p.stem  # save_1, save_auto
            sid = stem[5:]  # after save_
            try:
                ids.append(int(sid))
            except ValueError:
                ids.append(sid)
        # sort ints first then strings
        ints = sorted([x for x in ids if isinstance(x, int)])
        strs = sorted([x for x in ids if isinstance(x, str)])
        return ints + strs

    def next_available_slot(self):
        """First unused integer slot (arbitrary, 1..inf)."""
        ids = [x for x in self.list_slot_ids() if isinstance(x, int)]
        if not ids:
            return 1
        n = 1
        s = set(ids)
        while n in s:
            n += 1
        return n

    def delete(self, slot: int | str):
        path = self.save_dir / f"save_{slot}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def slot_exists(self, slot: int | str) -> bool:
        return (self.save_dir / f"save_{slot}.json").exists()

    def get_slot_info(self, slot: int | str):
        path = self.save_dir / f"save_{slot}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def autosave(self):
        return self.save("auto")

    def rollback_snapshot(self) -> dict:
        # called by interpreter
        return self.state.snapshot()
