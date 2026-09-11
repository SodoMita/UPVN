"""M26d — backlog (history) and rewind must be visible in the GUI, not only in
headless traces: the world-UI payload, the player's font-object writes, the
rewind keys/indicator, and the template objects the whole thing hangs off.
"""
from pathlib import Path
import sys

import pytest

from engine.ui import world_ui
from engine.core import vn_controller as vn_controller_mod
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
    # closed: hidden, but the body is left alone — a KX FONT only rebuilds its
    # glyph mesh while visible, so blanking it on close is what made the panel
    # reopen empty (see apply_world_ui's ordering note).
    world_ui.apply_world_ui(scene.get, {"speaker": "", "dialogue": "",
                                        "dialogue_visible": False, "choices": [],
                                        "history_visible": False, "history": "",
                                        "rewind_visible": False, "rewind": ""})
    assert scene.get(contract.HISTORY_PLANE).visible is False
    assert scene.get(contract.HISTORY_TEXT).visible is False
    assert scene.get(contract.REWIND_TEXT).visible is False
    assert scene.get(contract.HISTORY_TEXT).blenderObject.data.body == "A\nB"


def test_history_is_unhidden_before_the_text_is_written():
    """The player proved this ordering is load-bearing: body-then-visible left
    an empty glyph mesh behind a correctly drawn panel."""
    order = []

    def spy(name):
        ob = FakeObj(name)
        ob.visible = False

        def _setv(v):
            order.append(("visible", name, v))
        object.__setattr__(ob, "visible", False)

        class _P:
            def __set__(_s, _o, _v):
                order.append(("visible", name, _v))

            def __get__(_s, _o, _t=None):
                return False
        type(ob).visible = _P()
        body = ob.blenderObject.data

        class _D(type(body)):
            def __setattr__(_s, _a, _v):
                order.append(("body", name, _v))
                super().__setattr__(_a, _v)
        ob.blenderObject.data = _D()
        return ob

    store = {}

    def get_obj(name):
        if name not in store:
            store[name] = spy(name)
        return store[name]

    world_ui.apply_world_ui(get_obj, {"speaker": "", "dialogue": "",
                                      "dialogue_visible": False, "choices": [],
                                      "history_visible": True, "history": "A",
                                      "rewind_visible": False, "rewind": ""})
    # scoped to the backlog objects: the dialogue text is written earlier by
    # design, that is not the ordering this test guards
    def first(kind, name):
        hits = [i for i, e in enumerate(order)
                if e[0] == kind and (name is None or e[1] == name)
                and (kind != "visible" or e[2] is True)]
        return min(hits) if hits else None

    v, t = first("visible", "History_Text"), first("body", "History_Text")
    assert v is not None and t is not None, order
    assert v < t, f"History_Text must be unhidden before its body is written: {order}"


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
    body = world_ui.format_history(_entries(world_ui.HISTORY_MAX_LINES + 4))
    n_rows = len(body.split("\n"))
    assert n_rows == world_ui.HISTORY_MAX_LINES
    world_ui.layout_screen_ui(scene.get, {"choices": [], "history_visible": True,
                                          "history": body}, ortho=15.0)
    half = 15.0 / 2.0
    half_v = half / world_ui.aspect_wh()
    box = scene.get(contract.HISTORY_PLANE)
    htext = scene.get(contract.HISTORY_TEXT)
    rtext = scene.get(contract.REWIND_TEXT)
    assert box.worldPosition is not None
    assert htext.worldPosition[2] > 0, \
        "backlog text anchors above centre so it grows downward"
    # the backlog em is derived from the space available, not a magic number
    by_height = (half_v * (world_ui.BACKLOG_TOP - world_ui.BACKLOG_BOTTOM)) / (
        world_ui.HISTORY_MAX_LINES * world_ui.HISTORY_PITCH_EM)
    by_width = (15.0 / 2 * 1.72) / (world_ui.HISTORY_WRAP * world_ui.HISTORY_ADVANCE_EM)
    hist_em = min(by_height, by_width) * world_ui.HISTORY_FIT_SLACK
    assert htext.worldScale[0] == pytest.approx(hist_em, abs=1e-4), \
        "set_font_size rounds to 5 dp before caching"
    # the block grows UP from its origin (align_y is ignored at runtime), so a
    # full page must land with its first row just under the panel's top edge
    # and its bottom above the dialogue box — the old top-anchor clipped row 1
    # against the window edge.
    top = htext.worldPosition[2] + n_rows * hist_em * world_ui.HISTORY_PITCH_EM
    assert top <= half_v * world_ui.BACKLOG_TOP + 1e-6, "first row inside the band"
    assert htext.worldPosition[2] >= half_v * world_ui.BACKLOG_BOTTOM - 1e-6, \
        "last row stays clear of the dialogue box"
    # ...and a wrapped row still fits between the panel's edges
    assert world_ui.HISTORY_WRAP * hist_em * world_ui.HISTORY_ADVANCE_EM < 15.0 * 0.94
    # the depth rule IS the bug fix: the panel must clear the story planes and
    # the text must clear the panel, or the glyphs are silently not drawn
    assert box.worldPosition[1] - htext.worldPosition[1] == pytest.approx(world_ui.TEXT_FRONT)
    assert htext.worldPosition[1] - rtext.worldPosition[1] == pytest.approx(0.0)
    # marker and backlog share the same TOP row (they are never shown at once):
    # each origin is its block's bottom, so top = origin + rows * pitch * em
    row_h = hist_em * world_ui.HISTORY_PITCH_EM
    assert rtext.worldPosition[2] + row_h == pytest.approx(
        htext.worldPosition[2] + n_rows * row_h, abs=1e-4)
    assert htext.worldPosition[2] + n_rows * row_h == pytest.approx(
        half_v * world_ui.BACKLOG_TOP, abs=1e-4)
    # the panel is taller than the text block so the list reads as inside it
    assert box.worldScale[1] > htext.worldPosition[2]


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
    expr = (
        "import bpy;"
        "print('HAVE', [n for n in %r if bpy.data.objects.get(n)]);"
        "o=bpy.data.objects.get('History_Box');"
        "vs=list(o.data.vertices) if o else [];"
        "print('QUAD', len(vs)==4 and all(abs(abs(v.co.x)-1.0)<1e-4 for v in vs),"
        " round(max((abs(v.co.x) for v in vs), default=0),3),"
        " len(o.data.uv_layers) if o else 0,"
        " [round(c,2) for c in o.color] if o else None)" % names)
    blender = "/opt/upbge/upbge-0.50-linux-x64/blender"
    from shutil import which
    if not Path(blender).exists() and not which(blender):
        pytest.skip("UPBGE not installed in this sandbox")
    out = subprocess.run([blender, "--background", str(blend), "--python-expr", expr],
                         capture_output=True, text=True, timeout=180)
    lines = (out.stdout + out.stderr).splitlines()
    have = [l for l in lines if l.startswith("HAVE")]
    quad = [l for l in lines if l.startswith("QUAD")]
    assert have, out.stdout + out.stderr
    assert all(n in have[0] for n in names), have[0]
    # layout_screen_ui treats worldScale as the half extent, so the panel mesh
    # must be the +/-1 quad every other VN plane uses — a +/-0.5 mesh renders at
    # half size and the backlog text lands outside its own box (measured).
    assert quad and quad[0].startswith("QUAD True"), quad
    fields = quad[0].split()
    assert fields[1] == "True" and fields[2] == "1.0", quad[0]   # +/-1 quad
    assert int(fields[3]) >= 1, "UV layer required for TexImage sampling"
    assert "[0.03, 0.04, 0.09, 1.0]" in quad[0], \
        "History_Box must be tinted dark or it paints white-on-white"


