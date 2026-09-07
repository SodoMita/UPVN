"""
UPVN — Parser for Ren'Py-subset .rpy (Tier1 + The Question)

Direct .rpy → AST, no intermediate YAML/JSON file.
Mirrors Ren'Py's own parser pipeline (renpy/parser.py) but subset and with
friendly errors.

Supported for v0.1:
    define s = Character(_("Sylvie"), color="#c8ffc8")
    define s = Character("Sylvie")
    default book = False
    label start:
    scene bg lecturehall / scene black
    scene bg lecturehall with fade
    show sylvie green normal
    show sylvie green smile with dissolve
    hide sylvie
    with fade / with dissolve   (standalone, applies to previous)
    play music "illurock.opus"  / play music "theme" fadein 1.0
    stop music fadeout 1.0
    play sound "sfx.ogg"
    s "Dialogue text with [var] interpolation and {b} tags {/b}"
    "Narration text"
    menu:
        "Prompt text"  (optional narrator menu caption)
        "To ask her right away.":
            jump rightaway
        "To ask her later.":
            jump later
    jump label
    call label
    return
    $ book = True
    $ affection += 1
    if book:
    elif other:
    else:
    # comments and blank lines ignored

No inline `python:` / `init python` blocks — story script is declarative.
Extension code lives in .py plugins (see docs; LLM can add python via
explicit commands, not embedded blocks).

Parser output:
    {
      "labels": { "start": [ nodes... ], ... },
      "characters": { ... },   # collected defines
      "defaults": { ... },
      "ast_flat": [ ... ]   # optional trace order
    }
Each label's value is list[ASTNode.to_dict()] — JSON-serialisable
and suitable for interpreter + golden-trace tests.
"""
from __future__ import annotations
import ast
import re
from typing import List, Dict, Any, Optional, Tuple
from .lexer import group_logical_lines, LogicalLine, extract_quoted
from .ast_nodes import ASTNode, SourceLocation
from ..core.vn_errors import ParseError

# ------------------------------------------------------------------ regexes
_re_label = re.compile(r"^label\s+(\w+)\s*:\s*$")
_re_define = re.compile(r'^define\s+(\w+)\s*=\s*Character\s*\((.*)\)\s*$')
_re_default = re.compile(r"^default\s+(\w+)\s*=\s*(.+)\s*$")
_re_scene = re.compile(r"^scene\s+(.+?)(?:\s+with\s+(\w+))?\s*$")
_re_show = re.compile(r"^show\s+(.+?)(?:\s+with\s+(\w+))?\s*$")
_re_hide = re.compile(r"^hide\s+(\w+)(?:\s+with\s+(\w+))?\s*$")
_re_with = re.compile(r"^with\s+(\w+)\s*$")
_re_play_music = re.compile(r'^play\s+music\s+(?:"([^"]+)"|\'([^\']+)\'|(\S+))(?:\s+fadein\s+([\d.]+))?\s*$')
_re_play_sound = re.compile(r'^play\s+sound\s+(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$')
_re_play_voice = re.compile(r'^play\s+voice\s+(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$')
_re_stop = re.compile(r"^stop\s+(music|sound|voice)(?:\s+fadeout\s+([\d.]+))?\s*$")
_re_jump = re.compile(r"^jump\s+(\w+)\s*$")
_re_call = re.compile(r"^call\s+(\w+)\s*$")
_re_return = re.compile(r"^return\s*$")
_re_menu = re.compile(r"^menu\s*:\s*$")
_re_if = re.compile(r"^if\s+(.+)\s*:\s*$")
_re_elif = re.compile(r"^elif\s+(.+)\s*:\s*$")
_re_else = re.compile(r"^else\s*:\s*$")
_re_assign = re.compile(r"^\$\s*(.+)\s*$")
_re_pause = re.compile(r"^pause\s+([\d.]+)\s*$")
# 3D stubs — python-driven but parseable
_re_load_stage = re.compile(r"^load_stage\s+(\w+)\s*$")
_re_show3d = re.compile(r"^show3d\s+(\w+)(?:\s+at\s+(\w+))?\s*$")
_re_anim = re.compile(r"^anim\s+(\w+)\s+(\w+)\s*$")
_re_camera = re.compile(r"^camera\s+preset\s+(\w+)\s*$")
_re_camera_zoom = re.compile(r"^camera\s+zoom\s+([\d.]+)(?:\s+duration\s+([\d.]+))?(?:\s+with\s+(\w+))?\s*$")
_re_camera_zoom_alt = re.compile(r"^camera\s+zoom\s+([\d.]+)(?:\s+with\s+(\w+))?(?:\s+duration\s+([\d.]+))?\s*$")

