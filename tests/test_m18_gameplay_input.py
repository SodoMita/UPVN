"""
M18 — in-engine gameplay input (menu number keys) + frontend debug helpers.
Pure-function tests: the bge keyboard polling branch in vn_controller.update()
delegates to _digit_choice_index/_bge_input_state so it stays unit-testable
headless. _bge_input_state prefers the UPBGE 0.50 device.inputs API and falls
back to the deprecated device.events (returns None headless).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT))

from engine.core.vn_controller import _digit_choice_index, _bge_input_state  # noqa: E402


def _digits(*just: int, active=(), count=9) -> dict:
    """Build a digit-state dict: 'just' for indices in just, 'active' for active."""
    out = {}
    for i in range(min(9, count)):
        k = ord("1") + i
        if i in just:
            out[k] = "just"
        elif i in active:
            out[k] = "active"
        else:
            out[k] = None
    return out


def test_digit_choice_no_input():
    assert _digit_choice_index({}, 3) is None
    assert _digit_choice_index(_digits(), 3) is None


def test_digit_choice_just_activated():
    assert _digit_choice_index(_digits(2), 4) == 2          # '3' -> index 2
    assert _digit_choice_index(_digits(0), 1) == 0          # '1' -> index 0


def test_digit_choice_held_keys_ignored():
    assert _digit_choice_index(_digits(active=(0,)), 3) is None


def test_digit_choice_respects_count():
    # only 2 choices exist; '9' must not select out of range
    assert _digit_choice_index(_digits(8), 2) is None
    assert _digit_choice_index(_digits(1), 2) == 1
    assert _digit_choice_index(_digits(2), 3) == 2


def test_input_state_headless_none():
    assert _bge_input_state("keyboard", 32) is None
    assert _bge_input_state("mouse", 1) is None


def test_frontend_import_and_debug_keys_headless():
    """frontend must import and its debug helper must no-op without bge."""
    spec = importlib.util.spec_from_file_location("upvn_frontend_m18",
                                                  ROOT / "bge_frontend" / "frontend.py")
    fe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fe)
    assert fe.HAS_BGE is False
    fe._debug_keys(None, None)          # no crash headless
    assert fe._shot_seq == [0]


def test_frontend_resolve_finds_script_in_parent_dir():
    """Packaged layout: <pkg>/blend/UPVN_Template.blend + <pkg>/game/script.rpy.
    The frontend must look one/two levels above the .blend dir too."""
    import tempfile
    spec = importlib.util.spec_from_file_location(
        "upvn_frontend_m18b", ROOT / "bge_frontend" / "frontend.py")
    fe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fe)

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        blend_dir = root / "blend"
        game_dir = root / "game"
        blend_dir.mkdir()
        game_dir.mkdir()
        (game_dir / "script.rpy").write_text("label start:\n    return\n", encoding="utf-8")

        class FakeLogic:
            @staticmethod
            def expandPath(p):
                if str(p).startswith("//"):
                    return str(blend_dir / str(p).lstrip("//"))
                return p

        # object property points at //game/script.rpy (missing next to blend);
        # the parent-level candidate //../game/script.rpy must be found
        owner = {"script_path": "//game/script.rpy"}
        path, tried = fe.resolve_script_path(FakeLogic(), owner=owner)
        assert path == str(game_dir / "script.rpy"), tried
        assert any("../game" in t or "game" in t for t in tried)


def test_controller_update_menu_wait_unchanged_headless():
    """update() headless still auto-advances say events (menu input is bge-only)."""
    from engine.core.vn_controller import VNController
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
