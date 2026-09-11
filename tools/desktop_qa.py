#!/usr/bin/env python3
"""Drive the running UPVN player from outside and assert on what it drew.

Companion to tools/desktop_run.sh for GUI QA (agent + human). The player's
stdout is discarded, so state comes from the UPVN_HEARTBEAT json file and
appearance comes from a grim screenshot; keys are retried until the heartbeat
agrees, because XTest→XWayland drops synthetic events.

    tools/desktop_qa.py keys space space h --shot backlog --expect '{"event":"menu"}'
    tools/desktop_qa.py status
    tools/desktop_qa.py shot /tmp/x.png

Env: UPVN_WL_DIR (sway runtime dir, default /tmp/wl-upvn), UPVN_HEARTBEAT,
UPVN_QA_OUT (screenshot dir, default <repo>/tmp/qa).
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WL = os.environ.get("UPVN_WL_DIR", "/tmp/wl-upvn")
HB = os.environ.get("UPVN_HEARTBEAT", "/tmp/upvn_hb.json")
OUT = Path(os.environ.get("UPVN_QA_OUT", str(ROOT / "tmp" / "qa")))


def env():
    e = dict(os.environ)
    e.setdefault("XDG_RUNTIME_DIR", WL)
    if Path(WL, "env.sh").exists():
        for line in Path(WL, "env.sh").read_text().splitlines():
            if line.startswith("export "):
                k, _, v = line[7:].partition("=")
                e.setdefault(k, v)
    for k in ("WAYLAND_DISPLAY",):
        if k not in e or not e[k]:
            sock = [p for p in os.listdir(WL) if p.startswith("wayland-") and "lock" not in p] \
                if os.path.isdir(WL) else []
            if sock:
                e[k] = sorted(sock)[0]
    return e


def win_id(e):
    r = subprocess.run(["xdotool", "search", "--name", "UPVN_Template"],
                       capture_output=True, text=True, env=e, timeout=20)
    for line in r.stdout.split():
        if line.strip().isdigit():
            return line.strip()
    return None


# xdotool has its own key-name table and silently *ignores* names it does not
# know ("No such key name 'PageUp'") — the key never reaches the window and the
# run looks like an engine bug. Translate the names a VN manual actually uses.
KEY_ALIASES = {
    "PageUp": "Prior", "PageDown": "Next",
    "Home": "Home", "End": "End",
    "Escape": "Escape", "Return": "Return", "Space": "space",
}


def resolve_key(name):
    key = KEY_ALIASES.get(name, name)
    return key


def hb():
    try:
        return json.loads(Path(HB).read_text())
    except Exception:
        return {}


def wait_for(pred, tries=25, delay=0.4):
    for _ in range(tries):
        if pred(hb()):
            return True
        time.sleep(delay)
    return False


def shot(e, name):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{name}.png"
    subprocess.run(["grim", str(p)], env=e, capture_output=True, timeout=30)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "shot", "keys", "wheel"])
    ap.add_argument("rest", nargs="*")
    ap.add_argument("--shot", dest="shot_name")
    ap.add_argument("--expect", default=None, help="json subset to wait for")
    ap.add_argument("--settle", type=float, default=1.2)
    a = ap.parse_args()
    e = env()

    if a.cmd == "status":
        st = hb()
        print(json.dumps(st, indent=2) if st else "no heartbeat file (player down?)")
        return 0 if st else 1
    if a.cmd == "shot":
        p = shot(e, a.rest[0] if a.rest else "shot")
        print(p)
        return 0 if p.exists() else 1

    wid = win_id(e)
    if a.cmd == "wheel":
        if not wid:
            print("FAIL: no player window", file=sys.stderr)
            return 1
        subprocess.run(["xdotool", "windowactivate", wid], env=e, timeout=20)
        subprocess.run(["xdotool", "windowfocus", "--remap", wid], env=e, timeout=20)
        time.sleep(0.4)
        direction = (a.rest or ["up"])[0]
        count = int(a.rest[1]) if len(a.rest) > 1 else 1
        btn = "4" if direction.startswith("up") else "5"
        want = json.loads(a.expect) if a.expect else None
        # XTEST, not `--window`: synthetic (send_event) events are dropped by
        # the SDL/X11 frontend, and the wheel is the main Rewind binding in a
        # VN, so a harness that silently no-ops here reads as a broken engine.
        for i in range(count):
            subprocess.run(["xdotool", "click", btn], env=e, timeout=20)
            time.sleep(a.settle)
        print("state:", json.dumps(hb()))
        if want is not None:
            cur = hb()
            ok = all(cur.get(k) == v or str(cur.get(k)) == str(v) for k, v in want.items())
            print("wheel", direction, count, "->", "OK" if ok else f"MISMATCH want {want}")
            return 0 if ok else 1
        return 0
    if not wid:
        print("FAIL: no player window", file=sys.stderr)
        return 1
    subprocess.run(["xdotool", "windowactivate", wid], env=e, timeout=20)
    time.sleep(0.4)
    want = json.loads(a.expect) if a.expect else None
    fails = 0
    for key in a.rest:
        # A chord needs the modifier held across a logic tick (13-19 fps under
        # llvmpipe) so both halves register — 80 ms. A plain key must NOT: an
        # 80 ms hold spans two ticks and the engine's per-tick `just` edge sees
        # it twice, so one "PageUp" rolled back two lines.
        hold = "80" if "+" in key else "12"
        key = resolve_key(key)
        for attempt in range(3):
            r = subprocess.run(["xdotool", "key", "--window", wid, "--delay", hold, key],
                               env=e, capture_output=True, text=True, timeout=20)
            if "No such key name" in (r.stderr or ""):
                # never let a typoed keymasquerade as a failing feature
                sys.exit(f"xdotool does not know key {key!r}: {r.stderr.strip()}")
            time.sleep(a.settle)
            if want is None:
                break
            cur = hb()
            if all(str(cur.get(k)) == str(v) or cur.get(k) == v for k, v in want.items()):
                break
        else:
            if want is not None:
                print(f"WARN: {key} did not reach {want}; got {hb()}", file=sys.stderr)
                fails += 1
    if a.shot_name:
        print("shot:", shot(e, a.shot_name))
    print("state:", json.dumps(hb()))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
