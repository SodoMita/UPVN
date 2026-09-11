# BUGS — M25 Usability Stabilization Freeze

Living inventory for the freeze. Rule: **no new features until install/setup/play
is boring and reliable.** Every entry records symptom, cause, fix, and how it is
kept fixed (test / walkthrough step). Severities: P0 = cannot start or cannot
play; P1 = play breaks silently; P2 = cosmetic / QA pain.

| ID | Sev | Title | Status |
|----|-----|-------|--------|
| BUG-001 | P0 | Shipped template blend stale vs addon contract | fixed (regen2) |
| BUG-002 | P1 | Silent `except: pass` hid every field failure | fixed (M24/M25 audits) |
| BUG-003 | P1 | Off-frame UI layout (ortho half-width used for vertical Z) | fixed |
| BUG-004 | P1 | `set_font_text` was a no-op (KX_FontObject has no runtime `.text`) | fixed |
| BUG-005 | P1 | Black choice plates (empty TexImage→Emission link) | fixed |
| BUG-006 | P0 | Player segfault at startup (audio device `'None'` userpref) | fixed |
| BUG-007 | P1 | Skip/auto silently auto-resolved menus; `None` choice killed generator | fixed |
| BUG-008 | P2 | Ctrl+S also toggled skip mode on the same tick | fixed |
| BUG-009 | P0 | Game properties written as ID custom props are invisible at runtime (UPBGE 0.50) | fixed |
| BUG-010 | P0 | Digit choice select compared ASCII ordinals against bge key codes | fixed |
| BUG-011 | P1 | Modal screens (save/load) invisible + blocking in player; Esc quits at engine level | fixed (direct quick-save/load) |
| BUG-012 | P0 | SENSOR physics invisible to KX_GameObject.rayCast (UPBGE 0.50) — mouse choices dead | fixed (STATIC+BOX) |
| BUG-013 | P1 | ortho getScreenRay always None; KX_Scene.rayCast missing; mouse y from top | fixed (manual frustum rayCast) |
| BUG-014 | P1 | _hide_idle_sprites hid the opening sprite right after load | fixed (keep sprite_mgr planes) |
| BUG-015 | P1 | Setup Scene clobbered configured script_path with panel default | fixed (adopt blend value) |
| BUG-016 | P0 | blenderplayer SIGSEGV at startup with factory PulseAudio userpref | fixed (audio_device='None' recipe) |
| BUG-017 | P0 | Setup Scene NameError 'TEX_NODE_NAME' — every tex_capable sprite material crashed in the GUI | fixed (M26g) |
| BUG-018 | P0 | UPVN_GameBuilder.write() regenerated from placeholder labels — one click emptied an existing script | fixed (M26g) |
| BUG-019 | P0 | Create Project overwrote an existing script at project_path (Setup Scene had just adopted it) | fixed (M26g: refuses) |
| BUG-020 | P1 | UPVN_Prefs (AddonPreferences) never registered — Preferences page (Locate Engine/engine_path) invisible | fixed (M26g) |
| BUG-021 | P2 | package_addon.py wrote the zip to a *file* named dist on a fresh clone | fixed (M26g) |
| BUG-022 | P2 | smoke_walkthrough.sh broke on a relative blend path arg (cd $UPBGE first) | fixed (M26g) |
| BUG-023 | P2 | 2 GB sandbox: player OOM-killed 5–15 s in, before the window mapped (black desktop, stale heartbeat) | fixed (M26g: swap guard) |
| BUG-024 | P2 | desktop_sway.sh sway config: `model` word rejected by some sway 1.10.1 builds → swaynag banner | fixed (M26g: runtime mode) |


## BUG-001 — stale template
The shipped `blend/UPVN_Template.blend` predated the addon's object contract
(missing choice plates / wrong props), so "press P" played a broken scene.
Fix: template regenerated from the addon (regen2), contract-checked
(29/29 objects, `script_path` game property, 0 bad texture links).
Kept fixed: `tests/test_m20_upbge_runtime.py` contract assertions.

## BUG-002 — silent excepts
Dozens of `except: pass` blocks turned every later bug into "black screen, no
clue". Replaced with loud-once prints / `_last_upvn_error` surfaced by the F1
diag. Kept fixed: code review + F1 diag shows `last error`.

