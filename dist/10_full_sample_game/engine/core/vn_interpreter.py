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

Tiers:
  - .urpy / .rpy safe subset: expressions go through the AST whitelist
    (expr_eval.py). No embedded Python is executed.
  - .rpy full tier (drop-in Ren'Py): `python:` blocks, `init python`,
    `while`/`break`/`continue`, `renpy.*` compat and label parameters are
    executed — this tier trusts the author, exactly like Ren'Py does.
"""
from __future__ import annotations
import re
import copy
from typing import Any, Dict, List, Optional, Generator, Tuple

from .vn_state import VNState, CharacterDef
from .vn_errors import ScriptRuntimeError, LabelNotFoundError


# ------------------------------------------------------------------ safe eval
def safe_eval(expr: str, variables: dict, extra: Optional[dict] = None, loose: bool = False):
    """
    Evaluate an expression with only variables + safe builtins.
    No attribute access (except injected objects), no comprehensions, no
    imports, no open, no exec — enforced by an AST whitelist (expr_eval.py).

    ``loose=True`` is the drop-in tier: unknown identifiers resolve to None
    instead of aborting the game (see expr_eval.ExpressionEvaluator).
    """
    from ..script.expr_eval import evaluate
    try:
        return evaluate(expr, variables, extra, loose=loose)
    except ScriptRuntimeError as e:
        raise ScriptRuntimeError(f"expression error: {expr!r} -> {e}")


# declarative type coercion for `state:`-declared variables (M15)
_TYPE_COERCERS = {
    "int": lambda v: v if (not isinstance(v, bool) and isinstance(v, int)) else None,
    "float": lambda v: float(v) if (not isinstance(v, bool) and isinstance(v, (int, float))) else None,
    "str": lambda v: v if isinstance(v, str) else None,
    "string": lambda v: v if isinstance(v, str) else None,
    "bool": lambda v: v if isinstance(v, bool) else None,
    "list": lambda v: v if isinstance(v, list) else None,
}


def _coerce_declared(target: str, value, type_name: str):
    """Validate/coerce a value against a declared type. Raises on mismatch."""
    if type_name not in _TYPE_COERCERS:
        return value  # unknown type name — leave as-is
    out = _TYPE_COERCERS[type_name](value)
    if out is None:
        raise ScriptRuntimeError(
            f"type error: {target!r} is declared {type_name}, "
            f"but got {type(value).__name__} ({value!r})"
        )
    return out


def safe_exec_assign(target: str, op: str, expr: str, variables: dict,
                     declared_types: dict | None = None, extra: Optional[dict] = None,
                     loose: bool = False):
    val = safe_eval(expr, variables, extra, loose=loose)
    old = variables.get(target, 0 if op in ("+=", "-=", "*=", "/=") else None)
    if op == "=":
        new = val
    elif op == "+=":
        new = (old or 0) + val
    elif op == "-=":
        new = (old or 0) - val
    elif op == "*=":
        new = (old or 0) * val
    elif op == "/=":
        new = (old or 0) / val
    else:
        raise ScriptRuntimeError(f"unknown assign op {op!r}")
    if declared_types and target in declared_types:
        new = _coerce_declared(target, new, declared_types[target])
    variables[target] = new


def _is_state_value(v) -> bool:
    """True if a value is JSON-save-friendly (so python blocks don't leak objects)."""
    if v is None or isinstance(v, (bool, int, float, str)):
        return True
    if isinstance(v, (list, tuple, set)):
        return all(_is_state_value(x) for x in v)
    if isinstance(v, dict):
        return all(_is_state_value(k) and _is_state_value(x) for k, x in v.items())
    return False


# ------------------------------------------------------------------ text substitution
_bracket_pat = re.compile(r"\[([^\]\[]+)\]")  # Ren'Py [expr] interpolation

def interpolate(text: str, variables: dict, extra: Optional[dict] = None) -> str:
    """Interpolate ``[expr]`` brackets in dialogue text.

    Simple names resolve from ``variables``; anything else is evaluated with
    the same AST whitelist as story expressions (so ``[gold * 2]`` works, and
    in full mode ``[store.gold]`` / ``[renpy.loadable(...)]`` too). Unresolvable
    or invalid expressions are left verbatim (never crash the line).
    """
    def repl(m):
        expr = m.group(1).strip()
        if not expr:
            return m.group(0)
        if re.fullmatch(r"\w+", expr):
            return str(variables.get(expr, f"[{expr}]"))
        try:
            from ..script.expr_eval import evaluate
            val = evaluate(expr, variables, extra)
            return str(val)
        except Exception:
            return m.group(0)
    return _bracket_pat.sub(repl, text)


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

    def __init__(self, script: dict, state: Optional[VNState] = None, base_dir: Optional[str] = None,
                 compat: bool = False):
        # script is parser output: {"labels": {...}, "characters": {...}, "defaults": {...}, ...}
        self.script = script
        # Deep-copy labels so splicing (menu/if/while) doesn't mutate the original
        # script dict — allows reusing the same parsed dict across tests.
        import copy as _copy
        self.labels: Dict[str, List[dict]] = _copy.deepcopy(script.get("labels", {}))
        # pristine label templates — used to reset a label's block when it is
        # re-entered from the top, so spliced while/if/menu nodes from a previous
        # execution never accumulate (re-entry would otherwise re-run them).
        self._pristine_labels: Dict[str, List[dict]] = _copy.deepcopy(script.get("labels", {}))
        self.state = state or VNState()
        self.base_dir = base_dir
        # initialise defaults + character defs from script if state empty
        if not self.state.variables and script.get("defaults"):
            self.state.variables.update(copy.deepcopy(script["defaults"]))
        if not self.state.characters and script.get("characters"):
            for cid, cdata in script["characters"].items():
                self.state.characters[cid] = CharacterDef(id=cid, **cdata)
        # declarative declarations are always applied (they are schema, not state)
        if script.get("types"):
            self.state.declared_types.update(copy.deepcopy(script["types"]))
        if script.get("assets"):
            for kind in ("images", "audio", "stages"):
                if kind in script["assets"]:
                    self.state.assets.setdefault(kind, {}).update(copy.deepcopy(script["assets"][kind]))

        # full-tier metadata
        self.full: bool = bool(script.get("full"))
        # compat (drop-in) mode: python: failures are collected, not fatal —
        # a real game may need engine APIs or third-party modules UPVN lacks,
        # and we would rather keep running the story than abort at init.
        self.compat: bool = compat
        self.init_errors: List[str] = []
        self.python_errors: List[str] = []
        self.defines: Dict[str, Any] = copy.deepcopy(script.get("defines", {}))
        self.label_params: Dict[str, List[dict]] = copy.deepcopy(script.get("label_params", {}))
        self.transforms: Dict[str, dict] = copy.deepcopy(script.get("transforms", {}))
        self.screens: Dict[str, dict] = copy.deepcopy(script.get("screens", {}))
        self.styles: Dict[str, dict] = copy.deepcopy(script.get("styles", {}))
        self.translations: Dict[str, dict] = copy.deepcopy(script.get("translations", {}))

        # renpy compatibility namespace (full tier only)
        from ..script.renpy_compat import RenpyRuntime, RenpyCompat, StoreWrapper
        self._renpy_runtime = RenpyRuntime(self)
        # `define gui.x = …` / `define config.y = …` create store namespaces
        self.namespaces = self._build_namespaces()
        self._expr_extra = {
            "renpy": RenpyCompat(self._renpy_runtime, base_dir=base_dir,
                                 permissive=self.full),
            "store": StoreWrapper(self.state.variables),
        }
        if self.full:
            # Ren'Py's translation helper: no catalogue in UPVN, identity output
            from ..script.renpy_compat import identity_translation
            self._expr_extra["_"] = identity_translation
            self._expr_extra["_p"] = identity_translation
        self._expr_extra.update(self.namespaces)

        # execution pointer stack for call/return
        # each entry: (label, next_index, param_saves) where param_saves is
        # a list of (name, existed_before, old_value) to restore on return.
        self._call_stack: List[Tuple[str, int, Optional[list]]] = []
        # history for rollback-lite (snapshots at interactions)
        self.rollback_stack: List[dict] = []
        self.rollback_labels_stack: List[Dict[str, List[dict]]] = []  # parallel for label splices (M08)
        self.trace: List[dict] = []  # full event trace for testing

        # internal generator
        self._gen: Optional[Generator] = None
        self._pending_menu: Optional[dict] = None  # last menu event awaiting choice

        # init-time python (full tier): executes before the first label
        if self.full and script.get("init_python"):
            self._run_init_python(script["init_python"])

    def _build_namespaces(self) -> dict:
        """Turn dotted defines into namespace objects (``gui``, ``config``, …).

        ``define gui.accent_color = "#002ead"`` becomes an attribute on a
        ``gui`` object that ``python:`` blocks and expressions can read, the
        way Ren'Py's store does. Nested paths (``a.b.c``) build nested objects.
        """
        from ..script.renpy_compat import StoreNamespace

        def values_of(ns: StoreNamespace) -> dict:
            return object.__getattribute__(ns, "_values")

        roots: Dict[str, StoreNamespace] = {}
        for key, value in self.defines.items():
            if "." not in key:
                continue
            parts = key.split(".")
            ns = roots.get(parts[0])
            if ns is None:
                ns = StoreNamespace(parts[0], permissive=self.full)
                roots[parts[0]] = ns
            for part in parts[1:-1]:
                inner = values_of(ns).get(part)
                if not isinstance(inner, StoreNamespace):
                    inner = StoreNamespace(part, permissive=self.full)
                    values_of(ns)[part] = inner
                ns = inner
            values_of(ns)[parts[-1]] = value
        return roots

    # ------------------------ init-time python (full tier)
    def _run_init_python(self, code_lines: List[str]):
        env = self._python_env()
        for line in code_lines:
            try:
                exec(line, env)
            except Exception as e:
                first = (line or "").strip().splitlines()[0] if line else ""
                msg = f"init python error: {e}\n  in: {first[:120]}"
                if self.compat:
                    self.init_errors.append(msg)
                    continue
                raise ScriptRuntimeError(msg)
        self._sync_variables(env)
        self._renpy_runtime.store_dict = None

    def _python_env(self) -> dict:
        import builtins
        from ..script.renpy_compat import StoreWrapper, identity_translation
        if self.compat:
            from ..script.renpy_compat import PermissiveEnv
            env: dict = PermissiveEnv({"__builtins__": builtins.__dict__})
        else:
            env = {"__builtins__": builtins.__dict__}
        env["_"] = identity_translation
        env["_p"] = identity_translation
        # plain defines become store names; dotted ones live on their namespace
        env.update({k: v for k, v in self.defines.items() if "." not in k})
        env.update(self.namespaces)
        env.update(self.state.variables)
        env["renpy"] = self._expr_extra["renpy"]
        # `store` wraps the SAME namespace dict, so `store.x = ...` and bare
        # `x = ...` stay consistent (no stale-copy overwrite when syncing back).
        env["store"] = StoreWrapper(env)
        self._renpy_runtime.store_dict = env
        return env

    def _sync_variables(self, env: dict):
        """Copy python-block results back into the saveable variables dict."""
        skip = {"__builtins__", "renpy", "store"}
        skip.update(self.defines.keys())
        skip.update(getattr(self, "namespaces", {}).keys())
        before = set(self.state.variables.keys())
        for k, v in env.items():
            if k.startswith("_") or k in skip:
                continue
            if k in before or _is_state_value(v):
                self.state.variables[k] = v

    def _eval_expr(self, expr: str):
        extra = self._expr_extra if self.full else None
        # the drop-in tier forgives unknown identifiers (real games reference
        # store variables/classes UPVN does not model); the safe subset does not
        return safe_eval(expr, self.state.variables, extra, loose=self.full)

    def _enter_label(self, label: str, index: int = 0):
        """Set the execution pointer to a label.

        Entering from the top (index 0) resets the block to its pristine
        template, discarding any nodes spliced in by a previous pass over the
        label (while/if/menu bodies). Resuming mid-label (index > 0) keeps the
        spliced structure intact.
        """
        if index == 0:
            self.labels[label] = copy.deepcopy(self._pristine_labels.get(label, []))
        self.state.current_label = label
        self.state.instruction_index = index

    # ------------------------ label parameter binding (full tier)
    def _bind_label_params(self, label: str, provided: dict) -> Optional[list]:
        """Bind label parameters into variables. Returns undo info (or None)."""
        params = self.label_params.get(label)
        if not params:
            return None
        saves = []
        for p in params:
            name = p["name"]
            if name in provided:
                value = provided[name]
            elif p.get("default") is not None:
                value = self._eval_expr(p["default"])
            else:
                value = None
            saves.append((name, name in self.state.variables, self.state.variables.get(name)))
            self.state.variables[name] = value
        return saves

    def _restore_params(self, saves: Optional[list]):
        if not saves:
            return
        for name, existed, old in reversed(saves):
            if existed:
                self.state.variables[name] = old
            else:
                self.state.variables.pop(name, None)

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
                    # say / pause / call_screen etc. — auto-advance
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
                # fallthrough: reaching end of label = return (pop call stack or finish)
                if self._call_stack:
                    ret_label, ret_idx, saves = self._call_stack.pop()
                    self._restore_params(saves)
                    self._enter_label(ret_label, ret_idx)
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

            # Jumps / calls / returns / break / continue have already mutated
            # state inside _execute_node — do NOT auto-increment.
            if event.get("type") in ("jump", "call", "break", "continue"):
                yield event
                continue
            if event.get("type") == "return":
                yield event
                if event.get("to") is None:
                    # top-level return — terminate
                    label_block = self.labels.get(label, [])
                    self.state.instruction_index = len(label_block)
                    continue
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
                    # say / pause / call_screen etc.
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
            # interpolation [var] / [expr]
            text = interpolate(text_raw, self.state.variables, self._expr_extra if self.full else None)
            display = text  # keep tags for frontend to render rich text
            who_name = self.state.get_character_name(who) if who else None
            color = None
            if who and who in self.state.characters:
                color = self.state.characters[who].color
            event = {
                "type": "say",
                "who": who,
                "who_name": who_name,
                "color": color,
                "text": text,
                "display_text": display,
                "raw": text_raw,
                "wait": not node.get("nointeract"),
                "_loc": loc,
            }
            if node.get("expression"):
                event["expression"] = node["expression"]
            if node.get("voice_attr"):
                event["voice_attr"] = node["voice_attr"]
            if node.get("centered"):
                event["centered"] = node["centered"]
            if node.get("extend"):
                event["extend"] = True
            return event

        elif cmd == "scene":
            asset = node.get("asset")
            trans = node.get("transition")
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
            move_easings = {"move", "ease", "easein", "easeout", "easeinout", "linear"}
            from .vn_state import ShownActor
            import time as _t
            if trans in move_easings:
                prev = self.state.shown_actors.get(tag)
                from_pos = prev.position if prev else pos
                ease = trans if trans != "move" else "ease"
                actor = ShownActor(tag=tag, asset=asset, position=pos, transition=trans,
                                   move_from=from_pos, move_to=pos, move_t0=_t.time(),
                                   move_duration=0.5, move_easing=ease)
                self.state.shown_actors[tag] = actor
                return {"type": "show", "asset": asset, "tag": tag, "position": pos, "transition": trans,
                        "from_pos": from_pos, "to_pos": pos, "duration": 0.5, "easing": ease, "wait": False, "_loc": loc}
            else:
                self.state.shown_actors[tag] = ShownActor(tag=tag, asset=asset, position=pos, transition=trans)
                return {"type": "show", "asset": asset, "tag": tag, "position": pos, "transition": trans, "wait": False, "_loc": loc}

        elif cmd == "hide":
            tag = node.get("tag")
            trans = node.get("transition")
            self.state.shown_actors.pop(tag, None)
            return {"type": "hide", "tag": tag, "transition": trans, "wait": False, "_loc": loc}

        elif cmd == "with":
            trans = node.get("transition")
            return {"type": "with", "transition": trans, "wait": False, "_loc": loc}

        elif cmd == "play_music":
            asset, fadein = node.get("asset"), node.get("fadein")
            self.state.audio.music = asset
            return {"type": "play_music", "asset": asset, "fadein": fadein, "wait": False, "_loc": loc}

        elif cmd == "stop_music":
            fadeout = node.get("fadeout")
            self.state.audio.music = None
            return {"type": "stop_music", "fadeout": fadeout, "wait": False, "_loc": loc}

        elif cmd in ("play_sound", "play_audio"):
            self.state.audio.sound = node.get("asset")
            return {"type": "play_sound", "asset": node.get("asset"), "wait": False, "_loc": loc}

        elif cmd in ("stop_sound", "stop_voice", "stop_audio"):
            channel = cmd.split("_", 1)[1]
            if channel == "audio":
                channel = "sound"
            setattr(self.state.audio, channel, None)
            return {"type": cmd, "fadeout": node.get("fadeout"), "wait": False, "_loc": loc}

        elif cmd == "play_voice":
            return {"type": "play_voice", "asset": node.get("asset"), "wait": False, "_loc": loc}

        elif cmd == "pause":
            dur = node.get("duration")
            if isinstance(dur, str):        # `pause delay` — evaluated at runtime
                try:
                    dur = self._eval_expr(dur)
                except ScriptRuntimeError:
                    dur = None
            return {"type": "pause", "duration": dur, "wait": True, "_loc": loc}

        elif cmd == "jump":
            label = node.get("label")
            if label is None and node.get("expr"):
                label = str(self._eval_expr(node["expr"]))
            if label not in self.labels:
                raise LabelNotFoundError(f'jump target "{label}" does not exist', self.state.current_label, self.state.instruction_index)
            self._bind_label_params(label, {})
            self._enter_label(label)
            return {"type": "jump", "label": label, "wait": False, "_loc": loc}

        elif cmd == "call":
            label = node.get("label")
            if label is None and node.get("expr"):
                label = str(self._eval_expr(node["expr"]))
            if label not in self.labels:
                raise LabelNotFoundError(f'call target "{label}" does not exist', self.state.current_label, self.state.instruction_index)
            provided: dict = {}
            args = node.get("args")
            if args:
                params = self.label_params.get(label, [])
                for i, arg_expr in enumerate(args):
                    if i < len(params):
                        provided[params[i]["name"]] = self._eval_expr(arg_expr)
            saves = self._bind_label_params(label, provided)
            # push return address + param undo info
            self._call_stack.append((self.state.current_label, self.state.instruction_index + 1, saves))
            self._enter_label(label)
            return {"type": "call", "label": label, "wait": False, "_loc": loc}

        elif cmd == "return":
            if self._call_stack:
                ret_label, ret_idx, saves = self._call_stack.pop()
                self._restore_params(saves)
                self._enter_label(ret_label, ret_idx)
                return {"type": "return", "to": ret_label, "wait": False, "_loc": loc}
            else:
                # top-level return ends game
                return {"type": "return", "to": None, "wait": False, "_loc": loc}

        elif cmd == "assign":
            target, op, expr = node.get("target"), node.get("op"), node.get("expr")
            safe_exec_assign(target, op, expr, self.state.variables, self.state.declared_types,
                             self._expr_extra if self.full else None, loose=self.full)
            return {"type": "assign", "target": target, "op": op, "expr": expr, "value": self.state.variables[target], "wait": False, "_loc": loc}

        elif cmd == "if":
            branches = node.get("branches", [])
            chosen = None
            for br in branches:
                cond = br.get("cond")
                if cond is None:
                    chosen = br  # else
                    break
                if self._eval_expr(cond):
                    chosen = br
                    break
            if chosen is None:
                return None  # no branch taken -> just advance
            label = self.state.current_label
            block_list = self.labels[label]
            idx = self.state.instruction_index
            insert_pos = idx + 1
            for n in reversed(chosen.get("block", [])):
                block_list.insert(insert_pos, n)
            return None  # let loop advance to first inserted node

        elif cmd == "menu":
            if node.get("pre") and not node.get("_pre_done"):
                # splice `set`/`$`/say statements in front of the menu, then
                # re-insert the menu itself so it runs once afterwards
                node["_pre_done"] = True
                block_list = self.labels[self.state.current_label]
                at = self.state.instruction_index
                for n in reversed(list(node["pre"]) + [node]):
                    block_list.insert(at + 1, n)
                return None
            caption = node.get("caption")
            # filter conditional choices ("Text" if cond:)
            kept = []
            for c in node.get("choices", []):
                cond = c.get("cond")
                if cond is not None and not self._eval_expr(cond):
                    continue
                kept.append(c)
            # stable per-event choice ids so editor-built UI can bind hover/click
            # (object "choice_0" -> controller.choose(0), etc.)
            choices = [
                {"text": c["text"], "block": c.get("block", []), "id": i}
                for i, c in enumerate(kept)
            ]
            return {"type": "menu", "caption": caption, "choices": choices, "wait": True, "_loc": loc}

        # ---- full-tier flow constructs
        elif cmd == "python":
            code = node.get("code", "")
            env = self._python_env()
            try:
                exec(code, env)
            except ScriptRuntimeError:
                raise
            except Exception as e:
                if self.compat:
                    first = (code or "").strip().splitlines()[0] if code else ""
                    self.python_errors.append(f"{self.state.current_label}: {e} (in: {first[:100]})")
                else:
                    raise ScriptRuntimeError(f"python block error: {e}", self.state.current_label, self.state.instruction_index)
            self._sync_variables(env)
            self._renpy_runtime.store_dict = None
            # honor renpy.jump / renpy.call / renpy.quit from the block
            if self._renpy_runtime.jump_to:
                target = self._renpy_runtime.jump_to
                self._renpy_runtime.reset()
                if target not in self.labels:
                    raise LabelNotFoundError(f'renpy.jump target "{target}" does not exist', self.state.current_label, self.state.instruction_index)
                self._bind_label_params(target, {})
                self._enter_label(target)
                return {"type": "jump", "label": target, "wait": False, "_loc": loc}
            if self._renpy_runtime.call_to:
                target = self._renpy_runtime.call_to
                self._renpy_runtime.reset()
                if target not in self.labels:
                    raise LabelNotFoundError(f'renpy.call target "{target}" does not exist', self.state.current_label, self.state.instruction_index)
                saves = self._bind_label_params(target, {})
                self._call_stack.append((self.state.current_label, self.state.instruction_index + 1, saves))
                self._enter_label(target)
                return {"type": "call", "label": target, "wait": False, "_loc": loc}
            if self._renpy_runtime.quit_requested:
                self._renpy_runtime.reset()
                return {"type": "return", "to": None, "wait": False, "_loc": loc}
            return None

        elif cmd == "while":
            cond = node.get("cond")
            loop_id = node.get("loop_id")
            if self._eval_expr(cond):
                label = self.state.current_label
                block_list = self.labels[label]
                idx = self.state.instruction_index
                insert_pos = idx + 1
                tail = {"cmd": "while", "cond": cond, "block": node.get("block", []),
                        "loop_id": loop_id, "_tail": True}
                for n in reversed(list(node.get("block", [])) + [tail]):
                    block_list.insert(insert_pos, n)
            return None  # advance into spliced block, or past the while node

        elif cmd == "for":
            target = node.get("target")
            loop_id = node.get("loop_id")
            items = node.get("_items")
            if items is None:
                try:
                    items = list(self._eval_expr(node.get("iter")) or [])
                except (ScriptRuntimeError, TypeError):
                    items = []
            if items:
                block_list = self.labels[self.state.current_label]
                at = self.state.instruction_index
                first, rest = items[0], list(items[1:])
                self._bind_for_target(target, first)
                tail = {"cmd": "for", "target": target, "loop_id": loop_id,
                        "block": node.get("block", []), "_items": rest, "_tail": True}
                for n in reversed(list(node.get("block", [])) + [tail]):
                    block_list.insert(at + 1, n)
            return None

        elif cmd == "pass":
            return None

        elif cmd == "from_clause":
            return None

        elif cmd == "voice_sustain":
            return {"type": "voice_sustain", "wait": False, "_loc": loc}

        elif cmd == "voice":
            return {"type": "voice", "position": node.get("position"), "wait": False, "_loc": loc}

        elif cmd == "break":
            loop_id = node.get("loop_id")
            t = self._find_loop_tail(loop_id)
            if t is None:
                raise ScriptRuntimeError("break outside while loop", self.state.current_label, self.state.instruction_index)
            self.state.instruction_index = t + 1
            return {"type": "break", "wait": False, "_loc": loc}

        elif cmd == "continue":
            loop_id = node.get("loop_id")
            t = self._find_loop_tail(loop_id)
            if t is None:
                raise ScriptRuntimeError("continue outside while loop", self.state.current_label, self.state.instruction_index)
            self.state.instruction_index = t
            return {"type": "continue", "wait": False, "_loc": loc}

        elif cmd == "window":
            self.state.window = node.get("value", "auto")
            return {"type": "window", "value": self.state.window, "wait": False, "_loc": loc}

        elif cmd == "nvl":
            self.state.nvl = node.get("action")
            return {"type": "nvl", "action": self.state.nvl, "wait": False, "_loc": loc}

        elif cmd == "nvl_mode":
            self.state.nvl_mode = node.get("mode", "adv")
            return {"type": "nvl_mode", "mode": self.state.nvl_mode, "wait": False, "_loc": loc}

        elif cmd == "call_screen":
            return {"type": "call_screen", "screen": node.get("screen"),
                    "args": node.get("args") or [], "transition": node.get("transition"),
                    "wait": True, "_loc": loc}

        elif cmd == "show_screen":
            return {"type": "show_screen", "screen": node.get("screen"),
                    "args": node.get("args") or [], "wait": False, "_loc": loc}

        elif cmd == "hide_screen":
            return {"type": "hide_screen", "screen": node.get("screen"), "wait": False, "_loc": loc}

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
            prev = self.state.camera.get("zoom", 1.0)
            import time as _t
            self.state.camera["zoom"] = zoom
            self.state.camera["_zoom_from"] = prev
            self.state.camera["_zoom_to"] = zoom
            self.state.camera["_zoom_dur"] = dur
            self.state.camera["_zoom_ease"] = ease
            self.state.camera["_zoom_t0"] = _t.time()
            return {"type": "camera_zoom", "zoom": zoom, "duration": dur, "easing": ease, "wait": False, "_loc": loc}

        elif cmd == "custom_statement":
            # A statement the project registered with renpy.register_statement.
            # Ren'Py runs its python callback; we recorded the block instead,
            # so the honest runtime behaviour is to pass straight through.
            return {"type": "custom_statement", "name": node.get("name"),
                    "args": node.get("args"), "wait": False, "_loc": loc}

        else:
            raise ScriptRuntimeError(f"unknown command {cmd!r}", self.state.current_label, self.state.instruction_index)

    def _bind_for_target(self, target: str, value):
        """Bind a `for` target: `for x in …` or `for k, v in …`."""
        names = [t.strip() for t in (target or "").split(",") if t.strip()]
        if len(names) > 1:
            values = list(value)
            for name, val in zip(names, values):
                self.state.variables[name] = val
        elif names:
            self.state.variables[names[0]] = value

    def _find_loop_tail(self, loop_id) -> Optional[int]:
        """Find the spliced tail marker of the innermost matching while loop."""
        block = self.labels.get(self.state.current_label, [])
        for i in range(self.state.instruction_index, len(block)):
            n = block[i]
            if n.get("cmd") in ("while", "for") and n.get("_tail") and n.get("loop_id") == loop_id:
                return i
        return None

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

        label_block = self.labels[resume_label]
        for n in reversed(block):
            label_block.insert(resume_index, n)

        self.state.current_label = resume_label
        self.state.instruction_index = resume_index
        return True


def make_script(labels: dict, characters: Optional[dict] = None, defaults: Optional[dict] = None) -> dict:
    return {"labels": labels, "characters": characters or {}, "defaults": defaults or {}}
