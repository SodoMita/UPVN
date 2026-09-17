"""Wire the VNController logic bricks (Always -> Python[upvn_launcher]).

bpy.ops.logic.* SEGFAULTs in `--background` mode on UPBGE 0.50/Blender 5.0 and
has no data-API equivalent (obj.game.sensors has no .new()), so this tool runs
the EDITOR in GUI mode on whatever display is available (headless sway/Xvfb)
and quits when done. Safe to re-run (idempotent).

Usage (desktop up, e.g. after tools/desktop_sway.sh):
  DISPLAY=:0 LIBGL_ALWAYS_SOFTWARE=1 <upbge>/blender <blend> --python tools/wire_bricks_gui.py
or simply:
  tools/wire_bricks_gui.py <blend>          # wraps the call above
"""
import os
import subprocess
import sys

try:  # present only when executed inside Blender
    import bpy
except ImportError:  # pragma: no cover - CLI wrapper path
    bpy = None


def wire() -> None:
    o = bpy.data.objects.get("VNController")
    if o is None:
        print("WIRE_FAIL no VNController")
        return
    if not any(s.name == "Always" for s in o.game.sensors):
        bpy.ops.logic.sensor_add(type="ALWAYS", object="VNController",
                                 name="Always")
    if not any(c.name == "UPVN_Main" for c in o.game.controllers):
        bpy.ops.logic.controller_add(type="PYTHON", object="VNController",
                                     name="UPVN_Main")
    sen = o.game.sensors.get("Always")
    con = o.game.controllers.get("UPVN_Main")
    try:
        sen.use_pulse_true_level = True
    except Exception:
        pass
    for attr in ("frequency", "trigger_frequency"):
        if hasattr(sen, attr):
            setattr(sen, attr, 0)
    con.text = bpy.data.texts.get("upvn_launcher")
    try:
        con.link(sensor=sen)
    except Exception as e:  # pragma: no cover
        print("LINK_FAIL", e)
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    print("BRICKS_OK",
          [(x.name, x.type) for x in o.game.sensors],
          [(c.name, c.type, c.text.name if c.text else None)
           for c in o.game.controllers])
    bpy.ops.wm.quit_blender()


if __name__ == "__main__":
    if bpy is not None and not bpy.app.background:
        wire()
    elif bpy is None:
        # invoked as a CLI wrapper: re-exec ourselves inside GUI-mode Blender
        blend = sys.argv[1]
        upbge = os.environ.get("UPBGE_BIN",
                               "/opt/upbge/upbge-0.50-linux-x64/blender")
        env = dict(os.environ, DISPLAY=os.environ.get("DISPLAY", ":0"),
                   LIBGL_ALWAYS_SOFTWARE="1")
        r = subprocess.run([upbge, blend, "--python", __file__], env=env,
                           capture_output=True, text=True, timeout=300)
        ok = "BRICKS_OK" in r.stdout
        print(r.stdout[-800:])
        sys.exit(0 if ok else 1)
    else:
        print("WIRE_FAIL: run in GUI mode (background bpy.ops.logic segfaults)")
        sys.exit(1)
