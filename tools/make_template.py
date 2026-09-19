"""
Generate UPVN_Template.blend via bpy (run inside UPBGE/Blender).

Usage:
  ./upbge-0.50-linux-x64/blender --background --python tools/make_template.py
  # or with explicit output:
  ./upbge-0.50-linux-x64/blender --background --python tools/make_template.py -- blend/my.blend

All numbers (cameras, render, world, even Blender factory defaults) live in
engine/render/scene_settings.py — edit that file, then re-run this script or
press Setup Scene. Do not copy values into this file.

The template is the 2D VN wiring (cameras, UI, sprite pool, controller) plus
an empty VN_3DStage collection. Do not generate a demo classroom here — drop
a real 3D scene into VN_3DStage (or bake one with tools/bake_stage_into_template.py).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.render import scene_settings as ss  # noqa: E402 — single settings file

try:
    import bpy  # noqa: F401
except ImportError:
    bpy = None  # module stays importable headless; main() explains


def main(out_path: Path | None = None):
    if bpy is None:
        raise SystemExit("This script must be run inside Blender/UPBGE with bpy.")
    out_path = out_path or (ROOT / "blend" / "UPVN_Template.blend")

    # clean slate: end up with exactly one scene, VN_Main (Blender forbids
    # removing the last local scene, so rename the factory 'Scene' when alone)
    scene = bpy.data.scenes.get("VN_Main")
    if scene is None:
        if len(bpy.data.scenes) == 1:
            scene = bpy.data.scenes[0]
            scene.name = "VN_Main"
        else:
            scene = bpy.data.scenes.new("VN_Main")
    for sc in list(bpy.data.scenes):
        if sc is not scene:
            bpy.data.scenes.remove(sc, do_unlink=True)
    # empty master collection of leftover factory objects
    for ob in list(scene.collection.objects):
        scene.collection.objects.unlink(ob)
    try:
        bpy.context.window.scene = scene
    except Exception:
        pass
    bpy.data.orphans_purge()

    # ---- core UPVN wiring (same code as the add-on's Setup Scene) ----
    from blend.upvn_editor_addon import build_vn_scene  # engine discovery runs at import
    ctrl = build_vn_scene(bpy, scene_name=ss.SCENE_NAME,
                          script_path=ss.SCRIPT_PATH_DEFAULT)

    # VN_3DStage is created empty by build_vn_scene. Author a real 3D scene
    # into that collection; this generator does not invent placeholder rooms.

    # ---- save ----
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_path))
    size_kb = out_path.stat().st_size // 1024
    bricks = ctrl.get("upvn_bricks", "no")
    n_ctrl = len(ctrl.game.controllers) if hasattr(ctrl, "game") else 0
    n_sens = len(ctrl.game.sensors) if hasattr(ctrl, "game") else 0
    print(f"[make_template] Saved {out_path} ({size_kb}KB) — VNController bricks: "
          f"{n_ctrl} controller, {n_sens} sensors, "
          f"script_path={ctrl.get('script_path')}, upvn_root={ctrl.get('upvn_root')}, "
          f"bricks={bricks}")
    if n_ctrl == 0:
        print("[make_template] NOTE: no logic bricks in --background mode (bpy.ops.logic "
              "needs the UPBGE UI). Open the .blend in UPBGE, enable the UPVN add-on and "
              "press 'Setup Scene' once — it adds the Always→Python brick and saves.")
    # interactive runs (xvfb/UI): quit so the calling shell can proceed
    if not getattr(bpy.app, "background", True):
        try:
            bpy.ops.wm.quit_blender()
        except Exception:
            pass
    return out_path


if __name__ == "__main__":
    args = [a for a in sys.argv if not a.startswith("-") and a != "python" and a != "blender"]
    out = Path(args[-1]) if args and args[-1].endswith(".blend") else None
    main(out)
