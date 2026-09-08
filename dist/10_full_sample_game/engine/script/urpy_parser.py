"""
UPVN — `.urpy` parser (fully declarative visual-novel language)

`.urpy` is the strict, declarative tier of the UPVN script language. It has
NO embedded Python whatsoever:

- no `$`, no `define`, no `default`, no `python:` / `init` blocks;
- state is declared in a typed `state:` block;
- characters in a `character` block;
- assets in an explicit `image` / `audio` / `stage` manifest;
- assignment is `set`, menu choices are `choice "..."`;
- blocks are closed with an explicit, REQUIRED `end`.

It compiles to exactly the same IR as the `.rpy` parser
(`{"labels", "characters", "defaults", "types", "assets"}`), so the
interpreter and the whole engine treat it identically.

For Ren'Py-compatible scripts use the `.rpy` parser (safe subset or full).
"""
from __future__ import annotations
import re
from typing import List, Dict, Any, Optional

from .lexer import group_logical_lines, LogicalLine, extract_quoted
from .ast_nodes import ASTNode, SourceLocation
from ..core.vn_errors import ParseError
from .literals import eval_literal, check_value_type, type_default, normalize_type

# ------------------------------------------------------------------ regexes
_re_label = re.compile(r"^label\s+(\w+)\s*:\s*$")
_re_state = re.compile(r"^state\s*:\s*$")
_re_state_var_typed = re.compile(r"^(\w+)\s*:\s*(int|float|str|string|bool|list)(?:\s*=\s*(.+))?\s*$")
_re_state_var_plain = re.compile(r"^(\w+)\s*=\s*(.+)\s*$")
_re_character = re.compile(r"^character\s+(\w+)\s*:\s*$")
_re_char_prop_name = re.compile(r'^name\s+(?:"([^"]+)"|\'([^\']+)\')\s*$')
_re_char_prop_color = re.compile(r'^color\s+(?:"([^"]+)"|\'([^\']+)\')\s*$')
_re_image = re.compile(r'^image\s+(?:"([^"]+)"|([A-Za-z_][\w ]*?))\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$')
_re_audio = re.compile(r'^audio\s+(\w+)\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$')
_re_stage = re.compile(r'^stage\s+(\w+)\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$')
_re_end = re.compile(r"^end\s*$")

_re_scene = re.compile(r"^scene\s+(.+?)(?:\s+with\s+(\w+))?\s*$")
_re_show = re.compile(r"^show\s+(.+?)(?:\s+with\s+(\w+))?\s*$")
_re_hide = re.compile(r"^hide\s+(\w+)(?:\s+with\s+(\w+))?\s*$")
_re_with = re.compile(r"^with\s+(\w+)\s*$")
_re_play_music = re.compile(r'^play\s+music\s+(?:"([^"]+)"|\'([^\']+)\'|(\S+))(?:\s+fadein\s+([\d.]+))?\s*$')
_re_play_sound = re.compile(r'^play\s+sound\s+(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$')
_re_play_voice = re.compile(r'^play\s+voice\s+(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$')
_re_stop = re.compile(r"^stop\s+(music|sound|voice)(?:\s+fadeout\s+([\d.]+))?\s*$")
_re_pause = re.compile(r"^pause\s+([\d.]+)\s*$")
_re_set = re.compile(r"^set\s+(\w+)\s*(\+=|-=|\*=|/=|=)\s*(.+)\s*$")
_re_jump = re.compile(r"^jump\s+(\w+)\s*$")
_re_call = re.compile(r"^call\s+(\w+)\s*$")
_re_return = re.compile(r"^return\s*$")
_re_menu = re.compile(r"^menu\s*:\s*$")
_re_choice = re.compile(r'^choice\s+(?:"([^"]+)"|\'([^\']+)\')\s*:\s*$')
_re_if = re.compile(r"^if\s+(.+)\s*:\s*$")
_re_elif = re.compile(r"^elif\s+(.+)\s*:\s*$")
_re_else = re.compile(r"^else\s*:\s*$")
_re_say = re.compile(r'^(\w+)(?:\s+(\w+))?\s+"(.*)"\s*$')
_re_nar = re.compile(r'^"(.*)"\s*$')

