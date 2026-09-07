# Example 01 — Branching Choice
# Proves labels, menus, jumps
define e = Character("Eileen", color="#c8ffc8")

label start:
    e "Where should we go?"

    menu:
        "Library":
            jump library

        "Rooftop":
            jump rooftop

label library:
    e "Quiet. Good choice. The library smells like old paper."
    jump ending

label rooftop:
    e "Windy up here. But the view is worth it."
    jump ending

label ending:
    "The scene ends. Return to title."
    return
