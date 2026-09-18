# Ren'Py runner — what runs, what matters, how to run it on your PC

Everything here is measured on real UPBGE 0.53 player frames, not assumed.
Written 2026-09-18 for the person who wants to tune the look by hand.

---

## 1. The one command

```bash
UPBGE_DIR=/var/tmp/upbge/bin UPVN_OUT=/var/tmp/upvn_projects/the_question \
  bash tools/run_renpy_project.sh \
      /var/tmp/renpy/renpy-8.3.6-sdk/the_question 12 /tmp/x.png
```

It does four things, in order (all idempotent):

| # | Script | What it produces |
|---|--------|------------------|
| 1 | `tools/renpy_convert.py` (364 lines) | parses the `.rpy`, copies + slugs assets, writes the story script, `game/upvn_gui.json` (colours/sizes/fonts read from the project's own `gui.rpy`), and a copy of the template `.blend` |
| 2 | `tools/apply_gui_to_blend.py` (224) | **static parity pass** — bakes `upvn_gui.json` into that blend (textbox geometry, speaker/dialogue colours, font sizes) |
| 3 | `tools/desktop_sway.sh` / `tools/sway_up.sh` | headless sway + pixman desktop, only needed so *this sandbox* can screenshot |
| 4 | `blenderplayer` | runs the blend, waits for dialogue, screenshots |

**The image bank is created inside stage 1**: `renpy_convert.py` calls
`tools/wire_converted_blend.py` (208 lines), which makes one plane per image —

* `BGIMG_<stem>` — backdrops,
* `Sprite_img_<character>_<emotion>` — characters,

each with a baked material, sitting on `BACKGROUND_LAYER`.

Then at runtime:

| File | Role |
|------|------|
| `engine/render/scene_manager.py` (331) | `set_background()` picks the `BGIMG_*` plane, hides the rest, calls `_fit_bg_to_view()` |
| `engine/render/sprite_renderer.py` (539) | `show()/hide()`, `_renpy_place()` positions the plane on a `Pos_*` empty |
| `engine/ui/world_ui.py` (1104) | FONT objects (text curves) — `set_font_text()`, dialogue box, choices, history |
| `bge_frontend/frontend.py` (1511) | game loop, input, and the **heartbeat JSON** (`UPVN_HEARTBEAT=<path>`) |

> The converted project has its **own copy** of `engine/` + `bge_frontend/`.
> After editing either, `cp -rf engine/. $OUT/engine/ && cp -rf bge_frontend/. $OUT/bge_frontend/`
> and delete `__pycache__`, or you are testing stale code.

---

## 2. The knobs that actually decide how it looks

| Knob | Where | What we measured |
|------|-------|------------------|
| Sprite transparency | `tools/wire_converted_blend.py` → `_image_material(alpha=True)` | **CLIP** is the only mode the player renders correctly. OPAQUE draws an opaque quad around the character, BLEND washes the whole plane into whatever is behind it. Re-measure any time with `tools/make_alpha_probe.py` (3 planes, one screenshot). |
| Backdrop coverage | `engine/render/scene_manager.py` → `_fit_bg_to_view()` | It used to target `ortho` on width and `ortho*h/w` on height → a **15 × 8.44 backdrop inside the 26.7 × 15 frame** = the letterbox bars. Now it *covers*, keeping the image aspect. |
| Backdrop depth | `BACKGROUND_LAYER` (in **both** `scene_manager.py` and `wire_converted_blend.py`) | A plane at **Y=10 is not rendered at all** by the player; Y=0 and Y=6 are. Currently 0.0. To get the "more room in front of the backdrop" you want, move **Camera_UI back** (e.g. y=-10 → -20) and shift the UI layer with it, rather than pushing the backdrop to 10. |
| Text | `engine/ui/world_ui.py` → `set_font_text()` | Path order is load-bearing: `blenderObject.data.body → obj.text → obj.Text → obj.data.body → obj['Text']`, each write verified against the same target it wrote to. Reordering broke 4 tests. |
| Text look | font object materials in the blend | Still **dotted/sparse** — emission + sampling, not a text bug. |

---

## 3. Tone mapping — what I did *not* do

I never touched tone mapping. Measured in the converted blend:

```
view_transform = Standard   exposure = 0.0   gamma = 1.0   look = None
mist = off                  render engine = BLENDER_EEVEE
```

`Standard` means **no ACES/Filmic curve is baked into the file**, so if the picture
looks off, it is one of these — in the order I'd check them:

1. **The backdrop texture isn't being sampled in the player.** Symptom fits
   "flat dark blue": a Principled material whose image fails to display falls
   back to its base colour / object colour. Test: in the UPBGE editor pick the
   `BGIMG_bg_uni` plane, Material Properties → check the Image Texture node's
   image, and in the 3D view switch to *Material Preview* vs *Rendered*.
   Note the pure-Emission graph *does* go near-black in the player — Principled is
   the one that works.
2. **The player's own EEVEE-Next defaults** (render settings in the running
   game, not the .blend): Render Properties → Color Management, and whether the
   runtime applies exposure/bloom. Compare the same blend rendered by Blender
   (bright, mean 0.38) vs the player (dim, mean 0.13) — same geometry, so it is
   shading or colour management, not placement.
