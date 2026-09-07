import pytest
from engine.core.vn_controller import VNController

def test_00_headless():
    c = VNController("examples/00_minimal_dialogue/script.rpy")
    trace = c.run_headless()
    assert [e["type"] for e in trace] == ["say","say","say","say","return","end"]
    assert len(c.state.history) == 4

def test_01_both_paths():
    for choice, target_label in [(0,"library"), (1,"rooftop")]:
        c = VNController("examples/01_branching_choice/script.rpy")
        trace = c.run_headless(choices=[choice])
        # second event is menu, third is jump to chosen label
        jumps = [e for e in trace if e["type"]=="jump"]
        assert jumps[0]["label"] == target_label
        # both end via "ending"
        assert any(e.get("label")=="ending" for e in trace if e["type"] in ("say","end"))

def test_03_help_route():
    c = VNController("examples/03_variables_routes/script.rpy")
    c.run_headless(choices=[0])
    assert c.state.variables["affection"] == 1
    assert c.state.variables["helped_eileen"] is True
    assert c.state.variables["route"] == "good"
    # interpolation worked: last good_scene says contain "route good"
    texts = [e["text"] for e in c.state.history]
    assert any("route good" in t for t in texts)

def test_03_neutral_route():
    c = VNController("examples/03_variables_routes/script.rpy")
    c.run_headless(choices=[1])
    assert c.state.variables["affection"] == 0
    assert c.state.variables["route"] == "neutral"

def test_the_question_paths():
    import pathlib as _pl
    _p = _pl.Path("/home/user/renpy_src/the_question/game/script.rpy")
    if not _p.exists():
        pytest.skip("Ren'Py source not cloned at /home/user/renpy_src/the_question — skip")
    # path 0,0 = ask rightaway -> game -> marry, book False
    c = VNController(str(_p))
    c.run_headless(choices=[0,0])
    assert c.state.variables["book"] is False
    assert any("Good Ending" in e.get("text","") for e in c.state.history)

    # path 0,1 = ask rightaway -> book -> marry, book True
    c = VNController(str(_p))
    c.run_headless(choices=[0,1])
    assert c.state.variables["book"] is True

    # path 1 = ask later -> bad ending
    c = VNController(str(_p))
    c.run_headless(choices=[1])
    assert any("Bad Ending" in e.get("text","") for e in c.state.history)

def test_rollback_snapshot():
    from engine.core.vn_interpreter import VNInterpreter
    from engine.script.parser import parse_string
    script = parse_string(open("examples/03_variables_routes/script.rpy").read())
    from engine.core.vn_state import VNState
    s = VNState()
    interp = VNInterpreter(script, s)
    trace = interp.run_headless(choices=[0])
    # rollback stack should have entry per say/menu
    assert len(interp.rollback_stack) >= 4
    # Find snapshot before first say (affection 0)
    snap = interp.rollback_stack[1]  # after first say's snapshot? Check first few
    # mutate then restore to a snapshot where affection was 0
    s.variables["affection"] = 99
    # restore earliest snapshot where affection is still 0 (index 0)
    s.restore(interp.rollback_stack[0])
    assert s.variables["affection"] == 0  # initial

def test_save_load_roundtrip(tmp_path):
    from engine.save.save_manager import SaveManager
    c = VNController("examples/03_variables_routes/script.rpy")
    # run to just before choice
    trace = c.run_headless(choices=[0])
    # save
    mgr = SaveManager(c.state, save_dir=tmp_path)
    p = mgr.save(1)
    assert p.exists()
    # mutate
    c.state.variables["affection"] = 999
    # load
    mgr.load(1)
    assert c.state.variables["affection"] == 1

def test_interpolation_and_tags():
    from engine.script.parser import parse_string
    script = parse_string('''
default name = "World"
label start:
    "Hello [name] {b}bold{/b}!"
    return
''')
    from engine.core.vn_state import VNState
    from engine.core.vn_interpreter import VNInterpreter
    interp = VNInterpreter(script, VNState())
    trace = interp.run_headless()
    say = [e for e in trace if e["type"]=="say"][0]
    assert "Hello World" in say["text"]
