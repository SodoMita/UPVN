# M29 — HQ Scene, Packed Art, Zero-Setup Authoring (v0.7.2)

Same theme as M27/M28: **higher quality scene, less Python, reliability kept** — plus the
bug that made every 2D frame look broken and was misdiagnosed as a material problem.

---

## 1. Two rectangles that were not materials

Symptom, measured in the player on the headless sway/pixman desktop:

- a **brown band** across the character (`(74,64,56)` at rows ~292–365, x ≈ 376–912);
- a **grey square** with a darker lower half dead centre of the frame (`(93,96,102)` /
  `(13,17,26)`, 170 px wide).

Both looked like broken sprite materials, so hours went into the sprite shader graph
(`MIX_SHADER` vs `PRINCIPLED` vs `EMISSION`, `HASHED` vs `BLEND`, `use_transparent_shadow`).
The A/B/C variant scene was built to discriminate them — and then the *scene dump* answered
it in one shot: the running scene had exactly six visible contract objects
(`BG_Plane`, `Dialogue_Box`, `Sprite_center`, `VNController`, `Speaker_Text`,
`Dialogue_Text`) and **none of them could produce those rectangles**.

The rectangles were geometry:

1. **The factory `Cube`.** `tools/make_template.py` "emptied" the master collection with
   `scene.collection.objects.unlink(ob)` — which unlinks but never deletes. The default
   2×2×2 cube therefore shipped inside `blend/UPVN_Template.blend`. At ortho scale 15 over
   1280 px, 2 units = 171 px: exactly the grey square. It straddles `BG_Plane` (the cube
   spans y = −1…1, the background sits at y = 0), so half of it is *in front of* the art.
2. **The baked 3D classroom.** `VN_3DStage` (42 objects) exists so `show3d` /
   `load_stage` work with zero setup. For a 2D game it is not a feature: the desks are
   1.1 units deep and centred at y ≈ 0.2, so their front slice pokes through the background
   plane and drew the brown band across the character.

Both are fixed, and both are now impossible to reintroduce silently (see §3).

## 2. The rule: a stage the script has to ask for

`engine/render/stage_manager.py`

```python
STAGE_COLLECTION = "VN_3DStage"
STAGE_PROP       = "upvn_stage"
STAGE_EVENT_TYPES = ("load_stage", "show3d", "anim", "camera_preset")

script_uses_stage(script_dict)      # walks the parsed program, nested blocks included
StageManager.prepare(script_dict)   # hides the stage when it is not used
```

`VNController.load()` calls `prepare()`, so **both** the live player and the headless runner
go through one code path. No stage direction in the script → every object carrying
`upvn_stage` is switched off before the first frame; a script that uses the stage keeps it
untouched. The author does nothing.

Live verification, one build, two scripts:

| script | `stage_used` | stage objects visible | frame |
|---|---|---|---|
| `examples/20_smoke_game` | `false` | `0 / 43` | `art/qa/m29_09_clean.webp` |
| `examples/02_sprites_backgrounds` | `true` | `43 / 43` | `art/qa/m29_10_stage3d.webp` |

The debug log says which branch fired:

```
[StageManager] 2D script — hid 43 VN_3DStage objects (no load_stage/show3d/camera preset in script)
[StageManager] 2D script but no objects carry upvn_stage (scene built before M29? re-run Setup Scene)
```

### The flag, and the two ways it silently fails

The runtime finds the stage objects by a **game property**. Getting there was not obvious —
both alternatives look correct in `bpy` and are dead in the player:

| attempt | reads back as | why |
|---|---|---|
| `ob["upvn_stage"] = True` | ID property only | the player reads *game* properties, never ID properties |
| `game.properties.new(...)` | `AttributeError` | that collection has no `.new` in this build; use `bpy.ops.object.game_property_new()` under `temp_override` |
| BOOL game property | `False` after `value = True` | the value lives in a float slot the bool accessor does not read |
| INT game property | `1065353216` | float bits; another view of the same slot |
| **STRING game property** | `'1'` | what `_set_runtime_prop` already uses everywhere else |

