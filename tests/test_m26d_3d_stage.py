"""M26d 3D-stage tier + LibLoad-segfault regression tests (headless).

All decisions here were live-measured in the player against UPBGE 0.50.0:
- ANY LibLoad segfaults the player (even re-loading a copy of the running
  template) → LibLoad is opt-in behind UPVN_ENABLE_LIBLOAD, StageManager
  existence-checks first, SceneManager must not LibLoad at all.
- addObject() rejects active objects; collection-excluded objects do not
  exist in the runtime → spawn() repositions the active template master.
- camera_preset must check the Camera_UI guard BEFORE resolving Camera_3D
  (resolving first moved the dormant template camera in front of the UI).
"""
import ast
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO = os.path.join(os.path.dirname(__file__), "..")


def _src(rel):
    return open(os.path.join(REPO, rel)).read()


def test_load_stage_gated_and_guarded():
    from tests.test_m26c_camera_zoom import (
        test_stage_manager_libload_is_exists_guarded_and_gated,
    )
    test_stage_manager_libload_is_exists_guarded_and_gated()


def test_camera_preset_guards_camera_ui_first():
    src = _src("engine/render/stage_manager.py")
    body = src[src.index("def camera_preset"):]
    body = body[:body.index("\n    def ")] if "\n    def " in body else body
    guard = 'getattr(cam, "name", "") == "Camera_UI"'
    i_first_guard = body.index(guard)
    i_cam3d = body.index('scene.objects.get("Camera_3D")')
    assert i_first_guard < i_cam3d, (
        "camera_preset must check the Camera_UI guard BEFORE resolving "
        "Camera_3D (the resolve moved the dormant template camera and the "
        "viewport rendered from it — live-measured)"
    )
    # and it must skip with a log line, not move the UI camera
    assert "camera_preset skipped" in body


def test_spawn_has_reposition_fallback():
    src = _src("engine/render/stage_manager.py")
    body = src[src.index("def spawn"):]
    body = body[:body.index("\n    def ")] if "\n    def " in body else body
    assert "objectsInactive" in body, "prefer cloning an inactive master"
    assert "template_active" in body
    assert "worldPosition" in body and "worldOrientation" in body, (
        "active masters must be repositioned onto the marker (addObject "
        "rejects active objects; excluded collections don't exist in the "
        "runtime — both live-measured)"
    )
    assert "repositioned template" in body  # diagnostic line


def test_play_anim_logs_success():
    src = _src("engine/render/stage_manager.py")
    body = src[src.index("def play_anim"):]
    body = body[:body.index("\n    def ")] if "\n    def " in body else body
    assert "playAction" in body
    assert "play_anim" in body.split("playAction", 1)[1], (
        "success diagnostic expected after playAction (failure-only logging "
        "hid working animations during live verification)"
    )


def test_frontend_binds_camera_every_tick():
    src = _src("bge_frontend/frontend.py")
    body = src[src.index("def _bind_camera"):]
    body = body[:body.index("\ndef ")]
    # no sticky early-return guard: the bind must re-assert every tick
    assert "_upvn_cam_bound" in body
    assert body.index("sc.active_camera = want") < body.index(
        'logic._upvn_cam_bound = True'
    ), "assign active_camera before the sticky flag returns"


def test_bake_tool_exists_and_excludes_cameras():
    p = os.path.join(REPO, "tools", "bake_stage_into_template.py")
    assert os.path.exists(p)
    src = open(p).read()
    assert "EXCLUDE_SUFFIX" in src and '"Camera"' in src
    assert "30.0, -3.0, -30.0" in src, "template parking position"


def test_sample_stage_blend_shipped():
    p = os.path.join(REPO, "examples", "10_full_sample_game", "stages",
                     "classroom_3d.blend")
    assert os.path.exists(p), (
        "sample 3D stage (geometry, markers, preset, parked templates, wave "
        "action) must ship with the sample game"
    )
