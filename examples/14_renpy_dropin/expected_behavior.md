# Expected behavior — example 14 (Ren'Py drop-in tier)

`python -m tools.run_headless examples/14_renpy_dropin --mode full --choices 0`

1. A triple-quoted narration line plays, then `$ long_line = 1 + 2` (continuation).
2. `scene bg classroom with Dissolve(0.5)` and `show eileen happy at left, right with fade`.
3. Dialogue: "Hi Sam! Ready to test the drop-in tier?" (`[player_name]` interpolated
   from the `default player_name = "Sam"`).
4. `mc @ surprised "Sure!"` → say with `voice_attr="surprised"`.
5. `e -concerned "Great."` → say with `expression="-concerned"`.
6. The `nointeract` line does not wait (`wait: False`), `extend` continues it,
   `centered "CHAPTER ONE"` is a centred narration line.
7. `call intro from _call_intro_1` runs `intro` (music/queue/sound/pause/voice sustain)
   and returns to `start`.
8. The `for route_name in ROUTES:` loop emits three narration lines
   ("Route option: study/rest/explore").
9. `jump pick_route` reaches the **named menu** `pick_route` (also registered as a label).
10. With `gold = 5`, the choices shown are "Study in the library." and
    "Buy a coffee first." — the `else:` branch ("Walk home.") is filtered out.
11. Choice 0 → `route = "study"` → `label study` → sunset, `vcentered "THE END"`,
    hide, `stop music fadeout 2.0`, return → `END (study)`.

Choosing the coffee branch instead runs `call screen confirm(...)` (event carries
`args`), `show screen hud(score=gold)` and `hide screen hud` before `study`.

Tests: `tests/test_renpy_compat.py` (construct-by-construct) and
`tests/test_renpy_corpus.py` (the same machinery against a real game).
