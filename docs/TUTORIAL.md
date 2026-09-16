# UPVN Tutorial — Building a Visual Novel in UPBGE

This guide walks you through building a complete visual novel in **UPBGE**
using the **UPVN** engine. It covers the same topics as the official
Ren'Py Tutorial — writing dialogue, scenes, choices, and branching.

**What you need:**
- UPBGE 0.50 (Blender 5.0.1) installed
- The UPVN add-on (`dist/upvn_editor_addon_v0.7.1.zip`) installed and enabled
- Engine shows **✓ Engine: OK** in the UPVN sidebar tab

---

## Before You Start — Important Notes

### Write `.rpy` files directly in Blender's Text Editor

The UPVN panel has buttons like "Add Dialogue", "Add Scene", "Add Menu", etc.
**These buttons have known issues with script file attachment and are not
reliable for building games.** They may fail to append to the correct file,
produce malformed output, or lose track of the current label.

**Recommended workflow:** Write your `.rpy` script directly in Blender's
**Text Editor** (the built-in code editor, not the UPVN panel). Open it from
the editor type dropdown, create or open `script.rpy`, and type your story
there. The syntax is simple — this tutorial teaches it step by step.

The **Create Project** and **Quick Wizard** buttons do work correctly for
creating an initial script file. Use them to get started, then edit the
resulting `script.rpy` in the Text Editor.

### UI Layout — Aspect Ratio

The in-game UI (dialogue box, choice buttons, speaker name) is designed for
**landscape widescreen** (1024×576 or 1280×720). If you use a different
aspect ratio, elements may overlap — especially the menu choices and dialogue
box. Stick to 16:9 or similar widescreen ratios.

### Set Element Colors

UPVN renders sprites and UI planes using `Object Color` (the color property on
each object). To change how characters and UI look:

1. In the 3D Viewport, select the object (e.g. `Sprite_center`, `Dialogue_Box`,
   `choice_0`).
2. In the **Object Properties** panel (orange square icon), find **Viewport
   Display → Color**.
3. Change the RGBA color to whatever you want.
4. The engine reads `obj.color` at runtime and applies it via an Emission
   shader — no material editing needed.

Common objects to recolor:

| Object | What it is | Default |
|--------|-----------|---------|
| `BG_Plane` | Background | light gray |
| `Sprite_center` | Center character sprite | green |
| `Sprite_left` | Left character sprite | green |
| `Sprite_right` | Right character sprite | green |
| `Dialogue_Box` | Dialogue background box | white 80% alpha |
| `choice_0` .. `choice_8` | Menu choice buttons | white 80% alpha |
| `Speaker_Text` | Speaker name text | character's color |
| `Dialogue_Text` | Dialogue body text | dark gray |

Character sprites inherit their color from the `Character(color=...)` definition
in your script. The dialogue box and choice buttons use the defaults from
`Object Color` unless overridden by a converted `gui.rpy`.

---

## Part 1 — Creating a New Game

### Using the Quick Wizard (recommended)

1. **Open UPBGE.** Launch `blender` from your UPBGE install.

2. **Open the UPVN panel.** In the 3D Viewport, press `N` to open the sidebar.
   Click the **UPVN** tab. You should see:
   ```
   ✓ Engine: OK (repo root)
   ```

3. **Use the Quick Wizard:**
   - Set a **Game Title** (e.g. "My First VN").
   - Pick a **Theme**: school, fantasy, scifi, or mystery.
   - Click **Quick VN Wizard**.

   This creates `game/script.rpy` with a complete branching story — characters,
   variables, menus, two endings, all working. You can play it immediately.

4. **Open the script.** Switch to Blender's **Text Editor**, open the dropdown,
   and select `script.rpy`. This is where you'll make all changes.

### Using Create Project (minimal starter)

Click **Create UPVN Project** for a bare-minimum starter with one character
and a single line of dialogue. Then build from there in the Text Editor.

### Running from the command line

You can also run any `.rpy` file headlessly (no UPBGE window needed):

```bash
python -m tools.run_headless game/script.rpy --mode full
```

---

## Part 2 — Writing Dialogue

