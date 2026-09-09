"""M22 — the screen-language interpreter.

Captured `screen:` bodies used to be inert text: `call screen` / `show screen`
emitted an event with a name and nothing to draw, so the 99 screens in the
Ren'Py SDK tutorial and the 23 in LearnToCodeRPG never amounted to a UI.
These tests cover turning a screen body into a widget tree, and the wiring that
puts that tree on the event.
"""
import pytest

from engine.script.parser import parse_string
from engine.core.vn_interpreter import VNInterpreter
from engine.core.vn_state import VNState
from engine.ui.screen_lang import (
    ScreenLang,
    ScreenLangError,
    parse_screen_body,
    split_props,
    tokenize,
)


# ---------------------------------------------------------------- tokenising
def test_tokenize_keeps_calls_with_spaces_intact():
    toks = tokenize('textbutton _("Yes") id "confirm_yes_button" action yes_action')
    assert toks == ['textbutton', '_("Yes")', 'id', '"confirm_yes_button"',
                    'action', 'yes_action']


def test_tokenize_handles_nested_brackets():
    toks = tokenize('textbutton "Go" action [Return(1), Hide()]')
    assert toks == ['textbutton', '"Go"', 'action', '[Return(1), Hide()]']


def test_split_props_separates_positional_from_properties():
    args, props = split_props(['"Wave"', 'action', 'Return("wave")', 'xalign', '0.5'])
    assert args == ['"Wave"']
    assert props == {'action': 'Return("wave")', 'xalign': '0.5'}


# ---------------------------------------------------------------- parsing
def _tree(src, name='s'):
    script = parse_string(src, mode='full')
    body = script['screens'][name]
    return parse_screen_body(body['lines'], body['indents']), script


def test_body_keeps_indentation_and_params():
    _, script = _tree('''
label start:
    "x"

screen choice(items):
    vbox:
        for i in items:
            textbutton i.caption action i.action
''', 'choice')
    body = script['screens']['choice']
    assert body['params'] == 'items'
    assert body['indents'] == [4, 8, 12]


def test_parse_builds_nested_containers():
    nodes, _ = _tree('''
label start:
    "x"

screen s():
    vbox:
        xalign 0.5
        text "a"
        text "b"
''')
    assert len(nodes) == 1
    vbox = nodes[0]
    assert vbox.kind == 'vbox'
    # `xalign 0.5` is still a sibling _prop node here; the evaluator folds it
    # onto the container, so the tree keeps the source shape faithfully
    assert [c.kind for c in vbox.children] == ['_prop', 'text', 'text']
    assert vbox.children[0].props == {'xalign': '0.5'}


def test_has_vbox_wraps_the_following_siblings():
    nodes, _ = _tree('''
label start:
    "x"

screen s():
    frame:
        has vbox
        add "a.png"
        add "b.png"
''')
    frame = nodes[0]
    assert frame.kind == 'frame'
    # `has vbox` is a declaration, not a block: the container is synthesised
    assert len(frame.children) == 1
    vbox = frame.children[0]
    assert vbox.kind == 'vbox'
    assert [c.kind for c in vbox.children] == ['add', 'add']


def test_has_with_property_block_keeps_properties():
    nodes, _ = _tree('''
label start:
    "x"

screen s():
    frame:
        has vbox:
            spacing 10
        text "a"
''')
    vbox = nodes[0].children[0]
    assert vbox.kind == 'vbox'
    assert vbox.props == {'spacing': '10'}


def test_if_elif_else_collapse_into_one_chain():
    nodes, _ = _tree('''
label start:
    "x"

screen s():
    if a:
        text "one"
    elif b:
        text "two"
    else:
        text "three"
''')
    assert len(nodes) == 1
    chain = nodes[0]
    assert chain.kind == '_cond'
    assert [b.kind for b in chain.children] == ['if', 'elif', 'else']


def test_mismatched_indents_are_reported():
    with pytest.raises(ScreenLangError):
        parse_screen_body(['text "a"'], [0, 4])


# ---------------------------------------------------------------- rendering
def _render(src, name='s', scope=None, store=None):
    script = parse_string(src, mode='full')
    variables = dict(store or {})
    state = VNState()
    state.variables.update(variables)
    interp = VNInterpreter(script, state)
    sl = ScreenLang(screens=script['screens'],
                    evaluator=interp._eval_screen_expr,
                    executor=interp._exec_screen_code)
    return sl.render(name, scope=scope)


