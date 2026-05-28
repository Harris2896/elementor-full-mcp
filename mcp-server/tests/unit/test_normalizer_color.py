import json
from pathlib import Path

from elementor_mcp.core.normalizer.passes import pass1_colors

FIX = Path(__file__).parent.parent / "fixtures"


def _profile():
    return json.loads((FIX / "profiles" / "stacks-western.json").read_text())


def test_pass1_snaps_exact_match_to_global():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"title_color": "#8B4513"},
        "elements": [],
    }
    out, diff = pass1_colors(section, _profile())
    assert out["settings"].get("title_color") is None
    assert out["settings"]["__globals__"]["title_color"] == "globals/colors?id=primary"
    assert len(diff["colors_remapped"]) == 1
    assert diff["colors_remapped"][0]["to"] == "primary"


def test_pass1_snaps_near_match_to_global():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"title_color": "#8C4614"},
        "elements": [],
    }
    out, diff = pass1_colors(section, _profile())
    assert out["settings"]["__globals__"]["title_color"] == "globals/colors?id=primary"
    assert diff["colors_remapped"][0]["delta_e"] < 5


def test_pass1_records_overflow_for_far_color():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"title_color": "#00FF00"},
        "elements": [],
    }
    out, diff = pass1_colors(section, _profile())
    assert out["settings"]["title_color"] == "#00FF00"
    assert "__globals__" not in out["settings"] or "title_color" not in out["settings"]["__globals__"]
    assert "#00FF00" in [c["hex"] for c in diff["colors_overflow"]]


def test_pass1_recurses_into_elements():
    section = {
        "id": "s1", "elType": "section",
        "settings": {},
        "elements": [{
            "id": "w1", "elType": "widget", "widgetType": "heading",
            "settings": {"title_color": "#B22222"},
            "elements": [],
        }],
    }
    out, _ = pass1_colors(section, _profile())
    widget = out["elements"][0]
    assert widget["settings"]["__globals__"]["title_color"] == "globals/colors?id=accent"


def test_pass1_handles_mid_tier_warn():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"title_color": "#A0522D"},
        "elements": [],
    }
    out, diff = pass1_colors(section, _profile())
    assert out["settings"].get("title_color") == "#A0522D"
    warnings = diff.get("colors_warned", [])
    assert any(w["from"] == "#A0522D" for w in warnings)
