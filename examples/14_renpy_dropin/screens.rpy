# UPVN example 14 — screens, transforms and styles (captured for the editor)

screen say(who, what) tag dialogue modal False:
    window:
        vbox:
            text who
            text what

screen confirm(message, yes_action) zorder 100:
    frame:
        text message
        textbutton _("Yes") action yes_action
        textbutton _("No") action Return(False)

# M22: screens are *interpreted*, not just captured — this one is rendered into
# a widget tree by `show screen hud(score=gold)` in script.rpy. It exercises
# parameters, a `default`, `for`, `if`, `use` + `transclude`, `has`, and
# `[expr]` interpolation.
default achievements = []

screen panel(title):
    frame:
        has vbox:
            spacing 8
        label title
        transclude

screen hud(score=0):
    tag hud
    zorder 50
    use panel("Status"):
        text "Gold: [score]"
        for a in achievements:
            text "✓ [a]"
        if score > 5:
            textbutton "Claim reward" action Return("claim")
        else:
            text "Keep going."

transform delayed_blink(delay, cycle):
    alpha 0.0
    pause delay
    alpha 1.0
    pause cycle
    repeat

style default:
    font "DejaVuSans.ttf"
    size 24

style.button.text.color = "#ffffff"
style.button hover_background "#002ead"

translate english start_1:
    e "Hello!"
