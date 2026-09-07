import pytest
from pathlib import Path
from engine.script.parser import parse_file, ParseError

GALLERY = Path("examples/11_syntax_error_gallery")

# Map file -> expected hint substring
EXPECTED = {
    "bad_jump_colon.rpy": "does not take a colon",
    "bad_indent.rpy": "expected 4 spaces",
    "bad_menu_no_colon.rpy": "menu needs a colon",
    "bad_menu_choice_no_colon.rpy": "missing colon",
    "bad_label_no_colon.rpy": 'label needs a colon',
    "bad_define_missing_parens.rpy": "missing parentheses",
    "bad_default_call.rpy": "must be a literal",
    "bad_assign_no_op.rpy": "invalid assignment",
    "bad_unknown.rpy": "unknown statement",
    # declarative forms (M15)
    "bad_state_type.rpy": "type mismatch",
    "bad_character_no_colon.rpy": "character block needs a colon",
    "bad_set_no_op.rpy": "set needs an operator",
    "bad_end_unexpected.rpy": "unexpected 'end'",
    "bad_choice_outside_menu.rpy": "only valid inside a menu",
}

def test_gallery_all_fail_with_hint():
    for fname, hint in EXPECTED.items():
        path = GALLERY / fname
        assert path.exists(), f"missing {path}"
        with pytest.raises(ParseError) as ei:
            parse_file(str(path))
        msg = str(ei.value)
        assert hint.lower() in msg.lower(), f"{fname}: expected hint {hint!r} in {msg!r}"
        # must contain line:col and Hint:
        assert "Hint:" in msg, f"{fname} missing Hint"
        assert ":" in msg.splitlines()[0], f"{fname} missing file:line:col"

def test_good_scripts_still_parse():
    for good in Path("examples").rglob("script.rpy"):
        # skip gallery (they are bad)
        if "11_syntax" in str(good):
            continue
        # should not raise
        d = parse_file(str(good))
        assert "start" in d["labels"]

def test_validate_tool():
    import subprocess, sys
    # good file should exit 0
    r = subprocess.run([sys.executable, "-m", "tools.validate", "examples/00_minimal_dialogue/script.rpy"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr + r.stdout
    assert "OK" in r.stdout
    # bad file should exit 1 and contain Hint
    r = subprocess.run([sys.executable, "-m", "tools.validate", "examples/11_syntax_error_gallery/bad_jump_colon.rpy"], capture_output=True, text=True)
    assert r.returncode != 0
    assert "Hint" in r.stderr or "Hint" in r.stdout
