# Ren'Py criticism inventory → UPVN design rules

Condensed from community pain points researched 2026-09-07.

1. **Screen language side-effects & restart_interaction footgun** — screens may run multiple times (prediction). → UPVN screens are pure functions of VNState, immediate-mode, reactive per frame.

2. **Stale .rpyc ghost scripts** — deleted .rpy still executes if .rpyc remains. → Never execute orphan cache. Use manifest + source hash, fail loudly. Cache is disposable JSON.

3. **Indentation fragility** — spaces matter, no formatter. → Parser gives precise `expected 4, got 2` + caret + Hint.

4. **Magic filenames + flat global namespace** — all .rpy combined. → Explicit manifest `project.upvn.toml`, real modules/imports later.

5. **Branching combinatorics have no tooling** — → Headless trace + `tools/run_headless.py --choices` + future flow visualizer.

6. **Save/rollback brittleness (pickle)** — script edit breaks saves. → JSON state only, stable IDs, versioned saves, migration tests.

7. **Memory manual tuning `config.image_cache_size`** — → Observable streaming, debug overlay.

8. **ATL orphaned animations** — → Transforms owned by display manager, lifecycle-bound.

9. **No visual tooling** — → Inherit Blender viewport: place sprite anchors/UI in 3D view, export positions.

10. **Arbitrary Python in script hurts analysis** — → Story `.rpy` is declarative; Python lives in `.py` plugins with `@upvn_command(mutates=…)` metadata.

See `COMMAND_SPEC.md` for how each rule is tested.
