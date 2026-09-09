#!/usr/bin/env python3
"""UPVN — Ren'Py project compatibility checker.

Parses every ``.rpy`` / ``.rpym`` file of a real Ren'Py project with the
drop-in ("full") tier, merges the result the way Ren'Py does (one namespace
for the whole ``game/`` directory) and reports:

  * per-file parse results (labels, statements, screens, transforms…),
  * labels that are defined more than once,
  * ``jump`` / ``call`` targets that do not resolve,
  * ``call screen`` targets that are not defined,
  * Ren'Py APIs referenced from ``python:`` / ``$`` code (so you can see what
    the compat layer has to cover),
  * a summary of what the project uses.

Exit code is 0 when every file parses and every jump/call/screen resolves.

Usage:
    python -m tools.check_renpy_project <project-or-game-dir> [--json out.json]
    python -m tools.check_renpy_project /path/to/SomeGame            # uses <dir>/game
    python -m tools.check_renpy_project /path/to/SomeGame/game -v
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.core.vn_errors import ParseError  # noqa: E402
from engine.script.parser import Parser, discover_custom_statements  # noqa: E402

RENPY_API = re.compile(r"\brenpy\.([A-Za-z_]\w*)")
STORE_API = re.compile(r"\bstore\.([A-Za-z_]\w*)")


def find_script_dir(root: Path) -> Path:
    """A Ren'Py project keeps its scripts in ``game/``; accept either."""
    if root.is_dir() and (root / "game").is_dir() and list((root / "game").rglob("*.rpy")):
        return root / "game"
    return root


def collect_statements(nodes, counter: Counter):
    """Count AST node kinds recursively (labels, menus, choices, blocks…)."""
    for node in nodes or []:
        kind = node.get("cmd") or node.get("kind")
        if kind:
            counter[kind] += 1
        for key in ("block", "choices"):
            sub = node.get(key)
            if isinstance(sub, list):
                for item in sub:
                    if isinstance(item, dict):
                        if item.get("block"):
                            collect_statements(item["block"], counter)
                        elif item.get("cmd") or item.get("kind"):
                            collect_statements([item], counter)
        for branch in node.get("branches", []) or []:
            collect_statements(branch.get("block"), counter)


def collect_targets(nodes, out_jumps, out_calls, out_screens):
    """Gather jump/call/call-screen targets, ignoring expression forms."""
    for node in nodes or []:
        kind = node.get("cmd") or node.get("kind")
        if kind == "jump" and node.get("label"):
            out_jumps.append(node["label"])
        elif kind == "call" and node.get("label"):
            out_calls.append(node["label"])
        elif kind == "call_screen" and node.get("screen"):
            out_screens.append(node["screen"])
        for key in ("block", "choices"):
            sub = node.get(key)
            if isinstance(sub, list):
                for item in sub:
                    if isinstance(item, dict):
                        if item.get("block"):
                            collect_targets(item["block"], out_jumps, out_calls, out_screens)
                        elif item.get("cmd") or item.get("kind"):
                            collect_targets([item], out_jumps, out_calls, out_screens)
        for branch in node.get("branches", []) or []:
            collect_targets(branch.get("block"), out_jumps, out_calls, out_screens)


