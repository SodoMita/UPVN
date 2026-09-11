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


# ------------------------------------------------------- M26b texture graph
def _fake_mat_with_tex_graph():
    """Minimal dict-based stand-in mimicking the node graph contract."""
    class Sock:
        def __init__(self, name, value=None):
            self.name = name
            self.value = value

        @property
        def default_value(self):
            return self.value

        @default_value.setter
        def default_value(self, v):
            self.value = v

    class TexNode:
        type = "TEX_IMAGE"

        def __init__(self):
            self.image = "white"

    class MixNode:
        type = "MIX"

        def __init__(self):
            self.inputs = [Sock("Factor", 0.0)]

    class Mat:
        def __init__(self):
            self.nodes = [TexNode(), MixNode()]

    return Mat()


def test_apply_material_image_rejects_bad_paths():
    # no bpy headless → helpers must fail closed, not raise
    assert contract.apply_material_image(_fake_mat_with_tex_graph(),
                                         "/nonexistent/x.png") is False
    assert contract.apply_material_image(None, None) is False


def test_reset_material_palette_is_safe_headless():
    assert contract.reset_material_palette(None) is False


def test_plane_material_none_headless():
    assert contract.plane_material(None) is None


def test_tex_node_names_are_stable():
    # the addon bakes these into the .blend — never rename casually
    assert contract.TEX_NODE_NAME == "UPVN Tex Image"
    assert contract.MIX_NODE_NAME == "UPVN Tex Mix"
    assert contract.WHITE_IMAGE_NAME == "UPVN_White1px"


def test_template_carries_texture_graph_and_uvs():
    """blend/UPVN_Template.blend: TexImage+Mix nodes on BG + per-pos sprites,
    packed white starter, UV layers, per-position sprite materials."""
    import subprocess
    # binary test (same pattern as test_m26g_addon_live_update): without a
    # UPBGE install this must SKIP, not error — a hardcoded path with no
    # guard turned "no /opt/upbge on this machine" into a suite failure.
    if not Path("/opt/upbge/upbge-0.50-linux-x64/blender").exists():
        import pytest
        pytest.skip("UPBGE binary not present "
                    "(/opt/upbge/upbge-0.50-linux-x64)")
    blend = Path(__file__).resolve().parents[1] / "blend" / "UPVN_Template.blend"
    expr = (
        "import bpy;"
        "w = bpy.data.images.get('UPVN_White1px');"
        "print('WHITE_PACKED', w.packed_file is not None if w else None);"
        "m = bpy.data.materials.get('MABackground');"
        "k = sorted(n.type for n in m.node_tree.nodes);"
        "print('BG_NODES', 'TEX_IMAGE' in k and 'MIX' in k);"
        "sp = bpy.data.objects.get('Sprite_center');"
        "print('SPRITE_MAT', [x.name for x in sp.data.materials]);"
        "print('SPRITE_UV', len(sp.data.uv_layers) > 0);"
        "bg = bpy.data.objects.get('BG_Plane');"
        "print('BG_UV', len(bg.data.uv_layers) > 0, 'W', round(bg.scale.x, 1))"
    )
    out = subprocess.run(
        ["/opt/upbge/upbge-0.50-linux-x64/blender", "--background",
         str(blend), "--python-expr", expr],
        capture_output=True, text=True, timeout=120)
    lines = out.stdout + out.stderr
    def val(tag):
        for l in lines.splitlines():
            if l.startswith(tag):
                return l.split(None, 1)[1]
        return None
    assert val("WHITE_PACKED") == "True"
    assert val("BG_NODES") == "True"
    assert val("SPRITE_MAT") == "['MASprite_center']"
    assert val("SPRITE_UV") == "True"
    parts = val("BG_UV").split()
    bg_uv, bg_w = parts[0], parts[-1]
    assert bg_uv == "True"
    # widened background covers the 15-unit frustum on 16:9
    assert bg_w == "9.0"
