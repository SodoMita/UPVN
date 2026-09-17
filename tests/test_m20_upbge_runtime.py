"""
M20 — UPBGE runtime fixes found in the field:
  * UI is 3D scene objects (no blf overlay)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FRONTEND_SRC = ROOT / "bge_frontend" / "frontend.py"


def _read(path) -> str:
    return path.read_text(encoding="utf-8")


def test_frontend_has_no_blf_overlay():
    """Field: overlay was the only visible dialogue and choice clicks missed
    3D planes. UI is world objects only."""
    src = _read(FRONTEND_SRC)
    assert "import blf" not in src
    assert "def draw_overlay" not in src
    assert "sc.post_draw.append" not in src
    assert "build_world_ui" in src
    assert "_tick_pointer" in src


def test_addon_build_vn_scene_no_brick_collection_remove():
    """Field error: 'bpy_prop_collection: attribute "remove" not found' when
    Setup Scene ran twice — UPBGE 0.50 brick collections are read-only. The
    generator must reuse the existing VNController instead of deleting it."""
    src = _read(ROOT / "blend" / "upvn_editor_addon.py")
    assert 'game.controllers.remove(' not in src
    assert '.sensors.remove(' not in src
    # reuse path + per-piece brick addition must be present
    assert 'ctrl = scene.objects.get("VNController")' in src
    assert 'need_sensor' in src and 'need_controller' in src
    assert '_set_runtime_prop(_b, ctrl, "upvn_bricks", "existing")' in src
