"""M26i — stylized, colored 3D text.

Covers: Character color -> speaker name tint (payload + scene objects),
drop-shadow twins (text/visibility/color), and — binary-gated — that the
baked template actually carries the DejaVu typeface, extrude+bevel, the
rewind shear and the shadow objects.
"""

from pathlib import Path

import pytest

from engine.ui.world_ui import (apply_world_ui, build_world_ui,
                                parse_hex_color, _set_font_color)
from engine.render import contract


# ---------------------------------------------------------------- helpers
class FakeObj:
    def __init__(self):
        self.color = (1.0, 1.0, 1.0, 1.0)
        self.visible = True
        self.writes = 0

    def __setattr__(self, k, v):
        if k == "color":
            object.__setattr__(self, "writes", getattr(self, "writes", 0) + 1)
        object.__setattr__(self, k, v)


def make_store(names):
    return {n: FakeObj() for n in names}


ALL_NAMES = ("Speaker_Text", "Dialogue_Text", "Dialogue_Box",
             "Speaker_Shadow", "Dialogue_Shadow",
             "History_Box", "History_Text", "Rewind_Text") + tuple(
    f"choice_{i}{s}" for i in range(2) for s in ("", "_text", "_shadow"))


# ---------------------------------------------------------------- colors
def test_parse_hex_color_forms():
    assert parse_hex_color("#c8ffc8") == (200 / 255, 1.0, 200 / 255, 1.0)
    assert parse_hex_color("c8ffc8") == (200 / 255, 1.0, 200 / 255, 1.0)
    assert parse_hex_color("#abc") == parse_hex_color("#aabbcc")
    assert parse_hex_color(None) is None
    assert parse_hex_color("") is None
    assert parse_hex_color("#12") is None
    assert parse_hex_color("zzzzzz") is None


def test_build_world_ui_carries_speaker_color_event_path():
    p = build_world_ui({"type": "say", "who": "e", "who_name": "Eileen",
                        "color": "#c8ffc8", "text": "hi"})
    assert p["speaker_color"] == (200 / 255, 1.0, 200 / 255, 1.0)


def test_build_world_ui_carries_speaker_color_ui_mgr_path():
    class UM:
        current_who = "Eileen"
        current_color = "#c8c8ff"
        def revealed_text(self):
            return "hi"
    p = build_world_ui({"type": "say", "who": "e", "text": "hi"}, ui_mgr=UM())
    assert p["speaker_color"] == (200 / 255, 200 / 255, 1.0, 1.0)


def test_build_world_ui_no_color_is_none():
    p = build_world_ui({"type": "say", "who": "n", "who_name": "N",
                        "text": "hi"})
    assert p["speaker_color"] is None
    # narration (no who at all) also stays neutral
    p2 = build_world_ui({"type": "say", "text": "hi"})
    assert p2["speaker_color"] is None


# ---------------------------------------------------------------- apply
def _payload(**kw):
    p = build_world_ui({"type": "say", "who": "e", "who_name": "Eileen",
                        "color": "#c8ffc8", "text": "hello"}, **kw)
    p["choices"] = [{"name": "choice_0", "text": "1. Ask", "visible": True},
                    {"name": "choice_1", "text": "", "visible": False}]
    return p


def test_apply_world_ui_tints_speaker_and_shadows():
    store = make_store(ALL_NAMES)
    apply_world_ui(lambda n: store.get(n), _payload())
    # speaker name carries the character color… (_set_font_color rounds to
    # 4 decimals so its change-guard never flakes on float noise)
    assert store["Speaker_Text"].color == pytest.approx(
        (200 / 255, 1.0, 200 / 255, 1.0), abs=1e-3)
    # …its shadow stays dark and mirrors the text + visibility
    assert store["Speaker_Shadow"].color[:3] == (0.02, 0.03, 0.08)
    assert store["Speaker_Shadow"].visible is True
    assert store["Dialogue_Shadow"].color[:3] == (0.02, 0.03, 0.08)
    # choice shadows: visible choice gets the dark twin, hidden does not
    assert store["choice_0_shadow"].visible is True
    assert store["choice_1_shadow"].visible is False


