"""M25 Usability Stabilization Freeze — regression tests.

These pin the field bugs found by the first real UPBGE play sessions
(see BUGS.md). They are pure-Python on purpose: CI has no GL display, and
these exact bugs shipped because nothing headless could see them.
"""

import sys
import types

import pytest

from engine.ui import world_ui


class FakeObj:
    """Minimal stand-in for a KX game object (position/scale/visibility)."""

    def __init__(self, name):
        self.name = name
        self.worldPosition = (0.0, 0.0, 0.0)
        self.worldScale = (1.0, 1.0, 1.0)
        self.visible = True
        self.size = 0.3


class FakeFontData:
    def __init__(self):
        self.body = ""


class FakeBlenderObject:
    def __init__(self):
        self.data = FakeFontData()


class FakeFontObj(FakeObj):
    """KX_FontObject look-alike: no .text/.body, only .blenderObject.data."""

    def __init__(self, name):
        super().__init__(name)
        self.blenderObject = FakeBlenderObject()


def _store():
    names = ["Dialogue_Box", "Speaker_Text", "Dialogue_Text"]
    names += [f"choice_{i}" for i in range(9)]
    names += [f"choice_{i}_text" for i in range(9)]
    store = {}
    for n in names:
        store[n] = FakeFontObj(n) if ("Text" in n or "text" in n) else FakeObj(n)
    return store


def _payload(dialogue=True, choices=0):
    return {
        "speaker": "Eileen" if dialogue else "",
        "dialogue": "Line one." if dialogue else "",
        "dialogue_visible": dialogue,
        "choices": [
            {"name": f"choice_{i}", "text": f"c{i}", "visible": i < choices}
            for i in range(9)
        ],
    }


def test_dialogue_box_stays_inside_ortho_frame():
    """BUG-003: vertical layout used the horizontal half-extent (ortho_scale
    spans width). On a 16:9 window the box landed at z=-5.4 with a vertical
    half-extent of 4.22 — below the frame, i.e. a 'black screen'."""
    store = _store()
    world_ui.apply_world_ui(store.get, _payload(), ortho=15.0)
    half_v = (15.0 / 2.0) / (16.0 / 9.0)  # 4.21875 at the 16:9 fallback
    box = store["Dialogue_Box"]
    assert abs(box.worldPosition[2]) < half_v, box.worldPosition
    dt = store["Dialogue_Text"]
    sp = store["Speaker_Text"]
    # text must sit inside the box band, not below the frame
    for ob in (dt, sp):
        assert abs(ob.worldPosition[2]) < half_v, ob.worldPosition
        assert ob.worldPosition[2] > box.worldPosition[2] - 1.2


def test_layout_respects_window_aspect_when_bge_present():
    """With a 4:3 window the vertical half-extent is 7.5*(3/4)=5.625."""
    fake = types.ModuleType("bge")
    render = types.SimpleNamespace(getWindowWidth=lambda: 800, getWindowHeight=lambda: 600)
    fake.render = render
    old = sys.modules.get("bge")
    sys.modules["bge"] = fake
    try:
        assert world_ui.aspect_wh() == pytest.approx(4.0 / 3.0)
        store = _store()
        world_ui.layout_screen_ui(store.get, _payload(), ortho=15.0)
        half_v = 7.5 / (4.0 / 3.0)
        assert store["Dialogue_Box"].worldPosition[2] == pytest.approx(-half_v * 0.72)
    finally:
        if old is None:
            sys.modules.pop("bge", None)
        else:
            sys.modules["bge"] = old


def test_choices_stack_inside_frame():
    store = _store()
    world_ui.apply_world_ui(store.get, _payload(choices=4), ortho=15.0)
    half_v = (15.0 / 2.0) / (16.0 / 9.0)
    for i in range(4):
        z = store[f"choice_{i}"].worldPosition[2]
        assert -half_v < z < half_v
        assert store[f"choice_{i}"].visible is True
    assert store["choice_4"].visible is False


def test_set_font_text_writes_through_blender_object():
    """BUG-004: KX_FontObject exposes no .text/.body/.data in the UPBGE 0.50
    player; without the blenderObject path every glyph write was a no-op."""
    ob = FakeFontObj("Dialogue_Text")
    world_ui.set_font_text(ob, "Line one.")
    assert ob.blenderObject.data.body == "Line one."


def test_set_font_text_keeps_legacy_fallbacks():
    class TextOnly:
        pass

    ob = TextOnly()
    ob.text = ""
    world_ui.set_font_text(ob, "hi")
    assert ob.text == "hi"

    assert world_ui.set_font_text(None, "x") is None


