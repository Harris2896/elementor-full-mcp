import pytest

from elementor_mcp.core.library.db import open_db


def test_open_db_creates_file_and_applies_schema(tmp_path):
    db_path = tmp_path / "index.db"
    conn = open_db(db_path)
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='templates'"
    )
    assert cur.fetchone() is not None
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='templates_fts'"
    )
    assert cur.fetchone() is not None
    conn.close()


def test_open_db_is_idempotent(tmp_path):
    db_path = tmp_path / "index.db"
    open_db(db_path).close()
    open_db(db_path).close()  # second call must not raise


def test_ensure_schema_raises_when_fts5_unavailable(tmp_path, monkeypatch):
    from elementor_mcp.core.library import db as db_mod
    monkeypatch.setattr(db_mod, "_has_fts5", lambda conn: False)
    db_path = tmp_path / "no-fts.db"
    with pytest.raises(RuntimeError, match="FTS5"):
        open_db(db_path)


def test_template_columns_present(tmp_path):
    conn = open_db(tmp_path / "x.db")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(templates)").fetchall()}
    assert {
        "id", "path", "category", "source", "status",
        "widgets_used", "columns_max", "image_count",
        "dominant_colors", "font_families",
        "description", "use_cases", "style_tags", "industries",
        "augmented", "schema_version", "validated_at",
    }.issubset(cols)
    conn.close()
