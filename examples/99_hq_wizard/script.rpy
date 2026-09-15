state:
    affection: int = 0
    route: str = "none"
    has_book: bool = False

character e:
    name "Eileen"
    color "#c8ffc8"

character s:
    name "Sylvie"
    color "#c8c8ff"

image "bg classroom" = "backgrounds/bg_classroom.png"
image "bg library" = "backgrounds/bg_lecturehall.png"
image "bg meadow" = "backgrounds/bg_meadow.png"

stage classroom_3d = "stages/classroom_3d.blend"

label start:
    scene bg classroom with fade
    show eileen at center with dissolve
    e "Welcome to HQ Wizard Demo! This game was built with one click — no coding."
    "You can create your own story from the UPVN panel without typing .rpy."
    camera zoom 1.2 duration 0.8 with ease
    e "Let's make a choice that matters."
    menu:
        "What will you do?"
        choice "Help Eileen":
            jump help_eileen
        choice "Explore library":
            jump explore_library

label help_eileen:
    set affection += 1
    set route = "help"
    scene bg classroom with dissolve
    show eileen happy at center with move
    e "Thank you! You are so kind."
    e "I was looking for my book..."
    menu:
        "Do you have it?"
        choice "Give her the book":
            jump give_book
        choice "Say you don't":
            jump no_book

label explore_library:
    set route = "library"
    scene bg library with fade
    camera zoom 1.5 duration 1.0 with ease
    "The library is quiet. Rows of books stretch into the distance."
    show sylvie at right with move
    s "Oh, hello! Are you looking for something?"
    e "Hi Sylvie! Have you seen my book?"
    s "I think I saw one near the back..."
    menu:
        "Search for the book"
        choice "Search together":
            jump search_together
        choice "Search alone":
            jump search_alone

label give_book:
    set has_book = True
    set affection += 2
    show eileen happy at center with dissolve
    e "You found it! I knew I could count on you."
    jump classroom_3d_scene

label no_book:
    e "Oh... maybe I left it in the library."
    jump explore_library

label search_together:
    set affection += 1
    s "Let's look together!"
    "You and Sylvie search through the shelves..."
    pause 0.5
    e "Found it!"
    set has_book = True
    jump classroom_3d_scene

label search_alone:
    "You search alone, but can't find it."
    s "Need help?"
    jump search_together

label classroom_3d_scene:
    scene bg classroom with fade
    load_stage classroom_3d
    show3d eileen at marker_eileen
    camera preset wide
    "You return to the classroom. The 3D stage shows your characters in space."
    if has_book:
        e "Now I can finally study! Thank you so much!"
        set affection += 1
    else:
        e "I still can't find my book... but thanks for trying."
    end
    if affection >= 3:
        jump good_ending
    else:
        jump neutral_ending
    end

label good_ending:
    scene bg meadow with fade
    camera zoom 1.0 duration 1.0 with ease
    show eileen happy at center with dissolve
    show sylvie at right with dissolve
    e "This is the best day ever!"
    s "I'm glad everything worked out."
    "Good Ending — Affection [affection], Route [route]"
    return

label neutral_ending:
    scene bg classroom with fade
    show eileen at center
    e "Well, it was an okay day."
    "Neutral Ending — Try to get more affection next time!"
    return
