state:
    clues: int = 0
    suspect: str = "none"
    key_found: bool = False

character d:
    name "Detective"
    color "#ff8866"

character m:
    name "Ms. Gray"
    color "#cccccc"

image "bg office" = "backgrounds/bg_office.png"
image "bg manor" = "backgrounds/bg_manor.png"
image "bg garden" = "backgrounds/bg_garden.png"

label start:
    scene bg office with fade
    show detective at center with dissolve
    camera zoom 1.2 duration 1.0 with ease
    "Mystery Adventure. A rainy night. The phone rings."
    m "Detective? I need your help. My husband has vanished."
    d "Tell me everything. Start from the beginning."
    menu:
        "Where to begin the investigation:"
        choice "Search the manor":
            jump search_manor
        choice "Check the garden":
            jump check_garden

label search_manor:
    set suspect = "manor"
    scene bg manor with dissolve
    show detective at left with move
    show ms_gray at right with move
    d "When did you last see your husband?"
    m "Yesterday evening. He was in his study, as usual."
    "You notice a torn letter in the fireplace. Only half burned."
    menu:
        "The letter is partially readable:"
        choice "Read the fragment":
            jump read_fragment
        choice "Search the study":
            jump search_study

label check_garden:
    set suspect = "garden"
    scene bg garden with fade
    show detective at center with dissolve
    "The garden is overgrown. A fresh footprint in the mud."
    d "Someone was here recently — and they were in a hurry."
    set clues += 1
    "Near the greenhouse, you find a rusty key hidden in a planter."
    set key_found = True
    set clues += 1
    jump revelation

label read_fragment:
    set clues += 2
    d "The letter mentions a safe deposit box... and a flight to Paris."
    m "He never told me about any box!"
    d "People rarely tell their spouses everything."
    jump revelation

label search_study:
    set clues += 1
    "The study is meticulously organized — except for one drawer."
    d "This drawer was forced open. Recently."
    set key_found = True
    jump revelation

label revelation:
    scene bg office with fade
    show detective at center with dissolve
    d "I think I know what happened to your husband."
    if clues >= 3:
        d "He staged his own disappearance. The letter, the key, the garden — all deliberate."
        m "You mean... he's alive?"
        d "Very much so. He's in Paris by now."
        jump solved
    else:
        d "I have a theory, but I need more evidence."
        m "Please, detective. Find him."
        jump unsolved
    end

label solved:
    scene bg manor with fade
    show ms_gray at center with dissolve
    m "Thank you, detective. At least now I know the truth."
    "Solved Ending — Clues [clues], Key found: [key_found]"
    return

label unsolved:
    scene bg office with fade
    show detective at center
    d "The case remains open. But I'll find the truth."
    "Unsolved Ending — Gather more clues next time!"
    return
