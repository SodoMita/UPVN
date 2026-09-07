import pytest
from pathlib import Path
import tempfile
from engine.core.vn_controller import VNController
from engine.core.vn_state import VNState
from engine.script.parser import parse_string
from engine.core.vn_interpreter import VNInterpreter

def test_overlay_vs_modal_distinction():
    c = VNController("examples/00_minimal_dialogue/script.rpy")
    c.load()
    assert c.screen_mgr is not None
    # initially no modal, no overlay
    assert not c.screen_mgr.is_modal_active()
    assert c.screen_mgr.get_overlays() == []
    # show history as overlay (non-blocking)
    c.screen_mgr.show("history")
    assert c.screen_mgr.is_overlay_visible("history")
    assert not c.screen_mgr.is_modal_active()
    assert c.screen_mgr.screens["history"].is_modal == False
    # story should still be able to advance even with overlay visible (non-blocking)
    # simulate update blocking check: overlay shouldn't block
    assert not c.screen_mgr.is_modal_active()  # still not modal
    # hide history
    c.screen_mgr.hide("history")
    assert not c.screen_mgr.is_overlay_visible("history")
    # show save as modal (blocking)
    c.screen_mgr.show("save")
    assert c.screen_mgr.is_modal_active()
    assert c.screen_mgr.get_modal().name == "save"
    assert c.screen_mgr.screens["save"].is_modal == True
    # overlay can still be shown while modal active? In our lite, we allow but modal blocks
    c.screen_mgr.show("history")
    assert c.screen_mgr.is_overlay_visible("history")
    # modal still active
    assert c.screen_mgr.is_modal_active()
    # hide modal via handle_key escape
    c.screen_mgr.handle_key("escape")
    assert not c.screen_mgr.is_modal_active()
    # hide overlay
    c.screen_mgr.hide("history")

def test_history_overlay_contains_styled():
    c = VNController("examples/00_minimal_dialogue/script.rpy")
    # run a bit to populate history
    c.run_headless()
    assert len(c.state.history) == 4
    # show history overlay
    c2 = VNController("examples/00_minimal_dialogue/script.rpy")
    c2.load()
    c2.run_headless()
    # after run_headless, state has history, but screen_mgr is fresh; need to reload with state
    # use controller that was run_headless's state
    hist = c.state.history
    # verify screen manager can retrieve entries
    entries = c.screen_mgr.get_history_entries(strip=False)
    # after run_headless, screen_mgr was rebound to fresh_state, so c.screen_mgr has same state as c.state
    assert len(entries) == len(hist)
    # test stripped version
    entries_stripped = c.screen_mgr.get_history_entries(strip=True)
    for e in entries_stripped:
        assert "{" not in e["text"]  # stripped has no tags

def test_save_load_without_screens_rpy(tmp_path):
    # save/load via ScreenManager python API, not via big screens.rpy DSL
    c = VNController("examples/03_variables_routes/script.rpy")
    c.run_headless(choices=[0])  # good route
    # c state has affection 1
    assert c.state.variables["affection"] == 1
    # use screen_mgr save
    # need to ensure save_manager points to tmp_path
    from engine.save.save_manager import SaveManager
    sm = SaveManager(c.state, save_dir=tmp_path)
    c.screen_mgr.save_manager = sm
    # also update screens' save_manager
    for scr in c.screen_mgr.screens.values():
        if hasattr(scr, 'save_manager'):
            scr.save_manager = sm
    # save to slot 1 via screen manager (overlay vs modal distinction: save is modal)
    c.screen_mgr.show("save")
    assert c.screen_mgr.is_modal_active()
    p = c.screen_mgr.save_to_slot(1)
    assert p.exists()
    # hide save modal — should return to non-blocking
    c.screen_mgr.hide("save")
    assert not c.screen_mgr.is_modal_active()
    # mutate state
    c.state.variables["affection"] = 999
    c.state.variables["route"] = "tampered"
    # load via screen manager modal
    c.screen_mgr.show("load")
    assert c.screen_mgr.is_modal_active()
    data = c.screen_mgr.load_from_slot(1)
    assert c.state.variables["affection"] == 1
    assert c.state.variables["route"] == "good"
    assert data is not None
    c.screen_mgr.hide("load")
    assert not c.screen_mgr.is_modal_active()

def test_quick_menu_overlay():
    c = VNController("examples/00_minimal_dialogue/script.rpy")
    c.load()
    # quick menu is overlay
    c.screen_mgr.show("quick_menu")
    assert c.screen_mgr.is_overlay_visible("quick_menu")
    assert not c.screen_mgr.screens["quick_menu"].is_modal
    # can be toggled via handle_key q
    c.screen_mgr.handle_key("q")
    assert not c.screen_mgr.is_overlay_visible("quick_menu")
    c.screen_mgr.handle_key("q")
    assert c.screen_mgr.is_overlay_visible("quick_menu")

def test_main_menu_modal():
    c = VNController("examples/00_minimal_dialogue/script.rpy")
    c.load()
    c.screen_mgr.show("main_menu")
    assert c.screen_mgr.is_modal_active()
    modal = c.screen_mgr.get_modal()
    assert modal.name == "main_menu"
    # selecting choice returns value
    result = modal.select(0)  # New Game
    assert result == "New Game"
    assert modal.result == "New Game"
    c.screen_mgr.hide("main_menu")
    assert not c.screen_mgr.is_modal_active()

def test_tags_and_interpolation_via_history():
    script = parse_string('''
default name = "World"
label start:
    "Hello [name] {b}bold{/b}!"
    return
''')
    from engine.core.vn_state import VNState
    from engine.core.vn_interpreter import VNInterpreter, strip_tags
    state = VNState()
    interp = VNInterpreter(script, state)
    interp.run_headless()
    assert len(state.history) == 1
    h = state.history[0]
    # tags preserved in text
    assert "{b}bold{/b}" in h["text"]
    assert h["stripped"] == "Hello World bold!"
    assert strip_tags(h["text"]) == "Hello World bold!"
