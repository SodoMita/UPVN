"""
UPVN — shared literal/type helpers for the script parsers

Used by both the `.rpy` parser (safe subset + full) and the `.urpy` parser.
State values are restricted to JSON-safe literals (no code execution) and,
when declared, are checked against their type.
"""
from __future__ import annotations
import ast
from typing import Any, Tuple

# allowed type names for `state:` declarations
TYPE_NAMES = {"int", "float", "str", "string", "bool", "list"}

# default value when a typed declaration omits an initialiser
TYPE_DEFAULTS = {
    "int": 0,
    "float": 0.0,
    "str": "",
    "string": "",
    "bool": False,
    "list": [],
}


def normalize_type(name: str) -> str:
    return "str" if name == "string" else name


def type_default(name: str) -> Any:
    return TYPE_DEFAULTS[normalize_type(name)]


def check_value_type(value: Any, type_name: str) -> Tuple[bool, str]:
    """Return (ok, error_message) for a value against a declared type."""
    t = normalize_type(type_name)
    if t == "int":
        ok = (not isinstance(value, bool)) and isinstance(value, int)
    elif t == "float":
        ok = (not isinstance(value, bool)) and isinstance(value, (int, float))
    elif t == "str":
        ok = isinstance(value, str)
    elif t == "bool":
        ok = isinstance(value, bool)
    elif t == "list":
        ok = isinstance(value, list)
    else:
        return True, ""  # unknown type name — leave unvalidated
    if ok:
        return True, ""
    return False, f"expected {t}, got {type(value).__name__}"


def coerce_value(value: Any, type_name: str) -> Tuple[bool, Any]:
    """Validate/coerce a value to a declared type. Returns (ok, value)."""
    t = normalize_type(type_name)
    ok, _ = check_value_type(value, type_name)
    if ok:
        if t == "float" and (not isinstance(value, bool)) and isinstance(value, int):
            return True, float(value)
        return True, value
    return False, value


def eval_literal(expr: str) -> Any:
    """Evaluate a JSON-safe literal. Raises ValueError on non-literals."""
    return ast.literal_eval(expr.strip())
