# Manual QA — the boring-reliability checklist (M25)

Traces are CI; this page is for humans with eyes. Everything here runs on the
headless stack from `docs/SANDBOX_UPBGE.md` (Wayland preferred). Automated
twin: `tools/smoke_walkthrough.sh` (self-verifying, retry-until-state).

## 0. Prep (once per sandbox)
- [ ] UPBGE 0.50 extracted; `blenderplayer` runs (`--version`).
- [ ] userpref prep done (BUG-006) — otherwise instant segfault.
- [ ] compositor up: `swaymsg -t get_outputs` shows HEADLESS-1 (or Xvfb :99).
- [ ] `pytest tests/ -q` green (276 passed at freeze).

## 1. Install / Setup (editor, optional in sandbox)
- [ ] Install addon zip; enable; UPVN panel in View3D > N.
- [ ] Create Project → writes `game/script.rpy` + defines.
- [ ] Setup Scene → contract objects exist; `VNController` carries
      **game properties** `script_path` / `upvn_root` / `upvn_bricks`
      (Object properties > Game Properties, NOT just custom props — BUG-009).
- [ ] Check Wiring reports 29/29.

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
- [ ] Skip/auto never resolves the menu by itself (BUG-007).
- [ ] Ctrl+S writes `saves/save_quick.json`; game continues unblocked
      (BUG-011: no invisible modal).
- [ ] Ctrl+L returns to the saved line (state, not just visuals).
- [ ] Wheel up rolls back a line; wheel down redoes.
- [ ] F1 toggles the on-screen diag (label/idx/script/last error); F12 saves
      an in-game PNG.
- [ ] Esc quits the player (engine-level; expected — see BUG-011).

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
