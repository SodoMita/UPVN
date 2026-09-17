"""One-shot template refactor (TASK: sprite position empties).

Replaces the five per-position image planes (Sprite_far_left..Sprite_far_right)
with five Pos_<pos> empties (single source of truth for stage layout) plus ONE
pool plane (Sprite_pool) that the renderer claims/duplicates per sprite tag.

Run:
  <upbge>/blender --background blend/UPVN_Template.blend \
      --python tools/refactor_sprite_positions.py
Idempotent: re-running only reports current state.
"""
import os
import sys

import bpy

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
try:
    from engine.render.contract import POSITIONS, SPRITE_POSITIONS
except Exception:  # pragma: no cover - fallback literals
    SPRITE_POSITIONS = ("far_left", "left", "center", "right", "far_right")
    POSITIONS = {
        "far_left": (-6.0, -0.15, 0.0),
        "left": (-3.5, -0.15, 0.0),
        "center": (0.0, -0.15, 0.0),
        "right": (3.5, -0.15, 0.0),
        "far_right": (6.0, -0.15, 0.0),
    }


def main() -> None:
    made = []
    for pos in SPRITE_POSITIONS:
        name = f"Pos_{pos}"
        empty = bpy.data.objects.get(name)
        if empty is None:
            empty = bpy.data.objects.new(name, None)
            bpy.context.collection.objects.link(empty)
            made.append(name)
        empty.empty_display_type = "PLAIN_AXES"
        empty.empty_display_size = 0.6
        empty.location = POSITIONS[pos]

    pool = bpy.data.objects.get("Sprite_pool")
    if pool is None:
        src = bpy.data.objects.get("Sprite_center")
        if src is not None:
            src.name = "Sprite_pool"
            pool = src
    removed = []
    for pos in SPRITE_POSITIONS:
        ob = bpy.data.objects.get(f"Sprite_{pos}")
        if ob is not None and (pool is None or ob.name != pool.name):
            removed.append(ob.name)
            bpy.data.objects.remove(ob, do_unlink=True)

    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    left = [o.name for o in bpy.data.objects
            if o.name.startswith("Sprite") or o.name.startswith("Pos_")]
    print("REFACTOR_OK made=%s removed=%s left=%s" % (made, removed, sorted(left)))


main()
