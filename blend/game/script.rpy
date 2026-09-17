define e = Character("Eileen", color="#c8ffc8")
define s = Character("Sylvie", color="#9dd3f5")

label start:
    scene bg classroom
    show eileen at center
    e "Hi! I'm Eileen. Welcome to our school."
    s "I'm Sylvie. What would you like to do today?"
    menu:
        "Visit the library":
            jump lib
        "Walk in the park":
            jump park
        "Study together":
            jump study
    return

label lib:
    e "The library is quiet and cozy."
    return

label park:
    e "The park is sunny and warm."
    return

label study:
    s "Let's study together!"
    return
