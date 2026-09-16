# UPVN Tutorial — Recreating the Ren'Py Tutorial in UPBGE

This guide walks you through building a complete visual novel in **UPBGE** using
the **UPVN** add-on, step by step, covering the same topics as the official
Ren'Py Tutorial — but using the UPVN panel in Blender instead of writing `.rpy`
files by hand.

**What you need:**
- UPBGE 0.50 (Blender 5.0.1) installed
- The UPVN add-on (`dist/upvn_editor_addon_v0.7.1.zip`) installed and enabled
- Engine shows **✓ Engine: OK** in the UPVN sidebar tab

**What you'll learn:**
1. Creating a project (one click)
2. Writing dialogue (no typing `.rpy`)
3. Adding images and scenes
4. Positioning sprites
5. Transitions (fade, dissolve, move)
6. Music and sound effects
7. Choices and variables (branching)
8. Input and variable interpolation
9. Testing and previewing

---

## Part 1 — Creating a New Game

In Ren'Py, you click "Create New Project" in the launcher. In UPVN, you do the
same thing from the Blender sidebar.

### Steps

1. **Open UPBGE.** Launch `blender` from your UPBGE install.

2. **Open the UPVN panel.** In the 3D Viewport, press `N` to open the sidebar.
   Click the **UPVN** tab. You should see:
   ```
   ✓ Engine: OK (repo root)
   ```

3. **Create your project.** In the **Project** section:
   - Set **Script Path** to `//game/script.rpy` (the default is fine).
   - Click **Create UPVN Project**.
   
   This creates `game/script.rpy` with a starter script using declarative
   syntax. No Python coding needed.

4. **Or use the Quick Wizard** for a complete branching story:
   - Set a **Game Title** (e.g. "My First VN").
   - Pick a **Theme** (school, fantasy, scifi, mystery).
   - Click **Quick VN Wizard**.
   
   The wizard creates a full game with characters, variables, menus, and
   two endings — all in one click.

### What was created

The file `game/script.rpy` now contains something like:

```
state:
    affection: int = 0
    route: str = "none"

character e:
    name "Eileen"
    color "#c8ffc8"

character s:
    name "Sylvie"
    color "#c8c8ff"

label start:
    scene bg classroom with fade
    show eileen at center with dissolve
    e "Hello from Blender! This game was created with clicks, not code."
    ...
```

You can view this file in Blender's **Text Editor** — open `script.rpy` from
the text dropdown. But you don't need to edit it by hand for most tasks.

---

## Part 2 — Writing Dialogue

In Ren'Py, you write dialogue as `e "Hello!"` in a text file. In UPVN, you
use the **Add Dialogue** button.

### The two kinds of dialogue

| Kind | Ren'Py syntax | UPVN panel |
|------|--------------|------------|
| **Narration** (no speaker) | `"The sun was setting."` | Speaker field = *empty* |
| **Spoken line** | `e "Hello, player!"` | Speaker = `e` |

### Steps

1. In the UPVN panel, find the **Dialogue** section.
2. **Narration:** Leave **Speaker** empty. Type `"The lecture hall was quiet."`
   in **Text**. Click **Add Dialogue**.
3. **Spoken line:** Set **Speaker** to `e`. Type `"Hi! I'm Eileen."`.
   Click **Add Dialogue**.

Each click appends a new line to `game/script.rpy`. You never need to worry
about indentation or quotes — the panel handles it.

### Using characters

Before writing dialogue for a character, you need to define them. If you used
the **Create Project** button, `e` (Eileen) and `s` (Sylvie) are already
defined. To add more:

1. In the **Characters** section, set:
   - **ID**: `l` (short name, used in dialogue)
   - **Name**: `Lucy`
   - **Color**: pick a reddish color
2. Click **Add Character**.

Now you can use `l` as the speaker in dialogue.

### Text formatting

UPVN supports Ren'Py-style text tags in dialogue:

| Tag | Effect | Example |
|-----|--------|---------|
| `{b}text{/b}` | **Bold** | `e "This is {b}important{/b}."` |
| `{i}text{/i}` | *Italic* | `e "A {i}whispered{/i} word."` |
| `[variable]` | Variable interpolation | `e "Affection is [affection]."` |

---

## Part 3 — Adding Images (Scenes and Sprites)

In Ren'Py, you place image files in an `images/` folder and use `scene` and
`show` statements. In UPVN, the workflow is similar but uses the panel.

### Backgrounds (scene)

The `scene` statement sets the background. In UPVN:

