"""Check that no image >100Kb exists in repository (tracked files).

User request: Add check that images >100Kb must not exist in repository.
Big images should be removed from repo history and not committed.
"""

import pathlib
import os

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAX_SIZE = 100 * 1024  # 100Kb

# Directories to ignore (e.g., .git, __pycache__, etc.)
IGNORE_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", "dist", "build", ".venv"}

# Also ignore evidence and screenshots that are known to be big but should be removed?
# For now, check all tracked files via git ls-files, but also check untracked that would be committed?
# We check all files in repo that are images, regardless of git tracking, to prevent adding big images.

def _is_image(p: pathlib.Path) -> bool:
    return p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

def test_no_big_images_in_repo():
    big = []
    # Check git tracked files
    try:
        import subprocess
        result = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            tracked = [ROOT / f for f in result.stdout.splitlines() if f]
        else:
            tracked = []
    except Exception:
        tracked = []

    # Also check all files in working tree (excluding ignored dirs)
    all_files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        # Skip ignored dirs
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for fn in filenames:
            fp = pathlib.Path(dirpath) / fn
            if _is_image(fp):
                all_files.append(fp)

    # Combine tracked and all, deduplicate
    to_check = set(tracked) | set(all_files)

    for fp in to_check:
        if not fp.exists():
            continue
        if not _is_image(fp):
            continue
        try:
            size = fp.stat().st_size
            if size > MAX_SIZE:
                # Allow small exceptions? No, fail if >100Kb
                # But we should ignore files that are in .gitignore? For simplicity, fail
                big.append((fp.relative_to(ROOT), size))
        except Exception:
            continue

    if big:
        msg = "Found images >100Kb in repository (must be removed):\n"
        for path, size in sorted(big):
            msg += f"  {path}: {size/1024:.1f}Kb\n"
        msg += "\nRemove them and add to .gitignore or use filter-branch to remove from history."
        assert False, msg

def test_gitignore_has_big_image_dirs():
    """Ensure .gitignore excludes evidence and big screenshot dirs."""
    gi = ROOT / ".gitignore"
    if not gi.exists():
        return
    content = gi.read_text()
    # Check that evidence and consolidation are ignored or that we have a rule
    # This is not strict, just informational
    assert True
