# Bug log — M26d (desktop GUI: backlog + rewind)

Each entry is a real failure observed while running the engine in the desktop
target (UPBGE `blenderplayer` under headless sway, and the Blender editor with
the UPVN add-on), with the fix and the test that now guards it. Everything here
was measured in this repo (`git log` on branch `agent/desktop-gui-fixes`);
numbers are from the player, not from an editor guess.

Reproduce any of it with:

```bash
bash tools/desktop_sway.sh                                   # bootstrap
bash tools/desktop_run.sh blend/UPVN_Template.blend 120 &    # player
python3 tools/desktop_qa.py keys space space h --shot backlog --expect '{"history_open": true}'
python3 tools/desktop_qa.py wheel up 2                        # mouse-wheel rewind
```

## BUG-M26d-001 — backlog text was never drawn, with no error

* Symptom: `H` opened the overlay (payload `history_visible=True`, panel drawn),
  and `History_Text` reported a correct `body`, `visible=True`, non-zero
  `dimensions`, `hide=False` — and painted nothing. A full debug round was
  burned on font-visibility ordering before this was isolated.
* Cause: two different depth margins were conflated in one number. Every VN
  plane is a flat quad, so *who covers whom* is decided by Y alone; the panel
  needs to clear the **story** planes, while text needs to clear **its own**
  panel. A text curve ~0.05 units in front of a large flat quad loses the depth
  test outright and silently. The dialogue box only survives that margin
  because nothing is ever drawn on top of it.
* Fix: `engine/ui/world_ui.py` has explicit constants — `UI_DEPTH = 0.12`
  (panel over story planes) and `TEXT_FRONT = 0.45` (text over its panel) —
  used by the backlog panel and the rewind marker.
* Test: `test_layout_positions_history_panel_and_scales_text` asserts the two
  margins as an invariant (panel.y − text.y == TEXT_FRONT), so the coincidence
  cannot come back.

## BUG-M26d-002 — the key that opened the backlog could close it again

* Symptom: at player framerate the overlay flickered shut immediately, and the
  harness reported "H sometimes does nothing".
* Cause: `H` and an advance key can land in the same logic tick (or one tick
  apart); the overlay gate closed on the advance press that had just opened it.
* Fix: opening records `_history_opened_at` and the gate ignores advance/close
  input for 0.3 s.
* Test: `test_opening_the_backlog_cannot_be_closed_by_the_same_input`.

## BUG-M26d-003 — the FONT block grows UP in the player

* Symptom: the backlog was anchored "just inside the panel's top edge, growing
  downward" (`align_y='TOP'` is set on the curve) — in the player its first row
  was sliced off by the window edge.
* Cause: the runtime ignores the curve's `align_y`; glyphs are laid out from the
  object origin upward. Confirmed by geometry: an 8-row block anchored at
  `+0.45·half_v` drew from the anchor *up* to `+0.86·half_v`.
* Fix: `layout_screen_ui` now anchors the block's **bottom** at
  `first_row_z − rows·em·pitch`, with `rows` taken from the payload it is about
  to draw. Comment in `engine/ui/world_ui.py` says so, because the .blend and
  `align_y` both keep lying about it.
* Test: the layout test recomputes the expected top from the payload's row count
  and asserts the marker and the backlog share that top row.

## BUG-M26d-004 — the row budget counted entries, not drawn rows

* Symptom: "12 lines" produced 20+ rows that ran off the panel and over the
  dialogue box: each backlog entry wraps to 2–3 rows.
* Fix: paging works on **rendered rows** (`history_lines`), and
  `history_window` / `history_max_scroll` are the single source for the view and
  the controller's clamp — a drift there lets the wheel page into a blank panel.
* Test: `test_wrapping_counts_towards_the_row_budget`,
  `test_format_history_pages_by_rows_and_shows_position`.

## BUG-M26d-005 — font size came from the editor's curve metrics

* Symptom: after fixing the row count the block still overran the panel.
* Cause: `bpy`'s curve metrics (advance ≈ 0.42 em, pitch ≈ 1.12 em) are not what
  the game draws. Measured in-player from `History_Text` `dimensions`
  (2.207 units over 8 rows at `worldScale` 0.2789 → pitch **0.99 em**; a 44-char
  row measured 5.5 units → advance **0.44 em**, taken as 0.62 with margin).
