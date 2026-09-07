"""
UPVN — Lexer for .rpy subset

Handles the few lexical concerns Ren'Py cares about:
- logical line grouping (indent-sensitive)
- comment stripping
- string literal extraction (preserve for say/narration)

We intentionally keep story script (.rpy) and Python extension code (.py)
separate — no `init python` blocks in story files.  For state mutation
authors use:
    default affection = 0
    $ affection += 1          (mapped to safe eval)
    if affection >= 3:
rather than arbitrary python: blocks (see doc §4 / §11).

Indentation: Ren'Py *requires* spaces, case-sensitive, indent matters.
We follow same: count leading spaces, require consistent indent stack.
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


def group_logical_lines(source: str, filename: str = "<string>") -> List[LogicalLine]:
    """
    Split source into logical lines, stripping comments/empties but preserving
    indent for parser.  Ren'Py's lexer.group_logical_lines does more (continuations,
    triple-quoted), we keep minimal for Tier1 and expand as needed.
    """
    # Strip BOM if present (Ren'Py scripts often start with \ufeff)
    if source and source[0] == "\ufeff":
        source = source[1:]
    lines: List[LogicalLine] = []
    for idx, raw in enumerate(source.splitlines(), start=1):
        # keep raw for error display
        stripped_trailing = raw.rstrip("\n")
        # Strip comments — but not inside strings (naïve, ok for Tier1)
        # We only strip if # appears outside quotes.
        code_part = _strip_comment_outside_strings(stripped_trailing)
        if code_part.strip() == "":
            continue  # blank or comment-only
        try:
            indent = _count_indent(code_part)
        except ValueError as e:
            raise ParseError(str(e), filename, idx, 1, raw, hint="Use spaces, not tabs.")

        text = code_part.lstrip(" ")
        lines.append(LogicalLine(text=text, indent=indent, raw=raw, lineno=idx, filename=filename))
    return lines


def _strip_comment_outside_strings(line: str) -> str:
    """Remove trailing # comment unless inside quotes."""
    in_single = False
    in_double = False
    esc = False
    for i, ch in enumerate(line):
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i]
    return line


# ------------------------------------------------------------------ helpers
_string_re = re.compile(r'''(?:"([^"\\]*(?:\\.[^"\\]*)*)"|'([^'\\]*(?:\\.[^'\\]*)*)')''')

def extract_quoted(text: str) -> Optional[Tuple[str, int, int]]:
    """
    Find first quoted string in text, return (content, start, end).
    Handles escaped quotes.
    """
    m = _string_re.search(text)
    if not m:
        return None
    content = m.group(1) if m.group(1) is not None else m.group(2)
    # unescape \" \' \n etc. via python's unicode_escape? keep simple
    content = bytes(content, "utf-8").decode("unicode_escape")
    return content, m.start(), m.end()


def is_quoted_line(text: str) -> bool:
    return (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'"))