1. In the **Scene & Sprites** section, set **Background** to a name like
   `bg classroom`.
2. Optionally, click the folder icon next to **BG Image** to browse for a
   `.png`/`.jpg` file. UPVN will copy it to `assets/backgrounds/`.
3. Click **Add Scene**.

This appends `scene bg classroom` to your script.

**Without an image file**, UPVN renders the scene using its HQ headless
renderer — you get a gradient background with details (windows, floor lines,
etc.) based on the scene name. This is useful for prototyping.

### Sprites (show)

The `show` statement places a character sprite on screen. In UPVN:

1. Set **Asset** to the sprite name (e.g. `eileen` or `eileen happy`).
2. Pick a **Position**: left, center, right, far_left, far_right.
3. Set **With** to a transition: `move`, `dissolve`, or leave empty.
4. Optionally, attach a sprite image via **Sprite Image**.
5. Click **Add Show**.

### Hiding sprites

To remove a character from the scene:

1. Set **Asset** to the character's tag (e.g. `eileen`).
2. In the panel, use **Add Hide** (or manually write `hide eileen`).

In practice, `scene` clears everything and `show` replaces the same tag, so
`hide` is rarely needed.

---

## Part 4 — Positioning Images

Ren'Py uses `left`, `center`, `right` as built-in positions, plus custom
transforms with `xalign`/`yalign`. UPVN supports both.

### Built-in positions

When you click **Add Show**, the **Position** dropdown offers:

| Position | Effect |
|----------|--------|
| `left` | Left third of screen |
| `center` | Center |
| `right` | Right third |
| `far_left` | Far left edge |
| `far_right` | Far right edge |

### Example: moving a character

```
show eileen at center
e "I'm in the center."
show eileen at right with move
e "Now I moved to the right."
```

To create this in the panel:
1. **Add Show**: Asset=`eileen`, Position=`center`. Click.
2. **Add Dialogue**: Speaker=`e`, Text=`"I'm in the center."`. Click.
3. **Add Show**: Asset=`eileen`, Position=`right`, With=`move`. Click.
4. **Add Dialogue**: Speaker=`e`, Text=`"Now I moved to the right."`. Click.

---

## Part 5 — Transitions

In Ren'Py, you write `scene bg cave with dissolve`. In UPVN, transitions are
built into the Scene and Show operators.

### Available transitions

| Transition | Effect |
|------------|--------|
| `fade` | Fade to black, then fade in |
| `dissolve` | Cross-fade between old and new scene |
| `move` | Slide sprite from old position to new |
| `None` | Instant change (no transition) |

### Adding transitions

**When changing scenes:**
1. In **Scene & Sprites**, set **Background** and optionally fill **With**
   (e.g. `dissolve`).
2. Click **Add Scene**.
3. This generates: `scene bg library with dissolve`

**When showing/moving sprites:**
1. Set **Asset**, **Position**, and **With** (e.g. `move`).
2. Click **Add Show**.
3. This generates: `show eileen at right with move`

### Camera zoom (UPVN extension)

UPVN adds camera zoom transitions not in basic Ren'Py:

1. In the **Extras** section, set **Zoom** (e.g. `1.2`), **Duration** (e.g.
   `1.0`), and **Easing** (ease, linear, easein, easeout).
2. Click **Add Camera Zoom**.

This generates: `camera zoom 1.2 duration 1.0 with ease`

---

## Part 6 — Music and Sound Effects

Ren'Py uses `play music`, `stop music`, `play sound`. UPVN has buttons for
these.

### Background music

1. In the **Extras** section, set **Audio Asset** to a name (e.g. `theme`).
2. Optionally, click the folder icon to browse for an audio file
   (`.ogg`, `.opus`, `.mp3`). UPVN copies it to `assets/audio/`.
3. Click **Add Music/Sound**.

This generates: `play music "theme"`

### Stopping music

To stop music, add a line manually or use the **Add Dialogue** with the script
text editor to write `stop music` in the appropriate label.

### Sound effects

Sound effects use `play sound` instead of `play music`. In UPVN, you can
manually write `play sound "click.ogg"` in the script, or use the panel's
audio asset browser.

---

## Part 7 — Choices and Variables (Branching)

This is where visual novels get interesting. In Ren'Py, you write `menu:` blocks.
In UPVN, the panel generates them for you.

### Adding a menu (choice)

1. In the **Menu (Branching)** section, fill in:
   - **Menu Caption**: `"What will you do?"`
   - **Choice 1**: `"Help Eileen"` → **Jump 1**: `help_eileen`
   - **Choice 2**: `"Explore alone"` → **Jump 2**: `explore_alone`
