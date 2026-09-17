state:
    courage: int = 0
    magic: bool = False
    route: str = "none"

character k:
    name "Kael"
    color "#ffcc66"

character l:
    name "Lyra"
    color "#aa88ff"

image "bg forest" = "backgrounds/bg_forest.png"
image "bg castle" = "backgrounds/bg_castle.png"
image "bg mountain" = "backgrounds/bg_mountain.png"

label start:
    scene bg forest with fade
    show kael at center with dissolve
    camera zoom 1.1 duration 1.0 with ease
    k "Welcome to Fantasy Adventure! The forest grows dark ahead."
    "A knight stands at the crossroads, sword at his side."
    menu:
        "The path splits:"
        choice "Take the mountain road":
            jump mountain_road
        choice "Enter the dark cave":
            jump dark_cave

label mountain_road:
    set courage += 1
    set route = "mountain"
    scene bg mountain with dissolve
    "The mountain wind howls. Stones shift beneath your boots."
    show lyra at right with move
    l "You dare climb in this storm? You must be brave — or foolish."
    k "Perhaps both. But I seek the Dragon’s Peak."
    menu:
        "Lyra offers help:"
        choice "Accept her aid":
            jump accept_magic
        choice "Climb alone":
            jump climb_alone

label dark_cave:
    set route = "cave"
    scene bg forest with fade
    camera zoom 1.4 duration 0.8 with ease
    "The cave breathes cold air. Something glitters in the dark..."
    k "A crystal! It pulses with ancient magic."
    set magic = True
    set courage += 2
    jump dragon_encounter

label accept_magic:
    set magic = True
    set courage += 1
    l "Take this enchantment. It will shield you from dragon fire."
    jump dragon_encounter

label climb_alone:
    set courage += 2
    k "I need no magic — only courage."
    jump dragon_encounter

label dragon_encounter:
    scene bg castle with fade
    show kael at left with dissolve
    "At the peak, a dragon awaits. Its eyes burn like embers."
    if magic:
        k "The enchantment shields me! The dragon bows its head."
        "The dragon recognizes the ancient magic and grants safe passage."
        set courage += 2
    else:
        k "Stand back! I'll face it with steel alone!"
        "The battle is fierce, but your courage prevails."
    end
    if courage >= 4:
        jump dragon_friend
    else:
        jump dragon_survive
    end

label dragon_friend:
    scene bg mountain with fade
    show lyra at center with dissolve
    l "You didn't just survive — you befriended the dragon!"
    "Legendary Ending — Courage [courage], Magic: [magic]"
    return

label dragon_survive:
    scene bg forest with fade
    show kael at center
    k "I lived to tell the tale. That counts for something."
    "Survivor Ending — Try for more courage or magic next time!"
    return
