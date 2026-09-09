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
from typing import List, Dict, Any, Optional, Tuple, Iterable
from .lexer import group_logical_lines, LogicalLine, extract_quoted
from .ast_nodes import ASTNode, SourceLocation
from ..core.vn_errors import ParseError

# ------------------------------------------------------------------ regexes
_re_label = re.compile(r"^label\s+(\w+)\s*:\s*$")
_re_define = re.compile(r'^define\s+(\w+)\s*=\s*Character\s*\((.*)\)\s*$', re.S)
_re_default = re.compile(r"^default\s+([\w.]+)\s*=\s*(.+)\s*$", re.S)
_re_jump = re.compile(r"^jump\s+(\w+)\s*$")
_re_call = re.compile(r"^call\s+(\w+)\s*$")
_re_return = re.compile(r"^return\s*$")
_re_menu = re.compile(r"^menu\s*(\w+)?\s*(?:\(([^)]*)\))?\s*:\s*$")
_re_if = re.compile(r"^if\s+(.+)\s*:\s*$")
_re_elif = re.compile(r"^elif\s+(.+)\s*:\s*$")
_re_else = re.compile(r"^else\s*:\s*$")
_re_assign = re.compile(r"^\$\s*(.+)\s*$", re.S)
# 3D stubs — python-driven but parseable
_re_load_stage = re.compile(r"^load_stage\s+(\w+)\s*$")
_re_show3d = re.compile(r"^show3d\s+(\w+)(?:\s+at\s+(\w+))?\s*$")
_re_anim = re.compile(r"^anim\s+(\w+)\s+(\w+)\s*$")
_re_camera = re.compile(r"^camera\s+preset\s+(\w+)\s*$")
_re_camera_zoom = re.compile(r"^camera\s+zoom\s+([\d.]+)(?:\s+duration\s+([\d.]+))?(?:\s+with\s+(\w+))?\s*$")
_re_camera_zoom_alt = re.compile(r"^camera\s+zoom\s+([\d.]+)(?:\s+with\s+(\w+))?(?:\s+duration\s+([\d.]+))?\s*$")

# say:  s "text"  or  e happy "text"

# Character args parser (very subset): _("Name") or "Name", color="#..."
_re_char_name_tr = re.compile(r'_\(\s*"(.*?)"\s*\)')
_re_color = re.compile(r'color\s*=\s*["\'](.*?)["\']')

# ------------------------------------------------------------------ declarative forms (M15)
# `set` -- canonical assignment (declarative); `$` remains a legacy alias
_re_set = re.compile(r"^set\s+(\w+)\s*(\+=|-=|\*=|/=|=)\s*(.+)\s*$", re.S)
# `state:` block with typed declarations
_re_state = re.compile(r"^state\s*:\s*$")
_re_state_var_typed = re.compile(r"^(\w+)\s*:\s*(int|float|str|string|bool|list)(?:\s*=\s*(.+))?\s*$")
_re_state_var_plain = re.compile(r"^(\w+)\s*=\s*(.+)\s*$")
# `character` block -- declarative character definition
_re_character = re.compile(r"^character\s+(\w+)\s*:\s*$")
_re_char_prop_name = re.compile(r'^name\s+(?:"([^"]+)"|\'([^\']+)\')\s*$')
_re_char_prop_color = re.compile(r'^color\s+(?:"([^"]+)"|\'([^\']+)\')\s*$')
# declarative asset manifest
_re_image = re.compile(r'^image\s+(?:"([^"]+)"|([A-Za-z_][\w ]*?))\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$', re.S)
_re_audio = re.compile(r'^audio\s+(\w+)\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$', re.S)
_re_stage = re.compile(r'^stage\s+(\w+)\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$', re.S)
# `choice` keyword inside menus (declarative alternative to bare quoted choice)
_re_choice = re.compile(r'^choice\s+(?:"([^"]+)"|\'([^\']+)\')\s*:\s*$')
# explicit block terminator
_re_end = re.compile(r"^end\s*$")

# ------------------------------------------------------------------ full .rpy tier (drop-in Ren'Py)
_re_python = re.compile(r"^python\s*:\s*$")
_re_python_early = re.compile(r"^python\s+(?:early|hide|in\s+[\w.]+)(?:\s+(?:early|hide|in\s+[\w.]+))*\s*:\s*$")
_re_init_python = re.compile(r"^init\s+(-?\d+\s+)?python(?:\s+(?:early|hide|in\s+[\w.]+))*\s*:\s*$")
_re_init = re.compile(r"^init\s*(-?\d+)?\s*:\s*$")
_re_init_offset = re.compile(r"^init\s+offset\s*=\s*(-?\d+)\s*$")
_re_while = re.compile(r"^while\s+(.+)\s*:\s*$")
_re_break = re.compile(r"^break\s*$")
_re_continue = re.compile(r"^continue\s*$")
_re_pass = re.compile(r"^pass\s*$")
# both take an optional trailing transition: `window hide None`, `nvl show dissolve`
_re_window = re.compile(r"^window\s+(show|hide|auto)\s*(.*)$", re.S)
_re_nvl = re.compile(r"^nvl\s+(clear|show|hide)\s*(.*)$", re.S)
_re_nvl_mode = re.compile(r"^nvl\s+mode\s+(nvl|adv)\s*$")
_re_voice = re.compile(r'^voice\s+(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$')
_re_queue_music = re.compile(r'^queue\s+music\s+(?:"([^"]+)"|\'([^\']+)\'|(\S+))(?:\s+fadein\s+([\d.]+))?\s*$')
_re_queue_sound = re.compile(r'^queue\s+sound\s+(?:"([^"]+)"|\'([^\']+)\'|(\S+))\s*$')
_re_jump_expr = re.compile(r"^jump\s+expression\s+(.+)\s*$")
_re_call_expr = re.compile(r"^call\s+expression\s+(.+)\s*$")
_re_call_args = re.compile(r"^call\s+(\w+)\s*\(([^)]*)\)\s*$")
_re_define_generic = re.compile(r"^define\s+([\w.]+)\s*=\s*(.+)\s*$", re.S)
# `define config.x += [ … ]` — Ren'Py accepts the augmented forms too
_re_define_aug = re.compile(r"^define\s+([\w.]+)\s*(\+|\||-|\*|/)?=\s*(.+)\s*$", re.S)
_re_transform = re.compile(r"^transform\s+(\w+)\s*:\s*$")
_re_screen = re.compile(r"^screen\s+(\w+)\s*(?:\(([^)]*)\))?\s*:\s*$")
_re_style_block = re.compile(r"^style\s+(\w+)\s*(?:is\s+(\w+))?\s*:\s*$")
_re_translate = re.compile(r"^translate\s+([\w.]+)\s+(.+?)\s*:\s*$")

# M21: Ren'Py lets a project register its own statement keywords
# (`renpy.register_statement("example", parse=…, execute=…)` — the official SDK
# tutorial does exactly that). `testcase`/`testsuite` are Ren'Py's built-in test
# statements (renpy/parser.py:1230/1239). Both are captured, never executed.
_re_register_statement = re.compile(r"""register_statement\(\s*["\']([^"\']+)["\']""")
_re_test_statement = re.compile(r"^(testsuite|testcase)\s+([\w.]+)\s*:\s*$")
# always-available custom statement keywords in the drop-in tier
_BUILTIN_CUSTOM_STATEMENTS = frozenset({"testsuite", "testcase"})
_re_show_screen = re.compile(r"^show\s+screen\s+(\w+)\s*$")
_re_hide_screen = re.compile(r"^hide\s+screen\s+(\w+)\s*$")
_re_call_screen = re.compile(r"^call\s+screen\s+(\w+)\s*$")
_re_transform_prop = re.compile(r"^(\w+)\s+(.+?)\s*$", re.S)

