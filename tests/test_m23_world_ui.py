"""
M23 — 3D-only UI: no blf overlay, FONT + choice planes, unlit materials,
pointer raycast maps LMB on choice_N to VNController.choose.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.ui.world_ui import (  # noqa: E402
    apply_world_ui, build_world_ui, layout_screen_ui, normalize_hit_name, wrap_text,
)
from engine.ui.pointer import PointerTracker, HotspotMap  # noqa: E402


class _FakeObj:
    def __init__(self, name):
        self.name = name
        self.text = ""
        self.visible = True
        self._props = {}

    def __setitem__(self, k, v):
        self._props[k] = v

    def __getitem__(self, k):
        return self._props[k]


class _FakeUI:
    current_who = "Eileen"
    def revealed_text(self):
        return "Hello there, world of visual novels and friends."


def test_wrap_text_splits_long_line():
    s = wrap_text("one two three four five six", width=10)
    assert "\n" in s
    assert all(len(line) <= 10 or " " not in line for line in s.split("\n"))


def test_build_say_payload():
    ev = {"type": "say", "text": "hi"}
    p = build_world_ui(ev, ui_mgr=_FakeUI())
    assert p["speaker"] == "Eileen"
    assert "Hello" in p["dialogue"]
    assert p["dialogue_visible"] is True
    assert all(not c["visible"] for c in p["choices"])


def test_build_menu_payload_hides_unused():
    ev = {"type": "menu", "caption": "Pick",
          "choices": [{"id": "a", "text": "Ask"}, {"id": "b", "text": "Wait"}]}
    p = build_world_ui(ev, n_choices=9)
    # M28 Ren'Py identical: no numbering, just text (Ren'Py choice buttons show raw text)
    assert p["choices"][0]["visible"] and p["choices"][0]["text"] == "Ask"
    assert p["choices"][1]["visible"]
    assert not p["choices"][2]["visible"]
    assert len(p["choices"]) == 9


def test_apply_world_ui_writes_fonts_and_visibility():
    scene = {}
    for n in ("Speaker_Text", "Dialogue_Text", "Dialogue_Box"):
        scene[n] = _FakeObj(n)
    for i in range(9):
        scene[f"choice_{i}"] = _FakeObj(f"choice_{i}")
        scene[f"choice_{i}_text"] = _FakeObj(f"choice_{i}_text")
    ev = {"type": "menu", "caption": "Go?",
          "choices": [{"id": "a", "text": "Yes"}]}
    apply_world_ui(scene.get, build_world_ui(ev))
    assert scene["choice_0"].visible is True
    # M28 Ren'Py identical: raw text, no numbering
    assert scene["choice_0_text"].text == "Yes"
    assert scene["choice_1"].visible is False
    assert "Go?" in scene["Dialogue_Text"].text


def test_normalize_hit_name():
    assert normalize_hit_name("choice_2_text") == "choice_2"
    assert normalize_hit_name("choice_2") == "choice_2"
    assert normalize_hit_name(None) is None


def test_pointer_click_index():
    hs = HotspotMap.from_choices([{"id": 0, "text": "A"}, {"id": 1, "text": "B"}])
    tr = PointerTracker(hs)
    tr.update("choice_1")
    ev = tr.update("choice_1", clicked=True)
    assert tr.choose(ev[0]) == 1


def test_layout_ui_ndc_stable_across_zoom():
    # M28 Ren'Py identical: dialogue box at fixed DIALOGUE_LOCATION, not NDC-scaled
    class O:
        def __init__(self):
            self.worldPosition = (0, 0, 0)
            self.worldScale = (1, 1, 1)
            self.size = 0.3
            self.visible = True
            self.text = ""
    scene = {n: O() for n in ("Speaker_Text", "Dialogue_Text", "Dialogue_Box",
                              "choice_0", "choice_0_text")}
    payload = build_world_ui({"type": "menu", "caption": "Go?",
                              "choices": [{"id": 0, "text": "Yes"}]})
    from engine.render.contract import DIALOGUE_LOCATION
    layout_screen_ui(scene.get, payload, ortho=15.0)
    z15 = scene["Dialogue_Box"].worldPosition[2]
    layout_screen_ui(scene.get, payload, ortho=10.0)
    z10 = scene["Dialogue_Box"].worldPosition[2]
    # Fixed Ren'Py position, should be identical across ortho
    assert z15 == z10 == DIALOGUE_LOCATION[2]


def test_frontend_and_addon_are_3d_unlit():
    fe = (ROOT / "bge_frontend" / "frontend.py").read_text(encoding="utf-8")
    ad = (ROOT / "blend" / "upvn_editor_addon.py").read_text(encoding="utf-8")
    assert "import blf" not in fe
    assert "def draw_overlay" not in fe
    assert "_tick_pointer" in fe and "getScreenRay" in fe
    assert "showMouse" in fe
    assert "_rewrite_unlit" in ad
    assert "ShaderNodeEmission" in ad
    assert "Speaker_Text" in ad and "choice_" in ad
    _vm = re.search(r'"version":\s*\((\d+), (\d+), (\d+)\)', ad)
    assert _vm and _vm.group(0) in ad  # bl_info version present (bump-safe)
    assert "scene_name=None" in ad
    assert "_get_or_create" in ad
