# ============================================================
# UPVN — full .rpy tier (drop-in Ren'Py) example
#
# This script exercises the full Ren'Py-compatible language:
#   - define Character(...)      (works exactly like Ren'Py)
#   - init python: / init:       embedded Python at init time
#   - python:                    embedded Python blocks
#   - default                    defaults
#   - label name(params):        label parameters
#   - call label(args)           calls with arguments
#   - jump/call expression       computed target labels
#   - while / break / continue   loops
#   - $ x += 1 / $ python()      one-line Python
#   - menu choices "Text" if cond:  conditional choices
#   - window / nvl / voice / queue music|sound
#   - show/hide/call screen + screen/style/transform/translate blocks
#
# Parse with:  python tools/run_headless.py examples/12_full_rpy_tier/script.rpy --mode full --choices 0
# ============================================================

define e = Character("Eileen", color="#c8ffc8")
define narrator = Character(None, color="#ffffff")

# init-time embedded Python (full tier)
init python:
    greeting = "Welcome to the library"
    bonus_points = 3

# init block with a plain define inside
init:
    define music_volume = 0.8

init offset = 1

# ATL-lite transform block (parsed declaratively; scalar props recorded)
transform fade_in:
    alpha 0.0
    linear 0.5 alpha 1.0

# screen/style blocks (captured for the editor-built UI layer)
screen hud:
    text "Affection: [points]"

style hud_text:
    size 20

# translations are captured per-language (not applied at runtime yet)
translate russian start:
    e "Dobro pozhalovat'"

default points = 0
default read_book = False
default next_label = "after_loop"

label start():
    window show
    e "[greeting]."
    e "You have [points] points."

    # conditional menu choices — hidden unless the condition holds
    menu:
        "Ask about the book." if points >= 0:
            jump book
        "Leave without a word.":
            jump leave

label book(name="magic tome"):
    python:
        points += bonus_points
    nvl clear
    nvl mode nvl
    e "The [name] sits on the shelf."
    e "Let's count to ten to make sure loops work:"

    # while / if / break — full control flow
    while points < 10:
        $ points += 1
        if points >= 9:
            break

    e "Stopped at [points]."

    # computed jump target
    jump expression next_label

label after_loop():
    voice "voice/line01.ogg"
    queue music "music/theme.ogg" fadein 1.0
    queue sound "sfx/page_turn.ogg"
    show screen hud
    call describe("the tale of two cities")
    hide screen hud
    window auto
    return

label describe(title=""):
    e "It tells [title]."
    return

label leave():
    e "You step back into the rain."
    window hide
    return
