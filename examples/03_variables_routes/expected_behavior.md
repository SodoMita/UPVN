# Expected Behavior: Example 03 Variables and Routes

1. Defaults: affection=0, helped_eileen=False, route="none" at start.
2. Eileen asks for help, menu ["Help her","Say you're busy"].
3. Pick Help her:
   - $ affection +=1 -> 1
   - $ helped_eileen = True
   - $ route="good"
   - Eileen thanks
   - if affection>=1 true -> jump good_scene -> interpolation "[route]" -> "good", "[affection]" -> "1"
4. Pick Say busy:
   - $ route="neutral"
   - Eileen ok
   - if false -> jump neutral_scene -> interpolation "neutral"/"0"
5. Both routes jump to ending -> "End of example 03." -> return -> end.
6. Save/load: saving before choice then loading allows trying other path (see test_save_load_roundtrip).

Acceptance: both headless paths produce correct variable states (1/True/good vs 0/False/neutral) and interpolated texts.
