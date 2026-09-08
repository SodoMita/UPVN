"""
M18 — in-engine gameplay input (menu number keys) + frontend debug helpers.
Pure-function tests: the bge keyboard polling branch in vn_controller.update()
delegates to _menu_choice_from_keycodes so it stays unit-testable headless.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))

from engine.core.vn_controller import _menu_choice_from_keycodes  # noqa: E402

JUST = 1   # bge.logic.KX_INPUT_JUST_ACTIVATED
ACTIVE = 2  # bge.logic.KX_INPUT_ACTIVE


def test_menu_choice_no_keys():
    assert _menu_choice_from_keycodes({}) is None
    assert _menu_choice_from_keycodes(None) is None
    assert _menu_choice_from_keycodes({ord("a"): JUST}) is None


def test_menu_choice_digit_just_activated():
    # '3' pressed this frame -> index 2
    keys = {ord("1"): ACTIVE, ord("2"): ACTIVE, ord("3"): JUST, ord("4"): ACTIVE}
    assert _menu_choice_from_keycodes(keys) == 2


def test_menu_choice_respects_max_index():
    # only 2 choices exist; pressing '9' must not select out of range
    keys = {ord("9"): JUST}
    assert _menu_choice_from_keycodes(keys, max_index=2) is None
    keys2 = {ord("2"): JUST}
    assert _menu_choice_from_keycodes(keys2, max_index=2) == 1
    keys3 = {ord("3"): JUST}
    assert _menu_choice_from_keycodes(keys3, max_index=3) == 2


def test_menu_choice_ignores_held_keys():
    # key held since earlier frames (ACTIVE, not JUST_ACTIVATED) selects nothing
    keys = {ord("1"): ACTIVE}
    assert _menu_choice_from_keycodes(keys) is None


def test_frontend_import_and_debug_keys_headless():
    """frontend must import and its debug helper must no-op without bge."""
    spec = importlib.util.spec_from_file_location("upvn_frontend_m18",
                                                  ROOT / "bge_frontend" / "frontend.py")
    fe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fe)
    assert fe.HAS_BGE is False
    fe._debug_keys(None, None)          # no crash headless
    assert fe._shot_seq == [0]


def test_controller_update_menu_wait_unchanged_headless():
    """update() headless still auto-advances say events (menu input is bge-only)."""
    from engine.core.vn_controller import VNController
    from engine.core.vn_interpreter import VNInterpreter  # noqa: F401 (side imports ok)
    from engine.script.parser import parse_string
    script = parse_string(
        'label start:\n'
        '    "one"\n'
        '    menu:\n'
        '        "Pick"\n'
        '        "A":\n'
        '            jump end\n'
        '        "B":\n'
        '            jump end\n'
        'label end:\n'
        '    "bye"\n'
        '    return\n'
    )
    c = VNController(script_dict=script)
    c.load()
    assert c.current_event.get("type") == "say"
    c.update(dt=0.5)                    # headless: no input polling, waits
    assert c.current_event.get("type") == "say"
