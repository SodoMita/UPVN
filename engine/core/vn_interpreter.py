"""
UPVN — Interpreter (coroutine-based)

Ren'Py's magic is that script blocks on user input ("wait for click before
next line"). In UPBGE's frame-based loop we use a Python generator:
each `step()` yields an *event* that the frontend renders, then waits
until the event reports "done" (click, choice, transition finished, etc.).

Headless traces: the interpreter can run without UPBGE via `run_headless()`
which emits a trace list like:
  SAY eileen "Hello"
  SHOW eileen happy center
  MENU ["Ask", "Leave"] -> 0
  JUMP engine_talk

This makes agent verification possible with pytest alone (80% of engine
is verifiable without rendering).

Safety: assignment expressions are evaluated in a restricted environment
(no imports, no file I/O). Only variables dict is exposed.
"""
from __future__ import annotations
import re
import copy
from typing import Any, Dict, List, Optional, Generator, Tuple

from .vn_state import VNState, CharacterDef
from .vn_errors import ScriptRuntimeError, LabelNotFoundError


# ------------------------------------------------------------------ safe eval
def safe_eval(expr: str, variables: dict):
    """
    Evaluate a Python expression with only variables + safe builtins.
    No __import__, no open, no exec.
    """
    # whitelist of builtins / functions we allow in if conditions
    allowed_builtins = {
        "True": True, "False": False, "None": None,
        "len": len, "int": int, "float": float, "str": str, "bool": bool,
        "abs": abs, "min": min, "max": max,
    }
    # variables shadow builtins
    env = {**allowed_builtins, **variables}
    try:
        # empty globals, env as locals
        return eval(expr, {"__builtins__": {}}, env)
    except Exception as e:
        raise ScriptRuntimeError(f"expression error: {expr!r} -> {e}")


def safe_exec_assign(target: str, op: str, expr: str, variables: dict):
    val = safe_eval(expr, variables)
    old = variables.get(target, 0 if op in ("+=", "-=", "*=", "/=") else None)
    if op == "=":
        variables[target] = val
    elif op == "+=":
        variables[target] = (old or 0) + val
    elif op == "-=":
        variables[target] = (old or 0) - val
    elif op == "*=":
        variables[target] = (old or 0) * val
    elif op == "/=":
        variables[target] = (old or 0) / val
    else:
        raise ScriptRuntimeError(f"unknown assign op {op!r}")


# ------------------------------------------------------------------ text substitution
_var_pat = re.compile(r"\[(\w+)\]")  # Ren'Py [variable] interpolation

def interpolate(text: str, variables: dict) -> str:
    def repl(m):
        key = m.group(1)
        return str(variables.get(key, f"[{key}]"))
    return _var_pat.sub(repl, text)


# tags like {b}, {/b}, {color=#fff} — we strip for trace but keep raw
_tag_pat = re.compile(r"\{/?[^}]+\}")

def strip_tags(text: str) -> str:
    return _tag_pat.sub("", text)


