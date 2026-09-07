from engine.script.parser import parse_string
from engine.core.vn_state import VNState
from engine.core.vn_interpreter import VNInterpreter
from engine.render.headless_renderer import render_state
from pathlib import Path

def test_load_stage_and_show3d_and_camera_preset():
    script = parse_string('''
label start:
    load_stage classroom_3d
    show3d eileen at marker_eileen
    show3d sylvie at marker_sylvie
    anim eileen wave
    camera preset closeup_eileen
    "hello"
    return
''')
    state = VNState()
    interp = VNInterpreter(script, state)
    trace = interp.run_headless()
    assert state.stage == "classroom_3d"
    assert "eileen" in state.stage_objects
    assert state.stage_objects["eileen"]["marker"] == "marker_eileen"
    assert state.stage_objects["eileen"]["anim"] == "wave"
    assert state.stage_objects["sylvie"]["marker"] == "marker_sylvie"
    assert state.camera["preset"] == "closeup_eileen"
    # check trace contains those events
    types = [t["type"] for t in trace]
    assert "load_stage" in types
    assert "show3d" in types
    assert "camera_preset" in types

def test_hybrid_renderer_not_black_fallback(tmp_path):
    script = parse_string('''
label start:
    load_stage classroom_3d
    show3d eileen at marker_eileen
    camera preset closeup_eileen
    "No BG, just 3D stage — not black"
    return
''')
    state = VNState()
    interp = VNInterpreter(script, state)
    interp.run_headless()
    # render: should not be solid black, should contain stage floor color
    out = tmp_path / "hybrid.png"
    img = render_state(state, {"type":"say","who":None,"text":"No BG, just 3D stage — not black"}, out)
    assert out.exists()
    # sample pixel at floor area should not be black (6,8,14)
    pix = img.getpixel((640, 450))  # floor area
    assert pix != (6,8,14), f"floor should not be black fallback, got {pix}"
    # top area also not black when stage only (should be stage wall color)
    pix_top = img.getpixel((640, 100))
    assert pix_top != (6,8,14)

def test_hybrid_2d_and_3d_coexist():
    script = parse_string('''
define e = Character("Eileen")
label start:
    load_stage classroom_3d
    show3d eileen at marker_eileen
    scene bg classroom
    show eileen at left
    e "Left over 3D"
    show eileen at right with move
    e "Move right over 3D"
    return
''')
    state = VNState()
    interp = VNInterpreter(script, state)
    interp.run_headless()
    assert state.stage == "classroom_3d"
    assert "eileen" in state.stage_objects
    assert "eileen" in state.shown_actors  # 2D sprite
    assert state.scene.background == "bg classroom"
    # hybrid: both stage and bg present
    assert state.stage is not None and state.scene.background is not None

def test_show3d_anim_updates():
    script = parse_string('''
label start:
    load_stage classroom_3d
    show3d eileen at marker_eileen
    anim eileen wave
    anim eileen idle
    "test"
    return
''')
    state = VNState()
    interp = VNInterpreter(script, state)
    interp.run_headless()
    assert state.stage_objects["eileen"]["anim"] == "idle"
