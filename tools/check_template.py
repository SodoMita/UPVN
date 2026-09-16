#!/usr/bin/env python3
"""Verify the shipped template still honours the runtime contracts.

    tools/check_template.py                      # finds UPBGE itself
    tools/check_template.py --blend <file.blend>
    /opt/upbge/.../blender -b blend/UPVN_Template.blend --python tools/check_template.py

Why this exists: the M29 template shipped for weeks with a leftover factory
Cube and a 42-object 3D classroom that painted over every 2D frame, and no
test could see it — the .blend is zstd-compressed, so a byte scan finds
nothing, and the engine's own tests never open the file. The three rules
below are the ones that broke, stated as checks a human or CI can run:

  1. the master collection holds the VN contract and nothing else (a stray
     Cube/Camera/Light in there is drawn in front of the VN planes);
  2. every VN_3DStage object carries a *STRING* game property `upvn_stage`,
     which is what engine/render/stage_manager.py hides for 2D-only scripts
     (a BOOL game property written through the data API reads back as False,
     and an ID property is invisible to the player — both measured);
  3. the VNController still carries its launcher properties, otherwise the
     file is not playable at all.

Exit code is 0 only when every check passes.
"""
from __future__ import annotations

import os
import sys

try:
    import bpy
except ImportError:                                  # pragma: no cover - bpy only
    bpy = None

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_BLEND = os.path.join(REPO, "blend", "UPVN_Template.blend")

# Objects the runtime looks up by name. Keep in sync with engine/render/contract.py
CONTRACT = (
    "BG_Plane", "Dialogue_Box", "Dialogue_Shadow", "Dialogue_Text",
    "Speaker_Text", "Speaker_Shadow", "History_Box", "History_Text",
    "Rewind_Text", "Camera_UI", "Camera_3D", "SUN_Soft", "VNController",
    "Sprite_far_left", "Sprite_left", "Sprite_center", "Sprite_right",
    "Sprite_far_right",
) + tuple(f"choice_{i}" for i in range(9)) \
  + tuple(f"choice_{i}_text" for i in range(9)) \
  + tuple(f"choice_{i}_shadow" for i in range(9))

CONTROLLER_PROPS = ("script_path", "image_mode", "parse_root", "upvn_root",
                    "upvn_bricks", "parse_mode")
VN_COLLECTIONS = ("VN_Backgrounds", "VN_Characters", "VN_UI", "VN_Effects",
                  "VN_3DStage")
STAGE_PROP = "upvn_stage"


def check_structure():
    """1. master collection = the contract, no factory leftovers."""
    problems = []
    scene = bpy.context.scene
    for ob in scene.collection.objects:
        if ob.name not in CONTRACT:
            problems.append(
                f"{ob.name!r} sits in the master collection but is not part of "
                f"the VN contract — a stray object there is drawn over the "
                f"story planes (delete it, or move it into one of "
                f"{', '.join(VN_COLLECTIONS)})")
    missing = [n for n in CONTRACT if n not in bpy.data.objects]
    if missing:
        problems.append(f"contract objects missing from the file: {', '.join(missing)}")
    return problems


def check_stage_flag():
    """2. the 3D stage is stamped with a STRING game property."""
    problems = []
    stage = bpy.data.collections.get("VN_3DStage")
    if stage is None:
        return ["no VN_3DStage collection — `show3d`/`load_stage` scenes have no "
                "baked stage to fall back on"]
    unstamped = []
    wrong_type = []
    for ob in stage.objects:
        prop = ob.game.properties.get(STAGE_PROP)
        if prop is None:
            unstamped.append(ob.name)
        elif prop.type != "STRING" or str(prop.value) not in ("1", "true", "True"):
            wrong_type.append(f"{ob.name}:{prop.type}={prop.value!r}")
    if unstamped:
        problems.append(
            f"{len(unstamped)} VN_3DStage objects have no {STAGE_PROP} game "
            f"property (e.g. {', '.join(unstamped[:4])}) — the runtime cannot "
            f"hide the stage for 2D scripts without it; run Setup Scene")
    if wrong_type:
        problems.append(
            f"{STAGE_PROP} must be a STRING game property with a truthy value, "
            f"else the player reads False: {', '.join(wrong_type[:4])}")
    return problems


def check_controller():
    """3. the file is playable: launcher properties are present."""
    problems = []
    ctrl = bpy.data.objects.get("VNController")
    if ctrl is None:
        return ["VNController object is missing — the game cannot start"]
    props = {p.name: p for p in ctrl.game.properties}
    for name in CONTROLLER_PROPS:
        if name not in props and name not in ("parse_root",):
            problems.append(f"VNController has no {name!r} game property; "
                            f"re-run Setup Scene from the UPVN panel")
    if "script_path" in props:
        value = str(props["script_path"].value)
        if not value:
            problems.append("VNController.script_path is empty — the player will "
                            "start with no story")
    bricks = str(props.get("upvn_bricks").value) if "upvn_bricks" in props else None
    if bricks is None:
        problems.append("VNController has no upvn_bricks marker: the logic bricks "
                        "that run the launcher may be missing (open the file in "
                        "the editor and press Setup Scene)")
    return problems


CHECKS = (("structure", check_structure),
          ("stage flag", check_stage_flag),
          ("controller", check_controller))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    path = DEFAULT_BLEND
    if "--blend" in argv:
        path = os.path.abspath(argv[argv.index("--blend") + 1])

    if bpy is None:
        print("[check_template] run me inside Blender/UPBGE: "
              "blender -b <file.blend> --python tools/check_template.py",
              file=sys.stderr)
        return 2
    if not os.path.exists(path):
        print(f"[check_template] no such blend: {path}", file=sys.stderr)
        return 2
    if os.path.abspath(bpy.data.filepath or "") != path:
        bpy.ops.wm.open_mainfile(filepath=path)

    failures = []
    for label, fn in CHECKS:
        try:
            problems = fn()
        except Exception as exc:                     # a broken file must not
            problems = [f"check raised {type(exc).__name__}: {exc}"]
        if problems:
            print(f"[check_template] FAIL: {label}")
            for p in problems:
                print(f"    file: {os.path.relpath(path, REPO)}")
                print(f"    Hint: {p}")
            failures.extend(problems)
        else:
            print(f"[check_template] ok: {label}")

    if failures:
        print(f"[check_template] {len(failures)} problem(s) — template is not "
              "shippable")
        return 1
    print("[check_template] template is shippable")
    return 0


if bpy is not None:
    # when run with --python inside Blender the return value is ignored, so the
    # process must decide via its exit code explicitly
    code = main()
    if code:
        sys.exit(code)
