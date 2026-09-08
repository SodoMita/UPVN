"""
M19 — drop-in Ren'Py compatibility tests.

Everything here is verified without any external corpus: each construct that
real Ren'Py projects use (and that the LearnToCodeRPG corpus exercise drove
into the parser) gets a parse test and, where it produces events, a headless
run test.

The corpus itself is covered by tests/test_renpy_corpus.py (skipped when the
checkout is absent).
"""
import pytest

from engine.core.vn_controller import VNController
from engine.core.vn_errors import ParseError, ScriptRuntimeError
from engine.core.vn_interpreter import VNInterpreter
from engine.script.expr_eval import evaluate
from engine.script.lexer import group_logical_lines
from engine.script.parser import parse_string, parse_string_full
from engine.script.renpy_compat import (
    PermissiveEnv,
    RenpyNoOp,
    StoreNamespace,
    identity_translation,
)


def run(script: str, choices=None):
    d = parse_string_full(script)
    return VNInterpreter(d).run_headless(choices=choices or [])


# ------------------------------------------------------------------ lexer
def test_triple_quoted_string_spans_lines():
    lines = group_logical_lines('define about = _p("""\nline one\nline two\n""")\n')
    assert len(lines) == 1
    assert lines[0].text.startswith('define about = _p("""')
    assert "line one\nline two" in lines[0].text


def test_backslash_continuation_joins_without_newline():
    lines = group_logical_lines("$ total = 1 + \\\n    2\n")
    assert len(lines) == 1
    assert lines[0].text == "$ total = 1 +     2"


def test_unbalanced_brackets_continue_the_logical_line():
    lines = group_logical_lines('call screen confirm(\n    "Save?",\n    yes_action=Return(True),\n)\n')
    assert len(lines) == 1
    assert lines[0].text.count("\n") == 0
    assert "yes_action=Return(True)" in lines[0].text


def test_hash_inside_string_is_not_a_comment():
    lines = group_logical_lines('define gui.accent = u\'#002ead\' # dark blue\n')
    assert len(lines) == 1
    assert "#002ead" in lines[0].text
    assert "dark blue" not in lines[0].text


def test_bom_is_stripped_anywhere():
    lines = group_logical_lines('\ufefflabel start:\n    "hi"\n\ufefflabel two:\n    "yo"\n')
    assert [ln.text for ln in lines] == ['label start:', '"hi"', 'label two:', '"yo"']


def test_unterminated_triple_quote_reports_a_friendly_error():
    with pytest.raises(ParseError) as ei:
        group_logical_lines('define x = """\nnever closed\n')
    assert "triple-quoted" in str(ei.value)


# ------------------------------------------------------------------ parser: full tier
def test_from_clauses_are_parsed_and_recorded():
    d = parse_string_full(
        'label start:\n'
        '    call other from _call_other_3\n'
        '    jump away from _jump_away_4\n'
        '    from _start_1\n'
        'label other:\n    "x"\n'
        'label away:\n    "y"\n'
    )
    kinds = [n["cmd"] for n in d["labels"]["start"]]
    assert kinds == ["call", "jump", "from_clause"]
    assert d["labels"]["start"][0]["from_id"] == "_call_other_3"
    assert len(d["from_clauses"]) == 3


def test_call_screen_with_arguments_and_transition():
    d = parse_string_full('label start:\n    call screen quiz(answer=1, hard=True) with dissolve\n')
    node = d["labels"]["start"][0]
    assert node["cmd"] == "call_screen"
    assert node["screen"] == "quiz"
    assert node["args"] == ["answer=1", "hard=True"]
    assert node["transition"] == "dissolve"


def test_show_and_hide_screen_with_arguments():
    d = parse_string_full(
        'label start:\n    show screen hud(score=3)\n    hide screen hud\n')
    kinds = [n["cmd"] for n in d["labels"]["start"]]
    assert kinds == ["show_screen", "hide_screen"]
    assert d["labels"]["start"][0]["args"] == ["score=3"]


def test_for_loop_parses_with_body():
    d = parse_string_full(
        'label start:\n'
        '    for item in items:\n'
        '        "got [item]"\n'
    )
    node = d["labels"]["start"][0]
    assert node["cmd"] == "for"
    assert node["target"] == "item"
    assert node["iter"] == "items"
    assert node["block"][0]["cmd"] == "say"


