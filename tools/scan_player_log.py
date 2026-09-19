#!/usr/bin/env python3
"""Scan a blenderplayer log (+ optional heartbeat JSON) for CI failures.

UPBGE itself is noisy (ALSA, Mesa, RNA warnings). Those are allowed.
Crashes, Python tracebacks, and UPVN-authored errors/warnings fail the job.

Usage:
    python tools/scan_player_log.py /tmp/player_run.log
    python tools/scan_player_log.py LOG --heartbeat /tmp/upvn_hb.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Lines that are host/driver noise — never fail the job.
ALLOW = [
    re.compile(p, re.I)
    for p in (
        r"^ALSA",
        r"^AL lib",
        r"libGL",
        r"libEGL",
        r"Mesa",
        r"llvmpipe",
        r"GALLIUM",
        r"GHOST_",
        r"Wayland",
        r"Xwayland",
        r"Gtk-",
        r"^gtk",
        r"OpenGL",
        r"GPUTexture",
        r"GPUShader",
        r"GPU ",
        r"^WARN \(bke",
        r"^WARN \(gpu",
        r"^WARN \(wm",
        r"^Warning:.*(ID user|property|RNA| Copied)",
        r"^Info:",
        r"^Blender",
        r"^UPBGE",
        r"^Writing:",
        r"^Saved:",
        r"^Fra:",
        r"^\[probe\]",
        r"^\[debug_ray\]",
        r"^\[pointer\]",
        r"SDL_AUDIODRIVER",
        r"PulseAudio",
        r"jack server",
        r"Cannot connect to server",
        r"XDG_RUNTIME_DIR",
        r"^$",
    )
]

# Hard failures — crash / abort / missing blend / UPVN load failure.
FAIL = [
    re.compile(p, re.I)
    for p in (
        r"Segmentation fault",
        r"Fatal Python error",
        r"Aborted \(core dumped\)",
        r"Traceback \(most recent call last\)",
        r"blenderplayer:.*error",
        r"Error: Cannot read file",
        r"loading .* failed",
        r"Out of memory",
        r"Killed process .* blenderplayer",
        r"\[UPVN\] launcher error",
        r"\[UPVN\] failed to load",
        r"\[UPVN\] WARNING: no game script found",
        r"\[UPVN\] tick error",
        r"\[UPVN\] world UI sync error",
    )
]

# UPVN-authored warnings/errors that are not on the hard-fail list.
# Missing palette-mode images are allowed (starter has no art files).
UPVN_BAD = re.compile(r"\[UPVN\].*(error|fail|warn)", re.I)
UPVN_OK = re.compile(
    r"(missing image|image not found|no such file|retrying with mode=|"
    r"debug tee|Loaded script|active_camera|gui_par|resolve try)",
    re.I,
)


def _allowed(line: str) -> bool:
    s = line.strip("\n")
    return any(rx.search(s) for rx in ALLOW)


def classify_log(text: str) -> tuple[list[str], list[str]]:
    """Return (fails, warnings)."""
    fails: list[str] = []
    warns: list[str] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if any(rx.search(line) for rx in FAIL):
            fails.append(line)
            continue
        if UPVN_BAD.search(line) and not UPVN_OK.search(line) and not _allowed(line):
            warns.append(line)
    return fails, warns


def check_heartbeat(path: Path) -> list[str]:
    problems: list[str] = []
    if not path.exists():
        return [f"heartbeat missing: {path}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"heartbeat unreadable: {exc}"]
    if not data.get("label"):
        problems.append(f"heartbeat has no label: {data!r}"[:240])
    if data.get("event") in (None, ""):
        problems.append(f"heartbeat has no event type: {data.get('label')!r}")
    for key in ("init_errors", "python_errors", "payload_errors", "interp_warnings"):
        val = data.get(key) or []
        if val:
            problems.append(f"heartbeat {key}: {val!r}"[:300])
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fail CI on player crashes/errors")
    ap.add_argument("log", type=Path)
    ap.add_argument("--heartbeat", type=Path, default=None)
    ap.add_argument(
        "--require-heartbeat",
        action="store_true",
        help="fail when --heartbeat is missing/empty (CI default)",
    )
    args = ap.parse_args(argv)

    if not args.log.exists():
        print(f"FAIL: log not found: {args.log}", file=sys.stderr)
        return 1
    text = args.log.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        print("FAIL: player log is empty (crash before first print?)", file=sys.stderr)
        return 1

    fails, warns = classify_log(text)
    hb_problems: list[str] = []
    if args.heartbeat is not None:
        if args.require_heartbeat or args.heartbeat.exists():
            hb_problems = check_heartbeat(args.heartbeat)
        elif args.require_heartbeat:
            hb_problems = [f"heartbeat missing: {args.heartbeat}"]

    rc = 0
    if fails:
        rc = 1
        print("FAIL: crash/error lines:")
        for ln in fails[:40]:
            print(f"  {ln}")
    if warns:
        rc = 1
        print("FAIL: UPVN warning/error lines:")
        for ln in warns[:40]:
            print(f"  {ln}")
    if hb_problems:
        rc = 1
        print("FAIL: heartbeat:")
        for ln in hb_problems:
            print(f"  {ln}")
    if rc == 0:
        print(f"OK: player log clean ({len(text.splitlines())} lines)"
              + (f", heartbeat {args.heartbeat}" if args.heartbeat else ""))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
