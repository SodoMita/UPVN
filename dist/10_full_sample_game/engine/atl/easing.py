"""
UPVN ATL-lite easing — subset of Ren'Py ATL warpers
https://renpy.org/doc/html/atl.html#warpers
"""
import math

def ease_linear(t: float) -> float:
    return t

def ease_in(t: float) -> float:
    return t*t*t

def ease_out(t: float) -> float:
    return 1 - pow(1-t, 3)

def ease_in_out(t: float) -> float:
    return 4*t*t*t if t < 0.5 else 1 - pow(-2*t+2, 3)/2

def ease(t: float) -> float:  # Ren'Py default ease is ease_in_out-ish cubic
    return ease_in_out(t)

EASINGS = {
    "linear": ease_linear,
    "ease": ease,
    "easein": ease_in,
    "ease_in": ease_in,
    "easeout": ease_out,
    "ease_out": ease_out,
    "easeinout": ease_in_out,
    "ease_in_out": ease_in_out,
    "move": ease,  # alias
}

def get_easing(name: str):
    return EASINGS.get(name.lower(), ease)

def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
