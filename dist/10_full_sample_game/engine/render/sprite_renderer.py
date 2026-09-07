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
import time

# UPBGE world positions for ortho camera scale 10 (VN_Cam ortho_scale=10)
POSITIONS = {
    "left": (-3.0, 0, 1.2),
    "center": (0, 0, 1.2),
    "right": (3.0, 0, 1.2),
    "far_left": (-5.0, 0, 1.2),
    "far_right": (5.0, 0, 1.2),
}

# transition durations (seconds)
TRANS_DUR = {"dissolve": 0.4, "fade": 0.5, None: 0.0}

class SpriteRenderer:
    def __init__(self, state: VNState):
        self.state = state
        # tag -> {"obj": bge object, "tex": Texture, "t0": start time, "transition": name}
        self.planes: dict[str, dict] = {}

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
            self.planes[tag] = {"asset": asset, "position": pos, "transition": transition, "t0": time.time()}

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
            plane_name = f"Sprite_{position}"  # e.g. Sprite_center
            plane = scene.objects.get(plane_name) or scene.objects.get(f"Sprite_{tag}") or scene.objects.get("Sprite")
            if not plane:
                # create on the fly if template missing (LLM can build UI in python)
                import bge.logic as logic
                # duplicate a template plane
                tmpl = scene.objects.get("BG_Plane")
                if tmpl:
                    plane = scene.addObject(tmpl, tmpl)
                    plane.name = plane_name
                else:
                    return
            # place at correct world position
            plane.worldPosition = POSITIONS[position]  # type: ignore
            plane.visible = True
            # texture swap
            import bge.texture as vt
            import os
            # asset like "eileen happy" -> file assets/sprites/eileen/happy.png or eileen_happy.png
            # search order
            candidates = [
                bge.logic.expandPath(f"//assets/sprites/{asset.replace(' ', '/')}.png"),
                bge.logic.expandPath(f"//assets/sprites/{asset.replace(' ', '_')}.png"),
                bge.logic.expandPath(f"//assets/characters/{tag}/{asset.split()[-1] if ' ' in asset else 'neutral'}.png"),
            ]
            tex_path = None
            for p in candidates:
                if os.path.exists(p):
                    tex_path = p
                    break
            if tex_path:
                img = vt.ImageFFmpeg(tex_path)
                img.scale = False
                mat_id = vt.materialID(plane, "MASprite")
                tex = vt.Texture(plane, mat_id)
                tex.source = img
                self.planes[tag] = {"obj": plane, "tex": tex, "asset": asset, "position": position, "t0": time.time(), "transition": transition}
                # start alpha fade for dissolve
                if transition in ("dissolve", "fade"):
                    plane.color = (1,1,1,0.0)
                else:
                    plane.color = (1,1,1,1.0)
            else:
                # no file — keep plane visible with asset name as debug (LLM can generate textures)
                plane["upvn_asset"] = asset
                self.planes[tag] = {"obj": plane, "asset": asset, "position": position}
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
                # ease in-out
                alpha = t  # 0->1 fade in
                try:
                    obj.color = (1,1,1, alpha)
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
