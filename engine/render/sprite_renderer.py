"""
Sprite Renderer — 2D planes for characters (Tier2+)
Hybrid support: sprites can coexist with 3D stage (Option C).

UPBGE: tries bge.texture (real PNG) first; falls back to palette colour
       (object.color) when no file — textures essential but palette keeps
       desktop usable without assets, works on llvmpipe/lavapipe.

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
                       SPRITE_TAG_PREFIX, BG_PLANE, ASSET_SPRITES, sprite_color_for)
import time

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

    def _bge_show(self, tag: str, asset: str, position: str, transition: str | None):
        try:
            import bge.logic as logic
            scene = logic.getCurrentScene()  # type: ignore
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
            # try texture first
            if self._try_texture(plane, tag, asset, position, transition):
                return
            # fallback to palette colour
            self._apply_color(plane, tag, asset, position, transition)
        except Exception as e:
            print(f"[SpriteRenderer] show {tag} {asset} failed: {e}")

    def _try_texture(self, plane, tag: str, asset: str, position: str, transition: str | None) -> bool:
        try:
            import bge.texture as vt
            import os, bge
            stem = asset.replace(" ", "_")
            slash = asset.replace(" ", "/")
            last = asset.split()[-1] if " " in asset else "neutral"
            candidates = [
                bge.logic.expandPath(f"//{ASSET_SPRITES}/{slash}.png"),
                bge.logic.expandPath(f"//{ASSET_SPRITES}/{stem}.png"),
                bge.logic.expandPath(f"//{ASSET_SPRITES}/{tag}.png"),
                bge.logic.expandPath(f"//game/{ASSET_SPRITES}/{slash}.png"),
                bge.logic.expandPath(f"//game/{ASSET_SPRITES}/{stem}.png"),
                bge.logic.expandPath(f"//assets/characters/{tag}/{last}.png"),
                bge.logic.expandPath(f"//assets/sprites/{tag}.png"),
            ]
            for ext in (".png", ".jpg", ".webp"):
                candidates.append(bge.logic.expandPath(f"//{ASSET_SPRITES}/{stem}{ext}"))
            tex_path = None
            for p in candidates:
                if os.path.exists(p):
                    tex_path = p
                    break
            if not tex_path:
                return False
            try:
                mat_id = vt.materialID(plane, SPRITE_MATERIAL)
            except Exception:
                mat_id = -1
            if mat_id < 0:
                mat_id = 0
            img = vt.ImageFFmpeg(tex_path)
            img.scale = False
            tex = vt.Texture(plane, mat_id)
            tex.source = img
            # store
            try:
                plane["upvn_tag"] = tag
                plane["upvn_asset"] = asset
                plane["upvn_tex_path"] = tex_path
                plane.color = (1,1,1,1)
            except Exception:
                pass
            self.planes[tag] = {"obj": plane, "tex": tex, "asset": asset, "position": position, "t0": time.time(), "transition": transition, "target_color": (1,1,1,1)}
            if transition in ("dissolve", "fade"):
                try:
                    plane.color = (1,1,1,0.0)
                except Exception:
                    pass
            return True
        except Exception as e:
            # don't spam, but log once
            try:
                import bge
                if not getattr(bge.logic, "_upvn_sprite_tex_err", False):
                    bge.logic._upvn_sprite_tex_err = True
                    print(f"[SpriteRenderer] texture bind failed for {asset}: {e}")
            except Exception:
                pass
            return False

    def _apply_color(self, plane, tag: str, asset: str, position: str, transition: str | None):
        try:
            ch_color = None
            try:
                ch = self.state.characters.get(tag)
                if ch:
                    ch_color = ch.color
            except Exception:
                pass
            col = sprite_color_for(tag, asset, ch_color)
            try:
                plane["upvn_tag"] = tag
                plane["upvn_asset"] = asset
                plane["upvn_color"] = col
            except Exception:
                pass
            if transition in ("dissolve", "fade"):
                try:
                    plane.color = (col[0], col[1], col[2], 0.0)
                except Exception:
                    pass
                self.planes[tag] = {"obj": plane, "asset": asset, "position": position, "t0": time.time(), "transition": transition, "target_color": col}
            else:
                try:
                    plane.color = col
                except Exception:
                    pass
                self.planes[tag] = {"obj": plane, "asset": asset, "position": position, "target_color": col, "t0": time.time(), "transition": None}
        except Exception as e:
            print(f"[SpriteRenderer] color fallback failed {tag} {asset}: {e}")

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
            # only do alpha fade for colour fallback; texture path already handled via plane.color
            if trans in ("dissolve","fade") and t0:
                dur = TRANS_DUR.get(trans, 0.4)
                t = min(1.0, (now - t0)/dur) if dur>0 else 1.0
                try:
                    # if this was a texture, keep white; if colour, use target rgb
                    if target == (1,1,1,1):
                        obj.color = (1,1,1,t)
                    else:
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
