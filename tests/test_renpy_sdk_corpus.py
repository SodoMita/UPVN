"""
M21 — second real-world corpus gate: the Ren'Py SDK's own games.

The M19/M20 gate runs against freeCodeCamp/LearnToCodeRPG. This one runs
against a completely different codebase — the games that ship *inside* the
Ren'Py SDK itself (MIT), whose style is nothing like a shipped indie game:

  * `tutorial/`   — 23 scripts, heavy on `screen`/`style`/`transform`/ATL, and
                    it registers its own statement keywords with
                    `renpy.register_statement("example", …, block="script")`.
  * `the_question/` — the canonical demo the SDK has shipped for years.

Validating against two unrelated corpora is what keeps the drop-in tier from
being quietly fitted to one game's habits.

The corpus is NOT vendored. Point ``UPVN_RENPY_SDK`` at a checkout of
`renpy/renpy` (or at the directory holding `tutorial/` and `the_question/`)
and these tests light up, otherwise they skip:

    git clone --depth 1 https://github.com/renpy/renpy
    UPVN_RENPY_SDK=~/renpy_sdk pytest tests/test_renpy_sdk_corpus.py
"""
import os
from pathlib import Path

import pytest

from engine.core.vn_errors import ParseError
from engine.script.parser import Parser, discover_custom_statements
from tools.check_renpy_project import check_project, find_script_dir

CANDIDATES = [
    os.environ.get("UPVN_RENPY_SDK", ""),
    "/home/user/renpy_corpus/renpy_sdk",
    "/home/user/renpy_src",
]


def _root() -> Path | None:
    for cand in CANDIDATES:
        if not cand:
            continue
        p = Path(cand).expanduser()
        if p.is_dir() and (p / "tutorial" / "game").is_dir():
            return p
    return None


ROOT = _root()
needs_sdk = pytest.mark.skipif(ROOT is None,
                               reason="set UPVN_RENPY_SDK to a renpy/renpy checkout to run")

GAMES = ("tutorial", "the_question")


def _scripts(game: str):
    return sorted(find_script_dir(ROOT / game).rglob("*.rpy"))


def _registered(game: str):
    srcs = [p.read_text(encoding="utf-8", errors="replace") for p in _scripts(game)]
    return discover_custom_statements(srcs)


@needs_sdk
@pytest.mark.parametrize("game", GAMES)
def test_sdk_corpus_is_present_and_sized(game):
    scripts = _scripts(game)
    assert len(scripts) >= 3, f"{game}: only {len(scripts)} scripts — checkout looks incomplete"


@needs_sdk
@pytest.mark.parametrize("game", GAMES)
def test_every_sdk_file_parses(game):
    registered = _registered(game)
    failures = []
    for path in _scripts(game):
        src = path.read_text(encoding="utf-8", errors="replace")
        try:
            Parser(src, str(path), full=True, require_start=False,
                   custom_statements=registered).parse()
        except ParseError as e:
            failures.append(f"{path.name}: {str(e).splitlines()[0]}")
        except Exception as e:  # noqa: BLE001 - report anything, not just ParseError
            failures.append(f"{path.name}: {type(e).__name__}: {e}")
    assert not failures, "\n".join(failures[:10])


@needs_sdk
@pytest.mark.parametrize("game", GAMES)
def test_sdk_project_resolves_every_jump_and_call(game):
    rep = check_project(ROOT / game)
    assert not rep["parse_errors"], rep["parse_errors"][:5]
    assert rep["totals"]["start_label"], f"{game} must define `label start:`"
    assert not rep["unresolved_jumps"], rep["unresolved_jumps"][:10]
    assert not rep["unresolved_calls"], rep["unresolved_calls"][:10]
    assert not rep["unresolved_screens"], rep["unresolved_screens"][:10]


@needs_sdk
def test_tutorial_registers_custom_statements_and_we_honour_them():
    """The tutorial defines its own `example` statement — the whole point of M21."""
    registered = _registered("tutorial")
    assert registered.get("example") == "script", registered
    assert "show example" in registered and "hide example" in registered


@needs_sdk
def test_labels_inside_a_script_block_are_real_jump_targets():
    """`label play_pong:` lives inside an `example` block in the tutorial."""
    rep = check_project(ROOT / "tutorial")
    assert "play_pong" in rep["labels"]
    assert not rep["unresolved_jumps"], rep["unresolved_jumps"]


@needs_sdk
def test_bodies_we_do_not_implement_are_recorded_not_fatal():
    rep = check_project(ROOT / "tutorial")
    # whatever we could not read inside a foreign statement body is reported,
    # and the file still parsed
    assert isinstance(rep["custom_statement_errors"], list)
    assert not rep["parse_errors"], rep["parse_errors"][:3]
