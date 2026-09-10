"""M26d — backlog (history) and rewind must be visible in the GUI, not only in
headless traces: the world-UI payload, the player's font-object writes, the
rewind keys/indicator, and the template objects the whole thing hangs off.
"""
from pathlib import Path

import pytest

from engine.ui import world_ui
from engine.core.vn_controller import VNController
from engine.script.parser import parse_string
from engine.render import contract


ROOT = Path(__file__).resolve().parents[1]


class FakeObj:
    """Minimal KX_GameObject-ish double: the attributes world_ui touches."""

    def __init__(self, name):
        self.name = name
        self.visible = False
        self.worldPosition = None
        self.worldScale = None
        self.body = None
        data = type("d", (), {"size": 0.26, "body": ""})()
        self.blenderObject = type("bo", (), {"data": data, "scale": None})()

    def __setitem__(self, k, v):
        setattr(self, k, v)


class FakeScene:
    def __init__(self, names):
        self.objs = {n: FakeObj(n) for n in names}

    def get(self, name):
        return self.objs.get(name)


def test_build_world_ui_backlog_text_is_newest_last_and_wrapped():
    long_line = "the professor explained the rollback stack twice more until " \
                "everyone in the lecture hall had given up on understanding it"
    entries = [
        {"who_name": "Eileen", "stripped": "Line one."},
        {"who_name": None, "stripped": long_line},
    ]
    p = world_ui.build_world_ui({"type": "say", "text": "now"},
                                history_entries=entries, history_open=True)
    assert p["history_visible"] is True
    lines = p["history"].split("\n")
    assert lines[0].startswith("Eileen: Line one.")
    # the long narration line is wrapped, not kept as one 120-char run
    assert max(len(l) for l in lines) <= world_ui.HISTORY_WRAP + 12
    assert len(lines) >= 3
    assert p["history"].index("Line one.") < p["history"].index("professor")


def test_world_ui_names_come_from_the_contract():
    assert world_ui.HISTORY_BOX == contract.HISTORY_PLANE
    assert world_ui.HISTORY_TEXT == contract.HISTORY_TEXT
    assert world_ui.REWIND_TEXT == contract.REWIND_TEXT


def test_build_world_ui_trims_to_max_lines():
    entries = [{"who_name": None, "stripped": f"line {i}"} for i in range(40)]
    p = world_ui.build_world_ui({"type": "say"}, history_entries=entries,
                                history_open=True)
    body = p["history"]
    assert "line 39" in body
    assert "line 40 - 1" not in body
    assert f"line {40 - world_ui.HISTORY_MAX_LINES - 1}" not in body


def test_history_open_hides_choice_plates_and_empty_backlog_says_so():
    ev = {"type": "menu", "caption": "Which?",
          "choices": [{"text": "left"}, {"text": "right"}]}
    closed = world_ui.build_world_ui(ev, history_entries=[{"stripped": "x"}],
                                     history_open=False)
    assert [c["visible"] for c in closed["choices"]][:2] == [True, True]
    opened = world_ui.build_world_ui(ev, history_entries=[], history_open=True)
    assert all(not c["visible"] for c in opened["choices"])
    assert opened["history"] == "(no backlog yet)"


def test_rewind_marker_payload():
    p = world_ui.build_world_ui({"type": "say", "text": "x"}, rewind_depth=3)
    assert p["rewind_visible"] is True and "3" in p["rewind"]
    p0 = world_ui.build_world_ui({"type": "say", "text": "x"}, rewind_depth=0)
    assert p0["rewind_visible"] is False and p0["rewind"] == ""


def test_apply_world_ui_writes_history_and_hides_when_closed():
    names = [contract.SPEAKER_TEXT, contract.DIALOGUE_TEXT, contract.DIALOGUE_PLANE,
             contract.HISTORY_PLANE, contract.HISTORY_TEXT, contract.REWIND_TEXT]
    scene = FakeScene(names)
    payload = {"speaker": "Eileen", "dialogue": "hi", "dialogue_visible": True,
               "choices": [], "history_visible": True, "history": "A\nB",
               "rewind_visible": True, "rewind": "« rewound 1"}
    world_ui.apply_world_ui(scene.get, payload)
    assert scene.get(contract.HISTORY_TEXT).blenderObject.data.body == "A\nB"
    assert scene.get(contract.HISTORY_PLANE).visible is True
    assert scene.get(contract.REWIND_TEXT).visible is True
    # closed: body cleared, panel hidden (a stale backlog is worse than none)
    world_ui.apply_world_ui(scene.get, {"speaker": "", "dialogue": "",
                                        "dialogue_visible": False, "choices": [],
                                        "history_visible": False, "history": "",
                                        "rewind_visible": False, "rewind": ""})
    assert scene.get(contract.HISTORY_PLANE).visible is False
    assert scene.get(contract.HISTORY_TEXT).blenderObject.data.body == ""


