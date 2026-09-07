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
        # ensure save_dir is resolved for traversal checks
        try:
            self.save_dir = self.save_dir.resolve()
        except:
            pass

    def _sanitize_slot(self, slot: int | str) -> str:
        """Validate and sanitize slot — fixes L-1 path traversal.
        Accepts int (1..1000000) or string 'auto' or alphanum/underscore/dash.
        Rejects path separators, '..', absolute paths, and unsafe chars.
        """
        if isinstance(slot, int):
            if not (1 <= slot <= 10_000_000):
                raise ValueError(f"slot int out of range 1..10000000: {slot!r}")
            return str(slot)
        if isinstance(slot, str):
            # allow 'auto' and numeric strings; otherwise strict alphanum
            if slot == "auto":
                return "auto"
            # numeric string e.g. "42" -> treat as int string but validate
            if slot.isdigit():
                # ensure no leading +/-, just digits
                iv = int(slot)
                if not (1 <= iv <= 10_000_000):
                    raise ValueError(f"slot out of range: {slot!r}")
                return str(iv)
            # for arbitrary string slots, enforce safe pattern
            import re
            if not re.match(r"^[A-Za-z0-9_-]{1,64}$", slot):
                raise ValueError(f"invalid slot string (must match ^[A-Za-z0-9_-]{{1,64}}$): {slot!r}")
            if "/" in slot or "\\" in slot or ".." in slot:
                raise ValueError(f"invalid slot (path separator): {slot!r}")
            return slot
        raise TypeError(f"slot must be int or str, got {type(slot).__name__}: {slot!r}")

    def _slot_path(self, slot: int | str) -> Path:
        sid = self._sanitize_slot(slot)
        # construct path and ensure it stays under save_dir (resolve check)
        candidate = (self.save_dir / f"save_{sid}.json").resolve()
        try:
            # Python 3.9+: is_relative_to
            if hasattr(candidate, "is_relative_to"):
                if not candidate.is_relative_to(self.save_dir.resolve()):
                    raise ValueError(f"slot escapes save_dir: {slot!r}")
            else:
                # fallback string check
                if not str(candidate).startswith(str(self.save_dir.resolve())):
                    raise ValueError(f"slot escapes save_dir: {slot!r}")
        except ValueError:
            raise
        except Exception:
            pass
        return candidate

    def save(self, slot: int | str, screenshot_path: str | None = None) -> Path:
        # sanitize slot first (L-1)
        self._sanitize_slot(slot)
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
        path = self._slot_path(slot)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, slot: int | str) -> dict:
        path = self._slot_path(slot)
        if not path.exists():
            raise FileNotFoundError(f"save slot not found: {slot!r}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"corrupt save slot {slot!r}: {e}")
        # L-2: validate schema + version
        if not isinstance(data, dict):
            raise ValueError(f"invalid save format (not dict) slot {slot!r}")
        version = data.get("version")
        # accept missing version for backwards compat but warn; check type if present
        if version is not None and not isinstance(version, str):
            raise ValueError(f"invalid version type slot {slot!r}")
        # validate required fields with types and defaults
        # current_label
        cl = data.get("current_label")
        if not isinstance(cl, str):
            raise ValueError(f"invalid save: current_label must be str slot {slot!r}")
        # instruction_index
        ii = data.get("instruction_index")
        if not isinstance(ii, int):
            # coerce if possible
            try:
                ii = int(ii)
            except:
                raise ValueError(f"invalid save: instruction_index must be int slot {slot!r}")
        # variables
        vars_data = data.get("variables")
        if not isinstance(vars_data, dict):
            raise ValueError(f"invalid save: variables must be dict slot {slot!r}")
        # scene
        scene_data = data.get("scene")
        if not isinstance(scene_data, dict):
            raise ValueError(f"invalid save: scene must be dict slot {slot!r}")
        bg = scene_data.get("background")
        if bg is not None and not isinstance(bg, str):
            raise ValueError(f"invalid save: scene.background must be str slot {slot!r}")
        actors = scene_data.get("actors", {})
        if not isinstance(actors, dict):
            raise ValueError(f"invalid save: scene.actors must be dict slot {slot!r}")
        # history
        hist = data.get("history", [])
        if not isinstance(hist, list):
            raise ValueError(f"invalid save: history must be list slot {slot!r}")
        # truncate history to last 50 if huge (defense)
        if len(hist) > 200:
            hist = hist[-200:]
        # restore core fields with validated types
        self.state.current_label = cl
        self.state.instruction_index = ii
        self.state.variables = vars_data
        # scene
        from ..core.vn_state import SceneState, ShownActor
        self.state.scene.background = bg
        # actors: validate each entry
        cleaned_actors = {}
        for k, v in actors.items():
            if not isinstance(k, str) or not isinstance(v, dict):
                continue
            asset = v.get("asset")
            if not isinstance(asset, str):
                continue
            pos = v.get("position", "center")
            if not isinstance(pos, str):
                pos = "center"
            cleaned_actors[k] = ShownActor(tag=k, asset=asset, position=pos)
        self.state.shown_actors = cleaned_actors
        self.state.history = hist
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
        path = self._slot_path(slot)
        if path.exists():
            path.unlink()
            return True
        return False

    def slot_exists(self, slot: int | str) -> bool:
        try:
            return self._slot_path(slot).exists()
        except (ValueError, TypeError):
            return False

    def get_slot_info(self, slot: int | str):
        try:
            path = self._slot_path(slot)
        except (ValueError, TypeError):
            return None
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