def test_advance_without_choice_is_noop_on_menu(tmp_path):
    """BUG-007b: a stray advance (skip tick, Enter, modal edge) must not send
    None into a waiting menu — that raised ScriptRuntimeError inside the
    interpreter and killed the story generator."""
    from engine.core.vn_controller import VNController

    script = (
        "label start:\n"
        '    "hi"\n'
        "    menu:\n"
        '        "a":\n'
        "            jump ea\n"
        '        "b":\n'
        "            jump eb\n"
        "label ea:\n"
        '    "A"\n'
        "    return\n"
        "label eb:\n"
        '    "B"\n'
        "    return\n"
    )
    ctrl = VNController(script_dict=__import__(
        "engine.script.parser", fromlist=["parse_string"]).parse_string(script))
    ctrl.load()
    # headless: drive to the menu
    ev = ctrl.current_event
    while ev is not None and ev.get("type") != "menu":
        ctrl._advance()
        ev = ctrl.current_event
    assert ev is not None and ev["type"] == "menu"
    gen = ctrl._gen
    ctrl._advance(send_value=None)          # must be ignored
    assert ctrl._gen is gen                  # generator alive
    assert ctrl.current_event.get("type") == "menu"
    ctrl.choose(0)                           # explicit choice still works
    assert ctrl.current_event.get("text") == "A"


def test_skip_does_not_auto_resolve_menu_headless():
    """BUG-007: with skip on, update() must pause at menus instead of picking
    a choice for the player."""
    from engine.core.vn_controller import VNController

    script = (
        "label start:\n"
        '    "seen line"\n'
        "    menu:\n"
        '        "a":\n'
        "            jump ea\n"
        '        "b":\n'
        "            jump eb\n"
        "label ea:\n"
        '    "A"\n'
        "    return\n"
        "label eb:\n"
        '    "B"\n'
        "    return\n"
    )
    ctrl = VNController(script_dict=__import__(
        "engine.script.parser", fromlist=["parse_string"]).parse_string(script))
    ctrl.load()
    ctrl._advance()                     # say "seen line"
    ctrl._advance()                     # menu
    assert ctrl.current_event.get("type") == "menu"
    ctrl.toggle_skip()
    for _ in range(50):
        ctrl.update(dt=0.05)
    assert ctrl.current_event.get("type") == "menu"
    assert ctrl.state.current_label == "start"


def test_normalize_hit_name_still_strips_text_suffix():
    assert world_ui.normalize_hit_name("choice_3_text") == "choice_3"
    assert world_ui.normalize_hit_name("choice_3") == "choice_3"
    assert world_ui.normalize_hit_name(None) is None


# --- M25 BUG-010: digit selection must use digit-ordered states, never ASCII ---

def test_digit_choice_index_uses_digit_order_not_ascii():
    from engine.core.vn_controller import _digit_choice_index
    # states[i] is the state of digit key i+1 (bge codes are NOT ASCII: ONEKEY==14)
    assert _digit_choice_index([None, "just", None], 3) == 1
    assert _digit_choice_index(["just", "just"], 2) == 0   # lowest digit wins
    assert _digit_choice_index([None, "just"], 2) == 1     # within count
    assert _digit_choice_index([None, "just"], 1) is None  # beyond choice count
    assert _digit_choice_index(["active", "active"], 2) is None  # held != pressed
    assert _digit_choice_index([], 3) is None


def test_digit_choice_index_regression_ascii_keys_never_match():
    """Guard: a dict keyed by ASCII ordinals (the BUG-010 producer bug) must not
    silently look 'correct' — the helper only accepts ordered sequences."""
    from engine.core.vn_controller import _digit_choice_index
    ascii_keyed = {ord("1"): "just"}          # old broken producer shape
    assert _digit_choice_index(ascii_keyed, 2) is None   # fail closed on dicts


def test_quick_save_load_roundtrip_no_modal(tmp_path):
    """M25 BUG-011: Ctrl+S/Ctrl+L must save/load directly (files on disk),
    never open a modal screen (invisible + story-blocking in the player)."""
    from engine.core.vn_controller import VNController
    from engine.save.save_manager import SaveManager
    from engine.script.parser import parse_string
    ctrl = VNController(script_dict=parse_string(
        'label start:\n    "a"\n    "b"\n    "c"\n    return\n'))
    ctrl.load()
    assert ctrl.current_event.get("text") == "a"
    ctrl._advance()
    assert ctrl.current_event.get("text") == "b"
    ctrl.screen_mgr.save_manager = SaveManager(ctrl.state, save_dir=tmp_path)
    assert ctrl.quick_save() is True
    assert (tmp_path / "save_quick.json").is_file()
    ctrl._advance()
    assert ctrl.current_event.get("text") == "c"
    assert ctrl.quick_load() is True
    assert ctrl.current_event.get("text") == "b"
    # no modal was opened by either action
    assert ctrl.screen_mgr.active_modal is None
    assert ctrl.quick_load("missing_slot") is False   # graceful, no raise
