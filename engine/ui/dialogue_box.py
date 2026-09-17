"""
Dialogue Box — UI front-end (M01 Kinetic + M02/M03 + M28 typewriter fix)

MVP: plane + blf for text, typewriter, click-to-reveal.
Per doc §5: UI lives in 3D scene (planes + blf), no DSL — LLM builds via python.

show() stores current text in state (consumed by the UPBGE runtime UI).
UPBGE: draws via 3D FONT objects (world_ui) + optional blf fallback.

Typewriter: reveal over time, click does instant reveal before advancing.
M28 audit fix: typewriter was stubbed (pass) — now fully wired to world UI.
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
from typing import Optional


class DialogueBox:
    def __init__(self, state: VNState):
        self.state = state
        self.visible = False
        self.current_who: str | None = None
        self.current_color: str | None = None
        self.current_text: str = ""
        self._raw: str = ""
        self._stripped: str = ""  # tags stripped for typewriter counting
        self._typewriter_progress: float = 0.0  # chars revealed (float for smooth)
        self._chars_per_sec: float = 40.0
        self._done: bool = False
        self._interp_warnings: list = []

    def show(self, event: dict):
        """Show a new say event. Resets typewriter."""
        self.visible = True
        self.current_who = event.get("who_name")
        self.current_color = event.get("color")
        # display_text may have tags — keep for final render, but stripped for counting
        self.current_text = event.get("display_text", "") or event.get("text", "") or ""
        self._raw = event.get("raw", self.current_text)
        self._interp_warnings = event.get("interp_warnings", []) or []
        # Strip tags for accurate char counting (tags don't consume time)
        try:
            from ..core.vn_interpreter import strip_tags
            self._stripped = strip_tags(self.current_text)
        except Exception:
            self._stripped = self.current_text
        self._typewriter_progress = 0.0
        self._done = False
        if len(self._stripped) == 0:
            self._done = True
            self._typewriter_progress = 0.0

        # Log interpolation warnings if any (M28)
        if self._interp_warnings:
            print(f"[DialogueBox] interpolation warnings: {self._interp_warnings}")

        if HAS_BGE:
            try:
                scene = bge.logic.getCurrentScene()  # type: ignore
                txt_obj = scene.objects.get("Dialogue_Text")
                if txt_obj:
                    txt_obj["Text"] = self.current_text  # type: ignore
                name_obj = scene.objects.get("Speaker_Text")
                if name_obj:
                    name_obj["Text"] = self.current_who or ""  # type: ignore
            except Exception as e:
                print(f"[DialogueBox] show() BGE update failed: {e}")

    def hide(self):
        self.visible = False
        self.current_who = None
        self.current_text = ""
        self._stripped = ""
        self._typewriter_progress = 0.0
        self._done = False

    def update_typewriter(self, dt: float, chars_per_sec: float | None = None) -> bool:
        """
        Advance typewriter. Returns True if finished.
        M28 fix: now actually advances and is wired to world_ui via revealed_text().
        """
        if not self.visible:
            return True
        if self._done:
            return True
        cps = chars_per_sec or self._chars_per_sec
        if cps <= 0:
            self._typewriter_progress = len(self._stripped)
            self._done = True
            return True
        self._typewriter_progress += dt * cps
        if self._typewriter_progress >= len(self._stripped):
            self._typewriter_progress = float(len(self._stripped))
            self._done = True
        return self._done

    def instant_reveal(self):
        """Instantly reveal all text (on click)."""
        self._typewriter_progress = float(len(self._stripped))
        self._done = True

    def revealed_text(self) -> str:
        """Text revealed so far, with tags re-applied proportionally.

        Simple approach: reveal based on stripped length, but return
        corresponding slice of original (with tags). For accurate tag handling,
        we map stripped positions to original positions.
        """
        if self._done:
            return self.current_text
        n_stripped = int(self._typewriter_progress)
        if n_stripped <= 0:
            return ""
        if n_stripped >= len(self._stripped):
            return self.current_text

        # Map stripped count to original text with tags
        # We walk original text, counting only non-tag chars
        try:
            from ..core.vn_interpreter import _tag_pat
        except Exception:
            # Fallback: simple slice of stripped
            return self._stripped[:n_stripped]

        result = []
        stripped_count = 0
        pos = 0
        text = self.current_text
        while pos < len(text) and stripped_count < n_stripped:
            m = _tag_pat.search(text, pos)
            if m is None:
                # No more tags
                remaining = n_stripped - stripped_count
                result.append(text[pos:pos+remaining])
                break
            if m.start() > pos:
                # Text before tag
                chunk = text[pos:m.start()]
                need = n_stripped - stripped_count
                if len(chunk) >= need:
                    result.append(chunk[:need])
                    stripped_count += need
                    break
                else:
                    result.append(chunk)
                    stripped_count += len(chunk)
            # Include tag itself (tags don't count toward progress)
            result.append(m.group(0))
            pos = m.end()
        return "".join(result)

    def revealed_stripped(self) -> str:
        """Stripped version of revealed text (for history/skip)."""
        n = int(self._typewriter_progress)
        return self._stripped[:n]

    def is_done(self) -> bool:
        return self._done

    # text accessors
    def fully_revealed(self) -> str:
        return self.current_text

    def get_warnings(self) -> list:
        return list(self._interp_warnings)

    # UPBGE post_draw callback example (legacy blf path — kept for reference)
    def draw_blf(self):
        if not HAS_BGE or not HAS_BLF or not self.visible:
            return
        # Legacy blf path — now 3D FONT objects are used via world_ui,
        # but keep this for debugging
        try:
            import bge.render as render
            width = render.getWindowWidth()
            height = render.getWindowHeight()
            blf.position(0, 50, 50, 0)
            blf.size(0, 24, 72)
            # Draw revealed text, not full
            blf.draw(0, (self.current_who or "") + ": " + self.revealed_stripped())
        except Exception as e:
            print(f"[DialogueBox] draw_blf failed: {e}")
