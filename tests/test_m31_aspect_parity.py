"""M31 — window-aspect parity with original Ren'Py 8.5 (SDK A/B evidence).

Grim shots of the stock the_question at 1280x720 and 960x720
(parity/orig_169, parity/orig_43) show the real Ren'Py 8.5 window model:

* vertical scale is locked to the window HEIGHT (proj_h virtual pixels span
  the full window at any aspect; sprites keep their pixel size);
* horizontal is LEFT-ANCHORED (virtual x=0 at the window left; the 4:3
  window shows virtual columns [0..960], so the `right` sprite is nearly
  off-screen and the 790px choice bars clip at the right edge);

so wpp = (ortho*H/W)/proj_h with x = -half + px*wpp, z = half_v - py*wpp.
Sprites (00definitions.rpy transforms: left/center/right edge anchors) and
the choice menu (stock screens.rpy: choice_vbox xalign .5, ypos 270 on the
720 frame, yanchor .5, spacing gui.choice_spacing, xsize
gui.choice_button_width) must follow the same model.
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


def test_view_metrics_height_locked(stock_cfg):
    half, half_v, wpp, proj_w, proj_h = world_ui.view_metrics(15.0)
    assert (proj_w, proj_h) == (1280.0, 720.0)
    # 16:9: visible height = ortho*9/16, wpp = ortho/proj_w
    assert half_v == pytest.approx(15.0 * 9.0 / 16.0 / 2.0)
    assert wpp == pytest.approx(15.0 / 1280.0)


def test_choice_metrics_match_original_16_9(stock_cfg):
    """orig_169/menu.png: 790px bars centered, block center row 270."""
    store = _layout_at(1280, 720, choices=3)
    wpp = 15.0 / 1280.0
    half_v = 15.0 * 9.0 / 16.0 / 2.0
    b = store["choice_0"]
    assert 2 * b.worldScale[0] == pytest.approx(790 * wpp)
    assert 2 * b.worldScale[1] == pytest.approx((22 + 2 * 5) * wpp)
    assert b.worldPosition[0] == pytest.approx(0.0)  # 640px column = frame center
    # block center at row 270 (single middle of 3? no: 3 buttons, center row 270)
    mid = store["choice_1"].worldPosition[2]
    assert mid == pytest.approx(half_v - 270 * wpp)


def test_choice_metrics_match_original_4_3(stock_cfg):
    """orig_43/menu.png: same SCREEN pixels (row 270), 790px width in a
    960px window -> left-anchored virtual frame pushes the block right and
    the camera crops it."""
    store = _layout_at(960, 720, choices=3)
    half = 7.5
    half_v = 7.5 * 720.0 / 960.0  # visible vertical half-extent (= half/aspect)
    wpp = 2 * half_v / 720.0
    b0 = store["choice_0"]
    b1 = store["choice_1"]
    # 790px bars in a 960-wide window
    assert 2 * b0.worldScale[0] == pytest.approx(790 * wpp)
    # virtual column 640 -> world x = -7.5 + 640*wpp (= +2.5, right of center)
    assert b0.worldPosition[0] == pytest.approx(-half + 640 * wpp)
    # block center still screen row 270: z = half_v - 270*wpp
    assert b1.worldPosition[2] == pytest.approx(half_v - 270 * wpp)
    # ...and that IS the same screen fraction: (half_v - z)/2/half_v = 270/720
    frac = (half_v - b1.worldPosition[2]) / wpp / 720.0
    assert frac == pytest.approx(270.0 / 720.0)


def test_aspect_screen_pixel_consistency(stock_cfg):
    """Every choice transform maps to the same SCREEN pixels at both aspects
    (the parity definition of matching the original)."""
    a = _layout_at(1280, 720, choices=2)
    b = _layout_at(960, 720, choices=2)
    wpp_a = 15.0 / 1280.0
    wpp_b = (2 * (7.5 * 720.0 / 960.0)) / 720.0
    for name in ("choice_0", "choice_1", "choice_0_text", "choice_1_text"):
        wa = 2 * a[name].worldScale[0] / wpp_a   # width back in virtual px
        wb = 2 * b[name].worldScale[0] / wpp_b
        # rel 1e-3: set_font_size rounds world scale to 5 decimals
        # (sub-pixel at any window; the buttons themselves are exact)
        assert wa == pytest.approx(wb, rel=1e-3), name


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
