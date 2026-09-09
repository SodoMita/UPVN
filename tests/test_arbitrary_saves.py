import tempfile, pathlib
from engine.core.vn_state import VNState
from engine.save.save_manager import SaveManager
from engine.ui.screen_manager import ScreenManager
# Pillow backs the headless renderer; without it these tests skip rather
# than aborting collection (which would take the rest of the suite down).
import pytest
pytest.importorskip("PIL", reason="Pillow is required by the headless renderer")
from engine.render.headless_renderer import render_state

def test_arbitrary_slots_not_limited_to_6():
    tmp = pathlib.Path(tempfile.mkdtemp())
    state = VNState()
    sm = SaveManager(state, save_dir=tmp)
    # save to arbitrary slots including beyond 6
    for slot in [1, 2, 6, 7, 42, 100, 999, 1000, 12345]:
        state.variables["v"] = slot
        state.current_label = "start"
        state.instruction_index = slot
        sm.save(slot)
    ids = sm.list_slot_ids()
    assert 42 in ids
    assert 999 in ids
    assert 12345 in ids
    assert len(ids) == 9
    # next available should be 3? Actually we have 1,2,6,7 -> next is 3? But we have 6, so next is 3? Wait 3 missing? We saved 1,2,6,7 -> next is 3, then 4,5
    # we saved 1,2,6,7,42,100,999,1000,12345 -> missing 3,4,5 -> next is 3
    assert sm.next_available_slot() == 3
    sm.save(3)
    assert sm.next_available_slot() == 4
    # ScreenManager pagination arbitrary
    mgr = ScreenManager(state, save_manager=sm)
    save_scr = mgr.screens["save"]
    # should support page 0..many
    assert save_scr.page_size == 6
    # page 0 contains 1-6
    save_scr.page = 0
    lst0 = save_scr.list_page_slots()
    assert lst0[0][0] == 1
    assert lst0[5][0] == 6
    # page 7 should contain 43-48? For SAVE, page 7 (0-indexed) is 43-48, not 42. But 42 is on page 7? Let's compute: page*6+1 = 43 for page 7 -> 43-48, so 42 is on page 6 (37-42) actually page 6 is 37-42, includes 42
    save_scr.page = 6
    lst = save_scr.list_page_slots()
    assert any(sid == 42 for sid, _ in lst), f"page 6 should contain 42, got {lst}"
    # page for 12345: page = (12345-1)//6 = 2057
    save_scr.page = (12345-1)//6
    lst = save_scr.list_page_slots()
    assert any(sid == 12345 for sid, _ in lst)
    # load arbitrary
    sm.load(12345)
    assert state.instruction_index == 12345
    sm.load(999)
    assert state.instruction_index == 999

def test_save_overlay_arbitrary_render(tmp_path):
    tmp = pathlib.Path(tempfile.mkdtemp())
    state = VNState()
    state.history = [{"who":None,"who_name":None,"text":"hi","stripped":"hi"}]
    sm = SaveManager(state, save_dir=tmp)
    for slot in [1,7,42,500]:
        state.variables["x"]=slot
        sm.save(slot)
    from engine.ui.screen_manager import ScreenManager
    mgr = ScreenManager(state, save_manager=sm)
    mgr.show("save")
    # page 0 should show 1-6
    mgr.screens["save"].page = 0
    out0 = tmp_path / "save_p0.png"
    render_state(state, {"type":"say","who":None,"text":"test"}, out0, screen_mgr=mgr)
    assert out0.exists()
    # page 83 should show 500 (500//6=83)
    mgr.screens["save"].page = 83
    out83 = tmp_path / "save_p83.png"
    render_state(state, {"type":"say","who":None,"text":"test"}, out83, screen_mgr=mgr)
    assert out83.exists()
    # load screen pagination: only existing saves
    mgr.hide("save")
    mgr.show("load")
    # load page 0 should contain 1,7,42,500 (4 saves)
    mgr.screens["load"].page = 0
    out_load = tmp_path / "load_p0.png"
    render_state(state, {"type":"say","who":None,"text":"test"}, out_load, screen_mgr=mgr)
    assert out_load.exists()

def test_blender_builder_minimal_coding():
    from blend.upvn_editor_addon import UPVN_GameBuilder
    import tempfile, pathlib
    tmp = pathlib.Path(tempfile.mkdtemp()) / "script.rpy"
    b = UPVN_GameBuilder(str(tmp))
    b.add_character("e", "Eileen", "#c8ffc8")
    b.add_scene("bg classroom")
    b.add_say("e", "Hello from minimal coding")
    b.add_show("eileen", "center", "move")
    b.add_menu("Choose?", [("A","a_label"), ("B","b_label")])
    ok, msg = b.validate()
    assert ok, msg
    p = b.write()
    text = p.read_text()
    assert 'define e = Character("Eileen"' in text
    assert 'scene bg classroom' in text
    assert 'e "Hello' in text
    # preview screenshot should work headless
    out = b.preview_screenshot(str(tmp.parent / "preview.png"))
    assert out and out.exists()