Open `script.rpy` in the Text Editor and write dialogue directly.

### Narration (no speaker)

A line with just a string produces narration — no character name shown:

```renpy
label start:
    "The lecture hall was quiet."
    "I couldn't concentrate on the professor's words."
```

### Spoken dialogue

A character ID followed by a string shows the character's name and their line:

```renpy
label start:
    e "Hi! I'm Eileen."
    s "Nice to meet you!"
```

### Defining characters

Before using a character ID, define it at the top of the file:

```renpy
character e:
    name "Eileen"
    color "#c8ffc8"

character s:
    name "Sylvie"
    color "#c8c8ff"
```

The `color` sets the speaker name color in-game. Pick colors that contrast
with your dialogue box background — light colors on dark boxes, dark colors
on white boxes.

### Text formatting

| Tag | Effect | Example |
|-----|--------|---------|
| `{b}text{/b}` | **Bold** | `e "This is {b}important{/b}."` |
| `{i}text{/i}` | *Italic* | `e "A {i}whispered{/i} word."` |
| `[variable]` | Show variable value | `e "Affection is [affection]."` |

---

## Part 3 — Scenes and Sprites

### Changing the background

The `scene` statement replaces the entire screen with a background:

```renpy
label start:
    scene bg classroom with fade
    e "We're in the classroom now."
    scene bg library with dissolve
    e "Now we're in the library."
```

Known background names and their headless renderer appearance:

| Name | Description |
|------|------------|
| `bg classroom` | Warm room with windows and floor |
| `bg library` / `bg lecturehall` | Dark atmospheric hall with light rays |
| `bg meadow` | Green hills with clouds and flowers |
| `bg forest` | Dark forest with tree trunks and light shafts |
| `bg castle` | Stone walls with torchlight |
| `bg mountain` | Mountain peaks with snow and mist |
| `bg bridge` | Sci-fi bridge with holographic displays |
| `bg corridor` | Sci-fi corridor with perspective lines |
| `bg planet` | Space view with planet surface |
| `bg office` | Noir office with venetian blinds |
| `bg manor` | Dark wood paneling with chandelier |
| `bg garden` | Moonlit garden with hedges and mist |
| `black` | Dark background with subtle glow |

Without a matching image file, UPVN uses the headless renderer's procedural
backgrounds. To use your own images, place them in `assets/backgrounds/` and
declare them:

```renpy
image "bg classroom" = "backgrounds/bg_classroom.png"
```

### Showing character sprites

The `show` statement adds a character sprite:

```renpy
    scene bg classroom with fade
    show eileen at center with dissolve
    e "Hello!"
    show sylvie at right with move
    s "Hi there!"
    show eileen happy at center with dissolve
    e "I'm happy now!"
```

- The sprite **tag** (first word, e.g. `eileen`) determines which slot it
  occupies. Showing `eileen happy` replaces the previous `eileen` sprite.
- **Position**: `left`, `center`, `right`, `far_left`, `far_right`.
- **Transition**: `dissolve`, `move`, or omit for instant.

### Hiding sprites

```renpy
    hide sylvie with dissolve
```

Usually you don't need `hide` — `scene` clears everything, and `show` replaces
the same tag.

---

## Part 4 — Transitions

Transitions smooth scene changes. Add them with `with`:

```renpy
    scene bg classroom with fade
    # fade: fade to black, then fade in

    scene bg library with dissolve
    # dissolve: cross-fade between old and new

    show eileen at right with move
    # move: slide sprite from old position to new

    scene bg classroom
    # no transition: instant change
```

### Camera zoom (UPVN extension)

```renpy
    camera zoom 1.2 duration 0.8 with ease
```

This zooms the camera in smoothly. `duration` is in seconds. Easing options:
`linear`, `ease`, `easein`, `easeout`.

---

## Part 5 — Music and Sound Effects

```renpy
    play music "theme"
    # starts looping background music

    play music "new_song" fadein 1.0
    # cross-fade to new song over 1 second

    stop music
    # stops background music

    play sound "click.ogg"
    # plays a sound effect once
```

