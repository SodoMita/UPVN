"""
M22 — UPBGE play loop: camera actually used, keys via inputs.queue, no .events.

Field report: game starts, LMB advances, keys do nothing, Camera_UI pose is
wrong and never bound (headless still correct).
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.core.vn_controller import _classify_input_entry  # noqa: E402
from engine.render import contract  # noqa: E402


class _FakeInput:
    def __init__(self, queue=(), status=(), activated=False, active=False):
        self.queue = list(queue)
        self.status = list(status)
        self.activated = activated
        self.active = active


def test_classify_queue_just_activated():
    just, active = 1, 2
    e = _FakeInput(queue=[just], status=[active])
    assert _classify_input_entry(e, just, active) == "just"


def test_classify_status_active_only():
    just, active = 1, 2
    e = _FakeInput(queue=[], status=[active], active=True)
    assert _classify_input_entry(e, just, active) == "active"


def test_classify_legacy_int():
    assert _classify_input_entry(1, 1, 2) == "just"
    assert _classify_input_entry(2, 1, 2) == "active"
    assert _classify_input_entry(0, 1, 2) is None


def test_classify_none_and_empty():
    assert _classify_input_entry(None) is None
    assert _classify_input_entry(_FakeInput()) is None


def test_no_device_events_in_runtime_sources():
    """keyboard.events is deprecated and lossy — sources must not read it."""
    for rel in ("bge_frontend/frontend.py", "engine/core/vn_controller.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        for line in src.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            if "device.events" in line and "Never" not in line and "never" not in line:
                assert False, f"{rel} still references device.events: {line}"
            if ".events[" in line and "bge.events" not in line and "_bge.events" not in line and "_bge_imp.events" not in line:
                assert False, f"{rel} indexes *.events: {line}"


def test_frontend_binds_camera_ui():
    spec = importlib.util.spec_from_file_location(
        "upvn_frontend_m22", ROOT / "bge_frontend" / "frontend.py")
    fe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fe)
    assert hasattr(fe, "_bind_camera")
    fe._bind_camera()  # headless no-op
    src = (ROOT / "bge_frontend" / "frontend.py").read_text(encoding="utf-8")
    assert "active_camera" in src and "Camera_UI" in src
    assert "keyboard.events" not in src
    assert "_device_states" not in src


def test_camera_contract_front_view():
    assert contract.CAMERA_UI == "Camera_UI"
    assert contract.CAMERA_UI_LOCATION == (0.0, -10.0, 0.0)
    assert abs(contract.CAMERA_UI_ROTATION[0] - math.pi / 2) < 1e-9
    assert abs(contract.PLANE_ROTATION[0] - math.pi / 2) < 1e-9
    # sprites sit in front of BG (negative Y toward camera)
    assert contract.POSITIONS["center"][1] < 0
    names = {it["name"] for it in contract.required_objects()}
    assert "Camera_UI" in names and "Camera_3D" in names


def test_addon_setup_resets_camera_and_adds_allkeys():
    src = (ROOT / "blend" / "upvn_editor_addon.py").read_text(encoding="utf-8")
    assert 'CAMERA_UI_LOCATION' in src
    assert 'upvn_camera_custom' in src
    assert 'need_keys' in src and 'AllKeys' in src
    assert 'use_all_keys' in src
    assert '"version": (0, 6, 10)' in src
    assert "loc=(0, -10, 5)" not in src
