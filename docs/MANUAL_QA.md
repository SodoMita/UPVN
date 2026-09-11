# Manual QA — the boring-reliability checklist (M25)

Traces are CI; this page is for humans with eyes. Everything here runs on the
headless stack from `docs/SANDBOX_UPBGE.md` (Wayland preferred). Automated
twin: `tools/smoke_walkthrough.sh` (self-verifying, retry-until-state).

## 0. Prep (once per sandbox)
- [ ] UPBGE 0.50 extracted; `blenderplayer` runs (`--version`).
- [ ] userpref prep done (BUG-006) — otherwise instant segfault.
- [ ] compositor up: `swaymsg -t get_outputs` shows HEADLESS-1 (or Xvfb :99).
- [ ] `pytest tests/ -q` green (324 passed / 16 skipped on
      `agent/desktop-gui-fixes`, 276 at the M25 freeze).
- [ ] `bash tools/desktop_sway.sh` (bootstrap: sway + UPBGE + 3 GB swap) and
      `source /tmp/wl-upvn/env.sh`. After a sandbox reprovision this is the
      FIRST thing to re-run: apt packages, `/opt/upbge`, the swapfile and
      `.git/config` are all gone while workspace files survive (so git
      identity, the `origin` remote and `tools/*.sh` exec bits need redoing).

## 1. Install / Setup (editor, optional in sandbox)
- [ ] Install addon zip; enable; UPVN panel in View3D > N.
- [ ] Create Project → writes `game/script.rpy` + defines.
- [ ] Setup Scene → contract objects exist; `VNController` carries
      **game properties** `script_path` / `upvn_root` / `upvn_bricks`
      (Object properties > Game Properties, NOT just custom props — BUG-009).
- [ ] Check Wiring reports 29/29.
- [ ] **Old .blend files** (any file baked before the backlog existed) need the
      three UI objects added, or the overlay has nothing to draw into:

      ```bash
      <upbge>/blender --background blend/UPVN_Template.blend \
          --python tools/add_template_ui_objects.py -- --save blend/UPVN_Template.blend
      ```

      Prints `UPVN_UI_OBJECTS_ADDED History_Box,History_Text,Rewind_Text` (or
      `..._CHANGED …` / `..._CLEAN nothing to write`) and is idempotent. Press
      **Setup Scene** first if the scene predates the current contract, then run
      this, then re-check Wiring.
- [ ] `tools/make_template.py` produces the same objects from scratch (it died
      with `NameError: TEX_NODE_NAME` before BUG-M26d-007; if it ever saves 0
      controllers *and* no `History_Box`, that regression is back).
- [ ] A converted project embeds a runtime snapshot (`engine/`,
      `bge_frontend/`), so engine fixes need `tools/renpy_convert.py` re-run (or
      those two dirs copied) — an old converted project keeps old bugs.

## 2. Play — smoke game (`examples/20_smoke_game/script.rpy`)
Run `bash tools/smoke_walkthrough.sh` or by hand:
- [ ] P (or blenderplayer) shows slate BG + navy dialogue band, speaker
      "Eileen", "Line one." — **not** the "game script not found" diag
      (BUG-009 regression check).
- [ ] Click / Space / Enter advances; typewriter reveals then completes.
- [ ] Menu shows numbered plates "1. Go left / 2. Go right" (BUG-005 plates
      visible, not black).
- [ ] Press `1` → "You chose left." (BUG-006/010 digit select).
- [ ] `S` toggles skip, `A` auto, `H` history, `Q` quick menu; **Ctrl+S does
      not** enable skip (BUG-008).
- [ ] **Backlog (H)**: a translucent full-screen panel appears over the scene
      with the recent lines, oldest first, newest last, speaker prefixed
      (`Eileen: Line one.`), and the choice plates disappear while it is open.
      It must be READABLE — no row clipped by the window edge, nothing drawn
      over the dialogue box (BUG-M26d-001/-003/-004/-005 all looked like
      "history is broken" from the outside).
- [ ] **Backlog paging**: with more lines than fit (default budget 8 rows), a
      footer appears — `— rows 15-21 of 21 · page 1/3 (wheel) —`. Mouse wheel
      (and Up/Down) page it while the overlay is open; the same wheel gesture
      rewinds the *story* when it is closed, so check both. `H` again, a click
      or Space closes it; reopening lands on the newest page.
- [ ] **Rewind**: wheel up / PageUp / Backspace step back (including *across* a
      menu choice — `start idx=4` → `left idx=0` back to `start idx=3`), wheel
      down / PageDown replay forward, and a real advance clears the redo stack.
      Modals (quick menu, save browser) block rewind; that is intended.
      Keys are `Prior`/`Next` for xdotool — `PageUp` is silently dropped
      (BUG-M26d-009), so `python3 tools/desktop_qa.py keys Prior` is the
      harness-checked spelling.
- [ ] Skip/auto never resolves the menu by itself (BUG-007).
- [ ] Ctrl+S writes `saves/save_quick.json`; game continues unblocked
      (BUG-011: no invisible modal).
- [ ] Ctrl+L returns to the saved line (state, not just visuals).
- [ ] Wheel up rolls back a line; wheel down redoes (drive it with
      `tools/desktop_qa.py wheel up 2` — XTEST, not `--window`).
- [ ] F1 toggles the on-screen diag (label/idx/script/last error); F12 saves
      an in-game PNG.
- [ ] Esc quits the player (engine-level; expected — see BUG-011).

## 2b. Conversion path (Ren'Py → UPVN project)
- [ ] `python3 tools/renpy_convert.py examples/14_renpy_dropin --out tmp/conv \
      --blender <upbge>/blender` reports 0 parse errors AND
      `[wire] script_path=//../game image_mode=auto parse_mode=full`.
- [ ] `bash tools/desktop_run.sh tmp/conv/blend/UPVN_Template.blend 60` then
      shows the *game*, not the "game script not found" screen (BUG-M26d-008).
- [ ] In the converted game: `extend` lines render, `H` opens the backlog, the
      wheel pages it, and `Prior`/`Next` rewind and replay.
- [ ] `tools/check_renpy_project.py <src>` and `tools/validate.py <out>` agree.

## 3. Evidence to keep per release
`examples/20_smoke_game/evidence/` (Wayland stack, 2026-09-10):
`wayland_01_dialogue_line1`, `wayland_03_after_space_menu`,
`wayland_04_after_key1_left`, `wayland_06_after_quicksave`,
`wayland_08_after_quickload`. Regenerate with
`SMOKE_OUT=<dir> bash tools/smoke_walkthrough.sh`.

## 4. Known limitations at freeze
- Modal slot browsers (save/load) exist headless-only; player uses direct
  quick-save/load (BUG-011).
- Screens (`screen` language) render in traces, not in the player yet.
- Synthetic-input flake requires retries in harnesses (SANDBOX doc).
- llvmpipe: ~13–19 logic fps at 1024x576 — QA waits are sized for that.
- The backlog keeps a vertical margin rather than filling the panel: the engine's
  window size and the projected frustum disagree under a tiling WM (measured
  aspects 1.6 and 2.12 for one 1024×576 window), and `HISTORY_FIT_SLACK` (15 %)
  is what turns that variance into empty space instead of a clipped first row.
  See BUG-M26d-005.
- Backlog pages by *rows*, so a long entry can split across two pages
  (the footer always names the exact row range, so nothing is hidden silently).
- The backlog panel is translucent by design (Ren'Py-style): the dialogue box
  reads through it. It is not a bug unless a backlog row overlaps the box text.
