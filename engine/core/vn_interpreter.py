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
import warnings
import copy
from typing import Any, Dict, List, Optional, Generator, Tuple

from .vn_state import VNState, CharacterDef
from .vn_errors import ScriptRuntimeError, LabelNotFoundError


# ------------------------------------------------------------------ safe eval
def safe_eval(expr: str, variables: dict, extra: Optional[dict] = None, loose: bool = False,
              _loc: Optional[dict] = None, label: Optional[str] = None, index: Optional[int] = None):
    """
    Evaluate an expression with only variables + safe builtins.
    No attribute access (except injected objects), no comprehensions, no
    imports, no open, no exec — enforced by an AST whitelist (expr_eval.py).

    ``loose=True`` is the drop-in tier: unknown identifiers resolve to None
    instead of aborting the game (see expr_eval.ExpressionEvaluator).

    M28 audit fix: preserves _loc (file/line) and label/index for diagnostics
    instead of swallowing context.
    """
    from ..script.expr_eval import evaluate
    try:
        return evaluate(expr, variables, extra, loose=loose)
    except ScriptRuntimeError as e:
        # Preserve location: if caller provided _loc dict, include file:line
        loc_info = ""
        if _loc:
            f = _loc.get("file") or _loc.get("filename") or ""
            ln = _loc.get("line") or _loc.get("lineno") or ""
            if f or ln:
                loc_info = f" at {f}:{ln}" if f and ln else f" at {f or ln}"
        # Chain original message but keep label/index if provided
        raise ScriptRuntimeError(f"expression error: {expr!r} -> {e}{loc_info}", label, index) from e
    except Exception as e:
        # Non-ScriptRuntimeError (e.g. ZeroDivisionError) should also surface with loc
        loc_info = ""
        if _loc:
            f = _loc.get("file") or _loc.get("filename") or ""
            ln = _loc.get("line") or _loc.get("lineno") or ""
            if f or ln:
                loc_info = f" at {f}:{ln}"
        raise ScriptRuntimeError(f"expression error: {expr!r} -> {type(e).__name__}: {e}{loc_info}", label, index) from e


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
                     loose: bool = False, _loc: Optional[dict] = None,
                     label: Optional[str] = None, index: Optional[int] = None):
    val = safe_eval(expr, variables, extra, loose=loose, _loc=_loc, label=label, index=index)
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
        # M28 audit: division by zero must be explicit, not silent crash
        if val == 0 or val == 0.0:
            raise ScriptRuntimeError(f"division by zero in {target} /= {expr!r}", label, index)
        try:
            new = (old or 0) / val
        except ZeroDivisionError as e:
            raise ScriptRuntimeError(f"division by zero in {target} /= {expr!r}", label, index) from e
    else:
        raise ScriptRuntimeError(f"unknown assign op {op!r}", label, index)
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
def _exec_script_code(code: str, env: dict):
    r"""``exec`` a `python:` / `init python:` block taken from a script.

    Wrapped so a *syntax* warning in the author's own code does not pollute our
    output: real games ship regexes written as ``"\s+"`` rather than ``r"\s+"``,
    which Python flags with SyntaxWarning. Those warnings are about the game's
    code, not about UPVN. Genuine errors still propagate and are handled by the
    caller's compat logic.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        exec(code, env)


_bracket_pat = re.compile(r"\[([^\]\[]+)\]")  # Ren'Py [expr] interpolation

def interpolate(text: str, variables: dict, extra: Optional[dict] = None,
                _loc: Optional[dict] = None, strict: bool = False) -> str:
    """Interpolate ``[expr]`` brackets in dialogue text.

    Simple names resolve from ``variables``; anything else is evaluated with
    the same AST whitelist as story expressions (so ``[gold * 2]`` works, and
    in full mode ``[store.gold]`` / ``[renpy.loadable(...)]`` too).

    M28 audit improvements:
    - Preserves _loc for diagnostics (file:line) when strict=True
    - Simple names that are missing now leave a visible marker but also
      log a diagnostic event instead of silently returning literal
    - Complex expressions that fail: in strict mode raise, otherwise leave verbatim
      but collect error in trace via caller
    """
    errors = []

    def repl(m):
        expr = m.group(1).strip()
        if not expr:
            return m.group(0)
        if re.fullmatch(r"\w+", expr):
            if expr in variables:
                return str(variables[expr])
            errors.append(f"interpolation: variable {expr!r} not found")
            return f"[{expr}]"
        try:
            from ..script.expr_eval import evaluate
            val = evaluate(expr, variables, extra)
            if val is None:
                errors.append(f"interpolation: {expr!r} evaluated to None")
                return m.group(0)
            return str(val)
        except Exception as e:
            errors.append(f"interpolation: {expr!r} failed: {e}")
            if strict:
                loc_info = ""
                if _loc:
                    f = _loc.get("file") or _loc.get("filename") or ""
                    ln = _loc.get("line") or _loc.get("lineno") or ""
                    if f or ln:
                        loc_info = f" at {f}:{ln}"
                raise ScriptRuntimeError(f"interpolation error: {expr!r} -> {e}{loc_info}") from e
            return m.group(0)

    result = _bracket_pat.sub(repl, text)
    interpolate.last_errors = errors
    return result

interpolate.last_errors = []


# M28: improved tag handling — Ren'Py text tags {b},{i},{color},{size},{font},{alpha},{outline}, etc.
# We strip for trace but keep raw for frontend. The pattern handles nested = values and optional /
# Example: {color=#c8ffc8}, {/color}, {b}, {size=+4}, {font=DejaVuSans.ttf}
_tag_pat = re.compile(r"\{/?[a-zA-Z_][^}]*\}")

def strip_tags(text: str) -> str:
    """Strip Ren'Py text tags, preserving the inner text.

    Handles {b},{/b},{i},{/i},{color=...},{/color},{size=...},{/size},{font=...},{/font},
    {alpha=...},{outline}, {u}, {s}, {plain}, {w}, {nw}, {fast}, {p}, etc.
    """
    if not text:
        return ""
    # First strip our recognized pattern
    stripped = _tag_pat.sub("", text)
    # Also handle any remaining curly braces that look like tags but with numbers/symbols
    # e.g. {=...} or {{ escaped brace
    stripped = stripped.replace("{{{", "{").replace("}}}", "}")
    return stripped

def parse_rich_tags(text: str) -> list:
    """Parse text into segments with style info — for future rich rendering.

    Returns list of {text, bold, italic, color, size} dicts.
    Currently used for diagnostics and headless rendering bold/italic simulation.
    """
    if not text:
        return [{"text": "", "bold": False, "italic": False, "color": None}]
    segments = []
    pos = 0
    bold = False
    italic = False
    color = None
    # Find tags
    for m in _tag_pat.finditer(text):
        if m.start() > pos:
            seg_text = text[pos:m.start()]
            if seg_text:
                segments.append({"text": seg_text, "bold": bold, "italic": italic, "color": color})
        tag = m.group(0).strip("{}").strip()
        tag_lower = tag.lower()
        if tag_lower == "b":
            bold = True
        elif tag_lower == "/b":
            bold = False
        elif tag_lower == "i":
            italic = True
        elif tag_lower == "/i":
            italic = False
        elif tag_lower.startswith("color="):
            color = tag[6:].strip()
        elif tag_lower == "/color":
            color = None
        # size, font, alpha, etc. are currently ignored for 3D FONT but parsed
        pos = m.end()
    if pos < len(text):
        seg_text = text[pos:]
        if seg_text:
            segments.append({"text": seg_text, "bold": bold, "italic": italic, "color": color})
    if not segments:
        segments.append({"text": strip_tags(text), "bold": False, "italic": False, "color": None})
    return segments


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

        # M22: captured `screen:` bodies become real widgets instead of inert
        # text. `show screen` / `call screen` hand a frontend something to draw.
        from ..ui.screen_lang import ScreenLang
        self.screen_lang = ScreenLang(
            screens=self.screens,
            evaluator=self._eval_screen_expr,
            executor=self._exec_screen_code,
        )

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
        for i, line in enumerate(code_lines):
            try:
                _exec_script_code(line, env)
            except Exception as e:
                first = (line or "").strip().splitlines()[0] if line else ""
                # M28: include line number and file context in compat errors
                msg = f"init python error at line {i+1}: {e}\n  in: {first[:120]}"
                if self.compat:
                    self.init_errors.append(msg)
                    print(f"[UPVN] {msg} — compat mode continues")
                    continue
                raise ScriptRuntimeError(msg) from e
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

    def _eval_screen_expr(self, expr: str, scope: Optional[Dict[str, Any]] = None):
        """Evaluate one screen-language expression (full tier is permissive).

        Screen bodies see the store, the screen's own parameters (the overlay
        ``scope``) and the renpy compat namespace — the same surface a
        `python:` block gets. ``scope`` carries screen-local names (parameters,
        `default`s) so compound conditions like ``score > 5`` resolve.
        M28: includes loc preservation via safe_eval.
        """
        if not scope:
            return self._eval_expr(expr)
        try:
            return safe_eval(expr, {**self.state.variables, **scope},
                             self._expr_extra if self.full else None, loose=self.full)
        except ScriptRuntimeError as e:
            # Screen expr failures should not crash — log and return None for permissive tier
            if self.full:
                print(f"[UPVN] screen expr {expr!r} failed: {e} — returning None (compat)")
                return None
            raise

    def _render_screen(self, name: str, args: List[str]) -> dict:
        """Evaluate a `screen:` body into a widget tree.

        M28 audit: never raises in compat mode, but in strict mode surfaces errors.
        Errors are always included in the returned dict under "errors" and also
        printed for console visibility. Frontend must check event.get("errors").
        """
        try:
            result = self.screen_lang.render(name, args)
            # Ensure errors key exists
            if "errors" not in result:
                result["errors"] = []
            return result
        except Exception as e:
            import traceback
            tb = traceback.format_exc()[-500:]
            msg = f"screen {name!r} failed to render: {e}"
            print(f"[UPVN] {msg}\n{tb}")
            return {"name": name, "props": {}, "widgets": [],
                    "errors": [msg, tb]}

    def _exec_screen_code(self, code: str):
        """Run a `$` line from inside a screen body."""
        env = self._python_env()
        _exec_script_code(code, env)
        self._sync_variables(env)

    def _eval_expr(self, expr: str, _loc: Optional[dict] = None):
        extra = self._expr_extra if self.full else None
        label = self.state.current_label
        idx = self.state.instruction_index
        return safe_eval(expr, self.state.variables, extra, loose=self.full, _loc=_loc, label=label, index=idx)

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
                # handle menu choice — M28: bounds check before indexing
                if event["type"] == "menu":
                    choice_idx = response
                    if choice_idx is None:
                        raise ScriptRuntimeError("menu requires a choice index", label, idx)
                    choices = event.get("choices", [])
                    if not isinstance(choice_idx, int):
                        raise ScriptRuntimeError(f"menu choice must be int, got {type(choice_idx).__name__}", label, idx)
                    if choice_idx < 0 or choice_idx >= len(choices):
                        raise ScriptRuntimeError(f"menu choice {choice_idx} out of range (0..{len(choices)-1})", label, idx)
                    choice = choices[choice_idx]
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

    # ------------------------ per-node execution (M28 audit fixes)
    def _execute_node(self, node: dict) -> Optional[dict]:
        cmd = node.get("cmd")
        loc = node.get("_loc")
        label = self.state.current_label
        idx = self.state.instruction_index

        if cmd == "say":
            who = node.get("who")
            text_raw = node.get("text", "")
            # M28: interpolation with loc and error collection
            try:
                text = interpolate(text_raw, self.state.variables, self._expr_extra if self.full else None, _loc=loc)
                interp_errors = getattr(interpolate, "last_errors", [])
            except ScriptRuntimeError as e:
                # In strict mode interpolation failure should not crash line — log and keep raw
                text = text_raw
                interp_errors = [str(e)]
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
            if interp_errors:
                event["interp_warnings"] = interp_errors
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
            self.state.shown_actors.clear()
            return {"type": "scene", "asset": asset, "transition": trans, "wait": False, "_loc": loc}

        elif cmd == "show":
            asset = node.get("asset")
            tag = node.get("tag")
            pos = node.get("position") or "center"
            trans = node.get("transition")
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
            # M28: warn if hiding nonexistent sprite (was silent)
            if tag not in self.state.shown_actors:
                # Not an error — Ren'Py allows hiding nonexistent — but log for diagnostics
                pass
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
            if isinstance(dur, str):
                try:
                    dur = safe_eval(dur, self.state.variables, self._expr_extra if self.full else None,
                                    loose=self.full, _loc=loc, label=label, index=idx)
                except ScriptRuntimeError as e:
                    # M28: preserve loc, don't silently swallow
                    print(f"[UPVN] pause duration eval failed at {loc}: {e} — using None")
                    dur = None
            return {"type": "pause", "duration": dur, "wait": True, "_loc": loc}

        elif cmd == "jump":
            tgt_label = node.get("label")
            if tgt_label is None and node.get("expr"):
                try:
                    tgt_label = str(safe_eval(node["expr"], self.state.variables,
                                              self._expr_extra if self.full else None,
                                              loose=self.full, _loc=loc, label=label, index=idx))
                except ScriptRuntimeError as e:
                    raise ScriptRuntimeError(f"jump expression failed: {e}", label, idx) from e
            if tgt_label not in self.labels:
                raise LabelNotFoundError(f'jump target "{tgt_label}" does not exist', label, idx)
            self._bind_label_params(tgt_label, {})
            self._enter_label(tgt_label)
            return {"type": "jump", "label": tgt_label, "wait": False, "_loc": loc}

        elif cmd == "call":
            tgt_label = node.get("label")
            if tgt_label is None and node.get("expr"):
                try:
                    tgt_label = str(safe_eval(node["expr"], self.state.variables,
                                              self._expr_extra if self.full else None,
                                              loose=self.full, _loc=loc, label=label, index=idx))
                except ScriptRuntimeError as e:
                    raise ScriptRuntimeError(f"call expression failed: {e}", label, idx) from e
            if tgt_label not in self.labels:
                raise LabelNotFoundError(f'call target "{tgt_label}" does not exist', label, idx)
            provided: dict = {}
            args = node.get("args")
            if args:
                params = self.label_params.get(tgt_label, [])
                for i, arg_expr in enumerate(args):
                    if i < len(params):
                        try:
                            provided[params[i]["name"]] = safe_eval(arg_expr, self.state.variables,
                                                                    self._expr_extra if self.full else None,
                                                                    loose=self.full, _loc=loc, label=label, index=idx)
                        except ScriptRuntimeError as e:
                            raise ScriptRuntimeError(f"call arg {i} failed: {e}", label, idx) from e
            saves = self._bind_label_params(tgt_label, provided)
            self._call_stack.append((label, idx + 1, saves))
            self._enter_label(tgt_label)
            return {"type": "call", "label": tgt_label, "wait": False, "_loc": loc}

        elif cmd == "return":
            if self._call_stack:
                ret_label, ret_idx, saves = self._call_stack.pop()
                self._restore_params(saves)
                self._enter_label(ret_label, ret_idx)
                return {"type": "return", "to": ret_label, "wait": False, "_loc": loc}
            else:
                return {"type": "return", "to": None, "wait": False, "_loc": loc}

        elif cmd == "assign":
            target, op, expr = node.get("target"), node.get("op"), node.get("expr")
            try:
                safe_exec_assign(target, op, expr, self.state.variables, self.state.declared_types,
                                 self._expr_extra if self.full else None, loose=self.full,
                                 _loc=loc, label=label, index=idx)
            except ScriptRuntimeError:
                raise
            except Exception as e:
                raise ScriptRuntimeError(f"assign {target} {op} {expr!r} failed: {e}", label, idx) from e
            return {"type": "assign", "target": target, "op": op, "expr": expr, "value": self.state.variables.get(target), "wait": False, "_loc": loc}

        elif cmd == "if":
            branches = node.get("branches", [])
            chosen = None
            for br in branches:
                cond = br.get("cond")
                if cond is None:
                    chosen = br
                    break
                try:
                    if safe_eval(cond, self.state.variables, self._expr_extra if self.full else None,
                                 loose=self.full, _loc=loc, label=label, index=idx):
                        chosen = br
                        break
                except ScriptRuntimeError as e:
                    # M28: if condition eval fails, treat as False but log
                    print(f"[UPVN] if condition {cond!r} failed at {loc}: {e} — treating as False")
                    continue
            if chosen is None:
                return None
            block_list = self.labels[label]
            insert_pos = idx + 1
            for n in reversed(chosen.get("block", [])):
                block_list.insert(insert_pos, n)
            return None

        elif cmd == "menu":
            if node.get("pre") and not node.get("_pre_done"):
                node["_pre_done"] = True
                block_list = self.labels[label]
                at = idx
                for n in reversed(list(node["pre"]) + [node]):
                    block_list.insert(at + 1, n)
                return None
            caption = node.get("caption")
            kept = []
            for c in node.get("choices", []):
                cond = c.get("cond")
                if cond is not None:
                    try:
                        if not safe_eval(cond, self.state.variables, self._expr_extra if self.full else None,
                                         loose=self.full, _loc=loc, label=label, index=idx):
                            continue
                    except ScriptRuntimeError as e:
                        print(f"[UPVN] menu choice cond {cond!r} failed at {loc}: {e} — hiding choice")
                        continue
                kept.append(c)
            if not kept:
                # M28: empty menu after filtering — raise with loc instead of silent empty UI
                raise ScriptRuntimeError(f"menu at {label}:{idx} has no available choices after filtering", label, idx)
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
                _exec_script_code(code, env)
            except ScriptRuntimeError:
                raise
            except Exception as e:
                if self.compat:
                    first = (code or "").strip().splitlines()[0] if code else ""
                    # M28: include file/line in compat error
                    loc_str = f"{loc}" if loc else f"{label}:{idx}"
                    self.python_errors.append(f"{loc_str}: {e} (in: {first[:100]})")
                    print(f"[UPVN] python block error at {loc_str}: {e} — compat mode continues")
                else:
                    raise ScriptRuntimeError(f"python block error: {e}", label, idx)
            self._sync_variables(env)
            self._renpy_runtime.store_dict = None
            if self._renpy_runtime.jump_to:
                target = self._renpy_runtime.jump_to
                self._renpy_runtime.reset()
                if target not in self.labels:
                    raise LabelNotFoundError(f'renpy.jump target "{target}" does not exist', label, idx)
                self._bind_label_params(target, {})
                self._enter_label(target)
                return {"type": "jump", "label": target, "wait": False, "_loc": loc}
            if self._renpy_runtime.call_to:
                target = self._renpy_runtime.call_to
                self._renpy_runtime.reset()
                if target not in self.labels:
                    raise LabelNotFoundError(f'renpy.call target "{target}" does not exist', label, idx)
                saves = self._bind_label_params(target, {})
                self._call_stack.append((label, idx + 1, saves))
                self._enter_label(target)
                return {"type": "call", "label": target, "wait": False, "_loc": loc}
            if self._renpy_runtime.quit_requested:
                self._renpy_runtime.reset()
                return {"type": "return", "to": None, "wait": False, "_loc": loc}
            return None

        elif cmd == "while":
            cond = node.get("cond")
            loop_id = node.get("loop_id")
            try:
                cond_val = safe_eval(cond, self.state.variables, self._expr_extra if self.full else None,
                                     loose=self.full, _loc=loc, label=label, index=idx)
            except ScriptRuntimeError as e:
                print(f"[UPVN] while cond {cond!r} failed at {loc}: {e} — treating as False")
                cond_val = False
            if cond_val:
                block_list = self.labels[label]
                insert_pos = idx + 1
                tail = {"cmd": "while", "cond": cond, "block": node.get("block", []),
                        "loop_id": loop_id, "_tail": True}
                for n in reversed(list(node.get("block", [])) + [tail]):
                    block_list.insert(insert_pos, n)
            return None

        elif cmd == "for":
            target = node.get("target")
            loop_id = node.get("loop_id")
            items = node.get("_items")
            if items is None:
                try:
                    eval_result = safe_eval(node.get("iter"), self.state.variables,
                                            self._expr_extra if self.full else None,
                                            loose=self.full, _loc=loc, label=label, index=idx)
                    if eval_result is None:
                        items = []
                    else:
                        try:
                            items = list(eval_result)
                        except TypeError as e:
                            # M28: non-iterable in for loop — log and treat as empty, not silent
                            print(f"[UPVN] for loop iterable {node.get('iter')!r} not iterable at {loc}: {e} — treating as empty")
                            items = []
                except ScriptRuntimeError as e:
                    print(f"[UPVN] for loop iterable eval failed at {loc}: {e} — treating as empty")
                    items = []
            if items:
                block_list = self.labels[label]
                at = idx
                first, rest = items[0], list(items[1:])
                try:
                    self._bind_for_target(target, first)
                except Exception as e:
                    print(f"[UPVN] for target bind failed at {loc}: {e}")
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
                raise ScriptRuntimeError("break outside while loop", label, idx)
            self.state.instruction_index = t + 1
            return {"type": "break", "wait": False, "_loc": loc}

        elif cmd == "continue":
            loop_id = node.get("loop_id")
            t = self._find_loop_tail(loop_id)
            if t is None:
                raise ScriptRuntimeError("continue outside while loop", label, idx)
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
            name = node.get("screen")
            args = node.get("args") or []
            view = self._render_screen(name, args)
            self.state.active_screens[name] = {
                "args": list(args), "widgets": view["widgets"],
                "props": view["props"], "modal": True,
            }
            # M28: propagate screen errors to event and log
            if view.get("errors"):
                print(f"[UPVN] screen {name!r} render warnings at {loc}: {view['errors']}")
            return {"type": "call_screen", "screen": name, "args": args,
                    "transition": node.get("transition"),
                    "widgets": view["widgets"], "props": view["props"],
                    "errors": view["errors"],
                    "wait": True, "_loc": loc}

        elif cmd == "show_screen":
            name = node.get("screen")
            args = node.get("args") or []
            view = self._render_screen(name, args)
            self.state.active_screens[name] = {
                "args": list(args), "widgets": view["widgets"],
                "props": view["props"], "modal": False,
            }
            if view.get("errors"):
                print(f"[UPVN] screen {name!r} render warnings at {loc}: {view['errors']}")
            return {"type": "show_screen", "screen": name, "args": args,
                    "widgets": view["widgets"], "props": view["props"],
                    "errors": view["errors"],
                    "wait": False, "_loc": loc}

        elif cmd == "hide_screen":
            name = node.get("screen")
            self.state.active_screens.pop(name, None)
            return {"type": "hide_screen", "screen": name, "wait": False, "_loc": loc}

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
            else:
                print(f"[UPVN] anim target {tgt!r} not in stage_objects at {loc}")
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
            return {"type": "custom_statement", "name": node.get("name"),
                    "args": node.get("args"), "wait": False, "_loc": loc}

        else:
            raise ScriptRuntimeError(f"unknown command {cmd!r}", label, idx)


    def _bind_for_target(self, target: str, value):
        """Bind a `for` target: `for x in …` or `for k, v in …`.
        M28: handles non-iterable tuple-unpacking safely with diagnostics.
        """
        names = [t.strip() for t in (target or "").split(",") if t.strip()]
        if not names:
            return
        if len(names) > 1:
            try:
                values = list(value)
            except TypeError as e:
                print(f"[UPVN] for loop tuple unpack failed: target {target!r} value {value!r} not iterable: {e} — skipping")
                return
            # If lengths mismatch, zip safely and warn
            if len(values) != len(names):
                print(f"[UPVN] for loop unpack length mismatch: {len(names)} names vs {len(values)} values at {self.state.current_label}:{self.state.instruction_index}")
            for name, val in zip(names, values):
                self.state.variables[name] = val
        else:
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
