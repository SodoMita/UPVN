#!/usr/bin/env python3
"""Measure what the player actually drew: bounding boxes of the light text
pixels inside the dialogue band, so "dialogue text is tiny/missing" can be
diagnosed numerically instead of by eye. Usage: tools/probe_shot.py shot.png
"""
import sys
from PIL import Image


def boxes(path, band_rows):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    # text is near-white over the navy band: look for pixels much lighter than
    # the band colour, in the band's rows
    out = {}
    for name, (y0, y1) in band_rows.items():
        xs, ys = [], []
        for y in range(max(0, y0), min(h, y1)):
            for x in range(0, w, 2):
                r, g, b = px[x, y]
                if r > 170 and g > 170 and b > 170:
                    xs.append(x)
                    ys.append(y)
        if xs:
            out[name] = (min(xs), min(ys), max(xs), max(ys),
                         max(ys) - min(ys) + 1, len(xs))
        else:
            out[name] = None
    return out, (w, h)


if __name__ == "__main__":
    p = sys.argv[1]
    im = Image.open(p)
    w, h = im.size
    # dialogue band occupies roughly the bottom 25% of the frame
    res, size = boxes(p, {
        "dialogue_band": (int(h * 0.70), int(h * 0.99)),
        "upper_screen": (int(h * 0.05), int(h * 0.55)),
        "mid_screen": (int(h * 0.10), int(h * 0.60)),
    })
    print(f"{p} size={size}")
    for k, v in res.items():
        print(f"  {k}: {v}")