# say:  s "text"  or  e happy "text"
_re_say = re.compile(r'^(\w+)(?:\s+(\w+))?\s+"(.*)"\s*$')
_re_nar = re.compile(r'^"(.*)"\s*$')

# Character args parser (very subset): _("Name") or "Name", color="#..."
_re_char_name_tr = re.compile(r'_\(\s*"(.*?)"\s*\)')
_re_color = re.compile(r'color\s*=\s*["\'](.*?)["\']')

# ------------------------------------------------------------------ declarative forms (M15)
# `set` -- canonical assignment (declarative); `$` remains a legacy alias
_re_set = re.compile(r"^set\s+(\w+)\s*(\+=|-=|\*=|/=|=)\s*(.+)\s*$")
# `state:` block with typed declarations
_re_state = re.compile(r"^state\s*:\s*$")
_re_state_var_typed = re.compile(r"^(\w+)\s*:\s*(int|float|str|string|bool|list)(?:\s*=\s*(.+))?\s*$")
_re_state_var_plain = re.compile(r"^(\w+)\s*=\s*(.+)\s*$")
# `character` block -- declarative character definition
_re_character = re.compile(r"^character\s+(\w+)\s*:\s*$")
_re_char_prop_name = re.compile(r'^name\s+(?:"([^"]+)"|\'([^\']+)\')\s*$')
_re_char_prop_color = re.compile(r'^color\s+(?:"([^"]+)"|\'([^\']+)\')\s*$')
# declarative asset manifest
_re_image = re.compile(r'^image\s+(?:"([^"]+)"|([A-Za-z_][\w ]*?))\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$')
_re_audio = re.compile(r'^audio\s+(\w+)\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$')
_re_stage = re.compile(r'^stage\s+(\w+)\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$')
# `choice` keyword inside menus (declarative alternative to bare quoted choice)
_re_choice = re.compile(r'^choice\s+(?:"([^"]+)"|\'([^\']+)\')\s*:\s*$')
# explicit block terminator
_re_end = re.compile(r"^end\s*$")

def _parse_character_args(inner: str) -> Tuple[str, str, dict]:
    # inner is inside Character(...)
    # Try translatable first
    m = _re_char_name_tr.search(inner)
    if m:
        name = m.group(1)
    else:
        m2 = re.search(r'"([^"]+)"', inner)
        if m2:
            name = m2.group(1)
        else:
            m3 = re.search(r"'([^']+)'", inner)
            name = m3.group(1) if m3 else "??"
    color = "#ffffff"
    mc = _re_color.search(inner)
    if mc:
        color = mc.group(1)
    extra = {}
    return name, color, extra


