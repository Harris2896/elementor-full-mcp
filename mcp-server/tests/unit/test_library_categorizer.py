import json
from pathlib import Path

from elementor_mcp.core.library.categorizer import categorize
from elementor_mcp.core.library.extractor import extract_metadata

FIX = Path(__file__).parent.parent / "fixtures" / "templates"


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text())


def test_hero_simple_classified_as_hero():
    tpl = _load("hero-simple.json")
    assert categorize(tpl, extract_metadata(tpl)) == "hero"


def test_features_classified_as_features():
    tpl = _load("features-3col-icons.json")
    assert categorize(tpl, extract_metadata(tpl)) == "features"


def test_pricing_classified_as_pricing():
    tpl = _load("pricing-table.json")
    assert categorize(tpl, extract_metadata(tpl)) == "pricing"


def test_testimonial_classified_as_testimonial():
    tpl = _load("testimonial.json")
    assert categorize(tpl, extract_metadata(tpl)) == "testimonial"


def test_unknown_falls_back_to_section_general():
    blank = {"content": [{"id": "x", "elType": "section", "settings": {}, "elements": []}]}
    assert categorize(blank, extract_metadata(blank)) == "section-general"
