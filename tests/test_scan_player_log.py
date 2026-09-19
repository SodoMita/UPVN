"""CI player-log scanner: crash/error fails, host noise does not."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import scan_player_log as scan


NOISE = """\
Blender 5.0.1
AL lib: (EE) ALCjackPlayback_open: JACK error
libGL error: MESA-LOADER failed
WARN (bke.animrig): something
[probe] choice0col z=1.97: hit=None
[UPVN] Loaded script /tmp/game/script.rpy (mode=safe, from VNController.script_path)
[UPVN] resolve try '//game/script.rpy' -> '/tmp/x'
"""

CRASH = NOISE + "\nSegmentation fault (core dumped)\n"
TRACE = NOISE + "\nTraceback (most recent call last):\n  File \"frontend.py\", line 1\n"
UPVN_ERR = NOISE + "\n[UPVN] launcher error (shown once) - is the engine/ folder next to\n"
RETRY = NOISE + (
    "\n[UPVN] load with mode=safe failed (unexpected token); "
    "retrying with mode=full\n"
)
NO_SCRIPT = NOISE + "\n[UPVN] WARNING: no game script found — tried: //game/script.rpy\n"


def test_noise_is_clean():
    fails, warns = scan.classify_log(NOISE)
    assert fails == []
    assert warns == []


def test_segfault_fails():
    fails, _ = scan.classify_log(CRASH)
    assert any("Segmentation fault" in x for x in fails)


def test_traceback_fails():
    fails, _ = scan.classify_log(TRACE)
    assert any("Traceback" in x for x in fails)


def test_upvn_launcher_error_fails():
    fails, _ = scan.classify_log(UPVN_ERR)
    assert fails


def test_no_script_warning_fails():
    fails, _ = scan.classify_log(NO_SCRIPT)
    assert fails


def test_retry_full_is_allowed():
    fails, warns = scan.classify_log(RETRY)
    assert fails == []
    assert warns == []


def test_heartbeat_ok(tmp_path):
    hb = tmp_path / "hb.json"
    hb.write_text(json.dumps({
        "label": "start",
        "idx": 2,
        "event": "say",
        "init_errors": [],
        "python_errors": [],
        "payload_errors": [],
        "interp_warnings": [],
    }), encoding="utf-8")
    assert scan.check_heartbeat(hb) == []


def test_heartbeat_missing_and_errors(tmp_path):
    missing = tmp_path / "nope.json"
    assert scan.check_heartbeat(missing)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "label": "start",
        "event": "say",
        "init_errors": ["boom"],
        "interp_warnings": ["x"],
    }), encoding="utf-8")
    problems = scan.check_heartbeat(bad)
    assert any("init_errors" in p for p in problems)
    assert any("interp_warnings" in p for p in problems)


def test_cli_ok_and_fail(tmp_path):
    log = tmp_path / "player.log"
    log.write_text(NOISE, encoding="utf-8")
    hb = tmp_path / "hb.json"
    hb.write_text(json.dumps({"label": "start", "event": "say"}), encoding="utf-8")
    assert scan.main([str(log), "--heartbeat", str(hb), "--require-heartbeat"]) == 0
    log.write_text(CRASH, encoding="utf-8")
    assert scan.main([str(log)]) == 1
    empty = tmp_path / "empty.log"
    empty.write_text("", encoding="utf-8")
    assert scan.main([str(empty)]) == 1
