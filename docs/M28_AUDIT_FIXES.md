# M28 Audit Fixes — Reliability Hardening (v0.7.1)

Date: 2026-09-15
Version: 0.7.1
Previous: M27 HQ No-Code Workflow v0.7.0

## Goal
Continue dev of https://github.com/SodoMita/UPVN with higher quality scene and less python coding while keeping reliability. M28 is a pure audit fix release — no new Ren'Py syntax (M25 freeze), only hardening against silent failures found in field reports and code review.

## Audit Checklist (from user request)
All items below were fixed and verified:

### vn_interpreter.py
- [x] _execute_node: loc-aware eval, interpolation warnings collected, pause dur safe_eval _loc with fallback, jump/call expr eval with _loc, assign safe_exec_assign _loc + div-zero guard, if cond failure logged as False, menu cond filtering + empty check raises ScriptRuntimeError, for iterable safe_eval + non-iterable handling, _bind_for_target tuple unpack validation, python block loc in message, screen errors propagated, camera_zoom/move easing, anim missing logged
- [x] run(): menu choice bounds check isinstance int + 0..len-1 before indexing (was only run_headless)
- [x] _eval_expr(_loc) label/index, _eval_screen_expr returns None with log, _render_screen returns errors with traceback, _run_init_python logs line number

### parser.py
- [x] bare except -> except ValueError at camera_zoom dur parsing
- [x] Character fallback "??" -> "Unnamed" + warnings.warn

### world_ui.py
- [x] wrap_text tag-aware using strip_tags for measuring, added wrap_text_stripped
- [x] set_font_text returns bool (None for None legacy) and logs failures
- [x] _set_visible/_set_pos/_set_scale return bool and log
- [x] build_world_ui handles typewriter revealed_text + interp_warnings + screen_errors + choice tag stripping + typewriter_done/progress
- [x] apply_world_ui returns status dict {applied,failed,errors}

### dialogue_box.py
- [x] typewriter fully wired: show() strips tags, update_typewriter(dt,cps), instant_reveal(), revealed_text() preserves tags via _tag_pat mapping, is_done(), get_warnings()

### bge_frontend/frontend.py
- [x] _sync_world_ui collects init_errors/python_errors as screen_errors, passes to build_world_ui, logs event errors, logs UI apply status once, stores _upvn_last_ui_status
- [x] heartbeat JSON includes init_errors[:5], python_errors[:5], payload_errors[:5], interp_warnings[:5], typewriter_done, ui_status

### blend/upvn_editor_addon.py
- [x] register() resets _engine_api=None, ENGINE_AVAILABLE=False to force rediscovery, reads prefs engine_path into _PREF_OVERRIDE, logs search details, version string includes M28 audit fixes
- [x] _rewrite_unlit logs every failure path instead of silent pass (was BUG M26b: black objects)

## Verification
- pytest: 363 passed / 30 skipped / 6 warnings (Pillow getdata + Unnamed char)
- Headless traces:
  - interpolation: Hello Alex with bold — interp_warnings None
  - menu filtering: if True / if False -> only "Go" visible
  - for non-iterable: treated as empty with log
  - typewriter: stripped count -> original with tags preserved via _tag_pat loop
  - screen errors: propagated to event.errors
  - init/python errors: visible in heartbeat
- Dist: upvn_editor_addon_v0.7.1.zip 1007KB 41 entries (single-folder layout)
- No new syntax: M25 freeze respected

## Files Changed
- engine/core/vn_interpreter.py — 1000+ lines hardened
- engine/script/parser.py — bare except + Unnamed fallback
- engine/ui/world_ui.py — tag-aware wrap, bool returns, status dict
- engine/ui/dialogue_box.py — full rewrite typewriter
- bge_frontend/frontend.py — compat errors + heartbeat
- blend/upvn_editor_addon.py — register reset + _rewrite_unlit logging + version bump
- docs/M28_AUDIT_FIXES.md — this file
- STATUS.md — M28 top
- CHANGELOG.md — 0.7.1 entry
- dist/upvn_editor_addon_v0.7.1.zip — rebuilt

## Next
- Publish GitHub release with dist/upvn_editor_addon_v0.7.1.zip
- Human-in-the-loop acceptance: open blend/UPVN_Template.blend in UPBGE → UPVN tab ✓ Engine → Create Project → Setup Scene HQ → P → click/Space advances, menu filtering, typewriter, interpolation warnings visible in heartbeat
- Third corpus regression, release notes
