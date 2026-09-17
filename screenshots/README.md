# Screenshots — REAL engine output vs PIL mock-ups

**Read this before trusting any PNG in this folder.**

Every Pillow mock-up that used to live here has been deleted (2026-09-18):
`tools/generate_screenshots.py`, `generate_screenshots_v2.py`,
`make_placeholder_art.py`, `probe_shot.py`, `ascii_shot.py`, `parity_probe.py`
and every screenshot they produced. Only real captures remain.

| Folder | What produced it | Trust it? |
|---|---|---|
| `parity/` | `grim` capture of the real **UPBGE player** (headless sway + pixman) and of the real **Ren'Py** engine | ✅ **yes** — this is what the engine actually draws |
| `renpy_parity/` | `grim` captures from real UPBGE (see `docs/RENPY_PARITY_PROOF.md`) | ✅ yes |

**Never re-add a Pillow mock:** it cannot show what the engine really does (materials, camera,
fonts, depth, AA). Always regenerate evidence with:

```bash
tools/upvn_shot.sh            <blend> out.png "dialogue match text"   # UPBGE, grim
tools/renpy_reference_shot.sh <project> script.rpy:34 out.png         # Ren'Py, grim
```
