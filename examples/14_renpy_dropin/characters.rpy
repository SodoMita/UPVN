# UPVN example 14 — drop-in Ren'Py tier: declarations
# Everything here is stock Ren'Py syntax: no UPVN-specific keywords.

init offset = -2

# dotted defines become store namespaces (gui.accent_color, config.window_title)
define gui.accent_color = "#002ead"
define gui.text_size = 24
define config.window_title = "UPVN — Ren'Py drop-in example"

define narrator = Character(None, kind=nvl)
define mc = DynamicCharacter("player_name", color="#c8ffc8")
define e = Character("Eileen", color="#c8ffc8",
                     what_prefix="“", what_suffix="”")

# `default` values are applied when a new game starts
default player_name = "Sam"
default route = "none"
default visited = []
default gold = 5
default preferences.text_speed = 60

init python hide:
    # executed once at init, like Ren'Py does
    GREETING = _("Welcome to the drop-in tier")
    ROUTES = ["study", "rest", "explore"]

image bg classroom = "images/classroom.png"
image bg sunset = "images/sunset.png"
image eileen happy = "images/eileen_happy.png"
image eileen concerned = "images/eileen_concerned.png"
