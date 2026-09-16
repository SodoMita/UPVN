"""M29: Ren'Py SDK projects runnable from their original location.

These tests verify that UPVN can parse and run the official Ren'Py 8.5.1 SDK
projects (The Question, Tutorial) DIRECTLY from their installed location,
without copying them into the UPVN project.
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


@skip_no_sdk
class TestTheQuestionFromSDK:
    """Run The Question from its Ren'Py SDK location — no copying."""

    def test_script_exists(self):
        assert os.path.isfile(os.path.join(THE_QUESTION_GAME, "script.rpy"))

    def test_parses_full_mode(self):
        from engine.script.parser import parse_file
        ast = parse_file(os.path.join(THE_QUESTION_GAME, "script.rpy"),
                         mode="full", require_start=False)
        labels = ast.get("labels", {})
        assert len(labels) >= 5

    def test_runs_headless_path_0_0(self):
        from engine.core.vn_controller import VNController
        ctrl = VNController(script_path=os.path.join(THE_QUESTION_GAME, "script.rpy"),
                            mode="full")
        trace = ctrl.run_headless(choices=[0, 0])
        say = [e for e in trace if e.get("type") == "say"]
        assert len(say) >= 15, f"Expected 15+ say events, got {len(say)}"

    def test_runs_headless_path_1_1(self):
        from engine.core.vn_controller import VNController
        ctrl = VNController(script_path=os.path.join(THE_QUESTION_GAME, "script.rpy"),
                            mode="full")
        trace = ctrl.run_headless(choices=[1, 1])
        say = [e for e in trace if e.get("type") == "say"]
        assert len(say) >= 10

    def test_gui_rpy_parses(self):
        from engine.script.parser import parse_file
        path = os.path.join(THE_QUESTION_GAME, "gui.rpy")
        ast = parse_file(path, mode="full", require_start=False)
        assert isinstance(ast, dict)

    def test_screens_rpy_parses(self):
        from engine.script.parser import parse_file
        path = os.path.join(THE_QUESTION_GAME, "screens.rpy")
        ast = parse_file(path, mode="full", require_start=False)
        assert isinstance(ast, dict)


@skip_no_sdk
class TestTutorialFromSDK:
    """Run Tutorial from its Ren'Py SDK location — no copying."""

    def test_script_exists(self):
        assert os.path.isfile(os.path.join(TUTORIAL_GAME, "script.rpy"))

    def test_tutorial_files_count(self):
        rpy_files = sorted(glob.glob(os.path.join(TUTORIAL_GAME, "*.rpy")))
        assert len(rpy_files) >= 15

    def test_parses_full_mode(self):
        from engine.script.parser import parse_file
        ast = parse_file(os.path.join(TUTORIAL_GAME, "script.rpy"),
                         mode="full", require_start=False)
        assert isinstance(ast, dict)

    def test_runs_headless_compat(self):
        """Tutorial uses Ren'Py-specific modules (ui.adjustment) — needs --compat."""
        from engine.core.vn_controller import VNController
        ctrl = VNController(script_path=os.path.join(TUTORIAL_GAME, "script.rpy"),
                            mode="full")
        trace = ctrl.run_headless(compat=True)
        say = [e for e in trace if e.get("type") == "say"]
        assert len(say) >= 1, f"Tutorial should produce at least 1 say event, got {len(say)}"

    def test_tutorial_has_eileen(self):
        """Tutorial script says 'Hi! My name is Eileen' — verify via headless trace."""
        from engine.core.vn_controller import VNController
        ctrl = VNController(script_path=os.path.join(TUTORIAL_GAME, "script.rpy"),
                            mode="full")
        trace = ctrl.run_headless(compat=True)
        texts = [e.get("text", "") for e in trace if e.get("type") == "say"]
        assert any("Eileen" in t for t in texts), f"No Eileen in tutorial: {texts[:3]}"
