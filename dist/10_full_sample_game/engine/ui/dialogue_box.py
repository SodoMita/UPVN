"""
Dialogue Box — UI front-end (M01 Kinetic + M02/M03)

MVP: plane + blf for text, typewriter, click-to-reveal.
Per doc §5: UI lives in 3D scene (planes + blf), no DSL — LLM builds via python.

Headless: show() stores current text for render_state / headless_renderer.
UPBGE: draws via blf in scene.post_draw or via Text objects.

Typewriter: reveal over time, click does instant reveal before advancing.
"""
from __future__ import annotations
try:
    import bge, blf  # type: ignore
    HAS_BGE = True
    HAS_BLF = True
except ImportError:
    HAS_BGE = False
    HAS_BLF = False
    bge = None
    blf = None

from ..core.vn_state import VNState

class DialogueBox:
    def __init__(self, state: VNState):
        self.state = state
        self.visible = False
        self.current_who: str | None = None
        self.current_color: str | None = None
        self.current_text: str = ""
        self._raw: str = ""
        self._typewriter_progress: float = 0.0  # chars revealed
        self._chars_per_sec: float = 40.0

    def show(self, event: dict):
        self.visible = True
        self.current_who = event.get("who_name")
        self.current_color = event.get("color")
        self.current_text = event.get("display_text", "") or event.get("text", "")
        self._raw = event.get("raw", self.current_text)
        self._typewriter_progress = 0.0
        if HAS_BGE:
            # Update text objects if template has Dialogue_Text
            try:
                scene = bge.logic.getCurrentScene()  # type: ignore
                txt_obj = scene.objects.get("Dialogue_Text")
                if txt_obj:
                    txt_obj["Text"] = self.current_text  # type: ignore
                name_obj = scene.objects.get("Speaker_Text")
                if name_obj:
                    name_obj["Text"] = self.current_who or ""  # type: ignore
            except Exception:
                pass

    def hide(self):
        self.visible = False
        self.current_who = None
        self.current_text = ""

    def update_typewriter(self, dt: float, chars_per_sec: float | None = None) -> bool:
        """
        Advance typewriter. Returns True if finished.
        """
        if not self.visible:
            return True
        cps = chars_per_sec or self._chars_per_sec
        self._typewriter_progress += dt * cps
        done = self._typewriter_progress >= len(self.current_text)
        if HAS_BGE and HAS_BLF:
            # blf drawing would happen in post_draw; we just update progress
            pass
        return done

    def instant_reveal(self):
        self._typewriter_progress = len(self.current_text)

    def revealed_text(self) -> str:
        n = int(self._typewriter_progress)
        return self.current_text[:n]

    def is_done(self) -> bool:
        return self._typewriter_progress >= len(self.current_text)

    # headless helper
    def fully_revealed(self) -> str:
        return self.current_text

    # UPBGE post_draw callback example
    def draw_blf(self):
        if not HAS_BGE or not HAS_BLF or not self.visible:
            return
        # Example blf draw at screen coords (would be registered via scene.post_draw)
        # import bge.render as render
        # width = render.getWindowWidth(); height = render.getWindowHeight()
        # blf.position(0, 50, 50, 0)
        # blf.size(0, 24)
        # blf.draw(0, (self.current_who or "") + ": " + self.revealed_text())
        pass
