#!/usr/bin/env python3
"""
Generate VN screenshots via Pillow (headless, no GPU needed)
Simulates UPBGE planes + blf text rendering.
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from pathlib import Path
import textwrap

W, H = 1280, 720
OUT = Path("/home/user/upvn/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

# Try to find a decent font
import os
def find_font():
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/home/user/upbge-0.50-linux-x64/5.0/datafiles/fonts/Inter.woff2",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for p in candidates:
        if Path(p).exists():
            return p
    return None

FONT_PATH = find_font()
print(f"Using font: {FONT_PATH}")

def load_font(size):
    if FONT_PATH and FONT_PATH.endswith(".woff2"):
        # Pillow may not support woff2; fallback to DejaVu if not found
        try:
            return ImageFont.truetype(FONT_PATH, size)
        except:
            pass
    if FONT_PATH:
        try:
            return ImageFont.truetype(FONT_PATH, size)
        except:
            pass
    # fallback to DejaVuSans
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except:
        return ImageFont.load_default()

FONT_TITLE = load_font(28)
FONT_NAME = load_font(16)
FONT_TEXT = load_font(22)
FONT_SMALL = load_font(13)
FONT_MENU = load_font(20)

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2],16) for i in (0,2,4))

def draw_background(draw, img, scene):
    # Gradient backgrounds
    colors = {
        "bg classroom": ((18, 28, 70), (12, 18, 45)),
        "bg lecturehall": ((32, 38, 70), (15, 22, 45)),
        "bg meadow": ((28, 70, 45), (15, 45, 25)),
        "bg uni": ((35, 65, 80), (20, 35, 50)),
        "bg hallway": ((70, 50, 22), (45, 28, 12)),
        "black": ((5, 7, 12), (2, 3, 8)),
    }
    top, bot = colors.get(scene, ((14,20,35),(8,12,28)))
    for y in range(H):
        t = y / H
        r = int(top[0]*(1-t) + bot[0]*t)
        g = int(top[1]*(1-t) + bot[1]*t)
        b = int(top[2]*(1-t) + bot[2]*t)
        draw.line([(0,y),(W,y)], fill=(r,g,b))
    # Add subtle vignette / light
    # Light rectangle for classroom windows
    if "classroom" in scene:
        draw.rectangle([80, 80, 520, 340], fill=(55, 75, 120, 40), outline=None)

def draw_sprite(img, draw, tag, expr, pos, color="#c8ffc8"):
    # positions: left, center, right
    x_map = {"left": 260, "center": 640, "right": 1020, "far_left": 150, "far_right": 1130}
    x = x_map.get(pos, 640)
    y_bottom = 560
    w, h = 220, 340
    x0 = x - w//2
    y0 = y_bottom - h
    x1 = x0 + w
    y1 = y_bottom
    # Shadow
    draw.ellipse([x0-10, y1-20, x1+10, y1+10], fill=(0,0,0,80))
    # Body gradient rectangle
    col = hex_to_rgb(color) if color.startswith("#") else (180,200,160)
    # Create sprite image with rounded corners
    sprite = Image.new("RGBA", (w, h), (0,0,0,0))
    sdraw = ImageDraw.Draw(sprite)
    # Gradient fill
    for i in range(h):
        t = i / h
        r = int(col[0]*(0.7 + 0.3*(1-t)) + 30*t)
        g = int(col[1]*(0.7 + 0.3*(1-t)) + 30*t)
        b = int(col[2]*(0.7 + 0.3*(1-t)) + 30*t)
        sdraw.line([(0,i),(w,i)], fill=(r,g,b,255))
    # Face placeholder
    # head
    sdraw.ellipse([w//2-45, 55, w//2+45, 145], fill=(255, 228, 196, 255), outline=(0,0,0,30), width=2)
    # eyes
    sdraw.ellipse([w//2-28, 95, w//2-12, 112], fill=(30,30,30))
    sdraw.ellipse([w//2+12, 95, w//2+28, 112], fill=(30,30,30))
    # mouth based on expr
    if "happy" in expr or "smile" in expr or "giggle" in expr:
        sdraw.arc([w//2-18, 118, w//2+18, 130], 20, 160, fill=(180,50,50), width=3)
    elif "surprised" in expr:
        sdraw.ellipse([w//2-10, 118, w//2+10, 132], fill=(120,30,30))
    else:
        sdraw.line([w//2-14, 124, w//2+14, 124], fill=(80,30,30), width=2)
    # hair top
    sdraw.rectangle([w//2-55, 35, w//2+55, 75], fill=(col[0]//2, col[1]//2, col[2]//2, 255))
    # Label at bottom of sprite
    sdraw.rounded_rectangle([10, h-36, w-10, h-10], radius=8, fill=(0,0,0,90))
    # Paste onto main
    img.alpha_composite(sprite, (x0, y0))
    # Tag text
    txt = f"{tag} · {expr}"
    tw = draw.textlength(txt, font=FONT_SMALL)
    draw.rounded_rectangle([x - tw//2 -10, y1+6, x + tw//2 +10, y1+26], radius=10, fill=(10,12,22,200), outline=(0,184,195,80))
    draw.text((x - tw//2, y1+9), txt, fill=(180,220,230), font=FONT_SMALL)

def draw_dialogue(img, draw, speaker, speaker_color, text):
    # Dialogue box at bottom
    box_y0 = 540
    box = Image.new("RGBA", (W, H-box_y0), (0,0,0,0))
    bdraw = ImageDraw.Draw(box, "RGBA")
    # Box bg with blur
    bdraw.rounded_rectangle([40, 20, W-40, H-box_y0-20], radius=16, fill=(8,12,22,230), outline=(30,45,75,255), width=1)
    # Inner highlight
    bdraw.line([(60, 26),(W-60,26)], fill=(0,184,195,50), width=1)
    img.alpha_composite(box, (0, box_y0))
    # Speaker name tag
    if speaker:
        txt = speaker
        tw = draw.textlength(txt, font=FONT_NAME)
        nx = 70
        ny = box_y0 + 8
        draw.rounded_rectangle([nx, ny, nx+tw+24, ny+24], radius=12, fill=(15,38,44,255), outline=(0,184,195,100))
        draw.text((nx+12, ny+4), txt, fill=hex_to_rgb(speaker_color or "#7eeaff"), font=FONT_NAME)
    # Dialogue text wrapped
    if text:
        # Strip tags like {b}
        import re
        clean = re.sub(r"\{[^}]+\}", "", text)
        # Interpolate already done, but handle [var] we keep
        max_w = W - 120
        # Wrap
        lines = textwrap.wrap(clean, width=68)
        # Use manual wrapping with textlength for accuracy
        wrapped = []
        for para in clean.split("\n"):
            cur = ""
            for word in para.split():
                test = cur + " " + word if cur else word
                if draw.textlength(test, font=FONT_TEXT) > max_w:
                    wrapped.append(cur)
                    cur = word
                else:
                    cur = test
            if cur:
                wrapped.append(cur)
        wrapped = wrapped[:3]
        y = box_y0 + 42 if speaker else box_y0 + 32
        for line in wrapped:
            draw.text((70, y), line, fill=(232,238,247), font=FONT_TEXT)
            y += 30
    # Click hint
    draw.text((W-180, H-28), "click / space to advance", fill=(120,130,150), font=FONT_SMALL)
    # Progress indicator
    draw.ellipse([W//2-3, H-14, W//2+3, H-8], fill=(0,184,195,180))

def draw_menu(img, draw, caption, choices):
    # Darken
    overlay = Image.new("RGBA", (W,H), (2,5,12,160))
    img.alpha_composite(overlay, (0,0))
    # Caption on top if any
    y_start = 220
    if caption:
        tw = draw.textlength(caption, font=FONT_TEXT)
        draw.rounded_rectangle([W//2 - tw//2 -20, y_start-20, W//2 + tw//2 +20, y_start+30], radius=12, fill=(12,18,35,220), outline=(0,184,195,80))
        draw.text((W//2 - tw//2, y_start-8), caption, fill=(180,220,230), font=FONT_TEXT)
        y_start += 60
    # Choices
    for i, ch in enumerate(choices):
        bw = 420
        bh = 54
        x0 = W//2 - bw//2
        y0 = y_start + i* (bh+14)
        x1 = x0 + bw
        y1 = y0 + bh
        # Button bg
        draw.rounded_rectangle([x0, y0, x1, y1], radius=12, fill=(15,27,48,250), outline=(45,70,120,255), width=1)
        # Hover accent left
        draw.rounded_rectangle([x0, y0, x0+6, y1], radius=6, fill=(0,184,195,255))
        # Text
        tw = draw.textlength(ch, font=FONT_MENU)
        draw.text((W//2 - tw//2, y0+16), ch, fill=(220,235,255), font=FONT_MENU)
        # Number
        draw.text((x0+18, y0+18), str(i+1), fill=(0,184,195), font=FONT_SMALL)

def render_one(filename, scene, sprites, dialogue, speaker=None, speaker_color=None, menu=None):
    img = Image.new("RGBA", (W,H), (10,14,28,255))
    draw = ImageDraw.Draw(img, "RGBA")
    draw_background(draw, img, scene)
    # Sprites (list of dict)
    for s in sprites:
        draw_sprite(img, draw, s["tag"], s["expr"], s["pos"], s.get("color","#c8ffc8"))
    if menu:
        draw_menu(img, draw, menu.get("caption"), menu["choices"])
    else:
        draw_dialogue(img, draw, speaker, speaker_color, dialogue)
    # Top bar with scene label
    draw.rounded_rectangle([18,18, 280, 44], radius=8, fill=(0,0,0,100))
    draw.text((28,24), f"SCENE: {scene}", fill=(160,170,190), font=FONT_SMALL)
    # UPVN badge
    draw.rounded_rectangle([W-140,16, W-18,36], radius=8, fill=(0,25,30,180), outline=(0,184,195,80))
    draw.text((W-132,20), "UPVN · UPBGE 0.50", fill=(0,216,255), font=FONT_SMALL)
    img = img.convert("RGB")
    img.save(OUT / filename, "PNG", quality=95)
    print(f"Saved {OUT/filename}  {img.size}")

# Generate series
if __name__ == "__main__":
    # 00 minimal dialogue - narration
    render_one("00_narration.png", "bg classroom", [], "This is narration. The engine is running inside UPBGE (or headless).", None, None)
    render_one("00_dialogue.png", "bg classroom", [{"tag":"eileen","expr":"neutral","pos":"center","color":"#c8ffc8"}], "This is dialogue. Hello from UPVN! The engine can advance one line at a time.", "Eileen", "#c8ffc8")
    
    # 01 branching - menu
    render_one("01_menu.png", "bg lecturehall", [{"tag":"eileen","expr":"neutral","pos":"center","color":"#c8ffc8"}], None, None, menu={"caption":None, "choices":["Library","Rooftop"]})
    render_one("01_library.png", "bg hallway", [{"tag":"eileen","expr":"happy","pos":"center","color":"#c8ffc8"}], "Quiet. Good choice. The library smells like old paper.", "Eileen", "#c8ffc8")
    render_one("01_rooftop.png", "bg hallway", [{"tag":"eileen","expr":"happy","pos":"right","color":"#c8ffc8"}], "Windy up here. But the view is worth it.", "Eileen", "#c8ffc8")
    
    # 02 sprites - show/hide, transitions
    render_one("02_sprites.png", "bg classroom", [
        {"tag":"eileen","expr":"neutral","pos":"center","color":"#aaffaa"},
    ], "Now we have a background and a character.", "Eileen", "#aaffaa")
    render_one("02_expression.png", "bg classroom", [
        {"tag":"eileen","expr":"happy","pos":"center","color":"#aaffaa"},
    ], "Expressions work too — same tag replaces texture.", "Eileen", "#aaffaa")
    render_one("02_hide.png", "bg hallway", [], "She leaves. The background changed.", None, None)
    # 3D hybrid
    render_one("02_hybrid.png", "black", [
        {"tag":"eileen","expr":"idle","pos":"center","color":"#8ab4ff"},
    ], "3D classroom loaded behind planes · camera preset medium_shot", "Eileen", "#8ab4ff")

    # 03 variables
    render_one("03_ask.png", "bg meadow", [{"tag":"eileen","expr":"neutral","pos":"center","color":"#c8ffc8"}], "Can you help me carry these books?", "Eileen", "#c8ffc8")
    render_one("03_menu.png", "bg meadow", [{"tag":"eileen","expr":"neutral","pos":"center","color":"#c8ffc8"}], None, None, menu={"caption":None, "choices":["Help her","Say you're busy"]})
    render_one("03_good.png", "bg meadow", [{"tag":"eileen","expr":"happy","pos":"center","color":"#c8ffc8"}], "Thanks! You're really kind. You chose route good and affection is 1.", "Eileen", "#c8ffc8")
    render_one("03_neutral.png", "bg meadow", [{"tag":"eileen","expr":"neutral","pos":"center","color":"#c8ffc8"}], "Oh. Okay. I understand. Maybe next time.", "Eileen", "#c8ffc8")

    # The Question - Sylvie
    render_one("q_start.png", "bg lecturehall", [], "It's only when I hear the sounds of shuffling feet and supplies being put away that I realize that the lecture's over.", None, None)
    render_one("q_sylvie.png", "bg uni", [{"tag":"sylvie","expr":"green smile","pos":"center","color":"#c8ffc8"}], "Hi there! How was class?", "Sylvie", "#c8ffc8")
    render_one("q_menu1.png", "bg uni", [{"tag":"sylvie","expr":"green smile","pos":"center","color":"#c8ffc8"}], None, None, menu={"caption":"As soon as she catches my eye, I decide…", "choices":["To ask her right away.","To ask her later."]})
    render_one("q_menu2.png", "bg meadow", [{"tag":"sylvie","expr":"green smile","pos":"center","color":"#c8ffc8"}], None, None, menu={"caption":None, "choices":["It's a videogame.","It's an interactive book."]})
    render_one("q_good_ending.png", "black", [{"tag":"sylvie","expr":"blue giggle","pos":"center","color":"#8ab4ff"}], "{b}Good Ending{/b} — We get married shortly after that.", "Sylvie", "#c8ffc8")

    # Template overview
    render_one("template_overview.png", "bg classroom", [
        {"tag":"eileen","expr":"neutral","pos":"left","color":"#c8ffc8"},
        {"tag":"sylvie","expr":"happy","pos":"right","color":"#c8ffc8"},
    ], "UPVN template: Layer 0 BG plane · Layer 1 sprites · Layer 2 UI · 3D stage behind", "System", "#7eeaff")

    print(f"Done — {len(list(OUT.glob('*.png')))} screenshots in {OUT}")