def test_apply_world_ui_neutral_when_no_character_color():
    store = make_store(ALL_NAMES)
    p = build_world_ui({"type": "say", "text": "narration"})
    p["choices"] = []
    apply_world_ui(lambda n: store.get(n), p)
    assert store["Speaker_Text"].color == contract.DEFAULT_TEXT_COLOR


def test_set_font_color_change_guard():
    o = FakeObj()
    _set_font_color(o, (0.5, 0.5, 0.5, 1.0))
    first = o.writes
    _set_font_color(o, (0.5, 0.5, 0.5, 1.0))   # same value: no rewrite
    assert o.writes == first
    _set_font_color(o, (0.9, 0.9, 0.9, 1.0))   # different: writes again
    assert o.writes == first + 1


def test_shadow_names_are_stable_contract_constants():
    # the runtime and the bake tools must agree on these, forever
    assert contract.SPEAKER_SHADOW == "Speaker_Shadow"
    assert contract.DIALOGUE_SHADOW == "Dialogue_Shadow"
    assert contract.CHOICE_SHADOW_SUFFIX == "_shadow"
    assert len(contract.SHADOW_OFFSET) == 3


# ---------------------------------------------------------------- binary
BIN = Path("/opt/upbge/upbge-0.50-linux-x64/blender")

@pytest.mark.skipif(not BIN.exists(), reason="UPBGE binary not present")
def test_template_carries_styled_text_and_shadows():
    """The baked template: DejaVu on every FONT curve, extrude+bevel, the
    rewind italic shear, bold speaker/choice labels, and the 11 shadow
    twins with the dark tint."""
    import subprocess
    blend = Path(__file__).resolve().parents[1] / "blend" / "UPVN_Template.blend"
    expr = (
        "import bpy;"
        "fonts=[o for o in bpy.data.objects if o.type=='FONT'];"
        "print('N_FONT', len(fonts));"
        "print('N_UNSTYLED', sum(1 for o in fonts if o.data.font is None"
        "  or o.data.font.name == 'Bfont Regular' or o.data.extrude <= 0"
        "  or o.data.bevel_depth <= 0));"
        "print('REWIND_SHEAR', round(bpy.data.objects['Rewind_Text'].data.shear, 3));"
        "sp = bpy.data.objects['Speaker_Text'];"
        "print('SPEAKER_BOLD', 'Bold' in sp.data.font.name);"
        "shadows=[o for o in fonts if 'hadow' in o.name];"
        "print('N_SHADOW', len(shadows));"
        "print('SHADOW_DARK', all(tuple(round(c,2) for c in o.color)"
        "  == (0.02, 0.03, 0.08, 1.0) for o in shadows));"
        "ch = bpy.data.objects['choice_0_text'];"
        "print('CHOICE_BOLD', 'Bold' in ch.data.font.name)"
    )
    out = subprocess.run([str(BIN), "--background", str(blend),
                          "--python-expr", expr],
                         capture_output=True, text=True, timeout=120)
    lines = out.stdout + out.stderr

    def val(tag):
        for l in lines.splitlines():
            if l.startswith(tag):
                return l.split(None, 1)[1]
        return None

    assert val("N_FONT") is not None, lines[-500:]
    assert int(val("N_FONT")) >= 24                    # 13 mains + 11 shadows
    assert val("N_UNSTYLED") == "0", lines[-500:]
    assert float(val("REWIND_SHEAR")) == pytest.approx(0.18, abs=0.01)
    assert val("SPEAKER_BOLD") == "True"
    assert val("CHOICE_BOLD") == "True"
    assert int(val("N_SHADOW")) == 11
    assert val("SHADOW_DARK") == "True"