Place audio files in `assets/audio/` and declare them:

```renpy
audio theme = "audio/theme.ogg"
audio click = "audio/click.ogg"
```

---

## Part 6 — Choices and Variables

### Making choices

The `menu` statement presents choices to the player:

```renpy
    e "Do you want to help me?"
    menu:
        "What will you do?"
        choice "Yes, I'll help":
            jump help_eileen
        choice "No, sorry":
            jump refuse

label help_eileen:
    e "Thank you so much!"
    jump done

label refuse:
    e "I understand..."
    jump done

label done:
    e "Let's continue."
```

Each choice jumps to a label. The engine creates placeholder labels if they
don't exist, but you should define them with real content.

### State variables

Define variables in a `state:` block at the top of your script:

```renpy
state:
    affection: int = 0
    has_book: bool = False
    route: str = "none"
```

### Changing variables

Use `set` to modify variables (instead of Python's `$`):

```renpy
    set affection += 1
    set has_book = True
    set route = "help"
```

### Conditional branching

Use `if` / `elif` / `else` / `end` to branch on variables:

```renpy
    if affection >= 3:
        e "You've been so kind to me!"
        jump good_ending
    elif affection >= 1:
        e "We're friends, at least."
        jump neutral_ending
    else:
        e "I barely know you..."
        jump bad_ending
    end
```

Note: UPVN uses `end` to close `if` blocks (instead of Ren'Py's implicit
indentation-based blocks).

---

## Part 7 — Variable Interpolation

Show variable values in dialogue with `[variable]`:

```renpy
    e "Your affection is [affection]."
    e "Current route: [route]."
    e "Book status: [has_book]."
```

The engine replaces `[affection]` with the current value at runtime.

---

## Part 8 — Setting Up the Scene in UPBGE

When you're ready to play in UPBGE (not just headless), the engine needs
specific objects in the Blender scene — cameras, planes, text objects, logic
bricks. There are two ways to create them.

### Option A: Setup Scene button

Click **Setup Scene** in the UPVN panel. It creates everything automatically.
Then press **P** to play.

### Option B: Manual setup (by hand)

If Setup Scene doesn't work in your environment (e.g. you're running
headless/background mode where `bpy.ops` is unavailable), you can create
everything manually. This also helps you understand what the engine expects.

The engine looks for objects **by exact name**. If any are missing, the game
still runs but those elements won't appear. Here's the full list:

#### Step 1: Collections (scene organization)

Create 5 collections in the Outliner (right-click the scene collection →
New Collection):

| Collection | Purpose |
|------------|---------|
| `VN_Backgrounds` | Background planes |
| `VN_Characters` | Character sprite planes |
| `VN_UI` | Dialogue box, text, choice buttons |
| `VN_Effects` | Transition effects |
| `VN_3DStage` | 3D stage objects (optional) |

#### Step 2: Cameras

**Camera_UI** — orthographic camera for 2D UI (the main camera):
1. Add → Camera. Name it `Camera_UI`.
2. In Camera Properties: set Type to **Orthographic**, Orthographic Scale to **15**.
3. Location: `(0, -10, 0)`, Rotation: `(90°, 0, 0)` — looking down the +Y axis.
4. This camera should be the **active camera** (Scene Properties → Camera).

**Camera_3D** — perspective camera for 3D stages (optional):
1. Add → Camera. Name it `Camera_3D`.
2. Location: `(0, -6, 2.5)`, Rotation: `(66°, 0, 0)`.
3. Don't set as active — the engine switches to it when `load_stage` is used.

#### Step 3: Background plane

**BG_Plane** — large plane behind everything:
1. Add → Mesh → Plane. Name it `BG_Plane`.
2. Scale: `(9, 9, 1)` (18×18 world units).
3. Rotation: `(90°, 0, 0)` — standing upright in the XZ plane.
4. Location: `(0, 0, 0)`.
5. Add a material named `MABackground`. Set surface to **Emission**, strength 1.0.
6. In Object Properties → Viewport Display → Color, set `(0.95, 0.95, 0.95, 1)`.
7. Move to the `VN_Backgrounds` collection.

