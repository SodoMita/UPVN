"""UPVN experimental UI toolkit (prototype — see lab/README.md).

PHASE 1 ONLY: **static layout**. Every widget is placed with an explicit
rectangle taken from the theme cascade (Ren'Py-style `xpos`/`ypos`/`xsize`/
`ysize`).  `padding`, `margin` and `spacing` exist in `Style` but are *not*
applied yet — they are inert data reserved for phase 2, and the resolver says
so on every box it emits (`padding_applied=False`).

Nothing in `engine/` may import this package until phase 1 has been proven
against real UPBGE screenshots.
"""

from __future__ import annotations

__all__ = ["style", "layout"]