def test_voice_attribute_say():
    d = parse_string_full('label start:\n    player @ surprised "Oh!"\n')
    node = d["labels"]["start"][0]
    assert node["who"] == "player"
    assert node["voice_attr"] == "surprised"
    assert node["text"] == "Oh!"


def test_negative_image_attribute_say():
    d = parse_string_full('label start:\n    player -sweat neutral "Better."\n')
    node = d["labels"]["start"][0]
    assert node["who"] == "player"
    assert node["expression"] == "-sweat neutral"


def test_say_with_nointeract_and_attributes():
    d = parse_string_full('label start:\n    e happy smile "Hi" nointeract\n')
    node = d["labels"]["start"][0]
    assert node["expression"] == "happy smile"
    assert node["nointeract"] is True


def test_extend_and_centered():
    d = parse_string_full('label start:\n    extend "more"\n    centered "TITLE"\n    vcentered "MID"\n')
    nodes = d["labels"]["start"]
    assert nodes[0]["extend"] is True and nodes[0]["text"] == "more"
    assert nodes[1]["centered"] == "centered"
    assert nodes[2]["centered"] == "vcentered"


def test_with_accepts_expressions():
    d = parse_string_full(
        'label start:\n'
        '    scene bg room with Dissolve(0.5)\n'
        '    show e happy at left, right with hp8\n'
        '    with None\n'
    )
    scene, show, with_node = d["labels"]["start"]
    assert scene["transition"] == "Dissolve(0.5)"
    assert show["position"] == "left, right"
    assert show["transition"] == "hp8"
    assert show["asset"] == "e happy"
    assert with_node["transition"] == "None"


def test_show_clauses_as_behind_zorder_onlayer():
    d = parse_string_full('label start:\n    show expression "x.png" as fx behind e zorder 5 onlayer master\n')
    node = d["labels"]["start"][0]
    assert node["as_tag"] == "fx"
    assert node["behind"] == "e"
    assert node["zorder"] == "5"
    assert node["layer"] == "master"


def test_pause_variants():
    d = parse_string_full('label start:\n    pause\n    pause 1.5\n    pause delay\n    pause 2.0 with fade\n')
    nodes = d["labels"]["start"]
    assert nodes[0]["duration"] is None
    assert nodes[1]["duration"] == 1.5
    assert nodes[2]["duration"] == "delay"      # expression, evaluated at runtime
    assert nodes[3]["duration"] == 2.0 and nodes[3]["transition"] == "fade"


def test_audio_statements_with_every_option():
    d = parse_string_full(
        'label start:\n'
        '    play music ["a.ogg", "b.ogg"] fadein 1.0 loop\n'
        '    queue music "c.ogg"\n'
        '    stop sound fadeout 2.0\n'
        '    play audio "d.ogg"\n'
        '    voice sustain\n'
    )
    nodes = d["labels"]["start"]
    assert nodes[0]["cmd"] == "play_music" and nodes[0]["fadein"] == 1.0 and nodes[0]["loop"] is True
    assert nodes[0]["asset"] == '["a.ogg", "b.ogg"]'
    assert nodes[1]["queue"] is True
    assert nodes[2]["cmd"] == "stop_sound" and nodes[2]["fadeout"] == 2.0
    assert nodes[3]["cmd"] == "play_audio"
    assert nodes[4]["cmd"] == "voice_sustain"


def test_named_menu_is_a_jump_target():
    d = parse_string_full(
        'label start:\n'
        '    menu day_choices:\n'
        '        set visited\n'
        '        "Study":\n'
        '            jump study\n'
        '        "Rest":\n'
        '            jump rest\n'
        'label study:\n    "s"\n'
        'label rest:\n    "r"\n'
    )
    assert "day_choices" in d["labels"]
    menu = d["labels"]["start"][0]
    assert menu["name"] == "day_choices"
    assert menu["set"] == "visited"
    assert [c["text"] for c in menu["choices"]] == ["Study", "Rest"]