* Fix: `HISTORY_PITCH_EM`, `HISTORY_ADVANCE_EM`, `HISTORY_FIT_SLACK = 0.85`.
  The em is the *smaller* of the height bound and the width bound, so a wrapped
  row cannot exceed the panel either.
* Note on the slack: `aspect_wh()` reads the window from the engine and it has
  reported 1.6 and 2.12 across runs of the same 1024×576 window (the projection
  and the visible frame are not the same rectangle when the WM resizes the
  client). The 15 % slack is what keeps that variance a margin instead of a
  clipped first row; the cost is empty space above the backlog.

## BUG-M26d-006 — per-frame text rewrite drew two pages at once

* Symptom: after paging, the frame showed the previous page's lines interleaved
  with the new ones (looked like doubled, half-torn rows).
* Cause: `set_font_text` assigned `data.body` unconditionally every tick,
  rebuilding the glyph mesh 15–60×/s; a frame landing mid-rebuild drew a
  half-updated mesh. (The write itself was never duplicated — an instrumented
  run counted exactly one write per page change.)
* Fix: the write is skipped when the body already equals the text.
* Test: `test_set_font_text_is_idempotent`.

## BUG-M26d-007 — `tools/make_template.py` and "Setup Scene" died with NameError

* Symptom: `NameError: name 'TEX_NODE_NAME' is not defined` at
  `upvn_editor_addon.py::_rewrite_unlit` — no .blend was produced, and the
  editor's Setup Scene button did the same.
* Cause: `TEX_NODE_NAME` / `MIX_NODE_NAME` / `WHITE_IMAGE_NAME` were *locals* of
  `build_vn_scene`, but `_rewrite_unlit` and `_ensure_white_image` are separate
  module-level functions inside `if HAS_BPY:` and cannot see them.
* Fix: the three names are resolved at that module scope (contract import with
  the same literal fallback). `make_template.py` output now contains
  `History_Box` / `History_Text` / `Rewind_Text` — verified by loading the
  generated .blend and probing the objects.

## BUG-M26d-008 — a converted Ren'Py project would not load in the player

* Symptom: `tools/renpy_convert.py` reported "0 parse errors" and the project
  ran, but the player showed "UPVN: game script not found" while the .rpy files
  were on disk at the searched path.
* Cause: `parse_mode` did not exist as a runtime property, so the frontend always
  built `VNController` with the default `safe` tier; real Ren'Py source
  (`extend`, `init offset`, `screen`) needs `full`. The tool parsed with `full`,
  which is why the checker and the game disagreed.
* Fix: `parse_mode` is a *game* property (visible to `KX_GameObject`):
  `tools/wire_converted_blend.py` writes `full` for converted projects, the
  add-on seeds `safe` only when unset (Setup Scene must not downgrade a
  converted project), and the frontend retries once at `full` if the first load
  raises — so an older converted .blend plays instead of showing a diagnostic.
* Verified: `examples/14_renpy_dropin` and `examples/10_full_sample_game`
  converted, played, `extend` line rendered, backlog + rewind worked in-player.

## BUG-M26d-009 — tooling that lies (harness bugs, not engine bugs)

* `xdotool key PageUp` exits 0 and prints "No such key name" — the keysym is
  `Prior`/`Next`. One in-player rewind test was "failing" on this alone.
  `tools/desktop_qa.py` now aliases the names and aborts on an unknown key.
* `xdotool key --delay 80` on a *plain* key spans two logic ticks at 13–19 fps,
  so one PageUp rolled back two lines. Plain keys now use 12 ms; only chords use
  80 ms.
* `xdotool click --window` sends synthetic events, which the SDL frontend
  ignores; the wheel has to be XTEST (`xdotool click 4/5` with no `--window`).
  Hence `tools/desktop_qa.py wheel up|down N`.
* `tools/smoke_walkthrough.sh` hardcoded `/home/user/upbge/...` and died on
  `cd` after a reprovision; it probes `$UPBGE_DIR`, `/opt/upbge`, `~/upbge` and
  `$PATH` now, and asserts the backlog and rewind (keys *and* wheel) itself:
  `HISTORY_OK`, `REWIND_OK (key)`, `REWIND_OK (wheel)`, `REPLAY_OK`, and that
  paging the backlog never touches `rollforward_depth`.
* A screenshot is not the state at the instant of the heartbeat write; under
  llvmpipe it can be a frame behind. `tools/desktop_qa.py --shot` is advisory —
  assert on the heartbeat, then take a second shot.
