"""Full .rpy tier (drop-in Ren'Py) — parse, interpret, python blocks, control flow.

Three language tiers compile to one IR:
  1. .urpy        — fully declarative, zero embedded Python (urpy_parser.py)
  2. .rpy safe    — declarative subset; full-tier constructs rejected with guidance
  3. .rpy full    — drop-in Ren'Py: python:/init, while/break/continue, $, screens…

These tests cover tier 3 (mode='full') and the safe-mode rejection boundary.
"""
import pytest
from engine.script.parser import parse_string, parse_string_full, ParseError
from engine.core.vn_interpreter import VNInterpreter
from engine.core.vn_errors import ScriptRuntimeError

THE_QUESTION_STYLE = r'''
define e = Character("Eileen", color="#c8ffc8")

default points = 0

init python:
    bonus = 5

label start():
    python:
        points += bonus
    e "Welcome. You have [points] points."
    menu:
        "Ask about the book" if points > 0:
            jump book
        "Leave":
            jump leave

label book(name="magic"):
    e "The [name] book is on the shelf."
    while points < 10:
        $ points += 1
    e "Loop done: [points]."
    call ender(2)
    e "Back from ender."
    return

label ender(n):
    e "Called with n=[n]."
    return

label leave():
    e "Goodbye."
    return
'''


# ------------------------------------------------------------------ parsing
def test_full_parse_populates_tier3_fields():
    d = parse_string_full(THE_QUESTION_STYLE)
    assert d["full"] is True
    assert d["init_python"] == ["bonus = 5"]
    assert d["label_params"]["book"] == [{"name": "name", "default": '"magic"'}]
    assert d["label_params"]["ender"] == [{"name": "n", "default": None}]
    assert d["characters"]["e"]["name"] == "Eileen"
    assert d["defaults"]["points"] == 0


def test_full_parse_defines_transforms_screens_styles_translations():
    d = parse_string_full(r'''
define cfg_volume = 0.8
transform fade_in:
    alpha 0.0
    linear 0.5 alpha 1.0
screen hud:
    text "Health"
style hud_text:
    size 20
translate russian start:
    "Privet"
label start():
    "hi"
''')
    assert d["defines"]["cfg_volume"] == 0.8
    assert "fade_in" in d["transforms"]
    assert "hud" in d["screens"]
    assert "hud_text" in d["styles"]
    assert "russian_start" in d["translations"]


def test_full_parse_init_block_and_init_offset():
    d = parse_string_full(r'''
init:
    define cfg_music_vol = 0.9
init offset = 10
label start():
    "hi"
''')
    assert d["defines"]["cfg_music_vol"] == 0.9


def test_label_params_default_and_required():
    d = parse_string_full(r'''
label greet(name, greeting="hello"):
    "hi"
label start():
    "go"
''')
    assert d["label_params"]["greet"] == [
        {"name": "name", "default": None},
        {"name": "greeting", "default": '"hello"'},
    ]


# ------------------------------------------------------------------ interpretation
def test_full_run_init_python_while_call_params():
    d = parse_string_full(THE_QUESTION_STYLE)
    interp = VNInterpreter(d)
    trace = interp.run_headless(choices=[0])
    assert trace[0]["type"] == "say"
    assert trace[0]["text"] == "Welcome. You have 5 points."
    # while loop runs until points == 10
    assigns = [ev for ev in trace if ev["type"] == "assign"]
    assert [ev["value"] for ev in assigns] == [6, 7, 8, 9, 10]
    assert any(ev["type"] == "call" and ev["label"] == "ender" for ev in trace)
    texts = [ev["text"] for ev in trace if ev["type"] == "say"]
    assert "Called with n=2." in texts
    assert "Back from ender." in texts
    assert "The magic book is on the shelf." in texts
    assert interp.state.variables["points"] == 10
    assert interp.state.variables["bonus"] == 5


def test_full_run_conditional_menu_choice_hidden():
    d = parse_string_full(r'''
default flag = False
label start():
    menu:
        "Visible" if flag:
            jump a
        "Always":
            jump b
label a():
    "A"
    return
label b():
    "B"
    return
''')
    interp = VNInterpreter(d)
    trace = interp.run_headless(choices=[0])
    # "Visible" is filtered out; choice 0 selects "Always"
    menu = [ev for ev in trace if ev["type"] == "menu"][0]
    assert [c["text"] for c in menu["choices"]] == ["Always"]
    assert any(ev["type"] == "jump" and ev["label"] == "b" for ev in trace)


def test_full_break_and_continue():
    d = parse_string_full(r'''
default i = 0
default total = 0
label start():
    while i < 10:
        $ i += 1
        if i == 3:
            continue
        if i == 6:
            break
        $ total += i
    "done"
    return
''')
    interp = VNInterpreter(d)
    trace = interp.run_headless()
    assert any(ev["type"] == "break" for ev in trace)
    assert interp.state.variables["i"] == 6
    assert interp.state.variables["total"] == 1 + 2 + 4 + 5


def test_full_jump_call_expression():
    d = parse_string_full(r'''
default target = "finish"
label start():
    jump expression target
label other():
    "other"
    return
label finish():
    call expression "other"
    "fin"
    return
''')
    interp = VNInterpreter(d)
    trace = interp.run_headless()
    assert any(ev["type"] == "jump" and ev["label"] == "finish" for ev in trace)
    assert any(ev["type"] == "call" and ev["label"] == "other" for ev in trace)
    texts = [ev["text"] for ev in trace if ev["type"] == "say"]
    assert texts == ["other", "fin"]