def test_set_font_size_writes_transform_not_a_stray_attribute():
    """The old `obj.size = x` was a silent no-op on a KX object."""
    world_ui._font_scale_cache.clear()
    ob = FakeObj("Dialogue_Text")
    world_ui.set_font_size(ob, 0.36)
    assert ob.worldScale == (0.36, 0.36, 0.36)
    assert not hasattr(ob, "size") or ob.worldScale is not None
    # curve em size normalised so the scale is the single authority
    assert ob.blenderObject.data.size == 1.0
    # cached: a second identical call must not touch the object again
    ob.worldScale = None
    world_ui.set_font_size(ob, 0.36)
    assert ob.worldScale is None
    world_ui.set_font_size(ob, 0.5)
    assert ob.worldScale == (0.5, 0.5, 0.5)


def test_layout_positions_history_panel_and_scales_text():
    world_ui._font_scale_cache.clear()
    names = [contract.SPEAKER_TEXT, contract.DIALOGUE_TEXT, contract.DIALOGUE_PLANE,
             contract.HISTORY_PLANE, contract.HISTORY_TEXT, contract.REWIND_TEXT]
    scene = FakeScene(names)
    world_ui.layout_screen_ui(scene.get, {"choices": [], "history_visible": True},
                              ortho=15.0)
    assert scene.get(contract.HISTORY_PLANE).worldPosition is not None
    assert scene.get(contract.HISTORY_TEXT).worldPosition[2] > 0, \
        "backlog text anchors above centre so it grows downward"
    assert scene.get(contract.HISTORY_TEXT).worldScale[0] == pytest.approx(0.27)
    assert scene.get(contract.REWIND_TEXT).worldPosition[2] > \
        scene.get(contract.HISTORY_TEXT).worldPosition[2]


# ---------------------------------------------------------------- controller side
@pytest.fixture()
def ctrl():
    c = VNController(script_dict=parse_string('''
label start:
    "one"
    "two"
    "three"
    return
'''))
    c.load()
    return c


def test_history_open_blocks_advance_and_skip(ctrl):
    ctrl.screen_mgr.handle_key("h")
    assert ctrl._history_open() is True
    idx0 = ctrl.state.instruction_index
    # a click while reading the backlog closes it instead of scrolling past
    ctrl._is_advance_pressed = lambda: True
    ctrl.update(dt=0.016)
    assert ctrl.state.instruction_index == idx0
    assert ctrl._history_open() is False


def test_skip_is_paused_while_backlog_is_open(ctrl):
    ctrl.state.skip = True
    ctrl.screen_mgr.handle_key("h")
    # make the line "already seen" so skip would normally fire immediately
    ctrl.state.seen_history = ["start:1:two"]
    idx0 = ctrl.state.instruction_index
    for _ in range(10):
        ctrl.update(dt=0.2)
    assert ctrl.state.instruction_index == idx0, "skip must not run under the backlog"


def test_rewind_keys_are_wired_to_the_right_devices():
    src = (ROOT / "engine" / "core" / "vn_controller.py").read_text(encoding="utf-8")
    assert "_REWIND_KEYS" in src and "PAGEUPKEY" in src and "BACKSPACEKEY" in src
    assert "_REPLAY_KEYS" in src and "PAGEDOWNKEY" in src
    assert "WHEELUPMOUSE" in src and "WHEELDOWNMOUSE" in src
    # modals own the screen: rewind is gated on them
    assert "_rewind_blocked" in src


def test_template_ships_the_backlog_objects():
    """The committed .blend must carry what the contract requires, or pressing P
    in a fresh checkout silently has no history panel."""
    blend = ROOT / "blend" / "UPVN_Template.blend"
    import subprocess
    names = [contract.HISTORY_PLANE, contract.HISTORY_TEXT, contract.REWIND_TEXT]
    expr = ("import bpy;"
            "print('HAVE', [n for n in %r if bpy.data.objects.get(n)])" % names)
    blender = "/opt/upbge/upbge-0.50-linux-x64/blender"
    from shutil import which
    if not Path(blender).exists() and not which(blender):
        pytest.skip("UPBGE not installed in this sandbox")
    out = subprocess.run([blender, "--background", str(blend), "--python-expr", expr],
                         capture_output=True, text=True, timeout=180)
    line = [l for l in (out.stdout + out.stderr).splitlines() if l.startswith("HAVE")]
    assert line, out.stdout + out.stderr
    assert all(n in line[0] for n in names), line[0]
