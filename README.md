# UPVN — Ren'Py-like Visual Novel Framework inside UPBGE

**Version 0.1 (Tier 1 Kinetic)** — Minimal playable VN that runs both headless (for tests) and inside UPBGE as a real-time 3D engine.

> Inspired by Ren'Py's authoring comfort (labels, say, show/scene, menu/jump, variables, if) but rebuilt with UPBGE's 3D strengths. **Not a full clone** — same `.rpy` feeling, without the accumulated complexity.

## Why this exists (doc summary)

The attached spec (~4k lines) explored many design options:
- YAML/JSON intermediate vs direct `.rpy` parsing
- 2D planes vs 3D stages vs hybrid
- Where UI lives, how save/rollback works, which examples prove what

For v0.1 the decisions are:

| Question | Decision | Rationale |
|----------|----------|-----------|
| **YAML/JSON intermediate?** | **No.** `.rpy` is parsed directly to an AST (list[dict]), just like Ren'Py does. | You asked *“Does renpy itself use yaml or json internally? If not, better do directly without.”* — Correct. Ren'Py's own `renpy/lexer.py` + `parser.py` (1800+ lines each) lexe `.rpy` directly and pickles to `.rpyc`. No YAML. Our parser is a subset (~500 lines) that compiles straight to `{"labels": {"start": [...]}}`, which is JSON-serialisable for tracing/caching but never shown to authors. |
| **MVP scope** | **Tier 1 Kinetic** (you chose `tier1`): say/narration, click-to-advance, Character, label/jump/menu, `default`/`$`/`if`, scene/show/hide/with, play music. | Smallest playable that can already run *The Question*'s full script headlessly (see proof below). |
| **UPBGE version** | **UPBGE 0.50 (Blender 5.0.1) Linux x64** — downloaded verified 408 MB (`upbge-0.50-linux-x64.tar.xz`). Also works with `fake-bge-module` for headless pytest so you don't need to launch UPBGE to test logic. | You chose *any_linux + fake-bge*. 0.50 is latest stable (Jan 2026). |
| **Render mode** | **Hybrid stubbed from day 1** (you chose). 2D background/sprite planes on ortho camera **plus** 3D `load_stage`/`show3d`/`anim`/`camera preset` stubs. UI is created **in the 3D scene** (planes + `blf` text), no DSL for it — *LLM can build that using python* as you requested. | Doc §4 Option C. |

---

## Quickstart (headless — no UPBGE needed)

```bash
cd upvn
pip install -r requirements.txt  # (or just python — no deps for headless)
pytest tests/ -v
python -m tools.run_headless examples/00_minimal_dialogue/script.rpy
python -m tools.run_headless examples/03_variables_routes/script.rpy --choices 0
python -m tools.run_headless /home/user/renpy_src/the_question/game/script.rpy --choices 0 0
```

Expected: all 4 examples + *The Question* parse and trace cleanly. No YAML.

## Quickstart (in UPBGE — minimal coding, no .rpy typing)

1. Extract `~/upbge-0.50-linux-x64.tar.xz`
2. **Install the add-on (v0.6.5+, one file — engine is bundled):**
   Edit → Preferences → Add-ons → **Install from Disk…** (older UI: Install…) → select
   `dist/upvn_editor_addon_v0.6.5.zip` (or the raw `blend/upvn_editor_addon.py` when
   working from the repo) → enable **"UPVN — Visual Novel Editor"**.
   The UPVN tab (3D View or Text Editor sidebar, `N`) shows **✓ Engine: OK** when ready —
   if it ever shows ✗, press *Locate Engine…* / *Re-check* (or *Copy engine next to add-on*).
3. Open `blend/UPVN_Template.blend` — it is **pre-wired**: the `VNController` object already
   carries the `Always (True pulse) → Python (upvn_launcher)` brick, so you can press `P`
   immediately. (Older templates without bricks: run **Setup Scene** once from the UPVN tab —
   it is idempotent and safe to repeat.)
4. **One click wiring (UPBGE only, for your own scenes/projects):** UPVN tab → **Setup Scene** —
   creates/refreshes every object the engine expects **by name** (background plane + material,
   five `Sprite_*` planes + `MASprite` material, `VNController` object with `script_path`/
   `upvn_root`, the path-bootstrap `upvn_launcher` text and the `Always (True pulse) → Python`
   brick). Nothing to wire by hand, pressing it twice is safe. **Check Scene Wiring** then
   compares the scene against `engine/render/contract.py` and writes a missing-items report to
   the `UPVN_WIRING` text. The full name↔code table is in `blend/README.md` → "Scene-object contract".
