import time
from engine.script.parser import parse_string
from engine.core.vn_interpreter import VNInterpreter
from engine.core.vn_state import VNState
# Pillow backs the headless renderer; without it these tests skip rather
# than aborting collection (which would take the rest of the suite down).
import pytest
pytest.importorskip("PIL", reason="Pillow is required by the headless renderer")
from engine.render.headless_renderer import render_state
from pathlib import Path

def test_show_move_interpolates_not_snap():
    script = parse_string('''
label start:
    show eileen at left
    "left"
    show eileen at center with move
    "center after move"
    return
''')
    state = VNState()
    interp = VNInterpreter(script, state)
    gen = interp.run()
    # step through
    # first show left
    ev = next(gen)  # scene? actually show
    # need to consume until first say
    # easier: run_headless and check move fields
    state2 = VNState()
    interp2 = VNInterpreter(script, state2)
    trace = interp2.run_headless()
    # after headless, eileen should be at center with move_from left
    actor = state2.shown_actors["eileen"]
    assert actor.position == "center"
    assert actor.move_from == "left"
    assert actor.move_to == "center"
    assert actor.move_duration == 0.5
    # interpolation at t=0 should be left, at t=0.25 mid, at t=0.5 center
    # use sprite renderer helper or direct calc
    from engine.render.sprite_renderer import SpriteRenderer, POSITIONS
    renderer = SpriteRenderer(state2)
    now0 = actor.move_t0 or time.time()
    # at start (t0)
    pos0 = renderer.get_interpolated_position("eileen", now=now0 + 0.001)
    pos_mid = renderer.get_interpolated_position("eileen", now=now0 + 0.25)
    pos_end = renderer.get_interpolated_position("eileen", now=now0 + 1.0)
    # pos0 should be near left, pos_mid between, pos_end at center
    assert pos0[0] < -1.0  # left is -3, center 0, so mid ~ -1.5
    assert -2.5 < pos_mid[0] < -0.5  # between
    assert abs(pos_end[0] - 0) < 0.01

def test_show_move_ease_variants():
    for ease in ["move", "ease", "linear", "easein", "easeout"]:
        script = parse_string(f'''
label start:
    show eileen at left
    "a"
    show eileen at right with {ease}
    "b"
    return
''')
        state = VNState()
        interp = VNInterpreter(script, state)
        interp.run_headless()
        actor = state.shown_actors["eileen"]
        # easing should be recorded
        expected = "ease" if ease=="move" else ease
        assert actor.move_easing == expected
        assert actor.move_from == "left"
        assert actor.move_to == "right"

def test_camera_zoom_duration_and_easing():
    script = parse_string('''
label start:
    camera zoom 1.2
    "a"
    camera zoom 1.5 duration 1.0 with ease
    "b"
    camera zoom 0.8 duration 0.5 with linear
    "c"
    return
''')
    state = VNState()
    interp = VNInterpreter(script, state)
    trace = interp.run_headless()
    # final zoom should be 0.8
    assert state.camera["zoom"] == 0.8
    assert state.camera["_zoom_dur"] == 0.5
    assert state.camera["_zoom_ease"] == "linear"
    # check first zoom default duration 1.0
    # we can test by stepping manually
    state2 = VNState()
    interp2 = VNInterpreter(parse_string('''
label start:
    camera zoom 1.2
    "a"
    return
'''), state2)
    interp2.run_headless()
    assert state2.camera["zoom"] == 1.2
    assert state2.camera["_zoom_dur"] == 1.0
    assert state2.camera["_zoom_from"] == 1.0

def test_camera_zoom_interpolation_headless():
    from engine.render.stage_manager import StageManager
    state = VNState()
    state.camera["zoom"] = 1.5
    state.camera["_zoom_from"] = 1.0
    state.camera["_zoom_to"] = 1.5
    state.camera["_zoom_dur"] = 1.0
    state.camera["_zoom_ease"] = "linear"
    state.camera["_zoom_t0"] = time.time() - 0.5  # half
    mgr = StageManager(state)
    cur = mgr.get_current_zoom()
    # linear half should be 1.25
    assert abs(cur - 1.25) < 0.02
    # after duration done should be 1.5
    state.camera["_zoom_t0"] = time.time() - 2.0
    assert abs(mgr.get_current_zoom() - 1.5) < 0.01
    assert mgr.is_zoom_done() == True

def test_headless_renderer_shows_move_and_zoom_badges(tmp_path):
    script = parse_string('''
define e = Character("Eileen")
label start:
    scene bg classroom
    show eileen at left
    e "Left"
    show eileen at center with move
    e "Center after move"
    camera zoom 1.2
    e "Zoomed"
    return
''')
    from engine.core.vn_controller import VNController
    c = VNController(script_dict=script)
    c.load()
    # first say left
    assert c.current_event["text"] == "Left"
    # advance to after move
    c._advance()
    # now at center after move
    assert c.current_event["text"] == "Center after move"
    actor = c.state.shown_actors["eileen"]
    # set mid move for rendering test
    actor.move_t0 = time.time() - 0.25
    out = tmp_path / "mid.png"
    render_state(c.state, c.current_event, out)
    assert out.exists()
    # set zoom mid
    c.state.camera["zoom"] = 1.2
    c.state.camera["_zoom_from"] = 1.0
    c.state.camera["_zoom_to"] = 1.2
    c.state.camera["_zoom_dur"] = 1.0
    c.state.camera["_zoom_t0"] = time.time() - 0.5
    out2 = tmp_path / "zoom.png"
    render_state(c.state, c.current_event, out2)
    assert out2.exists()
