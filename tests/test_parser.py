import pytest
from engine.script.parser import parse_string, ParseError
from engine.core.vn_controller import VNController

def test_00_parses():
    d = parse_string(open("examples/00_minimal_dialogue/script.rpy").read())
    assert "start" in d["labels"]
    assert len(d["labels"]["start"]) == 5  # 4 says + return
    assert d["labels"]["start"][0]["cmd"] == "say"

def test_01_branching():
    d = parse_string(open("examples/01_branching_choice/script.rpy").read())
    assert set(d["labels"].keys()) == {"start","library","rooftop","ending"}
    menu = d["labels"]["start"][1]
    assert menu["cmd"] == "menu"
    assert len(menu["choices"]) == 2
    assert menu["choices"][0]["text"] == "Library"

def test_02_sprites_and_3d_stubs():
    d = parse_string(open("examples/02_sprites_backgrounds/script.rpy").read())
    cmds = [n["cmd"] for n in d["labels"]["start"]]
    assert "scene" in cmds
    assert "show" in cmds
    assert "hide" in cmds
    assert "load_stage" in cmds
    assert "show3d" in cmds
    assert "camera_preset" in cmds

def test_03_variables():
    d = parse_string(open("examples/03_variables_routes/script.rpy").read())
    assert d["defaults"]["affection"] == 0
    assert d["defaults"]["helped_eileen"] is False
    assert d["defaults"]["route"] == "none"
    # if node present
    assert any(n["cmd"] == "if" for n in d["labels"]["start"])

def test_the_question_parses():
    d = parse_string(open("/home/user/renpy_src/the_question/game/script.rpy").read())
    assert {"start","rightaway","game","book","marry","later"} <= set(d["labels"].keys())
    assert d["characters"]["s"]["name"] == "Sylvie"
    assert d["defaults"]["book"] is False

def test_bad_jump_colon_hint():
    with pytest.raises(ParseError) as ei:
        parse_string('label start:\n    jump foo:\n')
    assert "does not take a colon" in str(ei.value)
    assert "Hint" in str(ei.value)

def test_bad_indent_hint():
    with pytest.raises(ParseError) as ei:
        parse_string('label start:\n  "hi"\n')  # 2 spaces not 4
    assert "expected 4 spaces" in str(ei.value)

def test_menu_missing_colon():
    with pytest.raises(ParseError) as ei:
        parse_string('label start:\n    menu:\n        "choice"\n')
    # "choice" without colon but not caption? Actually single choice without colon or block is missing colon
    # Our parser treats bare quoted without colon as caption, then expects choices — this will error "menu has no choices"
    assert "menu has no choices" in str(ei.value) or "missing colon" in str(ei.value)
