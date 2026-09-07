# Example 00 — Minimal Dialogue
# Kinetic novel proof: narration + character dialogue + typewriter

define e = Character("Eileen", color="#c8ffc8")

label start:
    "This is narration. The engine is running inside UPBGE (or headless)."
    e "This is dialogue. Hello from UPVN!"
    e "The engine can advance one line at a time on click or space."
    "Every line here blocks until player input, just like Ren'Py."
    return
