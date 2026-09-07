# Blend template + Editor Add-on

Target file: `blend/UPVN_Template.blend`
Editor add-on: `blend/upvn_editor_addon.py` (minimal coding tools)

## Scene layout

```
Scene: VN_Main
  Camera_UI (Ortho, size 10)
  Camera_3D (Perspective)
  Empty: VNController  (logic: Always True pulse → Python: bge_frontend.frontend.main)
  Collection: VN_Backgrounds  (plane “BG_Plane” at z=0)
  Collection: VN_Characters   (planes “Sprite_left/center/right” at z=1)
  Collection: VN_UI           (plane “Dialogue_Box” + Text objects)
  Collection: VN_Effects      (for fade/dissolve shader planes)
  Collection: VN_3DStage      (empty markers: marker_eileen etc., 3D classroom mesh)
```

## Wiring

- `VNController` python component stores `script_path` property (`//game/script.rpy`).
- `frontend.main(cont)` loads via `VNController`, ticks each frame, handles click/space.
- `blf` overlay draws typewriter text; or `Text` objects (`Dialogue_Text`) — both supported.

## Editor add-on (minimal coding)

Install `blend/upvn_editor_addon.py` in Blender/UPBGE:
```
Edit → Preferences → Add-ons → Install → select blend/upvn_editor_addon.py → Enable
```
Then `View3D > Sidebar (N) > UPVN` and `Text Editor > Sidebar > UPVN` show panels:

- **Project**: `Create UPVN Project` → `//game/script.rpy` starter
- **Characters**: ID / Name / Color → `Add Character` → `define`
- **Scene & Sprites**: BG name → `Add Scene`; asset/position/with → `Add Show`
- **Dialogue**: speaker + text → `Add Dialogue` (supports `[var]` and `{b}/{color}`)
- **Menu**: caption + 2 choices/jumps → `Add Menu`
- **Tools**: `Validate` (parser line/col + hint), `Preview` (headless screenshot), `Save Demo (arbitrary slot)` → demos `SaveManager.save(999)` etc., saves are **arbitrary 1..∞** with pagination (6 per page, ←→)

Headless fallback: `tools/upvn_game_creator.py` uses same `UPVN_GameBuilder` API without `bpy`:
```bash
python tools/upvn_game_creator.py
# quick_game(project="my_game", characters=[("e","Eileen","#c8ffc8")], dialogues=[("e","Hi")])
```

## Generation (since we can't ship binary blend easily in this sandbox)

Run inside UPBGE/Blender:

```bash
upbge-0.50-linux-x64/blender --background --python tools/make_template.py
upbge-0.50-linux-x64/blender --background --python blend/upvn_editor_addon.py  # test register
```

That script uses `bpy` to create the collections, cameras, planes and save `blend/UPVN_Template.blend`. Stub file `tools/make_template.py` is provided; LLM can extend it to place UI in 3D (your request).

Until then, you can manually create the template: append planes, add Always sensor.

See also `engine/render/*` for how `scene`/`show` events map to plane textures (`bge.texture`). Arbitrary saves: `engine/save/save_manager.py` (`list_slot_ids`, `next_available_slot`, `slot_exists`) and `engine/ui/screen_manager.py` (pagination, any int slot).
