"""
M19 — real Ren'Py corpus gate.

Runs UPVN's drop-in parser over a complete, real Ren'Py game. The corpus is
NOT vendored: point ``UPVN_RENPY_CORPUS`` at a Ren'Py project (or its ``game/``
directory) and these tests light up, otherwise they skip — same convention as
the existing ``renpy_src`` checks.

Reference corpus used while building this milestone:

    freeCodeCamp/LearnToCodeRPG  (BSD-3-Clause, 61 .rpy/.rpym files, ~2 MB)
    git clone --depth 1 https://github.com/freeCodeCamp/LearnToCodeRPG
    UPVN_RENPY_CORPUS=~/renpy_corpus/LearnToCodeRPG pytest tests/test_renpy_corpus.py
"""
import os
from pathlib import Path

import pytest

from engine.core.vn_errors import ParseError
from engine.script.parser import Parser
from tools.check_renpy_project import check_project, find_script_dir, smoke_run

CANDIDATES = [
    os.environ.get("UPVN_RENPY_CORPUS", ""),
    "/home/user/renpy_corpus/LearnToCodeRPG",
    "/home/user/renpy_corpus/LearnToCodeRPG/game",
]


def _corpus() -> Path | None:
    for cand in CANDIDATES:
        if not cand:
            continue
        p = Path(cand).expanduser()
        if p.is_dir() and list(find_script_dir(p).rglob("*.rpy")):
            return p
    return None


CORPUS = _corpus()
needs_corpus = pytest.mark.skipif(CORPUS is None,
                                  reason="set UPVN_RENPY_CORPUS to a Ren'Py project to run")


def _all_scripts():
    game = find_script_dir(CORPUS)
    return sorted(set(list(game.rglob("*.rpy")) + list(game.rglob("*.rpym"))))


@needs_corpus
def test_corpus_has_a_meaningful_size():
    """Guard against silently testing an empty directory."""
    scripts = _all_scripts()
    assert len(scripts) >= 20, f"only {len(scripts)} scripts — corpus looks incomplete"


@needs_corpus
def test_every_file_parses_in_the_drop_in_tier():
    failures = []
    for path in _all_scripts():
        src = path.read_text(encoding="utf-8", errors="replace")
        try:
            Parser(src, str(path), full=True, require_start=False).parse()
        except ParseError as e:
            failures.append(f"{path.name}: {str(e).splitlines()[0]}")
        except Exception as e:  # noqa: BLE001 - report anything, not just ParseError
            failures.append(f"{path.name}: {type(e).__name__}: {e}")
    assert not failures, "\n".join(failures[:10])


@needs_corpus
def test_merged_project_resolves_every_jump_and_call():
    rep = check_project(CORPUS)
    assert not rep["parse_errors"], rep["parse_errors"][:5]
    assert rep["totals"]["start_label"], "the corpus must define `label start:`"
    assert not rep["unresolved_jumps"], rep["unresolved_jumps"][:10]
    assert not rep["unresolved_calls"], rep["unresolved_calls"][:10]
    # named menus are jump targets in Ren'Py — they must be registered as labels
    assert rep["totals"]["labels"] > 50


@needs_corpus
def test_headless_smoke_run_plays_the_story():
    """The interpreter, not just the parser: real dialogue must come out."""
    res = smoke_run(CORPUS, [0, 0, 0, 0, 0], max_steps=400)
    assert res["ok"], res["error"]
    assert res["events"] >= 10, f"only {res['events']} events — the run stopped early"
    assert res.get("say_events"), "no dialogue was produced"
    assert not res["python_errors"], res["python_errors"][:3]


@needs_corpus
def test_no_label_is_defined_twice():
    rep = check_project(CORPUS)
    assert not rep["duplicate_labels"], rep["duplicate_labels"][:5]