## BUG-003 — off-frame layout
`layout_screen_ui` divided the ortho frustum's half-**width** by aspect for
vertical placement… incorrectly: dialogue/box Z used `half` instead of
`half/aspect`, pushing UI off-frame on non-4:3 windows.
Fix: `aspect_wh()` + `half_v` in `engine/ui/world_ui.py`.
Kept fixed: `tests/test_m25_stabilization.py` layout tests.

## BUG-004 — font no-op
`KX_FontObject` exposes no runtime `.text`; writes went nowhere.
Fix: `set_font_text` writes `obj.blenderObject.data.body`.
Kept fixed: unit tests with fake font objects.

## BUG-005 — black plates
Choice plates built an Image Texture node with no image and linked it into
Emission Color → black. Fix: solid emission color, texture link only when an
image exists. Kept fixed: addon unit tests + walkthrough shots 03/04.

## BUG-006 — startup segfault
Userpref `audio_device='None'` (string) made the audio layer segfault the
player before the first frame. Fix: sandbox prep sets the device to a valid
value/None-object + prefs autoexec; docs/SANDBOX_UPBGE.md records the recipe.
Kept fixed: `docs/SANDBOX_UPBGE.md` prep step; player log banner check.

## BUG-007 — skip/auto ate menus
Skip (S) and auto (A) advanced through `menu` events, silently picking choice
`None`, which then raised inside the story generator (ScriptRuntimeError) and
bricked the session. Fix: `menu` never auto-resolves; `_advance(None)` guard.
Kept fixed: `tests/test_m25_stabilization.py::test_skip_does_not_resolve_menu`.

## BUG-008 — Ctrl+S doubled as skip
The bare-S skip toggle fired on the same tick as Ctrl+S quick-save, enabling
skip mode during a save. Fix: skip requires `not active(LEFTCTRLKEY)`.
Kept fixed: unit test on the ctrl guard.

## BUG-009 — runtime-invisible game properties (UPBGE 0.50)
**Symptom:** player showed "UPVN: game script not found" although the blend
carried `script_path='//../examples/20_smoke_game/script.rpy'`; the frontend
silently fell back to the bundled sample game.
**Cause:** UPBGE 0.50's `KX_GameObject` only exposes entries of
`object.game.properties` ("Game Properties"). Plain ID custom properties
(`obj["script_path"]`, what the addon wrote) are invisible at runtime
(probed live: `'script_path' in owner == False`, `owner['script_path']`
KeyError, while `bpy` offline showed the custom prop).
**Fix:** addon `_set_runtime_prop()` writes BOTH representations
(custom prop for the editor UI, game property for the player); template
regenerated with real game properties. Old blends: re-run Setup Scene.
Kept fixed: walkthrough step 01 must show the smoke game's first line
("Eileen / Line one."), not the diag screen.

## BUG-010 — digit select compared ASCII to bge key codes
**Symptom:** pressing 1–9 at a menu did nothing in the player while headless
tests stayed green.
**Cause:** two-layer mismatch. UPBGE 0.50 key codes are evdev-like
(`ONEKEY==14`, `SPACE==8`), not ASCII. The M25 producer fix switched polling
to `bge.events.ONEKEY..NINEKEY`, but `_digit_choice_index` still compared
`states.get(ord("1")+i)` — ASCII 49.. never equals 14.., so selection stayed
dead (found via live Wayland walkthrough, screenshot evidence).
**Fix:** states are now a **digit-ordered sequence**; the helper rejects dicts
(fail closed) and never sees raw codes. Kept fixed:
`tests/test_m25_stabilization.py` BUG-010 tests + walkthrough step 04
("You chose left." after pressing 1).

## BUG-011 — modal screens are an invisible trap in the player
**Symptom:** Ctrl+S / Ctrl+L opened save/load modals that render nothing in
the standalone player (screens only implement `draw_headless`), blocked story
advance, and the historical dismiss key (Esc) **quits blenderplayer at engine
level** — modal or not (legacy BGE player behaviour; no Python hook).
**Cause:** screen system was built for headless traces; player wiring assumed
an interactive UI that does not exist yet.
**Fix (freeze-safe):** in BGE mode Ctrl+S/Ctrl+L now perform a **direct**
quick-save / quick-load (`VNController.quick_save/quick_load`, slot `quick`,
no modal); save format mapped onto a state snapshot for restore. Headless
screen APIs unchanged. Kept fixed:
`tests/test_m25_stabilization.py::test_quick_save_load_roundtrip_no_modal`,
walkthrough steps 06–09 (save file on disk + state returns to save point).
**Known limitation (post-freeze):** slot browsing UI in the player.

