"""Stage B indexer — walk a directory of Elementor template JSONs, validate,
extract metadata, classify category, and upsert into the SQLite index."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from ..core.library.categorizer import categorize
from ..core.library.db import open_db
from ..core.library.extractor import extract_metadata
from ..core.library.validator import validate_template


def build_index(*, src_dir: Path, db_path: Path) -> dict:
    inserted = 0
    rejected = 0
    conn = open_db(db_path)
    now = datetime.now(UTC).isoformat()

    for json_path in sorted(src_dir.rglob("*.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            rejected += 1
            continue

        valid = validate_template(data)
        if not valid["ok"]:
            rejected += 1
            continue

        meta = extract_metadata(data)
        category = categorize(data, meta)
        rel_path = str(json_path.relative_to(src_dir))
        template_id = json_path.stem

        conn.execute("""
            INSERT INTO templates (
                id, path, category, source, status,
                widgets_used, columns_max, image_count,
                has_form, has_carousel, has_video,
                dominant_colors, font_families,
                schema_version, validated_at, imported_at
            ) VALUES (?, ?, ?, 'builtin', 'valid',
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                path=excluded.path,
                category=excluded.category,
                widgets_used=excluded.widgets_used,
                columns_max=excluded.columns_max,
                image_count=excluded.image_count,
                has_form=excluded.has_form,
                has_carousel=excluded.has_carousel,
                has_video=excluded.has_video,
                dominant_colors=excluded.dominant_colors,
                font_families=excluded.font_families,
                schema_version=excluded.schema_version,
                validated_at=excluded.validated_at
        """, (
            template_id, rel_path, category,
            json.dumps(meta["widgets_used"]),
            meta["columns_max"], meta["image_count"],
            meta["has_form"], meta["has_carousel"], meta["has_video"],
            json.dumps(meta["dominant_colors"]),
            json.dumps(meta["font_families"]),
            data.get("version"), now, now,
        ))
        inserted += 1

    conn.commit()
    conn.close()
    return {"inserted": inserted, "rejected": rejected}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--src", required=True, help="Directory of template *.json files")
    p.add_argument(
        "--db",
        default=str(Path(__file__).resolve().parent.parent / "data" / "index.db"),
        help="Path to index.db",
    )
    args = p.parse_args(argv)
    stats = build_index(src_dir=Path(args.src), db_path=Path(args.db))
    print(f"inserted={stats['inserted']} rejected={stats['rejected']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
