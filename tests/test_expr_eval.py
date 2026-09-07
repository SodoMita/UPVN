"""AST-whitelist expression evaluator — allows the declarative subset, blocks escapes."""
import pytest
from engine.script.expr_eval import evaluate
from engine.core.vn_errors import ScriptRuntimeError


def test_arithmetic_and_comparisons():
    v = {"affection": 2, "route": "good"}
    assert evaluate("affection + 1", v) == 3
    assert evaluate("affection * 3 - 1", v) == 5
    assert evaluate("affection >= 1", v) is True
    assert evaluate("affection == 3", v) is False
    assert evaluate("affection != 3 and route == 'good'", v) is True


def test_containers_and_membership():
    v = {"x": 1, "items": [1, 2, 3]}
    assert evaluate("x in items", v) is True
    assert evaluate("5 not in items", v) is True
    assert evaluate("[1, 2] + [3]", v) == [1, 2, 3]
    with pytest.raises(ScriptRuntimeError):
        evaluate("{'a': 1}['a']", {})


def test_allowed_functions():
    v = {"s": "hello", "xs": [3, 1, 2]}
    assert evaluate("len(s)", v) == 5
    assert evaluate("max(xs)", v) == 3
    assert evaluate("int('5')", v) == 5
    assert evaluate("bool(0)", v) is False
    assert evaluate("abs(-3)", v) == 3


def test_ternary():
    v = {"n": 2}
    assert evaluate("'yes' if n > 1 else 'no'", v) == "yes"


def test_blocked_attribute_access():
    with pytest.raises(ScriptRuntimeError):
        evaluate("().__class__", {})


def test_blocked_comprehension_escape():
    payload = "[c for c in ().__class__.__mro__[1].__subclasses__() if c.__name__=='BuiltinImporter']"
    with pytest.raises(ScriptRuntimeError):
        evaluate(payload, {})


def test_blocked_subscript_escape():
    with pytest.raises(ScriptRuntimeError):
        evaluate("().__class__.__bases__[0].__subclasses__()", {})


def test_blocked_import_and_open():
    with pytest.raises(ScriptRuntimeError):
        evaluate("__import__('os')", {})
    with pytest.raises(ScriptRuntimeError):
        evaluate("open('/etc/passwd')", {})


def test_blocked_arbitrary_call_and_lambda():
    with pytest.raises(ScriptRuntimeError):
        evaluate("some_func(1)", {})
    with pytest.raises(ScriptRuntimeError):
        evaluate("(lambda: 1)()", {})


def test_unknown_variable():
    with pytest.raises(ScriptRuntimeError):
        evaluate("nope + 1", {})


def test_short_circuit_boolean():
    v = {"a": False, "b": 0}
    # right side would raise if evaluated; short-circuit must skip it
    assert evaluate("a and b", v) is False
    assert evaluate("a or b", v) == 0
