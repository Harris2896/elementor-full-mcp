import json
from pathlib import Path

from elementor_mcp.core.library.extractor import extract_metadata

FIX = Path(__file__).parent.parent / "fixtures" / "templates"


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text())


def test_hero_metadata():
    meta = extract_metadata(_load("hero-simple.json"))
    assert set(meta["widgets_used"]) == {"heading", "button"}
    assert meta["columns_max"] == 1
    assert meta["image_count"] == 0
    assert meta["has_form"] == 0
    assert "#000000" in meta["dominant_colors"]
    assert "#FFFFFF" in meta["dominant_colors"]
    assert "#FF0000" in meta["dominant_colors"]
    assert "Inter" in meta["font_families"]


def test_features_columns_max_is_three():
    meta = extract_metadata(_load("features-3col-icons.json"))
    assert meta["columns_max"] == 3
    assert "icon-box" in meta["widgets_used"]


def test_pricing_carries_price_table_widget():
    meta = extract_metadata(_load("pricing-table.json"))
    assert "price-table" in meta["widgets_used"]
    assert "Manrope" in meta["font_families"]


def test_testimonial_has_no_form_no_image():
    meta = extract_metadata(_load("testimonial.json"))
    assert meta["has_form"] == 0
    assert meta["image_count"] == 0
