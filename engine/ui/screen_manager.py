"""
Screen System Lite — M09 (Python, no DSL)

Implements overlay vs modal distinction per ROADMAP M09.
Overlay: non-blocking, rendered on top while story continues (history, quick menu, skip indicator)
Modal: blocking, story pauses until dismissed and returns a value (save/load, main menu, confirm)

LLM can extend UI in python (per user request: "UI is created in 3D scene, no DSL").

Headless: draw_headless() uses Pillow via headless_renderer helpers.
UPBGE: draw_bge() uses blf + 3D planes (DialogueBox already does planes).

Usage in VNController:
    self.screen_mgr = ScreenManager(self.state)
    self.screen_mgr.register(HistoryScreen(state))
    self.screen_mgr.register(SaveScreen(state))
    self.screen_mgr.show("history", modal=False) # overlay
    self.screen_mgr.show("save", modal=True) # blocking, returns slot
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path

try:
    import bge, blf  # type: ignore
    HAS_BGE = True
except ImportError:
    HAS_BGE = False
    bge = None
    blf = None

from ..core.vn_state import VNState

class Screen:
    name: str
    is_modal: bool = False
    visible: bool = False
    # optional return value for modal
    result: Any = None

    def __init__(self, state: VNState, name: str, is_modal: bool = False):
        self.state = state
        self.name = name
        self.is_modal = is_modal
        self.visible = False
        self.result = None

    def show(self, **kwargs):
        self.visible = True
        self.result = None

    def hide(self):
        self.visible = False
        self.result = None

    def is_visible(self) -> bool:
        return self.visible

    # headless draw: override in subclasses
    def draw_headless(self, img, draw, state: VNState):
        pass

    # BGE draw
    def draw_bge(self):
        pass

    def handle_input(self, pressed_key: str) -> Optional[str]:
        """Handle key, return action or None"""
        return None

# ---------------------------------------------------------------- concrete screens

class HistoryScreen(Screen):
    """Overlay backlog — non-blocking, shows last 20 history entries with tags stripped option."""
    def __init__(self, state: VNState):
        super().__init__(state, "history", is_modal=False)
        self.max_entries = 20

    def show(self, **kwargs):
        super().show()
        # ensure we have history
        pass

    def get_entries(self, strip: bool = False):
        from ..core.vn_interpreter import strip_tags
        entries = self.state.history[-self.max_entries:]
        if strip:
            return [{"who": e.get("who_name"), "text": strip_tags(e.get("text","")), "raw": e.get("raw","")} for e in entries]
        else:
            return entries

    def draw_headless(self, img, draw, state: VNState):
        # Drawn by headless_renderer's history overlay; this is logic holder
        pass

class SaveScreen(Screen):
    """Modal save slots — arbitrary number, pagination, no fixed limit."""
    def __init__(self, state: VNState, save_manager=None):
        super().__init__(state, "save", is_modal=True)
        self.save_manager = save_manager
        self.page_size = 6
        self.page = 0

    @property
    def slots(self):
        """Compatibility: total slots = existing + 1 empty (arrow for new). Arbitrary."""
        if self.save_manager:
            return max(6, len(self.save_manager.list_slot_ids()) + 1)
        return 6

    @slots.setter
    def slots(self, v):
        # allow test to set page_size via .slots = N (legacy)
        self.page_size = int(v)

    def list_page_slots(self):
        """Return list of (slot_id, is_empty) for current page. Slot ids are ints 1..inf plus next."""
        if not self.save_manager:
            return [(i+1, True) for i in range(self.page_size)]
        ids = [x for x in self.save_manager.list_slot_ids() if isinstance(x, int)]
        ids_set = set(ids)
        # all slots from 1..max+1 plus pagination holes
        max_id = max(ids) if ids else 0
        # we want to show page * page_size .. (page+1)*page_size
        start = self.page * self.page_size + 1
        end = start + self.page_size
        out = []
        for sid in range(start, end):
            is_empty = sid not in ids_set
            # if beyond max+1, also empty but allow creation
            out.append((sid, is_empty))
        return out

    def next_available_slot(self):
        if self.save_manager:
            return self.save_manager.next_available_slot()
        return 1

    def save_to_slot(self, slot: int, screenshot_path: str | None = None):
        # arbitrary slot number — no limit
        if self.save_manager:
            path = self.save_manager.save(slot, screenshot_path)
            self.result = slot
            return path
        self.result = slot
        return slot

class LoadScreen(Screen):
    """Modal load slots — arbitrary number, only existing saves."""
    def __init__(self, state: VNState, save_manager=None):
        super().__init__(state, "load", is_modal=True)
        self.save_manager = save_manager
        self.page_size = 6
        self.page = 0

    @property
    def slots(self):
        if self.save_manager:
            return max(1, len([x for x in self.save_manager.list_slot_ids() if isinstance(x, int)]))
        return 6

    @slots.setter
    def slots(self, v):
        self.page_size = int(v)

    def list_page_slots(self):
        if not self.save_manager:
            return [(i+1, True) for i in range(self.page_size)]
        ids = sorted([x for x in self.save_manager.list_slot_ids() if isinstance(x, int)])
        start = self.page * self.page_size
        end = start + self.page_size
        page_ids = ids[start:end]
        # pad with empty if needed for grid consistency? load shows only existing, so return only page_ids
        return [(sid, False) for sid in page_ids]

    def load_from_slot(self, slot: int):
        if self.save_manager:
            try:
                data = self.save_manager.load(slot)
                self.result = slot
                return data
            except FileNotFoundError:
                self.result = None
                return None
        self.result = slot
        return slot

class MainMenuScreen(Screen):
    """Modal main menu — blocking, returns choice string"""
    def __init__(self, state: VNState):
        super().__init__(state, "main_menu", is_modal=True)
        self.choices = ["New Game", "Continue", "Load", "Preferences", "Quit"]
        self.selected = 0

    def select(self, index: int):
        if 0 <= index < len(self.choices):
            self.result = self.choices[index]
            return self.result
        return None

class QuickMenuScreen(Screen):
    """Overlay quick menu — always visible overlay with buttons (save/load/history/skip/auto/prefs)"""
    def __init__(self, state: VNState):
        super().__init__(state, "quick_menu", is_modal=False)
        # quick menu is often visible; start hidden and toggled via config
        self.buttons = ["Save", "Load", "History", "Skip", "Auto", "Prefs", "Quit"]
        self.visible = False  # start hidden, but can be shown as overlay

class PreferencesScreen(Screen):
    """Modal preferences — text speed, auto delay, volume"""
    def __init__(self, state: VNState):
        super().__init__(state, "preferences", is_modal=True)
        self.options = {"text_speed": 40, "auto_delay": 0.7, "volume": 1.0}

# ---------------------------------------------------------------- manager

class ScreenManager:
    def __init__(self, state: VNState, save_manager=None):
        self.state = state
        self.save_manager = save_manager
        self.screens: Dict[str, Screen] = {}
        self.active_modal: Optional[Screen] = None
        self._overlay_order: List[str] = []  # order of visible overlays

        # register default screens
        self.register(HistoryScreen(state))
        self.register(QuickMenuScreen(state))
        self.register(SaveScreen(state, save_manager))
        self.register(LoadScreen(state, save_manager))
        self.register(MainMenuScreen(state))
        self.register(PreferencesScreen(state))

    def register(self, screen: Screen):
        self.screens[screen.name] = screen
        # if screen was created with save_manager missing, inject
        if hasattr(screen, 'save_manager') and getattr(screen, 'save_manager') is None:
            setattr(screen, 'save_manager', self.save_manager)

    def show(self, name: str, modal: bool | None = None, **kwargs) -> Optional[Screen]:
        scr = self.screens.get(name)
        if not scr:
            raise ValueError(f"screen {name!r} not found")
        # allow override modal flag at call site
        if modal is not None:
            # don't mutate original, but treat as requested mode
            # for this lite implementation, we respect screen's own is_modal unless forced
            pass
        scr.show(**kwargs)
        if scr.is_modal:
            # modal blocks — set active_modal, hide others? overlays stay but dimmed
            self.active_modal = scr
        else:
            if name not in self._overlay_order:
                self._overlay_order.append(name)
        return scr

    def hide(self, name: str):
        scr = self.screens.get(name)
        if not scr:
            return
        scr.hide()
        if scr.is_modal and self.active_modal == scr:
            self.active_modal = None
        elif name in self._overlay_order:
            self._overlay_order.remove(name)

    def hide_all(self):
        for scr in self.screens.values():
            scr.hide()
        self.active_modal = None
        self._overlay_order.clear()

    def is_modal_active(self) -> bool:
        return self.active_modal is not None and self.active_modal.visible

    def get_modal(self) -> Optional[Screen]:
        return self.active_modal if self.is_modal_active() else None

    def get_overlays(self) -> List[Screen]:
        return [self.screens[n] for n in self._overlay_order if self.screens[n].visible]

    def is_overlay_visible(self, name: str) -> bool:
        return name in self._overlay_order and self.screens[name].visible

    def next_page(self):
        if self.is_modal_active() and hasattr(self.active_modal, "page"):
            self.active_modal.page += 1  # type: ignore
            return True
        return False

    def prev_page(self):
        if self.is_modal_active() and hasattr(self.active_modal, "page"):
            if self.active_modal.page > 0:  # type: ignore
                self.active_modal.page -= 1  # type: ignore
                return True
        return False

    # input routing — returns True if input was consumed by screen
    def handle_key(self, key: str) -> bool:
        # modal consumes all — also pagination for arbitrary slots
        if self.is_modal_active():
            mod = self.active_modal
            lk = key.lower()
            # pagination for save/load
            if lk in ("right", "pagedown", "n", "next"):
                if hasattr(mod, "page"):
                    mod.page += 1  # type: ignore
                    return True
            if lk in ("left", "pageup", "p", "prev"):
                if hasattr(mod, "page") and mod.page > 0:  # type: ignore
                    mod.page -= 1  # type: ignore
                    return True
            # ESC closes modal
            if lk in ("escape", "esc"):
                self.hide(mod.name)  # type: ignore
                return True
            # allow screen to handle
            res = mod.handle_input(key)  # type: ignore
            return True
        # overlays: H toggles history, Q toggles quick menu, etc.
        if key.lower() == "h":
            if self.is_overlay_visible("history"):
                self.hide("history")
            else:
                self.show("history")
            return True
        if key.lower() == "q":
            if self.is_overlay_visible("quick_menu"):
                self.hide("quick_menu")
            else:
                self.show("quick_menu")
            return True
        return False

    # save/load convenience (non-DSL, python)
    def save_to_slot(self, slot: int, screenshot_path: str | None = None) -> Path | None:
        scr = self.screens.get("save")
        if isinstance(scr, SaveScreen):
            return scr.save_to_slot(slot, screenshot_path)
        # fallback via save_manager
        if self.save_manager:
            return self.save_manager.save(slot, screenshot_path)
        return None

    def load_from_slot(self, slot: int):
        scr = self.screens.get("load")
        if isinstance(scr, LoadScreen):
            return scr.load_from_slot(slot)
        if self.save_manager:
            return self.save_manager.load(slot)
        return None

    def get_history_entries(self, strip: bool = False):
        hist = self.screens.get("history")
        if isinstance(hist, HistoryScreen):
            return hist.get_entries(strip=strip)
        return []

    # headless draw helper — called by headless_renderer
    def draw_headless_overlays(self, img, draw, state: VNState):
        for scr in self.get_overlays():
            try:
                scr.draw_headless(img, draw, state)
            except: pass
        if self.active_modal:
            try:
                self.active_modal.draw_headless(img, draw, state)
            except: pass
