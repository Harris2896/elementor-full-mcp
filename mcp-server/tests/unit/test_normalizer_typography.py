import json
from pathlib import Path

from elementor_mcp.core.normalizer.passes import pass3_typography_sizes

FIX = Path(__file__).parent.parent / "fixtures"


def _profile():
    return json.loads((FIX / "profiles" / "stacks-western.json").read_text())


def test_pass3_classifies_h1_size():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"typography_font_size": {"unit": "px", "size": 72}},
        "elements": [],
    }
    out, diff = pass3_typography_sizes(section, _profile())
    assert "typography_font_size" not in out["settings"]
    assert "typography_font_weight" not in out["settings"]
    assert "typography_line_height" not in out["settings"]
    assert out["settings"]["__globals__"]["typography_typography"] == "globals/typography?id=h1"
    assert diff["sizes_snapped"][0]["to_level"] == "h1"


def test_pass3_classifies_body_size():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"typography_font_size": {"unit": "px", "size": 17}},
        "elements": [],
    }
    out, _ = pass3_typography_sizes(section, _profile())
    assert out["settings"]["__globals__"]["typography_typography"] == "globals/typography?id=body"


def test_pass3_classifies_small_size():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"typography_font_size": {"unit": "px", "size": 12}},
        "elements": [],
    }
    out, _ = pass3_typography_sizes(section, _profile())
    assert out["settings"]["__globals__"]["typography_typography"] == "globals/typography?id=small"


def test_pass3_skips_non_px_unit():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"typography_font_size": {"unit": "em", "size": 2}},
        "elements": [],
    }
    out, _ = pass3_typography_sizes(section, _profile())
    assert out["settings"]["typography_font_size"]["unit"] == "em"
