import json
from pathlib import Path

from elementor_mcp.core.library.validator import validate_template

FIX = Path(__file__).parent.parent / "fixtures" / "templates"


def test_valid_template_accepted():
    data = json.loads((FIX / "hero-simple.json").read_text())
    result = validate_template(data)
    assert result["ok"] is True
    assert result["errors"] == []


def test_missing_content_array_rejected():
    result = validate_template({"version": "0.4"})
    assert result["ok"] is False
    assert any("content" in e for e in result["errors"])


def test_non_array_content_rejected():
    result = validate_template({"content": "not a list", "version": "0.4"})
    assert result["ok"] is False


def test_section_missing_id_rejected():
    bad = {"content": [{"elType": "section", "settings": {}, "elements": []}], "version": "0.4"}
    result = validate_template(bad)
    assert result["ok"] is False
    assert any("id" in e for e in result["errors"])


def test_unknown_top_level_key_warns():
    data = json.loads((FIX / "hero-simple.json").read_text())
    data["mystery"] = "x"
    result = validate_template(data)
    assert result["ok"] is True
    assert any("mystery" in w for w in result["warnings"])
