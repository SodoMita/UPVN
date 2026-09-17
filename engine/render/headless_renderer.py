"""
UPVN Headless Renderer — Pillow simulation of UPBGE planes + blf

Headless, no GPU: generates 1280x720 PNGs that match what UPBGE would show
via bge.texture + blf. Used for CI golden traces + screenshot gating.

This is the non-stub implementation for M02/M03: Layer0 bg, Layer1 sprites,
Layer2 UI, with transition-aware fading.

Mirrors the logic in blend template: BG_Plane (ortho), Sprite planes at
POSITIONS, Dialogue_Box plane + blf text.
"""
from __future__ import annotations
from pathlib import Path
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except Exception:  # UPBGE's bundled Python may lack Pillow — give a clear message later
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore
    HAS_PIL = False
import re

W, H = 1280, 720

# M28 Adaptive: try to load upvn_gui.json for true project colors (like contract.py)
def _load_adaptive_gui():
    try:
        from pathlib import Path as _P
        import json as _json
        # Search roots similar to gui_config
        cands = [
            _P.cwd() / "game" / "upvn_gui.json",
            _P.cwd() / "assets" / "gui_config.json",
            _P.cwd() / "upvn_gui.json",
        ]
        try:
            here = _P(__file__).resolve().parents[2]
            cands += [here / "game" / "upvn_gui.json", here / "assets" / "gui_config.json"]
        except Exception:
            pass
        for cand in cands:
            if cand.exists():
                try:
                    data = _json.loads(cand.read_text(encoding="utf-8"))
                    return data
                except Exception:
                    pass
        # Try via gui_config module if available
        try:
            from .gui_config import load_gui_config
            cfg = load_gui_config()
            if cfg and cfg.get("source") != "generic_defaults":
                return cfg
        except Exception:
            pass
    except Exception:
        pass
    return None

_adaptive_gui = _load_adaptive_gui()

def _adaptive_color(key, default_hex):
    try:
        if _adaptive_gui:
            cols = _adaptive_gui.get("colors", {})
            if key in cols and cols[key]:
                h = cols[key].lstrip("#")
                if len(h) == 6:
                    return tuple(int(h[i:i+2], 16) for i in (0,2,4))
    except Exception:
        pass
    # default_hex
    try:
        h = default_hex.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0,2,4))
    except Exception:
        return (255,255,255)


# ---------------------------------------------------------------- fonts
def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]:
        try:
            if Path(p).exists():
                return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()

if HAS_PIL:
    F_Title = _load_font(22, bold=True)
    F_Name = _load_font(14, bold=True)
    F_Text = _load_font(20)
    F_TextSmall = _load_font(18)
    F_Small = _load_font(12)
    F_Menu = _load_font(19)
    F_Caption = _load_font(16)
else:
    # module stays importable without Pillow (UPBGE bundled Python);
    # render_state() raises an instructive RuntimeError before any drawing
    F_Title = F_Name = F_Text = F_TextSmall = None
    F_Small = F_Menu = F_Caption = None

def hex_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0,2,4))


def fill_rgb(c, default=(230, 245, 255)):
    """Normalize a speaker/UI color to a 0-255 fill tuple.

    Interpreter events carry hex strings ("#c8ffc8"); world-UI payloads
    carry float rgba tuples (parse_hex_color output). Both must paint."""
    if not c:
        return default
    if isinstance(c, str):
        return hex_rgb(c)
    return tuple(max(0, min(255, round(v * 255))) for v in c[:3])

