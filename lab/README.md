# `lab/` — experimental, NOT part of the engine

Everything in this directory is **prototype code**. It is deliberately outside
`engine/` so nothing here can change runtime behaviour until it has been
proven. Nothing under `lab/` is imported by `engine/`, `bge_frontend/` or
`tools/` — only by tests (and those tests live in `tests/`, never in `lab/`).

## Rule for this sandbox (user directive, 2026-09-17)

> Automatic layouts with padding and other calculations are too early. Make
> sure everything works with **static layout** first.

So `lab/ui_toolkit` is being developed in two phases:

| Phase | Status | What it does |
|---|---|---|
| **1 — static layout** | in progress | Every widget gets an **explicit rectangle** (`x`, `y`, `width`, `height`) from the theme cascade. No flow, no stacking, no content-driven resizing of parents, **no padding/margin/spacing maths**. |
| 2 — auto layout | blocked until phase 1 is proven | padding, margins, spacing, vbox/hbox flow, shrink-to-fit, anchor/align resolution. |

`Style` already *carries* `padding`, `margin`, `spacing`, `anchor` — they are
**inert data** in phase 1. `lab/ui_toolkit/layout.py` resolves rectangles and
records `padding_applied=False` on every box so a phase-2 implementation can be
diffed against phase 1 instead of silently changing the picture.

## Verification is real rendering, never a mock renderer

Screenshots must come from the **real UPBGE player** running under
headless **sway + pixman** (`tools/desktop_sway.sh`, `tools/desktop_run.sh`,
`grim`). A PIL/paint mock is not evidence — it does not exercise the engine's
own geometry, materials, fonts or camera. See `docs/SANDBOX_UPBGE.md`.

## Contents

- `ui_toolkit/style.py` — theme/style data model (colours, metrics, cascade,
  Ren'Py `gui.rpy` import, JSON save/load).
- `ui_toolkit/layout.py` — widget tree + **static** layout resolver, screen
  builders (say / menu / input), draw-list emission.
