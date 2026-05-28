from pathlib import Path

from elementor_mcp.scripts.build_index import build_index
from elementor_mcp.tools.template import (
    template_get,
    template_list_categories,
    template_preview,
    template_search,
)


def _setup_db(tmp_path):
    src = tmp_path / "templates"
    src.mkdir()
    fix = Path(__file__).parent.parent / "fixtures" / "templates"
    for name in ["hero-simple.json", "pricing-table.json"]:
        (src / name).write_text((fix / name).read_text())
    db_path = tmp_path / "index.db"
    build_index(src_dir=src, db_path=db_path)
    return db_path, src


def test_template_search_returns_results(tmp_path):
    db_path, src = _setup_db(tmp_path)
    res = template_search(db_path=db_path, src_dir=src, query="", category="hero", k=5)
    assert res.ok is True
    assert len(res.data["results"]) == 1
    assert res.data["results"][0]["category"] == "hero"


def test_template_get_returns_template_json(tmp_path):
    db_path, src = _setup_db(tmp_path)
    res = template_get(db_path=db_path, src_dir=src, template_id="hero-simple")
    assert res.ok is True
    assert res.data["template"]["title"] == "Hero Simple"
    assert res.data["meta"]["category"] == "hero"


def test_template_get_returns_not_found_for_unknown_id(tmp_path):
    db_path, src = _setup_db(tmp_path)
    res = template_get(db_path=db_path, src_dir=src, template_id="zzz")
    assert res.ok is False
    assert res.error.code == "E_TEMPLATE_NOT_FOUND"


def test_template_list_categories_counts(tmp_path):
    db_path, src = _setup_db(tmp_path)
    res = template_list_categories(db_path=db_path)
    assert res.ok is True
    cats = {row["category"]: row["count"] for row in res.data["categories"]}
    assert cats == {"hero": 1, "pricing": 1}


def test_template_preview_returns_url_or_null(tmp_path):
    db_path, src = _setup_db(tmp_path)
    res = template_preview(db_path=db_path, template_id="hero-simple")
    assert res.ok is True
    assert res.data.get("preview_url") in (None, "", "null")
