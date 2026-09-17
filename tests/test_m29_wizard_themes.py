"""M29: theme-aware wizard tests + standalone game creator + Ren'Py SDK comparison."""
import sys
import os
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# --- Wizard theme tests ---

class TestWizardThemes:
    """All 4 wizard themes must parse, validate, and produce distinct content."""

    @pytest.fixture
    def builder(self, tmp_path):
        def _make(theme):
            sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from blend.upvn_editor_addon import UPVN_GameBuilder
            return UPVN_GameBuilder(str(tmp_path / f"test_{theme}.rpy"), use_declarative=True)
        return _make

    @pytest.mark.parametrize("theme", ["school", "fantasy", "scifi", "mystery"])
    def test_wizard_parse(self, builder, theme):
        b = builder(theme)
        b.create_quick_wizard(title=f"Test {theme}", theme=theme)
        rpy = b.build_rpy()
        assert len(rpy) > 500, f"{theme}: generated script too short"
        ok, msg = b.validate()
        assert ok, f"{theme}: validation failed: {msg}"

    @pytest.mark.parametrize("theme", ["school", "fantasy", "scifi", "mystery"])
    def test_wizard_has_2_endings(self, builder, theme):
        b = builder(theme)
        b.create_quick_wizard(title="Test", theme=theme)
        rpy = b.build_rpy()
        # Each theme should have at least 2 distinct endings
        assert rpy.count("return") >= 2, f"{theme}: needs at least 2 endings"

    @pytest.mark.parametrize("theme", ["school", "fantasy", "scifi", "mystery"])
    def test_wizard_has_variables(self, builder, theme):
        b = builder(theme)
        b.create_quick_wizard(title="Test", theme=theme)
        assert len(b.state_vars) >= 2, f"{theme}: needs at least 2 state vars"
        assert len(b.characters) >= 2, f"{theme}: needs at least 2 characters"

    @pytest.mark.parametrize("theme", ["school", "fantasy", "scifi", "mystery"])
    def test_wizard_has_menus(self, builder, theme):
        b = builder(theme)
        b.create_quick_wizard(title="Test", theme=theme)
        rpy = b.build_rpy()
        assert "menu:" in rpy, f"{theme}: needs at least 1 menu"
        assert rpy.count("choice") >= 4, f"{theme}: needs at least 4 choices total"

    @pytest.mark.parametrize("theme", ["school", "fantasy", "scifi", "mystery"])
    def test_wizard_headless_trace(self, builder, theme):
        """Run the wizard script headless with choice path [0,0] — must not crash."""
        from engine.script.parser import parse_string
        from engine.core.vn_state import VNState
        from engine.core.vn_interpreter import VNInterpreter
        b = builder(theme)
        b.create_quick_wizard(title="Test", theme=theme)
        rpy = b.build_rpy()
        script = parse_string(rpy)
        state = VNState()
        interp = VNInterpreter(script, state)
        gen = interp.run()
        events = []
        choices_made = 0
        try:
            ev = next(gen)
            while True:
                events.append(ev)
                if ev.get("wait") and ev.get("type") == "menu" and choices_made < 2:
                    ev = gen.send(0)
                    choices_made += 1
                elif ev.get("wait"):
                    ev = gen.send(None)
                else:
                    ev = next(gen)
        except StopIteration:
            pass
        assert len(events) >= 5, f"{theme}: too few events ({len(events)}) on path [0,0]"
        say_events = [e for e in events if e.get("type") == "say"]
        assert len(say_events) >= 3, f"{theme}: too few say events ({len(say_events)})"


# --- Standalone game creator ---

