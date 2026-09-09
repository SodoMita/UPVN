"""
UPVN — Lexer for .rpy subset

Handles the lexical concerns Ren'Py cares about:
- logical line grouping (indent-sensitive)
- comment stripping (never inside strings)
- string literal extraction (preserve for say/narration)
- **triple-quoted strings** spanning several physical lines (``\"\"\"…\"\"\"``)
- **line continuation** with a trailing backslash (``\\``)

We intentionally keep story script (.rpy) and Python extension code (.py)
separate — no `init python` blocks in story files.  For state mutation
authors use:
    default affection = 0
    $ affection += 1          (mapped to safe eval)
    if affection >= 3:
rather than arbitrary python: blocks (see doc §4 / §11).

Indentation: Ren'Py *requires* spaces, case-sensitive, indent matters.
We follow same: count leading spaces, require a consistent indent stack.
Helpful error if mixed tabs/spaces or mis-aligned choice body.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional

from ..core.vn_errors import ParseError


@dataclass
class LogicalLine:
    text: str          # stripped content (no leading indent)
    indent: int        # number of leading spaces
    raw: str           # original line incl. newline
    lineno: int
    filename: str


def _count_indent(line: str) -> int:
    if "\t" in line[: len(line) - len(line.lstrip())]:
        # Ren'Py docs: indentation must use spaces
        raise ValueError("tabs are not allowed — use spaces")
    return len(line) - len(line.lstrip(" "))


_TRIPLE = ('"""', "'''")


def _scan_line(line: str, open_str: Optional[str]) -> Tuple[str, Optional[str]]:
    """Scan one physical line, returning ``(code, still_open_string)``.

    ``code`` is the line with any trailing ``#`` comment removed (comments are
    only recognised outside of strings).  ``still_open_string`` is the delimiter
    (``\"\"\"``, ``'''``, ``\"`` or ``'``) when a string was left open — the
    logical line then continues on the next physical line.

    That is not a workaround: Ren'Py lexes string literals with ``re.DOTALL``
    (renpy/lexer.py ``match_regexp``), so ``e "one\n   two."`` written across
    two physical lines is one string in Ren'Py and must be one here too.
    """
    out: List[str] = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if open_str:                            # inside a string opened earlier
            if ch == "\\" and i + 1 < n:
                out.append(ch)
                out.append(line[i + 1])
                i += 2
                continue
            if line.startswith(open_str, i):
                out.append(open_str)
                i += len(open_str)
                open_str = None
                continue
            out.append(ch)
            i += 1
            continue
        # not inside a string
        if line.startswith('\"\"\"', i) or line.startswith("'''", i):
            open_str = line[i : i + 3]
            out.append(open_str)
            i += 3
            continue
        if ch in ('"', "'"):
            open_str = ch
            out.append(ch)
            i += 1
            continue
        if ch == "#":                           # comment — rest of line dropped
            break
        out.append(ch)
        i += 1
    return "".join(out), open_str


def _strip_comment_outside_strings(line: str) -> str:
    """Remove trailing # comment unless inside quotes (kept for compatibility)."""
    code, _ = _scan_line(line, None)
    return code


def _bracket_balance(text: str) -> int:
    """Net bracket depth of a code fragment (string-aware, never negative)."""
    depth = 0
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in ('"', "'"):
            if text.startswith(ch * 3, i):
                end = text.find(ch * 3, i + 3)
                i = n if end == -1 else end + 3
                continue
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == ch:
                    j += 1
                    break
                j += 1
            i = j
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        i += 1
    return depth


