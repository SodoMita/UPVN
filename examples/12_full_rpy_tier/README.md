# Full `.rpy` tier (drop-in Ren'Py)

This example shows the **full** `.rpy` language — the tier that lets UPVN act as a
drop-in Ren'Py replacement. It allows embedded Python and everything Ren'Py scripts
normally use, all compiling to the same internal IR as the other two tiers.

## What it exercises

- `define e = Character("Eileen", color="...")` — Ren'Py-style characters
- `init python:` / `init:` — embedded Python at init time
- `init offset = N` — priority offset (accepted, recorded)
- `python:` blocks and one-line `$ ...` Python
- `default` defaults
- `label name(params):` + `call label(args)` — label parameters/arguments
- `jump expression ...` / `call expression ...` — computed targets
- `while` / `if` / `break` — control flow
- `menu` choices with `"Text" if cond:` — conditional choices
- `window show|hide|auto`, `nvl clear|show|hide` + `nvl mode`, `voice`, `queue music|sound`
- `show/hide screen`, `screen:` / `style:` / `transform:` / `translate:` blocks (captured)

## Run it

```bash
python tools/run_headless.py examples/12_full_rpy_tier/script.rpy --mode full --choices 0
python tools/validate.py --mode full examples/12_full_rpy_tier/script.rpy
```

Parsing this file in the default **safe** mode fails on purpose, with a hint to use
`--mode full` — the safe subset forbids `python:`/`init`/arbitrary defines.
