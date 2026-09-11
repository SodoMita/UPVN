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

# ---------------------------------------------------------------- bg
def draw_bg(img: Image.Image, draw: ImageDraw.ImageDraw, scene: str | None):
    s = scene or "black"
    if s == "bg classroom":
        for y in range(H):
            t=y/H
            r=int(235 - 15*t)
            g=int(225 - 20*t)
            b=int(195 - 30*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        for wx in [70, 460, 850]:
            draw.rounded_rectangle([wx, 60, wx+320, 320], radius=6, fill=(135,175,215), outline=(90,110,140), width=3)
            draw.line([(wx+160,60),(wx+160,320)], fill=(90,110,140), width=3)
            draw.line([(wx,190),(wx+320,190)], fill=(90,110,140), width=3)
            draw.rounded_rectangle([wx+8, 68, wx+312, 182], radius=4, fill=(200,225,255,90))
        draw.rectangle([0,520,W,524], fill=(120,100,80))
        overlay = Image.new("RGBA", (W,H), (0,0,0,0))
        od = ImageDraw.Draw(overlay)
        for i in range(120):
            a = int(35*(1-i/120))
            od.rectangle([i,i,W-i-1,H-i-1], outline=(0,0,0,a))
        img.alpha_composite(overlay, (0,0))
    elif s == "bg lecturehall":
        for y in range(H):
            t=y/H
            r=int(42 - 12*t); g=int(52 - 10*t); b=int(84 - 14*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        for x in [220, 640, 1060]:
            draw.rectangle([x-2, 0, x+2, 360], fill=(255,240,180,10))
        draw.rectangle([0,480,W,540], fill=(28,32,48))
        draw.rectangle([W//2-140,450,W//2+140,480], fill=(42,48,70), outline=(65,72,95), width=1)
        draw.ellipse([W//2-180,520,W//2+180,560], fill=(0,0,0,35))
    elif s == "bg meadow":
        for y in range(H):
            t=y/H
            if t<0.52:
                tt=t/0.52
                r=int(135+60*tt); g=int(185+40*tt); b=int(235-20*tt)
            else:
                tt=(t-0.52)/0.48
                r=int(75-20*tt); g=int(135-15*tt); b=int(75-10*tt)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        draw.ellipse([-300,380,800,620], fill=(85,145,85))
        draw.ellipse([500,400,1450,650], fill=(70,125,70))
        for cx,cy in [(260,110),(620,90),(980,120)]:
            draw.ellipse([cx-90,cy-30,cx+90,cy+30], fill=(255,255,255,95))
            draw.ellipse([cx-60,cy-45,cx+60,cy+10], fill=(255,255,255,85))
    elif s == "bg uni":
        for y in range(H):
            t=y/H
            r=int(60+30*t); g=int(95+35*t); b=int(145+20*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        draw.rectangle([0,360,W,560], fill=(35,45,65))
        for x in range(60,W,170):
            draw.rectangle([x,300,x+110,360], fill=(50,60,80), outline=(70,80,100), width=2)
            for wy in [315,335]:
                draw.rectangle([x+12,wy,x+98,wy+14], fill=(255,235,160))
        for x in [120,340,760,1020]:
            draw.ellipse([x-35,340,x+35,385], fill=(45,90,45))
            draw.rectangle([x-6,385,x+6,410], fill=(70,50,30))
    elif s == "bg hallway":
        for y in range(H):
            t=y/H
            r=int(115-35*t); g=int(95-25*t); b=int(65-15*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        draw.polygon([(0,0),(340,0),(260,H),(0,H)], fill=(125,105,75))
        draw.polygon([(W,0),(W-340,0),(W-260,H),(W,H)], fill=(115,95,68))
        for y in range(380,H,70):
            w=int((y-380)*0.9+90)
            draw.polygon([(W//2-w//2,y),(W//2+w//2,y),(W//2+w//2+40,y+70),(W//2-w//2-40,y+70)], outline=(90,75,55), width=1, fill=(135,115,85) if (y//70)%2==0 else (125,105,78))
        for x in [30,170,1010,1150]:
            draw.rectangle([x,120,x+100,380], fill=(60,85,105), outline=(40,60,80), width=2)
            draw.ellipse([x+70,240,x+78,248], fill=(200,200,180))
    elif s == "black" or s is None:
        for y in range(H):
            draw.line([(0,y),(W,y)], fill=(6,8,14))
        overlay=Image.new("RGBA",(W,H),(0,0,0,0))
        od=ImageDraw.Draw(overlay)
        od.ellipse([W//2-400,H//2-300,W//2+400,H//2+300], fill=(20,30,55,45))
        img.alpha_composite(overlay,(0,0))
    else:
        for y in range(H):
            t=y/H
            r=int(18+10*t); g=int(22+12*t); b=int(38+15*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))

def draw_stage(img: Image.Image, draw: ImageDraw.ImageDraw, state):
    """M13 hybrid 3D stage — perspective floor + markers for show3d"""
    stage = state.stage or "unknown_stage"
    # if no scene bg, fill top with stage environment instead of black
    # we already drew bg (black) earlier; overwrite top 0-320 with stage sky
    # check state's scene background
    bg = state.scene.background if hasattr(state, "scene") else None
    if bg is None or bg == "black":
        for y in range(0, 320):
            t = y/320
            r=int(55 + 20*t); g=int(65 + 15*t); b=int(85 + 10*t)
            draw.line([(0,y),(W,y)], fill=(r,g,b))
        # also draw simple backdrop wall
        draw.rectangle([W//2 - 300, 60, W//2 + 300, 320], fill=(45,55,75), outline=(70,80,100), width=1)
        for wx in [W//2-280, W//2-90, W//2+110]:
            draw.rectangle([wx, 80, wx+160, 300], fill=(70,85,110), outline=(90,110,140), width=1)
    # floor
    for y in range(320, H-110):
        t = (y-320)/(H-110-320)
        r=int(38 - 10*t); g=int(45 - 8*t); b=int(60 - 10*t)
        draw.line([(0,y),(W,y)], fill=(r,g,b))
    for i in range(-2, 3):
        x_center = W//2 + i*140
        draw.line([(x_center, 320), (W//2 + i*40, H-110)], fill=(70,80,95,120), width=1)
    for y in [360, 400, 450, 520]:
        draw.line([(220,y),(W-220,y)], fill=(70,80,95,80), width=1)
    # richer classroom_3d desks when stage is classroom_3d (polish v0.5)
    if "classroom" in stage:
        # 3 rows x 3 cols of desks (wooden) + blackboard at front
        # blackboard
        draw.rounded_rectangle([W//2-180, 330, W//2+180, 360], radius=4, fill=(28,55,32), outline=(90,110,90), width=1)
        draw.text((W//2-42, 338), "BOARD", fill=(180,220,180), font=F_Small)
        # teacher desk
        draw.rounded_rectangle([W//2-90, 368, W//2+90, 390], radius=6, fill=(110,85,60), outline=(80,60,40), width=1)
        draw.line([(W//2, 368), (W//2, 390)], fill=(80,60,40), width=1)
        # student desks
        for row, y in enumerate([420, 470, 520]):
            for col, x in enumerate([W//2-220, W//2-70, W//2+80, W//2+230]):
                # skip center aisle for some
                if col == 2 and row == 1:
                    continue
                # desk top
                draw.rounded_rectangle([x-48, y-12, x+48, y+12], radius=5, fill=(125,95,65), outline=(90,70,45), width=1)
                draw.line([(x, y-12), (x, y+12)], fill=(90,70,45), width=1)
                # chair
                draw.rounded_rectangle([x-22, y+18, x+22, y+32], radius=4, fill=(85,75,65), outline=(60,55,45), width=1)
                # shadow
                draw.ellipse([x-30, y+32, x+30, y+38], fill=(0,0,0,18))
    txt = f"3D STAGE: {stage}"
    tw = draw.textlength(txt, font=F_Small)
    draw.rounded_rectangle([W//2 - tw//2 - 14, 340, W//2 + tw//2 +14, 360], radius=8, fill=(0,25,35,220), outline=(0,184,195,80))
    draw.text((W//2 - tw//2, 344), txt, fill=(0,214,245), font=F_Small)
    markers = {"marker_eileen": W//2 - 160, "marker_sylvie": W//2 + 160, "center": W//2, "marker_center": W//2}
    for asset, info in state.stage_objects.items():
        marker = info.get("marker") or "center"
        x = markers.get(marker, W//2)
        y_base = H-110
        draw.ellipse([x-45, y_base-90, x+45, y_base-10], fill=(0,0,0,25))
        draw.rounded_rectangle([x-30, 400, x+30, y_base-20], radius=8, fill=hex_rgb("#8ec8ff"), outline=(255,255,255,40))
        draw.ellipse([x-22, 380, x+22, 410], fill=(255,225,190), outline=(0,0,0,20))
        lab = f"show3d {asset} @ {marker} [{info.get('anim','idle')}]"
        tw2 = draw.textlength(lab, font=F_Small)
        draw.rounded_rectangle([x - tw2//2 -8, y_base+4, x+ tw2//2+8, y_base+22], radius=6, fill=(12,16,28,200), outline=(100,180,220,60))
        draw.text((x - tw2//2, y_base+8), lab, fill=(200,225,255), font=F_Small)

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
    box_y0=538; box_h=H-box_y0
    box=Image.new("RGBA",(W,box_h),(0,0,0,0))
    bd=ImageDraw.Draw(box,"RGBA")
    bd.rounded_rectangle([22,14,W-22,box_h-14], radius=16, fill=(10,14,28,235), outline=(38,55,95,255), width=1)
    bd.line([(34,20),(W-34,20)], fill=(0,184,195,55), width=1)
    bd.line([(34,box_h-18),(W-34,box_h-18)], fill=(255,255,255,10), width=1)
    img.alpha_composite(box,(0,box_y0))
    if speaker:
        tw=draw.textlength(speaker, font=F_Name)
        nx,ny=58, box_y0+4
        draw.rounded_rectangle([nx,ny,nx+tw+28,ny+26], radius=13, fill=(18,42,48,255), outline=(0,184,195,110), width=1)
        draw.ellipse([nx+10,ny+8,nx+20,ny+18], fill=hex_rgb(speaker_color or "#7eeaff"))
        draw.text((nx+28,ny+5), speaker, fill=(230,245,255), font=F_Name)
        text_y=box_y0+44
    else:
        text_y=box_y0+30
    if text:
        clean=re.sub(r"\{[^}]+?\}","",text)
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
            draw.text((74,text_y), line, fill=(232,238,247), font=F_Text); text_y+=30
        draw.polygon([(W-70,H-30),(W-58,H-22),(W-46,H-30)], fill=(0,184,195))
        draw.ellipse([W//2-4,H-10,W//2+4,H-6], fill=(0,184,195,180))
    draw.text((W-188,H-20), "click / space →", fill=(110,125,155), font=F_Small)

def draw_menu(img: Image.Image, draw: ImageDraw.ImageDraw, caption, choices):
    ov=Image.new("RGBA",(W,H),(6,10,22,150))
    img.alpha_composite(ov,(0,0))
    vig=Image.new("RGBA",(W,H),(0,0,0,0))
    vd=ImageDraw.Draw(vig)
    for i in range(90):
        a=int(18*(1-i/90))
        vd.rounded_rectangle([i,i,W-i-1,H-i-1], radius=18, outline=(0,0,0,a))
    img.alpha_composite(vig,(0,0))
    y_start=230
    if caption:
        tw=draw.textlength(caption, font=F_Text)
        bw=tw+48; x0=W//2-bw//2
        draw.rounded_rectangle([x0,y_start-18,x0+bw,y_start+34], radius=14, fill=(16,24,42,240), outline=(0,184,195,90), width=1)
        draw.text((W//2-tw//2,y_start-4), caption, fill=(200,225,235), font=F_Text)
        y_start+=68
    for i,ch in enumerate(choices):
        bw,bh=460,58
        x0=W//2-bw//2; y0=y_start+i*(bh+14); x1,y1=x0+bw,y0+bh
        draw.rounded_rectangle([x0,y0,x1,y1], radius=14, fill=(19,33,60,250), outline=(58,85,135,255), width=1)
        draw.rounded_rectangle([x0,y0,x0+8,y1], radius=7, fill=(0,184,195))
        draw.ellipse([x0+18,y0+18,x0+40,y0+40], fill=(0,184,195,25), outline=(0,184,195,70))
        draw.text((x0+24,y0+20), str(i+1), fill=(0,184,195), font=F_Small)
        tw=draw.textlength(ch, font=F_Menu)
        draw.text((W//2-tw//2+4,y0+16), ch, fill=(230,238,255), font=F_Menu)
        draw.line([(x0+12,y0+2),(x1-12,y0+2)], fill=(255,255,255,12), width=1)

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
        col = event.get("color") or (state.characters[event["who"]].color if event.get("who") in state.characters else None)
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