# ---- drop-in Ren'Py compatibility (M19) --------------------------------
# `from` clauses: Ren'Py inserts `call x from _call_x_3` / `jump x from …`
_re_bare_from = re.compile(r"^from\s+([\w.]+)\s*$")
_re_call_from = re.compile(r"^call\s+(.+?)\s+from\s+([\w.]+)\s*$")
_re_jump_from = re.compile(r"^jump\s+(.+?)\s+from\s+([\w.]+)\s*$")
# screen statements with arguments / transition
_re_show_screen_args = re.compile(r"^show\s+screen\s+([\w.]+)\s*(?:\((.*)\))?\s*(?:with\s+(.+?))?\s*$")
_re_hide_screen_args = re.compile(r"^hide\s+screen\s+([\w.]+)\s*$")
# `for x in items:`
_re_for = re.compile(r"^for\s+(.+?)\s+in\s+(.+?)\s*:\s*$")
# voice attributes:  who @ attr "text"
# generic transition:  with Dissolve(0.5) / with hp8 / with None
_re_with_any = re.compile(r"^with\s+(.+?)\s*$")
# pause:  pause / pause 1.0 / pause delay / pause 1.0 with fade
_re_pause_any = re.compile(r"^pause(?:\s+(.+?))?(?:\s+with\s+(.+?))?\s*$")
# audio:  play|queue|stop <channel> …
_re_audio_any = re.compile(r"^(play|queue|stop)\s+(music|sound|voice|audio)\b\s*(.*)$")
_re_voice_sustain = re.compile(r"^voice\s+sustain\s*$")
_re_voice_center = re.compile(r"^voice\s+(center|left|right)\b\s*$")
# centered / vcentered narration
_re_centered = re.compile(r"^(v?centered)\s+(\S.*)$")
# extend "more text"
_re_extend = re.compile(r"^extend\b\s*(.*)$")
# image with a block (layeredimage player: / image bg:)
_re_image_block = re.compile(r"^(layeredimage|image)\s+(.+?)\s*:\s*$")
# style statements at top level
_re_style_assign = re.compile(r"^style\s*\.?([\w.]+)\s*=\s*(.+)$", re.S)
_re_style_prop_line = re.compile(r"^style\s*\.?([\w.]+)\s+([A-Za-z_]\w*)\s+(.+)$", re.S)
# label with optional params + hide/nohide
_re_label_full = re.compile(r"^label\s+(\w+)\s*(?:\(([^)]*)\))?\s*(hide|nohide)?\s*:\s*$")
# screen / transform with parameters or trailing keywords
_re_screen_full = re.compile(
    r"^screen\s+(\w+)\s*(?:\(([^)]*)\))?\s*(?:tag\s+\w+)?\s*(?:modal\s+\S+)?\s*"
    r"(?:zorder\s+\d+)?\s*(?:predict\s+\S+)?\s*:\s*$")
_re_transform_full = re.compile(r"^transform\s+(\w+)\s*(?:\(([^)]*)\))?\s*:\s*$")
# default / define with a dotted name:  default preferences.text_cps = 60
# display statements (scene/show/hide) with any clauses


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


