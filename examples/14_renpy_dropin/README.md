# 14 — Ren'Py drop-in tier (multi-file)

A three-file Ren'Py project written **entirely in stock Ren'Py syntax** — no
UPVN-specific keywords anywhere. It exists to prove the drop-in tier parses and
runs the constructs real shipped games use.

| file | what it exercises |
|---|---|
| `characters.rpy` | `init offset`, dotted `define gui.* / config.*` (store namespaces), multi-line `Character(...)`, `default` (incl. dotted + expression), `init python hide:`, `image` definitions |
| `screens.rpy` | `screen name(params)` with `tag/modal/zorder`, `transform name(params)`, `style` blocks + style property statements, `translate` block |
| `script.rpy` | triple-quoted text, `\` line continuation, `with Dissolve(0.5)`, `show … at a, b with fade`, voice attributes (`mc @ surprised`), negated image attributes (`e -concerned`), `nointeract` + `extend`, `centered`/`vcentered`, `call … from _call_x`, `for x in list:`, named menu + `set`, `if/else` choice groups, `call screen f(args)`, `show/hide screen`, `pause expr`, `queue`, `voice sustain`, `stop music fadeout` |

## Run it

```bash
python -m tools.run_headless examples/14_renpy_dropin --mode full --choices 0
python -m tools.check_renpy_project examples/14_renpy_dropin --run
python -m tools.validate examples/14_renpy_dropin --mode full
```

## Checking a real Ren'Py game

```bash
git clone --depth 1 https://github.com/freeCodeCamp/LearnToCodeRPG ~/renpy_corpus/LearnToCodeRPG
python -m tools.check_renpy_project ~/renpy_corpus/LearnToCodeRPG --run
UPVN_RENPY_CORPUS=~/renpy_corpus/LearnToCodeRPG pytest tests/test_renpy_corpus.py
```

`check_renpy_project` parses every `.rpy`/`.rpym`, merges them the way Ren'Py
does, reports unresolved `jump`/`call`/`call screen` targets and the `renpy.*`
APIs the project uses, and (with `--run`) plays the story headless in compat
mode, collecting any `python:` block it could not execute.

## Known limitations of the drop-in tier

- `screen`/`style`/`transform`/`translate` bodies are captured verbatim for the
  editor — UPVN does not render Ren'Py screens.
- `python:` blocks run for real, so anything they need (third-party modules,
  `renpy.display.*` classes) must exist; with `compat=True` failures are
  collected in `interp.python_errors` / `interp.init_errors` and the story
  continues.
- Unknown `renpy.*` members are recorded no-ops (`interp._expr_extra["renpy"].compat_log`).
