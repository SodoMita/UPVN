#!/usr/bin/env python3
"""
Polished VN screenshots — simulate UPBGE planes + blf
Headless, Pillow only, no GPU needed
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import textwrap, re

W, H = 1280, 720
OUT = Path("/home/user/upvn/screenshots")
OUT.mkdir(parents=True, exist_ok=True)

def load_font(size, bold=False):
    # Try common fonts
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]:
        try:
            if Path(p).exists():
                return ImageFont.truetype(p, size)
        except: pass
    return ImageFont.load_default()

F_Title = load_font(22, bold=True)
F_Name = load_font(14, bold=True)
F_Text = load_font(20)
F_TextSmall = load_font(18)
F_Small = load_font(12)
F_Menu = load_font(19)
F_Caption = load_font(16)

def hex_rgb(h):
    h=h.lstrip("#")
    return tuple(int(h[i:i+2],16) for i in (0,2,4))

def draw_bg(img, draw, scene):
    # vibrant, Ren'Py-like backgrounds
    if scene == "bg classroom":
        # warm classroom: beige + windows
        for y in range(H):
            t=y/H
            r=int(235 - 15*t)
            g=int(225 - 20*t)
            b=int(195 - 30*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # windows
        for wx in [70, 460, 850]:
            draw.rounded_rectangle([wx, 60, wx+320, 320], radius=6, fill=(135, 175, 215), outline=(90,110,140), width=3)
            draw.line([(wx+160,60),(wx+160,320)], fill=(90,110,140), width=3)
            draw.line([(wx,190),(wx+320,190)], fill=(90,110,140), width=3)
            # light
            draw.rounded_rectangle([wx+8, 68, wx+312, 182], radius=4, fill=(200,225,255,90))
        # floor line
        draw.rectangle([0, 520, W, 524], fill=(120, 100, 80))
        # vignette
        overlay = Image.new("RGBA", (W,H), (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        for i in range(120):
            a = int(35 * (1 - i/120))
            od.rectangle([i,i,W-i-1,H-i-1], outline=(0,0,0,a))
        img.alpha_composite(overlay, (0,0))
    elif scene == "bg lecturehall":
        for y in range(H):
            t=y/H
            r=int(42 - 12*t)
            g=int(52 - 10*t)
            b=int(84 - 14*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # subtle vertical light gradients (soft, not circles)
        for x in [220, 640, 1060]:
            # vertical beam
            for i in range(140):
                a = int(18 * (1 - i/140))
                draw.line([(x-i//2, 0),(x+i//2, 0)], fill=(255,240,180,a))  # top glow line
                # instead draw thin rectangles for beam
                draw.rectangle([x-2, 0, x+2, 360], fill=(255,240,180,10))
        # podium
        draw.rectangle([0, 480, W, 540], fill=(28,32,48))
        draw.rectangle([W//2-140, 450, W//2+140, 480], fill=(42,48,70), outline=(65,72,95), width=1)
        draw.ellipse([W//2-180, 520, W//2+180, 560], fill=(0,0,0,35))
    elif scene == "bg meadow":
        # sky to green
        for y in range(H):
            t=y/H
            if t < 0.52:
                # sky
                tt = t/0.52
                r=int(135 + 60*tt)
                g=int(185 + 40*tt)
                b=int(235 - 20*tt)
            else:
                tt = (t-0.52)/0.48
                r=int(195 - 60*tt)
                g=int(225 - 30*tt)
                b=int(215 - 110*tt)
                # green meadow
                r=int(75 - 20*tt)
                g=int(135 - 15*tt)
                b=int(75 - 10*tt)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # hills
        draw.ellipse([-300, 380, 800, 620], fill=(85,145,85))
        draw.ellipse([500, 400, 1450, 650], fill=(70,125,70))
        # clouds
        for cx, cy in [(260,110),(620,90),(980,120)]:
            draw.ellipse([cx-90, cy-30, cx+90, cy+30], fill=(255,255,255,95))
            draw.ellipse([cx-60, cy-45, cx+60, cy+10], fill=(255,255,255,85))
    elif scene == "bg uni":
        for y in range(H):
            t=y/H
            r=int(60 + 30*t)
            g=int(95 + 35*t)
            b=int(145 + 20*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # university buildings silhouette
        draw.rectangle([0, 360, W, 560], fill=(35,45,65))
        for x in range(60, W, 170):
            draw.rectangle([x, 300, x+110, 360], fill=(50,60,80), outline=(70,80,100), width=2)
            for wy in [315, 335]:
                draw.rectangle([x+12, wy, x+98, wy+14], fill=(255,235,160))
        # trees
        for x in [120, 340, 760, 1020]:
            draw.ellipse([x-35, 340, x+35, 385], fill=(45,90,45))
            draw.rectangle([x-6, 385, x+6, 410], fill=(70,50,30))
    elif scene == "bg hallway":
        for y in range(H):
            t=y/H
            r=int(115 - 35*t)
            g=int(95 - 25*t)
            b=int(65 - 15*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # perspective walls
        draw.polygon([(0,0),(340,0),(260,H),(0,H)], fill=(125,105,75))
        draw.polygon([(W,0),(W-340,0),(W-260,H),(W,H)], fill=(115,95,68))
        # floor tiles
        for y in range(380, H, 70):
            w = int((y-380)*0.9 + 90)
            draw.polygon([(W//2-w//2, y),(W//2+w//2, y),(W//2+w//2+40, y+70),(W//2-w//2-40, y+70)], outline=(90,75,55), width=1, fill=(135,115,85) if (y//70)%2==0 else (125,105,78))
        # lockers
        for x in [30, 170, 1010, 1150]:
            draw.rectangle([x, 120, x+100, 380], fill=(60,85,105), outline=(40,60,80), width=2)
            draw.ellipse([x+70, 240, x+78, 248], fill=(200,200,180))
    elif scene == "black":
        for y in range(H):
            draw.line([(0,y),(W,y)], fill=(6,8,14))
        # subtle radial
        overlay = Image.new("RGBA", (W,H), (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        # center glow
        od.ellipse([W//2-400, H//2-300, W//2+400, H//2+300], fill=(20,30,55,45))
        img.alpha_composite(overlay, (0,0))
    else:
        for y in range(H):
            t=y/H
            r=int(18 + 10*t)
            g=int(22 + 12*t)
            b=int(38 + 15*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))

def draw_sprite(img, draw, tag, expr, pos, color):
    # pos - raise up to avoid dialogue box overlap
    x_map = {"left": 300, "center": 640, "right": 980, "far_left": 180, "far_right": 1100}
    x = x_map.get(pos, 640)
    y_bottom = 515  # was 545, now higher to clear dialogue (538)
    w, h = 240, 360
    x0 = x - w//2
    y0 = y_bottom - h
    # shadow on floor (slightly above)
    sh = Image.new("RGBA", (W,H), (0,0,0,0))
    sd = ImageDraw.Draw(sh)
    sd.ellipse([x-90, y_bottom-4, x+90, y_bottom+10], fill=(0,0,0,45))
    img.alpha_composite(sh, (0,0))
    # character card
    col = hex_rgb(color)
    # body gradient
    sprite = Image.new("RGBA", (w, h), (0,0,0,0))
    sd2 = ImageDraw.Draw(sprite)
    # rounded top
    sd2.rounded_rectangle([0,0,w-1,h-1], radius=18, fill=(0,0,0,30))
    # main fill with subtle gradient
    for i in range(h):
        t=i/h
        r = int(col[0]* (0.85 - 0.25*t) + 255*0.15*t + 18)
        g = int(col[1]* (0.85 - 0.25*t) + 255*0.15*t + 18)
        b = int(col[2]* (0.85 - 0.25*t) + 255*0.15*t + 18)
        # clamp
        r=max(0,min(255,r)); g=max(0,min(255,g)); b=max(0,min(255,b))
        sd2.line([(6,i),(w-7,i)], fill=(r,g,b,255))
    # uniform / outfit: bottom half darker
    sd2.rectangle([6, 220, w-7, h-7], fill=(col[0]//2+18, col[1]//2+18, col[2]//2+18, 255))
    # collar
    sd2.polygon([(w//2-34, 150),(w//2, 182),(w//2+34,150),(w//2+26, 162),(w//2, 190),(w//2-26,162)], fill=(245,245,240))
    # head
    # neck
    sd2.rectangle([w//2-18, 148, w//2+18, 170], fill=(255,222,185))
    sd2.ellipse([w//2-52, 58, w//2+52, 162], fill=(255, 225, 190), outline=(0,0,0,28), width=2)
    # hair - top bangs
    hair_col = (col[0]//3+15, col[1]//3+15, col[2]//3+15)
    sd2.rounded_rectangle([w//2-62, 32, w//2+62, 78], radius=10, fill=hair_col)
    # side hair
    sd2.rectangle([w//2-62, 70, w//2-44, 138], fill=hair_col)
    sd2.rectangle([w//2+44, 70, w//2+62, 138], fill=hair_col)
    # eyes
    # blush
    sd2.ellipse([w//2-44, 118, w//2-24, 128], fill=(255,160,150,70))
    sd2.ellipse([w//2+24, 118, w//2+44, 128], fill=(255,160,150,70))
    if "happy" in expr or "smile" in expr or "giggle" in expr:
        # closed happy eyes (curved)
        sd2.arc([w//2-38, 98, w//2-12, 116], 200, 340, fill=(30,30,30), width=3)
        sd2.arc([w//2+12, 98, w//2+38, 116], 200, 340, fill=(30,30,30), width=3)
        # smile
        sd2.arc([w//2-20, 122, w//2+20, 138], 25, 155, fill=(160,40,40), width=3)
        # teeth hint
        sd2.rectangle([w//2-8, 129, w//2+8, 133], fill=(255,255,255,180))
    elif "surprised" in expr:
        sd2.ellipse([w//2-32, 96, w//2-10, 118], fill=(255,255,255), outline=(30,30,30), width=2)
        sd2.ellipse([w//2+10, 96, w//2+32, 118], fill=(255,255,255), outline=(30,30,30), width=2)
        sd2.ellipse([w//2-24, 101, w//2-16, 113], fill=(30,30,30))
        sd2.ellipse([w//2+16, 101, w//2+24, 113], fill=(30,30,30))
        sd2.ellipse([w//2-12, 124, w//2+12, 140], fill=(90,20,20), outline=(60,10,10), width=1)
        sd2.ellipse([w//2-7, 132, w//2+7, 138], fill=(255,120,120,160))
    elif expr.strip() == "idle":
        sd2.ellipse([w//2-28, 97, w//2-12, 114], fill=(30,30,30))
        sd2.ellipse([w//2+12, 97, w//2+28, 114], fill=(30,30,30))
        sd2.ellipse([w//2-22, 102, w//2-18, 108], fill=(255,255,255,200))
        sd2.ellipse([w//2+18, 102, w//2+22, 108], fill=(255,255,255,200))
        sd2.line([w//2-12, 128, w//2+12, 128], fill=(90,40,30), width=2)
    else: # neutral
        sd2.ellipse([w//2-28, 96, w//2-11, 115], fill=(255,255,255), outline=(30,30,30), width=1)
        sd2.ellipse([w//2+11, 96, w//2+28, 115], fill=(255,255,255), outline=(30,30,30), width=1)
        sd2.ellipse([w//2-22, 102, w//2-15, 111], fill=(30,30,30))
        sd2.ellipse([w//2+15, 102, w//2+22, 111], fill=(30,30,30))
        sd2.ellipse([w//2-20, 104, w//2-17, 108], fill=(255,255,255,210))
        sd2.ellipse([w//2+17, 104, w//2+20, 108], fill=(255,255,255,210))
        sd2.line([w//2-14, 128, w//2+14, 128], fill=(90,30,30), width=2)

    # border
    sd2.rounded_rectangle([0,0,w-1,h-1], radius=18, outline=(0,0,0,55), width=1)
    # inner highlight
    sd2.rounded_rectangle([1,1,w-2, h-2], radius=17, outline=(255,255,255,28), width=1)

    # no inner label bar — clean

    img.alpha_composite(sprite, (x0, y0))
    # tag text badge under sprite (outside, not overlapping)
    txt = f"{tag}  •  {expr}"
    tw = draw.textlength(txt, font=F_Small)
    bx0 = x - tw//2 -14
    by0 = y_bottom + 12
    # ensure not overlapping dialogue (dialogue at 538, sprite bottom 515, badge at 527, so +12 = 527, dialogue 538 -> gap 11px OK)
    draw.rounded_rectangle([bx0, by0, bx0+tw+28, by0+22], radius=11, fill=(12,16,28,215), outline=(0,184,195,65), width=1)
    draw.ellipse([bx0+8, by0+6, bx0+18, by0+16], fill=(0,184,195))
    draw.text((bx0+24, by0+4), txt, fill=(190,220,230), font=F_Small)

def draw_dialogue(img, draw, speaker, speaker_color, text):
    box_y0 = 538
    box_h = H - box_y0
    # box bg
    box = Image.new("RGBA", (W, box_h), (0,0,0,0))
    bd = ImageDraw.Draw(box, "RGBA")
    bd.rounded_rectangle([22, 14, W-22, box_h-14], radius=16, fill=(10,14,28,235), outline=(38,55,95,255), width=1)
    # top inner line
    bd.line([(34, 20),(W-34,20)], fill=(0,184,195,55), width=1)
    # bottom line
    bd.line([(34, box_h-18),(W-34, box_h-18)], fill=(255,255,255,10), width=1)
    img.alpha_composite(box, (0, box_y0))
    # speaker
    if speaker:
        txt = speaker
        tw = draw.textlength(txt, font=F_Name)
        nx = 58
        ny = box_y0 + 4
        # tag
        draw.rounded_rectangle([nx, ny, nx+tw+28, ny+26], radius=13, fill=(18,42,48,255), outline=(0,184,195,110), width=1)
        # dot
        draw.ellipse([nx+10, ny+8, nx+20, ny+18], fill=hex_rgb(speaker_color or "#7eeaff"))
        draw.text((nx+28, ny+5), txt, fill=(230,245,255), font=F_Name)
        text_y = box_y0 + 44
    else:
        text_y = box_y0 + 30
    if text:
        clean = re.sub(r"\{[^}]+\}", "", text)
        # handle [var] keep but ensure spacing
        max_w = W - 150
        # wrap
        wrapped=[]
        for para in clean.split("\n"):
            cur=""
            for w in para.split():
                test = cur+" "+w if cur else w
                if draw.textlength(test, font=F_Text) > max_w:
                    wrapped.append(cur)
                    cur=w
                else:
                    cur=test
            if cur:
                wrapped.append(cur)
        wrapped=wrapped[:3]
        for line in wrapped:
            draw.text((74, text_y), line, fill=(232,238,247), font=F_Text)
            text_y+=30
        # continuation indicator
        draw.polygon([(W-70, H-30),(W-58, H-22),(W-46, H-30)], fill=(0,184,195))
        draw.ellipse([W//2-4, H-10, W//2+4, H-6], fill=(0,184,195,180))
    # hint
    draw.text((W-188, H-20), "click / space →", fill=(110,125,155), font=F_Small)

def draw_menu(img, draw, caption, choices):
    # overlay darken + blur
    ov = Image.new("RGBA", (W,H), (6,10,22,150))
    img.alpha_composite(ov, (0,0))
    # vignette darkening edges
    vig = Image.new("RGBA", (W,H), (0,0,0,0))
    vd = ImageDraw.Draw(vig)
    for i in range(90):
        a = int(18*(1-i/90))
        vd.rounded_rectangle([i,i,W-i-1,H-i-1], radius=18, outline=(0,0,0,a))
    img.alpha_composite(vig, (0,0))
    y_start = 230
    if caption:
        tw = draw.textlength(caption, font=F_Text)
        bw = tw + 48
        x0 = W//2 - bw//2
        draw.rounded_rectangle([x0, y_start-18, x0+bw, y_start+34], radius=14, fill=(16,24,42,240), outline=(0,184,195,90), width=1)
        draw.text((W//2 - tw//2, y_start-4), caption, fill=(200,225,235), font=F_Text)
        y_start += 68
    # choices
    for i, ch in enumerate(choices):
        bw, bh = 460, 58
        x0 = W//2 - bw//2
        y0 = y_start + i*(bh+14)
        x1, y1 = x0+bw, y0+bh
        # button
        draw.rounded_rectangle([x0,y0,x1,y1], radius=14, fill=(19,33,60,250), outline=(58,85,135,255), width=1)
        # left accent
        draw.rounded_rectangle([x0,y0,x0+8,y1], radius=7, fill=(0,184,195))
        # number
        draw.ellipse([x0+18, y0+18, x0+40, y0+40], fill=(0,184,195,25), outline=(0,184,195,70))
        draw.text((x0+24, y0+20), str(i+1), fill=(0,184,195), font=F_Small)
        # text
        tw = draw.textlength(ch, font=F_Menu)
        draw.text((W//2 - tw//2 +4, y0+16), ch, fill=(230,238,255), font=F_Menu)
        # hover highlight line
        draw.line([(x0+12, y0+2),(x1-12, y0+2)], fill=(255,255,255,12), width=1)

def render_one(fname, scene, sprites, text, speaker=None, col=None, menu=None):
    img = Image.new("RGBA", (W,H), (8,10,22,255))
    draw = ImageDraw.Draw(img, "RGBA")
    draw_bg(img, draw, scene)
    for s in sprites:
        draw_sprite(img, draw, s["tag"], s["expr"], s["pos"], s.get("color", col or "#c8ffc8"))
    if menu:
        draw_menu(img, draw, menu.get("caption"), menu["choices"])
    else:
        draw_dialogue(img, draw, speaker, col, text)
    # top bars
    # scene badge left
    tw = draw.textlength(f"SCENE: {scene}", font=F_Small)
    draw.rounded_rectangle([16,16, 16+tw+28, 38], radius=8, fill=(0,0,0,120), outline=(255,255,255,18))
    draw.ellipse([22,22,30,30], fill=(0,184,195))
    draw.text((36,20), f"SCENE: {scene}", fill=(180,185,195), font=F_Small)
    # upvn badge right
    tw2 = draw.textlength("UPVN · UPBGE 0.50", font=F_Small)
    draw.rounded_rectangle([W-16-tw2-28,16, W-16,38], radius=8, fill=(6,22,30,190), outline=(0,184,195,80))
    draw.text((W-16-tw2-14,20), "UPVN · UPBGE 0.50", fill=(0,214,245), font=F_Small)
    img = img.convert("RGB")
    img.save(OUT/fname, "PNG")
    print(f"Saved {OUT/fname}")

if __name__ == "__main__":
    # 00
    render_one("00_narration.png", "bg classroom", [], "This is narration. The engine is running inside UPBGE — or headless — with typewriter and click-to-advance.", None)
    render_one("00_dialogue.png", "bg classroom", [{"tag":"eileen","expr":"neutral","pos":"center","color":"#c8ffc8"}], "This is dialogue. Hello from UPVN! The engine can advance one line at a time on click or space.", "Eileen", "#c8ffc8")
    # 01
    render_one("01_menu.png", "bg lecturehall", [{"tag":"eileen","expr":"neutral","pos":"center","color":"#c8ffc8"}], None, None, menu={"caption":None, "choices":["Library","Rooftop"]})
    render_one("01_library.png", "bg hallway", [{"tag":"eileen","expr":"happy","pos":"center","color":"#c8ffc8"}], "Quiet. Good choice. The library smells like old paper and floor polish.", "Eileen", "#c8ffc8")
    render_one("01_rooftop.png", "bg hallway", [{"tag":"eileen","expr":"happy","pos":"right","color":"#c8ffc8"}], "Windy up here. But the view is worth it.", "Eileen", "#c8ffc8")
    # 02
    render_one("02_sprites.png", "bg classroom", [{"tag":"eileen","expr":"neutral","pos":"center","color":"#a0d8b0"}], "Now we have a background and a character.", "Eileen", "#a0d8b0")
    render_one("02_expression.png", "bg classroom", [{"tag":"eileen","expr":"happy","pos":"center","color":"#a0d8b0"}], "Expressions work — same tag replaces texture with a dissolve.", "Eileen", "#a0d8b0")
    render_one("02_hide.png", "bg hallway", [], "She leaves. The background changed with a fade.", None)
    render_one("02_hybrid.png", "black", [{"tag":"eileen","expr":"idle","pos":"center","color":"#8ab4ff"}], "3D classroom would be loaded behind planes · camera preset medium_shot (hybrid)", "Eileen", "#8ab4ff")
    # 03
    render_one("03_ask.png", "bg meadow", [{"tag":"eileen","expr":"neutral","pos":"center","color":"#c8ffc8"}], "Can you help me carry these books?", "Eileen", "#c8ffc8")
    render_one("03_menu.png", "bg meadow", [{"tag":"eileen","expr":"neutral","pos":"center","color":"#c8ffc8"}], None, None, menu={"caption":None, "choices":["Help her","Say you're busy"]})
    render_one("03_good.png", "bg meadow", [{"tag":"eileen","expr":"happy","pos":"center","color":"#c8ffc8"}], "Thanks! You're really kind. You chose route good and affection is 1.", "Eileen", "#c8ffc8")
    render_one("03_neutral.png", "bg meadow", [{"tag":"eileen","expr":"neutral","pos":"center","color":"#c8ffc8"}], "Oh. Okay. I understand. Maybe next time.", "Eileen", "#c8ffc8")
    # The Question
    render_one("q_start.png", "bg lecturehall", [], "It's only when I hear the sounds of shuffling feet and supplies being put away that I realize that the lecture's over.", None)
    render_one("q_sylvie.png", "bg uni", [{"tag":"sylvie","expr":"green smile","pos":"center","color":"#a0c8a0"}], "Hi there! How was class?", "Sylvie", "#a0c8a0")
    render_one("q_menu1.png", "bg uni", [{"tag":"sylvie","expr":"green smile","pos":"center","color":"#a0c8a0"}], None, None, menu={"caption":"As soon as she catches my eye, I decide…", "choices":["To ask her right away.","To ask her later."]})
    render_one("q_rightaway.png", "bg meadow", [{"tag":"sylvie","expr":"green smile","pos":"center","color":"#a0c8a0"}], "She turns to me and smiles. She looks so welcoming that I feel my nervousness melt away.", None)
    render_one("q_menu2.png", "bg meadow", [{"tag":"sylvie","expr":"green smile","pos":"center","color":"#a0c8a0"}], None, None, menu={"caption":None, "choices":["It's a videogame.","It's an interactive book."]})
    render_one("q_good_ending.png", "black", [{"tag":"sylvie","expr":"giggle","pos":"center","color":"#a0b8ff"}], "Good Ending — We get married shortly after that. Together, we live happily ever after.", "Sylvie", "#a0c8a0")
    render_one("template_overview.png", "bg classroom", [{"tag":"eileen","expr":"neutral","pos":"left","color":"#c8ffc8"},{"tag":"sylvie","expr":"happy","pos":"right","color":"#a0c8a0"}], "UPVN template: Layer 0 BG · Layer 1 sprites · Layer 2 UI · 3D stage behind (hybrid mode)", "System", "#7eeaff")
    # Count
    print(f"Done — {len(list(OUT.glob('*.png')))} PNGs in {OUT}")
