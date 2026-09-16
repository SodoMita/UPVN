state:
    trust_ai: int = 0
    route: str = "none"
    scanned: bool = False

character c:
    name "Captain Zara"
    color "#66ccff"

character a:
    name "ARIA"
    color "#66ffaa"

image "bg bridge" = "backgrounds/bg_bridge.png"
image "bg corridor" = "backgrounds/bg_corridor.png"
image "bg planet" = "backgrounds/bg_planet.png"

label start:
    scene bg bridge with fade
    show zara at center with dissolve
    camera zoom 1.1 duration 0.8 with ease
    c "Captain's log — Scifi Adventure. Day 47 in deep space."
    a "Captain, I'm detecting an anomalous signal from Sector 7."
    "ARIA, the ship's AI, projects a holographic display."
    menu:
        "The signal is unusual:"
        choice "Investigate the signal":
            jump investigate
        choice "Stay on course":
            jump stay_course

label investigate:
    set trust_ai += 1
    set route = "signal"
    scene bg corridor with dissolve
    c "ARIA, plot a course to Sector 7."
    a "Course plotted. ETA: 3 hours. Captain... be careful."
    menu:
        "Approaching the anomaly:"
        choice "Scan the anomaly":
            jump scan_anomaly
        choice "Hail on open frequency":
            jump hail

label stay_course:
    set route = "course"
    scene bg bridge with fade
    a "Understood. Maintaining heading."
    "But hours later, the signal grows stronger..."
    c "ARIA, what's happening?"
    a "The signal is following us. It wants to be found."
    set trust_ai += 1
    jump alien_contact

label scan_anomaly:
    set scanned = True
    set trust_ai += 1
    a "Scan complete. It's a derelict ship — pre-warp era."
    c "Life signs?"
    a "One. Faint. Humanoid."
    jump alien_contact

label hail:
    c "Unidentified vessel, this is Captain Zara. Respond."
    "Static... then a voice, ancient and tired."
    "\"We have waited... so long...\""
    set trust_ai += 2
    jump alien_contact

label alien_contact:
    scene bg planet with fade
    show zara at left with dissolve
    show aria_hologram at right with dissolve
    if scanned:
        c "The scans show it's safe. Let's make contact."
        set trust_ai += 1
    else:
        c "We go in blind. Stay sharp, ARIA."
    end
    if trust_ai >= 4:
        jump alliance
    else:
        jump mystery_remain
    end

label alliance:
    scene bg planet with fade
    show zara at center with dissolve
    a "Captain! The aliens are peaceful — they're offering a star map!"
    c "A new era for humanity. Thank you, ARIA."
    "Alliance Ending — Trust [trust_ai], Route [route]"
    return

label mystery_remain:
    scene bg bridge with fade
    show zara at center
    c "We'll return someday. Better prepared."
    "Mystery Ending — Build more trust with ARIA next time!"
    return
