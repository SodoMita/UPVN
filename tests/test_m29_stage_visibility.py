"""M29: the baked 3D stage is hidden for scripts that never use it.

Why this rule exists (all of it live-measured in the player, sway/pixman,
UPBGE 0.50.0, not inferred):

- The shipped template bakes a 3D classroom into the ``VN_3DStage``
  collection so ``load_stage`` / ``show3d`` work with zero setup. For a pure
  2D game those objects are painted over the art: ``Desk_*`` / ``Chair_*`` /
  ``Blackboard`` poked through the background plane and drew a brown band
  across the character, and the factory ``Cube`` (merely *unlinked* from the
  master collection by the old template builder, never deleted) sat as a grey
  171 px square dead centre of every frame.
- The rule is derived from the parsed script, not a checkbox: no author
  action is needed for the common case, and the 3D tier keeps working. Same
  build, two scripts: ``20_smoke_game`` → ``stage_visible=0``
  (art/qa/m29_09_clean.webp), ``02_sprites_backgrounds`` → 43/43 visible
  (art/qa/m29_10_stage3d.webp).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

from engine.render.stage_manager import (          # noqa: E402
    STAGE_EVENT_TYPES,
    STAGE_PROP,
    StageManager,
    script_uses_stage,
)


def test_detection_handles_parser_and_event_shapes():
    # the parser emits {"cmd": ...}, the interpreter's events use {"type": ...}
    assert script_uses_stage({"labels": {"start": [{"cmd": "say", "text": "hi"}]}}) is False
    assert script_uses_stage({"labels": {"start": [{"cmd": "show3d", "asset": "e"}]}}) is True
    assert script_uses_stage({"labels": {"start": [{"type": "camera_preset"}]}}) is True
    # nested bodies (if / menu / blocks) are walked generically
    nested = {"labels": {"start": [{"cmd": "if", "body": [{"cmd": "load_stage"}]}]}}
    assert script_uses_stage(nested) is True
    assert script_uses_stage(None) is False
    assert script_uses_stage({}) is False
    assert script_uses_stage({"labels": {}}) is False


def test_every_stage_directive_triggers_and_2d_vocabulary_does_not():
    for cmd in ("load_stage", "show3d", "anim", "camera_preset"):
        assert cmd in STAGE_EVENT_TYPES
        assert script_uses_stage({"labels": {"s": [{"cmd": cmd}]}}) is True
    for cmd in ("say", "scene", "show", "hide", "menu", "jump", "window",
                "camera_zoom", "play_music"):
        assert script_uses_stage({"labels": {"s": [{"cmd": cmd}]}}) is False


def test_examples_split_the_way_the_contract_does():
    from engine.script.parser import parse_file
    expected = {
        "00_minimal_dialogue": False,
        "02_sprites_backgrounds": True,     # load_stage + show3d + camera preset
        "10_full_sample_game": True,
        "20_smoke_game": False,             # the M29 showcase scene: 2D only
    }
    for name, want in expected.items():
        path = os.path.join(REPO, "examples", name, "script.rpy")
        if not os.path.exists(path):        # examples are optional to install
            continue
        assert script_uses_stage(parse_file(path)) is want, name


def test_prepare_records_the_flag_headless():
    from engine.core.vn_state import VNState

    mgr = StageManager(VNState())
    assert mgr.stage_used is False and mgr.stage_hidden == 0

    assert mgr.prepare({"labels": {"start": [{"cmd": "say"}]}}) is False
    assert mgr.stage_used is False
    # headless has no bge: nothing to hide, and it must not raise
    assert mgr.stage_hidden == 0

    assert mgr.prepare({"labels": {"start": [{"cmd": "show3d"}]}}) is True
    assert mgr.stage_used is True


def test_controller_decides_at_load():
    """VNController.load() is the single entry point, live and headless."""
    from engine.core.vn_controller import VNController

    path_2d = os.path.join(REPO, "examples", "20_smoke_game", "script.rpy")
    if os.path.exists(path_2d):
        ctrl = VNController(script_path=path_2d)
        ctrl.load()
        assert ctrl.stage_mgr is not None
        assert ctrl.stage_mgr.stage_used is False

    path_3d = os.path.join(REPO, "examples", "02_sprites_backgrounds", "script.rpy")
    if os.path.exists(path_3d):
        ctrl = VNController(script_path=path_3d)
        ctrl.load()
        assert ctrl.stage_mgr.stage_used is True


def _upbge_blender():
    """The shipped template can only be inspected with a real Blender/UPBGE."""
    for cand in (os.environ.get("UPVN_BLENDER"),
                 os.path.join(os.environ.get("UPBGE_DIR", ""), "blender"),
                 "/opt/upbge/upbge-0.50-linux-x64/blender",
                 "/opt/upbge/blender"):
        if cand and os.path.exists(cand):
            return cand
    return None


def test_shipped_template_passes_its_shipping_gate():
    """tools/check_template.py is the gate; it must pass on the shipped file.

    The gate exists because this file shipped with a leftover factory Cube and
    an unstamped 3D stage for weeks and no test could tell: the .blend is
    zstd-compressed (a byte scan finds nothing) and the engine never opens it.
    """
    import subprocess
    import pytest

    blender = _upbge_blender()
    if blender is None:
        pytest.skip("no UPBGE/Blender binary available to inspect the .blend")

    blend = os.path.join(REPO, "blend", "UPVN_Template.blend")
    proc = subprocess.run(
        [blender, "--background", "--python",
         os.path.join(REPO, "tools", "check_template.py"), "--", "--blend", blend],
        capture_output=True, text=True, timeout=300,
        env={**os.environ, "LIBGL_ALWAYS_SOFTWARE": "1"})
    tail = "\n".join((proc.stdout + proc.stderr).splitlines()[-25:])
    assert proc.returncode == 0, f"template gate failed:\n{tail}"
    assert "template is shippable" in proc.stdout, tail


def test_builders_stamp_and_delete_leftovers():
    """The tools that *make* a template must keep doing both things."""
    addon = open(os.path.join(REPO, "blend", "upvn_editor_addon.py")).read()
    assert "_mark_stage_objects(_b)" in addon
    assert '"upvn_stage", "1"' in addon, (
        "the flag must be a STRING game property: a BOOL game property created "
        "through the data API reads back as False in the player")

    maker = open(os.path.join(REPO, "tools", "make_template.py")).read()
    assert "_mark_stage_objects" in maker
    assert "bpy.data.objects.remove(ob, do_unlink=True)" in maker, (
        "unlinking factory objects is not deleting them — that is how the "
        "default Cube shipped in the template")


def test_runtime_reader_uses_game_property_lookup():
    engine = open(os.path.join(REPO, "engine", "render", "stage_manager.py")).read()
    assert "if STAGE_PROP in ob and ob[STAGE_PROP]" in engine
    front = open(os.path.join(REPO, "bge_frontend", "frontend.py")).read()
    assert '"upvn_stage" in ob' in front
    assert "_stage_stats(" in front
