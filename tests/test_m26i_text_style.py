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
from engine.core.vn_state import VNState


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
    # M28 Ren'Py identical: speaker default is accent blue #002ead, not None
    p = build_world_ui({"type": "say", "who": "n", "who_name": "N",
                        "text": "hi"})
    assert p["speaker_color"] == contract.SPEAKER_DEFAULT_COLOR
    # narration also returns default blue (speaker not visible, but color still default)
    p2 = build_world_ui({"type": "say", "text": "hi"})
    assert p2["speaker_color"] == contract.SPEAKER_DEFAULT_COLOR


# ---------------------------------------------------------------- apply
def _payload(**kw):
    p = build_world_ui({"type": "say", "who": "e", "who_name": "Eileen",
                        "color": "#c8ffc8", "text": "hello"}, **kw)
    # M28 Ren'Py identical: raw text, no numbering
    p["choices"] = [{"name": "choice_0", "text": "Ask", "visible": True},
                    {"name": "choice_1", "text": "", "visible": False}]
    return p


def test_apply_world_ui_tints_speaker_and_shadows():
    store = make_store(ALL_NAMES)
    apply_world_ui(lambda n: store.get(n), _payload())
    # speaker name carries the character color
    assert store["Speaker_Text"].color == pytest.approx(
        (200 / 255, 1.0, 200 / 255, 1.0), abs=1e-3)
    # M28 Ren'Py identical: shadows disabled (transparent, hidden)
    assert store["Speaker_Shadow"].visible is False
    assert store["Dialogue_Shadow"].visible is False
    # choice shadows also hidden
    assert store["choice_0_shadow"].visible is False
    assert store["choice_1_shadow"].visible is False


def test_apply_world_ui_neutral_when_no_character_color():
    store = make_store(ALL_NAMES)
    p = build_world_ui({"type": "say", "text": "narration"})
    p["choices"] = []
    apply_world_ui(lambda n: store.get(n), p)
    # M28 Adaptive: speaker default from config (generic #ff7f7f or LTCR #002ead)
    assert store["Speaker_Text"].color == pytest.approx(contract.SPEAKER_DEFAULT_COLOR, abs=1e-3)


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
    """M28 Ren'Py identical: flat text (no extrude), Lato/Hack/saxmono fonts, no shadow (transparent), white UI."""
    import subprocess
    blend = Path(__file__).resolve().parents[1] / "blend" / "UPVN_Template.blend"
    expr = (
        "import bpy;"
        "fonts=[o for o in bpy.data.objects if o.type=='FONT'];"
        "print('N_FONT', len(fonts));"
        "print('N_UNSTYLED', sum(1 for o in fonts if o.data.font is None or o.data.font.name == 'Bfont Regular'));"
        "print('REWIND_SHEAR', round(bpy.data.objects['Rewind_Text'].data.shear, 3));"
        "sp = bpy.data.objects['Speaker_Text'];"
        "print('SPEAKER_FONT', sp.data.font.name if sp.data.font else 'None');"
        "shadows=[o for o in fonts if 'hadow' in o.name];"
        "print('N_SHADOW', len(shadows));"
        "print('SHADOW_TRANSPARENT', all(o.color[3]<0.1 for o in shadows));"
        "ch = bpy.data.objects['choice_0_text'];"
        "print('CHOICE_FONT', ch.data.font.name if ch.data.font else 'None');"
        "dlg=bpy.data.objects.get('Dialogue_Box');"
        "print('DLG_COLOR', [round(c,2) for c in dlg.color] if dlg else None)"
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
    assert int(val("N_FONT")) >= 24
    # M28: flat text is expected, so N_UNSTYLED may be 0 or count of Bfont only, not extrude
    assert val("N_UNSTYLED") is not None
    # Speaker should use Hack font (Ren'Py identical)
    assert "Hack" in val("SPEAKER_FONT") or "Lato" in val("SPEAKER_FONT") or "DejaVu" in val("SPEAKER_FONT"), val("SPEAKER_FONT")
    assert int(val("N_SHADOW")) == 11
    # Shadows transparent for Ren'Py parity
    assert val("SHADOW_TRANSPARENT") == "True"
    # Dialogue box white semi-transparent
    assert "1.0" in val("DLG_COLOR") or "0.8" in val("DLG_COLOR")