## Environment / QA notes (not engine bugs)
- **Synthetic input flake:** XTest → XWayland → client drops single keys and
  chords intermittently; chords with zero hold delay release Ctrl between
  50–75 ms logic ticks. Walkthrough uses `--delay 80` + retry-until-state
  (`press_until`) against the frontend heartbeat file (`UPVN_HEARTBEAT`).
- **Player stdout is block-buffered** and lost on `kill -9`; never assert on
  player logs — use the heartbeat file or screenshots (grim / import).
- **Xvfb instability** (zombie servers, black captures <16 s) motivated the
  headless-Wayland stack; see docs/SANDBOX_UPBGE.md.


## BUG-012 — SENSOR not ray-detectable (UPBGE 0.50)
**Symptom:** mouse clicks on choice plates never selected (digit keys worked);
debug showed `hover=None clicked=True`.
**Cause:** `_static_ghost` set `physics_type='SENSOR'`; in UPBGE 0.50
`KX_GameObject.rayCast` does not report SENSOR objects (probed live:
STATIC planes hit, SENSOR planes missed).
**Fix:** plates/planes use `STATIC` + BOX collision bounds; template
regenerated; `tools/update_template_materials.py` upgrades old blends.
Kept fixed: in-field walkthrough (click choice 0 → `left` label), probe
env `UPVN_POINTER_PROBE=1`.

## BUG-013 — ortho camera picking
**Symptom:** hover always None under Camera_UI.
**Cause:** `Camera.getScreenRay` returns None on ortho cameras in 0.50;
`KX_Scene.rayCast` does not exist; `bge.logic.mouse.position` y is measured
from the window TOP (verified: mouse at window top reports y≈0).
**Fix:** `_object_under_cursor` builds the frustum column manually
(ortho_scale × NDC, y flipped) and casts `cam.rayCast(top, bottom)`.
Kept fixed: same walkthrough as BUG-012.

## BUG-014 — opening sprite hidden after load
**Symptom:** palette stage appeared, `show eileen` logged `painted=True`,
nothing on screen, no error.
**Cause:** `frontend.main` called `_hide_idle_sprites()` right after
`ctrl.load()`; the load already applied opening events, so the just-shown
sprite was hidden again.
**Fix:** `_hide_idle_sprites(ctrl)` keeps planes referenced by
`ctrl.sprite_mgr.planes`.