The engine swaps this object's `obj.color` at runtime when `scene` is called.

#### Step 4: Character sprite planes

Create 5 planes for character positions. Each needs a material named `MASprite`:

| Name | X location |
|------|-----------|
| `Sprite_far_left` | -5 |
| `Sprite_left` | -3 |
| `Sprite_center` | 0 |
| `Sprite_right` | 3 |
| `Sprite_far_right` | 5 |

For each:
1. Add → Mesh → Plane. Name it exactly (e.g. `Sprite_center`).
2. Scale: `(1.5, 2.4, 1)` — roughly portrait-sized.
3. Rotation: `(90°, 0, 0)` — standing upright.
4. Y location: `-0.15`, Z location: `0`.
5. Add material `MASprite`. Emission shader, strength 1.0.
6. Object Color: `(0.62, 0.78, 0.55, 1)` (default greenish).
7. Move to `VN_Characters` collection.

The engine swaps `obj.color` and optionally loads image textures at runtime.

#### Step 5: Dialogue box and text

**Dialogue_Box** — panel behind the dialogue text:
1. Add → Mesh → Plane. Name it `Dialogue_Box`.
2. Scale: `(4.0, 1.2, 1)`.
3. Rotation: `(90°, 0, 0)`.
4. Location: `(0, -0.4, -3.2)`.
5. Add material `MAUI`. Emission shader.
6. Object Color: `(1.0, 1.0, 1.0, 0.8)` (white, 80% alpha).
7. Move to `VN_UI` collection.

**Speaker_Text** — 3D text showing who's speaking:
1. Add → Text (Add → Curve → Text). Name it `Speaker_Text`.
2. In Font Properties, pick a font (DejaVu Sans works well).
3. Size: `0.30`.
4. Rotation: `(90°, 0, 0)`.
5. Location: `(-5.6, -0.55, -2.9)`.
6. Move to `VN_UI`.

**Dialogue_Text** — 3D text showing the dialogue:
1. Add → Text. Name it `Dialogue_Text`.
2. Size: `0.26`.
3. Rotation: `(90°, 0, 0)`.
4. Location: `(-5.4, -0.55, -3.3)`.
5. Move to `VN_UI`.

#### Step 6: Choice buttons

Create 9 pairs of objects for menu choices (`choice_0` through `choice_8`):

For each `choice_N` (N = 0..8):
1. Add → Mesh → Plane. Name it `choice_N`.
2. Scale: `(4.6, 0.36, 1)`.
3. Rotation: `(90°, 0, 0)`.
4. Z location: `1.05 - N * 0.66` (choice_0 at 1.05, choice_1 at 0.39, etc.).
5. Y location: `-0.5`.
6. Material `MAUI`. Object Color: `(1.0, 1.0, 1.0, 0.8)`.
7. Move to `VN_UI`.

For each `choice_N_text`:
1. Add → Text. Name it `choice_N_text`.
2. Size: `0.22`.
3. Rotation: `(90°, 0, 0)`.
4. Location: same Z as the plane, X offset to the left.
5. Move to `VN_UI`.

#### Step 7: History and rewind (optional)

**History_Box** — panel for the history overlay (H key):
1. Add → Mesh → Plane. Name it `History_Box`.
2. Scale: `(6.6, 3.0, 1)`.
3. Location: `(0, -0.45, 0.9)`.
4. Material `MAUI`. Object Color: `(0.02, 0.03, 0.08, 1)`.
5. Move to `VN_UI`.

**History_Text** and **Rewind_Text**: Text objects at appropriate locations.

#### Step 8: VNController and logic bricks

**VNController** — the engine's control object:
1. Add → Empty (Add → Empty → Plain Axes). Name it `VNController`.
2. In Custom Properties (Object Properties → add properties manually):
   - `script_path` (String): `//game/script.rpy`
   - `image_mode` (String): `color`
   - `parse_mode` (String): `safe`
   - `upvn_root` (String): `//` (or path to the engine root)