So the stamp is `upvn_stage = "1"` (STRING), written by
`upvn_editor_addon._mark_stage_objects()` (called at the end of `build_vn_scene`, i.e. on
every **Setup Scene**) and by `tools/make_template.py`. Checked by `tools/check_template.py`.

## 3. Shipping gate: `tools/check_template.py`

The .blend is zstd-compressed, so no byte-level test can see a stray Cube or a missing flag;
and the engine's tests never open the file. Hence a real gate:

```
tools/check_template.py                    # finds UPBGE itself
blender -b --python tools/check_template.py -- --blend <file.blend>
```

1. **structure** — the master collection holds the VN contract and nothing else;
2. **stage flag** — every `VN_3DStage` object carries a truthy STRING `upvn_stage`;
3. **controller** — launcher properties (`script_path`, `image_mode`, `upvn_root`,
   `upvn_bricks`, …) are present, i.e. the file is playable.

Failure output is friendly and non-zero:

```
[check_template] FAIL: structure
    file: blend/UPVN_Template.blend
    Hint: 'Cube' sits in the master collection but is not part of the VN contract — a stray
          object there is drawn over the story planes (delete it, or move it into one of
          VN_Backgrounds, VN_Characters, VN_UI, VN_Effects, VN_3DStage)
```

`tools/package_game.py` runs it against the packaged blend (`Template gate: … ok`) and
`tests/test_m29_stage_visibility.py` runs it whenever a UPBGE/Blender binary is present
(skipped, not faked, when there is none).

## 4. HQ scene + packed art

- **WebP first** — `IMAGE_EXTENSIONS = (".webp", ".png", ".jpg", ".jpeg")`; art converted,
  15 space-named duplicate `.webp` files (2.7 MB) removed, packaging asserts that art
  survives rather than assuming PNG.
- **Palette readability** — `ensure_readable()` plus the showcase palette (navy panel, light
  text, green speaker tint) applies to config-driven projects; a project with its own GUI
  keeps its own colours.
- **Sprite fit** — `fit_sprite_plane_scale()` sizes each plane to the art's aspect ratio on
  texture swap and grounds it on one shared line (`SPRITE_HEIGHT = 3.2`,
  `SPRITE_FEET_Z = −2.75`); live-verified `512×768 → (2.133, 3.2, 1.0) at z = −1.15`.
- **Zero-setup launcher** — the `sys.path` bootstrap walks up to five parents, so a blend
  saved in a subfolder still finds `engine/` instead of dying with
  `ModuleNotFoundError: No module named 'bge_frontend'`.

### Why the shipped template points at an example script

`blend/UPVN_Template.blend` keeps `script_path = //../examples/20_smoke_game/script.rpy`
on purpose: it makes "open the template, press P" play the smoke demo, and it is the file
`tools/smoke_walkthrough.sh` drives (its BUG-009 check is precisely that the player must
*not* show the "game script not found" panel). Packaged builds bake `//game/script.rpy`
instead (M26f), so released games are unaffected — do not "fix" this default.

## 5. QA recipe used for this milestone

```bash
# 1. capture a frame on the headless sway/pixman desktop (WebP, pixel-gated)
UPVN_SCENE_DUMP=/tmp/dump.json bash tools/desktop_shot.sh art/qa/shot.webp 30

# 2. what is on screen / what the story is doing
python3 -c "import json;print(json.load(open('/tmp/dump.json'))['stage'])"
python3 -c "import json;d=json.load(open('/tmp/upvn_hb.json'));print(d['stage_used'], d['stage_visible'])"

# 3. is the shipped .blend still sane?
LIBGL_ALWAYS_SOFTWARE=1 /opt/upbge/upbge-0.50-linux-x64/blender --background \
    --python tools/check_template.py
```

`UPVN_SCENE_DUMP` writes `{"objects": [...], "stage": {"used", "total", "visible",
"visible_names"}}`; the heartbeat carries `stage_used` / `stage_visible`. Screenshots are for
humans, the dump/heartbeat numbers are what the tests assert.
