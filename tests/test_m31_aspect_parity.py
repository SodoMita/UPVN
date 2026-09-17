"""M31 — window-aspect parity with original Ren'Py 8.5 (SDK A/B evidence).

REMOVED: responsive layout — this whole test suite was for responsive layout
that tried to match Ren'Py 8.5 window model (height-locked, left-anchored,
wpp = ortho*H/W/proj_h, x = -half + px*wpp, etc.). Never worked reliably,
distracted other agents, deleted per user request.

What was here before (left as comment):
- test_view_metrics_height_locked: checked view_metrics returned half_v = ortho*9/16/2, wpp=ortho/proj_w
- test_choice_metrics_match_original_16_9: checked 790px bars centered, block center row 270 at 1280x720
- test_choice_metrics_match_original_4_3: checked 790px bars in 960px window left-anchored, cropping
- test_aspect_screen_pixel_consistency: checked choice transforms map to same screen pixels at both aspects
- test_sprite_proj_resolution_reads_dict: checked _proj_resolution reading dict/list and fallback

All deleted. Now only test that fixed layout returns constant values.
"""

import sys
import types
import pytest
from engine.render import gui_config
from engine.ui import world_ui

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

def test_view_metrics_height_locked(stock_cfg):
    # Fixed layout: view_metrics returns fixed half_v = ortho*9/16/2, proj 1280x720
    half, half_v, wpp, proj_w, proj_h = world_ui.view_metrics(15.0)
    assert (proj_w, proj_h) == (1280.0, 720.0)
    assert half_v == pytest.approx(15.0 * 9.0 / 16.0 / 2.0)
    assert wpp == pytest.approx(15.0 / 1280.0)

# REMOVED: test_choice_metrics_match_original_16_9 — was testing responsive 790px bars at 1280x720
# REMOVED: test_choice_metrics_match_original_4_3 — was testing responsive left-anchored 960px window
# REMOVED: test_aspect_screen_pixel_consistency — was testing screen pixel consistency across aspects
# What was here: those tests used _layout_at with fake bge window sizes to check that
# choice button worldScale and worldPosition matched original Ren'Py screenshots.
# Deleted per user request — responsive layout never worked.

def test_choice_metrics_fixed_layout(stock_cfg):
    """Fixed layout: choices centered at x=0, no aspect adaptation, simple stack."""
    # Just check that layout doesn't crash and positions are fixed
    from engine.ui.world_ui import layout_screen_ui
    class _FakeObj:
        def __init__(self):
            self.visible = True
            self.worldPosition = (0.0, 0.0, 0.0)
            self.worldScale = (1.0, 1.0, 1.0)
            self.text = ""
    objs = {
        "Dialogue_Box": _FakeObj(),
        "Speaker_Text": _FakeObj(),
        "Dialogue_Text": _FakeObj(),
    }
    for i in range(9):
        objs[f"choice_{i}"] = _FakeObj()
        objs[f"choice_{i}_text"] = _FakeObj()
    payload = {
        "speaker": "Sylvie",
        "dialogue": "Pick one.",
        "dialogue_visible": True,
        "choices": [
            {"name": f"choice_{i}", "text": f"Option {i}", "visible": i < 2}
            for i in range(9)
        ],
    }
    layout_screen_ui(objs.get, payload, ortho=15.0)
    # Fixed: x_center = 0.0
    assert objs["choice_0"].worldPosition[0] == pytest.approx(0.0)
    assert objs["choice_1"].worldPosition[0] == pytest.approx(0.0)

def test_sprite_proj_resolution_fixed(stock_cfg):
    """Fixed layout: _proj_resolution always returns 1280x720, no gui_config reading."""
    from engine.render import sprite_renderer
    # Even if gui_config says 1920x1080, fixed layout returns 1280x720
    assert sprite_renderer._proj_resolution() == (1280.0, 720.0)
