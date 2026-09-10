"""
Sprite Renderer — 2D planes for characters (Tier2+)
Hybrid support: sprites can coexist with 3D stage (Option C).

UPBGE: planes at POSITIONS (world coords), colour tint via object.color on
       white emission materials — NO image textures (desktop-friendly, works on
       llvmpipe and lavapipe software GL without bge.texture).
Headless: state.shown_actors is source of truth; renderer just validates.

Accepted positions (SCRIPT_LANGUAGE_SPEC): left/center/right/far_left/far_right
and optional 'at' offset — e.g. show eileen happy at center
"""
from __future__ import annotations
try:
    import bge
    HAS_BGE = True
except ImportError:
    HAS_BGE = False

from ..core.vn_state import VNState
from .contract import (POSITIONS, SPRITE_MATERIAL, SPRITE_FALLBACK_TAG,
                       SPRITE_TAG_PREFIX, BG_PLANE, sprite_color_for)
import time

# transition durations (seconds)
TRANS_DUR = {"dissolve": 0.4, "fade": 0.5, None: 0.0}

class SpriteRenderer:
    def __init__(self, state: VNState):
        self.state = state
        self.planes: dict[str, dict] = {}
        if HAS_BGE:
            try:
                sc = bge.logic.getCurrentScene()  # type: ignore
                for ob in sc.objects:
                    if str(ob.name).startswith(SPRITE_TAG_PREFIX):
                        ob.visible = False
            except Exception:
                pass

    def apply_event(self, event: dict):
        t = event.get("type")
        if t == "show":
            self.show(event["tag"], event["asset"], event.get("position"), event.get("transition"))
        elif t == "hide":
            self.hide(event["tag"], event.get("transition"))

    def show(self, tag: str, asset: str, position: str | None, transition: str | None):
        pos = position or "center"
        if pos not in POSITIONS:
            pos = "center"
        if HAS_BGE:
            self._bge_show(tag, asset, pos, transition)
        else:
            self.planes[tag] = {"asset": asset, "position": pos, "transition": transition, "t0": time.time()}

    def hide(self, tag: str, transition: str | None):
        if HAS_BGE:
            self._bge_hide(tag, transition)
        self.planes.pop(tag, None)

    # ---------------- BGE implementation (no textures)
    def _bge_show(self, tag: str, asset: str, position: str, transition: str | None):
        try:
            scene = bge.logic.getCurrentScene()  # type: ignore
            plane_name = f"{SPRITE_TAG_PREFIX}{position}"
            plane = (scene.objects.get(plane_name)
                     or scene.objects.get(f"{SPRITE_TAG_PREFIX}{tag}")
                     or scene.objects.get(SPRITE_FALLBACK_TAG))
            if not plane:
                tmpl = scene.objects.get(BG_PLANE)
                if tmpl:
                    plane = scene.addObject(tmpl, tmpl)
                    plane.name = plane_name
                else:
                    return
            plane.worldPosition = POSITIONS[position]  # type: ignore
            plane.visible = True
            # colour from palette / character registry
            ch_color = None
            try:
                ch = self.state.characters.get(tag)
                if ch:
                    ch_color = ch.color
            except Exception:
                pass
            col = sprite_color_for(tag, asset, ch_color)
            # store for debug
            try:
                plane["upvn_tag"] = tag
                plane["upvn_asset"] = asset
                plane["upvn_color"] = col
            except Exception:
                pass
            # apply colour with alpha tween for dissolve/fade
            if transition in ("dissolve", "fade"):
                try:
                    plane.color = (col[0], col[1], col[2], 0.0)
                except Exception:
                    pass
                self.planes[tag] = {"obj": plane, "asset": asset, "position": position,
                                    "t0": time.time(), "transition": transition, "target_color": col}
            else:
                try:
                    plane.color = col
                except Exception:
                    pass
                self.planes[tag] = {"obj": plane, "asset": asset, "position": position,
                                    "target_color": col, "t0": time.time(), "transition": None}
        except Exception as e:
            print(f"[SpriteRenderer] show {tag} {asset} failed: {e}")

    def _bge_hide(self, tag: str, transition: str | None):
        try:
            info = self.planes.get(tag)
            if not info:
                return
            obj = info.get("obj")
            if obj:
                if transition in ("dissolve","fade"):
                    obj["upvn_fade_out"] = True
                    obj["upvn_fade_t0"] = time.time()
                    obj["upvn_fade_dur"] = TRANS_DUR.get(transition, 0.4)
                else:
                    obj.visible = False
        except Exception as e:
            print(f"[SpriteRenderer] hide {tag} failed: {e}")

    def get_interpolated_position(self, tag: str, now: float | None = None):
        import time as _t
        actor = self.state.shown_actors.get(tag)
        if not actor:
            return None
        if now is None:
            now = _t.time()
        if actor.move_from and actor.move_to and actor.move_t0:
            dur = actor.move_duration or 0.5
            t_raw = (now - actor.move_t0) / dur if dur>0 else 1.0
            t_raw = max(0.0, min(1.0, t_raw))
            if t_raw >= 1.0:
                return POSITIONS.get(actor.position, POSITIONS["center"])
            try:
                from ..atl.easing import get_easing
                ease_fn = get_easing(actor.move_easing or "ease")
            except:
                ease_fn = lambda x: x
            t = ease_fn(t_raw)
            p0 = POSITIONS.get(actor.move_from, POSITIONS["center"])
            p1 = POSITIONS.get(actor.move_to, POSITIONS["center"])
            x = p0[0] + (p1[0]-p0[0])*t
            y = p0[1] + (p1[1]-p0[1])*t
            z = p0[2] + (p1[2]-p0[2])*t
            return (x,y,z)
        return POSITIONS.get(actor.position, POSITIONS["center"])

    def is_move_done(self, tag: str, now: float | None = None) -> bool:
        import time as _t
        actor = self.state.shown_actors.get(tag)
        if not actor or not actor.move_t0:
            return True
        if now is None:
            now = _t.time()
        return (now - actor.move_t0) >= (actor.move_duration or 0.5)

    def update(self, dt: float):
        if not HAS_BGE:
            return
        now = time.time()
        for tag, info in list(self.planes.items()):
            obj = info.get("obj")
            if not obj:
                continue
            trans = info.get("transition")
            t0 = info.get("t0")
            target = info.get("target_color") or (1,1,1,1)
            if trans in ("dissolve","fade") and t0:
                dur = TRANS_DUR.get(trans, 0.4)
                t = min(1.0, (now - t0)/dur) if dur>0 else 1.0
                try:
                    # fade in: alpha 0->1, keep RGB at target
                    obj.color = (target[0], target[1], target[2], t)
                except Exception:
                    pass
                if t >= 1.0:
                    info["transition"] = None
        for tag, actor in list(self.state.shown_actors.items()):
            if actor.move_from and actor.move_to and actor.move_t0:
                dur = actor.move_duration or 0.5
                t_raw = (now - actor.move_t0) / dur if dur>0 else 1.0
                t_raw = max(0.0, min(1.0, t_raw))
                if t_raw >= 1.0:
                    try:
                        info = self.planes.get(tag)
                        if info and info.get("obj"):
                            info["obj"].worldPosition = POSITIONS.get(actor.move_to, POSITIONS["center"])
                    except: pass
                    actor.move_from = None
                    actor.move_t0 = None
                    continue
                try:
                    from ..atl.easing import get_easing
                    ease_fn = get_easing(actor.move_easing or "ease")
                except:
                    ease_fn = lambda x: x
                t = ease_fn(t_raw)
                p0 = POSITIONS.get(actor.move_from, POSITIONS["center"])
                p1 = POSITIONS.get(actor.move_to, POSITIONS["center"])
                x = p0[0] + (p1[0]-p0[0])*t
                y = p0[1] + (p1[1]-p0[1])*t
                z = p0[2] + (p1[2]-p0[2])*t
                info = self.planes.get(tag)
                if info and info.get("obj"):
                    try:
                        info["obj"].worldPosition = (x,y,z)
                    except: pass

    def positions_ok(self) -> bool:
        for tag, actor in self.state.shown_actors.items():
            if actor.position not in POSITIONS and actor.position not in ("left","center","right","far_left","far_right"):
                return False
        return True
