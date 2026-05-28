import sqlite3
from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent.parent.parent / "data" / "schema.sql"


def _has_fts5(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE _probe USING fts5(a)")
        conn.execute("DROP TABLE _probe")
        return True
    except sqlite3.OperationalError:
        return False


def ensure_schema(conn: sqlite3.Connection) -> None:
    if not _has_fts5(conn):
        raise RuntimeError(
            "SQLite build does not support FTS5. "
            "Use the system sqlite3 or a Python built with --enable-fts5."
        )
    schema_sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    with conn:
        conn.executescript(schema_sql)


def open_db(path) -> sqlite3.Connection:
    """Open (or create) the templates index database and apply schema."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn
