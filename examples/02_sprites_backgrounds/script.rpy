# Example 02 — Sprites and Backgrounds
# Requires scene/show/hide and transitions (2D planes + 3D stage stubs)
define e = Character("Eileen", color="#aaffaa")

label start:
    scene bg classroom with fade
    show eileen neutral at center

    e "Now we have a background and a character."

    show eileen happy at center with dissolve
    e "Expressions work too — same tag replaces texture."

    hide eileen with dissolve
    "She leaves."

    scene bg hallway with fade
    "The background changed."

    # 3D hybrid stub — these are python-driven, but parsable
    load_stage classroom_3d
    camera preset medium_shot
    show3d eileen at marker_eileen
    anim eileen idle
    e "Behind the planes, a real 3D classroom could be loaded."
    camera preset closeup_eileen
    e "Camera cuts work in 3D too."

    return
