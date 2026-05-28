import json
import sqlite3
from pathlib import Path

from elementor_mcp.scripts.build_index import build_index


def test_build_index_inserts_rows(tmp_path):
    src = tmp_path / "templates"
    src.mkdir()
    fix = Path(__file__).parent.parent / "fixtures" / "templates"
    (src / "hero.json").write_text((fix / "hero-simple.json").read_text())
    (src / "pricing.json").write_text((fix / "pricing-table.json").read_text())

    db_path = tmp_path / "index.db"
    stats = build_index(src_dir=src, db_path=db_path)
    assert stats["inserted"] == 2
    assert stats["rejected"] == 0

    conn = sqlite3.connect(str(db_path))
    cats = sorted(r[0] for r in conn.execute("SELECT category FROM templates").fetchall())
    assert cats == ["hero", "pricing"]
    conn.close()


def test_build_index_skips_invalid(tmp_path):
    src = tmp_path / "templates"
    src.mkdir()
    (src / "good.json").write_text(
        (Path(__file__).parent.parent / "fixtures" / "templates" / "hero-simple.json").read_text()
    )
    (src / "bad.json").write_text(json.dumps({"version": "0.4"}))  # no content

    db_path = tmp_path / "index.db"
    stats = build_index(src_dir=src, db_path=db_path)
    assert stats["inserted"] == 1
    assert stats["rejected"] == 1


def test_build_index_is_idempotent(tmp_path):
    src = tmp_path / "templates"
    src.mkdir()
    (src / "hero.json").write_text(
        (Path(__file__).parent.parent / "fixtures" / "templates" / "hero-simple.json").read_text()
    )

    db_path = tmp_path / "index.db"
    build_index(src_dir=src, db_path=db_path)
    stats = build_index(src_dir=src, db_path=db_path)
    assert stats["inserted"] == 1
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
    assert count == 1
    conn.close()
