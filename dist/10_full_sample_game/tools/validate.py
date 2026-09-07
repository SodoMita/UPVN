#!/usr/bin/env python3
"""Validator — checks .rpy syntax with friendly errors (no YAML needed)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.script.parser import parse_file, ParseError

def validate(path):
    try:
        d = parse_file(path)
        print(f"OK {path}: {len(d['labels'])} labels, {list(d['labels'].keys())}")
        return True
    except ParseError as e:
        print(f"FAIL {path}\n{e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    args = ap.parse_args()
    ok = True
    for p in args.paths:
        for q in Path(".").glob(p) if "*" in p else [Path(p)]:
            if q.is_dir():
                for r in q.rglob("*.rpy"):
                    ok = validate(str(r)) and ok
            else:
                ok = validate(str(q)) and ok
    sys.exit(0 if ok else 1)
