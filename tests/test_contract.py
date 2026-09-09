"""
M19 — scene contract (engine/render/contract.py): single source of truth for
the object/material/collection names the renderers expect, plus consistency
between the contract and the renderer modules (no silent drift).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.render import contract  # noqa: E402


def test_contract_core_identifiers():
    assert contract.BG_PLANE == "BG_Plane"
    assert contract.BG_MATERIAL == "MABackground"
    assert contract.SPRITE_MATERIAL == "MASprite"
    assert contract.SPRITE_POSITIONS == ("far_left", "left", "center", "right", "far_right")
    assert contract.CONTROLLER == "VNController"
    assert contract.CAMERA_UI == "Camera_UI"
    assert contract.CAMERA_3D == "Camera_3D"
    assert contract.LAUNCHER_TEXT == "upvn_launcher"
    assert set(contract.POSITIONS) == set(contract.SPRITE_POSITIONS)


def test_contract_required_objects_complete():
    items = contract.required_objects()
    names = {it["name"] for it in items}
    # every contract identifier appears in the required list
    assert contract.BG_PLANE in names
    assert contract.DIALOGUE_PLANE in names
    assert contract.CONTROLLER in names
    assert contract.LAUNCHER_TEXT in names
    for pos in contract.SPRITE_POSITIONS:
        assert f"Sprite_{pos}" in names
    assert contract.BG_MATERIAL in names
    assert contract.SPRITE_MATERIAL in names
    for col in contract.COLLECTIONS:
        assert col in names
    # every item carries an explanation of who uses it
    for it in items:
        assert it["purpose"]
        assert it["used_by"]
        assert it["kind"] in ("object", "material", "collection", "text")


def test_contract_check_full_scene_ok():
    obj_names = {contract.BG_PLANE, contract.DIALOGUE_PLANE, contract.CONTROLLER,
                 contract.CAMERA_UI, contract.CAMERA_3D}
    obj_names |= {f"Sprite_{p}" for p in contract.SPRITE_POSITIONS}
    mats = {contract.BG_MATERIAL, contract.SPRITE_MATERIAL}
    res = contract.check_contract(obj_names, mats, set(contract.COLLECTIONS),
                                  {contract.LAUNCHER_TEXT})
    assert res["missing"] == []
    assert len(res["present"]) == len(contract.required_objects())


def test_contract_check_empty_scene_lists_everything():
    res = contract.check_contract([], [], [], [])
    missing_names = {it["name"] for it in res["missing"]}
    assert missing_names == {it["name"] for it in contract.required_objects()}
    assert res["present"] == []


def test_contract_check_partial():
    res = contract.check_contract(object_names=[contract.BG_PLANE])
    missing_names = {it["name"] for it in res["missing"]}
    assert contract.BG_PLANE not in missing_names
    assert "Sprite_center" in missing_names
    assert contract.BG_MATERIAL in missing_names


def test_contract_renderer_consistency():
    """Renderers must read their identifiers from the contract — if a renderer
    hard-codes a name again, this test fails and the drift is visible."""
    from engine.render import scene_manager as sm
    from engine.render import sprite_renderer as sr
    assert sm.BG_PLANE == contract.BG_PLANE
    assert sm.BG_MATERIAL == contract.BG_MATERIAL
    assert sr.POSITIONS == contract.POSITIONS
    assert sr.SPRITE_MATERIAL == contract.SPRITE_MATERIAL
    assert sr.BG_PLANE == contract.BG_PLANE


def test_contract_renderer_no_legacy_literals():
    """Guard against reintroducing hard-coded names in the render modules."""
    import inspect
    from engine.render import scene_manager as sm
    from engine.render import sprite_renderer as sr
    src = (inspect.getsource(sm) + inspect.getsource(sr))
    for literal in ("objects.get(\"BG_Plane\")", "materialID(plane, \"MABackground\")",
                    "f\"Sprite_{position}\"", "materialID(plane, \"MASprite\")",
                    "\"assets/backgrounds/\""):
        assert literal not in src, f"legacy hard-coded identifier reintroduced: {literal}"