5. **Create game with clicks (no coding):**
   - `Create UPVN Project` → creates `//game/script.rpy` with starter `define` + `scene` + `say`
   - `Add Character` (ID, Name, Color) → writes `define e = Character("Eileen", color="#c8ffc8")`
   - `Add Scene` / `Add Show` (asset, position `left/center/right`, `with move/dissolve`) → writes `scene`/`show`
   - `Add Dialogue` (speaker, text with `[var]` and `{b}`) → writes `say`
   - `Add Menu` (caption, 2 choices + jumps) → writes `menu:` with automatic `jump` targets
   - `Validate` → parser checks line/col + hint (friendly errors), `Preview` → headless screenshot to `screenshots/upvn_preview.png`
6. The frontend reads **`script_path` from the `VNController` object** — exactly what the
   panel's `project_path` writes — so the game you build is the game that plays
   (legacy `//game/script.rpy`, `//script.rpy`, `//examples/…` are fallbacks).
7. Press `P` to play. **Controls (v0.6.5):** click / Space / Enter advance; **`1`–`9` pick a menu choice** (in-engine input, no extra wiring); `H` history, `Q` quick menu, `Ctrl+S` save, `Ctrl+L` load (arbitrary slots 1..∞, `←`/`→` page, `Esc` close), `S` skip, `A` auto, mouse wheel rollback, **`F1` console state dump, `F12` in-game screenshot** to `//screenshots/upvn_ingame_*.png` (QA/debug helpers).

## Troubleshooting (was: "Engine not available")

Old add-on versions were a lone `.py`: Blender copied them away from `engine/`, and every
button died with a bare **"Engine not available"**. Since v0.6:

