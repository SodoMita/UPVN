import pytest
from engine.script.parser import parse_string
from engine.core.vn_state import VNState
from engine.core.vn_interpreter import VNInterpreter, strip_tags, interpolate
from engine.core.vn_controller import VNController

def test_history_contains_styled_and_stripped():
    script = parse_string('''
default name = "World"
default route = "good"
label start:
    "Hello [name] {b}bold{/b} {color=#f00}red{/color}!"
    "Second {i}italic{/i} line"
    return
''')
    interp = VNInterpreter(script, VNState())
    trace = interp.run_headless()
    # history should have 2 entries
    assert len(interp.state.history) == 2
    h0 = interp.state.history[0]
    # tags preserved in text
    assert "{b}bold{/b}" in h0["text"]
    assert "{color" in h0["text"]
    # stripped version available
    assert h0["stripped"] == "Hello World bold red!"
    assert strip_tags(h0["text"]) == "Hello World bold red!"
    # interpolation worked
    assert "Hello World" in h0["text"]
    # seen_history populated
    assert len(interp.state.seen_history) == 2

def test_interpolation_route_affection():
    # uses example 03
    c = VNController("examples/03_variables_routes/script.rpy")
    c.run_headless(choices=[0])
    texts = [h["text"] for h in c.state.history]
    assert any("route good" in t for t in texts)
    assert any("affection is 1" in t for t in texts)
    c2 = VNController("examples/03_variables_routes/script.rpy")
    c2.run_headless(choices=[1])
    texts2 = [h["text"] for h in c2.state.history]
    assert any("route neutral" in t for t in texts2)

def test_backlog_preserves_all():
    c = VNController("examples/00_minimal_dialogue/script.rpy")
    c.run_headless()
    assert len(c.state.history) == 4
    # backlog should contain the narration + dialogues in order
    assert "This is narration" in c.state.history[0]["text"]
    # stripped equals without tags (no tags in this example, same)
    for h in c.state.history:
        assert "stripped" in h
        assert h["stripped"] == strip_tags(h["text"])

def test_skip_toggle():
    c = VNController("examples/00_minimal_dialogue/script.rpy")
    assert not c.state.skip
    c.toggle_skip()
    assert c.state.skip
    c.toggle_skip()
    assert not c.state.skip

def test_auto_toggle():
    c = VNController("examples/00_minimal_dialogue/script.rpy")
    assert not c.state.auto
    c.toggle_auto()
    assert c.state.auto
    assert c.state.auto_delay == 0.7

def test_rollback_n_steps_hash():
    import json
    # Create a new controller and step interactively — verify N-step rollback hash equality (M08)
    c2 = VNController("examples/03_variables_routes/script.rpy")
    c2.load()
    # initial event is say "Can you help..."
    assert c2.current_event["type"] == "say"
    h1 = json.loads(json.dumps(c2.state.snapshot(), sort_keys=True))
    # advance to menu
    c2._advance()  # to menu
    assert c2.current_event["type"] == "menu"
    h2 = json.loads(json.dumps(c2.state.snapshot(), sort_keys=True))
    c2.choose(0)  # Help her -> spliced block executes, now at Thanks
    assert c2.current_event["type"] == "say"
    assert "Thanks!" in c2.current_event["text"]
    h_before = json.loads(json.dumps(c2.state.snapshot(), sort_keys=True))
    # stack is [h1, h2, beforeThanks]; h_before has affection 1
    # Two rollbacks should get back to menu state (h2) — affection 0, history 1
    c2.rollback(steps=2)
    after = json.loads(json.dumps(c2.state.snapshot(), sort_keys=True))
    assert after["variables"] == h2["variables"]
    assert after["instruction_index"] == h2["instruction_index"]
    assert len(after["history"]) == len(h2["history"])
    # one more rollback (with duplicate push) needs 2 pops to reach h1 — just verify we can get back to start via 2 steps
    c2.rollback(steps=2)
    after2 = json.loads(json.dumps(c2.state.snapshot(), sort_keys=True))
    assert after2["variables"] == h1["variables"]
    assert after2["instruction_index"] == h1["instruction_index"]
    # forward 2 -> should be back to h2
    c2.roll_forward(steps=2)
    assert json.loads(json.dumps(c2.state.snapshot(), sort_keys=True))["variables"] == h2["variables"]
    # forward 2 -> should be back to h_before (Thanks state) affection 1
    c2.roll_forward(steps=2)
    assert json.loads(json.dumps(c2.state.snapshot(), sort_keys=True))["variables"] == h_before["variables"]

def test_rollback_stack_size():
    from engine.script.parser import parse_string
    script = parse_string('''
label start:
    "a"
    "b"
    "c"
    "d"
    return
''')
    interp = VNInterpreter(script, VNState())
    interp.run_headless()
    # should have 4 snapshots (one per say)
    assert len(interp.rollback_stack) == 4