class Parser:
    def __init__(self, source: str, filename: str = "<string>"):
        self.filename = filename
        self.lines: List[LogicalLine] = group_logical_lines(source, filename)
        self.pos = 0
        # outputs
        self.labels: Dict[str, List[dict]] = {}
        self.defaults: Dict[str, Any] = {}
        self.characters: Dict[str, dict] = {}
        self.types: Dict[str, str] = {}  # declarative `state:` type declarations
        self.assets: Dict[str, Dict[str, str]] = {"images": {}, "audio": {}, "stages": {}}
        # current label being filled
        self._current_label: Optional[str] = None
        self._current_list: Optional[List[dict]] = None
        # indent stack for block handling — start at 0
        self._indent_stack: List[int] = [0]

    # ---------------------------- public
    def parse(self) -> dict:
        if not self.lines:
            raise ParseError("empty script", self.filename, 1)

        # Pre-scan must have at least one label
        # We'll parse top-level sequentially
        # Top-level indent must be 0
        while self.pos < len(self.lines):
            ll = self.lines[self.pos]
            if ll.indent != 0:
                raise ParseError(
                    f"top-level statement must not be indented (found {ll.indent} spaces)",
                    ll.filename, ll.lineno, ll.indent + 1, ll.raw,
                    hint="labels, defines and defaults start at column 0",
                )
            self._parse_top_level(ll)
            # _parse_top_level advances pos as needed

        if "start" not in self.labels:
            raise ParseError('missing required label "start:"', self.filename, 1, hint='add:\nlabel start:\n    "Hello."')

        return {
            "labels": self.labels,
            "characters": self.characters,
            "defaults": self.defaults,
            "types": self.types,
            "assets": self.assets,
        }

    # ---------------------------- top-level dispatch
    def _parse_top_level(self, ll: LogicalLine):
        t = ll.text

        # define — with friendly hint for missing parens
        if t.startswith("define ") and "Character" in t and not _re_define.match(t):
            # try to detect malformed define
            if "Character" in t and "(" not in t:
                raise ParseError('define missing parentheses: expected define e = Character("Name")',
                                 ll.filename, ll.lineno, 1, ll.raw,
                                 hint='use: define e = Character("Eileen", color="#c8ffc8")')
            if "Character" in t and t.count("(") != t.count(")"):
                raise ParseError('define parentheses mismatch', ll.filename, ll.lineno, 1, ll.raw,
                                 hint='use: define e = Character("Eileen")')
        m = _re_define.match(t)
        if m:
            cid, inner = m.group(1), m.group(2)
            name, color, extra = _parse_character_args(inner)
            node = ASTNode("define_character", {"id": cid, "name": name, "color": color, "extra": extra},
                           SourceLocation(ll.filename, ll.lineno, ll.indent + 1))
            self.characters[cid] = {"name": name, "color": color, "extra": extra}
            # also keep as global header node? store in defaults list under "__init__"
            # For simplicity, ensure there's a implicit init label for defines? But interpreter reads self.characters dict directly.
            self.pos += 1
            return

        # default
        m = _re_default.match(t)
        if m:
            var, expr = m.group(1), m.group(2).strip()
            val = self._eval_literal(expr, ll)
            self.defaults[var] = val
            # also record node? defaults are handled as initial variables, not as executable statements.
            # But we also emit a default node for inspection.
            self.pos += 1
            return

        # state: block — declarative typed variable declarations
        if _re_state.match(t):
            self._parse_state_block(ll)
            return

        # character block — declarative character definition
        m = _re_character.match(t)
        if m:
            self._parse_character_block(ll, m.group(1))
            return

        # declarative asset manifest: image / audio / stage
        m = _re_image.match(t)
        if m:
            name = m.group(1) if m.group(1) is not None else (m.group(2) or "").strip()
            path = m.group(3) or m.group(4) or m.group(5)
            if not name:
                raise ParseError("image declaration needs a name", ll.filename, ll.lineno, 1, ll.raw,
                                 hint='use: image "bg classroom" = "backgrounds/classroom.png"')
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

        # label
        m = _re_label.match(t)
        if m:
            label = m.group(1)
            if label in self.labels:
                raise ParseError(f'duplicate label "{label}"', ll.filename, ll.lineno, 1, ll.raw)
            self._current_label = label
            self._current_list = []
            self.labels[label] = self._current_list
            self.pos += 1
            # parse its indented block
            self._parse_block(parent_indent=0, out=self._current_list)
            self._consume_end(0, "label")
            self._current_label = None
            self._current_list = None
            return

        # explicit end at top level with no open label
        if _re_end.match(t):
            raise ParseError("unexpected 'end' — no open block to close", ll.filename, ll.lineno, 1, ll.raw,
                             hint="remove this 'end', or it may be mis-indented")

        # friendly hint for common top-level mistakes
        if t.startswith("label ") and not t.strip().endswith(":"):
            raise ParseError(f'label needs a colon — got: {t!r}',
                             ll.filename, ll.lineno, 1, ll.raw,
                             hint='use: label start:')
        if t.startswith("define ") and "Character" in t:
            raise ParseError(f'define syntax error: {t!r}',
                             ll.filename, ll.lineno, 1, ll.raw,
                             hint='use: define e = Character("Eileen", color="#c8ffc8")')
        if t.startswith("character") and not t.strip().endswith(":"):
            raise ParseError(f'character block needs a colon — got: {t!r}',
                             ll.filename, ll.lineno, 1, ll.raw,
                             hint='use: character e:\n    name "Eileen"\n    color "#c8ffc8"')
        if t.startswith("state") and not t.strip().endswith(":"):
            raise ParseError(f'state block needs a colon — got: {t!r}',
                             ll.filename, ll.lineno, 1, ll.raw,
                             hint='use: state:\n    affection: int = 0')
        raise ParseError(
            f'expected "label", "define", "default", "state", "character", "image", "audio" or "stage" at top level, got: {t!r}',
            ll.filename, ll.lineno, 1, ll.raw,
            hint='example:\nlabel start:\n    "Hello."\ndefine e = Character("Eileen")'
        )

    # ---------------------------- declarative blocks (M15)
    def _consume_end(self, indent: int, kind: str) -> bool:
        """Consume an optional explicit `end` at the given indent. Returns True if consumed."""
        if self.pos < len(self.lines):
            nxt = self.lines[self.pos]
            if _re_end.match(nxt.text) and nxt.indent == indent:
                self.pos += 1
                return True
        return False

    def _parse_state_block(self, ll: LogicalLine):
        """`state:` block — typed variable declarations at indent+4, optional `end`."""
        self.pos += 1
        block_indent = ll.indent + 4
        seen: Dict[str, str] = {}
        while self.pos < len(self.lines):
            nxt = self.lines[self.pos]
            if nxt.indent <= ll.indent:
                break
            if nxt.indent != block_indent:
                raise ParseError(
                    f"state declaration must be indented {block_indent} spaces, got {nxt.indent}",
                    nxt.filename, nxt.lineno, nxt.indent + 1, nxt.raw,
                    hint=f"indent this line to {block_indent} spaces (4 per level)",
                )
            if _re_end.match(nxt.text):
                raise ParseError("unexpected 'end' inside state block", nxt.filename, nxt.lineno, 1, nxt.raw,
                                 hint="end closes the whole state block — it must be dedented to the same level as 'state:'")
            t = nxt.text
            m = _re_state_var_typed.match(t)
            if m:
                var, type_name, val_expr = m.group(1), m.group(2), m.group(3)
                typ = "str" if type_name == "string" else type_name
                if val_expr is not None:
                    val = self._eval_literal(val_expr.strip(), nxt)
                    self._check_declared_type(var, typ, val, nxt)
                else:
                    val = {"int": 0, "float": 0.0, "str": "", "bool": False, "list": []}[typ]
                if var in self.defaults:
                    raise ParseError(f"duplicate variable declaration {var!r}", nxt.filename, nxt.lineno, 1, nxt.raw,
                                     hint="declare each variable once in state:")
                self.defaults[var] = val
                self.types[var] = typ
                seen[var] = typ
                self.pos += 1
                continue
            m = _re_state_var_plain.match(t)
            if m:
                var, val_expr = m.group(1), m.group(2).strip()
                val = self._eval_literal(val_expr, nxt)
                if var in self.defaults:
                    raise ParseError(f"duplicate variable declaration {var!r}", nxt.filename, nxt.lineno, 1, nxt.raw,
                                     hint="declare each variable once in state:")
                self.defaults[var] = val
                self.pos += 1
                continue
            raise ParseError(f"invalid state declaration: {t!r}", nxt.filename, nxt.lineno, 1, nxt.raw,
                             hint='use: name: type = value   e.g. affection: int = 0  (types: int, float, str, bool, list)')
        self._consume_end(ll.indent, "state")

    def _parse_character_block(self, ll: LogicalLine, cid: str):
        """`character id:` block — name/color properties at indent+4, optional `end`."""
        self.pos += 1
        block_indent = ll.indent + 4
        name = cid
        color = "#ffffff"
        props: Dict[str, str] = {}
        while self.pos < len(self.lines):
            nxt = self.lines[self.pos]
            if nxt.indent <= ll.indent:
                break
            if nxt.indent != block_indent:
                raise ParseError(
                    f"character property must be indented {block_indent} spaces, got {nxt.indent}",
                    nxt.filename, nxt.lineno, nxt.indent + 1, nxt.raw,
                    hint=f"indent this line to {block_indent} spaces (4 per level)",
                )
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
            raise ParseError(f'duplicate character "{cid}"', ll.filename, ll.lineno, 1, ll.raw,
                             hint="define each character once")
        self.characters[cid] = {"name": name, "color": color, "extra": props}
        self._consume_end(ll.indent, "character")

    def _check_declared_type(self, var: str, typ: str, val, ll: LogicalLine):
        """Validate a state: literal against its declared type."""
        ok = False
        if typ == "int":
            ok = (not isinstance(val, bool)) and isinstance(val, int)
        elif typ == "float":
            ok = (not isinstance(val, bool)) and isinstance(val, (int, float))
        elif typ == "str":
            ok = isinstance(val, str)
        elif typ == "bool":
            ok = isinstance(val, bool)
        elif typ == "list":
            ok = isinstance(val, list)
        if not ok:
            raise ParseError(
                f"type mismatch: {var!r} is declared {typ}, but value is {type(val).__name__}",
                ll.filename, ll.lineno, 1, ll.raw,
                hint=f"declare it with a {typ} value, e.g. {var}: {typ} = 0",
            )

    # ---------------------------- block parsing (indent-sensitive)
    def _parse_block(self, parent_indent: int, out: List[dict]):
        """
        Consume lines whose indent > parent_indent and emit nodes into out.
        Stops when next line indent <= parent_indent (sibling / dedent).
        """
        while self.pos < len(self.lines):
            ll = self.lines[self.pos]
            if ll.indent <= parent_indent:
                # dedent — end of this block
                return
            # Must be exactly parent_indent + 4? We allow any > but warn if not 4
            expected = parent_indent + 4
            if ll.indent != expected:
                # friendly hint per doc §11 syntax error gallery
                if ll.indent < expected:
                    raise ParseError(
                        f"unexpected dedent: expected {expected} spaces, got {ll.indent}",
                        ll.filename, ll.lineno, ll.indent + 1, ll.raw,
                        hint=f"indent this line to {expected} spaces (4 per level)"
                    )
                elif ll.indent > expected:
                    raise ParseError(
                        f"unexpected indent: expected {expected} spaces, got {ll.indent}",
                        ll.filename, ll.lineno, ll.indent + 1, ll.raw,
                        hint=f"too many spaces — expected {expected}"
                    )

            # Now dispatch statement types that can appear inside a label/menu/if
            self._parse_statement(ll, parent_indent=ll.indent, out=out)
            # _parse_statement advances pos; if it consumed a sub-block, pos already after
            # else it did pos+=1

    def _parse_statement(self, ll: LogicalLine, parent_indent: int, out: List[dict]):
        t = ll.text

        # ---- scene
        m = _re_scene.match(t)
        if m:
            asset, trans = m.group(1).strip(), m.group(2)
            node = ASTNode("scene", {"asset": asset, "transition": trans}, SourceLocation(ll.filename, ll.lineno, ll.indent+1))
            out.append(node.to_dict())
            self.pos += 1
            return

        # ---- show
        m = _re_show.match(t)
        if m:
            asset, trans = m.group(1).strip(), m.group(2)
            # asset may include position: "sylvie green smile at left" — naive split
            # For Tier1: keep whole asset string, let renderer split tag/position later.
            # Extract position if " at " present
            position = None
            if " at " in asset:
                asset_part, position = asset.rsplit(" at ", 1)
                asset = asset_part.strip()
                position = position.strip()
            # tag is first word of asset
            tag = asset.split()[0] if asset else asset
            node = ASTNode("show", {"asset": asset, "tag": tag, "position": position, "transition": trans},
                           SourceLocation(ll.filename, ll.lineno, ll.indent+1))
            out.append(node.to_dict())
            self.pos += 1
            return

        # ---- hide
        m = _re_hide.match(t)
        if m:
            tag, trans = m.group(1), m.group(2)
            out.append(ASTNode("hide", {"tag": tag, "transition": trans},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return

        # ---- with (standalone)
        m = _re_with.match(t)
        if m:
            out.append(ASTNode("with", {"transition": m.group(1)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return

        # ---- play music
        m = _re_play_music.match(t)
        if m:
            asset = m.group(1) or m.group(2) or m.group(3)
            fadein = float(m.group(4)) if m.group(4) else None
            out.append(ASTNode("play_music", {"asset": asset, "fadein": fadein},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return

        # ---- play sound / voice
        m = _re_play_sound.match(t)
        if m:
            asset = m.group(1) or m.group(2) or m.group(3)
            out.append(ASTNode("play_sound", {"asset": asset},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return
        m = _re_play_voice.match(t)
        if m:
            asset = m.group(1) or m.group(2) or m.group(3)
            out.append(ASTNode("play_voice", {"asset": asset},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return

        # ---- stop
        m = _re_stop.match(t)
        if m:
            ch, fadeout = m.group(1), m.group(2)
            out.append(ASTNode(f"stop_{ch}", {"fadeout": float(fadeout) if fadeout else None},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return

        # ---- pause
        m = _re_pause.match(t)
        if m:
            out.append(ASTNode("pause", {"duration": float(m.group(1))},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return

        # ---- 3D stubs
        m = _re_load_stage.match(t)
        if m:
            out.append(ASTNode("load_stage", {"stage": m.group(1)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return
        m = _re_show3d.match(t)
        if m:
            out.append(ASTNode("show3d", {"asset": m.group(1), "marker": m.group(2)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return
        m = _re_anim.match(t)
        if m:
            out.append(ASTNode("anim", {"target": m.group(1), "animation": m.group(2)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return
        # M10 camera zoom — must check before preset
        m = _re_camera_zoom.match(t) or _re_camera_zoom_alt.match(t)
        if m:
            zoom = float(m.group(1))
            # groups: 1=zoom, 2=duration or with, 3=with or duration depending which regex
            # We try to detect: if group2 looks like easing word, it's with, else duration
            dur = None
            ease = None
            g2 = m.group(2)
            g3 = m.group(3)
            if g2 is not None:
                try:
                    dur = float(g2)
                except:
                    ease = g2
            if g3 is not None:
                try:
                    if dur is None:
                        dur = float(g3)
                    else:
                        ease = g3
                except:
                    ease = g3
            if dur is None:
                dur = 1.0
            if ease is None:
                ease = "ease"
            out.append(ASTNode("camera_zoom", {"zoom": zoom, "duration": dur, "easing": ease},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return
        m = _re_camera.match(t)
        if m:
            out.append(ASTNode("camera_preset", {"name": m.group(1)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return

        # ---- jump / call / return
        m = _re_jump.match(t)
        if m:
            out.append(ASTNode("jump", {"label": m.group(1)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return
        m = _re_call.match(t)
        if m:
            out.append(ASTNode("call", {"label": m.group(1)},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return
        if _re_return.match(t):
            out.append(ASTNode("return", {},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return

        # ---- assignment: set x = ... / set x += 1  (canonical) or legacy `$ x += 1`
        m = _re_set.match(t)
        assign_kind = "set"
        if not m:
            m = _re_assign.match(t)
            assign_kind = "$"
        if m:
            expr = m.group(1).strip()
            if assign_kind == "set":
                # regex already split target/op/value
                target, op, val_expr = m.group(1), m.group(2), m.group(3).strip()
            else:
                # split target / op / value
                am = re.match(r"(\w+)\s*(\+=|-=|\*=|/=|=)\s*(.+)", expr)
                if not am:
                    raise ParseError(f"invalid assignment: {expr!r}", ll.filename, ll.lineno, 1, ll.raw,
                                     hint='example: set book = True  or  set affection += 1')
                target, op, val_expr = am.group(1), am.group(2), am.group(3)
            out.append(ASTNode("assign", {"target": target, "op": op, "expr": val_expr},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return

        # ---- menu
        if _re_menu.match(t):
            self.pos += 1
            menu_node = ASTNode("menu", {"choices": []},
                                SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict()
            # menu's choices are at indent+4
            menu_indent = ll.indent
            # parse choices: each choice line looks like `"Text":` or `"Text" `
            # then its block at +4 deeper
            while self.pos < len(self.lines):
                choice_ll = self.lines[self.pos]
                if choice_ll.indent <= menu_indent:
                    break  # end of menu
                if choice_ll.indent != menu_indent + 4:
                    raise ParseError(
                        f"choice must be indented {menu_indent+4} spaces, got {choice_ll.indent}",
                        choice_ll.filename, choice_ll.lineno, choice_ll.indent+1, choice_ll.raw,
                        hint='inside menu:\n    "Choice text":\n        jump somewhere'
                    )
                # Ren'Py allows a caption string inside menu before choices:
                # menu:
                #     "As soon as she catches my eye..."
                #     "Ask right away.":
                #         jump ...
                ct = choice_ll.text
                # `choice "Text":` — declarative keyword form (M15)
                m_choice = _re_choice.match(ct)
                if m_choice:
                    choice_text = m_choice.group(1) if m_choice.group(1) is not None else m_choice.group(2)
                    self.pos += 1  # step past choice line
                    choice_block: List[dict] = []
                    if self.pos < len(self.lines) and self.lines[self.pos].indent > choice_ll.indent:
                        if self.lines[self.pos].indent != choice_ll.indent + 4:
                            raise ParseError(
                                f"choice body must be indented {choice_ll.indent+4} spaces",
                                self.lines[self.pos].filename, self.lines[self.pos].lineno, 1, self.lines[self.pos].raw
                            )
                        self._parse_block(parent_indent=choice_ll.indent, out=choice_block)
                    self._consume_end(choice_ll.indent, "choice")
                    menu_node["choices"].append({"text": choice_text, "block": choice_block, "_loc": {"file": choice_ll.filename, "line": choice_ll.lineno}})
                    continue

                colon = ct.endswith(":")
                if colon:
                    choice_text_raw = ct[:-1].strip()
                    q = extract_quoted(choice_text_raw)
                    if not q:
                        raise ParseError(f'menu choice must be a quoted string, got: {ct!r}',
                                         choice_ll.filename, choice_ll.lineno, 1, choice_ll.raw)
                    choice_text = q[0]
                else:
                    # no colon — could be caption ONLY if no choices yet and caption not set
                    q = extract_quoted(ct.strip())
                    if q:
                        if not menu_node["choices"] and "caption" not in menu_node:
                            # allow single caption before any choices
                            menu_node["caption"] = q[0]
                            self.pos += 1
                            continue
                        else:
                            raise ParseError(f'menu choice missing colon: {ct!r}',
                                             choice_ll.filename, choice_ll.lineno, 1, choice_ll.raw,
                                             hint='write: "Choice text":')
                    else:
                        raise ParseError(f"unexpected line in menu: {ct!r}", choice_ll.filename, choice_ll.lineno, 1, choice_ll.raw,
                                         hint='inside menu: "Choice text": then indented block')
                # Now choice block is indented deeper (choice_indent+4)
                self.pos += 1  # step past choice line
                choice_block: List[dict] = []
                # If next line exists and is indented deeper, parse as block
                if self.pos < len(self.lines) and self.lines[self.pos].indent > choice_ll.indent:
                    # must be exactly +4
                    if self.lines[self.pos].indent != choice_ll.indent + 4:
                        raise ParseError(
                            f"choice body must be indented {choice_ll.indent+4} spaces",
                            self.lines[self.pos].filename, self.lines[self.pos].lineno, 1, self.lines[self.pos].raw
                        )
                    self._parse_block(parent_indent=choice_ll.indent, out=choice_block)
                else:
                    # empty choice body — allowed but warn
                    pass

                menu_node["choices"].append({"text": choice_text, "block": choice_block, "_loc": {"file": choice_ll.filename, "line": choice_ll.lineno}})

            # optional explicit `end` closing the menu
            self._consume_end(menu_indent, "menu")

            if not menu_node["choices"]:
                raise ParseError("menu has no choices", ll.filename, ll.lineno, 1, ll.raw)

            out.append(menu_node)
            return

        # ---- if / elif / else
        m = _re_if.match(t)
        if m:
            return self._parse_if_chain(ll, parent_indent, out, first=True)
        # elif/else should not appear outside if — error
        if _re_elif.match(t) or _re_else.match(t):
            raise ParseError(f'"{t.split()[0]}" without matching "if"', ll.filename, ll.lineno, 1, ll.raw)

        # ---- say / narration
        # Try say first (character prefix)
        m = _re_say.match(t)
        if m:
            who, expr, text = m.group(1), m.group(2), m.group(3)
            # expr is optional second word like "happy" — treat as expression tag, ignore for Tier1
            # Check if who is a known keyword that isn't a character? but allow anyway
            # If text was empty group? Actually _re_say captures everything inside last quotes as (.*)
            # So this matches even narration-like but with leading word.
            # Distinguish narration: if who is not a defined character? But at parse time characters may not be defined yet? We'll treat as say if who looks like identifier and text was quoted.
            # The regex already ensures trailing quoted string, so this is definitely a say.
            out.append(ASTNode("say", {"who": who, "expression": expr, "text": text},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return
        m = _re_nar.match(t)
        if m:
            text = m.group(1)
            out.append(ASTNode("say", {"who": None, "text": text},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return

        # ---- fallback
        if _re_end.match(t):
            raise ParseError(f"unexpected 'end' — no open block to close at this indentation",
                             ll.filename, ll.lineno, 1, ll.raw,
                             hint="'end' must be dedented to the same level as the block it closes (label/menu/if/state/character/choice)")
        raise ParseError(f"unknown statement: {t!r}", ll.filename, ll.lineno, 1, ll.raw,
                         hint=self._hint_for_unknown(t))

    def _parse_if_chain(self, ll: LogicalLine, parent_indent: int, out: List[dict], first: bool):
        """
        Parse if / elif / else chain as a single 'if' node with branches.
        Consumes all consecutive elif/else at same indent level.
        """
        branches = []
        # first if
        m = _re_if.match(ll.text)
        assert m
        cond = m.group(1).strip()
        self.pos += 1
        block: List[dict] = []
        # parse its body
        if self.pos < len(self.lines) and self.lines[self.pos].indent > ll.indent:
            if self.lines[self.pos].indent != ll.indent + 4:
                raise ParseError("if body must be indented 4 spaces", self.lines[self.pos].filename, self.lines[self.pos].lineno, 1, self.lines[self.pos].raw)
            self._parse_block(parent_indent=ll.indent, out=block)
        branches.append({"cond": cond, "block": block})

        # lookahead for elif / else at same indent
        while self.pos < len(self.lines):
            nxt = self.lines[self.pos]
            if nxt.indent != ll.indent:
                break
            m2 = _re_elif.match(nxt.text)
            if m2:
                cond2 = m2.group(1).strip()
                self.pos += 1
                blk2: List[dict] = []
                if self.pos < len(self.lines) and self.lines[self.pos].indent > nxt.indent:
                    if self.lines[self.pos].indent != nxt.indent + 4:
                        raise ParseError("elif body must be indented 4 spaces", self.lines[self.pos].filename, self.lines[self.pos].lineno, 1, self.lines[self.pos].raw)
                    self._parse_block(parent_indent=nxt.indent, out=blk2)
                branches.append({"cond": cond2, "block": blk2})
                continue
            if _re_else.match(nxt.text):
                self.pos += 1
                blk3: List[dict] = []
                if self.pos < len(self.lines) and self.lines[self.pos].indent > nxt.indent:
                    if self.lines[self.pos].indent != nxt.indent + 4:
                        raise ParseError("else body must be indented 4 spaces", self.lines[self.pos].filename, self.lines[self.pos].lineno, 1, self.lines[self.pos].raw)
                    self._parse_block(parent_indent=nxt.indent, out=blk3)
                branches.append({"cond": None, "block": blk3})
                continue  # re-loop: an explicit `end` may close the chain
            if _re_end.match(nxt.text):
                # explicit `end` closes the if-chain
                self.pos += 1
                break
            else:
                break

        out.append(ASTNode("if", {"branches": branches},
                           SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
        # note: caller expects we already advanced pos, so don't increment again

    # ---------------------------------------------------------------- helpers
    def _eval_literal(self, expr: str, ll: LogicalLine):
        """Safe literal eval for `default` / `state:` values (no code execution)."""
        expr = expr.strip()
        try:
            return ast.literal_eval(expr)
        except (ValueError, SyntaxError, MemoryError, RecursionError):
            raise ParseError(f'value must be a literal (got {expr!r})', ll.filename, ll.lineno, 1, ll.raw,
                             hint='use: True, False, None, 0, 3.14, "text", [1, 2]')

    def _hint_for_unknown(self, t: str) -> str:
        if t.startswith("jump ") and t.endswith(":"):
            return '`jump` does not take a colon — use: jump label_name'
        if t.startswith("menu") and not t.endswith(":"):
            return 'menu needs a colon — use: menu:'
        if t == "menu":
            return 'write menu: (with colon)'
        if t.startswith("label ") and not t.endswith(":"):
            return 'label needs a colon — use: label start:'
        if "Character" in t and not t.startswith("define"):
            return 'character definitions must start with define — e.g. define e = Character("Eileen")'
        if t.startswith("$") and "=" not in t:
            return 'assignment after $ needs = or += — e.g. $ affection += 1'
        if t.startswith("set ") and "=" not in t:
            return 'set needs an operator — e.g. set affection += 1'
        if t.startswith("choice"):
            return '`choice "Text":` is only valid inside a menu: block'
        if t.startswith(("image", "audio", "stage")) and "=" in t:
            return 'image/audio/stage declarations are top-level only (no indentation)'
        if t.startswith(("state", "character")):
            return 'state: and character blocks are top-level only (no indentation)'
        return 'check spelling and indentation (4 spaces per level, spaces not tabs)'


def parse_string(source: str, filename: str = "<string>") -> dict:
    return Parser(source, filename).parse()


def parse_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return parse_string(f.read(), filename=path)