# ------------------------------------------------------- input plumbing (fake bge)
import types as _types


class _FakeDevice:
    def __init__(self, just=(), active=()):
        self.inputs = {}
        for k in just:
            self.inputs[k] = 1      # KX_INPUT_JUST_ACTIVATED
        for k in active:
            self.inputs[k] = 2      # KX_INPUT_ACTIVE


def _install_fake_bge(monkeypatch, just_keys=(), active_keys=(), mouse_just=()):
    fake = _types.ModuleType("bge")
    logic = _types.SimpleNamespace(
        KX_INPUT_JUST_ACTIVATED=1, KX_INPUT_ACTIVE=2, KX_INPUT_RELEASED=0,
        keyboard=_FakeDevice(tuple(just_keys) + tuple(active_keys), active_keys),
        mouse=_FakeDevice(mouse_just),
        getCurrentController=lambda: None, getCurrentScene=lambda: None,
        expandPath=lambda p: p,
    )
    events = _types.SimpleNamespace(
        HKEY=19, QKEY=20, SKEY=22, AKEY=10, LKEY=16, LEFTCTRLKEY=29,
        SPACEKEY=8, ENTERKEY=1, ESCKEY=16, LEFTMOUSE=105,
        ONEKEY=14, TWOKEY=15, THREEKEY=16, FOURKEY=17, FIVEKEY=18,
        SIXKEY=19, SEVENKEY=20, EIGHTKEY=21, NINEKEY=22,
        WHEELUPMOUSE=107, WHEELDOWNMOUSE=108,
        PAGEUPKEY=201, PAGEDOWNKEY=209, BACKSPACEKEY=14,
        UPARROWKEY=200, DOWNARROWKEY=203,
    )
    fake.logic = logic
    fake.events = events
    monkeypatch.setitem(sys.modules, "bge", fake)
    monkeypatch.setattr(vn_controller_mod, "HAS_BGE", True)
    return logic