def test_text_and_button_render_with_resolved_values():
    r = _render('''
label start:
    "x"

default score = 42

screen s(who):
    vbox:
        text "Hello, [who]! Score: [score]"
        textbutton "Wave" action Return("wave")
''', scope={'who': 'Eileen'})
    assert r['errors'] == []
    vbox = r['widgets'][0]
    text, button = vbox['children']
    assert text['text'] == 'Hello, Eileen! Score: 42'
    assert button['text'] == 'Wave'
    # the action has no Python value in UPVN, but its source must survive
    assert button['props']['action'] == 'Return("wave")'


def test_screen_level_properties_land_on_the_screen():
    r = _render('''
label start:
    "x"

screen s():
    modal True
    zorder 200
    style_prefix "confirm"
    text "hi"
''')
    assert r['props'] == {'modal': True, 'zorder': 200,
                          'style_prefix': 'confirm'}


def test_if_branch_is_chosen_by_the_store():
    src = '''
label start:
    "x"

default mood = "happy"

screen s():
    if mood == "happy":
        text "glad"
    else:
        text "sad"
'''
    assert _render(src)['widgets'][0]['text'] == 'glad'
    assert _render(src, store={'mood': 'sad'})['widgets'][0]['text'] == 'sad'


def test_for_expands_over_a_collection():
    r = _render('''
label start:
    "x"

screen s():
    vbox:
        for n in names:
            textbutton n
''', scope={'names': ['Ann', 'Bob', 'Cid']})
    labels = [w['text'] for w in r['widgets'][0]['children']]
    assert labels == ['Ann', 'Bob', 'Cid']


def test_default_param_applies_when_no_argument_is_given():
    src = '''
label start:
    "x"

screen s(greeting="Hi"):
    text greeting
'''
    script = parse_string(src, mode='full')
    state = VNState()
    interp = VNInterpreter(script, state)
    sl = ScreenLang(screens=script['screens'],
                    evaluator=interp._eval_screen_expr)
    assert sl.render('s')['widgets'][0]['text'] == 'Hi'
    assert sl.render('s', ['"Yo"'])['widgets'][0]['text'] == 'Yo'


def test_use_inlines_another_screen():
    r = _render('''
label start:
    "x"

screen button_row():
    hbox:
        textbutton "One"
        textbutton "Two"

screen s():
    frame:
        use button_row()
''')
    frame = r['widgets'][0]
    hbox = frame['children'][0]
    assert hbox['kind'] == 'hbox'
    assert [w['text'] for w in hbox['children']] == ['One', 'Two']


def test_transclude_inserts_the_use_block():
    r = _render('''
label start:
    "x"

screen wrapper():
    frame:
        vbox:
            transclude

screen s():
    use wrapper():
        text "inside"
''')
    assert r['errors'] == []
    frame = r['widgets'][0]
    vbox = frame['children'][0]
    assert [w['text'] for w in vbox['children']] == ['inside']


def test_dollar_line_runs_and_can_feed_the_screen():
    r = _render('''
label start:
    "x"

screen s():
    $ total = 2 + 3
    text "total is [total]"
''')
    assert r['errors'] == []
    assert r['widgets'][0]['text'] == 'total is 5'


def test_keyword_arguments_bind_by_name():
    # `show screen hud(score=gold)` must bind `score`, not the literal text
    src = (
        'label start:\n'
        '    "x"\n'
        '\n'
        'default gold = 7\n'
        '\n'
        'screen hud(score=0):\n'
        '    text "Gold: [score]"\n'
    )
    script = parse_string(src, mode='full')
    state = VNState()
    state.variables['gold'] = 7
    interp = VNInterpreter(script, state)
    sl = ScreenLang(screens=script['screens'],
                    evaluator=interp._eval_screen_expr)
    assert sl.render('hud', ['score=gold'])['widgets'][0]['text'] == 'Gold: 7'


def test_use_passes_arguments_without_the_screen_name():
    # `use panel("Status")` must pass "Status", not the token `panel("Status")`
    r = _render('''
label start:
    "x"

screen panel(title):
    frame:
        label title
        transclude

screen s():
    use panel("Status"):
        text "inner"
''')
    frame = r['widgets'][0]
    label, text = frame['children']
    assert label['text'] == 'Status'
    assert text['text'] == 'inner'


