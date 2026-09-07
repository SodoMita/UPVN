# Expected Behavior: Example 02 Sprites and Backgrounds + 3D stubs

1. `scene bg classroom with fade` -> scene event, background = "bg classroom", shown_actors cleared.
2. `show eileen neutral at center` -> show event, actor eileen at center.
3. Dialogue about background/character.
4. `show eileen happy at center with dissolve` -> replaces same tag (happy), no duplicate.
5. `hide eileen with dissolve` -> hide event, actor removed.
6. `scene bg hallway with fade` -> background changed to hallway.
7. 3D stubs:
   - `load_stage classroom_3d` -> stage = classroom_3d
   - `camera preset medium_shot` -> camera preset
   - `show3d eileen at marker_eileen` -> stage_objects[eileen]
   - `anim eileen idle` -> anim state
   - `camera preset closeup_eileen` -> camera preset changed.
8. Headless: trace contains all above in order.
9. UPBGE: planes appear at correct positions; stage collection loads (when blend template has 3D classroom mesh + markers).

Acceptance: `test_02_sprites_and_3d_stubs` green; UPBGE visual check shows plane swaps + 3D behind.
