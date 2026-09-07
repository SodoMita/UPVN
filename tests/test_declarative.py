"""Declarative script forms (M15) — parse, interpret, assets, typed state, `end`."""
import pytest
from pathlib import Path
from engine.script.parser import parse_string, ParseError
from engine.core.vn_state import VNState
from engine.core.vn_interpreter import VNInterpreter
from engine.core.vn_controller import VNController
from engine.core.vn_errors import ScriptRuntimeError

DECL = open("examples/05_declarative_script/script.rpy", encoding="utf-8").read()


def test_state_block_types_and_defaults():
    d = parse_string(DECL)
    assert d["defaults"]["affection"] == 0
    assert d["defaults"]["route"] == "none"
    assert d["types"]["affection"] == "int"
    assert d["types"]["route"] == "str"


def test_character_block():
    d = parse_string(DECL)
    assert d["characters"]["e"]["name"] == "Eileen"
    assert d["characters"]["e"]["color"] == "#c8ffc8"


def test_asset_manifest():
    d = parse_string(DECL)
    assert d["assets"]["images"]["bg classroom"] == "backgrounds/classroom.png"
    assert d["assets"]["images"]["eileen happy"] == "characters/eileen/happy.png"
    assert d["assets"]["audio"]["theme"] == "music/theme.ogg"
    assert d["assets"]["stages"]["classroom_3d"] == "stages/classroom.blend"


def test_set_and_choice_keyword_parse():
    d = parse_string(DECL)
    menu = [n for n in d["labels"]["start"] if n["cmd"] == "menu"][0]
    assert menu["choices"][0]["text"] == "Help Eileen"
    assert [n["cmd"] for n in menu["choices"][0]["block"]] == ["assign", "assign"]
    assigns = [n for n in menu["choices"][0]["block"]]
    assert assigns[0]["target"] == "affection" and assigns[0]["op"] == "+="


def test_headless_good_route():
    c = VNController(script_dict=parse_string(DECL))
    trace = c.run_headless(choices=[0])
    assert c.state.variables["affection"] == 1
    assert c.state.variables["route"] == "good"
    assert [e["type"] for e in trace] == ["scene", "show", "say", "menu", "assign", "assign", "jump", "say", "return", "end"]


def test_headless_neutral_route():
    c = VNController(script_dict=parse_string(DECL))
    c.run_headless(choices=[1])
    assert c.state.variables["affection"] == 0
    assert c.state.variables["route"] == "neutral"


def test_declarative_equals_legacy_trace():
    """The declarative forms must produce the same events as the legacy forms."""
    legacy = '''
define e = Character("Eileen")
default affection = 0
default route = "none"
label start:
    e "Hi."
    menu:
        "Help":
            $ affection += 1
            $ route = "good"
        "Ignore":
            $ route = "neutral"
    if affection >= 1:
        jump good
    else:
        jump neutral
label good:
    e "Good."
    return
label neutral:
    e "Neutral."
    return
'''
    decl = '''
character e:
    name "Eileen"
state:
    affection: int = 0
    route: str = "none"
label start:
    e "Hi."
    menu:
        choice "Help":
            set affection += 1
            set route = "good"
        end
        choice "Ignore":
            set route = "neutral"
        end
    end
    if affection >= 1:
        jump good
    else:
        jump neutral
    end
label good:
    e "Good."
    return
end
label neutral:
    e "Neutral."
    return
end
'''
    c1 = VNController(script_dict=parse_string(legacy))
    c2 = VNController(script_dict=parse_string(decl))
    t1 = c1.run_headless(choices=[0])
    t2 = c2.run_headless(choices=[0])
    sig1 = [(e["type"], e.get("label"), e.get("text")) for e in t1]
    sig2 = [(e["type"], e.get("label"), e.get("text")) for e in t2]
    assert sig1 == sig2
    assert c1.state.variables == c2.state.variables


def test_assets_resolve_in_state():
    c = VNController(script_dict=parse_string(DECL))
    c.run_headless(choices=[0])
    assert c.state.resolve_asset("images", "bg classroom") == "backgrounds/classroom.png"
    assert c.state.resolve_asset("images", "unknown") == "unknown"  # fallback


def test_typed_state_enforced():
    script = parse_string('''
state:
    affection: int = 0
label start:
    set affection = "oops"
    return
''')
    interp = VNInterpreter(script, VNState())
    with pytest.raises(ScriptRuntimeError) as ei:
        interp.run_headless()
    assert "declared int" in str(ei.value)


def test_typed_state_accepts_valid():
    script = parse_string('''
state:
    affection: int = 0
    ratio: float = 0.0
    name: str = ""
    flag: bool = False
    items: list = []
label start:
    set affection += 1
    set ratio = 0.5
    set name = "x"
    set flag = True
    set items = [1, 2]
    return
''')
    interp = VNInterpreter(script, VNState())
    interp.run_headless()
    assert interp.state.variables["affection"] == 1
    assert interp.state.variables["ratio"] == 0.5
    assert interp.state.variables["name"] == "x"
    assert interp.state.variables["flag"] is True
    assert interp.state.variables["items"] == [1, 2]


def test_end_terminators_optional():
    """`end` is optional — the same block parses with and without it."""
    with_end = '''
label start:
    menu:
        "A":
            jump a
    end
    return
end
label a:
    return
end
'''
    without_end = '''
label start:
    menu:
        "A":
            jump a
    return
label a:
    return
'''
    d1 = parse_string(with_end)
    d2 = parse_string(without_end)
    # AST shape (commands) must match; `_loc` line numbers naturally differ
    def shape(nodes):
        return [(n["cmd"], n.get("text"), n.get("label")) for n in nodes]
    assert shape(d1["labels"]["start"]) == shape(d2["labels"]["start"])


def test_bad_state_type_raises():
    with pytest.raises(ParseError) as ei:
        parse_string('''
state:
    affection: int = "not an int"
label start:
    return
''')
    assert "type mismatch" in str(ei.value)


def test_bad_end_unexpected_raises():
    with pytest.raises(ParseError) as ei:
        parse_string('''
label start:
    "hi"
end
end
''')
    assert "unexpected 'end'" in str(ei.value)


def test_set_outside_and_choice_outside_menu():
    with pytest.raises(ParseError):
        parse_string('label start:\n    choice "A":\n        jump a\n')
