import json
from pathlib import Path

from ..core.library.db import open_db
from ..core.library.search import search
from ..envelope import ToolResult, fail, ok
from ..errors import ErrorCode


def template_search(
    *,
    db_path: Path,
    src_dir: Path,
    query: str = "",
    category: str | None = None,
    has_image: bool | None = None,
    k: int = 5,
) -> ToolResult:
    conn = open_db(db_path)
    try:
        rows = search(conn, query, category=category, has_image=has_image, k=k)
    finally:
        conn.close()
    return ok({"results": rows, "count": len(rows)})


def template_get(*, db_path: Path, src_dir: Path, template_id: str) -> ToolResult:
    conn = open_db(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM templates WHERE id = ?", (template_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return fail(ErrorCode.E_TEMPLATE_NOT_FOUND, f"template not found: {template_id}")
    row = dict(row)
    json_path = src_dir / row["path"]
    if not json_path.exists():
        return fail(ErrorCode.E_TEMPLATE_NOT_FOUND, f"template file missing at {row['path']}")
    template_json = json.loads(json_path.read_text(encoding="utf-8"))
    return ok({"template": template_json, "meta": row})


def template_preview(*, db_path: Path, template_id: str) -> ToolResult:
    conn = open_db(db_path)
    try:
        row = conn.execute(
            "SELECT preview_url FROM templates WHERE id = ?", (template_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return fail(ErrorCode.E_TEMPLATE_NOT_FOUND, f"template not found: {template_id}")
    return ok({"preview_url": row["preview_url"]})


def template_list_categories(*, db_path: Path) -> ToolResult:
    conn = open_db(db_path)
    try:
        rows = conn.execute(
            "SELECT category, COUNT(*) AS count FROM templates "
            "WHERE category IS NOT NULL GROUP BY category ORDER BY count DESC"
        ).fetchall()
    finally:
        conn.close()
    return ok({"categories": [{"category": r["category"], "count": r["count"]} for r in rows]})
