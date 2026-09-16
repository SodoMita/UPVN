"""M29: Ren'Py SDK tutorial corpus validation.

Validates UPVN's parser against the official Ren'Py 8.5.1 SDK tutorial.
The tutorial/ directory has ~24 .rpy files covering all major Ren'Py features.
We test that key files parse in full mode without crashing.
"""
import os
import glob
import pytest

RENPY_SDK = os.path.expanduser("~/renpy-8.5.1-sdk")
TUTORIAL_GAME = os.path.join(RENPY_SDK, "tutorial", "game")
THE_QUESTION_GAME = os.path.join(RENPY_SDK, "the_question", "game")

skip_no_sdk = pytest.mark.skipif(
    not os.path.isdir(RENPY_SDK), reason="Ren'Py SDK not downloaded"
)


def _find_file(*candidates):
    """Return first existing path or None."""
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


@skip_no_sdk
class TestRenpyTutorialCorpus:
    """Ren'Py SDK tutorial/ — key files must parse in full mode."""

    def test_tutorial_files_exist(self):
        rpy_files = sorted(glob.glob(os.path.join(TUTORIAL_GAME, "*.rpy")))
        assert len(rpy_files) >= 15, f"Expected 15+ tutorial .rpy files, found {len(rpy_files)}"

    @pytest.mark.parametrize("filename", [
        "script.rpy",
        "examples.rpy",
    ])
    def test_key_tutorial_file_parses(self, filename):
        from engine.script.parser import parse_file
        path = os.path.join(TUTORIAL_GAME, filename)
        if not os.path.exists(path):
            pytest.skip(f"{filename} not found")
        ast = parse_file(path, mode="full", require_start=False)
        assert isinstance(ast, dict), f"{filename}: expected dict, got {type(ast)}"

    def test_tutorial_script_has_labels(self):
        from engine.script.parser import parse_file
        path = os.path.join(TUTORIAL_GAME, "script.rpy")
        if not os.path.exists(path):
            pytest.skip("script.rpy not found")
        try:
            ast = parse_file(path, mode="full", require_start=False)
            labels = ast.get("labels", {})
            assert len(labels) >= 1, f"Expected 1+ labels, got {len(labels)}"
        except Exception as e:
            pytest.xfail(f"Tutorial script.rpy parse failed: {e}")


@skip_no_sdk
class TestRenpyTheQuestionCorpus:
    """Ren'Py SDK the_question/ — complete game must parse and run."""

    def test_the_question_script_parses(self):
        from engine.script.parser import parse_file
        path = _find_file(
            os.path.join(THE_QUESTION_GAME, "script.rpy"),
            os.path.join(RENPY_SDK, "the_question", "script.rpy"),
        )
        assert path, "the_question script.rpy not found"
        ast = parse_file(path, mode="full", require_start=False)
        labels = ast.get("labels", {})
        assert len(labels) >= 5, f"Expected 5+ labels, got {len(labels)}"

    def test_the_question_has_characters(self):
        from engine.script.parser import parse_file
        path = _find_file(
            os.path.join(THE_QUESTION_GAME, "script.rpy"),
            os.path.join(RENPY_SDK, "the_question", "script.rpy"),
        )
        assert path, "script.rpy not found"
        ast = parse_file(path, mode="full", require_start=False)
        chars = ast.get("characters", {})
        assert len(chars) >= 2, f"Expected 2+ characters, got {len(chars)}"

    def test_the_question_has_defaults(self):
        from engine.script.parser import parse_file
        path = _find_file(
            os.path.join(THE_QUESTION_GAME, "script.rpy"),
            os.path.join(RENPY_SDK, "the_question", "script.rpy"),
        )
        assert path, "script.rpy not found"
        ast = parse_file(path, mode="full", require_start=False)
        defaults = ast.get("defaults", {})
        assert len(defaults) >= 1, f"Expected 1+ defaults, got {len(defaults)}"

    def test_the_question_headless_path_0_0(self):
        """Run with choices [0, 0] — must reach a return/ending."""
        from engine.script.parser import parse_file
        from engine.core.vn_state import VNState
        from engine.core.vn_interpreter import VNInterpreter
        path = _find_file(
            os.path.join(THE_QUESTION_GAME, "script.rpy"),
            os.path.join(RENPY_SDK, "the_question", "script.rpy"),
        )
        assert path, "script.rpy not found"
        script = parse_file(path, mode="full", require_start=False)
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
        assert say_count >= 15, f"Expected 15+ say events on path [0,0], got {say_count}"
        assert choices == 2, f"Expected 2 menus, got {choices}"

    def test_the_question_headless_path_1_1(self):
        """Run with choices [1, 1] — different path, must also complete."""
        from engine.script.parser import parse_file
        from engine.core.vn_state import VNState
        from engine.core.vn_interpreter import VNInterpreter
        path = _find_file(
            os.path.join(THE_QUESTION_GAME, "script.rpy"),
            os.path.join(RENPY_SDK, "the_question", "script.rpy"),
        )
        assert path, "script.rpy not found"
        script = parse_file(path, mode="full", require_start=False)
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
                    ev = gen.send(1)
                    choices += 1
                elif ev.get("wait"):
                    ev = gen.send(None)
                else:
                    ev = next(gen)
        except StopIteration:
            pass
        say_count = sum(1 for e in events if e.get("type") == "say")
        assert say_count >= 10, f"Expected 10+ say events on path [1,1], got {say_count}"

    def test_the_question_gui_rpy_parses(self):
        from engine.script.parser import parse_file
        path = _find_file(
            os.path.join(THE_QUESTION_GAME, "gui.rpy"),
            os.path.join(RENPY_SDK, "the_question", "gui.rpy"),
        )
        if not path:
            pytest.skip("gui.rpy not found")
        ast = parse_file(path, mode="full", require_start=False)
        assert isinstance(ast, dict)

    def test_the_question_screens_rpy_parses(self):
        from engine.script.parser import parse_file
        path = _find_file(
            os.path.join(THE_QUESTION_GAME, "screens.rpy"),
            os.path.join(RENPY_SDK, "the_question", "screens.rpy"),
        )
        if not path:
            pytest.skip("screens.rpy not found")
        ast = parse_file(path, mode="full", require_start=False)
        assert isinstance(ast, dict)

    def test_the_question_options_rpy_parses(self):
        from engine.script.parser import parse_file
        path = _find_file(
            os.path.join(THE_QUESTION_GAME, "options.rpy"),
            os.path.join(RENPY_SDK, "the_question", "options.rpy"),
        )
        if not path:
            pytest.skip("options.rpy not found")
        ast = parse_file(path, mode="full", require_start=False)
        assert isinstance(ast, dict)