def test_menu_conditional_groups_flatten_into_conditions():
    d = parse_string_full(
        'label start:\n'
        '    menu:\n'
        '        "Always":\n'
        '            jump a\n'
        '        if flag:\n'
        '            "Sometimes":\n'
        '                jump b\n'
        '        else:\n'
        '            "Never":\n'
        '                jump c\n'
        'label a:\n    "a"\nlabel b:\n    "b"\nlabel c:\n    "c"\n'
    )
    conds = [c["cond"] for c in d["labels"]["start"][0]["choices"]]
    assert conds[0] is None
    assert conds[1] == "(flag)"
    assert conds[2] == "not (flag)"


def test_menu_caption_and_dialogue_before_choices():
    d = parse_string_full(
        'label start:\n'
        '    menu:\n'
        '        "What now?"\n'
        '        e "Think about it."\n'
        '        "This":\n'
        '            jump a\n'
        'label a:\n    "a"\n'
    )
    menu = d["labels"]["start"][0]
    assert menu["caption"] == "What now?"
    assert menu["pre"][0]["cmd"] == "say"
    assert menu["pre"][0]["who"] == "e"


def test_choice_text_may_contain_the_word_if():
    d = parse_string_full(
        'label start:\n'
        '    menu:\n'
        '        "But it\'s a loss if people don\'t know!":\n'
        '            jump a\n'
        'label a:\n    "a"\n'
    )
    choice = d["labels"]["start"][0]["choices"][0]
    assert choice["text"] == "But it's a loss if people don't know!"
    assert choice["cond"] is None


def test_choice_with_condition_and_inline_props():
    d = parse_string_full(
        'label start:\n'
        '    menu:\n'
        '        "Go" (icon="arrow") if gold > 3:\n'
        '            jump a\n'
        'label a:\n    "a"\n'
    )
    menu = d["labels"]["start"][0]
    assert menu["choices"][0]["text"] == "Go"
    assert menu["choices"][0]["cond"] == "(gold > 3)"


def test_set_and_python_before_choices():
    d = parse_string_full(
        'label start:\n'
        '    menu:\n'
        '        $ asked = True\n'
        '        "Go":\n'
        '            jump a\n'
        'label a:\n    "a"\n'
    )
    assert d["labels"]["start"][0]["pre"][0]["cmd"] == "assign"


def test_default_may_be_an_expression_in_full_tier():
    d = parse_string_full('default stats = PlayerStats()\nlabel start:\n    "hi"\n')
    assert "stats" not in d["defaults"]
    assert d["init_python"] == ["stats = PlayerStats()"]


def test_default_inside_a_label_is_collected():
    d = parse_string_full(
        'label start:\n    default visited = False\n    "hi"\n')
    assert d["defaults"]["visited"] is False
    assert [n["cmd"] for n in d["labels"]["start"]] == ["say"]


def test_dotted_default_and_define_become_namespaces():
    d = parse_string_full(
        'default preferences.text_cps = 60\n'
        'define gui.accent_color = "#002ead"\n'
        'label start:\n    "hi"\n')
    assert d["defines"]["preferences.text_cps"] == "60"
    assert d["defines"]["gui.accent_color"] == "#002ead"


def test_image_definitions_and_blocks():
    d = parse_string_full(
        'image bg club = "images/club.png"\n'
        'image finale = im.Data(base64.b64decode("""\nAAAA\n"""))\n'
        'layeredimage player:\n'
        '    attribute neutral default null\n'
        '    group eyes auto prefix "eyes"\n'
        'label start:\n    "hi"\n')
    assert d["assets"]["images"]["bg club"] == "images/club.png"
    assert "finale" in d["assets"]["images"]
    assert "player" in d["image_blocks"]
    assert d["image_blocks"]["player"]["lines"][0].startswith("attribute neutral")


def test_style_statements_and_blocks():
    d = parse_string_full(
        'style default:\n'
        '    font "DejaVuSans.ttf"\n'
        'style.button.text.color = "#fff"\n'
        'style.button hover_background "#000"\n'
        'label start:\n    "hi"\n')
    assert "default" in d["styles"]
    assert d["styles"]["button.text.color"]["value"] == '"#fff"'
    assert d["styles"]["button"]["property"] == "hover_background"


def test_init_python_variants_and_early():
    d = parse_string_full(
        'init offset = -2\n'
        'init python hide:\n'
        '    x = 1\n'
        'python early:\n'
        '    y = 2\n'
        'label start:\n    "hi"\n')
    assert d["init_python"] == ["x = 1", "y = 2"]