**Logic bricks** — the game tick:
1. Select `VNController`.
2. In the **Logic Editor** (or Game Logic layout):
   - Add **Always sensor** (pulse mode on, frequency 0).
   - Add **Python controller**, module mode: `upvn_launcher.main`.
   - Link sensor → controller.
3. In the **Text Editor**, create a text block named `upvn_launcher` with the
   path-bootstrap script (see `blend/upvn_editor_addon.py` →
   `_UPVN_LAUNCHER_TEXT` for the exact content, or copy from any working
   `.blend` template).

Alternatively, if you have the UPVN add-on installed: select `VNController`,
go to the Logic Editor, add an Always sensor + Python controller in **Script**
mode with text `upvn_launcher`. The add-on's **Setup Scene** button writes
this text block automatically.

#### Step 9: Check your work

After creating everything, run the wiring check:

1. In the UPVN panel, click **Check Scene Wiring**.
2. It compares your scene against the engine contract and lists any missing
   objects.

Or from the command line:
```bash
python -c "
from engine.render.contract import check_contract
# list your object names here
objs = {'BG_Plane', 'Dialogue_Box', 'Speaker_Text', 'Dialogue_Text', ...}
result = check_contract(objs)
for m in result['missing']:
    print(f'MISSING: {m[\"name\"]} — {m[\"purpose\"]}')
"
```

### After setup — Customize the layout

Once the scene is built (by either method), you can customize everything.

**Recolor elements:**
1. Select `Dialogue_Box` → Object Properties → Viewport Display → Color →
   set to your preferred dialogue box color.
2. Select `choice_0` through `choice_8` → same process.
3. Select `BG_Plane` → set to your preferred background tint.

The engine reads `obj.color` every frame, so changes take effect immediately.

**Lock individual objects for custom layout:**

By default, the engine repositions and rescales every UI object every frame.
To prevent this for a specific object — so you can use Blender drivers,
constraints, manual positioning, or your own Python logic:

1. Select the object (e.g. `Dialogue_Box`, `choice_0`, `Speaker_Text`).
2. In **Object Properties → Custom Properties**, add a new property:
   - Name: `upvn_layout_custom`
   - Type: Boolean
   - Value: `True`
3. Now the engine will **not** override this object's position, scale, or color.
   You're free to:
   - Move it manually
   - Add a **Copy Location** or **Copy Scale** constraint
   - Add a **Driver** (e.g. `var * aspect_ratio` to make it responsive)
   - Control it from a Python logic brick or node

The engine still updates the **text content** and **visibility** of the object
(e.g. it will still set what the dialogue text says, and show/hide it). Only
the layout (position, scale, color) is skipped.

**What still works on locked objects:**
- Text content is updated (dialogue, speaker name, choice text)
- Visibility is toggled (show/hide based on game state)
- Font color for text objects is still set by the engine

**What is skipped on locked objects:**
- Position (`worldPosition` / `location`)
- Scale (`worldScale` / `localScale`)
- Object color (`obj.color`)

**Example: responsive dialogue box using a driver**

To make the dialogue box scale with the viewport aspect ratio:

1. Select `Dialogue_Box`. Add `upvn_layout_custom = True`.
2. In the **Drivers** editor (or right-click Scale X → Add Driver):
   - Expression: `7.5 * (bge.render.getWindowWidth() / bge.render.getWindowHeight()) / (16/9)`
3. Now the box stretches to fill the screen regardless of window size.

**Example: choices following a custom layout using constraints**

1. Select `choice_0`. Add `upvn_layout_custom = True`.
2. Add a **Copy Location** constraint targeting an Empty you place wherever
   you want the first choice.
3. Add **Copy Location** with offset for `choice_1`, `choice_2`, etc.
4. Now you control the entire choice layout from the position of your Empty
   objects — the engine won't fight you.

**Example: all objects unlocked (full custom)**

To unlock every UI object at once, run this in Blender's Python console:

```python
import bpy
for ob in bpy.data.objects:
    if ob.name in ('Dialogue_Box', 'Speaker_Text', 'Dialogue_Text',
                   'choice_0', 'choice_1', 'choice_2', 'choice_3',
                   'choice_4', 'choice_5', 'choice_6', 'choice_7',
                   'choice_8', 'History_Box', 'History_Text', 'Rewind_Text',
                   'BG_Plane'):
        ob["upvn_layout_custom"] = True
```