# ------------------------------------------------------------------ interpreter
class VNInterpreter:
    """
    Frame-friendly interpreter. Use like:

        interp = VNInterpreter(script_dict, state)
        for event in interp.run():
            # event is dict with {"type": ...}
            # if event["wait"]: wait for player input, then send response via `interp.send(choice)`
            # otherwise auto-continue

    For headless testing, use `run_headless(choices=[0,1,...])` which auto-picks menu choices.
    """

    def __init__(self, script: dict, state: Optional[VNState] = None):
        # script is parser output: {"labels": {...}, "characters": {...}, "defaults": {...}}
        self.script = script
        # Deep-copy labels so splicing (menu/if) doesn't mutate the original
        # script dict — allows reusing the same parsed dict across tests.
        import copy as _copy
        self.labels: Dict[str, List[dict]] = _copy.deepcopy(script.get("labels", {}))
        self.state = state or VNState()
        # initialise defaults + character defs from script if state empty
        if not self.state.variables and script.get("defaults"):
            self.state.variables.update(copy.deepcopy(script["defaults"]))
        if not self.state.characters and script.get("characters"):
            for cid, cdata in script["characters"].items():
                self.state.characters[cid] = CharacterDef(id=cid, **cdata)

        # execution pointer stack for call/return
        self._call_stack: List[Tuple[str, int]] = []  # (label, next_index)
        # history for rollback-lite (snapshots at interactions)
        self.rollback_stack: List[dict] = []
        self.rollback_labels_stack: List[Dict[str, List[dict]]] = []  # parallel for label splices (M08)
        self.trace: List[dict] = []  # full event trace for testing

        # internal generator
        self._gen: Optional[Generator] = None
        self._pending_menu: Optional[dict] = None  # last menu event awaiting choice

    # ------------------------ headless helpers
    def run_headless(self, choices: Optional[List[int]] = None, max_steps: int = 10000) -> List[dict]:
        """
        Run to completion headlessly, auto-choosing menu options in order.
        Returns trace list.
        """
        choices = choices or []
        choice_ptr = 0
        gen = self.run()
        trace = []
        try:
            event = next(gen)
            while True:
                trace.append(event)
                if event.get("type") == "menu" and event.get("wait"):
                    if choice_ptr >= len(choices):
                        # default to first choice
                        pick = 0
                    else:
                        pick = choices[choice_ptr]
                        choice_ptr += 1
                    # validate
                    opts = event.get("choices", [])
                    if pick < 0 or pick >= len(opts):
                        raise ScriptRuntimeError(f"menu choice {pick} out of range (0..{len(opts)-1})",
                                                 self.state.current_label, self.state.instruction_index)
                    event = gen.send(pick)
                elif event.get("wait"):
                    # say / pause etc. — auto-advance
                    event = gen.send(None)
                else:
                    event = next(gen)
                if len(trace) > max_steps:
                    raise ScriptRuntimeError("max_steps exceeded — possible infinite loop")
        except StopIteration as e:
            # e.value is return value if any
            if e.value:
                trace.append({"type": "return_value", "value": e.value})
        self.trace = trace
        return trace

    def run(self) -> Generator[dict, Any, Any]:
        """
        Main coroutine. Yields events; caller sends back choice index for menu.
        """
        self.state.current_label = self.state.current_label or "start"
        if self.state.current_label not in self.labels:
            raise LabelNotFoundError(f'label "{self.state.current_label}" not found', self.state.current_label)

        while True:
            label = self.state.current_label
            block = self.labels.get(label)
            if block is None:
                raise LabelNotFoundError(f'label "{label}" not found', label)

            idx = self.state.instruction_index
            if idx >= len(block):
                # fallthrough: if at end of label without return, try implicit next label? Ren'Py falls through sequentially.
                # For simplicity, we treat reaching end as return (pop call stack or finish).
                if self._call_stack:
                    ret_label, ret_idx = self._call_stack.pop()
                    self.state.current_label = ret_label
                    self.state.instruction_index = ret_idx
                    continue
                else:
                    yield {"type": "end", "label": label}
                    return

            node = block[idx]
            # snapshot before interaction points (say/menu) for rollback-lite (M08)
            if node.get("cmd") in ("say", "menu"):
                self.rollback_stack.append(self.state.snapshot())
                self.rollback_labels_stack.append(copy.deepcopy(self.labels))
                if len(self.rollback_stack) > 100:
                    self.rollback_stack.pop(0)
                    self.rollback_labels_stack.pop(0)

            event = self._execute_node(node)
            # event may be None (non-blocking) -> advance and loop
            # or event with wait=True -> yield and handle response
            if event is None:
                self.state.instruction_index += 1
                continue

            # record history / backlog (M07) — preserve styled raw, interpolate [var], keep tags
            if event.get("type") == "say":
                # raw is original script text before interpolation (with [var] and {b})
                raw = event.get("raw", event.get("text", ""))
                text = event.get("text", "")  # interpolated, still with tags
                display = event.get("display_text", text)
                # also compute stripped version for accessibility
                stripped = strip_tags(text)
                self.state.history.append({
                    "who": event.get("who"),
                    "who_name": event.get("who_name"),
                    "raw": raw,
                    "text": text,  # styled, tags preserved
                    "display_text": display,
                    "stripped": stripped,
                    "label": label,
                    "index": idx,
                })
                # for skip: track seen text hashes (only skip seen)
                h = f"{label}:{idx}:{stripped}"
                if h not in self.state.seen_history:
                    self.state.seen_history.append(h)

            self.trace.append(event)

            # Jumps / calls / returns have already mutated state inside _execute_node
            # They should NOT auto-increment; just yield and continue
            if event.get("type") in ("jump", "call"):
                yield event
                # don't increment — state already points to next location
                continue
            if event.get("type") == "return":
                yield event
                if event.get("to") is None:
                    # top-level return — terminate (next loop would infinite-loop otherwise)
                    # advance pointer beyond block to trigger end handling
                    label_block = self.labels.get(label, [])
                    self.state.instruction_index = len(label_block)
                    # next iteration will yield end
                    continue
                # called return already popped stack and set pointer
                continue

            if event.get("wait"):
                # yield and wait for input
                response = yield event
                # handle menu choice
                if event["type"] == "menu":
                    choice_idx = response
                    if choice_idx is None:
                        raise ScriptRuntimeError("menu requires a choice index", label, idx)
                    choice = event["choices"][choice_idx]
                    resume_label = label
                    resume_index = idx + 1
                    jumped = self._execute_choice_block(choice.get("block", []), resume_label, resume_index)
                    if not jumped:
                        self.state.current_label = resume_label
                        self.state.instruction_index = resume_index
                    continue
                else:
                    # say / pause etc.
                    self.state.instruction_index += 1
                    continue
            else:
                # non-waiting event — auto-advance
                self.state.instruction_index += 1
                yield event
                # loop continues

    # ------------------------ per-node execution
    def _execute_node(self, node: dict) -> Optional[dict]:
        cmd = node.get("cmd")
        loc = node.get("_loc")

        if cmd == "say":
            who = node.get("who")
            text_raw = node.get("text", "")
            # interpolation [var]
            text = interpolate(text_raw, self.state.variables)
            # tags handling — keep raw for display, stripped for accessible
            display = text  # keep tags for frontend to render rich text
            who_name = self.state.get_character_name(who) if who else None
            # color for dialogue box? from character def
            color = None
            if who and who in self.state.characters:
                color = self.state.characters[who].color
            return {
                "type": "say",
                "who": who,
                "who_name": who_name,
                "color": color,
                "text": text,
                "display_text": display,
                "raw": text_raw,
                "wait": True,
                "_loc": loc,
            }

        elif cmd == "scene":
            asset = node.get("asset")
            trans = node.get("transition")
            # handle `scene black` etc.
            self.state.scene.background = asset
            self.state.scene.transition = trans
            self.state.shown_actors.clear()  # scene clears actors like Ren'Py
            return {"type": "scene", "asset": asset, "transition": trans, "wait": False, "_loc": loc}

        elif cmd == "show":
            asset = node.get("asset")
            tag = node.get("tag")
            pos = node.get("position") or "center"
            trans = node.get("transition")
            # M10 ATL-lite: move/ease transitions interpolate rather than snap
            move_easings = {"move","ease","easein","easeout","easeinout","linear"}
            from .vn_state import ShownActor
            import time as _t
            if trans in move_easings:
                # need previous position for this tag
                prev = self.state.shown_actors.get(tag)
                from_pos = prev.position if prev else pos
                # duration default 0.5, easing = trans unless move->ease
                ease = trans if trans != "move" else "ease"
                # create actor with move state, but keep position as target for final, and store from/to for interpolation
                actor = ShownActor(tag=tag, asset=asset, position=pos, transition=trans,
                                   move_from=from_pos, move_to=pos, move_t0=_t.time(),
                                   move_duration=0.5, move_easing=ease)
                self.state.shown_actors[tag] = actor
                return {"type": "show", "asset": asset, "tag": tag, "position": pos, "transition": trans,
                        "from_pos": from_pos, "to_pos": pos, "duration": 0.5, "easing": ease, "wait": False, "_loc": loc}
            else:
                # expression replacement: if same tag already shown, replace asset
                from .vn_state import ShownActor
                self.state.shown_actors[tag] = ShownActor(tag=tag, asset=asset, position=pos, transition=trans)
                return {"type": "show", "asset": asset, "tag": tag, "position": pos, "transition": trans, "wait": False, "_loc": loc}

        elif cmd == "hide":
            tag = node.get("tag")
            trans = node.get("transition")
            self.state.shown_actors.pop(tag, None)
            return {"type": "hide", "tag": tag, "transition": trans, "wait": False, "_loc": loc}

        elif cmd == "with":
            trans = node.get("transition")
            # standalone with — frontend applies transition to last scene/show
            return {"type": "with", "transition": trans, "wait": False, "_loc": loc}

        elif cmd == "play_music":
            asset, fadein = node.get("asset"), node.get("fadein")
            self.state.audio.music = asset
            return {"type": "play_music", "asset": asset, "fadein": fadein, "wait": False, "_loc": loc}

        elif cmd == "stop_music":
            fadeout = node.get("fadeout")
            self.state.audio.music = None
            return {"type": "stop_music", "fadeout": fadeout, "wait": False, "_loc": loc}

        elif cmd == "play_sound":
            return {"type": "play_sound", "asset": node.get("asset"), "wait": False, "_loc": loc}

        elif cmd == "play_voice":
            return {"type": "play_voice", "asset": node.get("asset"), "wait": False, "_loc": loc}

        elif cmd == "pause":
            return {"type": "pause", "duration": node.get("duration"), "wait": True, "_loc": loc}

        elif cmd == "jump":
            label = node.get("label")
            if label not in self.labels:
                raise LabelNotFoundError(f'jump target "{label}" does not exist', self.state.current_label, self.state.instruction_index)
            self.state.current_label = label
            self.state.instruction_index = 0
            # jump is non-wait but we need to avoid auto-increment; signal via special event then caller will not increment
            # We'll return an event and let run() handle pointer reset; indicate jumped
            # Return a trace event for testing goldens
            return {"type": "jump", "label": label, "wait": False, "_loc": loc}

        elif cmd == "call":
            label = node.get("label")
            if label not in self.labels:
                raise LabelNotFoundError(f'call target "{label}" does not exist', self.state.current_label, self.state.instruction_index)
            # push return address
            self._call_stack.append((self.state.current_label, self.state.instruction_index + 1))
            self.state.current_label = label
            self.state.instruction_index = 0
            return {"type": "call", "label": label, "wait": False, "_loc": loc}

        elif cmd == "return":
            if self._call_stack:
                ret_label, ret_idx = self._call_stack.pop()
                self.state.current_label = ret_label
                self.state.instruction_index = ret_idx
                return {"type": "return", "to": ret_label, "wait": False, "_loc": loc}
            else:
                # top-level return ends game
                return {"type": "return", "to": None, "wait": False, "_loc": loc}

        elif cmd == "assign":
            target, op, expr = node.get("target"), node.get("op"), node.get("expr")
            safe_exec_assign(target, op, expr, self.state.variables)
            return {"type": "assign", "target": target, "op": op, "expr": expr, "value": self.state.variables[target], "wait": False, "_loc": loc}

        elif cmd == "if":
            branches = node.get("branches", [])
            chosen = None
            for br in branches:
                cond = br.get("cond")
                if cond is None:
                    chosen = br  # else
                    break
                if safe_eval(cond, self.state.variables):
                    chosen = br
                    break
            if chosen is None:
                return None  # no branch taken -> just advance
            # Execute chosen block inline similar to menu. Need to handle jumps inside.
            # If block contains only simple statements without jump, we can splice execution by executing them now and reporting events.
            # For golden traces, we need each inner statement to emit its own event. So we cannot just skip.
            # Instead, we handle `if` by *expanding* block: push remaining instructions + chosen block into a temporary queue.
            # Simpler for Tier1: we handle `if` by manually stepping chosen block via _execute_choice_block logic but without menu resume.
            # We'll create a synthetic label to hold remaining instructions after if, then jump into block.
            # Easiest: execute first instruction of block as next pointer trick — but block may have multiple nodes.
            # We'll instead inject block nodes into current label's list temporarily (insert after current idx) and continue.
            # This is a bit hacky but works for headless.
            label = self.state.current_label
            block_list = self.labels[label]
            idx = self.state.instruction_index
            insert_pos = idx + 1
            # Insert chosen block nodes at insert_pos
            # Mark them so we don't re-enter same if
            for n in reversed(chosen.get("block", [])):
                block_list.insert(insert_pos, n)
            return None  # let loop advance to first inserted node

        elif cmd == "menu":
            # Yield menu event, wait for choice. Filtering of conditional choices not yet implemented (Tier3)
            # caption is optional
            caption = node.get("caption")
            choices = [{"text": c["text"], "block": c.get("block", [])} for c in node.get("choices", [])]
            return {"type": "menu", "caption": caption, "choices": choices, "wait": True, "_loc": loc}

        # 3D stubs — record state, yield event for frontend
        elif cmd == "load_stage":
            self.state.stage = node.get("stage")
            return {"type": "load_stage", "stage": self.state.stage, "wait": False, "_loc": loc}
        elif cmd == "show3d":
            asset, marker = node.get("asset"), node.get("marker")
            self.state.stage_objects[asset] = {"marker": marker, "anim": "idle"}
            return {"type": "show3d", "asset": asset, "marker": marker, "wait": False, "_loc": loc}
        elif cmd == "anim":
            tgt, anim = node.get("target"), node.get("animation")
            if tgt in self.state.stage_objects:
                self.state.stage_objects[tgt]["anim"] = anim
            return {"type": "anim", "target": tgt, "animation": anim, "wait": False, "_loc": loc}
        elif cmd == "camera_preset":
            self.state.camera["preset"] = node.get("name")
            return {"type": "camera_preset", "name": node.get("name"), "wait": False, "_loc": loc}

        elif cmd == "camera_zoom":
            zoom = node.get("zoom")
            dur = node.get("duration", 1.0)
            ease = node.get("easing", "ease")
            # M10: store zoom interpolation in state.camera
            prev = self.state.camera.get("zoom", 1.0)
            import time as _t
            self.state.camera["zoom"] = zoom
            # need interpolation state: keep start/target/duration/easing/t0
            self.state.camera["_zoom_from"] = prev
            self.state.camera["_zoom_to"] = zoom
            self.state.camera["_zoom_dur"] = dur
            self.state.camera["_zoom_ease"] = ease
            self.state.camera["_zoom_t0"] = _t.time()
            return {"type": "camera_zoom", "zoom": zoom, "duration": dur, "easing": ease, "wait": False, "_loc": loc}

        else:
            raise ScriptRuntimeError(f"unknown command {cmd!r}", self.state.current_label, self.state.instruction_index)

    def _execute_choice_block(self, block: List[dict], resume_label: str, resume_index: int) -> bool:
        """
        Execute choice block inline by splicing its nodes after the menu.
        Returns True if we already moved the instruction pointer (so caller
        should NOT increment it again).

        The old temp-label approach emitted internal '__resume' jumps that
        polluted the golden trace. This insertion method keeps the trace
        clean: MENU -> [block events] -> resume OR jump elsewhere.
        """
        if not block:
            return False

        # Insert block nodes directly after the menu node.
        # resume_index is idx+1; after insertion the block occupies
        # [resume_index, resume_index+len(block)-1] and the original
        # resume node (if any) is shifted beyond it.
        label_block = self.labels[resume_label]
        # Defensive: ensure label_block is still the same list object
        # and idx hasn't shifted since we read it.
        for n in reversed(block):
            label_block.insert(resume_index, n)

        # Point execution to first inserted node
        self.state.current_label = resume_label
        self.state.instruction_index = resume_index
        return True


def make_script(labels: dict, characters: Optional[dict] = None, defaults: Optional[dict] = None) -> dict:
    return {"labels": labels, "characters": characters or {}, "defaults": defaults or {}}