def test_screen_and_transform_with_parameters():
    d = parse_string_full(
        'screen say(who, what) tag dialogue modal True:\n'
        '    text who\n'
        'transform delayed_blink(delay, cycle):\n'
        '    alpha 0.0\n'
        'label start:\n    "hi"\n')
    assert "say" in d["screens"]
    assert "delayed_blink" in d["transforms"]


def test_multiline_character_define():
    d = parse_string_full(
        'define credits = _p("""\n'
        'Character Art:\n'
        '    Someone (Nice Person)\n'
        '""")\n'
        'label start:\n    "hi"\n')
    assert "credits" in d["defines"]


def test_full_tier_accepts_any_consistent_indent():
    d = parse_string_full('label start:\n  "two spaces"\n  if True:\n    "nested"\n')
    assert [n["cmd"] for n in d["labels"]["start"]] == ["say", "if"]


def test_safe_tier_still_demands_four_spaces():
    with pytest.raises(ParseError) as ei:
        parse_string('label start:\n  "two spaces"\n')
    assert "expected 4 spaces" in str(ei.value)


def test_safe_tier_still_rejects_drop_in_constructs():
    for src, hint in (
        ('label start:\n    for x in y:\n        "a"\n', "full .rpy tier"),
        ('label start:\n    call screen foo(1)\n', "full .rpy tier"),
        ('label start:\n    python:\n        x = 1\n', "full .rpy tier"),
        ('default a.b = 1\nlabel start:\n    "x"\n', "full .rpy tier"),
    ):
        with pytest.raises(ParseError) as ei:
            parse_string(src)
        assert hint in str(ei.value), src


def test_require_start_false_for_multi_file_games():
    d = parse_string_full('label helper:\n    "no start here"\n', require_start=False)
    assert "helper" in d["labels"]
    with pytest.raises(ParseError) as ei:
        parse_string_full('label helper:\n    "no start here"\n')
    assert "start" in str(ei.value)


def test_label_with_params_hide_and_nohide():
    d = parse_string_full('label chapter(n, name="x") hide:\n    "hi"\n', require_start=False)
    assert d["label_params"]["chapter"][0]["name"] == "n"
    assert d["label_params"]["chapter"][1]["default"] == '"x"'


# ------------------------------------------------------------------ interpreter
def test_for_loop_runs_each_item():
    trace = run(
        'default items = ["a", "b", "c"]\n'
        'label start:\n'
        '    for item in items:\n'
        '        "got [item]"\n'
        '    "done"\n')
    texts = [e["text"] for e in trace if e["type"] == "say"]
    assert texts == ["got a", "got b", "got c", "done"]


def test_for_loop_tuple_target():
    trace = run(
        'default pairs = [["k1", 1], ["k2", 2]]\n'
        'label start:\n'
        '    for k, v in pairs:\n'
        '        "[k]=[v]"\n')
    assert [e["text"] for e in trace if e["type"] == "say"] == ["k1=1", "k2=2"]


def test_for_loop_break_and_continue():
    trace = run(
        'default items = [1, 2, 3, 4]\n'
        'label start:\n'
        '    for n in items:\n'
        '        if n == 2:\n'
        '            continue\n'
        '        if n == 4:\n'
        '            break\n'
        '        "n=[n]"\n'
        '    "end"\n')
    texts = [e["text"] for e in trace if e["type"] == "say"]
    assert texts == ["n=1", "n=3", "end"]


def test_from_clause_is_a_no_op():
    trace = run('label start:\n    from _start_1\n    "hi"\n')
    assert [e["type"] for e in trace if e["type"] != "end"] == ["say"]


def test_menu_pre_statements_run_before_the_choices():
    trace = run(
        'default asked = False\n'
        'label start:\n'
        '    menu:\n'
        '        $ asked = True\n'
        '        "Go":\n'
        '            "went"\n'
        'label after:\n    "a"\n',
        choices=[0])
    kinds = [e["type"] for e in trace]
    assert kinds.index("assign") < kinds.index("menu")
    assert "went" in [e.get("text") for e in trace]


