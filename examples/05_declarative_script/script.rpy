# UPVN declarative script — the canonical (non-Python) forms.
#
# The language is declarative: no `python:` blocks, no `$` needed.
# `$`, `define` and `default` still parse (legacy aliases), but the
# recommended forms below are what the editor generates.

# ---- asset manifest (declarative) --------------------------------------
image "bg classroom" = "backgrounds/classroom.png"
image eileen happy = "characters/eileen/happy.png"
image eileen sad = "characters/eileen/sad.png"
audio theme = "music/theme.ogg"
stage classroom_3d = "stages/classroom.blend"

# ---- characters (declarative block) ------------------------------------
character e:
    name "Eileen"
    color "#c8ffc8"

# ---- typed state (declarative block) -----------------------------------
state:
    affection: int = 0
    route: str = "none"

label start:
    scene bg classroom with fade
    show eileen happy at center
    e "Hi! Declarative scripts work. Affection is [affection]."

    menu:
        choice "Help Eileen":
            set affection += 1
            set route = "good"
        end
        choice "Ignore her":
            set route = "neutral"
        end
    end

    if affection >= 1:
        jump good
    else:
        jump neutral
    end
    return
end

label good:
    e "Thanks for helping! Route [route], affection [affection]."
    return
end

label neutral:
    e "Maybe next time. Route [route]."
    return
end
