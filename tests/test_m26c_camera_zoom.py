"""M26c camera-zoom + script-crash regression tests (headless).

Covers the two live bugs found playing the full-sample game in the player:
1. `load_stage classroom_3d` SIGSEGV'd blenderplayer — SceneManager
   LibLoad'ed the raw expanded path with no os.path.exists check (kernel
   log: sig=11). Guard: SceneManager must not LibLoad at all (StageManager
   owns it and existence-checks every candidate).
2. Zoom base traps: measuring "the un-zoomed ortho" from the live camera
   is wrong because the interpreter sets state.camera["zoom"] before the
   frontend's first tick (inflated base ×1.2) and calm ticks between
   tweens carry the previous zoom's ortho (compounding: authored 1.5×
   played as 1.8×). The contract constant is the single base, and the
   frontend is the single ortho writer.
"""
import ast
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bge_frontend.frontend import zoom_ortho_scale  # noqa: E402
from engine.render.contract import CAMERA_UI_ORTHO_SCALE  # noqa: E402

REPO = os.path.join(os.path.dirname(__file__), "..")


def _ease_linear(x):
    return x


def test_zoom_endpoints_exact():
    # authored values verified live in the player heartbeat:
    # 15.0 → 12.5 (1.2×) → 10.0 (1.5×) → 15.0 (1.0×)
    assert zoom_ortho_scale(15.0, 1.0, 1.2, 1.0, "linear", 1.0) == 12.5
    assert zoom_ortho_scale(15.0, 1.2, 1.5, 1.0, "linear", 1.0) == 10.0
    assert zoom_ortho_scale(15.0, 1.5, 1.0, 0.8, "linear", 1.0) == 15.0


def test_zoom_midpoint_linear():
    # half way 1.0→1.2 at base 15 → zoom 1.1 → ortho 15/1.1
    v = zoom_ortho_scale(15.0, 1.0, 1.2, 1.0, "linear", 0.5)
    assert math.isclose(v, 15.0 / 1.1, rel_tol=1e-9)


def test_zoom_clamps():
    # divide-by-zero guard: zoom 0 never crashes, ortho clamps at base/0.05
    v = zoom_ortho_scale(15.0, 1.0, 0.0, 1.0, "linear", 1.0)
    assert v == 15.0 / 0.05
    # ortho never below 1.0 even for an absurd contract base
    assert zoom_ortho_scale(0.5, 1.0, 1.0, 1.0, "linear", 0.0) >= 1.0
    # t_raw outside [0,1] is clamped (negative / >1 are endpoint values)
    assert (zoom_ortho_scale(15.0, 1.0, 1.2, 1.0, "linear", -3.0)
            == zoom_ortho_scale(15.0, 1.0, 1.2, 1.0, "linear", 0.0))


def test_unknown_easing_falls_back():
    # must not raise; falls back to default ease
    v = zoom_ortho_scale(15.0, 1.0, 1.2, 1.0, "definitely-not-an-easing", 1.0)
    assert v == 12.5


def test_scene_manager_never_libloads():
    """Regression: unguarded LibLoad on a missing stage file SIGSEGV'd the
    player. SceneManager must not call LibLoad at all."""
    src_path = os.path.join(REPO, "engine", "render", "scene_manager.py")
    tree = ast.parse(open(src_path).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else fn.id
            assert name != "LibLoad", (
                "scene_manager.py calls LibLoad — missing stage files segfault "
                "the player (StageManager owns stage loading, with exists checks)"
            )


def test_stage_manager_libload_is_exists_guarded():
    """StageManager may LibLoad, but only after an os.path.exists check."""
    src_path = os.path.join(REPO, "engine", "render", "stage_manager.py")
    src = open(src_path).read()
    assert "logic.LibLoad" in src
    # every LibLoad call site must sit behind an os.path.exists guard in its
    # branch (the guarded load_stage loop)
    lines = src.splitlines()
    for i, line in enumerate(lines):
        if "logic.LibLoad" in line:
            window = "\n".join(lines[max(0, i - 12):i])
            assert "os.path.exists(path)" in window, (
                f"LibLoad at line {i + 1} lacks an os.path.exists guard nearby"
            )


def test_frontend_is_single_ortho_writer():
    """The frontend's _apply_camera_state is the one place writing
    ortho_scale from the interpreter's zoom state; StageManager's legacy
    lerp must stay disabled."""
    sm = open(os.path.join(REPO, "engine", "render", "stage_manager.py")).read()
    fe = open(os.path.join(REPO, "bge_frontend", "frontend.py")).read
    # camera_zoom body disabled right after the M26c note
    idx = sm.index("def camera_zoom")
    body = sm[idx:idx + 600]
    assert "Keep this a no-op" in body and "\n        return\n" in body
    # update() zoom lerp disabled
    idx = sm.index("def update(self, dt: float):")
    assert "single ortho_scale writer" in sm[idx:idx + 600]
    # frontend owns the math via the pure function + contract base
    fe_src = open(os.path.join(REPO, "bge_frontend", "frontend.py")).read()
    assert "def zoom_ortho_scale" in fe_src
    assert "CAMERA_UI_ORTHO_SCALE," in fe_src
