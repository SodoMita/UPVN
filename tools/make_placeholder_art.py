"""Generate simple PNG sprites/backgrounds so UPBGE is not a flat colored plane."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _img(w, h, color):
    from PIL import Image
    return Image.new("RGBA", (w, h), color)


def _ellipse(draw, box, fill):
    draw.ellipse(box, fill=fill)


def _rect(draw, box, fill):
    draw.rectangle(box, fill=fill)


def character(path: Path, skin, hair, dress, accent):
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (512, 768), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # shadow
    _ellipse(d, (140, 700, 372, 748), (0, 0, 0, 50))
    # dress / body
    _rect(d, (170, 340, 342, 700), dress)
    d.polygon([(170, 340), (342, 340), (400, 700), (112, 700)], fill=dress)
    # torso
    _rect(d, (196, 280, 316, 420), accent)
    # arms
    _rect(d, (120, 300, 196, 520), dress)
    _rect(d, (316, 300, 392, 520), dress)
    # head
    _ellipse(d, (176, 110, 336, 290), skin)
    # hair
    _ellipse(d, (166, 80, 346, 200), hair)
    _rect(d, (166, 150, 196, 280), hair)
    _rect(d, (316, 150, 346, 280), hair)
    # eyes
    _ellipse(d, (210, 175, 238, 205), (30, 30, 40, 255))
    _ellipse(d, (274, 175, 302, 205), (30, 30, 40, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "PNG")


def background(path: Path, kind: str):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (1280, 720), (40, 44, 60))
    d = ImageDraw.Draw(im)
    if kind == "classroom":
        d.rectangle((0, 0, 1280, 720), fill=(210, 200, 175))
        d.rectangle((0, 0, 1280, 280), fill=(120, 160, 190))
        for x in (80, 360, 640, 920):
            d.rectangle((x, 40, x + 220, 240), fill=(180, 220, 235), outline=(90, 90, 80), width=6)
        d.rectangle((80, 320, 1200, 420), fill=(40, 80, 50))  # board
        d.rectangle((0, 560, 1280, 720), fill=(150, 120, 90))
    elif kind == "lecturehall":
        d.rectangle((0, 0, 1280, 720), fill=(50, 48, 70))
        d.rectangle((100, 40, 1180, 360), fill=(30, 30, 40))
        d.rectangle((140, 80, 1140, 320), fill=(80, 90, 70))
        for i, y in enumerate((420, 500, 580, 660)):
            d.rectangle((80 + i * 20, y, 1200 - i * 20, y + 50), fill=(70, 55, 80))
    elif kind == "meadow":
        d.rectangle((0, 0, 1280, 360), fill=(135, 190, 230))
        d.ellipse((900, 40, 1080, 220), fill=(255, 240, 160))
        d.rectangle((0, 360, 1280, 720), fill=(90, 160, 80))
        d.ellipse((200, 400, 480, 560), fill=(70, 140, 70))
        d.ellipse((700, 430, 1100, 620), fill=(80, 150, 75))
    else:  # uni
        d.rectangle((0, 0, 1280, 720), fill=(200, 205, 210))
        d.rectangle((0, 0, 1280, 280), fill=(140, 180, 210))
        d.rectangle((180, 120, 1100, 620), fill=(230, 225, 215), outline=(90, 80, 70), width=8)
        d.rectangle((560, 360, 720, 620), fill=(80, 60, 50))
        for x in (240, 400, 800, 960):
            d.rectangle((x, 180, x + 80, 300), fill=(160, 200, 220))
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, "PNG")


def main():
    dests = [
        ROOT / "examples" / "10_full_sample_game" / "assets",
        ROOT / "assets",
    ]
    chars = {
        "eileen.png": ((240, 190, 160, 255), (60, 120, 70, 255), (90, 160, 100, 255), (200, 230, 190, 255)),
        "eileen_happy.png": ((240, 190, 160, 255), (60, 120, 70, 255), (110, 180, 120, 255), (220, 245, 200, 255)),
        "sylvie.png": ((235, 200, 180, 255), (70, 70, 140, 255), (90, 90, 170, 255), (180, 180, 230, 255)),
    }
    bgs = {
        "bg classroom.png": "classroom",
        "bg_classroom.png": "classroom",
        "bg lecturehall.png": "lecturehall",
        "bg_lecturehall.png": "lecturehall",
        "bg meadow.png": "meadow",
        "bg_meadow.png": "meadow",
        "bg uni.png": "uni",
        "bg_uni.png": "uni",
    }
    for root in dests:
        for name, cols in chars.items():
            character(root / "sprites" / name, *cols)
        for name, kind in bgs.items():
            background(root / "backgrounds" / name, kind)
        # tag aliases
        character(root / "sprites" / "eileen happy.png", *chars["eileen_happy.png"])
    print("[placeholders] wrote sprites + backgrounds")


if __name__ == "__main__":
    main()