## BUG-015 — Setup Scene clobbered script_path
**Symptom:** template carried `script_path=//../examples/20_smoke_game/...`;
after Setup Scene the player ran the fallback demo ("press P after Create
Project").
**Cause:** panel default `//game/script.rpy` overwrote the blend's game
property unconditionally.
**Fix:** operator + `build_vn_scene` adopt the existing value when the
caller passes the default; panel field synced.

## BUG-016 — startup segfault (audio userpref)
**Symptom:** `blenderplayer <any>.blend` → SIGSEGV before the first frame
(`AUD_Device_setSpeedOfSound` ← `LA_Launcher::InitEngine`, gdb backtrace);
`blender --background` worked.
**Cause:** factory userprefs request PulseAudio; the audio device object is
NULL without a sound server.
**Fix (sandbox recipe):** run once:
`blender --background --python-expr "import bpy;
bpy.context.preferences.system.audio_device='None';
bpy.context.preferences.filepaths.use_scripts_auto_execute=True;
bpy.ops.wm.save_userpref()"`
(Blender 5.0: audio prefs live in `preferences.system`, not
`preferences.audio`; autoexec flag is `use_scripts_auto_execute`.)
Kept fixed: docs/SANDBOX_UPBGE.md step 0; smoke walkthrough depends on it.

## BUG-017 — Setup Scene NameError in the GUI (M26g)
**Symptom:** first click of *Setup Scene* in the real UPBGE 0.50 GUI raised
`NameError: name 'TEX_NODE_NAME' is not defined` from `_rewrite_unlit`
(addon `__init__.py:932`) and the operator reported "Setup failed"; no scene
wiring happened. Headless tests stayed green because the helpers live under
`if HAS_BPY:` and pytest runs without bpy.
**Cause:** M26b added the texture-capable material graph referencing
`TEX_NODE_NAME` / `MIX_NODE_NAME` / `WHITE_IMAGE_NAME`, but those names were
imported (with fallbacks) as LOCALS inside `build_vn_scene` — while
`_rewrite_unlit()` and `_ensure_white_image()` are defined at the outer
`if HAS_BPY:` scope and can never see them. Every `tex_capable=True`
material (all sprite planes) hit the NameError. The standalone
`tools/update_template_materials.py` has its own copy of the logic, which is
why the shipped template looked fine.
**Fix:** the three contract names are bound once at module scope (engine
import when available, mirrored hardcoded fallback); `build_vn_scene` no
longer shadows them. Kept fixed:
`tests/test_m26g_gui_scope.py` (symtable: every free name used by the
material helpers must be a module global or builtin).

## BUG-018 — write() could destroy an existing script (M26g)
**Symptom (live-verified):** with the panel's Script Path pointing at
`examples/20_smoke_game/script.rpy` (which Setup Scene adopts from the
blend), running any add_* operator whose line already existed — or Create
Project — replaced EVERY label body with `"Empty label."` / lost 26 lines of
the M25 smoke game. Additions also landed after the label's `return`
(unreachable dead code).
**Cause:** `UPVN_GameBuilder.__init__` parses the existing file into
*placeholder* (empty) labels; `write()`'s merge path bailed when there was
nothing to insert and fell through to a full `build_rpy()` regeneration —
from those empty placeholders.
**Fix:** `write()` is strictly non-destructive: new defines after the last
define; additions inserted BEFORE the label's trailing `return`; brand-new
labels appended as blocks; **no-op leaves the file byte-identical**. Kept
fixed: `tests/test_m26g_builder_write.py` (7 tests incl. byte-identical
no-op and reachability).

## BUG-019 — Create Project overwrote existing scripts (M26g)
**Symptom:** "Create UPVN Project" regenerates a starter script at
project_path — after Setup Scene adopted the blend's script_path, that
meant one click wiped an existing game (see BUG-018 for the blast radius).
**Fix:** the operator refuses with a clear report when the target file
exists and has any non-whitespace content; fresh paths still generate the
starter. Verified live in the GUI (ERROR report, file untouched).

## BUG-020 — UPVN_Prefs never registered (M26g)
**Symptom:** the add-on's Preferences page was permanently empty below the
header — no engine status, no engine_path picker, no Locate/Check/Copy
buttons — and "Locate Engine" could not persist its choice (the addon
entry did not exist).
**Cause:** `UPVN_Prefs(bpy.types.AddonPreferences)` was defined but missing
from the `classes` registration tuple.
**Fix:** registered; AST regression test asserts every `bpy.types.*` class
defined in the add-on is in the tuple (and vice versa).

## BUG-021 — package_addon.py on a fresh clone (M26g)
A non-zip out path that did not exist yet (the default `dist/`) was used as
the zip FILE path, producing a file literally named `dist`. Non-zip
arguments are now always treated as a directory (created if missing).

## BUG-022 — smoke_walkthrough.sh relative blend path (M26g)
The script `cd`s into `$UPBGE` before launching the player, so a relative
blend argument resolved against the wrong directory and the player aborted
with "loading … failed". The argument is now `realpath`-ed up front.

## BUG-023 — sandbox OOM masquerading as a render bug (M26g)
`blenderplayer` needs ~0.9–1.2 GB RSS. On a ~2 GB sandbox that also runs
platform services, the OOM killer struck 5–15 s in — typically BEFORE the
window mapped: black desktop, a *stale* heartbeat JSON (written by the
already-dead process), and (before swap existed) an intermittent
`general protection fault` in libc. The fix is 3 GB of swap, now created by
`tools/desktop_sway.sh` when missing; docs/SANDBOX_UPBGE.md leads with it.
Lesson recorded: check `dmesg` for `Out of memory: Killed process …
blenderplayer` before debugging the render stack.

## BUG-024 — sway output-mode syntax differs across builds (M26g)
The M26e `model 1280x800` config word is rejected by other sway 1.10.1
builds ("Invalid output subcommand: model") — a bad line parks a swaynag
banner over the QA desktop or kills startup. `desktop_sway.sh` now keeps
the config file mode-free and sets the mode at runtime
(`mode --custom`, falling back to `model`), both non-fatal.