def test_comparison_is_not_mistaken_for_a_keyword_argument():
    from engine.ui.screen_lang import split_call_args
    positional, kwargs = split_call_args(['"a"', 'x==y', 'n=3', '"k=v"'])
    assert positional == ['"a"', 'x==y', '"k=v"']
    assert kwargs == {'n': '3'}


def test_undefined_screen_degrades_instead_of_raising():
    script = parse_string('label start:\n    "x"\n', mode='full')
    sl = ScreenLang(screens=script['screens'])
    r = sl.render('nope')
    assert r['widgets'] == []
    assert r['errors'] and 'not defined' in r['errors'][0]


def test_use_of_undefined_screen_is_a_diagnostic():
    r = _render('''
label start:
    "x"

screen s():
    use missing_screen()
''')
    assert r['widgets'] == []
    assert any('undefined screen' in e for e in r['errors'])


def test_unresolvable_condition_is_reported_not_fatal():
    script = parse_string('''
label start:
    "x"

screen s():
    if totally_unknown_thing:
        text "never"
    text "always"
''', mode='full')
    # no evaluator at all: every expression misses
    sl = ScreenLang(screens=script['screens'])
    r = sl.render('s')
    assert any('cannot evaluate condition' in e for e in r['errors'])
    assert [w['text'] for w in r['widgets']] == ['always']


# ---------------------------------------------------------------- wiring
def _run(src):
    script = parse_string(src, mode='full')
    interp = VNInterpreter(script, VNState())
    return interp, interp.run_headless()


SCREEN_SCRIPT = '''
define e = Character("Eileen")

screen greeting(who):
    vbox:
        text "Hello, [who]!"
        textbutton "Wave" action Return("wave")

label start:
    e "Hi."
    show screen greeting("Eileen")
    e "Mid."
    hide screen greeting
    e "Bye."
'''


def test_show_screen_event_carries_widgets():
    _, trace = _run(SCREEN_SCRIPT)
    ev = next(e for e in trace if e['type'] == 'show_screen')
    assert ev['screen'] == 'greeting'
    assert ev['errors'] == []
    vbox = ev['widgets'][0]
    assert [w['text'] for w in vbox['children']] == ['Hello, Eileen!', 'Wave']


def test_show_screen_registers_in_state_and_hide_clears_it():
    interp, trace = _run(SCREEN_SCRIPT)
    shown = next(e for e in trace if e['type'] == 'show_screen')
    assert shown['screen'] in ('greeting',)
    # after the whole run the `hide screen` has removed it again
    assert interp.state.active_screens == {}
    assert any(e['type'] == 'hide_screen' for e in trace)


def test_show_screen_state_is_serialisable():
    import json
    src = '''
screen note():
    text "remember"

label start:
    show screen note()
    "end"
'''
    interp, _ = _run(src)
    assert 'note' in interp.state.active_screens
    # a save must round-trip: no non-JSON values may leak into state
    json.dumps(interp.state.active_screens)


def test_call_screen_is_modal_and_yields_widgets():
    src = '''
screen pick():
    vbox:
        textbutton "A" action Return("a")
        textbutton "B" action Return("b")

label start:
    call screen pick()
    "done"
'''
    _, trace = _run(src)
    ev = next(e for e in trace if e['type'] == 'call_screen')
    assert ev['wait'] is True
    vbox = ev['widgets'][0]
    assert [w['text'] for w in vbox['children']] == ['A', 'B']
    assert [w['props']['action'] for w in vbox['children']] == [
        'Return("a")', 'Return("b")']


def test_show_screen_of_unknown_screen_does_not_break_the_story():
    src = '''
label start:
    show screen does_not_exist()
    "still playing"
'''
    _, trace = _run(src)
    ev = next(e for e in trace if e['type'] == 'show_screen')
    assert ev['widgets'] == []
    assert ev['errors']
    says = [e['text'] for e in trace if e['type'] == 'say']
    assert says == ['still playing']


def test_screen_state_survives_a_save_round_trip():
    import json
    src = '''
screen hud():
    text "hud"

label start:
    show screen hud()
    "x"
'''
    interp, _ = _run(src)
    restored = VNState.from_json(interp.state.to_json())
    assert 'hud' in restored.active_screens
    assert restored.active_screens['hud']['widgets'][0]['text'] == 'hud'
