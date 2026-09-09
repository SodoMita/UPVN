"""
M20 — UPBGE runtime fixes found in the field:
  * blf.color() five-argument signature (font id + RGBA) in the overlay code
  * Pillow absence in UPBGE's bundled Python yields a clear message (not a
    raw ModuleNotFoundError traceback), and preview paths degrade gracefully
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FRONTEND_SRC = ROOT / "bge_frontend" / "frontend.py"


def _read(path) -> str:
    return path.read_text(encoding="utf-8")


def test_blf_color_calls_have_five_arguments():
    """UPBGE 0.50 requires blf.color(fontid, r, g, b, a). Field error:
    'blf.color() takes exactly 5 arguments (4 given)'."""
    src = _read(FRONTEND_SRC)
    calls = re.findall(r"blf\.color\(([^)]*)\)", src)
    assert calls, "no blf.color calls found"
    for call in calls:
        args = [a.strip() for a in call.split(",")]
        assert len(args) == 5, f"blf.color needs 5 args, got {len(args)}: blf.color({call})"
        # font id must be first
        assert args[0] == "0"


def test_blf_calls_use_font_id_pattern():
    """position/size/draw also take the font id as the first argument."""
    src = _read(FRONTEND_SRC)
    for m in re.finditer(r"blf\.(position|size|draw)\(0,", src):
        pass  # pattern match is the assertion itself
    assert len(re.findall(r"blf\.(position|size|draw)\(0,", src)) >= 6


def test_headless_renderer_importable_without_pil(monkeypatch):
    """The module must import even when Pillow is missing (UPBGE bundled Python),
    and render_state must raise a clear, instructive RuntimeError."""
    # simulate absence: hide PIL from import machinery
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "PIL" or name.startswith("PIL."):
            raise ImportError("No module named 'PIL'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    # force re-import under a fresh module name while PIL is hidden
    spec = importlib.util.spec_from_file_location(
        "upvn_headless_renderer_nopil",
        ROOT / "engine" / "render" / "headless_renderer.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.HAS_PIL is False                       # module imports w/o Pillow
    assert mod.F_Text is None                         # fonts degrades to None

    # render_state must raise an instructive error mentioning the fix
    from engine.core.vn_state import VNState
    with pytest.raises(RuntimeError) as ei:
        mod.render_state(VNState(), {"type": "say", "who": None, "text": "x"})
    msg = str(ei.value)
    assert "Pillow" in msg and "pip install pillow" in msg
    monkeypatch.undo()  # restore import machinery


def test_headless_renderer_real_pil_still_renders():
    """Sanity: with Pillow available, render_state still produces a file."""
    from engine.render.headless_renderer import HAS_PIL, render_state
    from engine.core.vn_state import VNState
    if not HAS_PIL:
        pytest.skip("Pillow missing in this environment")
    import tempfile
    out = Path(tempfile.mkdtemp()) / "r.png"
    img = render_state(VNState(), {"type": "say", "who": None, "text": "hello"}, out)
    assert out.exists() and out.stat().st_size > 1000
    assert img is not None


def test_addon_preview_error_field():
    """UPVN_GameBuilder.preview_screenshot records a human reason on failure
    instead of leaking a traceback (field report: ModuleNotFoundError: PIL)."""
    sys.path.insert(0, str(ROOT))
    from blend.upvn_editor_addon import UPVN_GameBuilder, ENGINE_AVAILABLE
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        b = UPVN_GameBuilder(str(Path(td) / "script.rpy"))
        assert hasattr(b, "last_error")
        if not ENGINE_AVAILABLE:
            out = b.preview_screenshot()
            assert out is None
            assert b.last_error  # a reason string, not an exception


def test_addon_pil_live_probe_exists():
    """The add-on probes Pillow with a live import (module-level stale flags go
    stale after a mid-session pip install)."""
    sys.path.insert(0, str(ROOT))
    from blend.upvn_editor_addon import pil_live_available
    assert isinstance(pil_live_available(), bool)
    # system Python has Pillow in this test env
    assert pil_live_available() is True


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
    assert '"upvn_bricks"] = "existing"' in src
