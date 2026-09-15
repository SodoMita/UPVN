# Release Process — UPVN

This repo now has automated GitHub Actions for building and publishing.

## Workflows

### 1. CI — `.github/workflows/ci.yml`
Runs on every push to `main` / `feat/**` and PRs:
- `tests` — `pytest tests/ -q`
- `examples` — validates every example in its own tier + plays headless
- `renpy-corpus` — freeCodeCamp/LearnToCodeRPG sparse checkout
- `renpy-sdk` — Ren'Py SDK tutorial sparse checkout

### 2. Build Dist — `.github/workflows/build.yml`
Runs on push to `main`, PRs, and manual dispatch:
- Runs tests (quick gate)
- Builds `dist/upvn_editor_addon_vX.Y.Z.zip` via `tools/package_addon.py`
- Validates self-containment (engine/script/parser.py, bge_frontend/frontend.py, __init__.py inside)
- Uploads artifact `upvn-addon-dist` for download from Actions tab

### 3. Publish Release — `.github/workflows/publish.yml`
Runs on:
- **Tag push** `v*.*.*` or `v*.*` (e.g. `v0.7.1`)
- **Manual dispatch** with optional `version` input (e.g. `v0.7.1`)

Steps:
1. Tests gate (`pytest`)
2. Builds:
   - Add-on zip (`tools/package_addon.py dist`)
   - Sample game packages (`tools/package_game.py --project examples/10_full_sample_game --out dist` and `99_creator_demo`) — non-blocking
3. Extracts changelog section for the version from `CHANGELOG.md`
4. Uploads `dist/*.zip` as artifact `upvn-dist-<tag>`
5. If triggered by tag or manual version, creates GitHub Release via `softprops/action-gh-release@v2` with:
   - Tag, name `UPVN <tag>`, body from changelog + auto-generated notes
   - Files: `dist/*.zip`

## How to publish a new version

### Option A — Tag push (recommended)
```bash
# bump version in blend/upvn_editor_addon.py bl_info
# update CHANGELOG.md and STATUS.md
git add blend/upvn_editor_addon.py CHANGELOG.md STATUS.md docs/
git commit -m "v0.7.2: ..."
git tag v0.7.2
git push origin main --tags
# Action publish.yml will create Release v0.7.2 with zip
```

### Option B — Manual dispatch
1. Go to Actions → Publish Release → Run workflow
2. Enter version `v0.7.2`, choose prerelease if needed
3. Run — it builds and creates Release

### Local build (no GitHub)
```bash
python tools/package_addon.py dist
ls -lh dist/
# dist/upvn_editor_addon_v0.7.1.zip — 41 entries, 1007KB
```

## Self-containment check
The zip layout is single-folder (v0.6.11+):
```
upvn_editor_addon/
  __init__.py  <- add-on
  engine/...
  bge_frontend/...
  blend/UPVN_Template.blend
  blend/fonts/
  LICENSE
  README-INSTALL.txt
```
No `engine/` at zip root — avoids `bl_info` pollution when installed.

## Future ideas
- Itch.io publish via `itch.io` Butler (add secret `ITCH_API_KEY`)
- Pages docs deploy
- Auto-version bump via `bump2version`
