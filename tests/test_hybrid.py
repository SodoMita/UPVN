from engine.script.parser import parse_string
from engine.core.vn_state import VNState
from engine.core.vn_interpreter import VNInterpreter
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