3. **The plane is behind / outside the ortho frustum.** Free proof: give the plane
   a screaming colour, run, screenshot, `magick identify -format "%[fx:mean]"`
   on it. Ignore `pointInsideFrustum` — it returns `False` even for objects you
   can plainly see.

---

## 4. Running it on your own machine

You need two downloads (both free):

* **UPBGE 0.53 alpha, weekly-build-100** — this sandbox pulls
  `https://github.com/UPBGE/upbge/releases/download/weekly-build-100/upbge-0.53-alpha-linux-x86_64-2026-09-13.tar.gz`;
  the release page has the Windows/macOS builds.
* **Ren'Py SDK 8.3.6** — `https://www.renpy.org/dl/8.3.6/renpy-8.3.6-sdk.zip`
  (`tools/fetch_renpy_sdk.sh` automates it).

Then:

```bash
git clone https://github.com/SodoMita/UPVN.git && cd UPVN
pip install -r requirements.txt          # just pytest; no Pillow in the engine

# convert (no screenshot needed on a real desktop)
UPBGE_DIR=/path/to/upbge-0.53 UPVN_OUT=~/upvn_projects/the_question \
  bash tools/run_renpy_project.sh /path/to/renpy-8.3.6-sdk/the_question 12
```

**On a PC you can drop the whole sway stage** — `blenderplayer -w 1280 720 0 0`
opens a real window on your GPU, no `LIBGL_ALWAYS_SOFTWARE=1`, no `grim`, no
`xdotool`. That is the loop you want for look work:

1. Convert **once**.
2. Open `$OUT/blend/UPVN_Template.blend` in UPBGE.
3. Edit materials / positions / camera in the editor, **Save**, press **P** to play.
4. When a setting is right, port it into `tools/wire_converted_blend.py`
   (bake-time: materials, plane placement) or `engine/render/scene_manager.py`
   (run-time: backdrop swap, fit), so the next conversion inherits it.

Ground truth for comparison, real Ren'Py at an exact script line:

```bash
bash tools/renpy_reference_shot.sh <project> <file.rpy> <line> <out.png>
```

---

## 5. Debug aids worth knowing

* **Heartbeat JSON** (`UPVN_HEARTBEAT=/tmp/hb.json`, dumped by
  `tools/upvn_shot.sh`): `dialogue`, `speaker`, `font_body`, `font_body_vis`,
  `font_body_dim`, `cam` (active camera, position, `ortho_scale`), and
  `stage[]` with `name/vis/pos/scale/color/frustum`.
* `UPVN_DEBUG_TEE=/tmp/dbg.log` captures every `[SceneManager]` /
  `[SpriteRenderer]` decision (which bank plane was chosen, bg-fit maths).
* `tools/upvn_shot.sh <blend> <out.png> "match text" [tries]` — advances with
  `xdotool key space` until the heartbeat matches, then screenshots.
* `tools/make_alpha_probe.py` — one blend, three planes (OPAQUE / BLEND / CLIP)
  on a bright background; one screenshot answers any material question.
* `magick identify -format "mean=%[fx:mean]\n" shot.png` — cheap brightness
  check on a **real** screenshot (measurement only, never as a renderer).

---

## 6. Open parity gaps and where they live

| Gap | Where to fix |
|-----|--------------|
| Backdrop renders flat dark blue (texture not showing / runtime shading) | `wire_converted_blend.py` materials + `scene_manager._swap_bge_texture()` |
| Dialogue text still dotted/sparse | font object materials in `blend/UPVN_Template.blend` |
| Dialogue box alpha `#000000cc` renders pitch black | material blend mode on `Dialogue_Box` in the template |
| Quick menu (History/Skip/Auto/Save/Q.Save/Load/Q.Load/Prefs) missing | does not exist in the template yet — must be authored and wired to the H/Q/S/A/Ctrl+S/Ctrl+L handlers in `engine/ui/screen_manager.py` |
