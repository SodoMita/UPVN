define e = Character("Eileen", color="#c8ffc8")
define s = Character("Sylvie", color="#c8c8ff")

label start:
    scene bg classroom
    e "This game was built with 3 lines of Python, no .rpy typing!"
    "UPVN Blender tools let you click to create."
    menu:
        "Try arbitrary saves?"
        "Yes, save to slot 99":
            jump save_demo
        "No, end":
            jump end_label

label save_demo:
    "Yes, save to slot 99 chosen."
    return

label end_label:
    "No, end chosen."
    return