_re_load_stage = re.compile(r"^load_stage\s+(\w+)\s*$")
_re_show3d = re.compile(r"^show3d\s+(\w+)(?:\s+at\s+(\w+))?\s*$")
_re_anim = re.compile(r"^anim\s+(\w+)\s+(\w+)\s*$")
_re_camera = re.compile(r"^camera\s+preset\s+(\w+)\s*$")
_re_camera_zoom = re.compile(r"^camera\s+zoom\s+([\d.]+)(?:\s+duration\s+([\d.]+))?(?:\s+with\s+(\w+))?\s*$")
_re_camera_zoom_alt = re.compile(r"^camera\s+zoom\s+([\d.]+)(?:\s+with\s+(\w+))?(?:\s+duration\s+([\d.]+))?\s*$")

# statements that belong to the .rpy tiers, not urpy
_FORBIDDEN_HINTS = [
    (re.compile(r"^\$\s"), "$ assignment is not allowed in .urpy — use: set var = value"),
    (re.compile(r"^define\s"), "define is not allowed in .urpy — use a character block"),
    (re.compile(r"^default\s"), "default is not allowed in .urpy — declare variables in a state: block"),
    (re.compile(r"^python\s*:"), "python: blocks are not allowed in .urpy (it is fully declarative)"),
    (re.compile(r"^init\b"), "init blocks are not allowed in .urpy"),
    (re.compile(r"^transform\b"), "transform/ATL belongs to the .rpy full tier, not .urpy"),
    (re.compile(r"^screen\b"), "screen language belongs to the .rpy full tier, not .urpy"),
    (re.compile(r"^style\b"), "style statements belong to the .rpy full tier, not .urpy"),
    (re.compile(r"^translate\b"), "translate blocks belong to the .rpy full tier, not .urpy"),
]