def test_full_renpy_jump_from_python_block():
    d = parse_string_full(r'''
label start():
    python:
        renpy.jump("target")
    "unreachable"
label target():
    "reached"
    return
''')
    interp = VNInterpreter(d)
    trace = interp.run_headless()
    assert any(ev["type"] == "jump" and ev["label"] == "target" for ev in trace)
    texts = [ev["text"] for ev in trace if ev["type"] == "say"]
    assert texts == ["reached"]


def test_full_window_nvl_voice_queue_screens():
    d = parse_string_full(r'''
screen hud:
    text "Health"
label start():
    window hide
    nvl clear
    nvl mode nvl
    voice "line01.ogg"
    queue music "theme.ogg" fadein 1.0
    queue sound "click.ogg"
    show screen hud
    hide screen hud
    window auto
    "ok"
    return
''')
    interp = VNInterpreter(d)
    trace = interp.run_headless()
    types = [ev["type"] for ev in trace]
    for expected in ("window", "nvl", "nvl_mode", "play_voice", "play_music",
                     "play_sound", "show_screen", "hide_screen", "say"):
        assert expected in types, expected
    assert interp.state.window == "auto"
    assert interp.state.nvl == "clear"
    assert interp.state.nvl_mode == "nvl"
    # music queued asset recorded
    music = [ev for ev in trace if ev["type"] == "play_music"][0]
    assert music["asset"] == "theme.ogg"
    assert music["fadein"] == 1.0


def test_full_generic_dollar_python_statement():
    d = parse_string_full(r'''
default x = 1
label start():
    $ x += 10
    $ print("hi")
    "x is [x]"
    return
''')
    interp = VNInterpreter(d)
    trace = interp.run_headless()
    assert interp.state.variables["x"] == 11


def test_full_python_block_error_is_runtime_error():
    d = parse_string_full(r'''
label start():
    python:
        raise ValueError("boom")
    return
''')
    interp = VNInterpreter(d)
    with pytest.raises(ScriptRuntimeError):
        interp.run_headless()


# ------------------------------------------------------------------ safe-mode boundary
@pytest.mark.parametrize("source,fragment", [
    ("label start:\n    python:\n        x = 1\n", "python:"),
    ("init python:\n    x = 1\n\nlabel start:\n    \"hi\"\n", "init"),
    ("init:\n    define x = 1\n\nlabel start:\n    \"hi\"\n", "init"),
    ("define cfg.x = 5\n\nlabel start:\n    \"hi\"\n", "define"),
    ("transform t:\n    xalign 0.5\n\nlabel start:\n    \"hi\"\n", "transform"),
    ("screen s:\n    text \"x\"\n\nlabel start:\n    \"hi\"\n", "screen"),
    ("style s:\n    size 20\n\nlabel start:\n    \"hi\"\n", "style"),
    ("translate ru start:\n    \"x\"\n\nlabel start:\n    \"hi\"\n", "translate"),
    ("label start:\n    while True:\n        pass\n", "while"),
    ("label start:\n    break\n", "break"),
    ("label start:\n    window hide\n", "window"),
    ("label start:\n    show screen hud\n", "screen"),
    ("label start:\n    jump expression x\n", "jump expression"),
    ("label start:\n    call foo(1)\n", "call with arguments"),
])
def test_safe_mode_rejects_full_tier_constructs(source, fragment):
    with pytest.raises(ParseError) as ei:
        parse_string(source)
    assert "full" in str(ei.value)


def test_same_ir_shape_across_tiers():
    """Safe and full modes both return the same IR keys (full adds tier-3 fields)."""
    safe = parse_string('label start():\n    "hi"\n')
    full = parse_string_full('label start():\n    "hi"\n')
    for key in ("labels", "characters", "defaults", "types", "assets"):
        assert key in safe and key in full
    assert full["full"] is True


# ------------------------------------------------------------------ .urpy tier (1)
def test_urpy_tier_parses_and_runs():
    """Tier 1 (.urpy) compiles to the same IR and runs headless."""
    from engine.script.parser import parse_file
    d = parse_file("examples/13_urpy_tier/script.urpy")
    assert d["language"] == "urpy"
    assert d["types"]["affection"] == "int"
    assert d["defaults"]["route"] == "none"
    assert "bird_route" in d["labels"]
    interp = VNInterpreter(d)
    trace = interp.run_headless(choices=[0])
    texts = [ev["text"] for ev in trace if ev["type"] == "say"]
    assert "This script is fully declarative." in texts[0]
    assert any("route bird" in t for t in texts)
    assert interp.state.variables["seen_bird"] is True


def test_urpy_tier_rejects_python_and_legacy_forms():
    from engine.script.urpy_parser import parse_urpy_string
    for bad in (
        'label start:\n    $ x = 1\nend\n',
        'label start:\n    "hi"\n',                      # missing required end
        'define e = Character("Eileen")\nlabel start:\n    "hi"\nend\n',
        'default x = 1\nlabel start:\n    "hi"\nend\n',
        'label start:\n    python:\n        x = 1\nend\n',
    ):
        with pytest.raises(ParseError):
            parse_urpy_string(bad)