# ---------------------------------------------------------------- bg
def draw_bg(img: Image.Image, draw: ImageDraw.ImageDraw, scene: str | None):
    """M27 HQ backgrounds — more polished, better colors, subtle gradients, details."""
    s = scene or "black"
    if s == "bg classroom":
        # HQ: warmer, more detailed classroom with better lighting
        for y in range(H):
            t=y/H
            r=int(240 - 18*t)
            g=int(230 - 22*t)
            b=int(200 - 28*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # windows with HQ glow
        for wx in [70, 460, 850]:
            draw.rounded_rectangle([wx, 60, wx+320, 320], radius=8, fill=(125,165,205), outline=(80,100,130), width=3)
            draw.line([(wx+160,60),(wx+160,320)], fill=(80,100,130), width=3)
            draw.line([(wx,190),(wx+320,190)], fill=(80,100,130), width=3)
            # glass highlight
            draw.rounded_rectangle([wx+10, 70, wx+150, 180], radius=5, fill=(200,230,255,120))
            draw.rounded_rectangle([wx+170, 70, wx+310, 180], radius=5, fill=(190,220,245,100))
            draw.rounded_rectangle([wx+10, 200, wx+150, 310], radius=5, fill=(180,210,235,80))
            draw.rounded_rectangle([wx+170, 200, wx+310, 310], radius=5, fill=(170,200,225,70))
        # floor line with shadow
        draw.rectangle([0,520,W,526], fill=(110,90,70))
        draw.rectangle([0,526,W,530], fill=(0,0,0,25))
        # vignette HQ
        overlay = Image.new("RGBA", (W,H), (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        for i in range(140):
            a = int(30*(1-i/140))
            od.rectangle([i,i,W-i-1,H-i-1], outline=(0,0,0,a))
        # subtle center glow
        od.ellipse([W//2-500, H//2-350, W//2+500, H//2+350], fill=(255,255,220,8))
        img.alpha_composite(overlay, (0,0))
    elif s == "bg lecturehall":
        # HQ: darker, more atmospheric
        for y in range(H):
            t=y/H
            r=int(38 - 10*t); g=int(48 - 8*t); b=int(80 - 12*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # light rays HQ
        for x in [220, 640, 1060]:
            for w in range(4):
                a = int(12 - w*2)
                draw.rectangle([x-2-w, 0, x+2+w, 360], fill=(255,240,180,a))
        draw.rectangle([0,480,W,540], fill=(24,28,42))
        draw.rectangle([W//2-140,450,W//2+140,480], fill=(38,44,66), outline=(60,68,90), width=1)
        draw.ellipse([W//2-180,520,W//2+180,560], fill=(0,0,0,45))
        # HQ: add subtle audience silhouettes
        for x in range(100, W-100, 80):
            draw.ellipse([x-15, 470, x+15, 490], fill=(0,0,0,30))
    elif s == "bg meadow":
        # HQ: more vibrant, better clouds, flowers
        for y in range(H):
            t=y/H
            if t<0.52:
                tt=t/0.52
                r=int(135+70*tt); g=int(190+45*tt); b=int(240-15*tt)
            else:
                tt=(t-0.52)/0.48
                r=int(85-15*tt); g=int(145-20*tt); b=int(80-15*tt)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        draw.ellipse([-300,380,800,620], fill=(90,150,90))
        draw.ellipse([500,400,1450,650], fill=(75,130,75))
        # HQ flowers
        for fx, fy in [(200, 600), (400, 620), (900, 610), (1100, 630)]:
            draw.ellipse([fx-6, fy-6, fx+6, fy+6], fill=(255,220,80))
            draw.ellipse([fx-3, fy-3, fx+3, fy+3], fill=(255,240,150))
        for cx,cy in [(260,110),(620,90),(980,120)]:
            draw.ellipse([cx-90,cy-30,cx+90,cy+30], fill=(255,255,255,110))
            draw.ellipse([cx-60,cy-45,cx+60,cy+10], fill=(255,255,255,95))
            draw.ellipse([cx-30,cy-35,cx+30,cy+5], fill=(255,255,255,80))
    elif s == "bg uni":
        for y in range(H):
            t=y/H
            r=int(65+35*t); g=int(100+40*t); b=int(150+25*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        draw.rectangle([0,360,W,560], fill=(38,48,68))
        for x in range(60,W,170):
            draw.rectangle([x,300,x+110,360], fill=(55,65,85), outline=(75,85,105), width=2)
            for wy in [315,335]:
                draw.rectangle([x+12,wy,x+98,wy+14], fill=(255,240,170))
                draw.rectangle([x+14,wy+2,x+96,wy+6], fill=(255,255,200,180))
        for x in [120,340,760,1020]:
            draw.ellipse([x-35,340,x+35,385], fill=(50,95,50))
            draw.ellipse([x-20,345,x+20,380], fill=(60,110,60))
            draw.rectangle([x-6,385,x+6,410], fill=(75,55,35))
    elif s == "bg hallway":
        for y in range(H):
            t=y/H
            r=int(120-30*t); g=int(100-22*t); b=int(70-12*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        draw.polygon([(0,0),(340,0),(260,H),(0,H)], fill=(130,110,80))
        draw.polygon([(W,0),(W-340,0),(W-260,H),(W,H)], fill=(120,100,73))
        for y in range(380,H,70):
            w=int((y-380)*0.9+90)
            draw.polygon([(W//2-w//2,y),(W//2+w//2,y),(W//2+w//2+40,y+70),(W//2-w//2-40,y+70)], outline=(90,75,55), width=1, fill=(140,120,90) if (y//70)%2==0 else (130,110,83))
        for x in [30,170,1010,1150]:
            draw.rectangle([x,120,x+100,380], fill=(65,90,110), outline=(45,65,85), width=2)
            draw.ellipse([x+70,240,x+78,248], fill=(210,210,190))
            # door handle highlight
            draw.ellipse([x+72,242,x+76,246], fill=(255,255,255,120))

    elif s == "bg forest":
        # HQ fantasy forest: dark canopy, shafts of light, mossy floor
        for y in range(H):
            t = y/H
            if t < 0.4:
                tt = t/0.4
                r = int(15+10*tt); g = int(28+15*tt); b = int(18+12*tt)
            else:
                tt = (t-0.4)/0.6
                r = int(25+18*tt); g = int(43+22*tt); b = int(30+15*tt)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # tree trunks
        for tx in [100, 350, 700, 1050]:
            draw.rectangle([tx-12, 100, tx+12, H-80], fill=(45,30,18))
            draw.rectangle([tx-8, 120, tx+8, H-100], fill=(55,38,22))
            # canopy
            draw.ellipse([tx-80, 20, tx+80, 180], fill=(20,55,25,180))
            draw.ellipse([tx-60, 50, tx+60, 150], fill=(28,65,30,160))
        # light shafts
        overlay = Image.new("RGBA", (W,H), (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        for lx in [300, 800]:
            for w in range(30):
                a = int(8 - w*0.25)
                od.polygon([(lx-w,0),(lx+w,0),(lx+w+60,H),(lx-w+60,H)], fill=(255,240,180,a))
        img.alpha_composite(overlay, (0,0))
    elif s == "bg castle":
        # HQ fantasy castle: stone walls, torchlight, vaulted ceiling
        for y in range(H):
            t = y/H
            r = int(35+15*t); g = int(30+12*t); b = int(40+18*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # stone blocks
        for by in range(0, 500, 40):
            for bx in range(0, W, 80):
                offset = 40 if (by // 40) % 2 else 0
                draw.rectangle([bx+offset, by, bx+offset+78, by+38], outline=(50,45,55,100), width=1)
        # archway
        draw.arc([W//2-200, 200, W//2+200, 600], 180, 0, fill=(60,55,70), width=8)
        draw.rectangle([W//2-200, 400, W//2-192, H-40], fill=(60,55,70))
        draw.rectangle([W//2+192, 400, W//2+200, H-40], fill=(60,55,70))
        # torch glow
        overlay = Image.new("RGBA", (W,H), (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        for tx in [200, W-200]:
            od.ellipse([tx-60, 300, tx+60, 420], fill=(255,160,60,30))
            od.ellipse([tx-30, 330, tx+30, 390], fill=(255,200,80,40))
        img.alpha_composite(overlay, (0,0))
    elif s == "bg mountain":
        # HQ fantasy mountain: misty peaks, dramatic sky
        for y in range(H):
            t = y/H
            if t < 0.45:
                tt = t/0.45
                r = int(70+50*tt); g = int(90+55*tt); b = int(140+40*tt)
            else:
                tt = (t-0.45)/0.55
                r = int(120-40*tt); g = int(145-35*tt); b = int(180-60*tt)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # peaks
        draw.polygon([(200,280),(400,120),(600,280)], fill=(75,80,95))
        draw.polygon([(500,300),(750,80),(1000,300)], fill=(65,70,85))
        draw.polygon([(800,320),(1050,160),(1280,320)], fill=(85,90,100))
        # snow caps
        draw.polygon([(370,130),(400,120),(430,130)], fill=(220,230,245))
        draw.polygon([(720,90),(750,80),(780,90)], fill=(210,220,240))
        # mist
        overlay = Image.new("RGBA", (W,H), (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        for my in range(250, 350):
            a = int(30 * (1 - abs(my-300)/50))
            od.line([(0,my),(W,my)], fill=(200,210,230,a))
        img.alpha_composite(overlay, (0,0))
    elif s == "bg bridge":
        # HQ sci-fi bridge: dark panels, holographic displays, ambient lights
        for y in range(H):
            t = y/H
            r = int(12+8*t); g = int(18+12*t); b = int(35+20*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # console panels
        for px in [80, 320, 960, 1200]:
            draw.rounded_rectangle([px, 280, px+120, 440], radius=5, fill=(15,25,50), outline=(0,140,200,120), width=2)
            draw.rectangle([px+10, 290, px+110, 350], fill=(0,40,80,180))
            draw.rectangle([px+10, 360, px+110, 430], fill=(0,30,60,160))
        # central viewport
        draw.rounded_rectangle([W//2-250, 30, W//2+250, 280], radius=10, fill=(5,15,40), outline=(0,100,180,150), width=3)
        # stars in viewport
        import random
        random.seed(42)
        for _ in range(30):
            sx = random.randint(W//2-240, W//2+240)
            sy = random.randint(40, 270)
            draw.ellipse([sx-1,sy-1,sx+1,sy+1], fill=(200,220,255,180))
        # ambient glow
        overlay = Image.new("RGBA", (W,H), (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        od.ellipse([W//2-120, 60, W//2+120, 250], fill=(0,80,140,20))
        img.alpha_composite(overlay, (0,0))
    elif s == "bg corridor":
        # HQ sci-fi corridor: perspective lines, grating, ambient
        for y in range(H):
            t = y/H
            r = int(18+10*t); g = int(24+14*t); b = int(45+22*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # perspective walls
        draw.polygon([(0,0),(350,180),(350,540),(0,H)], fill=(22,30,55))
        draw.polygon([(W,0),(W-350,180),(W-350,540),(W,H)], fill=(22,30,55))
        # floor grating
        for gy in range(540, H, 8):
            draw.line([(350,gy),(W-350,gy)], fill=(30,38,65,100))
        # ceiling lights
        for lx in range(450, W-400, 120):
            draw.rectangle([lx, 175, lx+60, 180], fill=(60,180,220,120))
            draw.ellipse([lx+10, 180, lx+50, 200], fill=(60,180,220,30))
    elif s == "bg planet":
        # HQ sci-fi planet: space view, planet surface, alien sky
        for y in range(H):
            t = y/H
            if t < 0.5:
                tt = t/0.5
                r = int(5+15*tt); g = int(8+20*tt); b = int(25+35*tt)
            else:
                tt = (t-0.5)/0.5
                r = int(20+30*tt); g = int(28+25*tt); b = int(60-10*tt)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # planet curve
        draw.ellipse([W//2-400, -200, W//2+400, 500], fill=(25,45,70))
        draw.ellipse([W//2-380, -180, W//2+380, 480], fill=(30,55,80))
        # atmosphere glow
        overlay = Image.new("RGBA", (W,H), (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        od.ellipse([W//2-420, -220, W//2+420, 520], outline=(60,140,200,60), width=8)
        # alien vegetation dots
        for gx in range(200, W-200, 40):
            import random
            random.seed(hash(str(gx)))
            gy = 400 + random.randint(-20, 20)
            draw.ellipse([gx-4, gy-4, gx+4, gy+4], fill=(40,120,60,120))
        img.alpha_composite(overlay, (0,0))
    elif s == "bg office":
        # HQ mystery office: noir lighting, desk, venetian blinds
        for y in range(H):
            t = y/H
            r = int(28+8*t); g = int(25+6*t); b = int(30+10*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # desk
        draw.rectangle([100, 420, W-100, 440], fill=(55,35,20))
        draw.rectangle([120, 440, W-120, 580], fill=(45,28,15))
        # desk items
        draw.rectangle([200, 400, 350, 420], fill=(60,55,50))  # typewriter
        draw.rectangle([900, 405, 1000, 420], fill=(40,35,30))  # papers
        # blinds (noir light shafts)
        overlay = Image.new("RGBA", (W,H), (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        for by in range(0, 350, 25):
            od.rectangle([0, by, W, by+12], fill=(0,0,0,60))
        # light shaft through blinds
        od.polygon([(800,0),(950,0),(1100,400),(900,400)], fill=(180,160,120,25))
        img.alpha_composite(overlay, (0,0))
    elif s == "bg manor":
        # HQ mystery manor: dark wood, chandelier, curtains
        for y in range(H):
            t = y/H
            r = int(32+10*t); g = int(28+8*t); b = int(22+6*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # wood panels
        for py in range(0, 400, 60):
            draw.rectangle([0, py, W, py+58], outline=(45,35,25,80), width=1)
        # chandelier
        draw.line([(W//2,0),(W//2,80)], fill=(80,65,40))
        draw.ellipse([W//2-60, 80, W//2+60, 100], outline=(100,80,50), width=2)
        for cx in range(W//2-50, W//2+51, 25):
            draw.line([(cx,100),(cx,120)], fill=(80,65,40))
            draw.ellipse([cx-6, 118, cx+6, 130], fill=(255,220,120,120))
        # curtains
        draw.rectangle([0,0,120,H], fill=(80,25,25))
        draw.rectangle([W-120,0,W,H], fill=(80,25,25))
        # glow from chandelier
        overlay = Image.new("RGBA", (W,H), (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        od.ellipse([W//2-200, 60, W//2+200, 300], fill=(255,220,120,15))
        img.alpha_composite(overlay, (0,0))
    elif s == "bg garden":
        # HQ mystery garden: overgrown, moonlit, misty
        for y in range(H):
            t = y/H
            if t < 0.5:
                tt = t/0.5
                r = int(15+10*tt); g = int(20+15*tt); b = int(35+20*tt)
            else:
                tt = (t-0.5)/0.5
                r = int(25+20*tt); g = int(35+25*tt); b = int(55-10*tt)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # moon
        draw.ellipse([900, 40, 1000, 140], fill=(200,210,230,150))
        draw.ellipse([920, 35, 1020, 135], fill=(15,20,35))  # crescent shadow
        # overgrown hedges
        for hx in range(50, W, 180):
            draw.ellipse([hx-40, 350, hx+40, 450], fill=(25,50,30,180))
            draw.ellipse([hx-30, 340, hx+30, 420], fill=(30,60,35,160))
        # path
        draw.polygon([(W//2-40,H),(W//2+40,H),(W//2+20,400),(W//2-20,400)], fill=(50,45,38))
        # mist
        overlay = Image.new("RGBA", (W,H), (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        for my in range(350, 450):
            a = int(25 * (1 - abs(my-400)/50))
            od.line([(0,my),(W,my)], fill=(150,160,180,a))
        img.alpha_composite(overlay, (0,0))

    elif s == "black" or s is None:
        # HQ: dark with subtle radial glow, not flat
        for y in range(H):
            t=y/H
            r=int(8+6*t); g=int(10+8*t); b=int(18+12*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        overlay=Image.new("RGBA",(W,H),(0,0,0,0))
        od=ImageDraw.Draw(overlay)
        od.ellipse([W//2-450,H//2-320,W//2+450,H//2+320], fill=(25,35,65,55))
        od.ellipse([W//2-250,H//2-180,W//2+250,H//2+180], fill=(35,50,85,35))
        img.alpha_composite(overlay,(0,0))
    else:
        # generic HQ with gradient
        for y in range(H):
            t=y/H
            r=int(20+12*t); g=int(24+14*t); b=int(42+18*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # subtle vignette
        overlay=Image.new("RGBA",(W,H),(0,0,0,0))
        od=ImageDraw.Draw(overlay)
        for i in range(80):
            a=int(20*(1-i/80))
            od.rectangle([i,i,W-i-1,H-i-1], outline=(0,0,0,a))
        img.alpha_composite(overlay,(0,0))

def draw_stage(img: Image.Image, draw: ImageDraw.ImageDraw, state):
    """M27 HQ 3D stage — richer classroom with lighting, depth, better markers."""
    stage = state.stage or "unknown_stage"
    bg = state.scene.background if hasattr(state, "scene") else None
    if bg is None or bg == "black":
        for y in range(0, 320):
            t = y/320
            r=int(60 + 25*t); g=int(70 + 20*t); b=int(90 + 15*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        draw.rectangle([W//2 - 320, 60, W//2 + 320, 320], fill=(50,60,80), outline=(75,85,105), width=1)
        for wx in [W//2-300, W//2-100, W//2+120]:
            draw.rectangle([wx, 80, wx+160, 300], fill=(75,90,115), outline=(95,115,145), width=1)
            # window light
            draw.rectangle([wx+10, 90, wx+150, 290], fill=(200,225,255,25))
    # floor HQ — perspective with better shading
    for y in range(320, H-110):
        t = (y-320)/(H-110-320)
        r=int(42 - 12*t); g=int(48 - 10*t); b=int(65 - 12*t)
        draw.line([(0,y),(W,y)], fill=(r,g,b))
    for i in range(-3, 4):
        x_center = W//2 + i*150
        draw.line([(x_center, 320), (W//2 + i*45, H-110)], fill=(75,85,100,110), width=1)
    for y in [360, 400, 450, 520]:
        draw.line([(200,y),(W-200,y)], fill=(75,85,100,70), width=1)
    # HQ classroom
    if "classroom" in stage:
        # blackboard with frame
        draw.rounded_rectangle([W//2-190, 325, W//2+190, 365], radius=6, fill=(32,60,36), outline=(95,115,95), width=2)
        draw.rounded_rectangle([W//2-185, 330, W//2+185, 360], radius=4, fill=(28,55,32))
        draw.text((W//2-45, 338), "BOARD", fill=(185,225,185), font=F_Small)
        # teacher desk HQ
        draw.rounded_rectangle([W//2-95, 372, W//2+95, 395], radius=7, fill=(115,90,65), outline=(85,65,45), width=1)
        draw.line([(W//2, 372), (W//2, 395)], fill=(85,65,45), width=1)
        draw.ellipse([W//2-70, 395, W//2+70, 405], fill=(0,0,0,20))
        # student desks HQ — more rows, better shadows
        for row, y in enumerate([425, 475, 525]):
            for col, x in enumerate([W//2-240, W//2-80, W//2+80, W//2+240]):
                if col == 2 and row == 1:
                    continue
                draw.rounded_rectangle([x-52, y-14, x+52, y+14], radius=6, fill=(130,100,70), outline=(95,75,50), width=1)
                draw.line([(x, y-14), (x, y+14)], fill=(95,75,50), width=1)
                draw.rounded_rectangle([x-24, y+20, x+24, y+36], radius=5, fill=(90,80,70), outline=(65,60,50), width=1)
                draw.ellipse([x-32, y+36, x+32, y+42], fill=(0,0,0,22))
                # desk highlight
                draw.line([(x-50, y-12), (x+50, y-12)], fill=(255,255,255,25), width=1)
    # stage badge HQ
    txt = f"3D STAGE: {stage} — HQ"
    tw = draw.textlength(txt, font=F_Small)
    draw.rounded_rectangle([W//2 - tw//2 - 16, 335, W//2 + tw//2 +16, 360], radius=9, fill=(0,28,40,230), outline=(0,200,210,90))
    draw.text((W//2 - tw//2, 342), txt, fill=(0,220,250), font=F_Small)
    markers = {"marker_eileen": W//2 - 160, "marker_sylvie": W//2 + 160, "center": W//2, "marker_center": W//2,
               "marker_left": W//2 - 260, "marker_right": W//2 + 260}
    for asset, info in state.stage_objects.items():
        marker = info.get("marker") or "center"
        x = markers.get(marker, W//2)
        y_base = H-110
        draw.ellipse([x-50, y_base-95, x+50, y_base-10], fill=(0,0,0,30))
        draw.rounded_rectangle([x-32, 395, x+32, y_base-22], radius=9, fill=hex_rgb("#8ec8ff"), outline=(255,255,255,50))
        draw.ellipse([x-24, 375, x+24, 408], fill=(255,230,195), outline=(0,0,0,25))
        # HQ character highlight
        draw.ellipse([x-18, 385, x-8, 395], fill=(255,255,255,80))
        lab = f"show3d {asset} @ {marker} [{info.get('anim','idle')}]"
        tw2 = draw.textlength(lab, font=F_Small)
        draw.rounded_rectangle([x - tw2//2 -10, y_base+4, x+ tw2//2+10, y_base+24], radius=7, fill=(14,18,32,210), outline=(110,190,230,70))
        draw.text((x - tw2//2, y_base+9), lab, fill=(210,235,255), font=F_Small)

def draw_sprite_at_x(img: Image.Image, draw: ImageDraw.ImageDraw, tag: str, expr: str, x: int, color: str, progress: float = 1.0):
    y_bottom=515
    w,h=240,360
    x0=x-w//2; y0=y_bottom-h
    sh=Image.new("RGBA",(W,H),(0,0,0,0))
    sd=ImageDraw.Draw(sh)
    sd.ellipse([x-90,y_bottom-4,x+90,y_bottom+10], fill=(0,0,0,45))
    img.alpha_composite(sh,(0,0))
    col=hex_rgb(color or "#c8ffc8")
    sprite=Image.new("RGBA",(w,h),(0,0,0,0))
    sd2=ImageDraw.Draw(sprite)
    if progress < 1.0:
        sd2.rounded_rectangle([2,0,w-1,h-1], radius=18, fill=(255,255,255,18))
    sd2.rounded_rectangle([0,0,w-1,h-1], radius=18, fill=(0,0,0,30))
    for i in range(h):
        t=i/h
        r=int(col[0]*(0.85-0.25*t)+255*0.15*t+18)
        g=int(col[1]*(0.85-0.25*t)+255*0.15*t+18)
        b=int(col[2]*(0.85-0.25*t)+255*0.15*t+18)
        r=max(0,min(255,r)); g=max(0,min(255,g)); b=max(0,min(255,b))
        sd2.line([(6,i),(w-7,i)], fill=(r,g,b,255))
    sd2.rectangle([6,220,w-7,h-7], fill=(col[0]//2+18, col[1]//2+18, col[2]//2+18, 255))
    sd2.polygon([(w//2-34,150),(w//2,182),(w//2+34,150),(w//2+26,162),(w//2,190),(w//2-26,162)], fill=(245,245,240))
    sd2.rectangle([w//2-18,148,w//2+18,170], fill=(255,222,185))
    sd2.ellipse([w//2-52,58,w//2+52,162], fill=(255,225,190), outline=(0,0,0,28), width=2)
    hair_col=(col[0]//3+15, col[1]//3+15, col[2]//3+15)
    sd2.rounded_rectangle([w//2-62,32,w//2+62,78], radius=10, fill=hair_col)
    sd2.rectangle([w//2-62,70,w//2-44,138], fill=hair_col)
    sd2.rectangle([w//2+44,70,w//2+62,138], fill=hair_col)
    sd2.ellipse([w//2-44,118,w//2-24,128], fill=(255,160,150,70))
    sd2.ellipse([w//2+24,118,w//2+44,128], fill=(255,160,150,70))
    expr_low=expr.lower()
    if any(k in expr_low for k in ("happy","smile","giggle")):
        sd2.arc([w//2-38,98,w//2-12,116], 200,340, fill=(30,30,30), width=3)
        sd2.arc([w//2+12,98,w//2+38,116], 200,340, fill=(30,30,30), width=3)
        sd2.arc([w//2-20,122,w//2+20,138], 25,155, fill=(160,40,40), width=3)
        sd2.rectangle([w//2-8,129,w//2+8,133], fill=(255,255,255,180))
    elif "surprised" in expr_low:
        sd2.ellipse([w//2-32,96,w//2-10,118], fill=(255,255,255), outline=(30,30,30), width=2)
        sd2.ellipse([w//2+10,96,w//2+32,118], fill=(255,255,255), outline=(30,30,30), width=2)
        sd2.ellipse([w//2-24,101,w//2-16,113], fill=(30,30,30))
        sd2.ellipse([w//2+16,101,w//2+24,113], fill=(30,30,30))
        sd2.ellipse([w//2-12,124,w//2+12,140], fill=(90,20,20), outline=(60,10,10), width=1)
    elif expr_low.strip()=="idle":
        sd2.ellipse([w//2-28,97,w//2-12,114], fill=(30,30,30))
        sd2.ellipse([w//2+12,97,w//2+28,114], fill=(30,30,30))
        sd2.ellipse([w//2-22,102,w//2-18,108], fill=(255,255,255,200))
        sd2.ellipse([w//2+18,102,w//2+22,108], fill=(255,255,255,200))
        sd2.line([w//2-12,128,w//2+12,128], fill=(90,40,30), width=2)
    else:
        sd2.ellipse([w//2-28,96,w//2-11,115], fill=(255,255,255), outline=(30,30,30), width=1)
        sd2.ellipse([w//2+11,96,w//2+28,115], fill=(255,255,255), outline=(30,30,30), width=1)
        sd2.ellipse([w//2-22,102,w//2-15,111], fill=(30,30,30))
        sd2.ellipse([w//2+15,102,w//2+22,111], fill=(30,30,30))
        sd2.ellipse([w//2-20,104,w//2-17,108], fill=(255,255,255,210))
        sd2.ellipse([w//2+17,104,w//2+20,108], fill=(255,255,255,210))
        sd2.line([w//2-14,128,w//2+14,128], fill=(90,30,30), width=2)
    sd2.rounded_rectangle([0,0,w-1,h-1], radius=18, outline=(0,0,0,55), width=1)
    sd2.rounded_rectangle([1,1,w-2,h-2], radius=17, outline=(255,255,255,28), width=1)
    img.alpha_composite(sprite,(x0,y0))
    txt=f"{tag}  •  {expr}  {int(progress*100)}%"
    tw=draw.textlength(txt, font=F_Small)
    y_bottom2=515
    bx0=x-tw//2-14; by0=y_bottom2+12
    draw.rounded_rectangle([bx0,by0,bx0+tw+28,by0+22], radius=11, fill=(12,16,28,215), outline=(0,184,195,65), width=1)
    draw.ellipse([bx0+8,by0+6,bx0+18,by0+16], fill=(0,184,195))
    draw.text((bx0+24,by0+4), txt, fill=(190,220,230), font=F_Small)

def draw_sprite(img: Image.Image, draw: ImageDraw.ImageDraw, tag: str, expr: str, pos: str, color: str):
    x_map={"left":300,"center":640,"right":980,"far_left":180,"far_right":1100}
    x=x_map.get(pos,640)
    y_bottom=515
    w,h=240,360
    x0=x-w//2; y0=y_bottom-h
    sh=Image.new("RGBA",(W,H),(0,0,0,0))
    sd=ImageDraw.Draw(sh)
    sd.ellipse([x-90,y_bottom-4,x+90,y_bottom+10], fill=(0,0,0,45))
    img.alpha_composite(sh,(0,0))
    col=hex_rgb(color or "#c8ffc8")
    sprite=Image.new("RGBA",(w,h),(0,0,0,0))
    sd2=ImageDraw.Draw(sprite)
    sd2.rounded_rectangle([0,0,w-1,h-1], radius=18, fill=(0,0,0,30))
    for i in range(h):
        t=i/h
        r=int(col[0]*(0.85-0.25*t)+255*0.15*t+18)
        g=int(col[1]*(0.85-0.25*t)+255*0.15*t+18)
        b=int(col[2]*(0.85-0.25*t)+255*0.15*t+18)
        r=max(0,min(255,r)); g=max(0,min(255,g)); b=max(0,min(255,b))
        sd2.line([(6,i),(w-7,i)], fill=(r,g,b,255))
    sd2.rectangle([6,220,w-7,h-7], fill=(col[0]//2+18, col[1]//2+18, col[2]//2+18, 255))
    sd2.polygon([(w//2-34,150),(w//2,182),(w//2+34,150),(w//2+26,162),(w//2,190),(w//2-26,162)], fill=(245,245,240))
    sd2.rectangle([w//2-18,148,w//2+18,170], fill=(255,222,185))
    sd2.ellipse([w//2-52,58,w//2+52,162], fill=(255,225,190), outline=(0,0,0,28), width=2)
    hair_col=(col[0]//3+15, col[1]//3+15, col[2]//3+15)
    sd2.rounded_rectangle([w//2-62,32,w//2+62,78], radius=10, fill=hair_col)
    sd2.rectangle([w//2-62,70,w//2-44,138], fill=hair_col)
    sd2.rectangle([w//2+44,70,w//2+62,138], fill=hair_col)
    sd2.ellipse([w//2-44,118,w//2-24,128], fill=(255,160,150,70))
    sd2.ellipse([w//2+24,118,w//2+44,128], fill=(255,160,150,70))
    expr_low=expr.lower()
    if any(k in expr_low for k in ("happy","smile","giggle")):
        sd2.arc([w//2-38,98,w//2-12,116], 200,340, fill=(30,30,30), width=3)
        sd2.arc([w//2+12,98,w//2+38,116], 200,340, fill=(30,30,30), width=3)
        sd2.arc([w//2-20,122,w//2+20,138], 25,155, fill=(160,40,40), width=3)
        sd2.rectangle([w//2-8,129,w//2+8,133], fill=(255,255,255,180))
    elif "surprised" in expr_low:
        sd2.ellipse([w//2-32,96,w//2-10,118], fill=(255,255,255), outline=(30,30,30), width=2)
        sd2.ellipse([w//2+10,96,w//2+32,118], fill=(255,255,255), outline=(30,30,30), width=2)
        sd2.ellipse([w//2-24,101,w//2-16,113], fill=(30,30,30))
        sd2.ellipse([w//2+16,101,w//2+24,113], fill=(30,30,30))
        sd2.ellipse([w//2-12,124,w//2+12,140], fill=(90,20,20), outline=(60,10,10), width=1)
    elif expr_low.strip()=="idle":
        sd2.ellipse([w//2-28,97,w//2-12,114], fill=(30,30,30))
        sd2.ellipse([w//2+12,97,w//2+28,114], fill=(30,30,30))
        sd2.ellipse([w//2-22,102,w//2-18,108], fill=(255,255,255,200))
        sd2.ellipse([w//2+18,102,w//2+22,108], fill=(255,255,255,200))
        sd2.line([w//2-12,128,w//2+12,128], fill=(90,40,30), width=2)
    else:
        sd2.ellipse([w//2-28,96,w//2-11,115], fill=(255,255,255), outline=(30,30,30), width=1)
        sd2.ellipse([w//2+11,96,w//2+28,115], fill=(255,255,255), outline=(30,30,30), width=1)
        sd2.ellipse([w//2-22,102,w//2-15,111], fill=(30,30,30))
        sd2.ellipse([w//2+15,102,w//2+22,111], fill=(30,30,30))
        sd2.ellipse([w//2-20,104,w//2-17,108], fill=(255,255,255,210))
        sd2.ellipse([w//2+17,104,w//2+20,108], fill=(255,255,255,210))
        sd2.line([w//2-14,128,w//2+14,128], fill=(90,30,30), width=2)
    sd2.rounded_rectangle([0,0,w-1,h-1], radius=18, outline=(0,0,0,55), width=1)
    sd2.rounded_rectangle([1,1,w-2,h-2], radius=17, outline=(255,255,255,28), width=1)
    img.alpha_composite(sprite,(x0,y0))
    txt=f"{tag}  •  {expr}"
    tw=draw.textlength(txt, font=F_Small)
    bx0=x-tw//2-14; by0=y_bottom+12
    draw.rounded_rectangle([bx0,by0,bx0+tw+28,by0+22], radius=11, fill=(12,16,28,215), outline=(0,184,195,65), width=1)
    draw.ellipse([bx0+8,by0+6,bx0+18,by0+16], fill=(0,184,195))
    draw.text((bx0+24,by0+4), txt, fill=(190,220,230), font=F_Small)

def draw_dialogue(img: Image.Image, draw: ImageDraw.ImageDraw, speaker, speaker_color, text):
    """M27 HQ dialogue — darker, more readable, better speaker badge, subtle glow.
    M28 Adaptive: if upvn_gui.json exists, uses its accent/text colors for Ren'Py parity.
    """
    box_y0=538; box_h=H-box_y0
    box=Image.new("RGBA",(W,box_h),(0,0,0,0))
    bd=ImageDraw.Draw(box,"RGBA")
    # HQ: darker, more polished box with inner glow
    # Adaptive: dialogue box color from gui config, default white 255,255,255,204 for Ren'Py parity
    try:
        db = _adaptive_color("dialogue_box", "#FFFFFF")
        # For Ren'Py parity, white box with alpha 204; if adaptive is not white, use its color with 230 alpha
        if db == (255,255,255):
            box_fill = (255,255,255,204)
            box_outline = (42,60,100,200)
        else:
            box_fill = db + (230,)
            box_outline = (42,60,100,200)
    except Exception:
        box_fill = (8,12,26,240)
        box_outline = (42,60,100,255)
    bd.rounded_rectangle([20,12,W-20,box_h-12], radius=18, fill=box_fill, outline=box_outline, width=1)
    # inner fill: if adaptive white, keep white too (Ren'Py parity)
    try:
        _db = _adaptive_color('dialogue_box', '#FFFFFF')
        inner_fill = (255,255,255,204) if _db == (255,255,255) else (_db + (230,))
    except Exception:
        inner_fill = (10,14,28,235)
    bd.rounded_rectangle([22,14,W-22,box_h-14], radius=16, fill=inner_fill)
    bd.line([(34,20),(W-34,20)], fill=(0,184,195,65), width=1)
    bd.line([(34,box_h-18),(W-34,box_h-18)], fill=(255,255,255,12), width=1)
    # inner highlight
    bd.line([(32,22),(W-32,22)], fill=(255,255,255,8), width=1)
    img.alpha_composite(box,(0,box_y0))
    if speaker:
        tw=draw.textlength(speaker, font=F_Name)
        nx,ny=58, box_y0+4
        # HQ speaker badge — more polished
        draw.rounded_rectangle([nx,ny,nx+tw+32,ny+28], radius=14, fill=(16,40,50,255), outline=(0,190,200,120), width=1)
        draw.rounded_rectangle([nx+2,ny+2,nx+tw+30,ny+26], radius=12, fill=(20,50,60,180))
        draw.ellipse([nx+10,ny+8,nx+20,ny+18], fill=fill_rgb(speaker_color, (126, 234, 255)))
        draw.ellipse([nx+12,ny+10,nx+16,ny+14], fill=(255,255,255,120))
        draw.text((nx+28,ny+5), speaker, fill=fill_rgb(speaker_color), font=F_Name)
        text_y=box_y0+44
    else:
        text_y=box_y0+30
    if text:
        clean=re.sub(r"\{[^}]+?\}","",text)
        # variable interpolation display
        max_w=W-150
        wrapped=[]
        for para in clean.split("\n"):
            cur=""
            for w in para.split():
                test=cur+" "+w if cur else w
                if draw.textlength(test, font=F_Text)>max_w:
                    wrapped.append(cur); cur=w
                else:
                    cur=test
            if cur: wrapped.append(cur)
        wrapped=wrapped[:3]
        for line in wrapped:
            # HQ: slight shadow for readability
            draw.text((75,text_y+1), line, fill=(0,0,0,80), font=F_Text)
            draw.text((74,text_y), line, fill=(30,35,45), font=F_Text)
            text_y+=30
        draw.polygon([(W-70,H-30),(W-58,H-22),(W-46,H-30)], fill=(0,184,195))
        draw.ellipse([W//2-4,H-10,W//2+4,H-6], fill=(0,184,195,180))
    draw.text((W-190,H-20), "click / space → HQ", fill=(80,90,110), font=F_Small)

def draw_menu(img: Image.Image, draw: ImageDraw.ImageDraw, caption, choices):
    """M27 HQ menu — better buttons with edge glow, larger click area, polished."""
    ov=Image.new("RGBA",(W,H),(6,10,22,160))
    img.alpha_composite(ov,(0,0))
    vig=Image.new("RGBA",(W,H),(0,0,0,0))
    vd=ImageDraw.Draw(vig)
    for i in range(100):
        a=int(22*(1-i/100))
        vd.rounded_rectangle([i,i,W-i-1,H-i-1], radius=20, outline=(0,0,0,a))
    img.alpha_composite(vig,(0,0))
    y_start=220
    if caption:
        tw=draw.textlength(caption, font=F_Text)
        bw=tw+56; x0=W//2-bw//2
        # HQ caption with glow
        draw.rounded_rectangle([x0-2,y_start-20,x0+bw+2,y_start+36], radius=16, fill=(0,184,195,30))
        draw.rounded_rectangle([x0,y_start-18,x0+bw,y_start+34], radius=14, fill=(14,22,40,245), outline=(0,190,200,100), width=1)
        draw.text((W//2-tw//2,y_start-4), caption, fill=(210,235,245), font=F_Text)
        y_start+=72
    for i,ch in enumerate(choices):
        bw,bh=480,62
        x0=W//2-bw//2; y0=y_start+i*(bh+16); x1,y1=x0+bw,y0+bh
        # HQ button — edge glow, better contrast
        draw.rounded_rectangle([x0-1,y0-1,x1+1,y1+1], radius=15, fill=(0,184,195,40))
        draw.rounded_rectangle([x0,y0,x1,y1], radius=14, fill=(18,32,62,252), outline=(62,90,140,255), width=1)
        draw.rounded_rectangle([x0,y0,x0+10,y1], radius=7, fill=(0,184,195))
        # number badge HQ
        draw.ellipse([x0+18,y0+18,x0+42,y0+42], fill=(0,184,195,30), outline=(0,184,195,80))
        draw.text((x0+26,y0+22), str(i+1), fill=(0,200,210), font=F_Small)
        tw=draw.textlength(ch, font=F_Menu)
        # text with shadow HQ
        draw.text((W//2-tw//2+5,y0+17), ch, fill=(0,0,0,100), font=F_Menu)
        draw.text((W//2-tw//2+4,y0+16), ch, fill=(235,242,255), font=F_Menu)
        draw.line([(x0+14,y0+3),(x1-14,y0+3)], fill=(255,255,255,15), width=1)

def draw_history_overlay(img: Image.Image, draw: ImageDraw.ImageDraw, state):
    ov = Image.new("RGBA", (W,H), (6,10,22,165))
    img.alpha_composite(ov, (0,0))
    box = Image.new("RGBA", (W, H), (0,0,0,0))
    bd = ImageDraw.Draw(box, "RGBA")
    bd.rounded_rectangle([30, 80, W-30, H-110], radius=14, fill=(12,16,32,240), outline=(0,184,195,90), width=1)
    img.alpha_composite(box, (0,0))
    draw.rounded_rectangle([50, 92, 50+280, 122], radius=8, fill=(0,25,35,200), outline=(0,184,195,80))
    draw.text((70,100), "HISTORY  —  H to close  •  stripped view", fill=(0,214,245), font=F_Small)
    y = 140
    from ..core.vn_interpreter import strip_tags
    entries = state.history[-10:]
    if not entries:
        draw.text((70,y), "(no history yet)", fill=(150,160,180), font=F_TextSmall)
    else:
        for e in entries:
            who = e.get("who_name") or e.get("who") or "—"
            txt = strip_tags(e.get("text",""))
            line = f'{who}: {txt}'
            while draw.textlength(line, font=F_TextSmall) > W-140 and len(line) > 20:
                line = line[:-3] + "…"
            draw.text((70,y), line[:90], fill=(220,230,240), font=F_TextSmall)
            y += 22
            if y > H-140: break
    draw.text((70, H-125), "Overlay — non-blocking (M09): story pauses visually but not logically", fill=(120,150,180), font=F_Small)

def draw_save_overlay(img: Image.Image, draw: ImageDraw.ImageDraw, state, mode="SAVE", slots=6, save_manager=None, page=0, page_size=6):
    # Arbitrary slots: pagination, any integer slot id
    ov = Image.new("RGBA", (W,H), (10,15,30,210))
    img.alpha_composite(ov, (0,0))
    title = "SAVE GAME" if mode=="SAVE" else "LOAD GAME"
    draw.rounded_rectangle([W//2-180, 70, W//2+180, 115], radius=10, fill=(0,30,45,240), outline=(0,184,195,100), width=1)
    tw = draw.textlength(title, font=F_Title)
    draw.text((W//2 - tw//2, 84), title, fill=(0,214,245), font=F_Title)
    # subtitle with arbitrary hint
    if save_manager and hasattr(save_manager, "list_slot_ids"):
        total = len([x for x in save_manager.list_slot_ids() if isinstance(x, int)])
        sub = f"Arbitrary slots 1..∞  •  {total} saves  •  page {page+1}  •  ESC cancels"
    else:
        sub = "Modal — blocking (M09): choose slot, ESC cancels, returns value"
    draw.text((W//2-180, 125), sub, fill=(120,180,210), font=F_Small)
    y0 = 160
    # determine which slot numbers to show for this page
    # for SAVE: show continuous range start..end (empty + existing)
    # for LOAD: show only existing sorted ids for this page
    if save_manager and hasattr(save_manager, "list_slot_ids"):
        ids = sorted([x for x in save_manager.list_slot_ids() if isinstance(x, int)])
        if mode == "LOAD":
            # paginate existing only
            page_ids = ids[page*page_size:(page+1)*page_size]
            slots_to_show = page_ids
            # if no ids, show empty placeholder
            if not slots_to_show:
                slots_to_show = []
        else:
            # SAVE: show range page*size+1 .. (page+1)*size
            start = page*page_size + 1
            slots_to_show = list(range(start, start+page_size))
    else:
        slots_to_show = list(range(1, slots+1))
        page_ids = slots_to_show if 'page_ids' not in locals() else page_ids

    # grid layout 3 cols
    for idx, sid in enumerate(slots_to_show):
        col = idx % 3
        row = idx // 3
        x0 = 100 + col*360
        y = y0 + row*190
        exists = False
        info = f"Slot {sid} — Empty"
        if save_manager:
            try:
                p = Path(save_manager.save_dir) / f"save_{sid}.json"
                if p.exists():
                    import json, time
                    d = json.loads(p.read_text())
                    tm = time.strftime("%Y-%m-%d %H:%M", time.localtime(d.get("timestamp",0)))
                    exists = True
                    var = d.get("variables",{})
                    info = f'Slot {sid}  {tm}  {d.get("current_label")}:{d.get("instruction_index")}  aff={var.get("affection","?")}'
                    if len(info) > 38:
                        info = info[:35] + "…"
            except: pass
        fill = (25,40,65,240) if exists else (18,28,45,180)
        out = (0,184,195,90) if exists else (60,80,110,60)
        draw.rounded_rectangle([x0, y, x0+300, y+150], radius=10, fill=fill, outline=out, width=1)
        draw.text((x0+16, y+16), info, fill=(220,235,255), font=F_Small)
        draw.text((x0+16, y+45), f'"{state.history[-1]["stripped"][:28]}..."' if state.history else "—", fill=(150,170,200), font=F_Small)
        draw.rounded_rectangle([x0+16, y+110, x0+284, y+135], radius=7, fill=(0,184,195,30), outline=(0,184,195,80))
        draw.text((x0+90, y+116), "Select" if exists or mode=="SAVE" else "Empty", fill=(0,214,245), font=F_Small)

    # pagination indicator & hint for arbitrary
    if save_manager and hasattr(save_manager, "list_slot_ids"):
        total_pages = 1
        if mode == "LOAD":
            ids = [x for x in save_manager.list_slot_ids() if isinstance(x, int)]
            total_pages = max(1, (len(ids) + page_size -1)//page_size)
        else:
            # for SAVE, we allow infinite pages, but show next page hint
            total_pages = max(1, page+1)
            # if many saves, compute
            ids = [x for x in save_manager.list_slot_ids() if isinstance(x, int)]
            if ids:
                total_pages = max(total_pages, (max(ids) + page_size -1)//page_size + 1)
        pag_txt = f"Page {page+1}/{total_pages}  •  arbitrary: any slot number via API save(slot)  •  ← → to paginate"
        draw.text((W//2 - draw.textlength(pag_txt, font=F_Small)//2, y0 + page_size//3*190 + 30), pag_txt, fill=(120,150,180), font=F_Small)
    draw.text((W//2-140, H-45), "SaveManager JSON — no pickle, no screens.rpy DSL • arbitrary slots", fill=(120,150,180), font=F_Small)

def draw_main_menu_overlay(img: Image.Image, draw: ImageDraw.ImageDraw, state):
    ov = Image.new("RGBA", (W,H), (6,10,22,220))
    img.alpha_composite(ov,(0,0))
    bw, bh = 420, 320
    x0, y0 = W//2 - bw//2, H//2 - bh//2
    draw.rounded_rectangle([x0,y0,x0+bw,y0+bh], radius=14, fill=(16,24,42,245), outline=(0,184,195,80), width=1)
    draw.text((x0+20, y0+18), "UPVN — Main Menu", fill=(0,214,245), font=F_Title)
    draw.line([(x0+20,y0+52),(x0+bw-20,y0+52)], fill=(0,184,195,40), width=1)
    choices = ["New Game", "Continue", "Load", "Preferences", "Quit"]
    for i,ch in enumerate(choices):
        yy = y0+70 + i*46
        draw.rounded_rectangle([x0+20, yy, x0+bw-20, yy+36], radius=8, fill=(22,36,60,200), outline=(60,85,120,80))
        draw.text((x0+40, yy+10), ch, fill=(220,235,255), font=F_Menu)
        draw.text((x0+bw-50, yy+12), f"{i+1}", fill=(0,184,195), font=F_Small)
    draw.text((x0+20, y0+bh-22), "Modal — ESC returns, select returns value (M09)", fill=(120,150,180), font=F_Small)

def draw_quick_menu_overlay(img: Image.Image, draw: ImageDraw.ImageDraw, state):
    draw.rounded_rectangle([W//2-320, 12, W//2+320, 52], radius=10, fill=(12,20,36,210), outline=(0,184,195,70), width=1)
    buttons = ["Save","Load","Hist","Skip","Auto","Prefs"]
    x = W//2-300
    for b in buttons:
        tw = draw.textlength(b, font=F_Small)
        active = (b=="Skip" and state.skip) or (b=="Auto" and state.auto)
        fill = (0,184,195,180) if active else (22,36,60,180)
        tc = (0,10,20) if active else (190,220,230)
        draw.rounded_rectangle([x, 20, x+tw+24, 44], radius=7, fill=fill, outline=(0,184,195,60))
        draw.text((x+12, 26), b, fill=tc, font=F_Small)
        x += tw+32 + 8

# ---------------------------------------------------------------- public
def _pil_probe():
    """Live check + binding of PIL names. The module may have been imported in
    the same Blender session before Pillow was installed, so HAS_PIL alone is
    stale — re-import on every render attempt. Raises RuntimeError with the
    install instruction when Pillow is genuinely unavailable."""
    global HAS_PIL, Image, ImageDraw, ImageFont
    if not HAS_PIL:
        try:
            from PIL import Image, ImageDraw, ImageFont
            HAS_PIL = True
        except Exception:
            raise RuntimeError(
                "Pillow (PIL) is not available in this Python interpreter. Install it into "
                "UPBGE's bundled Python, e.g.:\n"
                "  python3 -m pip install --python-version 3.11 --only-binary=:all: \\\n"
                "      --target <upbge>/5.0/python/lib/python3.11/site-packages pillow\n"
                "(UPBGE 0.50 ships Python as a lib only — no bin/python3.11 — so pip must\n"
                "cross-install from the host python3; without --python-version it installs\n"
                "host-ABI wheels and _imaging fails to load.)\n"
                "If you just installed it, restart Blender/UPBGE so the interpreter sees it."
            )
    return Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- M23 screens
# Widget trees produced by engine/ui/screen_lang.py. Ren'Py's real layout
# engine (predicted sizes, style inheritance, transforms) is deliberately not
# reimplemented: the point here is that a `show screen` is *visible* in a golden
# trace, so a human can tell the UI apart from an empty frame. Layout is a
# simple two-pass measure/place flow over vbox/hbox/frame, honouring the
# `xalign`/`yalign`/`spacing`/`xsize` hints that screen_lang leaves in `props`.

_SCR_PAD = 14
_SCR_GAP = 8


def _scr_num(value, default=0.0):
    """Coerce a prop to a number; props may be int, float or source text."""
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        t = value.strip()
        try:
            return float(t)
        except ValueError:
            return default
    return default


def _scr_color(value, default):
    if isinstance(value, str) and value.startswith("#"):
        try:
            return hex_rgb(value)
        except Exception:
            return default
    return default


def _scr_align(props, key, default):
    """`xalign 0.5` -> 0.5. Falls back to the default when absent/unparsable."""
    if key not in props:
        return default
    raw = props[key]
    if isinstance(raw, str) and not raw.replace('.', '', 1).replace('-', '', 1).isdigit():
        return default          # an unresolved expression: don't guess
    return _scr_num(raw, default)


def _scr_size(w, draw):
    """Measure a widget. Returns (width, height)."""
    kind = w.get("kind")
    props = w.get("props") or {}
    kids = w.get("children") or []

    if kind in ("text", "label"):
        font = F_Text if kind == "text" else F_Name
        txt = str(w.get("text") or "")
        tw = int(draw.textlength(txt, font=font)) if txt else 0
        return min(tw, W - 120), font.size + 6

    if kind == "textbutton":
        txt = str(w.get("text") or "")
        tw = int(draw.textlength(txt, font=F_Menu)) if txt else 0
        return tw + 34, F_Menu.size + 18

    if kind == "input":
        return 260, F_Text.size + 16

    if kind in ("add", "image", "imagebutton"):
        return 132, 74

    if kind == "bar":
        return 220, 16
    if kind == "vbar":
        return 16, 140

    if kind in ("key", "timer", "mousearea", "null"):
        return 0, 0

    # containers
    if kind in ("hbox", "vbox"):
        gap = _scr_num(props.get("spacing"), _SCR_GAP)
    else:
        gap = _SCR_GAP
    if not kids:
        if kind in ("frame", "window"):
            return _SCR_PAD * 2, _SCR_PAD * 2
        return 0, 0

    sizes = [_scr_size(k, draw) for k in kids]
    if kind == "hbox":
        inner_w = sum(s[0] for s in sizes) + gap * (len(sizes) - 1)
        inner_h = max(s[1] for s in sizes)
    else:
        inner_w = max(s[0] for s in sizes)
        inner_h = sum(s[1] for s in sizes) + gap * (len(sizes) - 1)

    if kind in ("frame", "window"):
        return inner_w + _SCR_PAD * 2, inner_h + _SCR_PAD * 2
    return inner_w, inner_h


def _scr_draw(w, img, draw, x, y, avail_w):
    """Draw a widget inside the box whose top-left is (x, y)."""
    kind = w.get("kind")
    props = w.get("props") or {}
    kids = w.get("children") or []

    if kind in ("key", "timer", "mousearea", "null"):
        return
    if not kind:
        return

    my_w, my_h = _scr_size(w, draw)

    if kind in ("text", "label"):
        font = F_Text if kind == "text" else F_Name
        ax = _scr_align(props, "xalign", 0.0)
        color = _scr_color(props.get("color"), (232, 236, 242))
        tx = int(x + (avail_w - my_w) * ax)
        draw.text((tx, y), str(w.get("text") or ""), fill=color, font=font)
        return

    if kind == "textbutton":
        ax = _scr_align(props, "xalign", 0.0)
        bx = int(x + (avail_w - my_w) * ax)
        has_action = bool(props.get("action"))
        bg = (24, 58, 78, 235) if has_action else (30, 34, 44, 200)
        edge = (0, 214, 245, 220) if has_action else (255, 255, 255, 40)
        draw.rounded_rectangle([bx, y, bx + my_w, y + my_h], radius=9,
                               fill=bg, outline=edge, width=2)
        draw.text((bx + 17, y + 8), str(w.get("text") or ""),
                  fill=(226, 240, 248), font=F_Menu)
        return

    if kind == "input":
        draw.rounded_rectangle([x, y, x + my_w, y + my_h], radius=8,
                               fill=(10, 26, 36, 235), outline=(0, 214, 245, 140),
                               width=2)
        draw.text((x + 12, y + 9), str(w.get("text") or "") + "|",
                  fill=(150, 200, 220), font=F_Text)
        return

    if kind in ("add", "image", "imagebutton"):
        # the asset itself is not available headless — show a labelled plate so
        # the frame still reads as "something is here"
        ax = _scr_align(props, "xalign", 0.0)
        bx = int(x + (avail_w - my_w) * ax)
        draw.rounded_rectangle([bx, y, bx + my_w, y + my_h], radius=6,
                               fill=(16, 30, 44, 210), outline=(0, 184, 195, 110),
                               width=2)
        label = str(w.get("text") or kind)
        label = label.split("/")[-1][:16]
        draw.text((bx + 10, y + my_h // 2 - 7), label,
                  fill=(120, 190, 210), font=F_Small)
        return

    if kind in ("bar", "vbar"):
        fill_w = int(my_w * 0.4) if kind == "bar" else my_w
        fill_h = my_h if kind == "bar" else int(my_h * 0.4)
        draw.rounded_rectangle([x, y, x + my_w, y + my_h], radius=7,
                               fill=(14, 26, 36, 220), outline=(255, 255, 255, 40))
        draw.rounded_rectangle([x + 2, y + 2, x + 2 + max(4, fill_w - 4),
                                y + 2 + max(4, fill_h - 4)],
                               radius=5, fill=(0, 184, 195, 220))
        return

    # ---- containers
    if kind in ("frame", "window"):
        bg = _scr_color(props.get("background"), None)
        fill = tuple(bg) + (215,) if bg else (6, 18, 28, 215)
        draw.rounded_rectangle([x, y, x + my_w, y + my_h], radius=12,
                               fill=fill, outline=(0, 184, 195, 130), width=2)
        inner_x, inner_y = x + _SCR_PAD, y + _SCR_PAD
        inner_w = max(0, my_w - _SCR_PAD * 2)
        gap = _scr_num(props.get("spacing"), _SCR_GAP)
        cy = inner_y
        for k in kids:
            kw, kh = _scr_size(k, draw)
            _scr_draw(k, img, draw, inner_x, cy, inner_w)
            cy += kh + gap
        return

    if kind == "fixed":
        for k in kids:                       # children stack, not flow
            _scr_draw(k, img, draw, x, y, avail_w)
        return

    # vbox and anything unrecognised: vertical flow
    gap = _scr_num(props.get("spacing"), _SCR_GAP) if kind == "vbox" else _SCR_GAP
    if kind == "hbox":
        cx = x
        for k in kids:
            kw, kh = _scr_size(k, draw)
            _scr_draw(k, img, draw, cx, y, kw)
            cx += kw + gap
        return

    cy = y
    for k in kids:
        kw, kh = _scr_size(k, draw)
        _scr_draw(k, img, draw, x, cy, avail_w)
        cy += kh + gap


def draw_active_screens(img: Image.Image, draw: ImageDraw.ImageDraw, state):
    """Draw every screen in ``state.active_screens`` (M22/M23).

    Returns the number of screens drawn. Sorted by `zorder` so a modal
    `confirm` lands on top of a HUD, the way Ren'Py layers them.
    """
    active = getattr(state, "active_screens", None) or {}
    if not active:
        return 0

    def zorder(item):
        props = (item[1] or {}).get("props") or {}
        return _scr_num(props.get("zorder"), 0.0)

    drawn = 0
    for name, scr in sorted(active.items(), key=zorder):
        widgets = (scr or {}).get("widgets") or []
        if not widgets:
            continue
        props = (scr or {}).get("props") or {}
        if _scr_num(props.get("modal"), 0.0) >= 1 or props.get("modal") is True:
            draw.rectangle([0, 0, W, H], fill=(0, 0, 0, 150))

        total_h = sum(_scr_size(w, draw)[1] for w in widgets) + _SCR_GAP * max(0, len(widgets) - 1)
        y = _SCR_PAD * 2
        for wdg in widgets:
            ww, wh = _scr_size(wdg, draw)
            ax = _scr_align((wdg.get("props") or {}), "xalign", 0.5)
            x = int((W - ww) * ax)
            x = max(_SCR_PAD, min(x, W - ww - _SCR_PAD))
            _scr_draw(wdg, img, draw, x, y, ww)
            y += wh + _SCR_GAP
            total_h -= 0
        drawn += 1
    return drawn



def render_state(state, event, out_path: Path | None = None, transition_alpha: float = 1.0, screen_mgr=None) -> Image.Image:
    Image, ImageDraw, ImageFont = _pil_probe()  # noqa: F811 (module-level rebinding)

    """
    Render a single frame from VNState + current waiting event.
    state: VNState (already mutated by interpreter)
    event: current Event dict or None
    """
    img = Image.new("RGBA", (W,H), (8,10,22,255))
    draw = ImageDraw.Draw(img, "RGBA")
    bg = state.scene.background
    draw_bg(img, draw, bg)
    # M13: if 3D stage present, draw it on top (hybrid)
    if state.stage:
        draw_stage(img, draw, state)
    # sprites from state.shown_actors (ordered by insert) — M10 move interpolation
    for tag, actor in state.shown_actors.items():
        col = "#c8ffc8"
        if tag in state.characters:
            col = state.characters[tag].color
        asset = actor.asset
        expr = asset[len(tag):].strip() if asset.startswith(tag) else actor.asset
        if not expr:
            expr = "neutral"
        if getattr(actor, "move_from", None) and getattr(actor, "move_to", None) and getattr(actor, "move_t0", None):
            import time as _tt
            now = _tt.time()
            dur = getattr(actor, "move_duration", 0.5) or 0.5
            t_raw = (now - actor.move_t0) / dur if dur>0 else 1.0
            t_raw = max(0.0, min(1.0, t_raw))
            if t_raw < 1.0:
                try:
                    from ..atl.easing import get_easing as _ge
                    ease_fn = _ge(getattr(actor, "move_easing", "ease") or "ease")
                except:
                    ease_fn = lambda x: x
                t = ease_fn(t_raw)
                pos_world = {"left": -3, "center": 0, "right": 3, "far_left": -5, "far_right": 5}
                x0 = pos_world.get(actor.move_from, 0)
                x1 = pos_world.get(actor.move_to, 0)
                x_world = x0 + (x1-x0)*t
                x_screen = int(640 + x_world*106)
                if t_raw > 0.95:
                    pass
                elif t_raw < 0.05:
                    pass
                else:
                    draw_sprite_at_x(img, draw, tag, expr, x_screen, col, progress=t_raw)
                    continue
        try:
            draw_sprite(img, draw, tag, expr, actor.position, col)
        except:
            draw_sprite(img, draw, tag, expr, actor.position, col)
    # UI: dialogue or menu
    if event and event.get("type") == "menu":
        draw_menu(img, draw, event.get("caption"), [c["text"] for c in event.get("choices",[])])
    elif event and event.get("type") == "say":
        speaker = event.get("who_name") or (state.get_character_name(event["who"]) if event.get("who") else None)
        # speaker_color = the resolved world-UI payload key; color = the raw
        # interpreter event key — accept both so either pipeline works
        col = (event.get("speaker_color") or event.get("color")
               or (state.characters[event["who"]].color
                   if event.get("who") in state.characters else None))
        draw_dialogue(img, draw, speaker, col, event.get("text",""))
    elif event and event.get("type") == "pause":
        pass
    else:
        if state.history:
            last = state.history[-1]
            who = last.get("who_name")
            col = None
            if last.get("who") in state.characters:
                col = state.characters[last["who"]].color
            draw_dialogue(img, draw, who, col, last.get("text",""))
    # top badges — avoid overlap: scene at (16,16), zoom/cam at second row y=52
    if state.stage and (bg is None or bg == "black"):
        bg_label = f"STAGE: {state.stage}"
    elif state.stage and bg:
        bg_label = f"{bg} + {state.stage}"
        if len(bg_label) > 28:
            bg_label = bg_label[:25] + "…"
    else:
        bg_label = f"SCENE: {bg}"
    tw = draw.textlength(bg_label, font=F_Small)
    draw.rounded_rectangle([16,16,16+tw+28,38], radius=8, fill=(0,0,0,120), outline=(255,255,255,18))
    draw.ellipse([22,22,30,30], fill=(0,184,195))
    draw.text((36,20), bg_label, fill=(180,185,195), font=F_Small)
    tw2 = draw.textlength("UPVN · UPBGE 0.50", font=F_Small)
    draw.rounded_rectangle([W-16-tw2-28,16,W-16,38], radius=8, fill=(6,22,30,190), outline=(0,184,195,80))
    draw.text((W-16-tw2-14,20), "UPVN · UPBGE 0.50", fill=(0,214,245), font=F_Small)
    # camera zoom + preset at second row to avoid overlap
    cam_zoom = None
    try:
        if state.camera:
            import time as _tt
            now = _tt.time()
            c = state.camera
            if "_zoom_t0" in c:
                dur = c.get("_zoom_dur",1.0)
                t_raw = (now - c["_zoom_t0"])/dur if dur>0 else 1.0
                t_raw = max(0.0, min(1.0, t_raw))
                if t_raw < 1.0:
                    from ..atl.easing import get_easing as _ge2
                    ease = _ge2(c.get("_zoom_ease","ease"))
                    t = ease(t_raw)
                    cam_zoom = c.get("_zoom_from",1.0) + (c.get("_zoom_to",1.0)-c.get("_zoom_from",1.0))*t
                else:
                    cam_zoom = c.get("_zoom_to", c.get("zoom",1.0))
            elif "zoom" in c:
                cam_zoom = c["zoom"]
    except: pass
    badge_x = 16
    badge_y = 52
    if cam_zoom is not None:
        txtz = f"ZOOM {cam_zoom:.2f}x"
        twz = draw.textlength(txtz, font=F_Small)
        draw.rounded_rectangle([badge_x, badge_y, badge_x+twz+28, badge_y+22], radius=8, fill=(0,25,35,200), outline=(0,184,195,70))
        draw.text((badge_x+14, badge_y+4), txtz, fill=(0,214,245), font=F_Small)
        badge_x += twz + 36
        if cam_zoom and cam_zoom != 1.0:
            draw.rounded_rectangle([0,0,W-1,H-1], radius=0, outline=(0,184,195, int(30*abs(cam_zoom-1))), width=2)
    if state.camera.get("preset"):
        txt2 = f'CAM {state.camera["preset"]}'
        tw2p = draw.textlength(txt2, font=F_Small)
        draw.rounded_rectangle([badge_x, badge_y, badge_x+tw2p+28, badge_y+22], radius=8, fill=(0,25,35,200), outline=(0,184,195,70))
        draw.text((badge_x+14, badge_y+4), txt2, fill=(0,214,245), font=F_Small)
        badge_x += tw2p + 12
    if state.stage:
        # stage badge if not already in scene label
        if bg and bg != "black" and bg is not None:
            txts = f"3D: {state.stage}"
            tws = draw.textlength(txts, font=F_Small)
            draw.rounded_rectangle([badge_x, badge_y, badge_x+tws+28, badge_y+22], radius=8, fill=(0,25,35,200), outline=(0,184,195,70))
            draw.text((badge_x+14, badge_y+4), txts, fill=(0,214,245), font=F_Small)
    # M09 screens — overlay vs modal (arbitrary slots pagination)
    if screen_mgr is not None:
        if screen_mgr.is_overlay_visible("quick_menu"):
            draw_quick_menu_overlay(img, draw, state)
        if screen_mgr.is_overlay_visible("history"):
            draw_history_overlay(img, draw, state)
        modal = screen_mgr.get_modal()
        if modal:
            if modal.name == "save":
                pg = getattr(modal, "page", 0)
                ps = getattr(modal, "page_size", 6)
                draw_save_overlay(img, draw, state, mode="SAVE", save_manager=getattr(modal, "save_manager", None), page=pg, page_size=ps)
            elif modal.name == "load":
                pg = getattr(modal, "page", 0)
                ps = getattr(modal, "page_size", 6)
                draw_save_overlay(img, draw, state, mode="LOAD", save_manager=getattr(modal, "save_manager", None), page=pg, page_size=ps)
            elif modal.name == "main_menu":
                draw_main_menu_overlay(img, draw, state)
            elif modal.name == "preferences":
                draw_main_menu_overlay(img, draw, state)
    # M23: screens from the drop-in tier (`show screen` / `call screen`).
    # Drawn after the built-in overlays so a game's own UI sits on top.
    try:
        draw_active_screens(img, draw, state)
    except Exception:
        pass  # a frame must never fail because a screen could not be laid out
    # quick menu hint when auto/skip active (always)
    if state.skip or state.auto:
        txt = "SKIP ▶" if state.skip else "AUTO ▶"
        draw.rounded_rectangle([W-110, 50, W-20, 74], radius=8, fill=(0,184,195,200), outline=(0,0,0,30))
        draw.text((W-95, 56), txt, fill=(0,10,20), font=F_Small)
    if transition_alpha < 1.0:
        ov = Image.new("RGBA", (W,H), (0,0,0,int(255*(1-transition_alpha))))
        img.alpha_composite(ov,(0,0))
    img = img.convert("RGB")
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, "PNG")
    return img

def render_trace(script_path: str | Path, choices: list[int] | None = None, out_dir: str | Path = "screenshots/trace"):
    """
    Convenience: run headless and dump PNG per waiting event.
    Returns list of Paths.
    """
    from upvn.engine.core.vn_controller import VNController
    from pathlib import Path
    ctrl = VNController(script_path=str(script_path))
    ctrl.load()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    step = 0
    ev = ctrl.current_event
    if ev:
        p = out_dir / f"step_{step:02d}_{ev.get('type')}.png"
        render_state(ctrl.state, ev, p)
        paths.append(p)
        step+=1
    from upvn.engine.core.vn_interpreter import VNInterpreter
    import copy
    script_dict = ctrl.script_dict
    from upvn.engine.core.vn_state import VNState
    state = VNState()
    interp = VNInterpreter(copy.deepcopy(script_dict), state)
    gen = interp.run()
    choices = choices or []
    cidx=0
    try:
        event = next(gen)
        while True:
            if event.get("wait"):
                p = out_dir / f"step_{step:02d}_{event.get('type')}.png"
                render_state(interp.state, event, p)
                paths.append(p)
                step+=1
            if event.get("type")=="menu" and event.get("wait"):
                pick = choices[cidx] if cidx < len(choices) else 0
                cidx+=1
                event = gen.send(pick)
            elif event.get("wait"):
                event = gen.send(None)
            else:
                event = next(gen)
    except StopIteration:
        pass
    return paths