def test_history_key_is_not_swallowed_by_the_typewriter(monkeypatch, ctrl):
    """M26d: H used to be polled *after* the typewriter early-return, so a press
    during a reveal was lost — at player framerates that read as 'history does
    nothing'. Keys are now polled first, on every tick."""
    _install_fake_bge(monkeypatch, just_keys=[19])  # 19 == events.HKEY
    ctrl.load() if ctrl.interp is None else None
    assert ctrl.current_event["type"] == "say"
    # force a mid-reveal typewriter (not done yet -> the old code returned here)
    ctrl.ui_mgr._typewriter_progress = 0.0
    ctrl.update(dt=0.016)
    assert ctrl._history_open() is True, "H must open the backlog even mid-reveal"


def test_rewind_key_rolls_back_exactly_one_line(monkeypatch, ctrl):
    """One press = one line: the keys must be polled once per tick, not twice."""
    ctrl._advance()
    ctrl._advance()
    before = ctrl.state.instruction_index
    assert before == 2                      # "three"
    _install_fake_bge(monkeypatch, just_keys=[201])   # PAGEUPKEY
    ctrl.update(dt=0.016)
    assert ctrl.state.instruction_index == before - 1, \
        "PageUp must move exactly one interaction back"
    assert ctrl.current_event["text"] == "two"
    assert ctrl.rewind_depth() == 1
    # a second press rewinds one more, never two
    ctrl.update(dt=0.016)
    assert ctrl.state.instruction_index == before - 2
    assert ctrl.current_event["text"] == "one"
    assert ctrl.rewind_depth() == 2


def test_global_keys_polled_once_before_the_typewriter_branch():
    src = (ROOT / "engine" / "core" / "vn_controller.py").read_text(encoding="utf-8")
    body = src.split("def update(self, dt")[1].split("def _is_advance_pressed")[0]
    calls = [l for l in body.splitlines()
             if "_handle_global_keys()" in l and not l.strip().startswith("#")]
    assert len(calls) == 1, f"double poll = double rewind: {calls}"
    assert body.index("_handle_global_keys()") < body.index("update_typewriter(dt)")
    # and the old inline polling is gone (no second home for the same edges)
    assert body.count('ev.HKEY') == 0


def test_opening_the_backlog_cannot_be_closed_by_the_same_input(ctrl, monkeypatch):
    """H and an advance key can land in one tick; the overlay must stay open."""
    logic = _install_fake_bge(monkeypatch, just_keys=[8])   # SPACE held "just"
    ctrl.ui_mgr._typewriter_progress = 999                   # reveal finished
    assert ctrl.toggle_history() is True
    ctrl.update(dt=0.016)                                    # same-tick advance
    assert ctrl._history_open() is True, "open guard: no flicker shut"
    # after the guard window the same press does close it
    ctrl._history_opened_at -= 1.0
    logic.keyboard.inputs[8] = 1                             # still just-pressed
    ctrl.update(dt=0.016)
    assert ctrl._history_open() is False


# ---------------------------------------------------------------- backlog paging
def _entries(n):
    return [{"who_name": "Eileen", "text": f"line {i}"} for i in range(1, n + 1)]


