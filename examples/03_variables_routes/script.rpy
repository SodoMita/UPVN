# Example 03 — Variables and Routes
# Exercises default, $ assignment, if/else, interpolation

define e = Character("Eileen", color="#c8ffc8")

default affection = 0
default helped_eileen = False
default route = "none"

label start:
    e "Can you help me carry these books?"

    menu:
        "Help her":
            $ affection += 1
            $ helped_eileen = True
            $ route = "good"
            e "Thanks! You're really kind."

        "Say you're busy":
            $ route = "neutral"
            e "Oh. Okay. I understand."

    if affection >= 1:
        jump good_scene
    else:
        jump neutral_scene

label good_scene:
    e "I'm glad you helped me earlier. It meant a lot."
    e "You chose route [route] and affection is [affection]."
    jump ending

label neutral_scene:
    e "Maybe next time you can help."
    e "You chose route [route] and affection stayed at [affection]."
    jump ending

label ending:
    "End of example 03."
    return
