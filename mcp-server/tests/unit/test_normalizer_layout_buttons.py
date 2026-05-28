import json
from pathlib import Path

from elementor_mcp.core.normalizer.passes import pass4_layout, pass5_buttons

FIX = Path(__file__).parent.parent / "fixtures"


def _profile():
    return json.loads((FIX / "profiles" / "stacks-western.json").read_text())


def test_pass4_snaps_section_padding_when_within_tolerance():
    # Profile expects top=100, bottom=100. Section has 110/95 → snap to 100/100.
    section = {
        "id": "s1", "elType": "section",
        "settings": {"padding": {"unit": "px", "top": "110", "right": "0", "bottom": "95", "left": "0", "isLinked": False}},
        "elements": [],
    }
    out, diff = pass4_layout(section, _profile())
    assert out["settings"]["padding"]["top"] == 100
    assert out["settings"]["padding"]["bottom"] == 100
    assert diff["padding_snapped"][0]["delta_top"] == 10


def test_pass4_leaves_padding_outside_tolerance():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"padding": {"unit": "px", "top": "300", "right": "0", "bottom": "300", "left": "0", "isLinked": False}},
        "elements": [],
    }
    out, diff = pass4_layout(section, _profile())
    assert out["settings"]["padding"]["top"] == "300"
    assert not any(p.get("snapped") for p in diff.get("padding_snapped", []))


def test_pass4_snaps_content_width():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"content_width": {"unit": "px", "size": 1250}},
        "elements": [],
    }
    out, _ = pass4_layout(section, _profile())
    assert out["settings"]["content_width"]["size"] == 1200


def test_pass5_applies_button_defaults():
    section = {
        "id": "s1", "elType": "section",
        "settings": {},
        "elements": [{
            "id": "w1", "elType": "widget", "widgetType": "button",
            "settings": {"text": "Shop"},
            "elements": [],
        }],
    }
    out, diff = pass5_buttons(section, _profile())
    btn = out["elements"][0]["settings"]
    assert btn["border_radius"]["top"] == 2
    assert btn["text_padding"]["left"] == 36
    assert btn["text_padding"]["top"] == 18
    assert len(diff["buttons_styled"]) == 1


def test_pass5_does_not_touch_non_buttons():
    section = {
        "id": "s1", "elType": "section",
        "settings": {},
        "elements": [{
            "id": "w1", "elType": "widget", "widgetType": "heading",
            "settings": {"title": "X"},
            "elements": [],
        }],
    }
    out, diff = pass5_buttons(section, _profile())
    assert "border_radius" not in out["elements"][0]["settings"]
    assert diff["buttons_styled"] == []
