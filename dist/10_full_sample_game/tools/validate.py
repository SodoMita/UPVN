#!/usr/bin/env python3
"""Validator — checks .rpy syntax with friendly errors (no YAML needed).

Single files are validated on their own and must define `label start:`.
A *directory* is a multi-file game: every file is parsed with
``require_start=False`` (the entry label may live in any file) and `start` is
then checked on the merged project, exactly like the engine loads it.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.script.parser import parse_file, ParseError, discover_custom_statements


def _discover(directory: Path, mode: str):
    """Statement keywords the project registers for itself (full tier only).

    Ren'Py collects `renpy.register_statement()` at init time, so a keyword
    registered in one file is legal in every other file of the project.
    """
    if mode != "full":
        return ()
    srcs = []
    for p in sorted(set(list(directory.rglob("*.rpy")) + list(directory.rglob("*.urpy")))):
        try:
            srcs.append(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            pass
    return discover_custom_statements(srcs)


def validate(path, mode="safe", require_start=True, custom_statements=()):
    try:
        d = parse_file(path, mode=mode, require_start=require_start,
                       custom_statements=custom_statements)
        print(f"OK {path}: {len(d['labels'])} labels, {list(d['labels'].keys())}")
        return True
    except ParseError as e:
        print(f"FAIL {path}\n{e}", file=sys.stderr)
        return False


def validate_dir(directory: Path, mode: str) -> bool:
    """Validate every script of a multi-file project, then the merged whole."""
    scripts = sorted(set(list(directory.rglob("*.rpy")) + list(directory.rglob("*.urpy"))))
    if not scripts:
        print(f"FAIL {directory}: no .rpy/.urpy files found", file=sys.stderr)
        return False
    ok = True
    labels = {}
    registered = _discover(directory, mode)
    for script in scripts:
        ok = validate(str(script), mode, require_start=False,
                      custom_statements=registered) and ok
        if ok:
            labels.update(parse_file(str(script), mode=mode, require_start=False,
                                     custom_statements=registered)["labels"])
    if ok and "start" not in labels:
        print(f'FAIL {directory}: no file defines `label start:`\n'
              f'Hint: one of the project\'s .rpy files must define:\n'
              f'label start:\n    "Hello."', file=sys.stderr)
        ok = False
    if ok:
        print(f"OK {directory}: {len(scripts)} files, {len(labels)} labels (merged)")
    return ok


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--mode", choices=("safe", "full"), default="safe",
                    help="parse mode: safe declarative subset (default) or full drop-in Ren'Py")
    args = ap.parse_args()
    ok = True
    for p in args.paths:
        for q in Path(".").glob(p) if "*" in p else [Path(p)]:
            if q.is_dir():
                ok = validate_dir(q, args.mode) and ok
            else:
                ok = validate(str(q), args.mode) and ok
    sys.exit(0 if ok else 1)
