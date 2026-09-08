"""
UPVN — AST-whitelisted expression evaluator (declarative expressions)

Replaces raw Python `eval` for `if` / `elif` / `set` / `$` expressions.

The story language is declarative, so expressions are limited to a small,
deterministic subset of Python: literals, names, arithmetic, comparisons,
boolean operators, `in` / `not in`, ternary, container literals and
*container* subscripting (``items[0]``, ``flags["x"]``), plus a fixed
allowlist of pure functions (``len``, ``int``, ``float``, ``str``, ``bool``,
``abs``, ``min``, ``max``).

Attribute access is only permitted on explicitly injected objects
(``renpy`` / ``store`` in the trusted full tier), never on dunder names,
and never on arbitrary values. This closes the classic sandbox escape
(``().__class__.__mro__[1].__subclasses__()...``) and keeps scripts
analyzable (criticism #6: no arbitrary Python inside story script).
"""
from __future__ import annotations
import ast
from typing import Any, Dict, Optional

from ..core.vn_errors import ScriptRuntimeError

# ------------------------------------------------------------------ operators
_BIN_OPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
}

_UNARY_OPS = {
    ast.UAdd: lambda a: +a,
    ast.USub: lambda a: -a,
    ast.Not: lambda a: not a,
}

_CMP_OPS = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
    ast.Is: lambda a, b: a is b,
    ast.IsNot: lambda a, b: a is not b,
}

# Pure functions we allow by name (no imports, no methods, no attribute calls)
_ALLOWED_FUNCTIONS: Dict[str, Any] = {
    "len": len,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "abs": abs,
    "min": min,
    "max": max,
}

# Literal constants available by name (variables shadow them)
_ALLOWED_NAMES: Dict[str, Any] = {"True": True, "False": False, "None": None}


