import json
import sqlite3
from pathlib import Path

from elementor_mcp.core.library.search import search
from elementor_mcp.scripts.build_index import build_index


def _build_test_db(tmp_path):
    src = tmp_path / "templates"
    src.mkdir()
    fix = Path(__file__).parent.parent / "fixtures" / "templates"
    for name in ["hero-simple.json", "features-3col-icons.json", "pricing-table.json", "testimonial.json"]:
        (src / name).write_text((fix / name).read_text())
    db_path = tmp_path / "index.db"
    build_index(src_dir=src, db_path=db_path)
    # Inject description + use_cases so FTS5 has content to rank on
    # (schema triggers auto-sync templates_fts on UPDATE).
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("UPDATE templates SET description=?, use_cases=? WHERE id=?",
                 ("clean modern hero with bold heading", json.dumps(["landing", "saas"]), "hero-simple"))
    conn.commit()
    return conn


def test_search_with_category_only_filters_by_category(tmp_path):
    conn = _build_test_db(tmp_path)
    results = search(conn, query="", category="pricing", k=5)
    assert len(results) == 1
    assert results[0]["id"] == "pricing-table"
    conn.close()


def test_search_with_query_uses_fts(tmp_path):
    conn = _build_test_db(tmp_path)
    results = search(conn, query="bold heading", k=5)
    ids = {r["id"] for r in results}
    assert "hero-simple" in ids
    conn.close()


def test_search_combines_category_and_query(tmp_path):
    conn = _build_test_db(tmp_path)
    results = search(conn, query="bold heading", category="hero", k=5)
    assert len(results) == 1
    assert results[0]["id"] == "hero-simple"
    conn.close()


def test_search_returns_empty_when_no_match(tmp_path):
    conn = _build_test_db(tmp_path)
    results = search(conn, query="zzznonexistent", k=5)
    assert results == []
    conn.close()
