# UPVN example 14 — drop-in Ren'Py tier: story
#
# Every construct below is stock Ren'Py and is used by real shipped games
# (the milestone was driven by the 61-file freeCodeCamp/LearnToCodeRPG corpus).
# Run it headless:
#     python -m tools.run_headless examples/14_renpy_dropin --mode full --choices 0 0

label start:
    # triple-quoted text and a line continuation
    """The drop-in tier accepts the syntax real Ren'Py games are written in."""
    $ long_line = 1 + \
        2

    scene bg classroom with Dissolve(0.5)
    show eileen happy at left, right with fade
    e happy smile "Hi [player_name]! Ready to test the drop-in tier?"

    # voice attribute, negated image attribute, nointeract
    mc @ surprised "Sure!"
    e -concerned "Great."
    e "This line does not wait for a click." nointeract
    extend " …and this one continues it."
    centered "CHAPTER ONE"

    # `from` clauses (Ren'Py inserts them for save compatibility)
    call intro from _call_intro_1

    # a `for` loop over a store list
    for route_name in ROUTES:
        "Route option: [route_name]"

    # a named menu is also a jump/call target
    jump pick_route

label intro:
    e "Let me show you around."
    play music "audio/theme.ogg" fadein 1.0 loop
    queue music "audio/theme2.ogg"
    play sound "audio/chime.ogg"
    pause 0.5
    pause 1.0 with fade
    voice sustain
    return

label pick_route:
    menu pick_route:
        set visited

        "Study in the library.":
            $ route = "study"
            jump study

        if gold > 3:
            "Buy a coffee first.":
                $ gold -= 1
                jump coffee

        else:
            "Walk home.":
                $ route = "rest"
                jump rest

label coffee:
    e "Good choice."
    call screen confirm("Enjoy your coffee?", Return(True))
    show screen hud(score=gold)
    hide screen hud
    jump study

label study:
    e "Here we are."
    scene bg sunset with fade
    vcentered "THE END"
    hide eileen with dissolve
    stop music fadeout 2.0
    return

label rest:
    e "See you tomorrow!"
    return
