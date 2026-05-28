import contextlib
import json
import sqlite3


def search(
    conn: sqlite3.Connection,
    query: str = "",
    *,
    category: str | None = None,
    has_image: bool | None = None,
    k: int = 5,
) -> list[dict]:
    """Hybrid search: SQL filter optionally joined with FTS5 keyword rank."""
    if query.strip():
        sql = """
            SELECT t.*, bm25(templates_fts) AS score
            FROM templates_fts
            JOIN templates t ON t.id = templates_fts.id
            WHERE templates_fts MATCH ?
        """
        params: list = [query]
        if category:
            sql += " AND t.category = ?"
            params.append(category)
        if has_image is True:
            sql += " AND t.image_count > 0"
        elif has_image is False:
            sql += " AND t.image_count = 0"
        sql += " ORDER BY score LIMIT ?"
        params.append(k)
    else:
        sql = "SELECT t.*, 0 AS score FROM templates t WHERE t.status='valid'"
        params = []
        if category:
            sql += " AND t.category = ?"
            params.append(category)
        if has_image is True:
            sql += " AND t.image_count > 0"
        elif has_image is False:
            sql += " AND t.image_count = 0"
        sql += " ORDER BY t.id LIMIT ?"
        params.append(k)

    return [_row_to_dict(row) for row in conn.execute(sql, params).fetchall()]


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("widgets_used", "dominant_colors", "font_families", "use_cases", "style_tags", "industries"):
        v = d.get(key)
        if isinstance(v, str) and v:
            with contextlib.suppress(json.JSONDecodeError):
                d[key] = json.loads(v)
    return d
