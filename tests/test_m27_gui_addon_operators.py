"""Integration test for UPVN Editor Addon operators in UPBGE.

Verifies that all GUI panel operators execute cleanly, update script.rpy,
maintain clean Ren'Py syntax (no unreachable return statements), and pass
validation/preview end-to-end.
"""

import os
import pathlib
import subprocess
import pytest

UPBGE_BIN = "/opt/upbge/upbge-0.50-linux-x64/blender"


@pytest.mark.skipif(
    not os.path.exists(UPBGE_BIN),
    reason="UPBGE binary not found at " + UPBGE_BIN,
)
def test_addon_all_operators_execute_and_build_valid_script(tmp_path):
    blend = pathlib.Path(__file__).resolve().parents[1] / "blend" / "UPVN_Template.blend"
    test_script_path = tmp_path / "game" / "script.rpy"

    py_code = f"""
import sys, pathlib, os, bpy

addon_path = str(pathlib.Path("{blend.parent}").resolve())
sys.path.insert(0, addon_path)
import upvn_editor_addon
upvn_editor_addon.register()

p = bpy.context.scene.upvn_props
p.project_path = "{test_script_path.as_posix()}"
p.char_id = "a"
p.char_name = "Alice"
p.char_color = (1.0, 0.0, 0.0, 1.0)
p.bg_name = "bg room"
p.speaker = "Alice"
p.dialogue = "Testing addon operators in UPBGE."
p.menu_caption = "Choose your action:"
p.menu_choice1 = "Option A"
p.menu_jump1 = "opt_a"
p.menu_choice2 = "Option B"
p.menu_jump2 = "opt_b"
p.stage_name = "room_3d"

# Execute all panel operators in sequence
assert bpy.ops.upvn.check_engine() == {{'FINISHED'}}
assert bpy.ops.upvn.create_project() == {{'FINISHED'}}
assert bpy.ops.upvn.add_character() == {{'FINISHED'}}
assert bpy.ops.upvn.add_scene() == {{'FINISHED'}}
assert bpy.ops.upvn.add_show() == {{'FINISHED'}}
assert bpy.ops.upvn.add_stage() == {{'FINISHED'}}
assert bpy.ops.upvn.add_dialogue() == {{'FINISHED'}}
assert bpy.ops.upvn.add_menu() == {{'FINISHED'}}
assert bpy.ops.upvn.validate() == {{'FINISHED'}}
assert bpy.ops.upvn.setup_scene() == {{'FINISHED'}}
assert bpy.ops.upvn.check_wiring() == {{'FINISHED'}}
assert bpy.ops.upvn.save_demo() == {{'FINISHED'}}
assert bpy.ops.upvn.preview_arbitrary() == {{'FINISHED'}}
assert bpy.ops.upvn.preview() == {{'FINISHED'}}

print("ALL_OPERATORS_SUCCESS")
"""

    res = subprocess.run(
        [UPBGE_BIN, "--background", str(blend), "--python-expr", py_code],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert "ALL_OPERATORS_SUCCESS" in res.stdout, f"Addon operators failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"

    # Verify script content
    assert test_script_path.exists()
    content = test_script_path.read_text(encoding="utf-8")
    assert 'define a = Character("Alice"' in content
    assert "scene bg room" in content
    assert 'Alice "Testing addon operators in UPBGE."' in content
    assert "menu:" in content
    assert "label opt_a:" in content

    # Ensure no dead code placed after return in label start
    lines = content.splitlines()
    start_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("label start:"):
            start_idx = i
            break
    assert start_idx is not None, "label start: not found in script"

    # Find first 'return' in label start
    first_return = None
    for j in range(start_idx + 1, len(lines)):
        if lines[j].strip().startswith("label "):
            break
        if lines[j].strip() == "return":
            first_return = j
            break

    assert first_return is not None, "return statement missing in label start"
    # Ensure all dialogue and scene statements occur BEFORE the return in label start
    assert any("scene bg room" in lines[k] for k in range(start_idx, first_return)), "scene statement was placed after return!"
    assert any("Alice " in lines[k] for k in range(start_idx, first_return)), "say statement was placed after return!"