Now the engine only updates text content and visibility — you have full
control over positioning, scaling, and coloring via Blender's tools.

---

## Part 9 — Playing and Testing

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

### Headless testing

```bash
# Run the full game headlessly
python -m tools.run_headless game/script.rpy --mode full

# Run with specific choices
python -m tools.run_headless game/script.rpy --mode full --choices 0 1

# JSON output for automation
python -m tools.run_headless game/script.rpy --mode full --json
```

### Running Ren'Py SDK projects directly

UPVN can run existing Ren'Py projects without copying or conversion:

```bash
# The Question (Ren'Py's example game)
python -m tools.run_headless ~/renpy-8.5.1-sdk/the_question/game/script.rpy \
    --mode full --choices 0 0

# The Ren'Py Tutorial (needs --compat for init python blocks)
python -m tools.run_headless ~/renpy-8.5.1-sdk/tutorial/game/script.rpy \
    --mode full --compat
```

The `--compat` flag is needed for projects that use Ren'Py-specific Python
modules (`ui`, `renpy.store`, etc.). Init python errors are collected rather
than fatal, so the story still plays.

---

## Quick Reference

| What you want | Script syntax |
|---------------|--------------|
| Background | `scene bg classroom with fade` |
| Show character | `show eileen at center with dissolve` |
| Hide character | `hide eileen with dissolve` |
| Narration | `"The sun was setting."` |
| Spoken line | `e "Hello, player!"` |
| Define character | `character e:` / `name "Eileen"` / `color "#c8ffc8"` |
| Define variable | `state:` / `affection: int = 0` |
| Change variable | `set affection += 1` |
| Choice menu | `menu:` / `choice "Option A":` / `jump label_a` |
| Conditional | `if affection >= 3:` / `else:` / `end` |
| Jump to label | `jump target_label` |
| Define label | `label new_scene:` |
| Pause | `pause 0.5` |
| Play music | `play music "theme"` |
| Camera zoom | `camera zoom 1.2 duration 1.0 with ease` |
| Show variable | `e "Value is [affection]."` |

---

## Full Example: "The Question" Recreation

Here's a complete script you can paste into `script.rpy` in the Text Editor.
It recreates the core of Ren'Py's "The Question" example:

```renpy
character me:
    name "Me"
    color "#ffffff"

character s:
    name "Sylvie"
    color "#c8c8ff"

state:
    affection: int = 0

label start:
    scene bg lecturehall with fade
    "It's only when I hear the sounds of shuffling feet that I realize
     the lecture is over."
    "Professor Eileen's lectures are usually interesting, but today
     I just couldn't concentrate."
    scene bg uni with fade
    "When we come out of the university, I spot her right away."
    show sylvie at center with dissolve
    "I've known Sylvie since we were kids."
    s "Hey... do you have a minute?"
    menu:
        "How do you respond?"
        choice "Sure, what's up?":
            jump sure
        choice "Sorry, I'm busy.":

label sure:
    set affection = 1
    s "I wanted to ask you something important."
    s "Will you marry me?"
    menu:
        choice "Of course!":
            jump marry
        choice "I need time...":
            jump later

label busy:
    set affection = 0
    s "Oh... okay. Maybe later then."
    "She looks disappointed as she walks away."
    jump end_scene

label marry:
    set affection += 2
    show sylvie happy at center with dissolve
    s "Really? You mean it?"
    me "Of course I will!"
    "We get married shortly after that."
    "{b}Good Ending{/b}."
    return

label later:
    s "I understand. Take your time."
    "You part ways, but the question lingers."
    "{b}Neutral Ending{/b}."
    return

label end_scene:
    "Sylvie walks away. You wonder what she wanted to ask."
    "{b}Alone Ending{/b}."
    return
```

### Play it

1. Save the script in Blender's Text Editor.
2. Click **Setup Scene** in the UPVN panel (first time only).
3. Recolor elements if desired (see Part 8).
4. Press **P** to play.
