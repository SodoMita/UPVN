"""M26c — scale-on-hover for choice plates.

Hover is applied inside layout_screen_ui (the single writer of choice-plane
scale), so it cannot go stale on camera zoom and is testable headlessly with
dict-like fake objects.
"""
from engine.ui.world_ui import HOVER_SCALE, apply_world_ui


class FakeObj:
    def __init__(self):
        self.visible = True
        self.worldPosition = None
        self.worldScale = None
        self.text = ""
        self.size = None


def _scene():
    objs = {
        "Dialogue_Box": FakeObj(),
        "Speaker_Text": FakeObj(),
        "Dialogue_Text": FakeObj(),
    }
    for i in range(2):
        objs[f"choice_{i}"] = FakeObj()
        objs[f"choice_{i}_text"] = FakeObj()
    return objs, objs.get


def _payload():
    return {
        "speaker": "Eileen",
        "dialogue": "Pick one.",
        "dialogue_visible": True,
        "choices": [
            {"name": "choice_0", "text": "1. Left", "visible": True},
            {"name": "choice_1", "text": "2. Right", "visible": True},
        ],
    }


def test_hovered_plate_scales_up():
    objs, get = _scene()
    apply_world_ui(get, _payload(), ortho=15.0, hovered="choice_1")
    w0, h0 = objs["choice_0"].worldScale[:2]
    w1, h1 = objs["choice_1"].worldScale[:2]
    assert abs(w1 - w0 * HOVER_SCALE) < 1e-6
    assert abs(h1 - h0 * HOVER_SCALE) < 1e-6


def test_no_hover_equal_sizes():
    objs, get = _scene()
    apply_world_ui(get, _payload(), ortho=15.0, hovered=None)
    w0 = objs["choice_0"].worldScale[0]
    w1 = objs["choice_1"].worldScale[0]
    assert abs(w1 - w0) < 1e-6


def test_hover_follows_the_cursor_between_plates():
    objs, get = _scene()
    apply_world_ui(get, _payload(), ortho=15.0, hovered="choice_0")
    a = objs["choice_0"].worldScale[0]          # hovered: base * 1.08
    apply_world_ui(get, _payload(), ortho=15.0, hovered="choice_1")
    # layout re-writes scale every frame: the previously hovered plate is
    # back to base, the new one is bumped — no stale-state restore needed
    assert objs["choice_0"].worldScale[0] < a
    assert abs(objs["choice_1"].worldScale[0] - a) < 1e-6


def test_hover_during_camera_zoom_stays_relative():
    """ortho changes between frames (camera zoom): the bump must stay 8%
    of whatever the current layout scale is — never a frozen base."""
    objs, get = _scene()
    apply_world_ui(get, _payload(), ortho=15.0, hovered="choice_0")
    zoomed_base = objs["choice_1"].worldScale[0]   # same ortho frame
    apply_world_ui(get, _payload(), ortho=18.0, hovered="choice_1")
    new_base = objs["choice_0"].worldScale[0]      # bigger ortho → wider plates
    bumped = objs["choice_1"].worldScale[0]
    assert abs(bumped - new_base * HOVER_SCALE) < 1e-6
    assert abs(new_base - zoomed_base * (18.0 / 15.0)) < 1e-6


def test_hover_scale_constant_is_subtle():
    # a design pin: big enough to read, small enough not to shift layout
    assert 1.02 <= HOVER_SCALE <= 1.2
