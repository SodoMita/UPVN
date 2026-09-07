"""
UPVN — Error types
Mirrors Ren'Py's ParseError / ScriptError but with friendly diagnostics
for LLM agents and human authors.
"""
from __future__ import annotations


class UPVNError(Exception):
    """Base for all UPVN errors."""


class ParseError(UPVNError, SyntaxError):
    def __init__(
        self,
        message: str,
        filename: str = "<string>",
        lineno: int = 1,
        col: int | None = None,
        line_text: str | None = None,
        hint: str | None = None,
    ):
        self.filename = filename
        self.lineno = lineno
        self.col = col
        self.line_text = line_text
        self.hint = hint
        full = f'{filename}:{lineno}'
        if col is not None:
            full += f':{col}'
        full += f': {message}'
        if line_text is not None:
            full += f'\n    {line_text.rstrip()}'
            if col is not None:
                full += f"\n    {' ' * (col - 1)}^"
        if hint:
            full += f"\nHint: {hint}"
        super().__init__(full)
        self.msg = message  # for compatibility

    def __str__(self):
        return self.args[0]


class ScriptRuntimeError(UPVNError):
    def __init__(self, message: str, label: str | None = None, index: int | None = None):
        loc = ""
        if label is not None:
            loc = f" [{label}:{index}]" if index is not None else f" [{label}]"
        super().__init__(f"{message}{loc}")
        self.label = label
        self.index = index


class LabelNotFoundError(ScriptRuntimeError):
    pass


class AssetNotFoundError(ScriptRuntimeError):
    pass
