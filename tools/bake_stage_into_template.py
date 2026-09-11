#!/usr/bin/env python3
"""M26d: bake a 3D stage blend INTO a game blend (template or packaged game).

Live-measured on UPBGE 0.50.0 blenderplayer: `bge.logic.LibLoad` SEGFAULTS on
ANY file (Scene/Collection/Library types, load_actions on/off, even a copy of
the running template — kernel sig=11 every time). Until that is fixed upstream
(or UPVN_ENABLE_LIBLOAD=1 on a fixed build), stages ship BAKED into the game
blend. This tool performs that bake with the conventions the runtime expects:

- stage GEOMETRY only — every CAMERA in the stage file is excluded (a second
  camera in the scene coincided with the viewport rendering from it instead of
  Camera_UI, dropping all ortho UI);
- character TEMPLATES (same names the script's `show3d <asset>` uses, e.g.
  "eileen") are parked at (30, -3, -30), far outside the Camera_UI frustum
  (camera at y=-10 looking +Y; UI slab is x[-7.5,7.5] z[-4.2,4.2]) —
  collection-excluded objects do not exist in the runtime at all and
  addObject() rejects active objects, so StageManager.spawn() REPOSITIONS the
  parked master onto the requested marker;
- markers (empty "marker_*") and presets ("preset_*"/"Preset_*") are linked
  into the scene (state-only anchors today);
- object ACTIONS come along (fake-user kept) so `anim <target> <name>` can
  playAction them.

Usage (needs the UPBGE/blender binary on PATH or UPVN_BLENDER env):
  python tools/bake_stage_into_template.py \
      --stage examples/10_full_sample_game/stages/classroom_3d.blend \
      --game blend/UPVN_Template.blend --out build/game_baked.blend
"""
import argparse
import os
import sys
import tempfile

EXCLUDE_SUFFIX = ("Camera",)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True)
    ap.add_argument("--game", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--script", default=None,
                    help="optional .rpy path to write into VNController.script_path")
    args = ap.parse_args()

    code = f'''
import bpy
SRC = {args.stage!r}
GAME = {args.game!r}
OUT = {args.out!r}
SCRIPT = {args.script!r}

bpy.ops.wm.open_mainfile(filepath=GAME)
sc = bpy.context.scene

with bpy.data.libraries.load(SRC, link=False) as (data_from, data_to):
    # M26d: NO cameras — any second camera coincided with the viewport
    # rendering from it instead of Camera_UI (ortho UI disappeared).
    data_to.objects = [n for n in data_from.objects
                       if not n.startswith({EXCLUDE_SUFFIX!r})
                       and not n.split(".")[0].endswith({EXCLUDE_SUFFIX!r})]
    data_to.actions = list(data_from.actions)

TEMPLATE_NAMES = {{"eileen", "sylvie"}}  # extend per game: show3d asset names
for ob in data_to.objects:
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    sc.collection.objects.link(ob)
    if ob.name.split(".")[0] in TEMPLATE_NAMES:
        ob.location = (30.0, -3.0, -30.0)  # parked out of the UI frustum

act = data_to.actions[0] if data_to.actions else None
if act:
    act.use_fake_user = True

if SCRIPT:
    for p in bpy.data.objects['VNController'].game.properties:
        if p.name == 'script_path':
            p.value = SCRIPT

bpy.ops.wm.save_mainfile(filepath=OUT, compress=True)
print("BAKED", OUT, "objects:", len(data_to.objects),
      "actions:", [a.name for a in data_to.actions])
'''
    # run inside the real binary (logic bricks/game props need it)
    exe = os.environ.get("UPVN_BLENDER")
    if not exe:
        for cand in ("/opt/upbge/upbge-0.50-linux-x64/blender", "blender"):
            if os.path.exists(cand) or os.system(f"command -v {cand} >/dev/null 2>&1") == 0:
                exe = cand
                break
    if not exe:
        print("blender binary not found (set UPVN_BLENDER)", file=sys.stderr)
        return 2
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        path = f.name
    rc = os.system(f'{exe} --background --python "{path}"')
    os.unlink(path)
    if rc == 0:
        # M26e: the blend's embedded launcher imports engine/bge_frontend
        # relative to the blend (//). Without them next to --out the player
        # dies with "No module named 'bge_frontend'" (live-measured). Copy
        # the runtime tree so the output is immediately playable.
        out_dir = os.path.dirname(os.path.abspath(args.out))
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        import shutil
        for folder in ("engine", "bge_frontend"):
            src = os.path.join(root, folder)
            dst = os.path.join(out_dir, folder)
            if os.path.isdir(src) and not os.path.isdir(dst):
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", ".pytest_cache"))
                print(f"copied runtime: {dst}")
    return 1 if rc else 0


if __name__ == "__main__":
    sys.exit(main())