# ------------------------------------------------------------------ clause splitting
def _mask_strings(text: str) -> str:
    """Return ``text`` with every quoted string's body replaced by spaces.

    Keyword scanning (`with`, `at`, `as`, …) must not match inside dialogue
    text, so we look at a same-length "mask" of the line instead.
    """
    out: List[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in ('"', "'"):
            if text.startswith(ch * 3, i):
                end = text.find(ch * 3, i + 3)
                end = n if end == -1 else end + 3
                out.append(text[i : i + 3])
                out.append(" " * max(0, end - i - 6))
                out.append(text[end - 3 : end])
                i = end
                continue
            j = i + 1
            while j < n:
                if text[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if text[j] == ch:
                    j += 1
                    break
                j += 1
            out.append(ch)
            out.append(" " * max(0, j - i - 2))
            out.append(ch)
            i = j
            continue
        out.append(ch)
        i += 1
    s = "".join(out)
    return s + " " * (n - len(s)) if len(s) < n else s


def _find_top_keyword(text: str, keyword: str, last: bool = True) -> Optional[int]:
    """Index of a top-level (outside strings/brackets) whole-word keyword, or None."""
    masked = _mask_strings(text)
    depth = 0
    found: Optional[int] = None
    for idx, ch in enumerate(masked):
        if ch in "([{":
            depth += 1
            continue
        if ch in ")]}":
            depth -= 1
            continue
        if depth == 0 and masked.startswith(keyword, idx):
            before_ok = idx == 0 or not (masked[idx - 1].isalnum() or masked[idx - 1] in "_.")
            after = idx + len(keyword)
            after_ok = after >= len(masked) or not (masked[after].isalnum() or masked[after] == "_")
            if before_ok and after_ok:
                found = idx
                if not last:
                    return idx
    return found


_CLAUSE_FIELDS = {"with": "transition", "at": "position", "behind": "behind",
                  "as": "as_tag", "onlayer": "layer", "zorder": "zorder"}


def _split_display_clauses(body: str) -> dict:
    """Split ``scene``/``show``/``hide``/``camera`` arguments into clauses.

    ``e happy as fx at left, right behind m zorder 2 with dissolve`` →
    ``{"asset": "e happy", "as_tag": "fx", "position": "left, right",
       "behind": "m", "zorder": "2", "transition": "dissolve"}``

    Every clause keyword is located at top level (never inside dialogue text or
    brackets), the marks are sorted, and each clause gets exactly the text up
    to the next keyword — so the order the author used does not matter.
    """
    marks = []
    for kw in _CLAUSE_FIELDS:
        idx = _find_top_keyword(body, kw, last=False)
        if idx is not None:
            marks.append((idx, kw))
    marks.sort()

    parts: Dict[str, Any] = {}
    parts["asset"] = (body[: marks[0][0]] if marks else body).strip()
    for i, (idx, kw) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(body)
        parts[_CLAUSE_FIELDS[kw]] = body[idx + len(kw): end].strip()
    return parts


# ------------------------------------------------------------------ say statements
_SAY_KW_OK = re.compile(r"^[+-]?[A-Za-z_]\w*$")


def _split_say(text: str):
    """Split a Ren'Py say statement.

    Handles the real-world forms::

        "narration"
        who "text"
        who happy smile "text"          (attributes / expression tags)
        who @ laugh "text"              (voice attribute, Ren'Py 7.4+)
        who "text" nointeract
        who id=xyz "text" (what_prefix="[")
        extend "more"

    Returns ``None`` when the line is not a say statement.
    """
    masked = _mask_strings(text)
    start = None
    depth = 0
    for idx, ch in enumerate(masked):
        if ch in "([{":
            depth += 1
            continue
        if ch in ")]}":
            depth -= 1
            continue
        if depth == 0 and text[idx] in ('"', "'"):
            start = idx
            break
    if start is None:
        return None
    q = extract_quoted(text[start:])
    if q is None:
        return None
    dialogue, _, end = q
    prefix = text[:start].strip()
    suffix = text[start + end:].strip()

    nointeract = False
    inline: Dict[str, str] = {}
    say_id: Optional[str] = None

    # `"Lucy" "text"` — the who is an expression, and a bare string literal is a
    # dynamic character name (renpy/parser.py: say_statement parses the who as
    # an expression, so quotes are legal there). Check before the suffix loop:
    # a leading quote is otherwise read as unrecognised trailing junk.
    if not prefix and suffix[:1] in ('"', "'"):
        q2 = extract_quoted(suffix)
        if q2 is not None and not suffix[q2[2]:].strip():
            return {"who": dialogue, "text": q2[0], "expression": None,
                    "voice_attr": None, "nointeract": False,
                    "kwargs": None, "inline": None, "id": None}

    if suffix:
        toks = suffix.split()
        i = 0
        while i < len(toks):
            tok = toks[i]
            if tok == "nointeract":
                nointeract = True
            elif tok == "id" and i + 1 < len(toks):
                # Ren'Py's automatic dialogue IDs (`… "text" id a1b2c3d4`),
                # inserted by the translation tooling into every shipped game
                say_id = toks[i + 1]
                i += 1
            elif tok.startswith("(") and tok.endswith(")"):
                for kv in _split_args(tok[1:-1]):
                    if "=" in kv:
                        k, v = kv.split("=", 1)
                        inline[k.strip()] = v.strip()
            else:
                return None   # trailing junk we do not understand → not a say
            i += 1

    who: Optional[str] = None
    voice_attr: Optional[str] = None
    attrs: List[str] = []
    kwargs: Dict[str, str] = {}
    if prefix:
        tokens = prefix.split()
        if not _SAY_KW_OK.match(tokens[0]):
            return None
        who = tokens[0]
        rest = tokens[1:]
        if rest and rest[0] == "@" and len(rest) > 1:
            voice_attr = rest[1]
            rest = rest[2:]
        for tok in rest:
            if "=" in tok and _SAY_KW_OK.match(tok.split("=", 1)[0]):
                k, v = tok.split("=", 1)
                kwargs[k] = v
            elif _SAY_KW_OK.match(tok):
                attrs.append(tok)
            else:
                return None
    return {
        "who": who,
        "text": dialogue,
        "expression": " ".join(attrs) if attrs else None,
        "voice_attr": voice_attr,
        "nointeract": nointeract,
        "kwargs": kwargs or None,
        "inline": inline or None,
        "id": say_id,
    }


def _matching_close_paren(text: str) -> Optional[int]:
    """Index of the ``)`` closing the leading ``(`` of ``text`` (or None)."""
    if not text.startswith("("):
        return None
    depth = 0
    for i, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
    return None


def _split_args(raw: str) -> List[str]:
    """Split a comma-separated argument list, ignoring separators inside brackets."""
    args: List[str] = []
    depth = 0
    cur = ""
    for ch in raw:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            args.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        args.append(cur.strip())
    return [a for a in args if a]


class Parser:
    def __init__(self, source: str, filename: str = "<string>", full: bool = False,
                 require_start: bool = True, custom_statements: Iterable[str] = ()):
        self.filename = filename
        self.full = full  # full = drop-in Ren'Py tier (python blocks, init, while, screens…)
        # multi-file games: only one file holds `label start:`, so per-file
        # parsing must not demand it (checked on the merged script instead)
        self.require_start = require_start
        self.lines: List[LogicalLine] = group_logical_lines(source, filename)
        self.pos = 0
        # outputs
        self.labels: Dict[str, List[dict]] = {}
        self.defaults: Dict[str, Any] = {}
        self.characters: Dict[str, dict] = {}
        self.types: Dict[str, str] = {}  # declarative `state:` type declarations
        self.assets: Dict[str, Dict[str, str]] = {"images": {}, "audio": {}, "stages": {}}
        # full-tier outputs
        self.label_params: Dict[str, List[dict]] = {}   # label -> [{name, default}]
        self.defines: Dict[str, Any] = {}               # non-Character `define name = value`
        self.init_python: List[str] = []                # init-time python code lines
        self.transforms: Dict[str, dict] = {}           # transform name -> {props, lines}
        self.screens: Dict[str, dict] = {}              # screen name -> {params, lines}
        self.styles: Dict[str, dict] = {}               # style name -> raw lines
        self.translations: Dict[str, dict] = {}         # translate lang label -> raw lines
        self.image_blocks: Dict[str, dict] = {}         # (layered)image name -> raw lines
        self.from_clauses: List[dict] = []              # `call/jump … from <id>` (compat)
        self.custom_statements: Dict[str, List[dict]] = {}   # project-registered keywords
        self.custom_statement_errors: List[dict] = []        # parse errors inside their bodies
        # Statements a project may use because it registers them itself. Ren'Py
        # collects registrations at init time; we collect them statically, both
        # from this file and from whatever the caller discovered project-wide.
        self._registered_statements: set = set(_BUILTIN_CUSTOM_STATEMENTS)
        # name -> block type ("script" = body is parsed as script, None = opaque)
        self._registered_blocks: Dict[str, Optional[str]] = scan_register_statements(source)
        if isinstance(custom_statements, dict):
            self._registered_blocks.update(custom_statements)
            self._registered_statements.update(custom_statements.keys())
        else:
            self._registered_statements.update(custom_statements)
        self._registered_statements.update(self._registered_blocks.keys())
        self._registered_names: List[str] = sorted(
            (n for n in self._registered_statements if n), key=len, reverse=True)
        self._loop_id = 0
        self._loop_stack: List[int] = []                # enclosing while-loop ids (for break/continue)
        # current label being filled
        self._current_label: Optional[str] = None
        self._current_list: Optional[List[dict]] = None
        # indent stack for block handling — start at 0
        self._indent_stack: List[int] = [0]

    # ---------------------------- public
    def parse(self) -> dict:
        if not self.lines and self.require_start:
            raise ParseError("empty script", self.filename, 1,
                             hint="this file holds no statements (comments only?)")

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

        if self.require_start and "start" not in self.labels:
            raise ParseError('missing required label "start:"', self.filename, 1, hint='add:\nlabel start:\n    "Hello."')

        return {
            "labels": self.labels,
            "characters": self.characters,
            "defaults": self.defaults,
            "types": self.types,
            "assets": self.assets,
            "label_params": self.label_params,
            "defines": self.defines,
            "init_python": self.init_python,
            "transforms": self.transforms,
            "screens": self.screens,
            "styles": self.styles,
            "translations": self.translations,
            "image_blocks": self.image_blocks,
            "from_clauses": self.from_clauses,
            "custom_statements": self.custom_statements,
            "custom_statement_errors": self.custom_statement_errors,
            "full": self.full,
        }

    # ---------------------------- top-level dispatch
    def _parse_top_level(self, ll: LogicalLine):
        t = ll.text

        # define — with friendly hint for missing parens
        m_char = re.match(r"^define\s+[\w.]+\s*=\s*Character\b(.*)$", t, re.S)
        if m_char and not _re_define.match(t):
            rest = m_char.group(1)
            if "(" not in rest:
                raise ParseError('define missing parentheses: expected define e = Character("Name")',
                                 ll.filename, ll.lineno, 1, ll.raw,
                                 hint='use: define e = Character("Eileen", color="#c8ffc8")')
            if "\n" not in t and rest.count("(") != rest.count(")"):
                # (multi-line defines join across newlines and may legitimately
                #  hold unbalanced parens inside their strings)
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
            if "." in var:
                # `default preferences.text_cps = 60` — a config/namespace default
                if not self.full:
                    raise ParseError("dotted defaults require the full .rpy tier",
                                     ll.filename, ll.lineno, 1, ll.raw,
                                     hint="parse with mode='full', or use `default name = value`")
                self.defines[var] = expr
                self.pos += 1
                return
            try:
                val = self._eval_literal(expr, ll)
            except ParseError:
                if not self.full:
                    raise
                # full tier: `default player_stats = PlayerStats()` — the value is
                # an expression, so it is evaluated once at init (like Ren'Py does
                # when a new game starts) instead of being stored as a literal.
                self.init_python.append(f"{var} = {expr}")
                self.pos += 1
                return
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
        # (layered)image with a block body — captured raw in the full tier
        if self.full:
            m = _re_image_block.match(t)
            if m:
                kind, name = m.group(1), m.group(2).strip()
                self._parse_capture_block(ll, self.image_blocks, kind, kind_id=name)
                return
            m = re.match(r"^(?:layered)?image\s+(.+?)\s*=\s*(.+)$", t, re.S)
            if m:
                name, rhs = m.group(1).strip(), m.group(2).strip()
                q = extract_quoted(rhs)
                # only a plain string RHS is a resolvable asset path
                path = q[0] if (q and q[2] == len(rhs)) else rhs
                self.assets["images"][name] = path
                self.pos += 1
                return
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

        # label (optionally with parameters — full tier)
        label = None
        params = None
        m = _re_label.match(t)
        if m:
            label = m.group(1)
        else:
            mp = _re_label_full.match(t)
            if mp:
                label = mp.group(1)
                if mp.group(2) is not None:
                    params = self._parse_param_list(mp.group(2))
                if not self.full and (any(p["name"] for p in (params or [])) or mp.group(3)):
                    raise ParseError(
                        "label parameters require the full .rpy tier",
                        ll.filename, ll.lineno, 1, ll.raw,
                        hint="parse with mode='full', or write `label name:` without parameters",
                    )
        if label is not None:
            if label in self.labels:
                raise ParseError(f'duplicate label "{label}"', ll.filename, ll.lineno, 1, ll.raw)
            self._current_label = label
            self._current_list = []
            self.labels[label] = self._current_list
            if params is not None:
                self.label_params[label] = params
            self.pos += 1
            # parse its indented block
            self._parse_block(parent_indent=0, out=self._current_list)
            self._consume_end(0, "label")
            self._current_label = None
            self._current_list = None
            return

        # ---- full-tier top-level statements
        if self.full:
            if _re_init_offset.match(t):
                # init offset only shifts statement priorities — record and ignore
                self.pos += 1
                return
            if _re_init_python.match(t) or _re_python.match(t) or _re_python_early.match(t):
                code = self._capture_python_block(ll)
                self.init_python.append(code)
                return
            if _re_init.match(t):
                self._parse_init_block(ll)
                return
            m_def = (_re_define_generic.match(t)
                     if not t.split("=")[0].rstrip().endswith(("+", "|", "-", "*", "/"))
                     else None) or _re_define_aug.match(t)
            if m_def and not re.match(r"^define\s+[\w.]+\s*[+|\-*/]?=\s*Character\s*\(", t):
                name = m_def.group(1)
                expr = (m_def.group(3) if m_def.lastindex == 3 else m_def.group(2)).strip()
                try:
                    val = self._eval_literal(expr, ll)
                except ParseError:
                    val = None  # non-literal defines (config.X = renpy.… etc.) stored as raw string
                    self.defines[name] = expr
                else:
                    self.defines[name] = val
                self.pos += 1
                return
            m = _re_transform_full.match(t) or _re_transform.match(t)
            if m:
                self._parse_transform_block(ll, m.group(1))
                return
            m = _re_screen_full.match(t) or _re_screen.match(t)
            if m:
                self._parse_capture_block(ll, self.screens, "screen", kind_id=m.group(1),
                                          params=m.group(2))
                return
            if _re_style_block.match(t):
                self._parse_capture_block(ll, self.styles, "style", kind_id=_re_style_block.match(t).group(1))
                return
            # `style foo.bar = value` / `style foo.bar property value`
            m = _re_style_assign.match(t)
            if m:
                self.styles[m.group(1)] = {"lines": [t], "value": m.group(2).strip()}
                self.pos += 1
                return
            m = _re_style_prop_line.match(t)
            if m:
                self.styles[m.group(1)] = {"lines": [t], "property": m.group(2), "value": m.group(3).strip()}
                self.pos += 1
                return
            m = _re_translate.match(t)
            if m:
                mtr = m
                self._parse_capture_block(ll, self.translations, "translate", kind_id=f"{mtr.group(1)}_{mtr.group(2)}")
                return
            if t.startswith("$"):
                # top-level $ is init-time python (full tier)
                self.init_python.append(t[1:].strip())
                self.pos += 1
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
        if re.match(r"^define\s+[\w.]+\s*=\s*Character\s*\(", t) and "Character" in t:
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
        if not self.full:
            # full-tier constructs are rejected with guidance in safe mode
            if _re_python.match(t):
                raise ParseError("python: blocks require the full .rpy tier", ll.filename, ll.lineno, 1, ll.raw,
                                 hint="parse with mode='full' (or use a .urpy declarative script)")
            if _re_init_python.match(t) or _re_init.match(t):
                raise ParseError("init blocks require the full .rpy tier", ll.filename, ll.lineno, 1, ll.raw,
                                 hint="parse with mode='full' (or declare state in a state: block)")
            if _re_transform.match(t) or _re_screen.match(t) or _re_style_block.match(t) or _re_translate.match(t):
                raise ParseError(f"{t.split()[0]} requires the full .rpy tier", ll.filename, ll.lineno, 1, ll.raw,
                                 hint="parse with mode='full'")
            if t.startswith("define ") and "Character" not in t:
                raise ParseError("only Character defines are allowed in the safe subset", ll.filename, ll.lineno, 1, ll.raw,
                                 hint="parse with mode='full' for arbitrary define (config, images, …)")
        # a statement the project registered itself (renpy.register_statement)
        if self.full:
            name = self._match_custom(t)
            if name is not None:
                self._parse_custom_statement(ll, name)
                return
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
                    from .literals import type_default
                    val = type_default(typ)
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
        from .literals import check_value_type
        ok, err = check_value_type(val, typ)
        if not ok:
            raise ParseError(
                f"type mismatch: {var!r} is declared {typ}, but value is {type(val).__name__}",
                ll.filename, ll.lineno, 1, ll.raw,
                hint=f"declare it with a {typ} value, e.g. {var}: {typ} = 0",
            )

    # ---------------------------- full-tier block helpers
    def _parse_param_list(self, raw: str) -> List[dict]:
        """Parse a label parameter list `(name, name2=default)` -> [{name, default}]."""
        params = []
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if "=" in part:
                name, default = part.split("=", 1)
                params.append({"name": name.strip(), "default": default.strip()})
            else:
                params.append({"name": part, "default": None})
        return params

    def _parse_arg_list(self, raw: str) -> List[str]:
        """Parse a call argument list `(1, "x", foo)` -> list of expression strings."""
        if not raw.strip():
            return []
        args = []
        depth = 0
        cur = ""
        for ch in raw:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            if ch == "," and depth == 0:
                args.append(cur.strip())
                cur = ""
            else:
                cur += ch
        if cur.strip():
            args.append(cur.strip())
        return args

    def _capture_python_block(self, ll: LogicalLine) -> str:
        """Capture a `python:` block's indented code as text (dedented).

        The block's own indent is taken from its first line (real Ren'Py games
        use 2-, 4- or 8-space indents), so the code stays executable.
        """
        self.pos += 1
        code_lines = []
        base = None
        while self.pos < len(self.lines) and self.lines[self.pos].indent > ll.indent:
            ln = self.lines[self.pos]
            if base is None:
                base = ln.indent
            code_lines.append(" " * max(0, ln.indent - base) + ln.text)
            self.pos += 1
        self._consume_end(ll.indent, "python")
        return "\n".join(code_lines)

    def _parse_init_block(self, ll: LogicalLine):
        """`init:` block — parse its indented lines as top-level statements (full tier)."""
        self.pos += 1
        block = []
        while self.pos < len(self.lines) and self.lines[self.pos].indent > ll.indent:
            block.append(self.lines[self.pos])
            self.pos += 1
        self._consume_end(ll.indent, "init")
        if not block:
            return
        self._parse_script_block(block, "init")

    def _parse_transform_block(self, ll: LogicalLine, name: str):
        """`transform name:` block — capture ATL lines + simple scalar properties."""
        self.pos += 1
        props: Dict[str, str] = {}
        raw_lines = []
        while self.pos < len(self.lines) and self.lines[self.pos].indent > ll.indent:
            ln = self.lines[self.pos]
            raw_lines.append(ln.text)
            m = _re_transform_prop.match(ln.text)
            if m:
                props[m.group(1)] = m.group(2).strip()
            self.pos += 1
        self._consume_end(ll.indent, "transform")
        self.transforms[name] = {"props": props, "lines": raw_lines}

    def _collect_atl_block(self, ll: LogicalLine, what: str) -> List[str]:
        """Consume the ATL block that follows a `show …:` / `scene …:` header."""
        self.pos += 1
        lines: List[str] = []
        while self.pos < len(self.lines) and self.lines[self.pos].indent > ll.indent:
            lines.append(self.lines[self.pos].text)
            self.pos += 1
        self._consume_end(ll.indent, what)
        return lines

    # ---------------- project-registered statements (M21)
    def _match_custom(self, t: str, multi_only: bool = False) -> Optional[str]:
        """Longest registered custom-statement keyword opening this line.

        ``multi_only`` is used on the early (pre-dispatch) path so that a
        registered two-word statement like `show example` wins over the generic
        `show` handler, while single-word keywords stay a fallback — a built-in
        statement always beats a same-named registration.
        """
        for name in self._registered_names:
            if multi_only and " " not in name:
                continue
            if t == name or t.startswith(name + " ") or t.startswith(name + ":"):
                return name
        return None

    def _parse_custom_statement(self, ll: LogicalLine, name: str,
                                out: Optional[List[dict]] = None):
        """Handle a statement the project registered with renpy.register_statement.

        Ren'Py runs a python callback for these, which we never execute. What we
        do honour is the ``block=`` argument: ``block="script"`` tells Ren'Py to
        parse the body as script, so labels and jumps declared inside are real
        (the SDK tutorial declares ``label play_pong:`` inside an ``example``
        block exactly that way). Any other body stays opaque.
        """
        t = ll.text
        rest = t[len(name):].strip()
        args = rest.rstrip(":").strip()
        has_block = rest.endswith(":")
        self.pos += 1
        block: List[LogicalLine] = []
        if has_block:
            while self.pos < len(self.lines) and self.lines[self.pos].indent > ll.indent:
                block.append(self.lines[self.pos])
                self.pos += 1
            self._consume_end(ll.indent, name)
        lines = [ln.text for ln in block]
        self.custom_statements.setdefault(name, []).append(
            {"args": args, "lines": lines,
             "filename": ll.filename, "lineno": ll.lineno})
        if block and self._registered_blocks.get(name) == "script":
            self._parse_script_block(block, name, tolerant=True)
        if out is not None:
            out.append(self._mk("custom_statement",
                                {"name": name, "args": args, "lines": lines}, ll))

    def _parse_script_block(self, block: List[LogicalLine], what: str,
                            tolerant: bool = False):
        """Parse a dedented run of lines as top-level statements.

        Used by `init:` and by custom statements registered with
        ``block="script"``. ``tolerant`` is for the latter: that body belongs to
        a statement whose semantics we do not implement, so a construct we
        cannot read must not abort the whole file — it is recorded in
        ``custom_statement_errors`` instead. `init:` is our own syntax, so its
        errors stay hard.
        """
        base = block[0].indent
        dedented = [LogicalLine(text=ln.text, indent=max(0, ln.indent - base), raw=ln.raw,
                                lineno=ln.lineno, filename=ln.filename) for ln in block]
        saved_lines, saved_pos = self.lines, self.pos
        self.lines = dedented
        self.pos = 0
        try:
            while self.pos < len(self.lines):
                ln = self.lines[self.pos]
                if ln.indent != 0:
                    raise ParseError(f"unexpected indent inside {what} block",
                                     ln.filename, ln.lineno, ln.indent + 1, ln.raw)
                self._parse_top_level(ln)
        except ParseError as e:
            if not tolerant:
                raise
            self.custom_statement_errors.append(
                {"statement": what, "file": e.filename, "line": e.lineno, "error": str(e)})
        finally:
            self.lines, self.pos = saved_lines, saved_pos

    def _parse_capture_block(self, ll: LogicalLine, target: dict, kind: str, kind_id: str,
                             params: Optional[str] = None):
        """Capture a screen/style/translate block (parse-level, full tier).

        ``lines`` stays stripped text for backwards compatibility; ``indents``
        carries the *relative* indent of each line so a consumer can rebuild the
        block's tree without re-lexing. Screen parameters are kept too — a
        `screen choice(items):` is not usable without them.
        """
        self.pos += 1
        raw_lines = []
        indents = []
        while self.pos < len(self.lines) and self.lines[self.pos].indent > ll.indent:
            raw_lines.append(self.lines[self.pos].text)
            indents.append(self.lines[self.pos].indent - ll.indent)
            self.pos += 1
        self._consume_end(ll.indent, kind)
        entry = {"lines": raw_lines, "indents": indents}
        if params is not None:
            entry["params"] = params.strip() if params else ""
        target[kind_id] = entry

    # ---------------------------- block parsing (indent-sensitive)
    def _block_indent(self, ll: LogicalLine, what: str) -> Optional[int]:
        """Validate the first line of a sub-block and return its indent.

        Safe/declarative tiers demand exactly 4 spaces; the drop-in tier accepts
        any consistent indent (real projects use 2, 4 or 8).
        """
        if self.pos >= len(self.lines):
            return None
        nxt = self.lines[self.pos]
        if nxt.indent <= ll.indent:
            return None
        if not self.full and nxt.indent != ll.indent + 4:
            raise ParseError(f"{what} body must be indented 4 spaces", nxt.filename,
                             nxt.lineno, nxt.indent + 1, nxt.raw,
                             hint=f"indent this line to {ll.indent + 4} spaces (4 per level)")
        return nxt.indent

    def _mk(self, kind: str, data: dict, ll: LogicalLine) -> dict:
        """Build a JSON-serialisable AST node dict."""
        return ASTNode(kind, data, SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict()

    @staticmethod
    def _parse_num_opt(rest: str, name: str):
        """`… fadein 1.0 …` -> 1.0 (or None)."""
        m = re.search(r"(?<![\w])" + name + r"\s+([\d.]+)", rest or "")
        if not m:
            return None
        try:
            return float(m.group(1))
        except ValueError:
            return None

    @staticmethod
    def _split_audio_asset(rest: str):
        """Split the target of `play`/`queue` from its options -> (asset, rest)."""
        rest = (rest or "").strip()
        if not rest:
            return None, ""
        if rest[0] in ('"', "'"):
            q = extract_quoted(rest)
            if q:
                return q[0], rest[q[2]:].strip()
            return rest, ""
        if rest[0] == "[":                      # playlist: play music ["a", "b"]
            depth = 0
            for i, ch in enumerate(rest):
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        return rest[: i + 1], rest[i + 1:].strip()
            return rest, ""
        parts = rest.split(None, 1)
        return parts[0], (parts[1] if len(parts) > 1 else "")

    def _parse_block(self, parent_indent: int, out: List[dict]):
        """
        Consume lines whose indent > parent_indent and emit nodes into out.
        Stops when next line indent <= parent_indent (sibling / dedent).

        Safe/declarative tiers demand exactly 4 spaces per level (UPVN rule,
        enforced by examples/11_syntax_error_gallery). The full drop-in tier
        accepts any *consistent* indent, because real Ren'Py projects use 2,
        4 or 8 spaces.
        """
        block_indent: Optional[int] = None
        while self.pos < len(self.lines):
            ll = self.lines[self.pos]
            if ll.indent <= parent_indent:
                # dedent — end of this block
                return
            if block_indent is None:
                if not self.full:
                    expected = parent_indent + 4
                    if ll.indent != expected:
                        # friendly hint per doc §11 syntax error gallery
                        if ll.indent < expected:
                            raise ParseError(
                                f"unexpected dedent: expected {expected} spaces, got {ll.indent}",
                                ll.filename, ll.lineno, ll.indent + 1, ll.raw,
                                hint=f"indent this line to {expected} spaces (4 per level)"
                            )
                        else:
                            raise ParseError(
                                f"unexpected indent: expected {expected} spaces, got {ll.indent}",
                                ll.filename, ll.lineno, ll.indent + 1, ll.raw,
                                hint=f"too many spaces — expected {expected}"
                            )
                block_indent = ll.indent
            elif ll.indent != block_indent:
                raise ParseError(
                    f"unexpected indent: expected {block_indent} spaces, got {ll.indent}",
                    ll.filename, ll.lineno, ll.indent + 1, ll.raw,
                    hint=f"lines in the same block must all be indented {block_indent} spaces"
                )

            # Now dispatch statement types that can appear inside a label/menu/if
            self._parse_statement(ll, parent_indent=ll.indent, out=out)
            # _parse_statement advances pos; if it consumed a sub-block, pos already after
            # else it did pos+=1

    def _parse_statement(self, ll: LogicalLine, parent_indent: int, out: List[dict]):
        t = ll.text

        # ---- full-tier statements (drop-in Ren'Py)
        if self.full:
            # registered multi-word statements ("show example") must be checked
            # before the generic show/hide handler
            name = self._match_custom(t, multi_only=True)
            if name is not None:
                self._parse_custom_statement(ll, name, out)
                return
            # `default` is collected wherever Ren'Py finds it (even inside a
            # label) and only applied when a new game starts
            m = _re_default.match(t)
            if m:
                var, expr = m.group(1), m.group(2).strip()
                if "." in var:
                    self.defines[var] = expr
                else:
                    try:
                        self.defaults.setdefault(var, self._eval_literal(expr, ll))
                    except ParseError:
                        self.init_python.append(f"{var} = {expr}")
                self.pos += 1
                return
            # `from` clause: Ren'Py inserts these for save-compatibility
            m = _re_bare_from.match(t)
            if m:
                self.from_clauses.append({"kind": "bare", "id": m.group(1)})
                out.append(self._mk("from_clause", {"id": m.group(1)}, ll))
                self.pos += 1
                return
            m = _re_call_from.match(t)
            if m:
                target, fid = m.group(1).strip(), m.group(2)
                self.from_clauses.append({"kind": "call", "target": target, "id": fid})
                plain = bool(re.fullmatch(r"\w+", target))
                out.append(self._mk("call", {"label": target if plain else None,
                                             "expr": None if plain else target,
                                             "from_id": fid}, ll))
                self.pos += 1
                return
            m = _re_jump_from.match(t)
            if m:
                target, fid = m.group(1).strip(), m.group(2)
                self.from_clauses.append({"kind": "jump", "target": target, "id": fid})
                plain = bool(re.fullmatch(r"\w+", target))
                out.append(self._mk("jump", {"label": target if plain else None,
                                             "expr": None if plain else target,
                                             "from_id": fid}, ll))
                self.pos += 1
                return
            # screens with arguments:  call screen quiz(answer=1) with dissolve
            m = re.match(r"^call\s+screen\s+([\w.]+)\s*(?:\((.*)\))?\s*(?:with\s+(.+?))?\s*$", t)
            if m:
                out.append(self._mk("call_screen", {
                    "screen": m.group(1),
                    "args": self._parse_arg_list(m.group(2) or ""),
                    "transition": m.group(3)}, ll))
                self.pos += 1
                return
            m = _re_show_screen_args.match(t)
            if m:
                out.append(self._mk("show_screen", {
                    "screen": m.group(1),
                    "args": self._parse_arg_list(m.group(2) or ""),
                    "transition": m.group(3)}, ll))
                self.pos += 1
                return
            m = _re_hide_screen_args.match(t)
            if m:
                out.append(self._mk("hide_screen", {"screen": m.group(1)}, ll))
                self.pos += 1
                return
            # `for x in items:`
            m = _re_for.match(t)
            if m:
                target, iterable = m.group(1).strip(), m.group(2).strip()
                self._loop_id += 1
                loop_id = self._loop_id
                self._loop_stack.append(loop_id)
                self.pos += 1
                block: List[dict] = []
                if self.pos < len(self.lines) and self.lines[self.pos].indent > ll.indent:
                    self._parse_block(parent_indent=ll.indent, out=block)
                self._loop_stack.pop()
                self._consume_end(ll.indent, "for")
                out.append(self._mk("for", {"target": target, "iter": iterable,
                                            "block": block, "loop_id": loop_id}, ll))
                return
            # voice
            if _re_voice_sustain.match(t):
                out.append(self._mk("voice_sustain", {}, ll))
                self.pos += 1
                return
            if _re_voice_center.match(t):
                out.append(self._mk("voice", {"position": _re_voice_center.match(t).group(1)}, ll))
                self.pos += 1
                return
            m = _re_python_early.match(t)
            if m:
                code = self._capture_python_block(ll)
                out.append(self._mk("python", {"code": code, "early": True}, ll))
                return
            if _re_python.match(t):
                code = self._capture_python_block(ll)
                out.append(ASTNode("python", {"code": code},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                return
            if _re_while.match(t):
                cond = _re_while.match(t).group(1).strip()
                self._loop_id += 1
                loop_id = self._loop_id
                self._loop_stack.append(loop_id)
                self.pos += 1
                block: List[dict] = []
                if self._block_indent(ll, "while") is not None:
                    self._parse_block(parent_indent=ll.indent, out=block)
                self._loop_stack.pop()
                self._consume_end(ll.indent, "while")
                out.append(ASTNode("while", {"cond": cond, "block": block, "loop_id": loop_id},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                return
            if _re_break.match(t):
                out.append(ASTNode("break", {"loop_id": self._loop_stack[-1] if self._loop_stack else None},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                self.pos += 1
                return
            if _re_continue.match(t):
                out.append(ASTNode("continue", {"loop_id": self._loop_stack[-1] if self._loop_stack else None},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                self.pos += 1
                return
            if _re_pass.match(t):
                out.append(ASTNode("pass", {}, SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                self.pos += 1
                return
            if _re_window.match(t):
                mw = _re_window.match(t)
                out.append(ASTNode("window", {"value": mw.group(1),
                                              "transition": (mw.group(2).strip() or None)},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                self.pos += 1
                return
            if _re_nvl.match(t):
                mn = _re_nvl.match(t)
                out.append(ASTNode("nvl", {"action": mn.group(1),
                                           "transition": (mn.group(2).strip() or None)},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                self.pos += 1
                return
            if _re_nvl_mode.match(t):
                out.append(ASTNode("nvl_mode", {"mode": _re_nvl_mode.match(t).group(1)},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                self.pos += 1
                return
            if _re_voice.match(t):
                mv = _re_voice.match(t)
                out.append(ASTNode("play_voice", {"asset": mv.group(1) or mv.group(2) or mv.group(3)},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                self.pos += 1
                return
            if _re_queue_music.match(t):
                mq = _re_queue_music.match(t)
                out.append(ASTNode("play_music", {"asset": mq.group(1) or mq.group(2) or mq.group(3),
                                                  "fadein": float(mq.group(4)) if mq.group(4) else None,
                                                  "queue": True},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                self.pos += 1
                return
            if _re_queue_sound.match(t):
                mq = _re_queue_sound.match(t)
                out.append(ASTNode("play_sound", {"asset": mq.group(1) or mq.group(2) or mq.group(3), "queue": True},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                self.pos += 1
                return
            if _re_show_screen.match(t):
                out.append(ASTNode("show_screen", {"screen": _re_show_screen.match(t).group(1)},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                self.pos += 1
                return
            if _re_hide_screen.match(t):
                out.append(ASTNode("hide_screen", {"screen": _re_hide_screen.match(t).group(1)},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                self.pos += 1
                return
            if _re_call_screen.match(t):
                out.append(ASTNode("call_screen", {"screen": _re_call_screen.match(t).group(1)},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                self.pos += 1
                return
            if _re_jump_expr.match(t):
                out.append(ASTNode("jump", {"label": None, "expr": _re_jump_expr.match(t).group(1).strip()},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                self.pos += 1
                return
            if _re_call_expr.match(t):
                out.append(ASTNode("call", {"label": None, "expr": _re_call_expr.match(t).group(1).strip()},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                self.pos += 1
                return
            if _re_call_args.match(t):
                mca = _re_call_args.match(t)
                label, args = mca.group(1), self._parse_arg_list(mca.group(2))
                out.append(ASTNode("call", {"label": label, "args": args},
                                   SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                self.pos += 1
                return

        # safe mode: full-tier statement constructs are rejected with guidance
        if not self.full:
            for pat, what in (
                (_re_python, "python: blocks"),
                (_re_while, "while loops"),
                (_re_break, "break"),
                (_re_continue, "continue"),
                (_re_pass, "pass"),
                (_re_window, "window"),
                (_re_nvl, "nvl"),
                (_re_nvl_mode, "nvl mode"),
                (_re_voice, "voice"),
                (_re_queue_music, "queue music"),
                (_re_queue_sound, "queue sound"),
                (_re_show_screen, "show screen"),
                (_re_hide_screen, "hide screen"),
                (_re_call_screen, "call screen"),
                (_re_jump_expr, "jump expression"),
                (_re_call_expr, "call expression"),
                (_re_call_args, "call with arguments"),
                (_re_for, "for loops"),
                (_re_bare_from, "`from` clauses"),
                (re.compile(r"^call\s+screen\s+[\w.]+\s*\("), "call screen with arguments"),
                (_re_show_screen_args, "show screen"),
                (_re_hide_screen_args, "hide screen"),
                (_re_voice_sustain, "voice sustain"),
                (_re_centered, "centered text"),
                (_re_extend, "extend"),
            ):
                if pat.match(t):
                    raise ParseError(f"{what} require the full .rpy tier", ll.filename, ll.lineno, 1, ll.raw,
                                     hint="parse with mode='full' (or use a .urpy declarative script)")

        # ---- scene / show / hide — with `at`/`as`/`behind`/`zorder`/`onlayer`/`with`
        for kw, kind in (("scene", "scene"), ("show", "show"), ("hide", "hide")):
            m = re.match(r"^" + kw + r"\b\s*(.*)$", t)
            if not m:
                continue
            body = m.group(1).strip()
            # `show x at pos:` / `scene bg:` may carry an ATL block (renpy/parser.py
            # show_statement: `if l.match(":"): stmt.atl = parse_atl(…)`), and a
            # bare `scene` clears the layer (`ast.Scene(loc, None, layer)`).
            atl_block = self.full and body.endswith(":")
            if atl_block:
                body = body[:-1].strip()
            if not body and not (self.full and kind == "scene"):
                raise ParseError(f"{kw} needs a target", ll.filename, ll.lineno, 1, ll.raw,
                                 hint=f"example: {kw} bg classroom with dissolve")
            cl = _split_display_clauses(body)
            asset = (cl.get("asset") or "").strip()
            tag = asset.split()[0] if asset else asset
            if kind == "hide":
                data = {"tag": tag, "asset": asset, "transition": cl.get("transition")}
            else:
                data = {"asset": asset, "tag": tag,
                        "position": cl.get("position"), "transition": cl.get("transition")}
                for key in ("as_tag", "behind", "layer", "zorder"):
                    if cl.get(key) is not None:
                        data[key] = cl[key]
            if atl_block:
                data["atl"] = self._collect_atl_block(ll, kw)
            out.append(self._mk(kind, data, ll))
            if not atl_block:
                self.pos += 1
            return

        # ---- with (standalone): `with fade` / `with Dissolve(0.5)` / `with None`
        m = _re_with_any.match(t)
        if m and t.split()[0] != "window":
            out.append(self._mk("with", {"transition": m.group(1).strip()}, ll))
            self.pos += 1
            return

        # ---- audio: play / queue / stop <channel> (any options, full tier aware)
        m = _re_audio_any.match(t)
        if m:
            verb, channel, rest = m.group(1), m.group(2), m.group(3).strip()
            data: Dict[str, Any] = {"channel": channel, "queue": verb == "queue"}
            if verb == "stop":
                data["fadeout"] = self._parse_num_opt(rest, "fadeout")
                out.append(self._mk(f"stop_{channel}", data, ll))
                self.pos += 1
                return
            asset, rest = self._split_audio_asset(rest)
            data["asset"] = asset
            data["fadein"] = self._parse_num_opt(rest, "fadein")
            data["fadeout"] = self._parse_num_opt(rest, "fadeout")
            if re.search(r"(?<![\w])loop(?![\w])", rest):
                data["loop"] = True
            if re.search(r"(?<![\w])noloop(?![\w])", rest):
                data["loop"] = False
            wid = _find_top_keyword(rest, "with")
            if wid is not None:
                data["transition"] = rest[wid + 4:].strip()
            out.append(self._mk(f"play_{channel}", data, ll))
            self.pos += 1
            return

        # ---- pause: `pause` / `pause 1.5` / `pause delay` / `pause 1.0 with fade`
        m = _re_pause_any.match(t)
        if m and (m.group(1) or not m.group(2)):
            dur_raw = (m.group(1) or "").strip()
            duration: Any = None
            if dur_raw:
                try:
                    duration = float(dur_raw)
                except ValueError:
                    duration = dur_raw        # expression - evaluated at runtime
            out.append(self._mk("pause", {"duration": duration,
                                          "transition": m.group(2)}, ll))
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
                am = re.match(r"(\w+)\s*(\+=|-=|\*=|/=|=)\s*(.+)", expr, re.S)
                if not am:
                    if self.full:
                        # arbitrary python statement after `$` (full tier)
                        out.append(ASTNode("python", {"code": expr},
                                           SourceLocation(ll.filename, ll.lineno, ll.indent + 1)).to_dict())
                        self.pos += 1
                        return
                    raise ParseError(f"invalid assignment: {expr!r}", ll.filename, ll.lineno, 1, ll.raw,
                                     hint='example: set book = True  or  set affection += 1')
                target, op, val_expr = am.group(1), am.group(2), am.group(3)
            out.append(ASTNode("assign", {"target": target, "op": op, "expr": val_expr},
                               SourceLocation(ll.filename, ll.lineno, ll.indent+1)).to_dict())
            self.pos += 1
            return

        # ---- menu   (optionally named: `menu day_choices:` / `menu m(x):`)
        m_menu = _re_menu.match(t)
        if m_menu:
            self.pos += 1
            menu_node = self._mk("menu", {"choices": []}, ll)
            if m_menu.group(1):
                menu_node["name"] = m_menu.group(1)
            if m_menu.group(2) is not None:
                menu_node["args"] = self._parse_arg_list(m_menu.group(2))
            menu_indent = ll.indent
            self._parse_menu_items(menu_indent, menu_node, [])
            # optional explicit `end` closing the menu
            self._consume_end(menu_indent, "menu")
            if not menu_node["choices"]:
                raise ParseError("menu has no choices", ll.filename, ll.lineno, 1, ll.raw)
            out.append(menu_node)
            # Ren'Py: a named menu (`menu foo:`) is also a jump/call target
            if menu_node.get("name") and menu_node["name"] not in self.labels:
                import copy as _copy
                self.labels[menu_node["name"]] = [_copy.deepcopy(menu_node)]
            return

        # ---- if / elif / else
        m = _re_if.match(t)
        if m:
            return self._parse_if_chain(ll, parent_indent, out, first=True)
        # elif/else should not appear outside if — error
        if _re_elif.match(t) or _re_else.match(t):
            raise ParseError(f'"{t.split()[0]}" without matching "if"', ll.filename, ll.lineno, 1, ll.raw)

        # ---- extend / centered / vcentered narration
        m = _re_extend.match(t)
        if m:
            say = _split_say("x " + m.group(1).strip())
            if say is None:
                raise ParseError(f"extend needs a quoted string: {t!r}", ll.filename, ll.lineno, 1, ll.raw,
                                 hint='use: extend "more text"')
            out.append(self._mk("say", {"who": None, "text": say["text"], "extend": True,
                                        "expression": None, "nointeract": say["nointeract"]}, ll))
            self.pos += 1
            return
        m = _re_centered.match(t)
        if m:
            say = _split_say(m.group(2).strip())
            if say is None or say["who"] is not None:
                raise ParseError(f"{m.group(1)} needs a quoted string: {t!r}", ll.filename, ll.lineno, 1, ll.raw,
                                 hint='use: centered "text"')
            out.append(self._mk("say", {"who": None, "text": say["text"], "centered": m.group(1),
                                        "expression": None, "nointeract": say["nointeract"]}, ll))
            self.pos += 1
            return

        # ---- say / narration (attributes, @voice, nointeract, triple-quoted text)
        say = _split_say(t)
        if say is not None:
            data = {"who": say["who"], "expression": say["expression"], "text": say["text"]}
            if say["voice_attr"]:
                data["voice_attr"] = say["voice_attr"]
            if say["nointeract"]:
                data["nointeract"] = True
            if say["kwargs"]:
                data["kwargs"] = say["kwargs"]
            if say["inline"]:
                data["inline"] = say["inline"]
            if say.get("id"):
                data["id"] = say["id"]
            out.append(self._mk("say", data, ll))
            self.pos += 1
            return

        # ---- style block used as a statement inside a label (full tier)
        if self.full and _re_style_block.match(t):
            name = _re_style_block.match(t).group(1)
            self.pos += 1
            lines: List[str] = []
            while self.pos < len(self.lines) and self.lines[self.pos].indent > ll.indent:
                lines.append(self.lines[self.pos].text)
                self.pos += 1
            self._consume_end(ll.indent, "style")
            self.styles[name] = {"lines": lines}
            return

        # ---- fallback
        if _re_end.match(t):
            raise ParseError(f"unexpected 'end' — no open block to close at this indentation",
                             ll.filename, ll.lineno, 1, ll.raw,
                             hint="'end' must be dedented to the same level as the block it closes (label/menu/if/state/character/choice)")
        if self.full:
            name = self._match_custom(t)
            if name is not None:
                self._parse_custom_statement(ll, name, out)
                return
        raise ParseError(f"unknown statement: {t!r}", ll.filename, ll.lineno, 1, ll.raw,
                         hint=self._hint_for_unknown(t))

    # ---------------------------- menu body (choices + pre-statements + if/else)
    def _parse_menu_items(self, parent_indent: int, menu_node: dict, cond_stack: List[str]):
        """Parse one level of a `menu:` body.

        Accepts, at the same indentation:
          * ``"Choice text":`` (+ its indented block) and the declarative
            ``choice "Text":`` form,
          * an optional caption (a bare quoted line before the first choice),
          * ``set`` / ``$`` / ``python:`` statements shown before the choices,
          * nested ``if`` / ``elif`` / ``else`` blocks that filter choices.
        """
        item_indent: Optional[int] = None
        while self.pos < len(self.lines):
            choice_ll = self.lines[self.pos]
            if choice_ll.indent <= parent_indent:
                break
            if item_indent is None:
                if not self.full:
                    expected = parent_indent + 4
                    if choice_ll.indent != expected:
                        raise ParseError(
                            f"choice must be indented {expected} spaces, got {choice_ll.indent}",
                            choice_ll.filename, choice_ll.lineno, choice_ll.indent + 1, choice_ll.raw,
                            hint='inside menu:\n    "Choice text":\n        jump somewhere'
                        )
                item_indent = choice_ll.indent
            elif choice_ll.indent != item_indent:
                raise ParseError(
                    f"unexpected indent: expected {item_indent} spaces, got {choice_ll.indent}",
                    choice_ll.filename, choice_ll.lineno, choice_ll.indent + 1, choice_ll.raw,
                    hint=f"choices in the same menu must all be indented {item_indent} spaces"
                )

            ct = choice_ll.text.strip()

            # `menu foo:` + `set variable` — Ren'Py's menu "set" declaration
            m_setname = re.match(r"^set\s+(\w+)\s*$", ct)
            if m_setname:
                menu_node["set"] = m_setname.group(1)
                self.pos += 1
                continue

            # statements allowed before/next to the choices (Ren'Py: `set`, `$`, `python:`)
            if _re_set.match(ct) or _re_assign.match(ct) or _re_pass.match(ct) \
                    or (self.full and _re_python.match(ct)):
                stmts: List[dict] = []
                self._parse_statement(choice_ll, item_indent, stmts)
                menu_node.setdefault("pre", []).extend(stmts)
                continue

            # nested conditional choice groups
            if _re_if.match(ct):
                self._parse_menu_if_chain(choice_ll, menu_node, cond_stack)
                continue

            # `choice "Text":` — declarative keyword form (M15)
            m_choice = _re_choice.match(ct)
            if m_choice:
                choice_text = m_choice.group(1) if m_choice.group(1) is not None else m_choice.group(2)
                self.pos += 1
                choice_block: List[dict] = []
                if self.pos < len(self.lines) and self.lines[self.pos].indent > choice_ll.indent:
                    self._parse_block(parent_indent=choice_ll.indent, out=choice_block)
                self._consume_end(choice_ll.indent, "choice")
                menu_node["choices"].append({
                    "text": choice_text, "block": choice_block,
                    "cond": " and ".join(cond_stack) if cond_stack else None,
                    "_loc": {"file": choice_ll.filename, "line": choice_ll.lineno}})
                continue

            colon = ct.endswith(":")
            choice_cond: Optional[str] = None
            if colon:
                # The quoted caption always comes first; only what follows it
                # can be inline properties or an `if` condition (so the word
                # "if" *inside* the caption stays part of the text).
                choice_text_raw = ct[:-1].strip()
                q = extract_quoted(choice_text_raw)
                if not q:
                    raise ParseError(f'menu choice must be a quoted string, got: {ct!r}',
                                     choice_ll.filename, choice_ll.lineno, 1, choice_ll.raw)
                choice_text = q[0]
                tail = choice_text_raw[q[2]:].strip()
                if tail.startswith("("):
                    close = _matching_close_paren(tail)
                    if close is not None:
                        for kv in _split_args(tail[1:close]):
                            if "=" in kv:
                                k, v = kv.split("=", 1)
                                menu_node.setdefault("choice_props", {})[k.strip()] = v.strip()
                        tail = tail[close + 1:].strip()
                if tail.startswith("if ") or tail == "if":
                    choice_cond = tail[2:].strip() or None
                elif tail:
                    raise ParseError(f"unexpected text after a menu choice: {tail!r}",
                                     choice_ll.filename, choice_ll.lineno, 1, choice_ll.raw,
                                     hint='write: "Choice text" (icon="x") if condition:')
            else:
                # no colon — Ren'Py allows dialogue before the choices, and a
                # bare quoted line is the menu caption
                say = _split_say(ct)
                if say is not None and say["who"] is not None:
                    stmts = []
                    self._parse_statement(choice_ll, item_indent, stmts)
                    menu_node.setdefault("pre", []).extend(stmts)
                    continue
                q = extract_quoted(ct)
                if q:
                    if not menu_node["choices"] and "caption" not in menu_node:
                        menu_node["caption"] = q[0]
                        self.pos += 1
                        continue
                    raise ParseError(f'menu choice missing colon: {ct!r}',
                                     choice_ll.filename, choice_ll.lineno, 1, choice_ll.raw,
                                     hint='write: "Choice text":')
                raise ParseError(f"unexpected line in menu: {ct!r}", choice_ll.filename, choice_ll.lineno, 1,
                                 choice_ll.raw, hint='inside menu: "Choice text": then indented block')

            self.pos += 1  # step past the choice line
            choice_block = []
            if self.pos < len(self.lines) and self.lines[self.pos].indent > choice_ll.indent:
                self._parse_block(parent_indent=choice_ll.indent, out=choice_block)

            conds = list(cond_stack)
            if choice_cond:
                conds.append(f"({choice_cond})")
            menu_node["choices"].append({
                "text": choice_text, "block": choice_block,
                "cond": " and ".join(conds) if conds else None,
                "_loc": {"file": choice_ll.filename, "line": choice_ll.lineno}})

    def _parse_menu_if_chain(self, ll: LogicalLine, menu_node: dict, cond_stack: List[str]):
        """`if`/`elif`/`else` inside a menu — choices inherit the condition."""
        m = _re_if.match(ll.text)
        assert m
        cond = m.group(1).strip()
        negations: List[str] = []

        def walk(cond_expr: Optional[str]):
            stack = list(cond_stack) + negations
            if cond_expr is not None:
                stack.append(f"({cond_expr})")
            self._parse_menu_items(ll.indent, menu_node, stack)

        self.pos += 1
        walk(cond)
        negations.append(f"not ({cond})")

        while self.pos < len(self.lines):
            nxt = self.lines[self.pos]
            if nxt.indent != ll.indent:
                break
            m2 = _re_elif.match(nxt.text)
            if m2:
                cond2 = m2.group(1).strip()
                self.pos += 1
                walk(cond2)
                negations.append(f"not ({cond2})")
                continue
            if _re_else.match(nxt.text):
                self.pos += 1
                walk(None)
                break
            if _re_end.match(nxt.text):
                self.pos += 1
                break
            break

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
        if self._block_indent(ll, "if") is not None:
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
                if self._block_indent(nxt, "elif") is not None:
                    self._parse_block(parent_indent=nxt.indent, out=blk2)
                branches.append({"cond": cond2, "block": blk2})
                continue
            if _re_else.match(nxt.text):
                self.pos += 1
                blk3: List[dict] = []
                if self._block_indent(nxt, "else") is not None:
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
            from .literals import eval_literal
            return eval_literal(expr)
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


def parse_string(source: str, filename: str = "<string>", mode: str = "safe",
                 require_start: bool = True, custom_statements=()) -> dict:
    """Parse a `.rpy` script. mode='safe' (default) or 'full' (drop-in Ren'Py).

    ``require_start=False`` is for one file of a multi-file game — the entry
    label may live in another file (checked on the merged script).
    ``custom_statements`` are keywords the project registers itself; see
    :func:`discover_custom_statements`.
    """
    return Parser(source, filename, full=(mode == "full"),
                  require_start=require_start,
                  custom_statements=custom_statements).parse()


def parse_string_full(source: str, filename: str = "<string>",
                      require_start: bool = True, custom_statements=()) -> dict:
    return parse_string(source, filename, mode="full", require_start=require_start,
                        custom_statements=custom_statements)


def scan_register_statements(source: str) -> Dict[str, Optional[str]]:
    """Map each ``renpy.register_statement`` name to its ``block=`` type.

    ``block="script"`` means Ren'Py parses the statement's body as script, so
    labels declared inside it are real labels (the SDK tutorial puts
    ``label play_pong:`` inside an ``example`` block this way). Anything else —
    or no ``block=`` at all — means the body is opaque to us.
    """
    out: Dict[str, Optional[str]] = {}
    for m in re.finditer(r"register_statement\s*\(", source):
        open_at = m.end() - 1
        # _matching_close_paren indexes into the slice we hand it, so the
        # offset has to be added back before it can index `source`
        rel = _matching_close_paren(source[open_at:])
        if rel is None:
            continue
        body = source[open_at + 1 : open_at + rel]
        nm = re.match(r"""\s*["']([^"']+)["']""", body)
        if not nm:
            continue
        blk = re.search(r"""block\s*=\s*["'](\w+)["']""", body)
        out[nm.group(1)] = blk.group(1) if blk else None
    return out


def discover_custom_statements(sources) -> Dict[str, Optional[str]]:
    """Statement keywords a project registers for itself -> their block type.

    Ren'Py collects `renpy.register_statement("NAME", parse=…, execute=…)` at
    init time, and a registration in one file makes `NAME` usable everywhere in
    the project — so discovery has to be project-wide, not per file. Pass the
    result to every :class:`Parser` of that project.
    """
    found: Dict[str, Optional[str]] = {n: None for n in _BUILTIN_CUSTOM_STATEMENTS}
    for src in sources:
        if src:
            found.update(scan_register_statements(src))
    return {n: b for n, b in found.items() if n.strip()}


def parse_file(path: str, mode: str = "safe", require_start: bool = True,
               custom_statements=()) -> dict:
    """Parse a script file. `.urpy` → declarative parser; else `.rpy` parser.

    ``require_start`` (default True) demands a ``start`` label in the file;
    pass False when parsing individual files of a multi-file game directory
    (the entry label is then checked on the merged script).
    """
    from pathlib import Path
    p = Path(path)
    if p.suffix.lower() == ".urpy":
        from .urpy_parser import parse_urpy_file
        return parse_urpy_file(str(p), require_start=require_start)
    with open(str(p), "r", encoding="utf-8") as f:
        return parse_string(f.read(), filename=str(p), mode=mode, require_start=require_start,
                            custom_statements=custom_statements)
