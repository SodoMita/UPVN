"""M26g regression: UPVN_GameBuilder.write() must never destroy an existing
script (and must place additions BEFORE `return`, not after it).

Field bugs (found live in the UPBGE GUI, 2026-09-11):
  1. When the merge had nothing to insert, write() fell through to a full
     regeneration from the constructor's *placeholder* labels — every
     existing label body was replaced with `"Empty label."`. One click of
     "Create UPVN Project" emptied the M25 smoke game script.
  2. Additions were inserted after the label's trailing `return` —
     unreachable dead code in the running game.
"""

import sys
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "blend"))

from upvn_editor_addon import UPVN_GameBuilder  # noqa: E402

SMOKE = """\
# Example 20 — Smoke Game
define e = Character("Eileen")

default route = "none"

label start:
    scene bg classroom
    show eileen happy at center
    e "Line one."
    e "Line two."

    menu:
        "Go left":
            $ route = "left"
            jump left

        "Go right":
            $ route = "right"
            jump right

label left:
    e "You chose left."
    jump save_test

label right:
    e "You chose right."
    jump save_test

label save_test:
    e "Save, load, rollback, and continue from here."
    e "Route is [route]."
    return
"""


@pytest.fixture
def smoke(tmp_path):
    p = tmp_path / "script.rpy"
    p.write_text(SMOKE, encoding="utf-8")
    return p


def test_add_say_inserts_before_return(smoke):
    b = UPVN_GameBuilder(str(smoke))
    b.ensure_label("save_test")
    b.add_say("e", "A brand new line.")
    b.write()
    text = smoke.read_text(encoding="utf-8")
    # new line present...
    assert 'e "A brand new line."' in text
    # ...and BEFORE the return of save_test (reachable code)
    idx_new = text.index('e "A brand new line."')
    idx_ret = text.index("return", text.index("label save_test:"))
    assert idx_new < idx_ret, "additions must be inserted before `return`"
    # everything else survived
    for needle in ('e "You chose left."', 'e "Line two."', '"Go right":',
                   "jump save_test", "default route"):
        assert needle in text


def test_duplicate_addition_leaves_file_untouched(smoke):
    before = smoke.read_text(encoding="utf-8")
    b = UPVN_GameBuilder(str(smoke))
    b.ensure_label("start")
    b.add_scene("bg classroom")          # line already exists in `start`
    b.write()
    assert smoke.read_text(encoding="utf-8") == before, (
        "nothing to add must mean nothing is written — the old code fell "
        "through to full regeneration and emptied every label"
    )


def test_no_label_is_ever_emptied(smoke):
    """The data-loss signature: 'Empty label.' appearing in a file that
    previously had content."""
    b = UPVN_GameBuilder(str(smoke))
    b.ensure_label("left")
    b.add_say("e", "Another line in left.")
    b.write()
    assert '"Empty label."' not in smoke.read_text(encoding="utf-8")


def test_new_label_block_appended(smoke):
    b = UPVN_GameBuilder(str(smoke))
    b.ensure_label("epilogue")
    b.add_say(None, "The end.")
    b.write()
    text = smoke.read_text(encoding="utf-8")
    assert "label epilogue:" in text
    assert '"The end."' in text
    # original labels intact
    assert 'e "You chose left."' in text
    # epilogue block gets its own return
    assert "return" in text[text.index("label epilogue:"):]


def test_new_define_inserted_after_existing_defines(smoke):
    b = UPVN_GameBuilder(str(smoke))
    b.add_character("s", "Sylvie", "#c8c8ff")
    b.ensure_label("start")
    b.add_say("s", "Hello.")
    b.write()
    lines = smoke.read_text(encoding="utf-8").splitlines()
    defines = [i for i, l in enumerate(lines) if l.strip().startswith("define ")]
    assert len(defines) == 2
    assert lines[defines[1]].startswith("define s =")
    # still before the first label
    first_label = next(i for i, l in enumerate(lines) if l.strip().startswith("label "))
    assert defines[1] < first_label


def test_fresh_project_still_generates_full_script(tmp_path):
    p = tmp_path / "new" / "script.rpy"
    b = UPVN_GameBuilder(str(p))
    b.add_character("e", "Eileen", "#c8ffc8")
    b.ensure_label("start")
    b.add_say("e", "Hello from Blender!")
    b.write()
    text = p.read_text(encoding="utf-8")
    assert "define e = Character" in text
    assert "label start:" in text
    assert 'e "Hello from Blender!"' in text


def test_menu_addition_creates_jump_targets(smoke):
    b = UPVN_GameBuilder(str(smoke))
    b.ensure_label("start")
    b.add_menu("What do you do?", [("Ask her", "ask"), ("Wait", "wait")])
    b.write()
    text = smoke.read_text(encoding="utf-8")
    assert "menu:" in text
    assert '"Ask her":' in text
    assert "label ask:" in text and "label wait:" in text
    # the menu must be reachable: before save-block's... it's in `start`,
    # which has no trailing return — insert before the next label then
    start_i = text.index("label start:")
    left_i = text.index("label left:")
    assert text.index("menu:", start_i) < left_i


def test_placeholder_empty_label_is_cleaned_up(tmp_path):
    """M27 (e16c666) behaviour folded into the non-destructive write: when
    real content enters a block that only carried build_rpy's
    `"Empty label."` placeholder, the placeholder line is dropped."""
    p = tmp_path / "script.rpy"
    p.write_text('define e = Character("Eileen")\n\nlabel start:\n    "Empty label."\n    return\n', encoding="utf-8")
    b = UPVN_GameBuilder(str(p))
    b.ensure_label("start")
    b.add_say("e", "Real line.")
    b.write()
    text = p.read_text(encoding="utf-8")
    assert '"Empty label."' not in text
    assert 'e "Real line."' in text
    assert "return" in text
