# Example 20 — Smoke Game: expected behavior

This is the M25 release gate. Every release must play this script in real
UPBGE (add-on → template → Setup Scene → P, or `blenderplayer` on the
template) without a single console traceback, and headless:

    python3 tools/run_headless.py examples/20_smoke_game/script.rpy --choices 0

Trace (choices 0):

1. scene bg classroom
2. show eileen happy at center
3. say Eileen "Line one."
4. say Eileen "Line two."
5. menu ["Go left", "Go right"]
6. choice 0 -> $ route = "left"; jump left
7. say Eileen "You chose left."
8. jump save_test
9. say Eileen "Save, load, rollback, and continue from here."
10. say Eileen "Route is left."
11. return (end)

Choice 1 mirrors steps 6-10 with route "right".

Automated visual walkthrough (Xvfb + llvmpipe, see docs/SANDBOX_UPBGE.md):

    bash tools/smoke_walkthrough.sh

Manual UPBGE checklist: docs/MANUAL_QA.md.
