"""
UPVN Screen Language — M22

Turns a captured `screen:` block into a concrete list of widgets.

Ren'Py screens were captured by the parser as indented text but nothing could
act on them, so `call screen` / `show screen` emitted an event carrying a name
and no content — 99 screens in the SDK tutorial and 23 in LearnToCodeRPG were
inert. This module evaluates a screen body the way Ren'Py does: control flow,
screen-local `default`s, `use` composition with `transclude`, and property
blocks — and produces a JSON-serialisable widget tree a UI layer can draw.

Deliberately minimal by design: it resolves *what is on screen* (text, buttons,
images, layout properties, actions), not pixel layout. Coordinates, styles and
anchors stay in ``props`` for the consumer to interpret.

Evaluation never raises at the caller: a screen that references something UPVN
does not model degrades to a placeholder and records a diagnostic, because in
compat mode a game must keep playing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------- vocabulary
# Kinds that take a child block. Anything else with a trailing `:` is still
# accepted (permissive) — an unknown container is better than a parse failure.
CONTAINER_KINDS = {
    "vbox", "hbox", "frame", "window", "fixed", "grid", "viewport", "side",
    "imagemap", "hotspot", "button", "null", "bar", "vbar",
}

# Kinds that are leaves: they draw something and take no child block.
LEAF_KINDS = {
    "text", "textbutton", "imagebutton", "add", "label", "input", "key",
    "timer", "mousearea", "image",
}

# Control flow / statements that are not widgets.
CONTROL_KINDS = {
    "if", "elif", "else", "for", "use", "has", "default", "python", "$",
    "transclude",
}

# Property names seen in real projects (Ren'Py SDK tutorial + LearnToCodeRPG)
# plus the common layout/style set. A bare `name value` line whose name is in
# here sets a property on the enclosing block instead of creating a widget.
PROPERTY_NAMES = {
    # position / size
    "xalign", "yalign", "align", "xpos", "ypos", "pos", "xanchor", "yanchor",
    "anchor", "xoffset", "yoffset", "offset", "xsize", "ysize", "xmaximum",
    "ymaximum", "xminimum", "yminimum", "xfill", "yfill", "xpadding",
    "ypadding", "xmargin", "ymargin", "spacing", "first_spacing", "area",
    "left", "right", "top", "bottom", "left_margin", "right_margin",
    "top_margin", "bottom_margin", "left_padding", "right_padding",
    "top_padding", "bottom_padding", "minwidth", "min_width",
    # appearance
    "background", "foreground", "child", "hover_background", "idle_background",
    "insensitive_background", "selected_idle_background",
    "selected_hover_background", "color", "hover_color", "idle_color",
    "selected_color", "text_color", "text_hover_color", "outlines", "font",
    "size", "text_size", "bold", "italic", "underline", "strikethrough",
    "kerning", "line_spacing", "line_leading", "text_align", "layout",
    "drop_shadow", "slow", "slow_speed", "slow_cps", "slow_cps_multiplier",
    "text_xalign", "text_yalign", "text_xpos", "text_ypos", "text_layout",
    "text_outlines", "text_font", "text_bold", "text_italic",
    # behaviour
    "action", "hovered", "unhovered", "clicked", "alternate", "value",
    "range", "offset_value", "style", "style_prefix", "style_group",
    "sensitive", "focus_mask", "tooltip", "id", "default", "modal", "zorder",
    "tag", "layer", "mousewheel", "arrowkeys", "page", "bar_vertical",
    "bar_invert", "bar_resizing", "left_gutter", "right_gutter",
    "top_gutter", "bottom_gutter", "thumb", "thumb_shadow", "thumb_offset",
    "unscrollable", "yinitial", "scrollbars", "side_xpos", "side_ypos",
    "side_spacing", "edgescroll", "drag_name", "drag_handle", "draggable",
    "dragged", "droppable", "dropped", "drop_shadow_color", "subpixel",
    "crop", "corner1", "corner2", "radius", "alpha", "additive", "zoom",
    "xzoom", "yzoom", "rotate", "rotation", "matrixcolor",
}

# `name "value"` pairs that appear as bare lines at the top of a screen and
# apply to the screen itself rather than to a widget.
SCREEN_LEVEL_PROPS = {
    "modal", "zorder", "tag", "layer", "style_prefix", "style", "predict",
    "variant", "rollback",
}

class ScreenLangError(Exception):
    """A screen body that cannot be interpreted. Carries a friendly message."""

    def __init__(self, message: str, screen: str = "", line: int = 0,
                 hint: str = ""):
        self.screen = screen
        self.line = line
        self.hint = hint
        super().__init__(message)


# ---------------------------------------------------------------- tokenising
def tokenize(text: str) -> List[str]:
    """Split a screen-language line into tokens, respecting quotes and brackets.

    ``textbutton _("Yes") id "confirm_yes_button" action yes_action``
      -> ['textbutton', '_("Yes")', 'id', '"confirm_yes_button"', 'action', 'yes_action']

    ``_("Yes")`` stays one token even though it contains a space.
    """
    out: List[str] = []
    buf: List[str] = []
    quote: Optional[str] = None
    depth = 0
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            continue
        if ch in "([{":
            depth += 1
            buf.append(ch)
            continue
        if ch in ")]}":
            depth = max(0, depth - 1)
            buf.append(ch)
            continue
        if ch.isspace() and depth == 0:
            if buf:
                out.append("".join(buf))
                buf = []
            continue
        buf.append(ch)
    if buf:
        out.append("".join(buf))
    return out


_KWARG = re.compile(r"^([A-Za-z_]\w*)\s*=(?!=)(.+)$", re.S)


def split_call_args(args: List[str]) -> Tuple[List[str], Dict[str, str]]:
    """Split ``['"Yes"', 'score=gold']`` into positional args and kwargs.

    `a==b` is a comparison, not a keyword argument, and a quoted `"a=b"` is a
    string — both must stay positional.
    """
    positional: List[str] = []
    kwargs: Dict[str, str] = {}
    for a in args:
        m = _KWARG.match(a.strip())
        if m:
            kwargs[m.group(1)] = m.group(2).strip()
        else:
            positional.append(a)
    return positional, kwargs


def _is_bare_identifier(tok: str) -> bool:
    return tok.isidentifier()


def split_props(tokens: List[str]) -> Tuple[List[str], Dict[str, str]]:
    """Split ``[positional args..., name value, name value...]``.

    Positional arguments come first; the first token that is a known property
    name starts the property section (Ren'Py resolves this from its style
    system, so a known-name set is the faithful approach). A property whose
    value is a call/list consumes its single token — the tokeniser already
    keeps ``Return(True)`` and ``[a, b]`` intact.
    """
    args: List[str] = []
    props: Dict[str, str] = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if _is_bare_identifier(tok) and tok in PROPERTY_NAMES:
            if i + 1 < len(tokens):
                props[tok] = tokens[i + 1]
                i += 2
            else:
                # a trailing flag with no value: treat as boolean-ish
                props[tok] = "True"
                i += 1
            continue
        args.append(tok)
        i += 1
    return args, props


# ---------------------------------------------------------------- AST
@dataclass
class WidgetNode:
    """One node of a screen body: a widget, a property, or control flow."""
    kind: str
    args: List[str] = field(default_factory=list)
    props: Dict[str, str] = field(default_factory=dict)
    children: List["WidgetNode"] = field(default_factory=list)
    lineno: int = 0
    # control-flow only
    cond: str = ""            # if / elif
    target: str = ""          # for <target>
    iter_expr: str = ""       # for ... in <iter_expr>
    use_screen: str = ""      # use <name>
    code: List[str] = field(default_factory=list)   # python block lines


# ---------------------------------------------------------------- parsing
def _parse_block(lines: List[str], indents: List[int], i: int,
                 base: int) -> Tuple[List[WidgetNode], int]:
    """Parse sibling nodes at indent ``base``. Returns (nodes, next index)."""
    nodes: List[WidgetNode] = []
    while i < len(lines):
        indent = indents[i]
        if indent < base:
            break
        if indent > base:
            # Should not happen: a deeper line is consumed by its parent's
            # recursion. Skip it rather than mis-nesting everything after.
            i += 1
            continue
        text = lines[i].strip()
        lineno = i + 1
        if not text:
            i += 1
            continue

        # block header (containers + control flow): `vbox:` / `if x:`
        if text.endswith(":") and not text.endswith("::"):
            header = text[:-1].rstrip()
            head_toks = tokenize(header)
            kind = head_toks[0] if head_toks else ""
            child_indent = indents[i + 1] if i + 1 < len(lines) else None
            children, i2 = ([], i + 1)
            if child_indent is not None and child_indent > base:
                children, i2 = _parse_block(lines, indents, i + 1, child_indent)
            else:
                i2 = i + 1
            nodes.append(_make_node(kind, head_toks, children, lineno))
            i = i2
            continue

        # bare statement: property assignment or a leaf widget
        toks = tokenize(text)
        kind = toks[0] if toks else ""
        if kind in ("$", "python") or text.startswith("$"):
            node = WidgetNode(kind="$" if kind == "$" else "python", lineno=lineno)
            node.code = [text[1:].strip()] if kind == "$" else []
            nodes.append(node)
            i += 1
            continue
        args, props = split_props(toks)
        if not args and props:
            # `xalign .5` — a property of the enclosing block
            node = WidgetNode(kind="_prop", props=props, lineno=lineno)
            nodes.append(node)
            i += 1
            continue
        nodes.append(_make_node(kind, toks, [], lineno))
        i += 1
    return _group_conditions(_apply_has(nodes)), i


def _make_node(kind: str, toks: List[str], children: List[WidgetNode],
               lineno: int) -> WidgetNode:
    node = WidgetNode(kind=kind, children=children, lineno=lineno)
    rest = toks[1:]

    if kind in ("if", "elif"):
        node.cond = " ".join(rest)
        return node
    if kind == "for":
        body = " ".join(rest)
        if " in " in body:
            target, _, expr = body.partition(" in ")
            node.target = target.strip()
            node.iter_expr = expr.strip()
        else:
            node.iter_expr = body
        return node
    if kind == "use":
        if rest:
            call = rest[0]
            node.use_screen = call.split("(")[0]
            inner = call[len(node.use_screen):].strip()
            if inner.startswith("(") and inner.endswith(")"):
                # arguments live inside the parens, not in the token itself
                args, props = split_props(tokenize(inner[1:-1]))
            else:
                args, props = split_props(rest[1:])
            node.args, node.props = args, props
        return node
    if kind in ("default",):
        body = " ".join(rest)
        if "=" in body:
            name, _, expr = body.partition("=")
            node.target, node.iter_expr = name.strip(), expr.strip()
        return node
    if kind == "transclude":
        return node
    if kind == "has":
        node.args = rest
        return node

    args, props = split_props(rest)
    node.args, node.props = args, props
    return node


def _apply_has(nodes: List[WidgetNode]) -> List[WidgetNode]:
    """Rewrite `has X` — the siblings after it become children of a container X.

    Ren'Py's `has vbox` is a declaration, not a block: there is no indented
    body, so the container has to be synthesised from the siblings that follow.
    `has vbox:` with its own property lines keeps them on the container.
    """
    out: List[WidgetNode] = []
    i = 0
    while i < len(nodes):
        n = nodes[i]
        if n.kind == "has" and n.args:
            kind = n.args[0]
            container = WidgetNode(kind=kind, lineno=n.lineno)
            container.props = dict(n.props)
            # `has vbox:` may carry its own property block
            for child in n.children:
                if child.kind == "_prop":
                    container.props.update(child.props)
            container.children = _apply_has(nodes[i + 1:])
            out.append(container)
            return out
        out.append(n)
        i += 1
    return out


def _group_conditions(nodes: List[WidgetNode]) -> List[WidgetNode]:
    """Fold `if` / `elif` / `else` siblings into one chain node.

    Ren'Py treats them as a single statement; keeping them as siblings would
    make the evaluator re-test each branch independently.
    """
    out: List[WidgetNode] = []
    i = 0
    while i < len(nodes):
        n = nodes[i]
        if n.kind == "if":
            chain = WidgetNode(kind="_cond", lineno=n.lineno)
            chain.children = [n]
            j = i + 1
            while j < len(nodes) and nodes[j].kind in ("elif", "else"):
                chain.children.append(nodes[j])
                j += 1
            out.append(chain)
            i = j
            continue
        out.append(n)
        i += 1
    return out


def parse_screen_body(lines: List[str],
                      indents: Optional[List[int]] = None) -> List[WidgetNode]:
    """Parse a captured screen body into a widget tree.

    ``indents`` are the relative indents recorded by the parser. Without them
    every line is treated as a flat sibling, which loses `vbox:` nesting — so
    callers that have them should always pass them.
    """
    if not lines:
        return []
    if indents is None:
        indents = [0] * len(lines)
    if len(indents) != len(lines):
        raise ScreenLangError(
            f"screen body has {len(lines)} lines but {len(indents)} indents",
            hint="pass the `indents` list captured alongside `lines`")
    base = min(x for x in indents if x >= 0)
    nodes, _ = _parse_block(lines, indents, 0, base)
    return nodes


# ---------------------------------------------------------------- rendering
_BRACKET = re.compile(r"\[([^\]\[]+)\]")


def _interpolate(text: str, ev: Callable[[str], Any]) -> str:
    """Resolve ``[expr]`` brackets in screen text, as Ren'Py does.

    Unresolvable expressions stay verbatim rather than blanking the label — a
    button reading ``[score]`` is more useful to a player than one reading
    nothing.
    """
    if "[" not in text:
        return text

    def repl(m):
        expr = m.group(1).strip()
        if not expr:
            return m.group(0)
        try:
            val = ev(expr)
        except Exception:
            return m.group(0)
        if val is None:
            return m.group(0)
        return str(val)
    return _BRACKET.sub(repl, text)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _resolve(expr: str, evaluator: Callable[[str], Any]) -> Any:
    """Resolve one expression. A quoted string is its own content."""
    e = (expr or "").strip()
    if not e:
        return ""
    if len(e) >= 2 and e[0] == e[-1] and e[0] in "\"'":
        return e[1:-1]
    try:
        return evaluator(e)
    except Exception:
        # keep the source text: an unresolved `gui.x` is more useful to a UI
        # layer (and to a reader) than a replacement character
        return e


@dataclass
class ScreenLang:
    """Evaluates captured `screen:` bodies into widget trees."""

    screens: Dict[str, dict] = field(default_factory=dict)
    evaluator: Optional[Callable[[str], Any]] = None
    executor: Optional[Callable[[str], None]] = None
    max_depth: int = 12
    max_widgets: int = 4000

    def __post_init__(self):
        self.errors: List[str] = []

    # -- public API
    def has(self, name: str) -> bool:
        return name in self.screens

    def names(self) -> List[str]:
        return sorted(self.screens)

    def render(self, name: str, args: Optional[List[str]] = None,
               scope: Optional[Dict[str, Any]] = None) -> dict:
        """Evaluate a screen and return a JSON-serialisable widget tree.

        Returns ``{"name", "props", "widgets", "errors"}``. Never raises: an
        unresolvable screen yields an empty tree plus diagnostics, so a caller
        in the middle of playing a game is not interrupted.
        """
        self.errors = []
        if name not in self.screens:
            self.errors.append(f"screen {name!r} is not defined")
            return {"name": name, "props": {}, "widgets": [],
                    "errors": list(self.errors)}
        body = self.screens[name] or {}
        lines = body.get("lines") or []
        indents = body.get("indents")
        try:
            tree = parse_screen_body(lines, indents)
        except ScreenLangError as e:
            self.errors.append(f"screen {name!r}: {e}")
            return {"name": name, "props": {}, "widgets": [],
                    "errors": list(self.errors)}

        env: Dict[str, Any] = {}
        self._bind_params(body.get("params") or "", args or [], env, name)
        if scope:
            env.update(scope)
        self._apply_defaults(tree, env)

        widgets: List[dict] = []
        screen_props: Dict[str, Any] = {}
        self._eval_nodes(tree, env, widgets, name, depth=0,
                         transclude=None, props=screen_props)
        return {"name": name, "props": screen_props, "widgets": widgets,
                "errors": list(self.errors)}

    # -- params / defaults
    def _bind_params(self, params: str, args: List[str], env: Dict[str, Any],
                     screen: str) -> None:
        """Bind `screen foo(a, b=2):` against the call's argument list."""
        positional, kwargs = split_call_args(args)
        if not params.strip():
            # no declared parameters: still expose keyword arguments, so a
            # screen can read them via [name] instead of silently blanking
            for pname, raw in kwargs.items():
                env[pname] = _resolve(raw, self._eval)
            return
        names = [p.strip() for p in params.split(",") if p.strip()]
        for i, spec in enumerate(names):
            if "=" in spec:
                pname, _, default = spec.partition("=")
                pname, default = pname.strip(), default.strip()
                if pname in kwargs:
                    env[pname] = _resolve(kwargs[pname], self._eval)
                elif i < len(positional):
                    env[pname] = _resolve(positional[i], self._eval)
                else:
                    env[pname] = _resolve(default, self._eval)
            elif spec in kwargs:
                env[spec] = _resolve(kwargs[spec], self._eval)
            elif i < len(positional):
                env[spec] = _resolve(positional[i], self._eval)
            else:
                env[spec] = None

    def _apply_defaults(self, tree: List[WidgetNode], env: Dict[str, Any]):
        """`default x = expr` — set the name unless the caller already did."""
        for n in tree:
            if n.kind == "default" and n.target and n.target not in env:
                env[n.target] = _resolve(n.iter_expr, self._eval_in(env))
            elif n.children:
                self._apply_defaults(n.children, env)

    # -- evaluation
    @staticmethod
    def _missing(expr: str) -> Any:
        raise KeyError(expr)

    def _eval(self, expr: str) -> Any:
        return _resolve(expr, self.evaluator or self._missing)

    def _eval_in(self, env: Dict[str, Any]) -> Callable[[str], Any]:
        """Evaluator that sees the screen's local scope as well as the store.

        A bare name resolves straight from the local scope; a compound
        expression (``score > 5``) is handed to the evaluator with the scope as
        an overlay, so screen parameters are visible inside it too.
        """
        outer = self.evaluator

        def _local(expr: str) -> Any:
            if expr in env:
                return env[expr]
            if outer is None:
                raise KeyError(expr)
            try:
                return outer(expr, env)
            except TypeError:
                # a plain single-argument evaluator (tests) still works
                return outer(expr)
        return _local

    def _eval_nodes(self, nodes: List[WidgetNode], env: Dict[str, Any],
                    out: List[dict], screen: str, depth: int,
                    transclude: Optional[List[WidgetNode]],
                    props: Dict[str, str]) -> None:
        if depth > self.max_depth:
            self.errors.append(
                f"screen {screen!r}: nesting deeper than {self.max_depth} — truncated")
            return
        ev = self._eval_in(env)
        for n in nodes:
            if len(out) >= self.max_widgets:
                self.errors.append(
                    f"screen {screen!r}: more than {self.max_widgets} widgets — truncated")
                return

            if n.kind == "_prop":
                # a property of the enclosing block (`xalign .5` on its own line)
                for key, raw in n.props.items():
                    props[key] = _resolve(raw, ev)
                continue

            if n.kind == "_cond":
                self._eval_cond(n, env, out, screen, depth, transclude, props)
                continue

            if n.kind == "for":
                self._eval_for(n, env, out, screen, depth, transclude, props)
                continue

            if n.kind == "use":
                self._eval_use(n, env, out, screen, depth)
                continue

            if n.kind == "transclude":
                if transclude:
                    self._eval_nodes(transclude, env, out, screen, depth + 1,
                                     None, props)
                continue

            if n.kind == "$":
                if self.executor:
                    try:
                        self.executor(" ".join(n.code))
                    except Exception as e:
                        self.errors.append(
                            f"screen {screen!r} line {n.lineno}: {e}")
                continue

            if n.kind == "python":
                continue

            if n.kind == "default":
                continue

            # a real widget
            child_props: Dict[str, str] = {}
            children: List[dict] = []
            self._eval_nodes(n.children, env, children, screen, depth + 1,
                             transclude, child_props)
            widget = self._build_widget(n, env, ev, child_props, children,
                                        screen)
            if widget is not None:
                out.append(widget)

    def _eval_cond(self, chain: WidgetNode, env: Dict[str, Any], out: List[dict],
                   screen: str, depth: int,
                   transclude: Optional[List[WidgetNode]],
                   props: Dict[str, str]) -> None:
        ev = self._eval_in(env)
        for branch in chain.children:
            if branch.kind == "else":
                self._eval_nodes(branch.children, env, out, screen, depth + 1,
                                 transclude, props)
                return
            try:
                if bool(ev(branch.cond)):
                    self._eval_nodes(branch.children, env, out, screen,
                                     depth + 1, transclude, props)
                    return
            except Exception as e:
                self.errors.append(
                    f"screen {screen!r} line {branch.lineno}: cannot evaluate "
                    f"condition {branch.cond!r} ({e})")
                return

    def _eval_for(self, n: WidgetNode, env: Dict[str, Any], out: List[dict],
                  screen: str, depth: int,
                  transclude: Optional[List[WidgetNode]],
                  props: Dict[str, str]) -> None:
        ev = self._eval_in(env)
        try:
            items = ev(n.iter_expr)
        except Exception as e:
            self.errors.append(
                f"screen {screen!r} line {n.lineno}: cannot iterate "
                f"{n.iter_expr!r} ({e})")
            return
        if items is None:
            return
        if not hasattr(items, "__iter__"):
            self.errors.append(
                f"screen {screen!r} line {n.lineno}: {n.iter_expr!r} is not iterable")
            return
        for item in list(items):
            inner = dict(env)
            if n.target:
                inner[n.target] = item
            self._eval_nodes(n.children, inner, out, screen, depth + 1,
                             transclude, props)

    def _eval_use(self, n: WidgetNode, env: Dict[str, Any], out: List[dict],
                  screen: str, depth: int) -> None:
        """`use other(args):` — inline another screen, honouring `transclude`."""
        target = n.use_screen
        if target not in self.screens:
            self.errors.append(
                f"screen {screen!r} line {n.lineno}: use of undefined screen "
                f"{target!r}")
            return
        body = self.screens[target] or {}
        try:
            tree = parse_screen_body(body.get("lines") or [],
                                     body.get("indents"))
        except ScreenLangError as e:
            self.errors.append(f"screen {target!r}: {e}")
            return
        inner: Dict[str, Any] = dict(env)
        # positional args keep their name so the used screen's `default`s apply
        self._bind_params(body.get("params") or "", n.args, inner, target)
        self._apply_defaults(tree, inner)
        self._eval_nodes(tree, inner, out, target, depth + 1,
                         transclude=n.children or None, props={})

    def _build_widget(self, n: WidgetNode, env: Dict[str, Any],
                      ev: Callable[[str], Any], child_props: Dict[str, str],
                      children: List[dict], screen: str) -> Optional[dict]:
        # `label _("Prompt")` is a styled text, not a menu label
        kind = n.kind
        resolved: Dict[str, Any] = {k: _resolve(raw, ev)
                                    for k, raw in n.props.items()}

        text: Optional[str] = None
        if kind in ("text", "textbutton", "label"):
            parts = [_resolve(a, ev) for a in n.args]
            text = "".join(_as_text(p) for p in parts) if parts else ""
            text = _interpolate(text, ev)
        elif kind in ("add", "image", "imagebutton", "key"):
            text = _as_text(_resolve(n.args[0], ev)) if n.args else None

        merged = dict(child_props)
        for key, value in resolved.items():
            if value is None:
                # no Python value (e.g. an action object UPVN does not model):
                # keep the source text so the intent survives into the widget
                value = n.props[key]
            merged[key] = value

        widget: dict = {"kind": kind, "props": merged}
        if text is not None:
            widget["text"] = text
        if children:
            widget["children"] = children
        if n.lineno:
            widget["line"] = n.lineno
        return widget
