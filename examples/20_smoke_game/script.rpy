# Example 20 — Smoke Game (M25 Usability Stabilization Freeze)
# The one script every release must pass: dialogue, sprites, choices,
# save/load, rollback, quit. Intentionally plain — no fancy syntax.

define e = Character("Eileen")

default route = "none"

label start:
    scene bg classroom
    show eileen happy at center
    e "Line one."
    e "Line two."

    menu:
        "Go left":
            $ route = "left"
            jump left

        "Go right":
            $ route = "right"
            jump right

label left:
    e "You chose left."
    jump save_test

label right:
    e "You chose right."
    jump save_test

label save_test:
    e "Save, load, rollback, and continue from here."
    e "Route is [route]."
    return