def test_format_history_pages_by_rows_and_shows_position():
    body = world_ui.format_history(_entries(20))
    lines = body.split("\n")
    budget = world_ui.HISTORY_MAX_LINES - 1          # footer steals one row
    assert len(lines) == world_ui.HISTORY_MAX_LINES, "never more rows than fit"
    assert lines[-1].startswith("\u2014 rows") and f"of 20" in lines[-1]
    assert lines[0] == f"Eileen: line {20 - budget + 1}" and lines[-2] == "Eileen: line 20"
    assert "page 1/" in lines[-1]
    pages = int(lines[-1].split("page ")[1].split("/")[1].split()[0])
    assert pages == -(-20 // budget)
    oldest = world_ui.format_history(_entries(20), scroll=pages - 1)
    assert oldest.split("\n")[0] == "Eileen: line 1"
    # clamped: past the oldest page the newest page stays put
    assert world_ui.format_history(_entries(20), scroll=99).split("\n")[0] \
        == "Eileen: line 1"
    # a short script needs no pager at all
    short = world_ui.format_history(_entries(3))
    assert "page" not in short and len(short.split("\n")) == 3
    cap = world_ui.HISTORY_MAX_LINES
    assert world_ui.history_max_scroll(_entries(cap)) == 0, "what fits has no pager"
    assert world_ui.history_max_scroll(_entries(cap + 1)) >= 1


def test_wrapping_counts_towards_the_row_budget():
    """The bug this guards: 11 *entries* became 20+ drawn rows and ran off the
    panel, because paging counted entries."""
    long_entries = [{"who_name": "", "text": "word " * 30} for _ in range(8)]
    rows = world_ui.history_lines(long_entries)
    assert len(rows) > 20, "each entry wraps to several rows"
    body = world_ui.format_history(long_entries)
    assert len(body.split("\n")) <= world_ui.HISTORY_MAX_LINES
    budget, pages = world_ui.history_pages(long_entries)
    assert pages == -(-len(rows) // budget)


@pytest.fixture()
def long_ctrl():
    """A 40-line script: several backlog pages long."""
    c = VNController(script_dict=parse_string("\n".join(
        ["label start:"] + [f'    "line {i}"' for i in range(1, 41)] + ["    return"])))
    c.load()
    for _ in range(40):
        c._advance()
    return c


def test_backlog_wheel_pages_instead_of_rewinding(monkeypatch, long_ctrl):
    """While the overlay is open the wheel scrolls the backlog; the very same
    gesture rewinds the story once it is closed."""
    ctrl = long_ctrl
    lim = ctrl._history_max_scroll()
    assert lim >= 2, "fixture must span several pages"
    logic = _install_fake_bge(monkeypatch, mouse_just=[107])   # WHEELUPMOUSE
    assert ctrl.toggle_history() is True
    assert ctrl._history_scroll == 0
    ctrl.update(dt=0.016)
    assert ctrl._history_scroll == 1, "wheel up pages to older rows"
    ctrl.update(dt=0.016)
    assert ctrl._history_scroll == 2
    for _ in range(lim + 4):
        logic.mouse = _FakeDevice([107])
        ctrl.update(dt=0.016)
    assert ctrl._history_scroll == lim, "paged clamps at the oldest page"
    logic.mouse = _FakeDevice([108])                            # WHEELDOWNMOUSE
    ctrl.update(dt=0.016)
    assert ctrl._history_scroll == lim - 1
    # the wheel never rewound the story while the backlog was up
    assert ctrl.rewind_depth() == 0, "paging must not steal the rewind gesture"
    ctrl._close_history()
    assert ctrl._history_scroll == 0, "closing resets the page"


def test_scroll_offset_reaches_the_payload(long_ctrl):
    ctrl = long_ctrl
    rows = len(world_ui.history_lines(ctrl.state.history))
    budget, pages = world_ui.history_pages(ctrl.state.history)
    assert pages >= 2
    payload = world_ui.build_world_ui(ctrl.current_event, None,
                                      history_entries=ctrl.state.history,
                                      history_open=True, history_scroll=1)
    assert f"page 2/{pages}" in payload["history"]
    assert f"of {rows}" in payload["history"]
    assert world_ui.build_world_ui(ctrl.current_event, None, history_entries=[],
                                   history_open=False)["history"] == ""


class _CurveObj:
    """Minimal stand-in for a KX font object (blenderObject.data.body)."""

    def __init__(self):
        self.writes = 0
        self._body = ""

        class _D:
            def __init__(inner, outer):
                inner._o = outer

            @property
            def body(inner):
                return inner._o._body

            @body.setter
            def body(inner, v):
                inner._o.writes += 1
                inner._o._body = v

        self.data = _D(self)
        self.blenderObject = type("BO", (), {"data": self.data})()


def test_set_font_text_is_idempotent():
    """M26d: the layout runs every tick; re-writing an unchanged body rebuilds
    the glyph mesh each time and the player drew two pages on top of each other
    in the frame where a mesh rebuild was still in flight."""
    ob = _CurveObj()
    world_ui.set_font_text(ob, "page one")
    assert ob.writes == 1
    world_ui.set_font_text(ob, "page one")
    world_ui.set_font_text(ob, "page one")
    assert ob.writes == 1, "unchanged text must not touch the curve"
    world_ui.set_font_text(ob, "page two")
    assert ob.writes == 2 and ob._body == "page two"