class UrpyParser:
    def __init__(self, source: str, filename: str = "<string>", require_start: bool = True):
        self.filename = filename
        self.require_start = require_start
        self.lines: List[LogicalLine] = group_logical_lines(source, filename)
        self.pos = 0
        self.labels: Dict[str, List[dict]] = {}
        self.defaults: Dict[str, Any] = {}
        self.characters: Dict[str, dict] = {}
        self.types: Dict[str, str] = {}
        self.assets: Dict[str, Dict[str, str]] = {"images": {}, "audio": {}, "stages": {}}

    # ------------------------------------------------------------------ public
    def parse(self) -> dict:
        if not self.lines:
            raise ParseError("empty script", self.filename, 1)
        while self.pos < len(self.lines):
            ll = self.lines[self.pos]
            if ll.indent != 0:
                raise ParseError(
                    f"top-level statement must not be indented (found {ll.indent} spaces)",
                    ll.filename, ll.lineno, ll.indent + 1, ll.raw,
                    hint="state:/character:/image/audio/stage/label start at column 0",
                )
            self._parse_top_level(ll)
        if self.require_start and "start" not in self.labels:
            raise ParseError('missing required label "start:"', self.filename, 1, hint='add:\nlabel start:\n    "Hello."\nend')
        return {
            "labels": self.labels,
            "characters": self.characters,
            "defaults": self.defaults,
            "types": self.types,
            "assets": self.assets,
            "language": "urpy",
        }

    # ------------------------------------------------------------------ top level
    def _parse_top_level(self, ll: LogicalLine):
        t = ll.text

        # forbidden .rpy-tier constructs — friendly guidance
        for pat, hint in _FORBIDDEN_HINTS:
            if pat.match(t):
                raise ParseError(f"{t!r} is not part of .urpy", ll.filename, ll.lineno, 1, ll.raw, hint=hint)

        if _re_state.match(t):
            return self._parse_state_block(ll)
        m = _re_character.match(t)
        if m:
            return self._parse_character_block(ll, m.group(1))
        m = _re_image.match(t)
        if m:
            name = m.group(1) if m.group(1) is not None else (m.group(2) or "").strip()
            path = m.group(3) or m.group(4) or m.group(5)
            self.assets["images"][name] = path
            self.pos += 1
            return
        m = _re_audio.match(t)
        if m:
            self.assets["audio"][m.group(1)] = m.group(2) or m.group(3) or m.group(4)
            self.pos += 1
            return
        m = _re_stage.match(t)
        if m:
            self.assets["stages"][m.group(1)] = m.group(2) or m.group(3) or m.group(4)
            self.pos += 1
            return
        m = _re_label.match(t)
        if m:
            label = m.group(1)
            if label in self.labels:
                raise ParseError(f'duplicate label "{label}"', ll.filename, ll.lineno, 1, ll.raw)
            self.labels[label] = []
            self.pos += 1
            self._parse_block(0, self.labels[label])
            self._require_end(0, "label", ll)
            return
        if t.startswith("label ") and not t.strip().endswith(":"):
            raise ParseError(f'label needs a colon — got: {t!r}', ll.filename, ll.lineno, 1, ll.raw, hint='use: label start:')
        if _re_end.match(t):
            raise ParseError("unexpected 'end' — no open block to close", ll.filename, ll.lineno, 1, ll.raw,
                             hint="remove this 'end', or it may be mis-indented")
        raise ParseError(
            f'expected "state", "character", "image", "audio", "stage" or "label" at top level, got: {t!r}',
            ll.filename, ll.lineno, 1, ll.raw,
            hint='example:\nstate:\n    affection: int = 0\nend\n\nlabel start:\n    "Hello."\nend',
        )

    def _parse_state_block(self, ll: LogicalLine):
        self.pos += 1
        ind = ll.indent + 4
        while self.pos < len(self.lines):
            nxt = self.lines[self.pos]
            if nxt.indent < ind:
                break
            if nxt.indent != ind:
                raise ParseError(f"state declaration must be indented {ind} spaces", nxt.filename, nxt.lineno,
                                 nxt.indent + 1, nxt.raw, hint=f"indent this line to {ind} spaces")
            t = nxt.text
            if _re_end.match(t):
                raise ParseError("unexpected 'end' inside state block", nxt.filename, nxt.lineno, 1, nxt.raw,
                                 hint="'end' closes the state block — dedent it to the same level as 'state:'")
            m = _re_state_var_typed.match(t)
            if m:
                var, type_name, val_expr = m.group(1), m.group(2), m.group(3)
                typ = normalize_type(type_name)
                if val_expr is not None:
                    try:
                        val = eval_literal(val_expr.strip())
                    except (ValueError, SyntaxError, MemoryError, RecursionError):
                        raise ParseError(f'state value must be a literal (got {val_expr!r})', nxt.filename, nxt.lineno, 1, nxt.raw,
                                         hint="use a literal: 0, 1.5, \"text\", true/false? no — True/False, [1, 2]")
                    ok, err = check_value_type(val, typ)
                    if not ok:
                        raise ParseError(f"type mismatch: {var!r} is declared {typ}, but value is {type(val).__name__}",
                                         nxt.filename, nxt.lineno, 1, nxt.raw,
                                         hint=f"declare it with a {typ} value, e.g. {var}: {typ} = 0")
                else:
                    val = type_default(typ)
                if var in self.defaults:
                    raise ParseError(f"duplicate variable declaration {var!r}", nxt.filename, nxt.lineno, 1, nxt.raw,
                                     hint="declare each variable once in state:")
                self.defaults[var] = val
                self.types[var] = typ
                self.pos += 1
                continue
            m = _re_state_var_plain.match(t)
            if m:
                var, val_expr = m.group(1), m.group(2).strip()
                try:
                    val = eval_literal(val_expr)
                except (ValueError, SyntaxError, MemoryError, RecursionError):
                    raise ParseError(f'state value must be a literal (got {val_expr!r})', nxt.filename, nxt.lineno, 1, nxt.raw,
                                     hint="use a literal: 0, 1.5, \"text\", True, [1, 2]")
                if var in self.defaults:
                    raise ParseError(f"duplicate variable declaration {var!r}", nxt.filename, nxt.lineno, 1, nxt.raw,
                                     hint="declare each variable once in state:")
                self.defaults[var] = val
                self.pos += 1
                continue
            raise ParseError(f"invalid state declaration: {t!r}", nxt.filename, nxt.lineno, 1, nxt.raw,
                             hint='use: name: type = value   e.g. affection: int = 0  (types: int, float, str, bool, list)')
        self._require_end(ll.indent, "state", ll)

    def _parse_character_block(self, ll: LogicalLine, cid: str):
        self.pos += 1
        ind = ll.indent + 4
        name = cid
        color = "#ffffff"
        while self.pos < len(self.lines):
            nxt = self.lines[self.pos]
            if nxt.indent < ind:
                break
            if nxt.indent != ind:
                raise ParseError(f"character property must be indented {ind} spaces", nxt.filename, nxt.lineno,
                                 nxt.indent + 1, nxt.raw, hint=f"indent this line to {ind} spaces")
            t = nxt.text
            m = _re_char_prop_name.match(t)
            if m:
                name = m.group(1) if m.group(1) is not None else m.group(2)
                self.pos += 1
                continue
            m = _re_char_prop_color.match(t)
            if m:
                color = m.group(1) if m.group(1) is not None else m.group(2)
                self.pos += 1
                continue
            raise ParseError(f"unknown character property: {t!r}", nxt.filename, nxt.lineno, 1, nxt.raw,
                             hint='character properties: name "..." and color "#..."')
        if cid in self.characters:
            raise ParseError(f'duplicate character "{cid}"', ll.filename, ll.lineno, 1, ll.raw, hint="define each character once")
        self.characters[cid] = {"name": name, "color": color, "extra": {}}
        self._require_end(ll.indent, "character", ll)

    # ------------------------------------------------------------------ blocks
    def _require_end(self, indent: int, kind: str, ll: LogicalLine):
        if self.pos < len(self.lines):
            nxt = self.lines[self.pos]
            if _re_end.match(nxt.text) and nxt.indent == indent:
                self.pos += 1
                return
        raise ParseError(f"missing 'end' for {kind} block", ll.filename, ll.lineno, 1, ll.raw,
                         hint=f".urpy requires an explicit 'end' dedented to the same level as '{kind}:'")

    def _parse_block(self, parent_indent: int, out: List[dict]):
        while self.pos < len(self.lines):
            ll = self.lines[self.pos]
            if ll.indent <= parent_indent:
                return
            expected = parent_indent + 4
            if ll.indent != expected:
                raise ParseError(
                    f"expected {expected} spaces, got {ll.indent}",
                    ll.filename, ll.lineno, ll.indent + 1, ll.raw,
                    hint=f"indent this line to {expected} spaces (4 per level)",
                )
            self._parse_statement(ll, out)

    def _parse_statement(self, ll: LogicalLine, out: List[dict]):
        t = ll.text
        for pat, hint in _FORBIDDEN_HINTS:
            if pat.match(t):
                raise ParseError(f"{t!r} is not part of .urpy", ll.filename, ll.lineno, 1, ll.raw, hint=hint)

        m = _re_scene.match(t)
        if m:
            out.append(ASTNode("scene", {"asset": m.group(1).strip(), "transition": m.group(2)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        m = _re_show.match(t)
        if m:
            asset, trans = m.group(1).strip(), m.group(2)
            position = None
            if " at " in asset:
                asset, position = asset.rsplit(" at ", 1)
                asset = asset.strip()
                position = position.strip()
            tag = asset.split()[0] if asset else asset
            out.append(ASTNode("show", {"asset": asset, "tag": tag, "position": position, "transition": trans},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        m = _re_hide.match(t)
        if m:
            out.append(ASTNode("hide", {"tag": m.group(1), "transition": m.group(2)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        m = _re_with.match(t)
        if m:
            out.append(ASTNode("with", {"transition": m.group(1)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        m = _re_play_music.match(t)
        if m:
            asset = m.group(1) or m.group(2) or m.group(3)
            fadein = float(m.group(4)) if m.group(4) else None
            out.append(ASTNode("play_music", {"asset": asset, "fadein": fadein},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        m = _re_play_sound.match(t)
        if m:
            out.append(ASTNode("play_sound", {"asset": m.group(1) or m.group(2) or m.group(3)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        m = _re_play_voice.match(t)
        if m:
            out.append(ASTNode("play_voice", {"asset": m.group(1) or m.group(2) or m.group(3)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        m = _re_stop.match(t)
        if m:
            out.append(ASTNode(f"stop_{m.group(1)}", {"fadeout": float(m.group(2)) if m.group(2) else None},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        m = _re_pause.match(t)
        if m:
            out.append(ASTNode("pause", {"duration": float(m.group(1))},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        m = _re_load_stage.match(t)
        if m:
            out.append(ASTNode("load_stage", {"stage": m.group(1)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        m = _re_show3d.match(t)
        if m:
            out.append(ASTNode("show3d", {"asset": m.group(1), "marker": m.group(2)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        m = _re_anim.match(t)
        if m:
            out.append(ASTNode("anim", {"target": m.group(1), "animation": m.group(2)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        m = _re_camera_zoom.match(t) or _re_camera_zoom_alt.match(t)
        if m:
            zoom = float(m.group(1))
            dur, ease = None, None
            g2, g3 = m.group(2), m.group(3)
            if g2 is not None:
                try:
                    dur = float(g2)
                except ValueError:
                    ease = g2
            if g3 is not None:
                try:
                    if dur is None:
                        dur = float(g3)
                    else:
                        ease = g3
                except ValueError:
                    ease = g3
            out.append(ASTNode("camera_zoom", {"zoom": zoom, "duration": dur or 1.0, "easing": ease or "ease"},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        m = _re_camera.match(t)
        if m:
            out.append(ASTNode("camera_preset", {"name": m.group(1)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return

        m = _re_jump.match(t)
        if m:
            out.append(ASTNode("jump", {"label": m.group(1)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        m = _re_call.match(t)
        if m:
            out.append(ASTNode("call", {"label": m.group(1)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        if _re_return.match(t):
            out.append(ASTNode("return", {},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return

        m = _re_set.match(t)
        if m:
            out.append(ASTNode("assign", {"target": m.group(1), "op": m.group(2), "expr": m.group(3).strip()},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return

        if _re_menu.match(t):
            return self._parse_menu(ll, out)

        m = _re_if.match(t)
        if m:
            return self._parse_if_chain(ll, out)
        if _re_elif.match(t) or _re_else.match(t):
            raise ParseError(f'"{t.split()[0]}" without matching "if"', ll.filename, ll.lineno, 1, ll.raw)

        m = _re_say.match(t)
        if m:
            out.append(ASTNode("say", {"who": m.group(1), "expression": m.group(2), "text": m.group(3)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return
        m = _re_nar.match(t)
        if m:
            out.append(ASTNode("say", {"who": None, "text": m.group(1)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
            self.pos += 1
            return

        if _re_end.match(t):
            raise ParseError("unexpected 'end' — no open block to close", ll.filename, ll.lineno, 1, ll.raw,
                             hint="'end' must be dedented to the same level as the block it closes")
        raise ParseError(f"unknown statement: {t!r}", ll.filename, ll.lineno, 1, ll.raw,
                         hint="check spelling and indentation (4 spaces per level, spaces not tabs)")

    def _parse_menu(self, ll: LogicalLine, out: List[dict]):
        menu_node = ASTNode("menu", {"choices": []},
                            SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict()
        menu_indent = ll.indent
        self.pos += 1
        while self.pos < len(self.lines):
            c = self.lines[self.pos]
            if c.indent <= menu_indent:
                break
            if c.indent != menu_indent + 4:
                raise ParseError(f"choice must be indented {menu_indent + 4} spaces, got {c.indent}",
                                 c.filename, c.lineno, c.indent + 1, c.raw,
                                 hint='inside menu:\n    choice "Text":\n        ...\n    end')
            t = c.text
            # optional caption — bare quoted line before the first choice
            if not menu_node["choices"] and "caption" not in menu_node and not _re_choice.match(t):
                q = extract_quoted(t.strip())
                if q and not t.rstrip().endswith(":"):
                    menu_node["caption"] = q[0]
                    self.pos += 1
                    continue
            m = _re_choice.match(t)
            if not m:
                raise ParseError(f"menu choices must use 'choice \"Text\":' in .urpy, got: {t!r}",
                                 c.filename, c.lineno, 1, c.raw,
                                 hint='use: choice "Text":\n    ...\nend')
            text = m.group(1) if m.group(1) is not None else m.group(2)
            self.pos += 1
            block: List[dict] = []
            if self.pos < len(self.lines) and self.lines[self.pos].indent > c.indent:
                if self.lines[self.pos].indent != c.indent + 4:
                    raise ParseError(f"choice body must be indented {c.indent + 4} spaces",
                                     self.lines[self.pos].filename, self.lines[self.pos].lineno, 1, self.lines[self.pos].raw)
                self._parse_block(c.indent, block)
            self._require_end(c.indent, "choice", c)
            menu_node["choices"].append({"text": text, "block": block,
                                         "_loc": {"file": c.filename, "line": c.lineno}})
        if not menu_node["choices"]:
            raise ParseError("menu has no choices", ll.filename, ll.lineno, 1, ll.raw)
        self._require_end(menu_indent, "menu", ll)
        out.append(menu_node)

    def _parse_if_chain(self, ll: LogicalLine, out: List[dict]):
        branches = []
        m = _re_if.match(ll.text)
        cond = m.group(1).strip()
        self.pos += 1
        block: List[dict] = []
        if self.pos < len(self.lines) and self.lines[self.pos].indent > ll.indent:
            if self.lines[self.pos].indent != ll.indent + 4:
                raise ParseError("if body must be indented 4 spaces", self.lines[self.pos].filename,
                                 self.lines[self.pos].lineno, 1, self.lines[self.pos].raw)
            self._parse_block(ll.indent, block)
        branches.append({"cond": cond, "block": block})

        while self.pos < len(self.lines):
            nxt = self.lines[self.pos]
            if nxt.indent != ll.indent:
                break
            m2 = _re_elif.match(nxt.text)
            if m2:
                self.pos += 1
                blk: List[dict] = []
                if self.pos < len(self.lines) and self.lines[self.pos].indent > nxt.indent:
                    if self.lines[self.pos].indent != nxt.indent + 4:
                        raise ParseError("elif body must be indented 4 spaces", self.lines[self.pos].filename,
                                         self.lines[self.pos].lineno, 1, self.lines[self.pos].raw)
                    self._parse_block(nxt.indent, blk)
                branches.append({"cond": m2.group(1).strip(), "block": blk})
                continue
            if _re_else.match(nxt.text):
                self.pos += 1
                blk3: List[dict] = []
                if self.pos < len(self.lines) and self.lines[self.pos].indent > nxt.indent:
                    if self.lines[self.pos].indent != nxt.indent + 4:
                        raise ParseError("else body must be indented 4 spaces", self.lines[self.pos].filename,
                                         self.lines[self.pos].lineno, 1, self.lines[self.pos].raw)
                    self._parse_block(nxt.indent, blk3)
                branches.append({"cond": None, "block": blk3})
                continue
            break
        self._require_end(ll.indent, "if", ll)
        out.append(ASTNode("if", {"branches": branches},
                           SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())


def parse_urpy_string(source: str, filename: str = "<string>", require_start: bool = True) -> dict:
    return UrpyParser(source, filename, require_start=require_start).parse()


def parse_urpy_file(path: str, require_start: bool = True) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return parse_urpy_string(f.read(), filename=path, require_start=require_start)
