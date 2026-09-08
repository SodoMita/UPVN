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
