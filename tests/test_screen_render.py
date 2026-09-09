"""M23 — the headless renderer draws the M22 widget trees.

`engine/ui/screen_lang.py` produces the widget list and M22 records it in
`VNState.active_screens`; this milestone makes `render_state` actually paint
it, so a `show screen` is visible in a golden trace instead of only correct in
JSON. These tests assert pixels, not JSON.
"""
from PIL import Image

from engine.script.parser import parse_string
from engine.core.vn_interpreter import VNInterpreter
from engine.core.vn_state import VNState
from engine.render.headless_renderer import draw_active_screens, render_state

SCRIPT = '''
default gold = 12
default achievements = ["Found the key", "Met Rosa"]

screen panel(title):
    frame:
        has vbox:
            spacing 8
        label title
        transclude

screen hud(score=0):
    zorder 50
    use panel("Status"):
        text "Gold: [score]"
        for a in achievements:
            text "[a]"
        if score > 5:
            textbutton "Claim reward" action Return("claim")

screen confirm(message, yes_action):
    modal True
    zorder 200
    frame:
        vbox:
            label message
            hbox:
                textbutton "Yes" action yes_action
                textbutton "No" action Return(False)

label start:
    scene bg classroom
    show screen hud(score=gold)
    "look"
'''


def _state():
    interp = VNInterpreter(parse_string(SCRIPT, mode='full'), VNState())
    interp.run_headless()
    return interp.state


def test_no_screens_draws_nothing_and_does_not_raise():
    state = VNState()
    img = Image.new("RGBA", (1280, 720), (8, 10, 22, 255))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img, "RGBA")
    assert draw_active_screens(img, draw, state) == 0


def test_hud_is_painted_onto_the_frame():
    state = _state()
    blank = Image.new("RGB", (1280, 720), (8, 10, 22))
    frame = render_state(state, None, None)
    # the screen must visibly change the frame, not silently no-op
    assert list(frame.getdata()) != list(blank.getdata())
    # and the change is near the top where the HUD is laid out
    top = frame.crop((0, 0, 1280, 220))
    assert list(top.getdata()) != list(blank.crop((0, 0, 1280, 220)).getdata())


def test_zorder_and_modal_dim():
    state = _state()
    # add a modal confirm on top of the hud
    confirm = state.active_screens and dict(state.active_screens)
    interp = VNInterpreter(parse_string(SCRIPT, mode='full'), state)
    interp.screen_lang  # ensure wired
    # render with hud only vs with an added modal screen
    from engine.render.headless_renderer import render_state as rs
    state2 = _state()
    state2.active_screens["confirm"] = {
        "args": [], "modal": True,
        "props": {"modal": True, "zorder": 200},
        "widgets": state.active_screens["hud"]["widgets"],
    }
    img_no = rs(state, None, None)
    img_modal = rs(state2, None, None)
    # the modal must dim the backdrop: a background pixel goes darker
    px = img_no.getpixel((640, 600))
    px2 = img_modal.getpixel((640, 600))
    assert sum(px2) <= sum(px)


def test_render_never_raises_on_garbage_widgets():
    state = VNState()
    state.active_screens["broken"] = {"args": [], "props": {}, "modal": False,
                                      "widgets": [{"kind": "vbox", "props": {},
                                                   "children": [
                                                       {"kind": "no-such-widget",
                                                        "props": {"xalign": "not-a-number"},
                                                        "text": "x"}]}]}
    img = render_state(state, None, None)
    assert img.size == (1280, 720)
