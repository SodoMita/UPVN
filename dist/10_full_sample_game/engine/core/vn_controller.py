"""
UPVN — VNController (UPBGE Python component)

Main runtime controller — mirrors doc §3 A.

Responsibilities:
    - load scripts (parse .rpy → AST)
    - manage VNState
    - run interpreter coroutine
    - wait for player input (bge.events / mouse click)
    - trigger UI / render / audio managers
    - save/load + rollback

Usage in .blend:
    - Create Empty "VNController"
    - Add Python component: from upvn.engine.core.vn_controller import VNController
    - Set script path: //game/script.rpy
    - Add Always sensor (True pulse) -> Python controller -> VNController.update

For headless tests, use without bge:
    ctrl = VNController(script_path="examples/00_minimal_dialogue/script.rpy")
    ctrl.load() ; trace = ctrl.run_headless(choices=[0])
"""
from __future__ import annotations
import copy
import json
import time
from pathlib import Path
from typing import Optional, List

from .vn_state import VNState
from .vn_interpreter import VNInterpreter
try:
    from ..script.parser import parse_file, parse_string
except ImportError:
    parse_file = None  # type: ignore
    parse_string = None  # type: ignore

try:
    import bge  # type: ignore
    HAS_BGE = True
except ImportError:
    HAS_BGE = False
    bge = None  # type: ignore


def _digit_choice_index(states: dict, count: int) -> int | None:
    """Map per-digit states to a menu choice index. Pure helper (unit-testable).

    states: {digit key code: 'just' | 'active' | None} — produced by
    _bge_input_state for each of the first 9 digits. Digit key codes are ASCII
    (ONEKEY == ord('1') == 49). Returns the index (0-based) of the lowest digit
    that is 'just' and within count; None otherwise.
    """
    if not states:
        return None
    for i in range(min(9, count)):
        if states.get(ord("1") + i) == "just":
            return i
    return None


def _classify_input_entry(entry, just_code: int = 1, active_code: int = 2):
    """Map one SCA_InputEvent (or a legacy int) to 'just' | 'active' | None.

    UPBGE 0.50: JUST_ACTIVATED lives in entry.queue (list), ACTIVE in
    entry.status (list). Convenience bools .activated/.active exist on
    SCA_InputEvent. Never reads device.events (deprecated). Pure; unit-testable.
    """
    if entry is None:
        return None
    if isinstance(entry, int):
        if entry == just_code:
            return "just"
        if entry == active_code:
            return "active"
        return None
    try:
        queue = getattr(entry, "queue", None)
        if queue is not None and just_code in queue:
            return "just"
    except Exception:
        pass
    try:
        if getattr(entry, "activated", False):
            return "just"
    except Exception:
        pass
    try:
        status = getattr(entry, "status", None)
        if status is not None:
            if status == just_code or (isinstance(status, (list, tuple)) and just_code in status):
                return "just"
    except Exception:
        pass
    try:
        if getattr(entry, "active", False):
            return "active"
    except Exception:
        pass
    try:
        status = getattr(entry, "status", None)
        if status is not None:
            if status == active_code or (isinstance(status, (list, tuple)) and active_code in status):
                return "active"
    except Exception:
        pass
    return None


def _bge_input_state(device_name: str, key: int):
    """Input state for one key on a bge device: 'just' | 'active' | None.

    Uses device.inputs[key] only (UPBGE 0.50). Never touches device.events
    (deprecated; conversion is lossy — LMB can work while keys do not).
    Headless (no bge) returns None. Never raises.
    """
    if not HAS_BGE:
        return None
    try:
        import bge as _bge_imp
        dev = getattr(_bge_imp.logic, device_name, None)
        if dev is None:
            return None
    except Exception:
        return None
    try:
        just_c = _bge_imp.logic.KX_INPUT_JUST_ACTIVATED
        active_c = _bge_imp.logic.KX_INPUT_ACTIVE
    except Exception:
        just_c, active_c = 1, 2
    try:
        inputs = getattr(dev, "inputs", None)
        if inputs is None:
            return None
        return _classify_input_entry(inputs[key], just_c, active_c)
    except Exception:
        return None


def _bge_just(device_name: str, key: int) -> bool:
    return _bge_input_state(device_name, key) == "just"


def _bge_active(device_name: str, key: int) -> bool:
    return _bge_input_state(device_name, key) in ("just", "active")