def group_logical_lines(source: str, filename: str = "<string>") -> List[LogicalLine]:
    """
    Split source into logical lines, stripping comments/empties but preserving
    indent for the parser.

    Physical lines are merged into one logical line when
      * a triple-quoted string is left open (newlines inside are preserved),
      * the line ends with a single backslash (continuation, newline dropped), or
      * brackets are left unbalanced — ``call screen foo(`` … ``)`` spans lines
        exactly like it does in Ren'Py/Python (joined with a space).
    """
    # Strip BOM (Ren'Py scripts often start with \ufeff — and a concatenated
    # multi-file source carries one per file, so drop them all)
    if "\ufeff" in source:
        source = source.replace("\ufeff", "")
    physical = source.splitlines()
    lines: List[LogicalLine] = []

    parts: List[Tuple[str, bool]] = []   # (code, keep_newline_after)
    acc = ""                              # accumulated logical line (for bracket balance)
    start_lineno = 0
    start_raw = ""
    indent: Optional[int] = None
    open_str: Optional[str] = None   # delimiter of a string left open (1 or 3 chars)

    def flush():
        nonlocal parts, indent, acc
        if not parts:
            return
        text = "".join(code + ("\n" if nl else "") for code, nl in parts)
        if text.strip() != "":
            assert indent is not None
            lines.append(LogicalLine(text=text.lstrip(" "), indent=indent,
                                     raw=start_raw, lineno=start_lineno, filename=filename))
        parts = []
        acc = ""
        indent = None

    for idx, raw in enumerate(physical, start=1):
        if not parts:
            start_lineno, start_raw = idx, raw
        code, open_after = _scan_line(raw, open_str)
        if indent is None:
            try:
                indent = _count_indent(code)
            except ValueError:
                raise ParseError("tabs are not allowed — use spaces", filename, idx, 1, raw,
                                 hint="Use spaces, not tabs.")

        if open_after:                          # string continues on the next line
            parts.append((code, True))
            open_str = open_after
            acc = "".join(c + ("\n" if nl else "") for c, nl in parts)
            continue
        open_str = None

        stripped = code.rstrip()
        if stripped.endswith("\\") and not stripped.endswith("\\\\"):
            parts.append((stripped[:-1], False))  # explicit continuation
            acc = (acc + " " + stripped[:-1]).strip()
            continue

        parts.append((code, False))
        acc = (acc + " " + code).strip()
        if _bracket_balance(acc) > 0:             # unbalanced brackets → keep going
            continue
        flush()

    if open_str:
        if len(open_str) == 3:
            raise ParseError(
                "unterminated triple-quoted string",
                filename, start_lineno, 1, start_raw,
                hint='close it with the same delimiter (""" … """)',
            )
        raise ParseError(
            "unterminated string",
            filename, start_lineno, 1, start_raw,
            hint=f"close it with {open_str} — Ren'Py lets a string run over several\n"
                 f"lines, but it still needs its closing {open_str}",
        )
    flush()   # tolerate a trailing continuation at EOF
    return lines


# ------------------------------------------------------------------ helpers
def _unescape(content: str) -> str:
    """Resolve \\n, \\", \\' … without mangling non-ASCII characters."""
    if "\\" not in content:
        return content
    try:
        return content.encode("utf-8", "backslashreplace").decode("unicode_escape").encode(
            "latin-1", "backslashreplace").decode("utf-8", "replace")
    except (UnicodeDecodeError, ValueError):
        return content


def extract_quoted(text: str) -> Optional[Tuple[str, int, int]]:
    """
    Find first quoted string in text, return (content, start, end).
    Handles escaped quotes and triple-quoted (multi-line) strings.
    """
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in ('"', "'"):
            if text.startswith(ch * 3, i):          # """…""" / '''…'''
                end = text.find(ch * 3, i + 3)
                if end == -1:
                    return None
                return text[i + 3 : end], i, end + 3
            buf: List[str] = []
            j = i + 1
            while j < n:
                c = text[j]
                if c == "\\" and j + 1 < n:
                    buf.append(text[j : j + 2])
                    j += 2
                    continue
                if c == ch:
                    return _unescape("".join(buf)), i, j + 1
                buf.append(c)
                j += 1
            return None                              # unterminated
        i += 1
    return None


def is_quoted_line(text: str) -> bool:
    return (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'"))