def check_project(root: Path, verbose: bool = False) -> dict:
    game_dir = find_script_dir(root)
    files = sorted(set(list(game_dir.rglob("*.rpy")) + list(game_dir.rglob("*.rpym"))))
    files = [f for f in files if "tl" not in f.relative_to(game_dir).parts] or files

    report = {
        "project": str(root),
        "game_dir": str(game_dir),
        "files": [],
        "parse_errors": [],
        "labels": {},
        "duplicate_labels": [],
        "unresolved_jumps": [],
        "unresolved_calls": [],
        "unresolved_screens": [],
        "renpy_apis": [],
        "totals": {},
    }

    labels: dict = {}
    label_owner: dict = {}
    characters: dict = {}
    screens: dict = {}
    transforms: dict = {}
    statements: Counter = Counter()
    renpy_apis: Counter = Counter()
    jumps, calls, call_screens = [], [], []

    # Pass 1: read everything and find the statement keywords the project
    # registers for itself — a registration in one file makes the keyword legal
    # in every other file, exactly as in Ren'Py.
    sources: dict = {}
    for path in files:
        try:
            sources[path] = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:  # pragma: no cover - unreadable file
            report["parse_errors"].append(
                {"file": str(path.relative_to(game_dir)), "error": str(e)})
    registered = discover_custom_statements(sources.values())
    report["custom_statements"] = sorted(set(registered) - {"testsuite", "testcase"})
    report["custom_statement_errors"] = []

    for path in files:
        rel = str(path.relative_to(game_dir))
        src = sources.get(path)
        if src is None:
            continue
        try:
            parsed = Parser(src, str(path), full=True, require_start=False,
                            custom_statements=registered).parse()
        except ParseError as e:
            report["parse_errors"].append({"file": rel, "line": getattr(e, "lineno", None),
                                           "error": str(e).splitlines()[0]})
            continue
        except Exception as e:  # noqa: BLE001 - report, never crash the checker
            report["parse_errors"].append({"file": rel, "error": f"{type(e).__name__}: {e}"})
            continue

        for err in parsed.get("custom_statement_errors", []):
            report["custom_statement_errors"].append({**err, "file": rel})

        file_labels = parsed.get("labels", {})
        for name, block in file_labels.items():
            if name in label_owner:
                report["duplicate_labels"].append({"label": name, "files": [label_owner[name], rel]})
            label_owner[name] = rel
            labels[name] = block
        characters.update(parsed.get("characters", {}))
        screens.update(parsed.get("screens", {}))
        transforms.update(parsed.get("transforms", {}))

        per_file: Counter = Counter()
        for block in file_labels.values():
            collect_statements(block, per_file)
            collect_statements(block, statements)
        for block in file_labels.values():
            collect_targets(block, jumps, calls, call_screens)

        for code in parsed.get("init_python", []):
            renpy_apis.update(RENPY_API.findall(code or ""))
        for block in file_labels.values():
            for node in block:
                if (node.get("cmd") or node.get("kind")) == "python":
                    renpy_apis.update(RENPY_API.findall(node.get("code", "")))

        report["files"].append({
            "file": rel,
            "labels": len(file_labels),
            "label_names": sorted(file_labels)[:12] if verbose else None,
            "characters": len(parsed.get("characters", {})),
            "screens": len(parsed.get("screens", {})),
            "transforms": len(parsed.get("transforms", {})),
            "init_python_lines": len(parsed.get("init_python", [])),
            "statements": sum(per_file.values()),
        })

    report["labels"] = {name: label_owner[name] for name in sorted(labels)}
    report["unresolved_jumps"] = sorted({t for t in jumps if t not in labels})
    report["unresolved_calls"] = sorted({t for t in calls if t not in labels})
    report["unresolved_screens"] = sorted({t for t in call_screens if t not in screens})
    report["renpy_apis"] = [{"name": f"renpy.{k}", "uses": v}
                            for k, v in renpy_apis.most_common()]
    report["totals"] = {
        "files": len(files),
        "files_parsed": len(report["files"]),
        "files_failed": len(report["parse_errors"]),
        "labels": len(labels),
        "characters": len(characters),
        "screens": len(screens),
        "transforms": len(transforms),
        "statements": sum(statements.values()),
        "start_label": "start" in labels,
        "statement_kinds": dict(statements.most_common()),
    }
    return report


