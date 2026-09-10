# 3D Characters with Animation — UPVN

UPVN is a **hybrid** engine: 2D VN planes (BG, sprites, dialogue) render on `Camera_UI` (ortho, looking +Y, XZ planes), while 3D content lives in `Camera_3D` (perspective) and in `VN_3DStage` collection. You can mix them: `scene`/`show` for 2D, `load_stage`/`show3d`/`anim`/`camera_preset` for 3D.

## Minimal setup (template is empty by default)

`blend/UPVN_Template.blend` ships **minimal**: only contract objects (BG_Plane, 5 Sprites, Dialogue, 9 choices, 2 cameras, VNController, 5 collections, one `marker_center` empty). No desks, no classroom, no random shapes — add what you need.

### 1. Create a 3D character blend

- Model/rig your character in Blender (armature + mesh, weight paint). Keep it in its own `stages/MyCharacter.blend` or `assets/characters/MyChar.blend`.
- Mark the **root object** (armature or empty) with name `MyCharacter` — that's the name `show3d` will look for.
- Animate actions in Dope Sheet → push to NLA or keep as Actions named `Idle`, `Walk`, `Talk`, etc. Use `anim` to play.

Example structure for `assets/characters/Eileen_3D.blend`:
```
Eileen_3D (Armature, with Action "Eileen_Idle", "Eileen_Talk")
  └ Eileen_Mesh (skinned)
```

### 2. Declare the stage in script.rpy

```rpy
# declare once at top level (optional, just for tooling)
stage classroom = "stages/classroom.blend"
image eileen happy = "characters/eileen/happy.png"  # 2D fallback

label start:
    scene bg classroom with fade
    # hybrid: 2D BG + 3D characters
    load_stage classroom          # LibLoad stages/classroom.blend
    show3d Eileen_3D at marker_center with fade
    show3d Sylvie_3D at marker_sylvie with move
    anim Eileen_3D "Eileen_Talk" loop
    camera preset_closeup_eileen with dissolve
    e "Hey — I'm a 3D mesh, not a sprite."

    # you can still use 2D sprites together:
    show eileen happy at left with dissolve
```

### 3. Markers & camera presets

Markers are empties in `VN_3DStage` that define spawn positions. Template has `marker_center` (0,0.5,0). Add your own:

- In Blender, `Add → Empty → Plain Axes`, name it `marker_eileen`, place where you want the character.
- It will be in `VN_3DStage` collection. `show3d MyChar at marker_eileen` lerps the character's `worldPosition` to that empty (via `SpriteRenderer`/`StageManager`).

Camera presets are empties with a rotation, e.g. `preset_closeup_eileen` at (-1.6,-1.5,1.4) looking at the character. `camera preset_closeup_eileen with dissolve` lerps `Camera_3D` there. You can create any `preset_*` empty and call it.

### 3D vs 2D: when to use which

| Use | Command | What happens |
|-----|---------|--------------|
| 2D sprite (classic VN) | `show eileen happy at center` | Swaps `Sprite_center` plane texture via `bge.texture` (PNG) or palette fallback; visible on ortho camera |
| 3D character | `show3d Eileen_3D at marker_center` | `LibLoad` + `addObject` of the armature, placed at marker; visible on perspective camera; `anim` plays Action |

You can mix: keep dialogue/choices on ortho, characters in 3D. `hide` / `hide3d` both exist.

### Animation

```
anim Eileen_3D "Eileen_Idle" loop      # loop an NLA action
anim Eileen_3D "Eileen_Talk"           # one-shot, then holds last frame
anim Eileen_3D stop
```

Actions must be on the armature's `animation_data`. The engine looks up `bpy.data.actions[action_name]` and plays via `KX_GameObject.playAction`.

### Why template is minimal now

Previously the template shipped a full classroom (9 desks, board, floor, 2 capsule characters, 3 presets) — useful as a demo but considered "random shapes" and hid the contract. Now it's empty; copy `examples/15_3d_stage` if you want a demo stage (that example still has the classroom, but it's opt-in).

See:
- `engine/render/stage_manager.py` — `load_stage`/`show3d`/`anim` implementation
- `engine/render/sprite_renderer.py` — 2D vs 3D coexistence
- `examples/15_3d_stage/script.rpy` — working hybrid example
- `tools/make_template.py` — template generation (minimal)

### Tip: 2D fallback for headless

If a 3D blend is missing, `show3d` is a no-op headlessly and the story continues. Keep a 2D `image` with the same base name (`eileen happy`) so `show eileen happy` works when 3D is not loaded.
