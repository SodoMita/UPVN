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
2. Open `blend/UPVN_Template.blend`
3. **Enable editor tools:** Edit → Preferences → Add-ons → Install → `blend/upvn_editor_addon.py` → Enable. Then in 3D View or Text Editor press `N` → tab **UPVN**.
4. **Create game with clicks (no coding):**
   - `Create UPVN Project` → creates `//game/script.rpy` with starter `define` + `scene` + `say`
   - `Add Character` (ID, Name, Color) → writes `define e = Character("Eileen", color="#c8ffc8")`
   - `Add Scene` / `Add Show` (asset, position `left/center/right`, `with move/dissolve`) → writes `scene`/`show`
   - `Add Dialogue` (speaker, text with `[var]` and `{b}`) → writes `say`
   - `Add Menu` (caption, 2 choices + jumps) → writes `menu:` with automatic `jump` targets
   - `Validate` → parser checks line/col + hint (friendly errors), `Preview` → headless screenshot to `screenshots/upvn_preview.png`
5. Scene `VN_Main` contains `Empty: VNController` with logic:
   ```
   Always (True pulse) → Python Controller → bge_frontend.frontend.main
   ```
6. Set `script_path` property to `//game/script.rpy` or `//examples/99_creator_demo/script.rpy`
7. Press `P` to play. Click / Space to advance, `H` history, `Q` quick menu, `S` save, `L` load (arbitrary slots 1..∞), mouse wheel rollback.

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
