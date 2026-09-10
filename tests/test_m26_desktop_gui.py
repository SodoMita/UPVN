"""M26 — texture-free palette, image policy, dir-script resolution.

Covers the texture-free GUI milestone: palette lookups, the image_mode
policy chain (env > controller prop > default), the object-color helper,
path-prefix coverage and the frontend's directory script resolution.
"""
import os
from pathlib import Path

import pytest

from engine.render import contract
from engine.render.contract import (
    COLOR_STAGES, SPRITE_TINTS, apply_object_color, hash_color,
    image_mode_from, sprite_color, stage_color,
)
from engine.render.scene_manager import BG_PATH_PREFIXES
from engine.render.sprite_renderer import SPRITE_PATH_PREFIXES


# ---------------------------------------------------------------- palette
def test_stage_color_curated_tokens():
    assert stage_color("bg classroom") == (*COLOR_STAGES["classroom"], 1.0)
    assert stage_color("bg classroom day") == (*COLOR_STAGES["classroom"], 1.0)
    assert stage_color("bg lecturehall") == (*COLOR_STAGES["lecturehall"], 1.0)
    assert stage_color("black") == (*COLOR_STAGES["black"], 1.0)


def test_stage_color_hash_fallback_deterministic():
    a = stage_color("bg spaceship_deck")
    b = stage_color("bg spaceship_deck")
    assert a == b
    assert len(a) == 4
    assert all(0.0 <= c <= 1.0 for c in a)
    # different names differ with overwhelming likelihood
    assert stage_color("bg something_else") != a


def test_sprite_color_curated_and_hash():
    assert sprite_color("eileen") == (*SPRITE_TINTS["eileen"], 1.0)
    assert sprite_color("eileen happy") == (*SPRITE_TINTS["eileen"], 1.0)
    assert sprite_color("nobody") == sprite_color("nobody")


def test_hash_color_is_stable_across_processes():
    # hash() is process-seeded; hash_color must not use it
    assert hash_color("stable") == (0.7215686274509805, 0.3862514417531719, 0.4730394192278989, 1.0)


# ---------------------------------------------------------------- policy
def test_image_mode_default_is_color():
    assert image_mode_from(None, env=None) == "color"
    assert image_mode_from(None, env="") == "color"
    assert contract.IMAGE_MODE_DEFAULT == "color"


def test_image_mode_env_overrides():
    assert image_mode_from(None, env="auto") == "auto"
    assert image_mode_from(None, env="1") == "auto"
    assert image_mode_from(None, env="COLOR") == "color"


def test_image_mode_owner_dict_prop():
    assert image_mode_from({"image_mode": "auto"}, env=None) == "auto"
    # env beats the property
    assert image_mode_from({"image_mode": "auto"}, env="color") == "color"


def test_image_mode_kx_like_owner():
    class KXLike:
        def __contains__(self, key):
            return key == "image_mode"

        def __getitem__(self, key):
            return "auto"

    assert image_mode_from(KXLike()) == "auto"


def test_image_mode_unknown_fails_closed():
    assert image_mode_from({"image_mode": "sometimes"}, env=None) == "color"
    assert image_mode_from(None, env="bogus") == "color"


# ---------------------------------------------------------------- tinting
def test_apply_object_color_sets_and_reports():
    class Fake:
        color = (1, 1, 1, 1)

    ob = Fake()
    assert apply_object_color(ob, (0.2, 0.4, 0.6, 1.0)) is True
    assert ob.color == (0.2, 0.4, 0.6, 1.0)
    assert apply_object_color(None, (1, 1, 1, 1)) is False


# ---------------------------------------------------------------- paths
def test_asset_path_prefixes_cover_repo_and_package_layouts():
    for prefixes in (BG_PATH_PREFIXES, SPRITE_PATH_PREFIXES):
        assert "//" in prefixes
        assert "//../" in prefixes          # repo: <repo>/blend + <repo>/assets
        assert "//../game/" in prefixes     # packaged: <pkg>/blend + <pkg>/assets
        assert "//../../" in prefixes


# ---------------------------------------------------------------- frontend
def test_resolve_script_path_accepts_directory(tmp_path, monkeypatch):
    """Converted Ren'Py projects point at a directory — the resolver must
    accept dirs (VNController.load merges every .rpy inside)."""
    from bge_frontend.frontend import resolve_script_path

    game_dir = tmp_path / "game"
    game_dir.mkdir()
    (game_dir / "script.rpy").write_text("label start:\n    return\n")

    class Logic:
        def expandPath(self, p):
            return p  # identity — candidates are absolute already

    got, tried = resolve_script_path(Logic(), owner=None,
                                     extra_candidates=[str(game_dir)])
    assert got == str(game_dir)
    assert str(game_dir) in tried


def test_resolve_script_path_still_finds_files(tmp_path):
    from bge_frontend.frontend import resolve_script_path

    script = tmp_path / "script.rpy"
    script.write_text("label start:\n    return\n")

    class Logic:
        def expandPath(self, p):
            return p

    got, _tried = resolve_script_path(Logic(), owner=None,
                                      extra_candidates=[str(script)])
    assert got == str(script)


def test_image_mode_prop_written_by_builder(tmp_path):
    """The addon builder writes image_mode next to script_path (source-level
    check — bpy is unavailable headless)."""
    src = (Path(__file__).resolve().parents[1] / "blend" /
           "upvn_editor_addon.py").read_text()
    assert '_set_runtime_prop(_b, ctrl, "image_mode", IMAGE_MODE_DEFAULT)' in src
    # and never clobbers a configured script_path with the default
    assert "effective_script_path" in src