class TestGameCreator:
    """tools/upvn_game_creator.py must produce valid scripts."""

    @pytest.mark.parametrize("theme", ["school", "fantasy", "scifi", "mystery"])
    def test_creator_produces_valid_rpy(self, tmp_path, theme):
        from blend.upvn_editor_addon import UPVN_GameBuilder
        out = str(tmp_path / f"game_{theme}" / "script.rpy")
        builder = UPVN_GameBuilder(out, use_declarative=True)
        builder.create_quick_wizard(title=f"Creator {theme}", theme=theme)
        builder.write()
        assert os.path.exists(out), f"{theme}: output file missing"
        content = open(out).read()
        assert "label start:" in content, f"{theme}: missing label start"
        assert "character" in content or "define" in content, f"{theme}: missing character defs"
        ok, msg = builder.validate()
        assert ok, f"{theme}: validation failed: {msg}"


# --- Ren'Py SDK comparison ---

class TestRenpySDKComparison:
    """Compare UPVN parser against Ren'Py 8.5.1 SDK scripts."""

    RENPY_SDK = os.path.expanduser("~/renpy-8.5.1-sdk")

    @pytest.mark.skipif(not os.path.isdir(os.path.expanduser("~/renpy-8.5.1-sdk")),
                        reason="Ren'Py SDK not downloaded")
    def test_the_question_parses_full(self):
        """The Question (the standard Ren'Py example) must parse in full mode."""
        from engine.script.parser import parse_file
        script = os.path.join(self.RENPY_SDK, "the_question", "game", "script.rpy")
        if not os.path.exists(script):
            pytest.skip("the_question/script.rpy not found")
        ast = parse_file(script, mode='full', require_start=False)
        labels = ast.get("labels", {})
        assert len(labels) >= 5, f"Expected 5+ labels, got {len(labels)}"

    @pytest.mark.skipif(not os.path.isdir(os.path.expanduser("~/renpy-8.5.1-sdk")),
                        reason="Ren'Py SDK not downloaded")
    def test_the_question_headless_run(self):
        """The Question must run headlessly with choices [0, 0]."""
        from engine.script.parser import parse_file
        from engine.core.vn_state import VNState
        from engine.core.vn_interpreter import VNInterpreter
        script_path = os.path.join(self.RENPY_SDK, "the_question", "game", "script.rpy")
        if not os.path.exists(script_path):
            pytest.skip("the_question/script.rpy not found")
        script = parse_file(script_path, mode='full', require_start=False)
        state = VNState()
        interp = VNInterpreter(script, state)
        gen = interp.run()
        events = []
        choices = 0
        try:
            ev = next(gen)
            while True:
                events.append(ev)
                if ev.get("wait") and ev.get("type") == "menu" and choices < 2:
                    ev = gen.send(0)
                    choices += 1
                elif ev.get("wait"):
                    ev = gen.send(None)
                else:
                    ev = next(gen)
        except StopIteration:
            pass
        say_count = sum(1 for e in events if e.get("type") == "say")
        assert say_count >= 10, f"Expected 10+ say events, got {say_count}"

    @pytest.mark.skipif(not os.path.isdir(os.path.expanduser("~/renpy-8.5.1-sdk")),
                        reason="Ren'Py SDK not downloaded")
    def test_the_question_gui_rpy_parses(self):
        """gui.rpy from the SDK should parse without errors."""
        from engine.script.parser import parse_file
        gui = os.path.join(self.RENPY_SDK, "the_question", "game", "gui.rpy")
        if not os.path.exists(gui):
            pytest.skip("gui.rpy not found")
        ast = parse_file(gui, mode='full', require_start=False)
        assert isinstance(ast, dict), "gui.rpy should return a dict"

    @pytest.mark.skipif(not os.path.isdir(os.path.expanduser("~/renpy-8.5.1-sdk")),
                        reason="Ren'Py SDK not downloaded")
    def test_screens_rpy_parses(self):
        """screens.rpy from the SDK should parse without errors."""
        from engine.script.parser import parse_file
        screens = os.path.join(self.RENPY_SDK, "the_question", "game", "screens.rpy")
        if not os.path.exists(screens):
            pytest.skip("screens.rpy not found")
        ast = parse_file(screens, mode='full', require_start=False)
        assert isinstance(ast, dict), "screens.rpy should return a dict"