2. Click **Add Menu**.

This generates:
```
menu:
    "What will you do?"
    choice "Help Eileen":
        jump help_eileen
    choice "Explore alone":
        jump explore_alone
```

UPVN automatically creates placeholder labels for the jump targets so they
always exist. You fill them in later with real content.

### Adding variables (state)

In Ren'Py, you write `$ affection += 1`. In UPVN, you use declarative `set`:

1. In the **Variables — State** section:
   - **Variable**: `affection`
   - **Type**: `int`
   - **Value**: `0`
2. Click **Add Variable**.

This adds to the `state:` block:
```
state:
    affection: int = 0
```

### Changing variables

1. In the **Logic — No Python Needed** section:
   - **Set Variable**: `affection`
   - **Op**: `+=`
   - **Expression**: `1`
2. Click **Add Set**.

This generates: `set affection += 1`

### Conditional branching

1. Set **If Condition** to `affection >= 3`.
2. Click **Add If**.
3. Add dialogue for the true case.
4. Click **Add Else**.
5. Add dialogue for the false case.
6. Click **Add End**.

This generates:
```
if affection >= 3:
    e "You've been so kind!"
else:
    e "Maybe next time."
end
```

### Full branching example (using the panel)

Here's how to recreate the Ren'Py Tutorial's choice example entirely from the
panel:

1. **Add Dialogue**: Speaker=`e`, Text=`"Do you like visual novels with choices?"`
2. **Add Menu**: Caption=`"What do you prefer?"`,
   Choice1=`"Yes, I do."` → Jump1=`choice_yes`,
   Choice2=`"No, I don't."` → Jump2=`choice_no`
3. **Add Label**: Label=`choice_yes`
4. **Add Set**: Variable=`liked_choices`, Op=`=`, Expr=`True`
5. **Add Dialogue**: Speaker=`e`, Text=`"Great! Choices make games interactive."`
6. **Add Jump**: Target=`choice_done`
7. **Add Label**: Label=`choice_no`
8. **Add Set**: Variable=`liked_choices`, Op=`=`, Expr=`False`
9. **Add Dialogue**: Speaker=`e`, Text=`"Kinetic novels are fun too!"`
10. **Add Jump**: Target=`choice_done`
11. **Add Label**: Label=`choice_done`
12. **Add If**: Condition=`liked_choices`
13. **Add Dialogue**: Speaker=`e`, Text=`"I remember you like choices."`
14. **Add Else**
15. **Add Dialogue**: Speaker=`e`, Text=`"I remember you prefer kinetic novels."`
16. **Add End**

---

## Part 8 — Input and Variable Interpolation

Ren'Py lets you show variable values in dialogue using `[variable]`. UPVN
supports this natively.

### Showing variable values

Write dialogue text with `[variable]` syntax:

```
e "Your affection level is [affection]."
e "Current route: [route]."
```

The engine replaces `[affection]` with the current value of the `affection`
variable at runtime.

### Setting variables from choices

Combine menus with `set` to make choices affect the story:

```
menu:
    "Give her the book?"
    choice "Yes":
        jump give_book
    choice "No":
        jump refuse

label give_book:
    set has_book = True
    set affection += 2
    e "Thank you! [affection] affection now."
    ...

label refuse:
    set affection -= 1
    e "Oh... [affection] affection now."
    ...
```

---

## Part 9 — Testing and Previewing

### Headless preview (no UPBGE needed)

From the command line:

```bash
# Run the full game headlessly
python -m tools.run_headless game/script.rpy --mode full

# Run with specific choices
python -m tools.run_headless game/script.rpy --mode full --choices 0 1

# Generate a preview screenshot
python -m tools.run_headless game/script.rpy --mode full --json
```

### In-UPBGE preview

1. In the UPVN panel, click **Validate** to check for script errors.
2. Click **Preview Screenshot** to generate a headless screenshot.
3. Press **P** in the 3D Viewport to play the game in UPBGE.

### Controls (in-game)

| Key | Action |
|-----|--------|
| Click / Space / Enter | Advance dialogue |
| `1`–`9` | Pick a menu choice |
| `H` | Show history |
| `Q` | Quick menu |
| `Ctrl+S` | Save game |
| `Ctrl+L` | Load game |
| `S` | Skip mode |
| `A` | Auto mode |
| Mouse wheel up | Rollback |
| `F1` | Debug state dump |
| `F12` | Screenshot |

---

