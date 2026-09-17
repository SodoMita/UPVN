# Current Status — 2026-09-15 (M28: Audit Fixes & Reliability Hardening, v0.7.1)

## Branch refactor/sprite-position-empties (2026-09-17, in progress)
- M29: visual-parity loop vs the Ren'Py tutorial on sway: static blend parity
  pass (tools/apply_gui_to_blend.py), parser char-name kwarg fix, bg fit via
  bpy scale; tutorial beat now matches tut_scene_renpy.png closely (full-bleed
  bg, centred sprite, dark textbox, sized name/dialogue). Known residual gaps:
  textbox is opaque (alpha blends render black on llvmpipe), name tint not
  applied to the shared MAUI text emission.
- Sprite stage layout moved from five per-position image planes (Sprite_<pos>)
  to Pos_<pos> empties + ONE Sprite_pool plane, duplicated per tag at runtime
  with single-user MASprite_<tag> material copies. Template blend migrated via
  tools/refactor_sprite_positions.py; addon Setup Scene, contract inventory,
  tests and tools/update_template_materials.py updated to match.
- Addon: STRING fallback where UPBGE 0.50 (Blender 5.0) removed the ENUM game
  property type (Setup Scene crashed in _set_runtime_prop before this).
- Currently failing: test_m27_gui_addon_operators.py::test_addon_all_operators_
  execute_and_build_valid_script — PRE-EXISTING gap: bpy.ops.upvn.preview_arbitrary
  / preview operators are not implemented anywhere in the addon (test only runs
  where UPBGE+Pillow exist; CI skips it).
- Env notes: UPBGE 0.50 at /opt/upbge, headless sway+pixman desktop via
  tools/desktop_sway.sh; Pillow installed into UPBGE's bundled python.

## Last completed
- **M28 Audit Fixes Phase 1+2 (2026-09-15, v0.7.1)**: full engine/UI/frontend/addon reliability hardening — no silent failures.
  - **vn_interpreter.py**: _execute_node loc-aware — say interpolate with _loc + interp_warnings collection, pause dur safe_eval _loc with logged fallback, jump/call expr eval with _loc, assign safe_exec_assign _loc + div-zero guard, if cond eval failure logged as False, menu cond safe_eval _loc filters false choices, raises ScriptRuntimeError if no choices after filtering, caption preserved, for loop safe_eval iterable _loc + non-iterable handled via list() try/except treating as empty with log, _bind_for_target validates tuple unpack with TypeError/length mismatch warning, python block errors include loc in compat message and _loc in strict, screen render errors propagated to event and logged, camera_zoom/move easing handled, anim target missing logged. run() menu choice validates isinstance int and bounds 0..len-1 before indexing (was only run_headless), raises ScriptRuntimeError on bad choice. _eval_expr signature (_loc) with label/index, _eval_screen_expr returns None in full tier with log instead of crash, _render_screen returns errors dict with traceback snippet and prints, _run_init_python logs line number i+1 in compat errors. strip_tags improved + parse_rich_tags preserved.
  - **parser.py**: bare except at camera_zoom dur parsing (lines 1549/1557) fixed to except ValueError (prevents swallowing KeyboardInterrupt/SystemExit), Character fallback "??" replaced with "Unnamed" + warnings.warn for visibility.
  - **world_ui.py**: wrap_text tag-aware using strip_tags for measuring (was counting tag chars causing premature wraps), added wrap_text_stripped for history, set_font_text returns None for None obj (legacy compat) else bool and logs all fallback failures, _set_visible/_set_pos/_set_scale return bool and log failures, build_world_ui new signature includes screen_errors, collects interp_warnings, payload errors, validates menu list, strips tags for choice display (FONT can't render inline tags), returns errors/interp_warnings/typewriter_done/progress, apply_world_ui returns status dict {applied,failed,errors} and logs payload errors, counts applied/failed, handles missing choice planes/text as errors.
  - **dialogue_box.py**: typewriter fully wired — show(event dict) strips tags via strip_tags, update_typewriter(dt,cps) advances float progress (40 cps default), instant_reveal(), revealed_text() maps stripped count to original preserving {tags} via _tag_pat search loop, revealed_stripped(), is_done(), get_warnings(), fully_revealed(). Previously stubbed pass — now wired to world_ui and VNController (VNController.update ticks typewriter, click instant reveals before advance).
  - **frontend.py**: _sync_world_ui collects interp.init_errors+python_errors as screen_errors, passes to build_world_ui, logs event errors with loc, logs UI apply status once via _upvn_ui_failed_logged, stores _upvn_last_ui_status, heartbeat JSON now includes init_errors[:5], python_errors[:5], payload_errors[:5], interp_warnings[:5], typewriter_done, ui_status for QA harness.
  - **addon.py**: register() now resets _engine_api=None, ENGINE_AVAILABLE=False to force rediscovery on every reload (fixes stale cache bug where second reload kept old engine path), reads prefs engine_path into _PREF_OVERRIDE and logs search details, version string includes M28 audit fixes. _rewrite_unlit now logs every failure path (use_nodes, nodes.clear, core nodes creation, tex mix link fallback, HQ fresnel, emission inputs, object color link, output link, blend_method/shadow_method/backface) instead of silent except: pass that produced black objects (BUG M26b). Version bumped to 0.7.1, dist zip 1007KB 41 entries.
  - **Reliability**: 363 passed / 30 skipped (6 warnings Pillow getdata + Unnamed char warn), no new syntax (M25 freeze intact), headless traces verified (interpolation, menu filtering, for non-iterable, typewriter tag-preserving), higher quality scene kept (M26 palette + M26i styled text baseline), less coding via Blender panels / UPVN_GameBuilder intact.
  - Docs: CHANGELOG 0.7.1

## M27 (previous)
- **M27 Creator Quality & No-Code (2026-09-15, v0.7.0)**: higher quality scene + less Python coding, reliability kept.
  - HQ Scene: emission 1.2 + Fresnel edge glow, dark gradient world, soft SUN_Soft, larger dialogue/choice, template classroom richer, headless HQ BGs, stage HQ, dialogue HQ, menu HQ.
  - No-Code: declarative builder (state_vars, images/audios/stages, set, choice, if/else/end, quick wizard one-click full game 2 endings), 13 new operators, boxed panels, asset browser copies, example 99_hq_wizard.
  - Reliability: 363 passed / 30 skipped, contract unchanged, dist v0.7.0 1002KB.

## M26i (main, v0.6.16)
- Real typeface DejaVu Book/Bold, extrude 0.16 + bevel 0.035, rewind italic shear 0.18, dark drop-shadow twins, Character(color) tint via obj.color. Live-verified green Eileen, 3D side faces, shadow rim. 375 passed / 16 skipped.

## Notes
- No new Ren'Py syntax until install/setup/play boring (M25 freeze rule) — M28 respected: only reliability fixes, no syntax.
- Higher quality default scene: M26 color palette + M26i styled text baseline kept (HQ materials, soft lighting, edge glow, DejaVu fonts, shadows).
- Less coding via Blender panels / UPVN_GameBuilder: declarative builder intact, quick wizard, asset browser.
- Keep pytest green + headless traces: 363 passed verified after M28 fixes.

## Recommended next task
- Publish GitHub release with dist/upvn_editor_addon_v0.7.1.zip
- Human-in-the-loop acceptance: open blend/UPVN_Template.blend in UPBGE → UPVN tab ✓ Engine → Create Project → Setup Scene HQ → P → click/Space advances, menu filtering, typewriter, interpolation warnings visible in heartbeat
- Third corpus regression breadth, GitHub release notes