def smoke_run(root: Path, choices, max_steps: int = 500) -> dict:
    """Load the merged project and run it headless in drop-in compat mode.

    Proves the *interpreter* survives a real game, not just the parser: the
    story is executed, ``python:`` failures are collected instead of raised.
    """
    from engine.core.vn_controller import VNController

    out = {"ok": False, "events": 0, "init_errors": [], "python_errors": [], "error": None}
    try:
        controller = VNController(script_path=find_script_dir(root), mode="full", compat=True)
        controller.load()
        trace = controller.interp.run_headless(choices=list(choices), max_steps=max_steps)
        out["events"] = len(trace)
        out["init_errors"] = list(controller.interp.init_errors)[:20]
        out["python_errors"] = list(controller.interp.python_errors)[:20]
        out["say_events"] = [e.get("text", "")[:80] for e in trace if e.get("type") == "say"][:5]
        out["ok"] = True
    except Exception as e:  # noqa: BLE001 - reported, never a traceback to the author
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Check a real Ren'Py project against UPVN's parser")
    ap.add_argument("project", help="project directory (or its game/ directory)")
    ap.add_argument("-v", "--verbose", action="store_true", help="list label names per file")
    ap.add_argument("--json", dest="json_out", help="write the full report as JSON")
    ap.add_argument("--run", action="store_true",
                    help="also run the game headless (drop-in compat mode) as a smoke test")
    ap.add_argument("--choices", default="0,0,0,0,0",
                    help="menu choices for --run (default 0,0,0,0,0)")
    ap.add_argument("--max-steps", type=int, default=500, help="event cap for --run")
    args = ap.parse_args(argv)

    root = Path(args.project).expanduser()
    if not root.exists():
        print(f"not found: {root}", file=sys.stderr)
        return 2

    rep = check_project(root, verbose=args.verbose)
    t = rep["totals"]

    failed = t["files_failed"]
    suffix = "" if not failed else f", {failed} failed"
    print(f"Ren'Py compatibility check — {rep['project']}")
    print(f"  game dir      : {rep['game_dir']}")
    print(f"  files         : {t['files_parsed']}/{t['files']} parsed{suffix}")
    print(f"  labels        : {t['labels']} (start: {'yes' if t['start_label'] else 'NO'})")
    print(f"  characters    : {t['characters']}   screens: {t['screens']}   transforms: {t['transforms']}")
    print(f"  statements    : {t['statements']}")
    if rep["parse_errors"]:
        print(f"\nPARSE ERRORS ({len(rep['parse_errors'])}):")
        for e in rep["parse_errors"][:20]:
            print(f"  {e['file']}:{e.get('line', '?')}  {e['error']}")
    if rep["duplicate_labels"]:
        print(f"\nDUPLICATE LABELS ({len(rep['duplicate_labels'])}):")
        for d in rep["duplicate_labels"][:20]:
            print(f"  {d['label']}  in {', '.join(d['files'])}")
    for key, title in (("unresolved_jumps", "UNRESOLVED JUMPS"),
                       ("unresolved_calls", "UNRESOLVED CALLS"),
                       ("unresolved_screens", "UNRESOLVED SCREENS")):
        if rep[key]:
            print(f"\n{title} ({len(rep[key])}):")
            for name in rep[key][:20]:
                print(f"  {name}")
    if rep["renpy_apis"]:
        print(f"\nrenpy.* APIs used by python: blocks ({len(rep['renpy_apis'])}):")
        print("  " + ", ".join(f"{a['name']}×{a['uses']}" for a in rep["renpy_apis"][:24]))
    if args.verbose:
        print("\nper file:")
        for f in rep["files"]:
            print(f"  {f['file']:<50} labels={f['labels']:<4} statements={f['statements']:<6} "
                  f"screens={f['screens']:<3} init_py={f['init_python_lines']}")
            if f.get("label_names"):
                print(f"      {', '.join(f['label_names'])}")

    if args.run:
        choices = [int(x) for x in args.choices.split(",") if x.strip() != ""]
        res = smoke_run(root, choices, args.max_steps)
        rep["smoke_run"] = res
        print("\nHEADLESS SMOKE RUN (drop-in compat):")
        if not res["ok"]:
            print(f"  FAILED: {res['error']}")
        else:
            print(f"  events: {res['events']}   init python errors: {len(res['init_errors'])}"
                  f"   python: errors: {len(res['python_errors'])}")
            for line in res.get("say_events", []):
                print(f"    say: {line}")
            for err in res["init_errors"][:5]:
                print(f"    init: {err.splitlines()[0][:120]}")
            for err in res["python_errors"][:5]:
                print(f"    python: {err[:120]}")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rep, indent=2), encoding="utf-8")
        print(f"\nreport written to {args.json_out}")

    ok = not rep["parse_errors"] and not rep["unresolved_jumps"] and not rep["unresolved_calls"]
    if args.run:
        ok = ok and rep.get("smoke_run", {}).get("ok", False)
    print("\nRESULT: " + ("OK — every file parsed and every jump/call resolves"
                          if ok else "problems found (see above)"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
