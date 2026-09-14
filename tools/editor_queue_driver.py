# UPVN editor queue driver — run via UPBGE's --python to make a LIVE editor
# session remotely driveable (the blind-agent QA mechanism from M26g/M26h).
#
# WHY a draw handler (hard-won knowledge, do not "simplify" this away):
#   - bpy.app.timers registered from a --python startup script NEVER pump in
#     the UPBGE 0.50 GUI (the script runs before any window exists);
#   - bpy.app.handlers.load_post does NOT fire for the CLI file argument;
#   - modal-operator event timers started at script time never see TIMER
#     events (same reason — no window yet).
# A SpaceView3D POST_PIXEL draw handler runs on every viewport redraw, which
# is the one mechanism that reliably pumps. The editor only redraws on
# interaction, so the harness forces redraws with harmless numpad view keys
# (xdotool key KP_0 / KP_5) before reading results.
#
# While the embedded game runs (P key), the editor does NOT redraw — the
# game owns the window. That is expected, not a hang: drive the game with
# plain keys and read UPVN_HEARTBEAT (see bge_frontend/frontend.py) instead.
#
# Protocol (JSONL, one command per line, file replaced atomically by the
# writer): {"id": "...", "op": "...", "kwargs": {...}}
#   op "upvn.<name>" -> bpy.ops.upvn.<name>(**kwargs)
#   op "eval"        -> eval(kwargs["expr"]) with bpy bound (NOTE: driver
#                       eval cannot run statements — wrap assignments in
#                       (lambda: (setattr(...), x)[1])(), and separate
#                       statements with commas inside the lambda tuple, not
#                       semicolons)
#   op "ping"        -> liveness probe
#   op "quit"        -> clean editor shutdown
# Results are appended as JSONL to $UPVN_DRV_RESULTS:
#   {"id": ..., "ok": true, "result": "..."} or {"id": ..., "error": ...}
# Heartbeat counter in $UPVN_DRV_HB (one line, beats so far).
#
# Usage:
#   /opt/upbge/.../blender --window-geometry 0 0 1280 720 \
#       --python tools/editor_queue_driver.py blend/UPVN_Template.blend
#   tools/editor_drive.sh '{"id":"v","op":"eval","kwargs":{"expr":"1+1"}}'
import bpy
import json
import os
import traceback

QUEUE = os.environ.get("UPVN_DRV_QUEUE", "/tmp/upvn_cmd_queue.json")
RESULTS = os.environ.get("UPVN_DRV_RESULTS", "/tmp/upvn_cmd_results.jsonl")
HEARTBEAT = os.environ.get("UPVN_DRV_HB", "/tmp/driver_heartbeat")
state = {"beats": 0}


def _write(res):
    with open(RESULTS, "a") as f:
        f.write(json.dumps(res) + "\n")


def handle_queue():
    if not os.path.exists(QUEUE):
        return
    with open(QUEUE) as f:
        lines = [l for l in f.read().splitlines() if l.strip()]
    os.remove(QUEUE)
    for line in lines:
        try:
            cmd = json.loads(line)
        except Exception as e:
            _write({"id": "?", "error": "json: " + str(e)})
            continue
        cid = cmd.get("id")
        op = cmd.get("op", "")
        kw = cmd.get("kwargs", {}) or {}
        try:
            if op == "eval":
                val = eval(kw["expr"], {"bpy": bpy})
                try:
                    val = str(val)
                except Exception:
                    val = "<unprintable>"
                _write({"id": cid, "ok": True, "result": val})
            elif op == "quit":
                _write({"id": cid, "ok": True, "result": "quitting"})
                bpy.ops.wm.quit_blender()
            elif op == "ping":
                _write({"id": cid, "ok": True, "result": "pong"})
            elif op.startswith("upvn."):
                fn = bpy.ops
                for part in op.split("."):
                    fn = getattr(fn, part)
                r = fn(**kw)
                _write({"id": cid, "ok": True, "result": str(r)})
            else:
                _write({"id": cid, "error": "unknown op " + op})
        except Exception as e:
            _write({"id": cid, "error": repr(e),
                    "tb": traceback.format_exc()[-400:]})


def _poll():
    # runs in the draw context: keep it cheap, never raise
    try:
        state["beats"] += 1
        with open(HEARTBEAT, "w") as f:
            f.write(str(state["beats"]))
        handle_queue()
    except Exception as e:
        try:
            _write({"id": "poll", "error": repr(e)})
        except Exception:
            pass


try:
    bpy.types.SpaceView3D.draw_handler_add(_poll, (), 'WINDOW', 'POST_PIXEL')
    print("[driver] draw-handler queue poller installed:", QUEUE)
except Exception as e:
    print("[driver] draw_handler_add failed:", e)