def _merge_scripts(a: dict | None, b: dict | None) -> dict:
    """Merge two parsed script dicts (used for multi-file game dirs)."""
    out: dict = {
        "labels": {}, "characters": {}, "defaults": {}, "types": {},
        "assets": {"images": {}, "audio": {}, "stages": {}},
        "label_params": {}, "defines": {}, "init_python": [],
        "transforms": {}, "screens": {}, "styles": {}, "translations": {},
        "image_blocks": {}, "from_clauses": [],
        "custom_statements": {}, "custom_statement_errors": [],
    }
    for d in (a, b):
        if not d:
            continue
        out["labels"].update(d.get("labels", {}))
        out["characters"].update(d.get("characters", {}))
        out["defaults"].update(d.get("defaults", {}))
        out["types"].update(d.get("types", {}))
        for kind in ("images", "audio", "stages"):
            out["assets"][kind].update(d.get("assets", {}).get(kind, {}))
        out["label_params"].update(d.get("label_params", {}))
        out["defines"].update(d.get("defines", {}))
        out["init_python"].extend(d.get("init_python", []))
        out["transforms"].update(d.get("transforms", {}))
        out["screens"].update(d.get("screens", {}))
        out["styles"].update(d.get("styles", {}))
        out["translations"].update(d.get("translations", {}))
        out["image_blocks"].update(d.get("image_blocks", {}))
        out["from_clauses"].extend(d.get("from_clauses", []))
        for name, blocks in d.get("custom_statements", {}).items():
            out["custom_statements"].setdefault(name, []).extend(blocks)
        out["custom_statement_errors"].extend(d.get("custom_statement_errors", []))
        if d.get("full"):
            out["full"] = True
        if d.get("language") == "urpy":
            out["language"] = "urpy"
    return out


