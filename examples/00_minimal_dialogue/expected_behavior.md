# Expected Behavior: Example 00 Minimal Dialogue

1. Game starts at `label start`.
2. First narration appears without namebox: "This is narration…"
3. Player clicks or presses space -> advances.
4. Second line: Eileen namebox (`#c8ffc8`) + "This is dialogue…"
5. Third line: Eileen again.
6. Fourth narration.
7. `return` at end triggers `END` event; game stops cleanly.
8. History contains 4 entries in order; `rollback_stack` has entry per say.
9. Headless: `VNController("examples/00…").run_headless()` yields trace `say,say,say,say,return,end` (16 chars of interpolation not needed).

Acceptance: `pytest tests/test_interpreter.py::test_00_headless` green; manual UPBGE press P then 4 clicks ends.