class ExpressionEvaluator:
    """Evaluate a declarative expression against a variables dict.

    ``extra`` maps root names to injected objects (e.g. ``renpy``, ``store``)
    whose attributes may be read — but ONLY on these injected objects, and
    never on names starting with ``_``. That keeps the sandbox closed while
    allowing the trusted full tier to call ``renpy.loadable(...)`` etc.
    """

    def __init__(self, extra: Optional[Dict[str, Any]] = None):
        self.extra = extra or {}

    def evaluate(self, expr: str, variables: Dict[str, Any]) -> Any:
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as e:
            raise ScriptRuntimeError(f"invalid expression {expr!r}: {e}")
        return self._eval(tree.body, variables)

    # ---------------------------------------------------------------- nodes
    def _eval(self, node: ast.AST, variables: Dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.Name):
            if node.id in variables:
                return variables[node.id]
            if node.id in _ALLOWED_NAMES:
                return _ALLOWED_NAMES[node.id]
            if node.id in self.extra:
                return self.extra[node.id]
            raise ScriptRuntimeError(f"unknown variable {node.id!r}")

        if isinstance(node, ast.BinOp):
            op = _BIN_OPS.get(type(node.op))
            if op is None:
                raise ScriptRuntimeError(f"operator {type(node.op).__name__} not allowed")
            return op(self._eval(node.left, variables), self._eval(node.right, variables))

        if isinstance(node, ast.UnaryOp):
            op = _UNARY_OPS.get(type(node.op))
            if op is None:
                raise ScriptRuntimeError(f"unary operator {type(node.op).__name__} not allowed")
            return op(self._eval(node.operand, variables))

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                # short-circuit
                result = True
                for v in node.values:
                    result = self._eval(v, variables)
                    if not result:
                        return result
                return result
            if isinstance(node.op, ast.Or):
                result = False
                for v in node.values:
                    result = self._eval(v, variables)
                    if result:
                        return result
                return result
            raise ScriptRuntimeError(f"boolean operator {type(node.op).__name__} not allowed")

        if isinstance(node, ast.Compare):
            left = self._eval(node.left, variables)
            for op_node, comp in zip(node.ops, node.comparators):
                right = self._eval(comp, variables)
                op = _CMP_OPS.get(type(op_node))
                if op is None:
                    raise ScriptRuntimeError(f"comparison {type(op_node).__name__} not allowed")
                if not op(left, right):
                    return False
                left = right
            return True

        if isinstance(node, ast.IfExp):
            if self._eval(node.test, variables):
                return self._eval(node.body, variables)
            return self._eval(node.orelse, variables)

        # container literals (elements are themselves evaluated, so nested
        # non-literals still go through the whitelist)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            values = [self._eval(e, variables) for e in node.elts]
            if isinstance(node, ast.List):
                return values
            if isinstance(node, ast.Tuple):
                return tuple(values)
            return set(values)

        if isinstance(node, ast.Dict):
            out = {}
            for k, v in zip(node.keys, node.values):
                if k is None:  # ** unpacking
                    raise ScriptRuntimeError("dict unpacking (**) not allowed")
                out[self._eval(k, variables)] = self._eval(v, variables)
            return out

        if isinstance(node, ast.Call):
            return self._eval_call(node, variables)

        if isinstance(node, ast.Attribute):
            return self._eval_attribute(node, variables)

        if isinstance(node, ast.Subscript):
            return self._eval_subscript(node, variables)

        # explicitly rejected constructs
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            raise ScriptRuntimeError("comprehensions are not allowed in expressions")
        if isinstance(node, ast.Lambda):
            raise ScriptRuntimeError("lambda is not allowed in expressions")
        if isinstance(node, ast.NamedExpr):
            raise ScriptRuntimeError("walrus operator ':=' is not allowed in expressions")

        raise ScriptRuntimeError(f"expression node {type(node).__name__} not allowed")

    # ---------------------------------------------------------------- attribute access
    def _eval_attribute(self, node: ast.Attribute, variables: Dict[str, Any]) -> Any:
        name = node.attr
        if name.startswith("_"):
            raise ScriptRuntimeError(f"attribute {name!r} is not allowed in expressions")
        obj = self._eval_attr_base(node.value, variables)
        try:
            return getattr(obj, name)
        except AttributeError:
            raise ScriptRuntimeError(f"object has no attribute {name!r}")

    def _eval_attr_base(self, node: ast.AST, variables: Dict[str, Any]) -> Any:
        """Resolve the object an attribute is read from.

        Only injected roots (``renpy`` / ``store``) — and objects reached by
        walking their attributes — may be traversed. Everything else is
        rejected, which keeps ``().__class__...`` escapes impossible.
        """
        if isinstance(node, ast.Name):
            if node.id in self.extra:
                return self.extra[node.id]
            raise ScriptRuntimeError(
                f"attribute access is only allowed on injected objects (renpy/store), not {node.id!r}")
        if isinstance(node, ast.Attribute):
            return self._eval_attribute(node, variables)
        raise ScriptRuntimeError("attribute access is not allowed in expressions")

    # ---------------------------------------------------------------- subscripting
    def _eval_subscript(self, node: ast.Subscript, variables: Dict[str, Any]) -> Any:
        base = self._eval(node.value, variables)
        if not isinstance(base, (list, tuple, dict, str)):
            raise ScriptRuntimeError("subscripting ('[]') is not allowed in expressions")
        if isinstance(node.slice, ast.Slice):
            raise ScriptRuntimeError("slices are not allowed in expressions")
        index = self._eval(node.slice, variables)
        try:
            return base[index]
        except Exception as e:
            raise ScriptRuntimeError(f"subscript: {e}")

    # ---------------------------------------------------------------- calls
    def _eval_call(self, node: ast.Call, variables: Dict[str, Any]) -> Any:
        if node.keywords:
            raise ScriptRuntimeError("keyword arguments are not allowed in expressions")
        args = [self._eval(a, variables) for a in node.args]

        func = node.func
        if isinstance(func, ast.Name):
            name = func.id
            if name in _ALLOWED_FUNCTIONS:
                try:
                    return _ALLOWED_FUNCTIONS[name](*args)
                except Exception as e:
                    raise ScriptRuntimeError(f"{name}(...): {e}")
            if name in self.extra:
                obj = self.extra[name]
                if callable(obj):
                    try:
                        return obj(*args)
                    except Exception as e:
                        raise ScriptRuntimeError(f"{name}(...): {e}")
            raise ScriptRuntimeError(f"function {name!r} is not allowed")

        if isinstance(func, ast.Attribute):
            # call on an injected object's attribute (e.g. renpy.loadable(...))
            callee = self._eval_attribute(func, variables)
            if not callable(callee):
                raise ScriptRuntimeError(f"{func.attr!r} is not callable")
            try:
                return callee(*args)
            except ScriptRuntimeError:
                raise
            except Exception as e:
                raise ScriptRuntimeError(f"{func.attr}(...): {e}")

        raise ScriptRuntimeError("only simple function calls are allowed (e.g. len(x))")


def evaluate(expr: str, variables: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> Any:
    """Evaluate a declarative expression (whitelisted subset of Python).

    ``extra`` optionally injects objects (``renpy``/``store``) whose
    attributes may be read (trusted full tier).
    """
    return ExpressionEvaluator(extra).evaluate(expr, variables)