| Symptom | Fix |
|---|---|
| ✗ Engine NOT found in the UPVN tab | Install the **zip release** (engine is inside it) or press *Locate Engine…* and point at the folder containing `engine/`; press *Re-check*. |
| `Warning: add-on missing 'bl_info'` for engine/ + bge_frontend/ | Leftovers of the old v0.6.0 zip layout in your add-ons folder — delete `addons/engine` and `addons/bge_frontend` (v0.6.5 zip is a single folder). |
| Add-on installed from an old single `.py` | Enable, then in Preferences → Add-ons → UPVN press *Copy engine next to add-on* (or reinstall from the zip). |
| "no game script found" in the console when pressing P | The `script_path` on `VNController` points nowhere — set panel `project_path`, press `Create Project`, then `Setup Scene` again. |
| Pressing P shows a frozen viewport-like scene, no dialogue | The template had no logic bricks (old file). In the UPVN tab press **Setup Scene** once and File → Save; the committed `blend/UPVN_Template.blend` already includes the bricks. |
| Running in plain Blender (not UPBGE) | Editing/Validate/Preview work; *Setup Scene* and *P to play* need UPBGE (has the game engine). |
| Setup Scene in `--background` | Logic-brick operators need the UPBGE UI context — run Setup Scene from the panel, not headless. |
| `blf.color() takes exactly 5 arguments` in the game console | Fixed in 0.6.5 — reinstall the add-on zip so the updated `bge_frontend` is used. |
| `Preview failed: … Pillow (PIL) is not installed…` | UPBGE uses its own bundled Python, where Pillow may be missing even if the system has it. Press **Install Pillow** in the UPVN panel (runs `python3.11 -m pip install pillow` in UPBGE's Python). |

**Headless minimal coding (without Blender):**
```bash
python tools/upvn_game_creator.py
# or Python API:
from blend.upvn_editor_addon import UPVN_GameBuilder
b = UPVN_GameBuilder("game/script.rpy")
b.add_character("e","Eileen","#c8ffc8").add_scene("bg classroom").add_say("e","Hello!").write()
b.preview_screenshot()
```
See `blend/README.md` for plane setup (Layer 0 bg, Layer 1 sprites, Layer 2 UI) and `blend/upvn_editor_addon.py` for full API.
Saves are **arbitrary 1..∞** (not 6): `SaveManager.save(42)` / `save(9999)` + pagination in save/load screens (6 per page, ←→ to paginate, `next_available_slot()`).

---

## Repo layout (agent-friendly, doc §3/§4)

```
upvn/
  README.md                ← you are here
  ROADMAP.md               ← machine-readable ledger (agent reads first)
  AGENTS.md                ← operating rules
  COMMAND_SPEC.md          ← every command, good/bad/example/error
  SCRIPT_LANGUAGE_SPEC.md  ← precise .rpy subset grammar
  engine/
    core/   vn_state.py, vn_controller.py, vn_interpreter.py, vn_errors.py
    script/ lexer.py, parser.py, ast_nodes.py   # direct .rpy → AST, no YAML
    render/ scene_manager.py, sprite_renderer.py, stage_manager.py # hybrid
    ui/     dialogue_box.py                      # plane + blf; python-extensible
    audio/  audio_manager.py                     # aud wrapper
    save/   save_manager.py                      # JSON, not pickle
  bge_frontend/frontend.py   # thin bge.* adapter (works with fake-bge)
  examples/
    00_minimal_dialogue/  (Tier 1 prove: say/return)
    01_branching_choice/  (Tier 1: menu/jump)
    02_sprites_backgrounds/ (Tier 2: scene/show + 3D stubs)
    03_variables_routes/ (Tier 2: default/$/if + [interpolation])
  tests/          # golden trace tests (headless, no bge)
  tools/ run_headless.py, validate.py, extract_upbge.py
  blend/ UPVN_Template.blend + generation script
  docs/           # design notes, Ren'Py criticism inventory
```

**Core / frontend split** is intentional (doc recommendation): `engine/` is pure Python, testable with `pytest` alone. `bge_frontend/` is the only place that imports `bge`. An LLM agent can verify 80% of the engine without clicking a rendered game — traces vs golden files.

---

## What Ren'Py does internally (and what we copy / reject)

Reading `renpy_src/renpy/{lexer,parser,ast,execution,script}.py` (~9k LOC total):

- **Lexer**: `renpy/lexer.py` groups logical lines by indentation, tokenises. We keep the same indentation-sensitive idea, 4 spaces per level, spaces not tabs, but emit friendlier errors.
- **Parser**: `renpy/parser.py` dispatches per-statement parsers (`parse_image_name`, `parse_simple_expression_list`, …) and builds `renpy.ast.*` nodes. We build a much smaller `list[dict]` AST with `_loc` for good errors. No `python:` blocks.
- **Execution**: `renpy/execution.py` runs the AST, blocking on `renpy.ui.interact()` for `say`/`menu`. We use a coroutine (`VNInterpreter.run()` yields `{"wait":True}` events) so UPBGE's frame loop can `send()` choice indices.
- **Pickle saves**: Ren'Py pickles the whole store. We store only JSON (`VNState.to_json()`), versioned, with stable statement semantics — addresses the community's #1 complaint (save incompatibility after script edits).

Full criticism inventory → `docs/renpy_criticism.md`.

---

## Tier 1 prove: The Question already parses

The canonical Ren'Py demo *The Question* (two characters, menus, `if book:`, `{b}` tags, `with fade`) **already parses and runs headlessly** with our subset:

```python
from upvn.engine.core.vn_controller import VNController
c = VNController("/home/user/renpy_src/the_question/game/script.rpy")
c.run_headless(choices=[0,0])  # rightaway → game → good ending
# c.state.variables == {"book": False}
c = VNController("/home/user/renpy_src/the_question/game/script.rpy")
c.run_headless(choices=[0,1])  # rightaway → book → good ending with book=True
```

See `tools/run_headless.py` for replay.

---

## Next for agents (read ROADMAP.md)

```
M0 harness (done) → M1 kinetic (done) → M2 sprites (stub) → M3 transitions
→ M4 The Question parity (done headless) → M5 audio/save → M6 DSL validation
→ M9 screens → M10 ATL-lite → M13 3D classroom
```

Each milestone has `examples/exNN_*/expected_behavior.md` + `tests/test_exNN*.py` golden traces. Agent protocol: open `ROADMAP.md`, find first `todo` with deps `done`, read its `SPEC`, implement, run `pytest`, flip status, commit.

---

## UPBGE download provenance

- Source: `https://upbge.org/#/download` → `https://github.com/UPBGE/upbge/releases/download/v0.50/upbge-0.50-linux-x64.tar.xz` (408,374,596 bytes, SHA via release notes). Downloaded 2026-09-07 to `~/upbge-0.50-linux-x64.tar.xz` (verified `xz` + `408M`).
- Ren'Py source: `https://github.com/renpy/renpy` cloned shallow to `~/renpy_src` (150 MB). Inspected `renpy/{lexer,parser,ast,execution}.py`.

---

## Legal

- UPBGE is GPL/BSD mix (see `upbge-0.50-linux-x64/license/`). We don't bundle it — you download it.
- Ren'Py is MIT-style with LGPL portions; we do **not** copy its code — only read for inspiration. Our `.rpy` is a new implementation, **inspired by** Ren'Py workflow (safe per doc §11).
- If you ship a game, bundle UPBGE's player or your own build; attribute per licenses.

---

*Status 2026-09-07: Tier 1 headless green, hybrid stubs present, UPBGE template scaffolding present, next agent should finish M2 rendering planes + M5 save/rollback polish.*
