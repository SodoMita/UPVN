"""
Sprite Renderer — 2D planes for characters (Tier2+)
Hybrid support: sprites can coexist with 3D stage (Option C).

UPBGE: planes at POSITIONS (world coords), texture swap via bge.texture,
       alpha tween for dissolve, move interpolation for M10.
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
                       SPRITE_TAG_PREFIX, BG_PLANE, ASSET_SPRITES,
                       image_mode_from, sprite_color, SPRITE_FALLBACK_COLOR,
                       apply_object_color)
import time

# Relative search prefixes for sprite images, relative to the .blend
# (repo layout <repo>/blend + <repo>/assets, packaged <pkg>/blend + <pkg>/assets).
SPRITE_PATH_PREFIXES = ("//", "//game/", "//../", "//../game/",
                        "//../../", "//../../game/")

def _dbg(msg: str):
    print(f"[SpriteRenderer] {msg}")

# transition durations (seconds)
TRANS_DUR = {"dissolve": 0.4, "fade": 0.5, None: 0.0}

class SpriteRenderer:
    def __init__(self, state: VNState):
        self.state = state
        # tag -> {"obj": bge object, "tex": Texture, "t0": start time, "transition": name}
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
            # allow custom marker name for hybrid — treat unknown as center but log
            pos = "center"
        # state already updated by interpreter (VNState.shown_actors[tag]=...)
        if HAS_BGE:
            self._bge_show(tag, asset, pos, transition)
        else:
            # headless validation: ensure no duplicate tag with different asset without replacement
            # interpreter already replaces; we just track
            self.planes[tag] = {"asset": asset, "position": pos, "transition": transition, "t0": time.time(), "tint": sprite_color(tag)}

    def hide(self, tag: str, transition: str | None):
        if HAS_BGE:
            self._bge_hide(tag, transition)
        # remove from tracking
        self.planes.pop(tag, None)

    # ---------------- BGE implementation
    def _bge_show(self, tag: str, asset: str, position: str, transition: str | None):
        try:
            scene = bge.logic.getCurrentScene()  # type: ignore
            # Choose plane object by position; fallback to generic Sprite_%
            plane_name = f"{SPRITE_TAG_PREFIX}{position}"  # e.g. Sprite_center
            plane = (scene.objects.get(plane_name)
                     or scene.objects.get(f"{SPRITE_TAG_PREFIX}{tag}")
                     or scene.objects.get(SPRITE_FALLBACK_TAG))
            if not plane:
                # create on the fly if template missing (LLM can build UI in python)
                import bge.logic as logic
                # duplicate a template plane
                tmpl = scene.objects.get(BG_PLANE)
                if tmpl:
                    plane = scene.addObject(tmpl, tmpl)
                    plane.name = plane_name
                else:
                    _dbg(f"show {tag}: no plane object in scene — skipped")
                    return
            # place at correct world position
            plane.worldPosition = POSITIONS[position]  # type: ignore
            plane.visible = True
            plane["upvn_asset"] = asset
            # M26 policy: "color" never touches image files; "auto" tries
            # PNG/JPG/WebP first and falls back to the palette tint. The
            # policy lives on the VNController game property (image_mode).
            ctrl = scene.objects.get("VNController")
            mode = image_mode_from(ctrl if ctrl is not None else plane)
            tex_path = None
            if mode == "auto":
                import bge.texture as vt
                import os
                stem = asset.replace(" ", "_")
                slash = asset.replace(" ", "/")
                last = asset.split()[-1] if " " in asset else "neutral"
                candidates = []
                for prefix in SPRITE_PATH_PREFIXES:
                    candidates.extend([
                        bge.logic.expandPath(f"{prefix}{ASSET_SPRITES}/{slash}.png"),
                        bge.logic.expandPath(f"{prefix}{ASSET_SPRITES}/{stem}.png"),
                        bge.logic.expandPath(f"{prefix}{ASSET_SPRITES}/{tag}.png"),
                    ])
                candidates.append(
                    bge.logic.expandPath(f"//assets/characters/{tag}/{last}.png"))
                for ext in (".png", ".jpg", ".webp"):
                    for prefix in SPRITE_PATH_PREFIXES:
                        candidates.append(
                            bge.logic.expandPath(f"{prefix}{ASSET_SPRITES}/{stem}{ext}"))
                for p in candidates:
                    try:
                        if os.path.exists(p):
                            tex_path = p
                            break
                    except Exception:
                        continue
            tint = sprite_color(tag)
            if tex_path:
                try:
                    img = vt.ImageFFmpeg(tex_path)
                    img.scale = False
                    try:
                        mat_id = vt.materialID(plane, SPRITE_MATERIAL)
                    except Exception:
                        mat_id = -1
                    if mat_id < 0:
                        # fallback plane may carry only a generic material — use the
                        # first slot (note: shared datablocks are a known limitation)
                        mat_id = 0
                    tex = vt.Texture(plane, mat_id)
                    tex.source = img
                    self.planes[tag] = {"obj": plane, "tex": tex, "asset": asset, "position": position, "t0": time.time(), "transition": transition, "tint": tint}
                    _dbg(f"show {tag} '{asset}' → image {tex_path}")
                    # start alpha fade for dissolve
                    if transition in ("dissolve", "fade"):
                        plane.color = (1,1,1,0.0)
                    else:
                        plane.color = (1,1,1,1.0)
                    return
                except Exception as e:
                    _dbg(f"show {tag} '{asset}' image bind failed ({e}) → palette tint")
            # no image (or bind failed) — paint the silhouette with the palette
            # tint so a missing texture must not equal "no sprite".
            painted = apply_object_color(plane, tint)
            _dbg(f"show {tag} '{asset}' at {position} → palette tint "
                 f"(mode={mode}, painted={painted})")
            self.planes[tag] = {"obj": plane, "asset": asset, "position": position, "tint": tint}
            # start alpha fade for dissolve
            if transition in ("dissolve", "fade"):
                plane.color = (tint[0], tint[1], tint[2], 0.0)
            else:
                plane.color = (tint[0], tint[1], tint[2], 1.0)
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
        """Headless helper: returns (x,y,z) interpolated for move, or final pos."""
        import time as _t
        actor = self.state.shown_actors.get(tag)
        if not actor:
            return None
        if now is None:
            now = _t.time()
        # check move fields
        if actor.move_from and actor.move_to and actor.move_t0:
            dur = actor.move_duration or 0.5
            t_raw = (now - actor.move_t0) / dur if dur>0 else 1.0
            t_raw = max(0.0, min(1.0, t_raw))
            if t_raw >= 1.0:
                return POSITIONS.get(actor.position, POSITIONS["center"])
            # easing
            try:
                from ..atl.easing import get_easing
                ease_fn = get_easing(actor.move_easing or "ease")
            except:
                ease_fn = lambda x: x
            t = ease_fn(t_raw)
            p0 = POSITIONS.get(actor.move_from, POSITIONS["center"])
            p1 = POSITIONS.get(actor.move_to, POSITIONS["center"])
            # lerp
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
        """Per-frame tick for transition alpha + move (M10)."""
        if not HAS_BGE:
            # headless: clear finished moves so is_move_done reflects final? keep but we can clear after done for snapshot
            # Do not clear — let get_interpolated handle. But we can optionally snap position after done.
            return
        now = time.time()
        for tag, info in list(self.planes.items()):
            obj = info.get("obj")
            if not obj:
                continue
            trans = info.get("transition")
            t0 = info.get("t0")
            if trans in ("dissolve","fade") and t0:
                dur = TRANS_DUR.get(trans, 0.4)
                t = min(1.0, (now - t0)/dur) if dur>0 else 1.0
                # ease in-out; keep the palette tint, only ramp alpha
                tint = info.get("tint") or (1.0, 1.0, 1.0)
                alpha = t  # 0->1 fade in
                try:
                    obj.color = (tint[0], tint[1], tint[2], alpha)
                except Exception:
                    pass
                if t >= 1.0:
                    info["transition"] = None
        # M10 move interpolation BGE
        for tag, actor in list(self.state.shown_actors.items()):
            if actor.move_from and actor.move_to and actor.move_t0:
                dur = actor.move_duration or 0.5
                t_raw = (now - actor.move_t0) / dur if dur>0 else 1.0
                t_raw = max(0.0, min(1.0, t_raw))
                if t_raw >= 1.0:
                    # snap to final and clear move
                    try:
                        # find plane for this tag's target position
                        # reuse same plane object even if position changed — need to move it
                        info = self.planes.get(tag)
                        if info and info.get("obj"):
                            info["obj"].worldPosition = POSITIONS.get(actor.move_to, POSITIONS["center"])  # type: ignore
                    except: pass
                    # clear move to mark done
                    actor.move_from = None
                    actor.move_t0 = None
                    continue
                # easing lerp worldPosition
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
                        info["obj"].worldPosition = (x,y,z)  # type: ignore
                    except: pass

    def positions_ok(self) -> bool:
        """Headless check: all shown actors have valid positions."""
        for tag, actor in self.state.shown_actors.items():
            if actor.position not in POSITIONS and actor.position not in ("left","center","right","far_left","far_right"):
                return False
        return True
