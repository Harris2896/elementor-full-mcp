import json
from pathlib import Path

from elementor_mcp.core.normalizer.normalize import normalize_section
from elementor_mcp.core.normalizer.passes import strip_tablet

FIX = Path(__file__).parent.parent / "fixtures"


def _profile():
    return json.loads((FIX / "profiles" / "stacks-western.json").read_text())


def test_strip_tablet_removes_tablet_keys():
    section = {
        "id": "s1", "elType": "section",
        "settings": {
            "padding_tablet": {"unit": "px", "top": "60"},
            "padding_mobile": {"unit": "px", "top": "40"},
            "padding": {"unit": "px", "top": "100"},
        },
        "elements": [],
    }
    out = strip_tablet(section)
    assert "padding_tablet" not in out["settings"]
    assert "padding_mobile" in out["settings"]
    assert "padding" in out["settings"]


def test_normalize_section_returns_diff_with_all_buckets():
    section = {
        "id": "s1", "elType": "section",
        "settings": {
            "background_color": "#8B4513",
            "typography_font_family": "Playfair Display",
            "typography_font_size": {"unit": "px", "size": 64},
            "padding": {"unit": "px", "top": "100", "bottom": "100", "left": "0", "right": "0", "isLinked": False},
            "padding_tablet": {"unit": "px", "top": "60"},
        },
        "elements": [{
            "id": "w1", "elType": "widget", "widgetType": "button",
            "settings": {"text": "Buy"},
            "elements": [],
        }],
    }
    result = normalize_section(section, _profile())
    diff = result["diff"]
    assert any(c["to"] == "primary" for c in diff["colors_remapped"])
    assert any(f["to"] == "primary" for f in diff["fonts_remapped"])
    assert any(s["to_level"] == "h1" for s in diff["sizes_snapped"])
    assert "tablet_stripped" in diff
    assert diff["tablet_stripped"] >= 1
    assert any(b for b in diff.get("buttons_styled", []))


def test_normalize_section_does_not_mutate_input():
    section = {"id": "s1", "elType": "section", "settings": {"background_color": "#8B4513"}, "elements": []}
    original = json.dumps(section)
    normalize_section(section, _profile())
    assert json.dumps(section) == original
