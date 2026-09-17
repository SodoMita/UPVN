"""M31 — window-aspect parity with original Ren'Py (letterbox semantics).

Ren'Py keeps the project's virtual frame (gui.init resolution) at ANY window
aspect: it scales to fit and paints letterbox/pillarbox bars (doc/config.html,
config.gl_clear_color). Sprites (00definitions.rpy transforms: left/center/
right are edge-anchored to the frame) and the choice menu (stock screens.rpy:
choice_vbox xalign 0.5, ypos 270, yanchor 0.5, spacing gui.choice_spacing)
therefore never reflow when the window aspect changes — UPVN's world layout
must not either.
"""
import sys
import types

import pytest

from engine.render import gui_config
from engine.ui import world_ui

# the_question-equivalent metrics at the stock 1280x720 virtual frame
_CFG = {
    "source": "renpy_gui",
    "resolution": {"width": 1280, "height": 720},
    "sizes": {"text": 22, "name": 30, "interface": 24},
    "choice": {
        "button_width": 790,
        "button_height": None,
        "spacing": 22,
        "borders": (100, 5, 100, 5),
    },
    "world": {},
}


@pytest.fixture
def stock_cfg(monkeypatch):
    monkeypatch.setattr(gui_config, "load_gui_config", lambda *a, **k: _CFG)
    return _CFG


class _FakeObj:
    def __init__(self):
        self.visible = True
        self.worldPosition = (0.0, 0.0, 0.0)
        self.worldScale = (1.0, 1.0, 1.0)
        self.text = ""


def _scene():
    objs = {
        "Dialogue_Box": _FakeObj(),
        "Speaker_Text": _FakeObj(),
        "Dialogue_Text": _FakeObj(),
    }
    for i in range(9):
        objs[f"choice_{i}"] = _FakeObj()
        objs[f"choice_{i}_text"] = _FakeObj()
    return objs


def _payload(choices=2):
    return {
        "speaker": "Sylvie",
        "dialogue": "Pick one.",
        "dialogue_visible": True,
        "choices": [
            {"name": f"choice_{i}", "text": f"Option {i}", "visible": i < choices}
            for i in range(9)
        ],
    }


def _fake_bge(w, h):
    fake = types.ModuleType("bge")
    fake.render = types.SimpleNamespace(
        getWindowWidth=lambda: w, getWindowHeight=lambda: h)
    return fake


def _layout_at(win_w, win_h, choices=2):
    """Run layout_screen_ui with a fake bge window; return UI transforms."""
    old = sys.modules.get("bge")
    sys.modules["bge"] = _fake_bge(win_w, win_h)
    try:
        store = _scene()
        world_ui.layout_screen_ui(store.get, _payload(choices), ortho=15.0)
        return store
    finally:
        if old is None:
            sys.modules.pop("bge", None)
        else:
            sys.modules["bge"] = old


def test_design_frame_is_project_aspect_not_window_aspect(stock_cfg):
    """half_v must come from gui.init(1280, 720) -> 15 * 720/1280 / 2."""
    half, half_v, proj_w, proj_h = world_ui.design_frame(15.0)
    assert (proj_w, proj_h) == (1280.0, 720.0)
    assert half == pytest.approx(7.5)
    assert half_v == pytest.approx(15.0 * 720.0 / 1280.0 / 2.0)


def test_ui_layout_identical_at_16_9_and_4_3(stock_cfg):
    """Ren'Py letterboxes: every UI transform is aspect-invariant.

    (Regression: the old layout used half_v = half / window_aspect, which
    moved choices/history and rescaled BG cover at 4:3 vs the original.)
    """
    a = _layout_at(1280, 720)
    b = _layout_at(800, 600)
    for name in ("Dialogue_Box", "Speaker_Text", "Dialogue_Text",
                 "choice_0", "choice_1", "choice_0_text", "choice_1_text"):
        assert a[name].worldPosition == pytest.approx(b[name].worldPosition), name
        assert a[name].worldScale == pytest.approx(b[name].worldScale), name


def test_choice_block_center_at_stock_ypos(stock_cfg):
    """choice_vbox yanchor center: ypos 270/720 -> z = half_v * 0.25."""
    store = _layout_at(1280, 720, choices=1)
    _, half_v, _, _ = world_ui.design_frame(15.0)
    box = store["choice_0"]
    # single button: its center IS the block center
    assert box.worldPosition[2] == pytest.approx(half_v * 0.25)


def test_choice_button_width_and_height_from_gui_metrics(stock_cfg):
    """xsize gui.choice_button_width=790px, height = text 22px + 2*5px pad."""
    store = _layout_at(1280, 720, choices=1)
    box = store["choice_0"]
    px2wu = 15.0 / 1280.0
    assert 2 * box.worldScale[0] == pytest.approx(790 * px2wu)
    assert 2 * box.worldScale[1] == pytest.approx((22 + 2 * 5) * px2wu)


def test_choice_buttons_centered_and_spaced(stock_cfg):
    store = _layout_at(1280, 720, choices=3)
    z0 = store["choice_0"].worldPosition[2]
    z1 = store["choice_1"].worldPosition[2]
    z2 = store["choice_2"].worldPosition[2]
    h0 = 2 * store["choice_0"].worldScale[1]
    pitch = z0 - z1
    assert pitch == pytest.approx(z1 - z2)
    assert pitch > h0  # spacing gap between buttons, never overlapping
    # vbox xalign 0.5 -> horizontally centered
    for i in range(3):
        assert store[f"choice_{i}"].worldPosition[0] == pytest.approx(0.0)


def test_sprite_proj_resolution_reads_dict(monkeypatch):
    """upvn_gui.json stores resolution as {"width": w, "height": h}.

    (Regression: `res[1]` on that dict raised KeyError, so a 1920x1080
    project silently fell back to 720 and sprites rendered 1.5x oversized.)
    """
    from engine.render import sprite_renderer
    monkeypatch.setattr(gui_config, "load_gui_config",
                        lambda *a, **k: {"resolution": {"width": 1920, "height": 1080}})
    assert sprite_renderer._proj_resolution() == (1920.0, 1080.0)
    # list form tolerated
    monkeypatch.setattr(gui_config, "load_gui_config",
                        lambda *a, **k: {"resolution": [1280, 720]})
    assert sprite_renderer._proj_resolution() == (1280.0, 720.0)
    # missing/garbage -> stock frame
    monkeypatch.setattr(gui_config, "load_gui_config", lambda *a, **k: {})
    assert sprite_renderer._proj_resolution() == (1280.0, 720.0)
