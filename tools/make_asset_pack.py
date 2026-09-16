#!/usr/bin/env python3
"""UPVN asset pack — turn raw art into game-ready assets with ONE command.

M29 motivation: UPVN's shipped sample art was flat placeholder blocks, so the
"higher quality scene" story ended at the palette. Real projects start from
raw art (photographs, AI generations, drawings) that is *almost* right:

  * backgrounds come at whatever aspect ratio the artist had — the game plane
    is 16:9 and a stretched background looks broken;
  * character art usually arrives on a flat backdrop (a chroma magenta / green
    screen) and needs a real alpha channel, or the sprite plane draws an
    opaque rectangle around the character;
  * sprites come in wildly different figure scales, so two characters on stage
    look like they live in different universes.

Output format: WebP, always (M29 rule). Backgrounds are lossy WebP
(`quality`, default 88); sprites are LOSSLESS WebP so the alpha the chroma key
produced survives bit-for-bit. No PNG, no JPG is written by this tool — WebP
is 30-70% smaller than both at equivalent quality, and UPBGE/Blender 5.0 loads
it natively.

This tool does those three jobs deterministically, from a small manifest, with
no Blender and no Python written by the creator:

    python tools/make_asset_pack.py assets/pack.json            # build the pack
    python tools/make_asset_pack.py assets/pack.json --check    # verify only
    python tools/make_asset_pack.py --init mygame               # write a starter pack.json

Manifest (JSON — asset_pack.json next to your art):

    {
      "canvas":   [1280, 720],           # background target size (16:9 default)
      "sprite":   {"width": 512, "height": 768, "margin": 18},
      "backgrounds": [
        {"src": "art/bg_classroom.png", "out": "assets/backgrounds/bg_classroom.webp",
         "fit": "cover", "quality": 88}
      ],
      "sprites": [
        {"src": "art/eileen_happy.png", "out": "assets/sprites/eileen_happy.webp",
         "key": "magenta", "trim": true}
      ],
      "copies": [ {"src": "art/eileen_neutral.png", "out": "assets/sprites/eileen.webp"} ]
    }

`fit`: "cover" (fill the canvas, crop the overflow — the default, no
distortion) or "contain" (letterbox onto a background color) or "stretch".
`key`: "magenta" | "green" | "auto" | null — colour key that becomes alpha.

Everything is Pillow + stdlib. Missing source files are reported and skipped,
never fatal: a half-finished art folder still produces a working game that
falls back to the UPVN palette for the missing pieces.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageChops, ImageFilter
except Exception:  # pragma: no cover - env problem, not author error
    print("Pillow is required: python -m pip install pillow", file=sys.stderr)
    raise SystemExit(2)

DEFAULT_CANVAS = (1280, 720)
DEFAULT_SPRITE = {"width": 512, "height": 768, "margin": 18}

# Chroma presets as (target RGB, hard radius, soft radius). Magenta is the
# usual AI-sprite backdrop; green is the classic film/video key. Radii are in
# 0..255 per-channel distance: <= hard is fully transparent, up to soft is a
# gradient, above soft is opaque. The soft band keeps antialiased outlines
# from turning into hard jaggies.
KEYS = {
    "magenta": ((255, 0, 255), 90.0, 150.0),
    "green": ((0, 255, 0), 90.0, 150.0),
}


def _dist(px, key):
    """Max per-channel distance — cheap and stable (no sqrt in hot loop)."""
    return max(abs(px[0] - key[0]), abs(px[1] - key[1]), abs(px[2] - key[2]))


def chroma_alpha(img: Image.Image, key_name: str) -> Image.Image:
    """Return an RGBA copy of `img` with the key colour knocked out.

    Straight-forward per-pixel distance keying with a soft ramp; the result is
    then despilled (the key colour bleeding into subject edges is pulled back
    toward neutral) so hair/outline pixels do not glow pink on stage.
    """
    kind = (key_name or "").lower()
    if kind not in KEYS:
        return img.convert("RGBA")
    key, hard, soft = KEYS[kind]
    rgb = img.convert("RGB")
    out = Image.new("RGBA", rgb.size)
    src = rgb.load()
    dst = out.load()
    w, h = rgb.size
    span = max(1.0, soft - hard)
    for y in range(h):
        for x in range(w):
            r, g, b = src[x, y]
            d = _dist((r, g, b), key)
            if d <= hard:
                a = 0
            elif d >= soft:
                a = 255
            else:
                a = int(255 * (d - hard) / span)
            if a < 255:
                # despill: only the channels that ARE the key colour get
                # pulled down toward the other channels' level
                if kind == "magenta":
                    cap = max(g, b)
                    r = min(r, cap)
                    b = min(b, cap)
                else:
                    cap = max(r, b)
                    g = min(g, cap)
                if a == 0:
                    r = g = b = 0
            dst[x, y] = (r, g, b, a)
    return out


def _content_bbox(img: Image.Image, alpha_threshold: int = 12):
    """Bounding box of everything not (nearly) transparent."""
    alpha = img.getchannel("A").point(lambda v: 255 if v >= alpha_threshold else 0)
    return alpha.getbbox()


def fit_sprite(img: Image.Image, width: int, height: int, margin: int,
               trim: bool = True, align: str = "feet") -> Image.Image:
    """Scale the figure to the canonical sprite canvas, feet on the baseline.

    Two characters authored at different zooms must still line up on stage, so
    every sprite in a pack comes out of here with the SAME canvas size and the
    same rule: figure height = canvas height - 2·margin, horizontally centred,
    bottom at canvas height - margin.
    """
    img = img.convert("RGBA")
    if trim:
        bbox = _content_bbox(img)
        if bbox:
            img = img.crop(bbox)
    target_h = max(1, height - 2 * margin)
    sw, sh = img.size
    if sh <= 0 or sw <= 0:
        return Image.new("RGBA", (width, height), (0, 0, 0, 0))
    scale = target_h / float(sh)
    new_w = max(1, int(round(sw * scale)))
    new_h = max(1, int(round(sh * scale)))
    # Never enlarge past the canvas width: very wide art gets width-bound.
    if new_w > width - 2 * margin:
        scale = (width - 2 * margin) / float(sw)
        new_w = max(1, int(round(sw * scale)))
        new_h = max(1, int(round(sh * scale)))
    resample = Image.LANCZOS
    fig = img.resize((new_w, new_h), resample)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    x = (width - new_w) // 2
    if align == "feet":
        y = height - margin - new_h
    elif align == "top":
        y = margin
    else:  # center
        y = (height - new_h) // 2
    canvas.alpha_composite(fig, (max(0, x), max(0, y)))
    return canvas


def fit_background(img: Image.Image, width: int, height: int, fit: str = "cover",
                   pad_color=(8, 10, 20)) -> Image.Image:
    """Aspect-correct the background: cover (crop), contain (letterbox) or stretch."""
    img = img.convert("RGB")
    sw, sh = img.size
    if sw <= 0 or sh <= 0:
        return Image.new("RGB", (width, height), pad_color)
    if fit == "stretch":
        return img.resize((width, height), Image.LANCZOS)
    img_ar = sw / float(sh)
    want_ar = width / float(height)
    if fit == "contain":
        scale = min(width / float(sw), height / float(sh))
        new = img.resize((max(1, int(sw * scale)), max(1, int(sh * scale))), Image.LANCZOS)
        canvas = Image.new("RGB", (width, height), pad_color)
        canvas.paste(new, ((width - new.width) // 2, (height - new.height) // 2))
        return canvas
    # cover: scale so BOTH dimensions are >= target, then centre-crop
    if img_ar > want_ar:
        new_h = height
        new_w = max(width, int(round(sw * height / float(sh))))
    else:
        new_w = width
        new_h = max(height, int(round(sh * width / float(sw))))
    new = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    return new.crop((left, top, left + width, top + height))


def _save(img: Image.Image, out: Path, quality: int = 88, lossless: bool = False) -> str:
    """Write WebP (the pack format) and return the real path written.

    A manifest asking for .png/.jpg is accepted but redirected to .webp, so an
    older manifest keeps working while the shipped tree stays WebP-only.
    `lossless=True` for anything with alpha (sprites): keying + resampling must
    not be re-compressed.
    """
    if out.suffix.lower() != ".webp":
        out = out.with_suffix(".webp")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "WEBP", quality=int(quality), lossless=bool(lossless),
             method=6)
    return out.name


def build_pack(manifest: dict, root: Path, check_only: bool = False) -> dict:
    """Process one manifest. Returns a report dict: built/skipped/failed.

    `root` is the manifest's own folder. Paths in the manifest resolve against
    the PROJECT root (the `root` key, relative to the manifest — e.g. "../.."
    for a manifest in tools/pack/); when a source is not found there, the
    manifest folder and up to 3 of its parents are searched too, so a pack
    definition works wherever the creator parked it.
    """
    report = {"built": [], "skipped": [], "failed": []}
    canvas = tuple(manifest.get("canvas") or DEFAULT_CANVAS)
    sprite_cfg = dict(DEFAULT_SPRITE)
    sprite_cfg.update(manifest.get("sprite") or {})
    proj_root = (root / manifest["root"]).resolve() if manifest.get("root") else root
    search = [proj_root, root] + list(root.parents[:3])
    seen = []
    for base in search:
        if base not in seen:
            seen.append(base)
    search = seen

    def prune(out_path: Path) -> list:
        """Delete stale .png/.jpg/.jpeg twins of a .webp output (M29 rule: the
        pack is WebP-only, so an old uncompressed file must not shadow or
        bloat it). Returns the removed names."""
        removed = []
        if out_path.suffix.lower() != ".webp":
            return removed
        for ext in (".png", ".jpg", ".jpeg", ".bmp"):
            twin = out_path.with_suffix(ext)
            if twin.is_file():
                try:
                    twin.unlink()
                    removed.append(twin.name)
                except Exception:
                    pass
        return removed

    def resolve(p, for_output: bool = False):
        q = Path(p)
        if q.is_absolute():
            return q
        if not for_output:
            for base in search:
                cand = base / q
                if cand.exists():
                    return cand
        return proj_root / q

    for entry in manifest.get("backgrounds", []):
        src = resolve(entry["src"])
        out = resolve(entry["out"], for_output=True)
        if not src.is_file():
            report["failed"].append(f"background source missing: {src}")
            continue
        if check_only:
            report["skipped"].append(f"(check) {out.relative_to(root) if out.is_relative_to(root) else out}")
            continue
        try:
            img = fit_background(Image.open(src), canvas[0], canvas[1],
                                 entry.get("fit", "cover"),
                                 tuple(entry.get("pad_color", (8, 10, 20))))
            name = _save(img, out, int(entry.get("quality", 88)), lossless=False)
            pruned = prune(out if out.suffix.lower() == ".webp" else out.with_suffix(".webp"))
            report["built"].append(
                f"{name} {img.size[0]}x{img.size[1]} webp/q{int(entry.get('quality', 88))}"
                + (f" (pruned {', '.join(pruned)})" if pruned else ""))
        except Exception as e:  # one bad file must not stop the pack
            report["failed"].append(f"{src}: {e}")

    for entry in manifest.get("sprites", []):
        src = resolve(entry["src"])
        out = resolve(entry["out"], for_output=True)
        if not src.is_file():
            report["failed"].append(f"sprite source missing: {src}")
            continue
        if check_only:
            report["skipped"].append(f"(check) {out.relative_to(root) if out.is_relative_to(root) else out}")
            continue
        try:
            img = Image.open(src)
            if entry.get("key"):
                img = chroma_alpha(img, entry["key"])
            img = fit_sprite(img, int(entry.get("width", sprite_cfg["width"])),
                             int(entry.get("height", sprite_cfg["height"])),
                             int(entry.get("margin", sprite_cfg["margin"])),
                             bool(entry.get("trim", True)),
                             entry.get("align", "feet"))
            # sprites are LOSSLESS: the keyed alpha and the resample must
            # survive byte-exact, a lossy pass would fringe the outlines
            name = _save(img, out, lossless=True)
            pruned = prune(out if out.suffix.lower() == ".webp" else out.with_suffix(".webp"))
            report["built"].append(
                f"{name} {img.size[0]}x{img.size[1]} RGBA webp/lossless"
                + (f" (pruned {', '.join(pruned)})" if pruned else ""))
        except Exception as e:
            report["failed"].append(f"{src}: {e}")

    for entry in manifest.get("copies", []):
        src = resolve(entry["src"])
        out = resolve(entry["out"], for_output=True)
        if not src.is_file():
            report["failed"].append(f"copy source missing: {src}")
            continue
        if check_only:
            continue
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(src.read_bytes())
            report["built"].append(f"{out.name} (copy)")
        except Exception as e:
            report["failed"].append(f"{src}: {e}")
    return report


STARTER = {
    "canvas": [1280, 720],
    "sprite": {"width": 512, "height": 768, "margin": 18},
    "backgrounds": [
        {"src": "art/bg_classroom.png", "out": "assets/backgrounds/bg_classroom.webp",
         "fit": "cover", "quality": 88},
    ],
    "sprites": [
        {"src": "art/eileen_happy.png", "out": "assets/sprites/eileen_happy.webp",
         "key": "magenta", "trim": True},
    ],
    "copies": [],
}

USAGE_HINTS = [
    "backgrounds: 16:9 cover-cropped lossy WebP (quality 88 by default)",
    "sprites: lossless WebP with alpha, fixed canvas, feet on the baseline",
    "keys: magenta / green / auto",
    "legacy .png/.jpg outputs are redirected to .webp — the pack is WebP-only",
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="UPVN asset pack builder")
    ap.add_argument("manifest", nargs="?", help="path to asset_pack.json")
    ap.add_argument("--init", metavar="DIR", help="write a starter asset_pack.json in DIR")
    ap.add_argument("--check", action="store_true", help="verify inputs exist, build nothing")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    args = ap.parse_args(argv)

    if args.init:
        d = Path(args.init)
        d.mkdir(parents=True, exist_ok=True)
        out = d / "asset_pack.json"
        if out.exists():
            print(f"refusing to overwrite existing {out}")
            return 1
        out.write_text(json.dumps(STARTER, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out}\nEdit the src/out pairs, then: "
              f"python tools/make_asset_pack.py {out}")
        return 0

    if not args.manifest:
        ap.print_help()
        return 2
    mp = Path(args.manifest).resolve()
    if not mp.is_file():
        print(f"no such manifest: {mp}", file=sys.stderr)
        return 2
    try:
        manifest = json.loads(mp.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"{mp}: not valid JSON — {e}", file=sys.stderr)
        return 2

    report = build_pack(manifest, mp.parent, check_only=args.check)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if not report["failed"] else 1
    print(f"UPVN asset pack — {mp}")
    for line in report["built"]:
        print(f"  built   {line}")
    for line in report["skipped"]:
        print(f"  check   {line}")
    for line in report["failed"]:
        print(f"  MISSING {line}")
    print(f"  → {len(report['built'])} built, {len(report['failed'])} unmet")
    for hint in USAGE_HINTS:
        print(f"  note: {hint}")
    return 0 if not report["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
