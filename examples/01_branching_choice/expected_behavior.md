# Expected Behavior: Example 01 Branching Choice

1. Starts at `start`, shows Eileen “Where should we go?” then menu.
2. Menu has caption None, choices ["Library","Rooftop"].
3. Pick Library (0): `jump library` -> Eileen “Quiet…” -> jump ending -> narration “The scene ends.” -> return -> end at `ending`.
4. Pick Rooftop (1): `jump rooftop` -> Eileen “Windy…” -> jump ending -> same final.
5. Both paths produce distinct traces but share final say.
6. Invalid jump raises LabelNotFoundError.

Acceptance: `test_01_both_paths` green — both choices yield correct jumps.
