import json
from pathlib import Path

from elementor_mcp.core.normalizer.passes import pass2_fonts

FIX = Path(__file__).parent.parent / "fixtures"


def _profile():
    return json.loads((FIX / "profiles" / "stacks-western.json").read_text())


def test_pass2_maps_primary_font_to_global():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"typography_font_family": "Playfair Display"},
        "elements": [],
    }
    out, diff = pass2_fonts(section, _profile())
    assert out["settings"].get("typography_font_family") is None
    assert out["settings"]["__globals__"]["typography_typography"] == "globals/typography?id=primary"
    assert diff["fonts_remapped"][0]["to"] == "primary"


def test_pass2_maps_secondary_font_to_global():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"typography_font_family": "Inter"},
        "elements": [],
    }
    out, _ = pass2_fonts(section, _profile())
    assert out["settings"]["__globals__"]["typography_typography"] == "globals/typography?id=secondary"


def test_pass2_unknown_font_kept_and_warned():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"typography_font_family": "Comic Sans"},
        "elements": [],
    }
    out, diff = pass2_fonts(section, _profile())
    assert out["settings"].get("typography_font_family") == "Comic Sans"
    assert diff["fonts_warned"][0]["from"] == "Comic Sans"


def test_pass2_recurses():
    section = {
        "id": "s1", "elType": "section",
        "settings": {},
        "elements": [{
            "id": "w1", "elType": "widget", "widgetType": "heading",
            "settings": {"typography_font_family": "Playfair Display"},
            "elements": [],
        }],
    }
    out, _ = pass2_fonts(section, _profile())
    widget_globals = out["elements"][0]["settings"]["__globals__"]
    assert widget_globals["typography_typography"] == "globals/typography?id=primary"