## Full Example: The Ren'Py Tutorial's "The Question" in UPVN

Here's how to recreate the core of Ren'Py's "The Question" example using only
the UPVN panel (no `.rpy` typing):

### 1. Create project
- Click **Create UPVN Project**

### 2. Define characters
- **Add Character**: ID=`me`, Name=`Me`, Color=`#ffffff`
- **Add Character**: ID=`s`, Name=`Sylvie`, Color=`#c8c8ff`

### 3. Write the opening
- **Add Scene**: Background=`bg lecturehall`, With=`fade`
- **Add Dialogue**: (narration) `"It's only when I hear the sounds of shuffling
  feet..."`
- **Add Dialogue**: (narration) `"Professor Eileen's lectures are usually
  interesting, but today I just couldn't concentrate."`
- **Add Scene**: Background=`bg uni`, With=`fade`
- **Add Dialogue**: (narration) `"When we come out of the university, I spot her
  right away."`
- **Add Show**: Asset=`sylvie`, Position=`center`, With=`dissolve`

### 4. The first choice
- **Add Dialogue**: Speaker=`s`, Text=`"Hey... do you have a minute?"`
- **Add Menu**: Caption=`"How do you respond?"`,
  Choice1=`"Sure, what's up?"` → Jump1=`sure`,
  Choice2=`"Sorry, I'm busy."` → Jump2=`busy`

### 5. The "sure" branch
- **Add Label**: Label=`sure`
- **Add Set**: Variable=`affection`, Op=`=`, Expr=`1`
- **Add Dialogue**: Speaker=`s`, Text=`"I wanted to ask you something..."`
- **Add Jump**: Target=`proposal`

### 6. The "busy" branch
- **Add Label**: Label=`busy`
- **Add Dialogue**: Speaker=`s`, Text=`"Oh... okay. Maybe later."`
- **Add Set**: Variable=`affection`, Op=`=`, Expr=`0`
- **Add Jump**: Target=`proposal`

### 7. The proposal and ending
- **Add Label**: Label=`proposal`
- **Add Dialogue**: Speaker=`s`, Text=`"Will you marry me?"`
- **Add If**: Condition=`affection >= 1`
- **Add Dialogue**: Speaker=`me`, Text=`"Of course I will!"`
- **Add Dialogue**: (narration) `"{b}Good Ending{/b}."`
- **Add Else**
- **Add Dialogue**: Speaker=`me`, Text=`"I need time to think..."`
- **Add Dialogue**: (narration) `"{b}Neutral Ending{/b}."`
- **Add End**
- **Add Return**

### 8. Play it
- Click **Validate** (should say OK)
- Click **Preview Screenshot** to see the first frame
- Press **P** to play through in UPBGE

---

## Quick Reference — UPVN Panel → Ren'Py Syntax

| UPVN Panel Action | Generated Ren'Py syntax |
|-------------------|------------------------|
| Create Project | `character e:` / `label start:` |
| Add Character | `character l:` / `name "Lucy"` / `color "#ffcccc"` |
| Add Variable | `state:` / `affection: int = 0` |
| Add Scene | `scene bg classroom with dissolve` |
| Add Show | `show eileen at right with move` |
| Add Hide | `hide eileen with dissolve` |
| Add Dialogue (narration) | `"The sun was setting."` |
| Add Dialogue (speaker) | `e "Hello, player!"` |
| Add Menu | `menu:` / `choice "Option A":` / `jump label_a` |
| Add Set | `set affection += 1` |
| Add If / Else / End | `if affection >= 3:` / `else:` / `end` |
| Add Jump | `jump target_label` |
| Add Label | `label new_scene:` |
| Add Pause | `pause 0.5` |
| Add Music | `play music "theme"` |
| Add Camera Zoom | `camera zoom 1.2 duration 1.0 with ease` |

---

## Running Ren'Py SDK Projects Directly

UPVN can also run existing Ren'Py projects without modification:

```bash
# The Question (Ren'Py's example game)
python -m tools.run_headless ~/renpy-8.5.1-sdk/the_question/game/script.rpy \
    --mode full --choices 0 0

# The Ren'Py Tutorial (uses --compat for init python blocks)
python -m tools.run_headless ~/renpy-8.5.1-sdk/tutorial/game/script.rpy \
    --mode full --compat
```

No copying, no conversion — UPVN reads the `.rpy` files in place from the
Ren'Py SDK directory. The `--compat` flag is needed for projects that use
Ren'Py-specific Python modules (`ui`, `renpy.store`, etc.) — init python errors
are collected rather than fatal.