class VNController:
    def __init__(self, script_path: str | Path | None = None, script_dict: dict | None = None,
                 state: Optional[VNState] = None, mode: str = "safe", compat: bool = False):
        self.script_path = Path(script_path) if script_path else None
        self.script_dict = script_dict
        self.state = state or VNState()
        self.mode = mode  # "safe" (default declarative subset) | "full" (drop-in Ren'Py)
        self.compat = compat  # full tier: collect python: failures instead of raising
        self.interp: Optional[VNInterpreter] = None
        self._gen = None
        self._current_event: Optional[dict] = None
        self._waiting = False
        self._forward_stack: List[dict] = []  # for roll-forward (M08) state snapshots
        self._forward_labels_stack: List[dict] = []  # parallel labels
        self._auto_timer: float = 0.0

        # sub-managers (created after load)
        self.scene_mgr = None
        self.sprite_mgr = None
        self.stage_mgr = None
        self.ui_mgr = None
        self.audio_mgr = None
        self.screen_mgr = None

    # ---------------------------- loading
    def load(self):
        if self.script_dict is None:
            if self.script_path is None:
                raise ValueError("no script_path or script_dict provided")
            if parse_file is None:
                raise ImportError("parser not available")
            # handle directory containing multiple .rpy/.urpy files (manifest-free for Tier1)
            if self.script_path.is_dir():
                # Scan the whole game/ dir and merge — exactly what Ren'Py does.
                # Each file is parsed on its own so errors keep their real
                # file:line, and `start` may live in any file.
                merged = None
                for p in sorted(set(list(self.script_path.rglob("*.rpy"))
                                    + list(self.script_path.rglob("*.urpy")))):
                    d = parse_file(str(p), mode=self.mode, require_start=False)
                    merged = _merge_scripts(merged, d)
                if merged is None:
                    raise ValueError(f"no .rpy/.urpy scripts found in {self.script_path}")
                if "start" not in merged["labels"]:
                    from .vn_errors import ParseError as _PE
                    raise _PE('missing required label "start:"', str(self.script_path), 1,
                              hint="one of the game's .rpy files must define `label start:`")
                self.script_dict = merged
            else:
                self.script_dict = parse_file(str(self.script_path), mode=self.mode)
                # hash for save compatibility
                import hashlib
                txt = Path(self.script_path).read_text(encoding="utf-8")
                self.state.script_hash = hashlib.sha256(txt.encode("utf-8")).hexdigest()[:12]

        # init interpreter
        base_dir = None
        if self.script_path is not None:
            base_dir = str(self.script_path if self.script_path.is_dir()
                           else self.script_path.parent)
        self.interp = VNInterpreter(self.script_dict, self.state, base_dir=base_dir,
                                    compat=self.compat)
        self._gen = self.interp.run()

        # init managers (lazy, allow headless without bge)
        try:
            from ..render.scene_manager import SceneManager
            from ..render.sprite_renderer import SpriteRenderer
            from ..render.stage_manager import StageManager
            from ..ui.dialogue_box import DialogueBox
            from ..audio.audio_manager import AudioManager
            from ..ui.screen_manager import ScreenManager
            from ..save.save_manager import SaveManager
            self.scene_mgr = SceneManager(self.state)
            self.sprite_mgr = SpriteRenderer(self.state)
            self.stage_mgr = StageManager(self.state)
            self.ui_mgr = DialogueBox(self.state)
            self.audio_mgr = AudioManager(self.state)
            # screen manager uses save manager for save/load slots
            try:
                sm = SaveManager(self.state)
            except: sm = None
            self.screen_mgr = ScreenManager(self.state, save_manager=sm)
        except Exception:
            pass
            self.screen_mgr = None

        # advance to first wait event
        self._advance()

    def _advance(self, send_value=None):
        if self._gen is None:
            return
        try:
            if self._current_event is None:
                # first call
                self._current_event = next(self._gen)
            else:
                if send_value is not None:
                    self._current_event = self._gen.send(send_value)
                else:
                    self._current_event = next(self._gen)
            self._waiting = bool(self._current_event and self._current_event.get("wait"))
            self._dispatch(self._current_event)
            # auto-advance non-waiting events
            while self._current_event and not self._waiting:
                try:
                    self._current_event = next(self._gen)
                    if self._current_event is None:
                        continue
                    self._dispatch(self._current_event)
                    self._waiting = bool(self._current_event.get("wait"))
                    if self._waiting:
                        break
                except StopIteration:
                    self._current_event = {"type": "end"}
                    self._waiting = False
                    break
        except StopIteration:
            self._current_event = {"type": "end"}
            self._waiting = False

    def _dispatch(self, event: dict):
        if event is None:
            return
        # route to managers
        try:
            if self.scene_mgr:
                self.scene_mgr.apply_event(event)
            if self.sprite_mgr:
                self.sprite_mgr.apply_event(event)
            if self.stage_mgr:
                self.stage_mgr.apply_event(event)
            if self.ui_mgr and event.get("type") == "say":
                self.ui_mgr.show(event)
            if self.audio_mgr:
                self.audio_mgr.apply_event(event)
        except Exception:
            pass

    # ---------------------------- per-frame update (called from UPBGE)
    def update(self, dt: float = 0.016):
        # dt from frontend; also works if called without dt via Always sensor
        if not HAS_BGE:
            # M10: tick stage/sprite for headless atl (so is_move_done reflects)
            if self.stage_mgr:
                try: self.stage_mgr.update(dt)
                except: pass
            if self.sprite_mgr:
                try: self.sprite_mgr.update(dt)
                except: pass
            # still tick typewriter for headless callers that poll update(dt)
            if self.ui_mgr and self._waiting and self._current_event and self._current_event.get("type") in ("say", "pause"):
                self.ui_mgr.update_typewriter(dt)
                # auto/skip handling headless (M07)
                if self.state.skip or self.state.auto:
                    self._auto_timer += dt
                    delay = 0.05 if self.state.skip else self.state.auto_delay
                    # for skip, only skip if already seen (check seen_history)
                    if self.state.skip:
                        # if not seen, don't skip — wait for input simulation
                        # we approximate: if stripped hash not in seen_history[:-1], don't skip
                        cur = self._current_event
                        if cur and cur.get("type") == "say":
                            stripped = cur.get("text", "")
                            try:
                                from .vn_interpreter import strip_tags
                                stripped = strip_tags(stripped)
                            except: pass
                            h = f"{self.state.current_label}:{self.state.instruction_index}:{stripped}"
                            # last entry is current, so check earlier
                            if h not in self.state.seen_history[:-1]:
                                self._auto_timer = 0
                                return
                    if self._auto_timer >= delay:
                        self._auto_timer = 0
                        if self.ui_mgr and not self.ui_mgr.is_done():
                            self.ui_mgr.instant_reveal()
                        else:
                            self._advance()
                        return
                # auto-advance pause when duration elapsed
                if self._current_event.get("type") == "pause":
                    dur = self._current_event.get("duration", 0.5)
                    # use ui progress as timer? For pause we store elapsed in _typewriter_progress
                    if self.ui_mgr._typewriter_progress >= dur * 40:  # chars/sec 40 -> convert
                        self._advance()
            return
        # handle transitions: block advance until fade/dissolve done
        if self.scene_mgr and not self.scene_mgr.is_transition_done():
            # still fading, keep rendering alpha via scene_mgr.transition_alpha()
            if self.sprite_mgr:
                self.sprite_mgr.update(dt)
            if self.stage_mgr:
                try: self.stage_mgr.update(dt)
                except: pass
            if self.ui_mgr and self._waiting:
                self.ui_mgr.update_typewriter(dt)
            return
        if self.sprite_mgr:
            self.sprite_mgr.update(dt)
        if self.stage_mgr:
            try: self.stage_mgr.update(dt)
            except: pass
        # M09: modal screens block story advance
        if self.screen_mgr and self.screen_mgr.is_modal_active():
            # still tick overlays? modal blocks typewriter/auto/advance
            # allow ESC to dismiss modal via handle_key
            if HAS_BGE:
                try:
                    import bge as _bge_imp
                    if _bge_just("keyboard", _bge_imp.events.ESCKEY):
                        self.screen_mgr.handle_key("escape")
                except Exception:
                    pass
            return
        # M07 skip/auto handling (BGE)
        if self._waiting and self._current_event and (self.state.skip or self.state.auto):
            self._auto_timer += dt
            delay = 0.05 if self.state.skip else self.state.auto_delay
            # skip only if already seen
            should_skip = True
            if self.state.skip and self._current_event.get("type") == "say":
                try:
                    from .vn_interpreter import strip_tags
                    stripped = strip_tags(self._current_event.get("text",""))
                    h = f"{self.state.current_label}:{self.state.instruction_index}:{stripped}"
                    if h not in self.state.seen_history[:-1]:
                        should_skip = False
                except: pass
            if should_skip and self._auto_timer >= delay:
                self._auto_timer = 0
                if self.ui_mgr and self._current_event.get("type") == "say" and not self.ui_mgr.is_done():
                    self.ui_mgr.instant_reveal()
                else:
                    self._advance()
                return
        else:
            self._auto_timer = 0
        # check input: mouse click / space / enter to advance
        if self._waiting and self._current_event:
            # first tick typewriter
            if self.ui_mgr and self._current_event.get("type") == "say":
                done = self.ui_mgr.update_typewriter(dt)
                if not done:
                    # typewriter still running — click will instant reveal
                    if self._is_advance_pressed():
                        self.ui_mgr.instant_reveal()
                    return
            if self._is_advance_pressed():
                if self._current_event.get("type") == "say":
                    self._advance(send_value=None)
                elif self._current_event.get("type") == "menu":
                    # click/space intentionally does not advance a menu;
                    # choice comes from number keys (below) or controller.choose()
                    pass
                elif self._current_event.get("type") == "pause":
                    self._advance()
                # dissolve/fade auto-advance after duration is handled above
            # M18: menu choices via number keys 1..9 — the in-engine fallback
            # until pointer/raycast choice-clicking is wired in the frontend.
            if self._current_event.get("type") == "menu" and HAS_BGE:
                try:
                    import bge as _bge_imp
                    ev = _bge_imp.events
                    count = len(self._current_event.get("choices", []))
                    digit_states = {}
                    for i in range(min(9, count)):
                        key = ord("1") + i
                        st = _bge_input_state("keyboard", key)
                        pad = getattr(ev, f"PAD{i + 1}", None) or getattr(ev, f"PAD{i + 1}KEY", None)
                        if pad is not None and _bge_input_state("keyboard", pad) == "just":
                            st = "just"
                        digit_states[key] = st
                    idx = _digit_choice_index(digit_states, count)
                    if idx is not None:
                        self.choose(idx)
                        return
                except Exception:
                    pass
            # skip/auto toggles via keys + screens H/Q (M09)
            if HAS_BGE:
                try:
                    import bge as _bge_imp
                    ev = _bge_imp.events
                    if _bge_just("keyboard", ev.SKEY):  # S for skip
                        self.toggle_skip()
                    if _bge_just("keyboard", ev.AKEY):  # A for auto
                        self.toggle_auto()
                    if _bge_just("keyboard", ev.HKEY):  # H for history
                        if self.screen_mgr:
                            self.screen_mgr.handle_key("h")
                    if _bge_just("keyboard", ev.QKEY):  # Q for quick menu
                        if self.screen_mgr:
                            self.screen_mgr.handle_key("q")
                    if _bge_just("keyboard", ev.SKEY) and _bge_active("keyboard", ev.LEFTCTRLKEY):  # Ctrl+S quick save
                        if self.screen_mgr:
                            self.screen_mgr.show("save")
                    if _bge_just("keyboard", ev.LKEY) and _bge_active("keyboard", ev.LEFTCTRLKEY):  # Ctrl+L quick load
                        if self.screen_mgr:
                            self.screen_mgr.show("load")
                except Exception:
                    pass
        # rollback: mouse wheel up, forward wheel down (M08)
        if HAS_BGE and self._is_rollback_pressed():
            self.rollback()
        if HAS_BGE and self._is_rollforward_pressed():
            self.roll_forward()

        # for pause type, auto-advance after duration even without click (when no BGE input)
        if self._waiting and self._current_event and self._current_event.get("type") == "pause":
            if not HAS_BGE:
                # handled above
                pass
            else:
                # in BGE, pause should also auto-advance after duration if no input processing already
                dur = self._current_event.get("duration", 0.5)
                # use a simple timer stored on controller
                if not hasattr(self, "_pause_t0"):
                    self._pause_t0 = time.time()  # type: ignore
                if time.time() - self._pause_t0 >= dur:  # type: ignore
                    delattr(self, "_pause_t0")
                    self._advance()
            # reset timer when leaving pause
            if self._current_event.get("type") != "pause" and hasattr(self, "_pause_t0"):
                delattr(self, "_pause_t0")

    def _is_advance_pressed(self) -> bool:
        if not HAS_BGE:
            return False
        try:
            import bge as _bge_imp
            ev = _bge_imp.events
        except Exception:
            return False
        # Mouse left, Space, Enter
        if _bge_just("mouse", ev.LEFTMOUSE):
            return True
        if _bge_just("keyboard", ev.SPACEKEY):
            return True
        if _bge_just("keyboard", ev.ENTERKEY):
            return True
        return False

    def _is_rollback_pressed(self) -> bool:
        if not HAS_BGE:
            return False
        try:
            import bge as _bge_imp
            return _bge_just("mouse", _bge_imp.events.WHEELUPMOUSE)
        except Exception:
            return False

    def _is_rollforward_pressed(self) -> bool:
        if not HAS_BGE:
            return False
        try:
            import bge as _bge_imp
            return _bge_just("mouse", _bge_imp.events.WHEELDOWNMOUSE)
        except Exception:
            return False

    def choose(self, index: int):
        """Called from UI when player picks a menu choice."""
        if self._current_event and self._current_event.get("type") == "menu":
            self._advance(send_value=index)
        else:
            raise RuntimeError("no menu to choose from")

    def rollback(self, steps: int = 1):
        """Rollback N steps (M08). Stores forward history for roll-forward."""
        if not self.interp or not self.interp.rollback_stack:
            return
        for _ in range(steps):
            if not self.interp.rollback_stack:
                break
            # save current state + labels for forward
            self._forward_stack.append(self.state.snapshot())
            self._forward_labels_stack.append(copy.deepcopy(self.interp.labels))
            if len(self._forward_stack) > 100:
                self._forward_stack.pop(0)
                self._forward_labels_stack.pop(0)
            snap = self.interp.rollback_stack.pop()
            lab = self.interp.rollback_labels_stack.pop() if hasattr(self.interp, "rollback_labels_stack") and self.interp.rollback_labels_stack else None
            self.state.restore(snap)
            if lab is not None:
                self.interp.labels = lab
        # reinitialize generator at restored point (keep restored labels)
        # we must not deepcopy labels again; use current interp.labels directly
        # create a fresh generator that will continue from restored state without losing spliced structure
        # To keep restored labels, we temporarily override interpreter's labels deepcopy behavior:
        # Use current labels as base, not original script copy.
        # So we create a new interpreter-like gen but keep labels
        # Instead we just run with current interpreter's labels (already restored)
        # We need to ensure run() doesn't deepcopy again — it does deepcopy on init, but here we reuse existing interp
        # So we patch: set labels directly and make _gen
        self._gen = self.interp.run()
        # restore labels after run() deepcopy would have overwritten? run() uses self.labels deepcopy from script, but we just restored self.interp.labels
        # run() deepcopy is only in __init__, not in run(), so run() will use current self.labels as is (good)
        self._current_event = None
        self._advance()

    def roll_forward(self, steps: int = 1):
        """Redo after rollback (M08)."""
        if not self._forward_stack:
            return
        for _ in range(steps):
            if not self._forward_stack:
                break
            snap = self._forward_stack.pop()
            lab = self._forward_labels_stack.pop() if self._forward_labels_stack else None
            # push current onto rollback so you can rollback again
            if self.interp:
                self.interp.rollback_stack.append(self.state.snapshot())
                if hasattr(self.interp, "rollback_labels_stack"):
                    self.interp.rollback_labels_stack.append(copy.deepcopy(self.interp.labels))
            self.state.restore(snap)
            if lab is not None and self.interp:
                self.interp.labels = lab
        self._gen = self.interp.run()
        self._current_event = None
        self._advance()

    def toggle_skip(self):
        self.state.skip = not self.state.skip
        return self.state.skip

    def toggle_auto(self):
        self.state.auto = not self.state.auto
        self._auto_timer = 0.0
        return self.state.auto

    # ---------------------------- headless convenience
    def run_headless(self, choices: List[int] | None = None):
        # Headless should start from a clean state, not the pre-advanced
        # state left by load()'s _advance() which pollutes history.
        # Create a fresh VNState + VNInterpreter from same script_dict.
        if self.script_dict is None:
            # need to load scripts first (without keeping the advanced state)
            self.load()
            # Now discard the advanced state: recreate fresh
            # Save script_dict, reset state and interpreter
            script_dict = self.script_dict
            self.state = VNState()
            # Preserve script_hash if we computed it
            # Recompute hash if needed (load already set it before, but we reset)
            # We keep it on fresh state if needed; not critical for headless.
            self.interp = VNInterpreter(script_dict, self.state)
            self.script_dict = script_dict
            # Reset UPBGE managers' reference to new state (or just ignore for headless)
            self._gen = self.interp.run()
            self._current_event = None
            self._waiting = False
        else:
            # script_dict already available but self.state may be polluted
            # If _current_event was already set (load called), reset fresh
            if self._current_event is not None:
                script_dict = self.script_dict
                self.state = VNState()
                self.interp = VNInterpreter(script_dict, self.state)
                self._gen = self.interp.run()
                self._current_event = None
                self._waiting = False

        # handle script_dict case where interp not yet created (direct script_dict init)
        if self.interp is None and self.script_dict is not None:
            import copy as _copy2
            self.interp = VNInterpreter(_copy2.deepcopy(self.script_dict), self.state)
            self._gen = self.interp.run()
            self._current_event = None
            self._waiting = False
        assert self.interp is not None
        # Ensure fresh interpreter — create one more fresh to avoid mutation from previous run_headless splicing
        # VNInterpreter splices labels (menu/if); so reuse of same interpreter across multiple run_headless calls would double-splice.
        # Therefore create a clone of script_dict for each run.
        import copy as _copy
        fresh_script = _copy.deepcopy(self.script_dict)
        fresh_state = VNState()
        fresh_state.script_hash = self.state.script_hash
        fresh_interp = VNInterpreter(fresh_script, fresh_state)
        self.interp = fresh_interp
        self.state = fresh_state
        # also rebind managers if they exist
        try:
            if self.scene_mgr: self.scene_mgr.state = fresh_state
            if self.sprite_mgr: self.sprite_mgr.state = fresh_state
            if self.stage_mgr: self.stage_mgr.state = fresh_state
            if self.ui_mgr: self.ui_mgr.state = fresh_state
            if self.audio_mgr: self.audio_mgr.state = fresh_state
            if self.screen_mgr:
                self.screen_mgr.state = fresh_state
                # re-create save_manager for new state
                from ..save.save_manager import SaveManager
                try:
                    self.screen_mgr.save_manager = SaveManager(fresh_state)
                    for scr in self.screen_mgr.screens.values():
                        if hasattr(scr, 'save_manager'):
                            scr.save_manager = self.screen_mgr.save_manager
                            scr.state = fresh_state
                        else:
                            scr.state = fresh_state
                except: pass
        except Exception:
            pass
        return fresh_interp.run_headless(choices=choices or [])

    @property
    def current_event(self):
        return self._current_event
