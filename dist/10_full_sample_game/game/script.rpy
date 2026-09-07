define e = Character("Eileen", color="#c8ffc8")
define s = Character("Sylvie", color="#c8c8ff")
define m = Character("Mei", color="#ffc8c8")
define narrator = Character("Narrator", color="#ffffff")

default affection = 0
default book = False
default route = "none"
default has_key = False

label start:
    scene bg classroom with fade
    "Welcome to the UPVN 30-min Showcase — every milestone in one game."
    "This demo exercises: say, Character, scene/show/hide, menu/jump, $/if, play music, with fade/dissolve, save/load (arbitrary), history (H), rollback (wheel), move/zoom, 3D stage, and Blender editor tools."
    e "Hi! I'm Eileen. Let's test the kinetic engine — click to advance."
    s "And I'm Sylvie. The text here uses {b}bold{/b}, {i}italic{/i}, and {color=#ffaaaa}color{/color}."
    "You can press {b}H{/b} for history backlog (stripped view) and {b}Q{/b} for quick menu — both overlays, non-blocking."
    $ affection = 0
    $ book = False
    menu:
        "Meet in the library? (tests menu + jump + $)":
            $ affection += 1
            jump library
        "Stay in classroom (tests branching)":
            jump classroom

label library:
    scene bg lecturehall with dissolve
    show sylvie at left with move
    s "You chose the library. Affection is now [affection]."
    show eileen at right with ease
    e "I moved with {b}ease{/b} — not snap! (ATL-lite move/zoom)"
    camera zoom 1.2 duration 1.0 with ease
    "Camera zoomed 1.2× with ease (headless + UPBGE)."
    camera zoom 1.5 duration 1.0 with linear
    "Now linear zoom to 1.5×."
    camera zoom 1.0 duration 0.8 with ease
    "Back to 1.0×."
    menu:
        "Pick up the book (tests $ + if)":
            $ book = True
            $ has_key = True
            jump book_taken
        "Leave it":
            jump book_left

label book_taken:
    s "You picked it up! Book is [book]."
    if has_key:
        "You have the key now."
    else:
        "No key."
    jump classroom

label book_left:
    s "You left it. Book is [book]."
    jump classroom

label classroom:
    scene bg classroom with fade
    show eileen at center with dissolve
    if book:
        e "You brought the book — affection [affection]!"
        $ route = "good"
    else:
        e "No book — but we can still proceed. Affection [affection]."
        $ route = "neutral"
    # 3D hybrid — not black fallback
    load_stage classroom_3d
    show3d eileen at marker_eileen
    show3d sylvie at marker_sylvie
    anim eileen wave
    camera preset closeup_eileen
    "Hybrid 3D: VN dialogue over live UPBGE stage — 2D sprites over 3D capsules, no black fallback."
    show eileen at left with move
    e "I slide left over 3D — hybrid coexistence."
    show eileen at center with move
    e "Back to center."
    # audio
    play music "theme" fadein 1.0
    "Music playing (JSON save will capture this)."
    play sound "knock.ogg"
    "Sound played."
    # pause
    pause 0.5
    # save demo arbitrary
    "Try saving to arbitrary slot 42 or 500 — saves are 1..∞ with pagination (6/page, ←→)."
    "Press S for quick save, Q for quick menu, H for history."
    menu:
        "Save to slot 42 and continue (good ending)":
            $ affection += 1
            jump good_ending
        "Save to slot 500 and see neutral":
            $ affection = 0
            jump neutral_ending
        "Rollback test — choose then wheel up":
            jump rollback_demo

label good_ending:
    scene bg meadow with fade
    show eileen happy at center with dissolve
    e "Good ending! Affection [affection], route [route], book [book]. Thanks for playing UPVN!"
    "30-min showcase would continue here with more chapters — this is a condensed demo exercising all systems."
    return

label neutral_ending:
    scene bg uni with fade
    show sylvie at center with dissolve
    s "Neutral ending. Affection [affection]."
    return

label rollback_demo:
    e "This line is for rollback test — press wheel up to rollback, wheel down to roll forward."
    e "Second line — rollback should restore previous variables."
    $ affection = 99
    e "Affection set to 99 — rollback 2 steps should restore earlier."
    return