def test_named_menu_can_be_jumped_to():
    trace = run(
        'label start:\n'
        '    jump pick\n'
        'label pick:\n'
        '    menu pick:\n'
        '        "One":\n'
        '            "chose one"\n'
        '        "Two":\n'
        '            "chose two"\n',
        choices=[1])
    assert "chose two" in [e.get("text") for e in trace if e["type"] == "say"]


def test_call_screen_event_carries_arguments():
    trace = run('label start:\n    call screen quiz(a=1)\n')
    ev = [e for e in trace if e["type"] == "call_screen"][0]
    assert ev["args"] == ["a=1"]


def test_pause_expression_is_evaluated():
    trace = run('default delay = 2.5\nlabel start:\n    pause delay\n')
    assert [e for e in trace if e["type"] == "pause"][0]["duration"] == 2.5


def test_say_extras_reach_the_event():
    trace = run('label start:\n    e happy "Hi" nointeract\n    extend "!"\n    centered "T"\n    voice sustain\n')
    say, ext, cen, vs = [e for e in trace if e["type"] in ("say", "voice_sustain")]
    assert say["expression"] == "happy" and say["wait"] is False
    assert ext["extend"] is True
    assert cen["centered"] == "centered"
    assert vs["type"] == "voice_sustain"


def test_stop_sound_clears_the_channel():
    trace = run('label start:\n    play sound "a.ogg"\n    stop sound\n')
    kinds = [e["type"] for e in trace if e["type"] != "end"]
    assert kinds == ["play_sound", "stop_sound"]


def test_unknown_identifier_in_full_tier_condition_is_forgiven():
    trace = run('label start:\n    if totally_unknown_flag:\n        "yes"\n    else:\n        "no"\n')
    assert [e["text"] for e in trace if e["type"] == "say"] == ["no"]


def test_python_block_error_is_fatal_without_compat():
    d = parse_string_full('label start:\n    python:\n        undefined_thing()\n    "hi"\n')
    with pytest.raises(ScriptRuntimeError):
        VNInterpreter(d).run_headless()


def test_compat_mode_collects_python_errors_and_continues():
    d = parse_string_full(
        'label start:\n'
        '    python:\n'
        '        boom = 1 / 0\n'
        '    "still running"\n')
    interp = VNInterpreter(d, compat=True)
    trace = interp.run_headless()
    assert "still running" in [e.get("text") for e in trace if e["type"] == "say"]
    assert len(interp.python_errors) == 1


def test_namespaces_built_from_dotted_defines():
    d = parse_string_full(
        'define gui.accent_color = "#002ead"\n'
        'define config.window_title = "Demo"\n'
        'label start:\n'
        '    python:\n'
        '        store.seen_accent = gui.accent_color\n'
        '        gui.init(1920, 1080)\n'
        '    "ok"\n')
    interp = VNInterpreter(d)
    interp.run_headless()
    assert interp.namespaces["gui"].accent_color == "#002ead"
    assert interp.state.variables["seen_accent"] == "#002ead"


def test_translation_helper_is_available():
    d = parse_string_full(
        'label start:\n'
        '    python:\n'
        '        store.msg = _("Hello")\n'
        '    "ok"\n')
    interp = VNInterpreter(d)
    interp.run_headless()
    assert interp.state.variables["msg"] == "Hello"


# ------------------------------------------------------------------ expression sandbox
def test_loose_mode_returns_none_for_unknown_names():
    assert evaluate("nope", {}, loose=True) is None
    assert evaluate("gui.accent", {}, loose=True) is None
    assert evaluate("some_fn(1)", {}, loose=True) is None


def test_strict_mode_still_raises_for_unknown_names():
    with pytest.raises(ScriptRuntimeError):
        evaluate("nope", {})


def test_loose_mode_supports_comprehensions_and_kwargs():
    assert evaluate("[x * 2 for x in items]", {"items": [1, 2]}, loose=True) == [2, 4]
    assert evaluate("any(x > 1 for x in items)", {"items": [1, 2]}, loose=True) is True
    assert evaluate('fn(a=1)', {"fn": lambda a: a + 1}, loose=True) == 2


def test_sandbox_escape_is_blocked_in_both_modes():
    payload = "().__class__.__mro__[1].__subclasses__()"
    for loose in (False, True):
        with pytest.raises(ScriptRuntimeError):
            evaluate(payload, {}, loose=loose)
    with pytest.raises(ScriptRuntimeError):
        evaluate("x.__class__", {"x": 1}, loose=True)


