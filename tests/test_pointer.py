"""Pointer/hotspot events for editor-built UI — hover & click over named objects."""
from engine.ui.pointer import HotspotMap, PointerTracker, PointerEvent, Hotspot


def test_from_choices_maps_ids():
    m = HotspotMap.from_choices([{"text": "A", "id": 0}, {"text": "B", "id": 1}])
    assert m.resolve("choice_0").choice_index == 0
    assert m.resolve("choice_1").choice_index == 1
    assert m.resolve("other") is None


def test_hover_enter_leave():
    m = HotspotMap.from_choices([{"text": "A", "id": 0}, {"text": "B", "id": 1}])
    t = PointerTracker(m)
    ev = t.update("choice_0")
    assert ev == [PointerEvent("enter", "choice_0", "choice", 0)]
    ev = t.update("choice_1")
    assert ev == [
        PointerEvent("leave", "choice_0", "choice", 0),
        PointerEvent("enter", "choice_1", "choice", 1),
    ]
    ev = t.update(None)
    assert ev == [PointerEvent("leave", "choice_1", "choice", 1)]


def test_click_over_choice():
    m = HotspotMap.from_choices([{"text": "A", "id": 0}, {"text": "B", "id": 1}])
    t = PointerTracker(m)
    t.update("choice_1")
    ev = t.update("choice_1", clicked=True)
    assert ev == [PointerEvent("click", "choice_1", "choice", 1)]
    assert t.choose(ev[0]) == 1


def test_click_not_over_hotspot():
    m = HotspotMap.from_choices([{"text": "A", "id": 0}])
    t = PointerTracker(m)
    # hover over a non-hotspot first, then click it: enter + click, no choice index
    t.update("background_plane")
    ev = t.update("background_plane", clicked=True)
    assert ev[-1].kind == "click"
    assert t.choose(ev[-1]) is None


def test_disabled_hotspot():
    m = HotspotMap()
    m.add(Hotspot("choice_0", choice_index=0, enabled=False))
    t = PointerTracker(m)
    ev = t.update("choice_0", clicked=True)
    assert t.choose(ev[0]) is None