def test_loose_comparison_with_none_degrades_to_false():
    assert evaluate("needle in unknown_list", {}, loose=True) is False


# ------------------------------------------------------------------ renpy compat objects
def test_renpy_noop_is_callable_subscriptable_and_a_base_class():
    noop = RenpyNoOp("renpy.display.layout.DynamicDisplayable")
    assert noop(1, 2, x=3) is None
    assert noop["k"] is None
    noop["k"] = 1                       # must not raise

    class Child(noop):                  # __mro_entries__ makes this legal
        pass

    assert isinstance(Child(), object)


def test_renpy_noop_blocks_private_names():
    noop = RenpyNoOp("renpy.x")
    with pytest.raises(AttributeError):
        noop._private
    with pytest.raises(AttributeError):
        getattr(noop, "__subclasses__")


def test_store_namespace_holds_values_and_forgives_unknowns():
    ns = StoreNamespace("gui", {"accent": "#fff"}, permissive=True)
    assert ns.accent == "#fff"
    ns.size = 24
    assert ns.size == 24
    assert ns.init(1, 2) is None        # permissive no-op
    strict = StoreNamespace("gui", permissive=False)
    with pytest.raises(AttributeError):
        strict.nope


def test_permissive_env_resolves_unknown_globals():
    env = PermissiveEnv()
    assert env["MusicRoom"](fadeout=1) is None
    assert env.missing_log == ["MusicRoom"]
    with pytest.raises(KeyError):
        env["__import__"]


def test_identity_translation():
    assert identity_translation("Save?") == "Save?"
    assert identity_translation() == ""


# ------------------------------------------------------------------ multi-file loading
def test_directory_project_merges_and_runs(tmp_path):
    (tmp_path / "chars.rpy").write_text(
        'define e = Character("Eileen")\n', encoding="utf-8")
    (tmp_path / "story.rpy").write_text(
        'label start:\n    e "Hello from another file"\n    call helper from _call_helper\n'
        'label helper:\n    e "helper line"\n', encoding="utf-8")
    controller = VNController(script_path=tmp_path, mode="full")
    controller.load()
    assert set(controller.script_dict["labels"]) >= {"start", "helper"}
    trace = controller.interp.run_headless()
    texts = [e["text"] for e in trace if e["type"] == "say"]
    assert texts == ["Hello from another file", "helper line"]


def test_directory_without_start_reports_a_friendly_error(tmp_path):
    (tmp_path / "chars.rpy").write_text('define e = Character("E")\n', encoding="utf-8")
    controller = VNController(script_path=tmp_path, mode="full")
    with pytest.raises(ParseError) as ei:
        controller.load()
    assert "start" in str(ei.value)


# ------------------------------------------------------------------ example project
EXAMPLE = "examples/14_renpy_dropin"


def test_example_14_directory_parses_and_runs():
    controller = VNController(script_path=EXAMPLE, mode="full")
    controller.load()
    assert set(controller.script_dict["labels"]) >= {
        "start", "intro", "pick_route", "coffee", "study", "rest"}
    # the named menu is registered as a jump target too
    assert "pick_route" in controller.script_dict["labels"]
    trace = controller.interp.run_headless(choices=[0])
    texts = [e.get("text", "") for e in trace if e["type"] == "say"]
    assert "Hi Sam! Ready to test the drop-in tier?" in texts
    assert "Route option: explore" in texts          # for-loop over a store list
    assert "THE END" in texts


def test_example_14_conditional_choice_group_is_filtered():
    controller = VNController(script_path=EXAMPLE, mode="full")
    controller.load()
    trace = controller.interp.run_headless(choices=[1])     # coffee branch
    menu = [e for e in trace if e["type"] == "menu"][0]
    assert [c["text"] for c in menu["choices"]] == [
        "Study in the library.", "Buy a coffee first."]      # `else:` branch hidden
    call = [e for e in trace if e["type"] == "call_screen"][0]
    assert call["screen"] == "confirm" and len(call["args"]) == 2


def test_example_14_rejects_the_safe_tier():
    with pytest.raises(ParseError):
        parse_string(open(f"{EXAMPLE}/script.rpy", encoding="utf-8").read())
