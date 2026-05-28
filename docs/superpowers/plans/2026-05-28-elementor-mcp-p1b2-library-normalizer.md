# Elementor MCP — Phase 1b-2 (Library indexing + Kit Normalizer) Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Index the 2,232 section-express templates so agents can `template.search(query, category)` instead of hand-crafting JSON, AND implement the six-pass Kit Normalizer so any section JSON (from library or AI-composed) gets snapped to the active Kit profile — colors→globals, fonts→globals, sizes→typography scale — with a diff report explaining every change.

**Architecture:** All indexing and normalization lives in Python. A new SQLite database (`mcp-server/elementor_mcp/data/index.db`) stores per-template structural metadata + FTS5 keyword index. The normalizer is a pure pipeline of six passes operating on Elementor section JSON. Color overflow (any color outside the profile's palette) gets auto-promoted to Kit `custom_colors` via the existing PUT `/kit` endpoint.

**Tech Stack:** Python 3.11+, SQLite 3 with FTS5, `colormath` for LAB ΔE color distance, existing `httpx` + `pydantic`. No new infra.

**Spec reference:** `docs/superpowers/specs/2026-05-27-elementor-mcp-design.md` §3 #4 (template indexing), §3 #10–#13 (color overflow, tier mapping, diff report), §3 #11 (mobile-only responsive), §8 template tools, §10.1 (Stage B auto-extract), §10.3 (SQLite schema), §10.4 (hybrid search), §11 (six-pass normalizer with custom_colors overflow + diff report).

**Plan scope:** P1b-2 only. P1b-3 (Kit Mapper Admin UI + MCP HTTP server) will get its own plan after P1b-2 ships.

**Predecessor:** `v0.1.1-p1b1` tag must be merged and CI green.

---

## File structure (created/modified by this plan)

```
mcp-server/
├─ pyproject.toml                                  MODIFY — add colormath
├─ elementor_mcp/
│  ├─ data/                                        NEW — .gitignored except schema.sql
│  │  ├─ schema.sql                                NEW — SQLite schema (FTS5)
│  │  └─ index.db                                  GITIGNORED — built locally
│  ├─ core/
│  │  ├─ library/
│  │  │  ├─ __init__.py                            NEW
│  │  │  ├─ db.py                                  NEW — sqlite connection + schema bootstrap
│  │  │  ├─ validator.py                           NEW — Elementor JSON schema check
│  │  │  ├─ extractor.py                           NEW — structural metadata extraction
│  │  │  ├─ categorizer.py                         NEW — heuristic category detection
│  │  │  └─ search.py                              NEW — hybrid SQL + FTS5 search
│  │  └─ normalizer/
│  │     ├─ __init__.py                            NEW
│  │     ├─ color_distance.py                      NEW — LAB ΔE math
│  │     ├─ passes.py                              NEW — six transform passes
│  │     ├─ diff.py                                NEW — diff report assembly
│  │     └─ normalize.py                           NEW — orchestrator
│  ├─ tools/
│  │  └─ template.py                               NEW — template_search/get/preview/list_categories
│  └─ server.py                                    MODIFY — register 4 template tools
├─ scripts/
│  ├─ build_index.py                               NEW — Stage B indexer CLI
│  └─ verify_library.py                            NEW — re-validate library + report
└─ tests/
   ├─ fixtures/
   │  ├─ templates/                                NEW — small subset for tests
   │  │  ├─ hero-simple.json                       NEW
   │  │  ├─ features-3col-icons.json               NEW
   │  │  ├─ pricing-table.json                     NEW
   │  │  └─ testimonial.json                       NEW
   │  ├─ profiles/
   │  │  └─ stacks-western.json                    NEW — profile used in golden tests
   │  └─ expected/                                 NEW — golden normalized outputs
   │     ├─ hero-simple__stacks-western.json
   │     ├─ features-3col-icons__stacks-western.json
   │     └─ ...
   ├─ unit/
   │  ├─ test_library_db.py                        NEW
   │  ├─ test_library_validator.py                 NEW
   │  ├─ test_library_extractor.py                 NEW
   │  ├─ test_library_categorizer.py               NEW
   │  ├─ test_library_search.py                    NEW
   │  ├─ test_color_distance.py                    NEW
   │  ├─ test_normalizer_color.py                  NEW
   │  ├─ test_normalizer_font.py                   NEW
   │  ├─ test_normalizer_typography.py             NEW
   │  ├─ test_normalizer_layout_buttons.py         NEW
   │  ├─ test_normalizer_diff.py                   NEW
   │  ├─ test_normalize_golden.py                  NEW — golden fixture regression
   │  └─ test_tools_template.py                    NEW
   └─ integration/
      └─ test_normalize_apply.py                   NEW — normalize + section.add roundtrip
```

`mcp-server/elementor_mcp/data/index.db` is added to `.gitignore`. Only `schema.sql` is tracked.

---

## Conventions

- TDD per task: failing test → run (see fail) → minimal impl → run (see pass) → commit.
- Git config: `-c user.email="webcuahao@gmail.com" -c user.name="webcuahao"`.
- Commit format: Conventional commits with scope `mcp|infra|test|docs`. Footer: `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`.
- Branch: continue on `master`.
- All P1a + P1b-1 tests must remain green (85 PHPUnit / 52 pytest unit / 4 integration → growing).

---

## Task 1: SQLite schema + db helper

**Files:**
- Create: `mcp-server/elementor_mcp/data/schema.sql`
- Create: `mcp-server/elementor_mcp/core/library/__init__.py` (empty)
- Create: `mcp-server/elementor_mcp/core/library/db.py`
- Test: `mcp-server/tests/unit/test_library_db.py`
- Modify: `.gitignore` — already has `mcp-server/elementor_mcp/data/index.db`, no change.

`db.py` opens a `sqlite3.Connection`, ensures schema is applied (CREATE TABLE IF NOT EXISTS via running `schema.sql`), and returns the connection. FTS5 is mandatory; if SQLite was compiled without it, the function raises a clear error.

- [ ] **Step 1: Write failing test**

`mcp-server/tests/unit/test_library_db.py`:

```python
import sqlite3

import pytest

from elementor_mcp.core.library.db import ensure_schema, open_db


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
    # Simulate a SQLite build without FTS5 by patching the probe.
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
```

- [ ] **Step 2: Run, confirm fail**

```bash
cd mcp-server && uv run pytest tests/unit/test_library_db.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `data/schema.sql`**

```sql
-- Elementor MCP template library — SQLite schema (Stage B + FTS5)
CREATE TABLE IF NOT EXISTS templates (
    id              TEXT PRIMARY KEY,
    path            TEXT NOT NULL,
    category        TEXT,
    source          TEXT NOT NULL DEFAULT 'builtin',
    status          TEXT NOT NULL DEFAULT 'valid',
    widgets_used    TEXT,         -- JSON array
    columns_max     INTEGER,
    image_count     INTEGER DEFAULT 0,
    has_form        INTEGER DEFAULT 0,
    has_carousel    INTEGER DEFAULT 0,
    has_video       INTEGER DEFAULT 0,
    dominant_colors TEXT,         -- JSON array of hex
    font_families   TEXT,         -- JSON array
    complexity      INTEGER DEFAULT 0,
    is_responsive   INTEGER DEFAULT 0,
    width_mode      TEXT,
    preview_url     TEXT,
    description     TEXT,
    use_cases       TEXT,         -- JSON
    style_tags      TEXT,         -- JSON
    industries      TEXT,         -- JSON
    color_scheme    TEXT,
    augmented       INTEGER NOT NULL DEFAULT 0,
    schema_version  TEXT,
    validated_at    TEXT,
    imported_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_templates_category   ON templates(category);
CREATE INDEX IF NOT EXISTS idx_templates_source     ON templates(source);
CREATE INDEX IF NOT EXISTS idx_templates_has_image  ON templates(image_count);

CREATE VIRTUAL TABLE IF NOT EXISTS templates_fts USING fts5(
    id UNINDEXED,
    description,
    use_cases,
    style_tags,
    industries,
    content='templates'
);
```

- [ ] **Step 4: Implement `core/library/__init__.py`** (empty file)

```python
```

- [ ] **Step 5: Implement `core/library/db.py`**

```python
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
```

- [ ] **Step 6: Run tests, confirm pass**

```bash
uv run pytest tests/unit/test_library_db.py -v && uv run ruff check .
```

Expected: 4 green + ruff clean.

- [ ] **Step 7: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/data/schema.sql mcp-server/elementor_mcp/core/library/__init__.py mcp-server/elementor_mcp/core/library/db.py mcp-server/tests/unit/test_library_db.py
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "feat(mcp): library index database (SQLite + FTS5)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Template JSON validator

**Files:**
- Create: `mcp-server/elementor_mcp/core/library/validator.py`
- Create: `mcp-server/tests/fixtures/templates/hero-simple.json`
- Test: `mcp-server/tests/unit/test_library_validator.py`

Validates an Elementor section template JSON. Returns `{ok, errors, warnings}` matching the Profile_Schema convention.

Valid template top-level shape (from section-express): `{"content": [section, …], "page_settings": {...}, "version": "0.4", "title": "...", "type": "section"}`.

- [ ] **Step 1: Create fixture `mcp-server/tests/fixtures/templates/hero-simple.json`**

```json
{
  "content": [{
    "id": "abc12345",
    "elType": "section",
    "settings": {"_title": "Hero", "background_background": "classic", "background_color": "#000000"},
    "elements": [{
      "id": "col10001",
      "elType": "column",
      "settings": {"_column_size": 100},
      "elements": [{
        "id": "wid10001",
        "elType": "widget",
        "widgetType": "heading",
        "settings": {"title": "Welcome", "typography_font_family": "Inter", "title_color": "#FFFFFF"},
        "elements": []
      }, {
        "id": "wid10002",
        "elType": "widget",
        "widgetType": "button",
        "settings": {"text": "Shop", "background_color": "#FF0000"},
        "elements": []
      }]
    }]
  }],
  "page_settings": {},
  "version": "0.4",
  "title": "Hero Simple",
  "type": "section"
}
```

- [ ] **Step 2: Write failing test**

`mcp-server/tests/unit/test_library_validator.py`:

```python
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
```

- [ ] **Step 3: Run, confirm fail**

```bash
uv run pytest tests/unit/test_library_validator.py -v
```

- [ ] **Step 4: Implement `core/library/validator.py`**

```python
from typing import Any

_TOP_LEVEL = {"content", "page_settings", "version", "title", "type"}


def validate_template(data: Any) -> dict:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        return {"ok": False, "errors": ["template must be a JSON object"], "warnings": []}

    content = data.get("content")
    if not isinstance(content, list):
        errors.append("missing or invalid 'content' (must be array of sections)")
    else:
        for i, section in enumerate(content):
            if not isinstance(section, dict):
                errors.append(f"content[{i}] is not an object")
                continue
            if not section.get("id"):
                errors.append(f"content[{i}] missing 'id'")
            if not section.get("elType"):
                errors.append(f"content[{i}] missing 'elType'")
            if not isinstance(section.get("elements", []), list):
                errors.append(f"content[{i}].elements must be an array")

    for k in data.keys():
        if k not in _TOP_LEVEL:
            warnings.append(f"unknown top-level key: '{k}'")

    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}
```

- [ ] **Step 5: Run, confirm pass**

```bash
uv run pytest tests/unit/test_library_validator.py -v && uv run ruff check .
```

Expected: 5 green + ruff clean.

- [ ] **Step 6: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/core/library/validator.py mcp-server/tests/fixtures/templates/hero-simple.json mcp-server/tests/unit/test_library_validator.py
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "feat(mcp): template JSON validator

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Structural metadata extractor

**Files:**
- Create: `mcp-server/elementor_mcp/core/library/extractor.py`
- Create: 3 more fixture templates: `features-3col-icons.json`, `pricing-table.json`, `testimonial.json`
- Test: `mcp-server/tests/unit/test_library_extractor.py`

Walks the template's `content` array and pulls out: widgets used (unique), max column count, image count, has_form, has_carousel, has_video, dominant colors (hex strings collected from `*_color` keys), font families.

- [ ] **Step 1: Create 3 more fixtures**

`mcp-server/tests/fixtures/templates/features-3col-icons.json`:

```json
{
  "content": [{
    "id": "feat0001",
    "elType": "section",
    "settings": {"structure": "33"},
    "elements": [
      {"id": "col0001", "elType": "column", "settings": {"_column_size": 33}, "elements": [
        {"id": "ico0001", "elType": "widget", "widgetType": "icon-box", "settings": {"title_text": "Fast", "icon_primary_color": "#FF0000"}, "elements": []}
      ]},
      {"id": "col0002", "elType": "column", "settings": {"_column_size": 33}, "elements": [
        {"id": "ico0002", "elType": "widget", "widgetType": "icon-box", "settings": {"title_text": "Secure", "icon_primary_color": "#00FF00"}, "elements": []}
      ]},
      {"id": "col0003", "elType": "column", "settings": {"_column_size": 33}, "elements": [
        {"id": "ico0003", "elType": "widget", "widgetType": "icon-box", "settings": {"title_text": "Cheap", "icon_primary_color": "#0000FF"}, "elements": []}
      ]}
    ]
  }],
  "version": "0.4",
  "title": "3-col features",
  "type": "section"
}
```

`mcp-server/tests/fixtures/templates/pricing-table.json`:

```json
{
  "content": [{
    "id": "pric0001",
    "elType": "section",
    "settings": {},
    "elements": [{"id": "pcol001", "elType": "column", "settings": {"_column_size": 100}, "elements": [
      {"id": "ptbl001", "elType": "widget", "widgetType": "price-table", "settings": {"heading": "Pro Plan", "currency_symbol": "$", "price": "29", "typography_font_family": "Manrope"}, "elements": []}
    ]}]
  }],
  "version": "0.4",
  "title": "Pricing",
  "type": "section"
}
```

`mcp-server/tests/fixtures/templates/testimonial.json`:

```json
{
  "content": [{
    "id": "test0001",
    "elType": "section",
    "settings": {},
    "elements": [{"id": "tcol001", "elType": "column", "settings": {"_column_size": 100}, "elements": [
      {"id": "tquote1", "elType": "widget", "widgetType": "testimonial", "settings": {"content": "It works great!", "name": "Jane Doe", "title_color": "#222222"}, "elements": []}
    ]}]
  }],
  "version": "0.4",
  "title": "Testimonial",
  "type": "section"
}
```

- [ ] **Step 2: Write failing test**

`mcp-server/tests/unit/test_library_extractor.py`:

```python
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
```

- [ ] **Step 3: Run, confirm fail**

```bash
uv run pytest tests/unit/test_library_extractor.py -v
```

- [ ] **Step 4: Implement `core/library/extractor.py`**

```python
import re
from typing import Any


_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_COLOR_KEY_RE = re.compile(r"(_color$|^background_color$)")


def extract_metadata(template: dict) -> dict:
    """Walk a template JSON and return structural metadata."""
    widgets: set[str] = set()
    colors: set[str] = set()
    fonts: set[str] = set()
    image_count = 0
    has_form = 0
    has_carousel = 0
    has_video = 0
    columns_max = 0

    def visit_section(section: dict) -> None:
        nonlocal columns_max
        cols = [e for e in section.get("elements", []) if e.get("elType") == "column"]
        if cols:
            columns_max = max(columns_max, len(cols))
        for child in section.get("elements", []):
            visit(child)

    def visit(node: dict) -> None:
        nonlocal image_count, has_form, has_carousel, has_video
        el_type = node.get("elType")
        if el_type == "widget":
            wt = node.get("widgetType") or ""
            widgets.add(wt)
            if wt == "image":
                image_count += 1
            if wt in {"form", "shortcode-form"}:
                has_form = 1
            if "carousel" in wt or wt == "image-carousel":
                has_carousel = 1
            if "video" in wt:
                has_video = 1
        # Collect colors + fonts from any node's settings
        for k, v in (node.get("settings") or {}).items():
            if isinstance(v, str):
                if _COLOR_KEY_RE.search(k) and _COLOR_RE.match(v):
                    colors.add(v.upper())
                if k == "typography_font_family" and v:
                    fonts.add(v)
        for child in node.get("elements", []) or []:
            visit(child)

    for section in template.get("content", []):
        visit_section(section)
        visit(section)

    return {
        "widgets_used": sorted(widgets),
        "columns_max":  columns_max,
        "image_count":  image_count,
        "has_form":     has_form,
        "has_carousel": has_carousel,
        "has_video":    has_video,
        "dominant_colors": sorted(colors),
        "font_families":   sorted(fonts),
    }
```

- [ ] **Step 5: Run, confirm pass**

```bash
uv run pytest tests/unit/test_library_extractor.py -v && uv run ruff check .
```

Expected: 4 green + ruff clean.

- [ ] **Step 6: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/core/library/extractor.py mcp-server/tests/fixtures/templates/features-3col-icons.json mcp-server/tests/fixtures/templates/pricing-table.json mcp-server/tests/fixtures/templates/testimonial.json mcp-server/tests/unit/test_library_extractor.py
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "feat(mcp): template structural metadata extractor

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Heuristic category classifier

**Files:**
- Create: `mcp-server/elementor_mcp/core/library/categorizer.py`
- Test: `mcp-server/tests/unit/test_library_categorizer.py`

Given a template + already-extracted metadata, infer a category: `hero`, `features`, `pricing`, `testimonial`, `contact`, `footer`, `navbar`, `social-proof`, `cta`, `section-general` (fallback).

Heuristics (in order, first match wins):
- form widget present → `contact`
- price-table widget → `pricing`
- testimonial widget → `testimonial`
- nav-menu widget → `navbar`
- icon-box widgets + columns_max >= 3 → `features`
- heading + button + (image or background_image) + columns_max == 1 → `hero`
- multiple image widgets in a single section, no other content → `social-proof`
- text widget with multi-line links (>3 hrefs) → `footer`
- single heading + single button → `cta`
- else → `section-general`

- [ ] **Step 1: Write failing test**

`mcp-server/tests/unit/test_library_categorizer.py`:

```python
import json
from pathlib import Path

from elementor_mcp.core.library.categorizer import categorize
from elementor_mcp.core.library.extractor import extract_metadata


FIX = Path(__file__).parent.parent / "fixtures" / "templates"


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text())


def test_hero_simple_classified_as_hero():
    tpl = _load("hero-simple.json")
    assert categorize(tpl, extract_metadata(tpl)) == "hero"


def test_features_classified_as_features():
    tpl = _load("features-3col-icons.json")
    assert categorize(tpl, extract_metadata(tpl)) == "features"


def test_pricing_classified_as_pricing():
    tpl = _load("pricing-table.json")
    assert categorize(tpl, extract_metadata(tpl)) == "pricing"


def test_testimonial_classified_as_testimonial():
    tpl = _load("testimonial.json")
    assert categorize(tpl, extract_metadata(tpl)) == "testimonial"


def test_unknown_falls_back_to_section_general():
    blank = {"content": [{"id": "x", "elType": "section", "settings": {}, "elements": []}]}
    assert categorize(blank, extract_metadata(blank)) == "section-general"
```

- [ ] **Step 2: Run, confirm fail**

```bash
uv run pytest tests/unit/test_library_categorizer.py -v
```

- [ ] **Step 3: Implement `core/library/categorizer.py`**

```python
def categorize(template: dict, meta: dict) -> str:
    widgets = set(meta.get("widgets_used") or [])
    columns_max = meta.get("columns_max", 0)
    image_count = meta.get("image_count", 0)

    if widgets & {"form", "shortcode-form"}:
        return "contact"
    if "price-table" in widgets:
        return "pricing"
    if "testimonial" in widgets:
        return "testimonial"
    if "nav-menu" in widgets:
        return "navbar"
    if "icon-box" in widgets and columns_max >= 3:
        return "features"
    if {"heading", "button"} <= widgets and columns_max <= 1:
        return "hero"
    if image_count >= 4 and not (widgets - {"image"}):
        return "social-proof"
    if {"heading", "button"} <= widgets:
        return "cta"
    return "section-general"
```

- [ ] **Step 4: Run, confirm pass**

```bash
uv run pytest tests/unit/test_library_categorizer.py -v && uv run ruff check .
```

Expected: 5 green + ruff clean.

- [ ] **Step 5: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/core/library/categorizer.py mcp-server/tests/unit/test_library_categorizer.py
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "feat(mcp): heuristic template category classifier

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: build_index.py CLI

**Files:**
- Create: `mcp-server/scripts/build_index.py`
- Test: `mcp-server/tests/unit/test_build_index_cli.py`

Walks a directory of templates, validates + extracts + categorizes each, inserts into the SQLite index. Idempotent (UPSERT). Prints progress.

- [ ] **Step 1: Write failing test**

`mcp-server/tests/unit/test_build_index_cli.py`:

```python
import json
import sqlite3
from pathlib import Path

from elementor_mcp.scripts.build_index import build_index


def test_build_index_inserts_rows(tmp_path):
    src = tmp_path / "templates"
    src.mkdir()
    # Copy 2 fixtures into src/
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
    # On re-run, all rows are upserted (still 1 final row)
    assert stats["inserted"] == 1
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
    assert count == 1
    conn.close()
```

Note: tests import from `elementor_mcp.scripts.build_index` — to enable that the scripts dir needs to be importable. We'll make it a sub-package of elementor_mcp:

- [ ] **Step 2: Move scripts under the package**

Rather than `mcp-server/scripts/build_index.py`, create:
- `mcp-server/elementor_mcp/scripts/__init__.py` (empty)
- `mcp-server/elementor_mcp/scripts/build_index.py`

This makes `elementor_mcp.scripts.build_index` importable from tests AND keeps the CLI runnable via `python -m elementor_mcp.scripts.build_index`.

- [ ] **Step 3: Run test, confirm fail**

```bash
uv run pytest tests/unit/test_build_index_cli.py -v
```

- [ ] **Step 4: Implement `mcp-server/elementor_mcp/scripts/__init__.py`** (empty)

```python
```

- [ ] **Step 5: Implement `mcp-server/elementor_mcp/scripts/build_index.py`**

```python
"""Stage B indexer — walk a directory of Elementor template JSONs, validate,
extract metadata, classify category, and upsert into the SQLite index."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..core.library.categorizer import categorize
from ..core.library.db import open_db
from ..core.library.extractor import extract_metadata
from ..core.library.validator import validate_template


def build_index(*, src_dir: Path, db_path: Path) -> dict:
    inserted = 0
    rejected = 0
    conn = open_db(db_path)
    now = datetime.now(timezone.utc).isoformat()

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
        template_id = json_path.stem  # filename without .json

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
```

- [ ] **Step 6: Run, confirm pass**

```bash
uv run pytest tests/unit/test_build_index_cli.py -v && uv run ruff check .
```

Expected: 3 green + ruff clean.

- [ ] **Step 7: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/scripts/__init__.py mcp-server/elementor_mcp/scripts/build_index.py mcp-server/tests/unit/test_build_index_cli.py
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "feat(mcp): build_index CLI — Stage B indexer

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Hybrid search (SQL filter + FTS5 rank) + `template.*` MCP tools

**Files:**
- Create: `mcp-server/elementor_mcp/core/library/search.py`
- Create: `mcp-server/elementor_mcp/tools/template.py`
- Modify: `mcp-server/elementor_mcp/server.py` — register 4 tools
- Test: `mcp-server/tests/unit/test_library_search.py`
- Test: `mcp-server/tests/unit/test_tools_template.py`

`search.py` exposes `search(conn, query, *, category=None, has_image=None, k=5)` → list of `{id, path, category, score, ...}`. When query is empty, falls back to plain SQL filter. When query is non-empty, joins FTS5 ranking against the SQL filter.

P1b-2 ships keyword-only search (FTS5). Vector/semantic ranking is P2.

4 MCP tools:
- `template_search(query, category?, has_image?, k=5)`
- `template_get(template_id)` — return full row + JSON file content
- `template_preview(template_id)` — return preview URL (from `preview_url` column, often empty in P1b-2)
- `template_list_categories()` — distinct list with counts

- [ ] **Step 1: Write failing tests**

`mcp-server/tests/unit/test_library_search.py`:

```python
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
    # Add some descriptions to enable FTS hits (real descriptions come from Stage C / AI)
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE templates SET description=?, use_cases=? WHERE id=?",
                 ("clean modern hero with bold heading", json.dumps(["landing", "saas"]), "hero-simple"))
    conn.execute("INSERT INTO templates_fts(id, description, use_cases) "
                 "SELECT id, description, use_cases FROM templates WHERE description IS NOT NULL")
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
```

`mcp-server/tests/unit/test_tools_template.py`:

```python
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

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
    # preview_url is empty in Stage B; returning None or empty is acceptable.
    assert res.data.get("preview_url") in (None, "", "null")
```

- [ ] **Step 2: Run, confirm fail**

```bash
uv run pytest tests/unit/test_library_search.py tests/unit/test_tools_template.py -v
```

- [ ] **Step 3: Implement `core/library/search.py`**

```python
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
            try:
                d[key] = json.loads(v)
            except json.JSONDecodeError:
                pass
    return d
```

- [ ] **Step 4: Implement `tools/template.py`**

```python
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
```

- [ ] **Step 5: Register tools in `server.py`**

Add the following to `_list()` (after `image_describe_slot`):

```python
            Tool(name="template_search",
                 description="Search the template library by query + filters. Returns top-k template metadata rows.",
                 inputSchema={"type":"object","properties":{
                     "query":{"type":"string"},
                     "category":{"type":"string"},
                     "has_image":{"type":"boolean"},
                     "k":{"type":"integer"},
                 },"additionalProperties":False}),
            Tool(name="template_get",
                 description="Get a template's full JSON + indexed metadata by id.",
                 inputSchema={"type":"object","properties":{
                     "template_id":{"type":"string"},
                 },"required":["template_id"],"additionalProperties":False}),
            Tool(name="template_preview",
                 description="Get a template's preview URL (may be null in Stage B).",
                 inputSchema={"type":"object","properties":{
                     "template_id":{"type":"string"},
                 },"required":["template_id"],"additionalProperties":False}),
            Tool(name="template_list_categories",
                 description="List all distinct template categories with counts.",
                 inputSchema={"type":"object","properties":{},"additionalProperties":False}),
```

Inside `_call()`, near the top of the function (alongside other imports), add:

```python
        from pathlib import Path as _Path
        from .tools.template import (
            template_get, template_list_categories, template_preview, template_search,
        )
        _DB_PATH = _Path(__file__).resolve().parent / "data" / "index.db"
        _SRC_DIR = _Path(__file__).resolve().parent.parent.parent / "section-express-libr" / "pack" / "JSON Files"
```

Append to the elif chain:

```python
        elif name == "template_search":
            result = template_search(db_path=_DB_PATH, src_dir=_SRC_DIR, **arguments)
        elif name == "template_get":
            result = template_get(db_path=_DB_PATH, src_dir=_SRC_DIR, **arguments)
        elif name == "template_preview":
            result = template_preview(db_path=_DB_PATH, **arguments)
        elif name == "template_list_categories":
            result = template_list_categories(db_path=_DB_PATH)
```

- [ ] **Step 6: Run all tests + ruff**

```bash
uv run pytest tests/unit -v && uv run ruff check .
```

Expected: 9 new green (4 search + 5 template tools) on top of existing. Ruff clean.

- [ ] **Step 7: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/core/library/search.py mcp-server/elementor_mcp/tools/template.py mcp-server/elementor_mcp/server.py mcp-server/tests/unit/test_library_search.py mcp-server/tests/unit/test_tools_template.py
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "feat(mcp): hybrid template search + template.* MCP tools (4 tools)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Run build_index against the real section-express library

**Files:**
- Modify: `.gitignore` — add `mcp-server/elementor_mcp/data/index.db`

This task only adds a `.gitignore` entry and provides the user with a one-liner to build the real index. The committed schema.sql is the only artifact tracked; index.db is per-developer.

- [ ] **Step 1: Append to `.gitignore`**

```
mcp-server/elementor_mcp/data/index.db
mcp-server/elementor_mcp/data/index.db-shm
mcp-server/elementor_mcp/data/index.db-wal
```

- [ ] **Step 2: Run the indexer against the real library**

```bash
cd mcp-server && uv run python -m elementor_mcp.scripts.build_index \
  --src "../section-express-libr/pack/JSON Files"
```

Expected output: `inserted=N rejected=M` where N is around 2,000+ and M is small (templates that aren't valid Elementor section files, like the `Help/` subdirectory's text files).

If errors are reported, paste them and STOP. Otherwise note the counts.

- [ ] **Step 3: Sanity-check via `template_list_categories`**

```bash
uv run python -c "
from pathlib import Path
from elementor_mcp.tools.template import template_list_categories
p = Path('elementor_mcp/data/index.db')
r = template_list_categories(db_path=p)
print(r.model_dump_json(indent=2))
"
```

Expected: a JSON envelope with `categories` showing counts per detected category (`section-general` likely dominates because heuristics are conservative; that's fine for v1).

- [ ] **Step 4: Commit (gitignore only)**

```bash
cd .. && git add .gitignore
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "chore: gitignore generated index.db

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Color distance utility (LAB ΔE)

**Files:**
- Modify: `mcp-server/pyproject.toml` — add `colormath>=3.0`
- Create: `mcp-server/elementor_mcp/core/normalizer/__init__.py` (empty)
- Create: `mcp-server/elementor_mcp/core/normalizer/color_distance.py`
- Test: `mcp-server/tests/unit/test_color_distance.py`

Returns ΔE_2000 between two hex colors via colormath's `sRGB → LAB` conversion.

- [ ] **Step 1: Add `colormath` to pyproject.toml**

In `dependencies = [...]` append `"colormath>=3.0"`. Then:

```bash
cd mcp-server && uv pip install -e ".[dev]"
```

- [ ] **Step 2: Write failing test**

`mcp-server/tests/unit/test_color_distance.py`:

```python
import pytest

from elementor_mcp.core.normalizer.color_distance import delta_e


def test_identical_hex_delta_zero():
    assert delta_e("#FF0000", "#FF0000") == pytest.approx(0, abs=0.01)


def test_close_colors_small_delta():
    # Very close reds — should be < 5
    assert delta_e("#FF0000", "#FE0101") == pytest.approx(0, abs=2.0)


def test_far_colors_large_delta():
    # Red vs cyan — should be very large
    assert delta_e("#FF0000", "#00FFFF") > 60


def test_case_insensitive_hex():
    assert delta_e("#ff0000", "#FF0000") == pytest.approx(0, abs=0.01)


def test_invalid_hex_raises():
    with pytest.raises(ValueError):
        delta_e("not-a-color", "#FF0000")
```

- [ ] **Step 3: Run, confirm fail**

```bash
uv run pytest tests/unit/test_color_distance.py -v
```

- [ ] **Step 4: Implement `core/normalizer/__init__.py`** (empty)

```python
```

- [ ] **Step 5: Implement `core/normalizer/color_distance.py`**

```python
import re

from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000
from colormath.color_objects import LabColor, sRGBColor


_HEX_RE = re.compile(r"^#?[0-9A-Fa-f]{6}$")


def _to_lab(hex_color: str) -> LabColor:
    if not _HEX_RE.match(hex_color):
        raise ValueError(f"invalid hex color: {hex_color!r}")
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return convert_color(sRGBColor(r, g, b), LabColor)


def delta_e(a: str, b: str) -> float:
    """Perceptual color distance (ΔE2000) between two hex colors."""
    return float(delta_e_cie2000(_to_lab(a), _to_lab(b)))
```

- [ ] **Step 6: Run, confirm pass**

```bash
uv run pytest tests/unit/test_color_distance.py -v && uv run ruff check .
```

Expected: 5 green + ruff clean.

- [ ] **Step 7: Commit**

```bash
cd .. && git add mcp-server/pyproject.toml mcp-server/elementor_mcp/core/normalizer/__init__.py mcp-server/elementor_mcp/core/normalizer/color_distance.py mcp-server/tests/unit/test_color_distance.py
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "feat(mcp): LAB ΔE color distance utility

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 9: Normalizer Pass 1 — color mapping

**Files:**
- Create: `mcp-server/elementor_mcp/core/normalizer/passes.py`
- Create: `mcp-server/tests/fixtures/profiles/stacks-western.json`
- Test: `mcp-server/tests/unit/test_normalizer_color.py`

Pass 1: walk every `settings` dict in the section tree; for every key ending in `_color` (`title_color`, `background_color`, `*_text_color`, etc.), match its value against the profile palette via ΔE. Three tiers:
- ΔE < 5  → SNAP: move value to `__globals__[key] = "globals/colors?id=<slot>"`, remove the original key.
- ΔE 5–15 → WARN: keep value as-is, record in diff report.
- ΔE > 15 → OVERFLOW: keep value, record for later promotion to Kit `custom_colors` (handled in Pass 1.5).

- [ ] **Step 1: Create fixture `stacks-western.json`**

```json
{
  "name": "Stacks-Western",
  "colors": {
    "primary":    "#8B4513",
    "secondary":  "#B87333",
    "text":       "#2C1810",
    "accent":     "#B22222",
    "background": "#FAF5E9",
    "custom":     []
  },
  "fonts": {
    "primary":   {"family": "Playfair Display", "source": "google", "weights": [400, 700, 900]},
    "secondary": {"family": "Inter", "source": "google", "weights": [400, 500, 600]}
  },
  "typography": {
    "h1":   {"size": 64, "mobile": 36, "weight": 900, "line_height": 1.05},
    "h2":   {"size": 48, "mobile": 32, "weight": 700, "line_height": 1.15},
    "h3":   {"size": 32, "mobile": 22, "weight": 700, "line_height": 1.25},
    "body": {"size": 17, "mobile": 15, "weight": 400, "line_height": 1.7},
    "small":{"size": 14, "mobile": 12, "weight": 500, "line_height": 1.5}
  },
  "layout": {
    "container_width":         1280,
    "content_width":           1200,
    "section_padding":         {"top": 100, "bottom": 100},
    "section_padding_mobile":  {"top": 48, "bottom": 48}
  },
  "breakpoints": {"mobile": 767, "desktop": 1280},
  "buttons": {"border_radius": 2, "padding_x": 36, "padding_y": 18}
}
```

- [ ] **Step 2: Write failing test**

`mcp-server/tests/unit/test_normalizer_color.py`:

```python
import json
from pathlib import Path

from elementor_mcp.core.normalizer.passes import pass1_colors


FIX = Path(__file__).parent.parent / "fixtures"


def _profile():
    return json.loads((FIX / "profiles" / "stacks-western.json").read_text())


def test_pass1_snaps_exact_match_to_global():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"title_color": "#8B4513"},
        "elements": [],
    }
    out, diff = pass1_colors(section, _profile())
    assert out["settings"].get("title_color") is None
    assert out["settings"]["__globals__"]["title_color"] == "globals/colors?id=primary"
    assert len(diff["colors_remapped"]) == 1
    assert diff["colors_remapped"][0]["to"] == "primary"


def test_pass1_snaps_near_match_to_global():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"title_color": "#8C4614"},  # near primary
        "elements": [],
    }
    out, diff = pass1_colors(section, _profile())
    assert out["settings"]["__globals__"]["title_color"] == "globals/colors?id=primary"
    assert diff["colors_remapped"][0]["delta_e"] < 5


def test_pass1_records_overflow_for_far_color():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"title_color": "#00FF00"},  # neon green, far from any profile color
        "elements": [],
    }
    out, diff = pass1_colors(section, _profile())
    # Color is kept verbatim
    assert out["settings"]["title_color"] == "#00FF00"
    assert "__globals__" not in out["settings"] or "title_color" not in out["settings"]["__globals__"]
    # And recorded for promotion
    assert "#00FF00" in [c["hex"] for c in diff["colors_overflow"]]


def test_pass1_recurses_into_elements():
    section = {
        "id": "s1", "elType": "section",
        "settings": {},
        "elements": [{
            "id": "w1", "elType": "widget", "widgetType": "heading",
            "settings": {"title_color": "#B22222"},
            "elements": [],
        }],
    }
    out, _ = pass1_colors(section, _profile())
    widget = out["elements"][0]
    assert widget["settings"]["__globals__"]["title_color"] == "globals/colors?id=accent"


def test_pass1_handles_mid_tier_warn():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"title_color": "#A0522D"},  # similar-but-not-snap to primary
        "elements": [],
    }
    out, diff = pass1_colors(section, _profile())
    # Should keep the color as-is and warn
    assert out["settings"].get("title_color") == "#A0522D"
    warnings = diff.get("colors_warned", [])
    assert any(w["from"] == "#A0522D" for w in warnings)
```

- [ ] **Step 3: Run, confirm fail**

```bash
uv run pytest tests/unit/test_normalizer_color.py -v
```

- [ ] **Step 4: Implement `core/normalizer/passes.py` (pass1 only — other passes added in later tasks)**

```python
import copy
import re

from .color_distance import delta_e

_COLOR_KEY_RE = re.compile(r"(_color$|^background_color$|_text_color$)")

DELTA_SNAP = 5.0
DELTA_ASK = 15.0


def _profile_color_map(profile: dict) -> dict[str, str]:
    """Map each named profile color slot → hex."""
    colors = profile.get("colors") or {}
    out = {}
    for slot in ("primary", "secondary", "text", "accent", "background"):
        if isinstance(colors.get(slot), str):
            out[slot] = colors[slot].upper()
    for item in (colors.get("custom") or []):
        name = item.get("name")
        val = item.get("value")
        if name and isinstance(val, str):
            out[name] = val.upper()
    return out


def _classify(hex_color: str, palette: dict[str, str]) -> tuple[str, str | None, float]:
    """Returns (verdict, slot_id, delta_e). verdict ∈ {snap, warn, overflow}."""
    best_slot = None
    best_delta = float("inf")
    for slot, palette_hex in palette.items():
        d = delta_e(hex_color, palette_hex)
        if d < best_delta:
            best_delta = d
            best_slot = slot
    if best_delta < DELTA_SNAP:
        return ("snap", best_slot, best_delta)
    if best_delta < DELTA_ASK:
        return ("warn", best_slot, best_delta)
    return ("overflow", None, best_delta)


def pass1_colors(section: dict, profile: dict) -> tuple[dict, dict]:
    """Walk the section, snap colors to profile globals, return (new_section, diff)."""
    out = copy.deepcopy(section)
    palette = _profile_color_map(profile)
    diff = {
        "colors_remapped": [],
        "colors_warned":   [],
        "colors_overflow": [],
    }

    def visit_settings(settings: dict) -> None:
        if not isinstance(settings, dict):
            return
        for key in list(settings.keys()):
            if not _COLOR_KEY_RE.search(key):
                continue
            value = settings[key]
            if not isinstance(value, str) or not value.startswith("#"):
                continue
            verdict, slot, d = _classify(value.upper(), palette)
            if verdict == "snap":
                globals_dict = settings.setdefault("__globals__", {})
                globals_dict[key] = f"globals/colors?id={slot}"
                del settings[key]
                diff["colors_remapped"].append({
                    "key": key, "from": value.upper(), "to": slot, "delta_e": round(d, 2),
                })
            elif verdict == "warn":
                diff["colors_warned"].append({
                    "key": key, "from": value.upper(), "nearest": slot, "delta_e": round(d, 2),
                })
            else:
                if value.upper() not in [c["hex"] for c in diff["colors_overflow"]]:
                    diff["colors_overflow"].append({"key": key, "hex": value.upper()})

    def visit(node: dict) -> None:
        visit_settings(node.get("settings"))
        for child in node.get("elements", []) or []:
            visit(child)

    visit(out)
    return out, diff
```

- [ ] **Step 5: Run, confirm pass**

```bash
uv run pytest tests/unit/test_normalizer_color.py -v && uv run ruff check .
```

Expected: 5 green + ruff clean.

- [ ] **Step 6: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/core/normalizer/passes.py mcp-server/tests/fixtures/profiles/stacks-western.json mcp-server/tests/unit/test_normalizer_color.py
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "feat(mcp): normalizer pass 1 — color mapping with LAB ΔE tier policy

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 10: Normalizer Pass 2 — font mapping + Pass 3 — typography size snapping

**Files:**
- Modify: `mcp-server/elementor_mcp/core/normalizer/passes.py` — add pass2_fonts + pass3_typography_sizes
- Test: `mcp-server/tests/unit/test_normalizer_font.py`
- Test: `mcp-server/tests/unit/test_normalizer_typography.py`

Pass 2: for `typography_font_family`, exact-match against `profile.fonts.primary.family` → `globals/typography?id=primary`; against secondary → `globals/typography?id=secondary`. Unknown family is left in place (warned in diff).

Pass 3: for `typography_font_size`, classify by px:
- ≥ 56 → h1
- ≥ 40 → h2
- ≥ 28 → h3
- ≥ 18 → body
- else  → small

Map to the typography global at that level. Strip `typography_font_weight`, `typography_line_height` (Kit owns those). Mobile sibling key `typography_font_size_mobile` snaps to `profile.typography[level].mobile`.

- [ ] **Step 1: Write failing tests**

`mcp-server/tests/unit/test_normalizer_font.py`:

```python
import json
from pathlib import Path

from elementor_mcp.core.normalizer.passes import pass2_fonts


FIX = Path(__file__).parent.parent / "fixtures"


def _profile():
    return json.loads((FIX / "profiles" / "stacks-western.json").read_text())


def test_pass2_maps_primary_font_to_global():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"typography_font_family": "Playfair Display"},
        "elements": [],
    }
    out, diff = pass2_fonts(section, _profile())
    assert out["settings"].get("typography_font_family") is None
    assert out["settings"]["__globals__"]["typography_typography"] == "globals/typography?id=primary"
    assert diff["fonts_remapped"][0]["to"] == "primary"


def test_pass2_maps_secondary_font_to_global():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"typography_font_family": "Inter"},
        "elements": [],
    }
    out, _ = pass2_fonts(section, _profile())
    assert out["settings"]["__globals__"]["typography_typography"] == "globals/typography?id=secondary"


def test_pass2_unknown_font_kept_and_warned():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"typography_font_family": "Comic Sans"},
        "elements": [],
    }
    out, diff = pass2_fonts(section, _profile())
    assert out["settings"].get("typography_font_family") == "Comic Sans"
    assert diff["fonts_warned"][0]["from"] == "Comic Sans"


def test_pass2_recurses():
    section = {
        "id": "s1", "elType": "section",
        "settings": {},
        "elements": [{
            "id": "w1", "elType": "widget", "widgetType": "heading",
            "settings": {"typography_font_family": "Playfair Display"},
            "elements": [],
        }],
    }
    out, _ = pass2_fonts(section, _profile())
    widget_globals = out["elements"][0]["settings"]["__globals__"]
    assert widget_globals["typography_typography"] == "globals/typography?id=primary"
```

`mcp-server/tests/unit/test_normalizer_typography.py`:

```python
import json
from pathlib import Path

from elementor_mcp.core.normalizer.passes import pass3_typography_sizes


FIX = Path(__file__).parent.parent / "fixtures"


def _profile():
    return json.loads((FIX / "profiles" / "stacks-western.json").read_text())


def test_pass3_classifies_h1_size():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"typography_font_size": {"unit": "px", "size": 72}},
        "elements": [],
    }
    out, diff = pass3_typography_sizes(section, _profile())
    assert "typography_font_size" not in out["settings"]
    assert "typography_font_weight" not in out["settings"]
    assert "typography_line_height" not in out["settings"]
    assert out["settings"]["__globals__"]["typography_typography"] == "globals/typography?id=h1"
    assert diff["sizes_snapped"][0]["to_level"] == "h1"


def test_pass3_classifies_body_size():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"typography_font_size": {"unit": "px", "size": 17}},
        "elements": [],
    }
    out, _ = pass3_typography_sizes(section, _profile())
    assert out["settings"]["__globals__"]["typography_typography"] == "globals/typography?id=body"


def test_pass3_classifies_small_size():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"typography_font_size": {"unit": "px", "size": 12}},
        "elements": [],
    }
    out, _ = pass3_typography_sizes(section, _profile())
    assert out["settings"]["__globals__"]["typography_typography"] == "globals/typography?id=small"


def test_pass3_skips_non_px_unit():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"typography_font_size": {"unit": "em", "size": 2}},
        "elements": [],
    }
    out, _ = pass3_typography_sizes(section, _profile())
    # Should not modify when unit is not px
    assert out["settings"]["typography_font_size"]["unit"] == "em"
```

- [ ] **Step 2: Run, confirm fail**

```bash
uv run pytest tests/unit/test_normalizer_font.py tests/unit/test_normalizer_typography.py -v
```

- [ ] **Step 3: Append to `passes.py`**

```python
def pass2_fonts(section: dict, profile: dict) -> tuple[dict, dict]:
    out = copy.deepcopy(section)
    fonts = profile.get("fonts") or {}
    primary = (fonts.get("primary") or {}).get("family") or ""
    secondary = (fonts.get("secondary") or {}).get("family") or ""
    diff = {"fonts_remapped": [], "fonts_warned": []}

    def visit_settings(settings: dict) -> None:
        if not isinstance(settings, dict):
            return
        fam = settings.get("typography_font_family")
        if not isinstance(fam, str) or not fam:
            return
        slot = None
        if fam == primary:    slot = "primary"
        elif fam == secondary: slot = "secondary"
        if slot:
            globals_dict = settings.setdefault("__globals__", {})
            globals_dict["typography_typography"] = f"globals/typography?id={slot}"
            del settings["typography_font_family"]
            diff["fonts_remapped"].append({"from": fam, "to": slot})
        else:
            diff["fonts_warned"].append({"from": fam, "nearest": None})

    def visit(node: dict) -> None:
        visit_settings(node.get("settings"))
        for child in node.get("elements", []) or []:
            visit(child)

    visit(out)
    return out, diff


def _classify_size_px(px: float) -> str:
    if px >= 56: return "h1"
    if px >= 40: return "h2"
    if px >= 28: return "h3"
    if px >= 18: return "body"
    return "small"


def pass3_typography_sizes(section: dict, profile: dict) -> tuple[dict, dict]:
    out = copy.deepcopy(section)
    diff = {"sizes_snapped": []}

    def visit_settings(settings: dict) -> None:
        if not isinstance(settings, dict):
            return
        fs = settings.get("typography_font_size")
        if not isinstance(fs, dict):
            return
        if fs.get("unit") != "px":
            return
        try:
            size_px = float(fs.get("size") or 0)
        except (TypeError, ValueError):
            return
        if size_px <= 0:
            return
        level = _classify_size_px(size_px)
        globals_dict = settings.setdefault("__globals__", {})
        globals_dict["typography_typography"] = f"globals/typography?id={level}"
        diff["sizes_snapped"].append({"px": size_px, "to_level": level})
        for k in ("typography_font_size", "typography_font_weight", "typography_line_height"):
            settings.pop(k, None)

    def visit(node: dict) -> None:
        visit_settings(node.get("settings"))
        for child in node.get("elements", []) or []:
            visit(child)

    visit(out)
    return out, diff
```

- [ ] **Step 4: Run, confirm pass**

```bash
uv run pytest tests/unit/test_normalizer_font.py tests/unit/test_normalizer_typography.py -v && uv run ruff check .
```

Expected: 8 green + ruff clean.

- [ ] **Step 5: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/core/normalizer/passes.py mcp-server/tests/unit/test_normalizer_font.py mcp-server/tests/unit/test_normalizer_typography.py
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "feat(mcp): normalizer passes 2 + 3 — font + typography size snapping

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 11: Normalizer Passes 4–6 — section padding + content width + button defaults

**Files:**
- Modify: `mcp-server/elementor_mcp/core/normalizer/passes.py` — add `pass4_layout` + `pass5_buttons`
- Test: `mcp-server/tests/unit/test_normalizer_layout_buttons.py`

Pass 4 (combined): on the top-level section's settings, snap `padding.top/bottom` to `profile.layout.section_padding.top/bottom` if within ±20px tolerance. Same for `padding_mobile` against `section_padding_mobile`. Snap `content_width.size` to `profile.layout.content_width` if delta ≤ 100px.

Pass 5: walk button widgets. For each `widget` where `widgetType == "button"`:
- Set `border_radius` to profile.buttons.border_radius (all 4 sides linked).
- Set `text_padding` to profile.buttons.padding_x / padding_y (linked = false, custom top/right/bottom/left).
- If a button has `button_background_color` or `background_color`, leave Pass 1 to handle.

- [ ] **Step 1: Write failing test**

`mcp-server/tests/unit/test_normalizer_layout_buttons.py`:

```python
import json
from pathlib import Path

from elementor_mcp.core.normalizer.passes import pass4_layout, pass5_buttons


FIX = Path(__file__).parent.parent / "fixtures"


def _profile():
    return json.loads((FIX / "profiles" / "stacks-western.json").read_text())


def test_pass4_snaps_section_padding_when_within_tolerance():
    # Profile expects top=100, bottom=100. Section has 110/95 → snap to 100/100.
    section = {
        "id": "s1", "elType": "section",
        "settings": {"padding": {"unit": "px", "top": "110", "right": "0", "bottom": "95", "left": "0", "isLinked": False}},
        "elements": [],
    }
    out, diff = pass4_layout(section, _profile())
    assert out["settings"]["padding"]["top"] == 100
    assert out["settings"]["padding"]["bottom"] == 100
    assert diff["padding_snapped"][0]["delta_top"] == 10


def test_pass4_leaves_padding_outside_tolerance():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"padding": {"unit": "px", "top": "300", "right": "0", "bottom": "300", "left": "0", "isLinked": False}},
        "elements": [],
    }
    out, diff = pass4_layout(section, _profile())
    assert out["settings"]["padding"]["top"] == "300"  # unchanged
    assert not any(p.get("snapped") for p in diff.get("padding_snapped", []))


def test_pass4_snaps_content_width():
    section = {
        "id": "s1", "elType": "section",
        "settings": {"content_width": {"unit": "px", "size": 1250}},
        "elements": [],
    }
    out, _ = pass4_layout(section, _profile())
    assert out["settings"]["content_width"]["size"] == 1200


def test_pass5_applies_button_defaults():
    section = {
        "id": "s1", "elType": "section",
        "settings": {},
        "elements": [{
            "id": "w1", "elType": "widget", "widgetType": "button",
            "settings": {"text": "Shop"},
            "elements": [],
        }],
    }
    out, diff = pass5_buttons(section, _profile())
    btn = out["elements"][0]["settings"]
    assert btn["border_radius"]["top"] == 2
    assert btn["text_padding"]["left"] == 36
    assert btn["text_padding"]["top"] == 18
    assert len(diff["buttons_styled"]) == 1


def test_pass5_does_not_touch_non_buttons():
    section = {
        "id": "s1", "elType": "section",
        "settings": {},
        "elements": [{
            "id": "w1", "elType": "widget", "widgetType": "heading",
            "settings": {"title": "X"},
            "elements": [],
        }],
    }
    out, diff = pass5_buttons(section, _profile())
    assert "border_radius" not in out["elements"][0]["settings"]
    assert diff["buttons_styled"] == []
```

- [ ] **Step 2: Run, confirm fail**

```bash
uv run pytest tests/unit/test_normalizer_layout_buttons.py -v
```

- [ ] **Step 3: Append to `passes.py`**

```python
def _to_int(v) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def pass4_layout(section: dict, profile: dict) -> tuple[dict, dict]:
    out = copy.deepcopy(section)
    layout = profile.get("layout") or {}
    diff: dict = {"padding_snapped": [], "content_width_snapped": []}

    target_top = (layout.get("section_padding") or {}).get("top", 80)
    target_bot = (layout.get("section_padding") or {}).get("bottom", 80)
    target_cw  = layout.get("content_width", 1200)

    settings = out.get("settings") or {}
    pad = settings.get("padding") if isinstance(settings.get("padding"), dict) else None
    if pad and pad.get("unit") == "px":
        t = _to_int(pad.get("top"))
        b = _to_int(pad.get("bottom"))
        if t is not None and abs(t - target_top) <= 20:
            diff["padding_snapped"].append({"delta_top": t - target_top, "snapped": True})
            pad["top"] = target_top
        if b is not None and abs(b - target_bot) <= 20:
            pad["bottom"] = target_bot

    cw = settings.get("content_width") if isinstance(settings.get("content_width"), dict) else None
    if cw and cw.get("unit") == "px":
        size = _to_int(cw.get("size"))
        if size is not None and abs(size - target_cw) <= 100:
            diff["content_width_snapped"].append({"from": size, "to": target_cw})
            cw["size"] = target_cw

    return out, diff


def pass5_buttons(section: dict, profile: dict) -> tuple[dict, dict]:
    out = copy.deepcopy(section)
    btn = profile.get("buttons") or {}
    r = btn.get("border_radius", 0)
    px = btn.get("padding_x", 32)
    py = btn.get("padding_y", 16)
    diff: dict = {"buttons_styled": []}

    def visit(node: dict) -> None:
        if node.get("elType") == "widget" and node.get("widgetType") == "button":
            s = node.setdefault("settings", {})
            s["border_radius"] = {"unit": "px", "top": r, "right": r, "bottom": r, "left": r, "isLinked": True}
            s["text_padding"]  = {"unit": "px", "top": py, "right": px, "bottom": py, "left": px, "isLinked": False}
            diff["buttons_styled"].append({"widget_id": node.get("id")})
        for child in node.get("elements", []) or []:
            visit(child)

    visit(out)
    return out, diff
```

- [ ] **Step 4: Run, confirm pass**

```bash
uv run pytest tests/unit/test_normalizer_layout_buttons.py -v && uv run ruff check .
```

Expected: 5 green + ruff clean.

- [ ] **Step 5: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/core/normalizer/passes.py mcp-server/tests/unit/test_normalizer_layout_buttons.py
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "feat(mcp): normalizer passes 4 + 5 — layout snapping + button defaults

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 12: Normalizer orchestrator + tablet stripping + diff report

**Files:**
- Create: `mcp-server/elementor_mcp/core/normalizer/diff.py`
- Create: `mcp-server/elementor_mcp/core/normalizer/normalize.py`
- Modify: `mcp-server/elementor_mcp/core/normalizer/passes.py` — add `strip_tablet`
- Test: `mcp-server/tests/unit/test_normalizer_diff.py`

`strip_tablet`: remove any settings key ending in `_tablet` (per spec §3 #11, profiles model only desktop + mobile).

`normalize.py` orchestrates: strip_tablet → pass1_colors → pass2_fonts → pass3_typography_sizes → pass4_layout → pass5_buttons. Merges per-pass diff dicts into one final report.

- [ ] **Step 1: Write failing test**

`mcp-server/tests/unit/test_normalizer_diff.py`:

```python
import json
from pathlib import Path

from elementor_mcp.core.normalizer.normalize import normalize_section
from elementor_mcp.core.normalizer.passes import strip_tablet


FIX = Path(__file__).parent.parent / "fixtures"


def _profile():
    return json.loads((FIX / "profiles" / "stacks-western.json").read_text())


def test_strip_tablet_removes_tablet_keys():
    section = {
        "id": "s1", "elType": "section",
        "settings": {
            "padding_tablet": {"unit": "px", "top": "60"},
            "padding_mobile": {"unit": "px", "top": "40"},
            "padding": {"unit": "px", "top": "100"},
        },
        "elements": [],
    }
    out = strip_tablet(section)
    assert "padding_tablet" not in out["settings"]
    assert "padding_mobile" in out["settings"]
    assert "padding" in out["settings"]


def test_normalize_section_returns_diff_with_all_buckets():
    section = {
        "id": "s1", "elType": "section",
        "settings": {
            "background_color": "#8B4513",
            "typography_font_family": "Playfair Display",
            "typography_font_size": {"unit": "px", "size": 64},
            "padding": {"unit": "px", "top": "100", "bottom": "100", "left": "0", "right": "0", "isLinked": False},
            "padding_tablet": {"unit": "px", "top": "60"},
        },
        "elements": [{
            "id": "w1", "elType": "widget", "widgetType": "button",
            "settings": {"text": "Buy"},
            "elements": [],
        }],
    }
    result = normalize_section(section, _profile())
    diff = result["diff"]
    assert any(c["to"] == "primary" for c in diff["colors_remapped"])
    assert any(f["to"] == "primary" for f in diff["fonts_remapped"])
    assert any(s["to_level"] == "h1" for s in diff["sizes_snapped"])
    assert "tablet_stripped" in diff
    assert diff["tablet_stripped"] >= 1
    assert any(b for b in diff.get("buttons_styled", []))


def test_normalize_section_does_not_mutate_input():
    section = {"id": "s1", "elType": "section", "settings": {"background_color": "#8B4513"}, "elements": []}
    original = json.dumps(section)
    normalize_section(section, _profile())
    assert json.dumps(section) == original
```

- [ ] **Step 2: Run, confirm fail**

```bash
uv run pytest tests/unit/test_normalizer_diff.py -v
```

- [ ] **Step 3: Append `strip_tablet` to `passes.py`**

```python
def strip_tablet(section: dict) -> dict:
    """Remove any *_tablet settings key (profile is desktop + mobile only)."""
    out = copy.deepcopy(section)

    def visit_settings(settings: dict) -> int:
        if not isinstance(settings, dict):
            return 0
        removed = 0
        for k in list(settings.keys()):
            if k.endswith("_tablet"):
                del settings[k]
                removed += 1
        return removed

    count = 0

    def visit(node: dict) -> None:
        nonlocal count
        count += visit_settings(node.get("settings"))
        for child in node.get("elements", []) or []:
            visit(child)

    visit(out)
    out["_tablet_stripped"] = count  # transient counter for orchestrator
    return out
```

- [ ] **Step 4: Implement `core/normalizer/diff.py`**

```python
def merge_diffs(*parts: dict) -> dict:
    """Merge per-pass diff dicts. Lists are concatenated; ints are summed; unknown keys preserved."""
    out: dict = {}
    for part in parts:
        for k, v in part.items():
            if k in out:
                if isinstance(v, list) and isinstance(out[k], list):
                    out[k] = out[k] + v
                elif isinstance(v, int) and isinstance(out[k], int):
                    out[k] = out[k] + v
                else:
                    out[k] = v
            else:
                out[k] = v
    return out
```

- [ ] **Step 5: Implement `core/normalizer/normalize.py`**

```python
from .diff import merge_diffs
from .passes import (
    pass1_colors,
    pass2_fonts,
    pass3_typography_sizes,
    pass4_layout,
    pass5_buttons,
    strip_tablet,
)


def normalize_section(section: dict, profile: dict) -> dict:
    """Apply six-pass normalizer to a section. Returns {section, diff}."""
    stripped = strip_tablet(section)
    tablet_count = stripped.pop("_tablet_stripped", 0)

    s, d1 = pass1_colors(stripped, profile)
    s, d2 = pass2_fonts(s, profile)
    s, d3 = pass3_typography_sizes(s, profile)
    s, d4 = pass4_layout(s, profile)
    s, d5 = pass5_buttons(s, profile)

    diff = merge_diffs(d1, d2, d3, d4, d5, {"tablet_stripped": tablet_count})
    return {"section": s, "diff": diff}
```

- [ ] **Step 6: Run, confirm pass**

```bash
uv run pytest tests/unit -v && uv run ruff check .
```

Expected: 3 new green; full suite green; ruff clean.

- [ ] **Step 7: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/core/normalizer/passes.py mcp-server/elementor_mcp/core/normalizer/diff.py mcp-server/elementor_mcp/core/normalizer/normalize.py mcp-server/tests/unit/test_normalizer_diff.py
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "feat(mcp): normalizer orchestrator + tablet stripping + diff report

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 13: Golden fixture regression test

**Files:**
- Create: `mcp-server/tests/fixtures/expected/hero-simple__stacks-western.json`
- Test: `mcp-server/tests/unit/test_normalize_golden.py`

Generates the expected output for the `hero-simple.json` × `stacks-western.json` combo and commits it. The test re-runs normalization and asserts byte-identical output (ignoring `__globals__` dict ordering — sort keys).

- [ ] **Step 1: Generate the expected output manually (one-shot)**

```bash
cd mcp-server && uv run python -c "
import json
from pathlib import Path
from elementor_mcp.core.normalizer.normalize import normalize_section
fix = Path('tests/fixtures')
template = json.loads((fix / 'templates' / 'hero-simple.json').read_text())
profile = json.loads((fix / 'profiles' / 'stacks-western.json').read_text())
# normalize the first section only
section = template['content'][0]
result = normalize_section(section, profile)
(fix / 'expected').mkdir(exist_ok=True)
out_path = fix / 'expected' / 'hero-simple__stacks-western.json'
out_path.write_text(json.dumps(result, indent=2, sort_keys=True))
print(f'wrote {out_path}')
"
```

- [ ] **Step 2: Write the regression test**

`mcp-server/tests/unit/test_normalize_golden.py`:

```python
import json
from pathlib import Path

from elementor_mcp.core.normalizer.normalize import normalize_section


FIX = Path(__file__).parent.parent / "fixtures"


def test_hero_simple_stacks_western_normalization_matches_golden():
    template = json.loads((FIX / "templates" / "hero-simple.json").read_text())
    profile = json.loads((FIX / "profiles" / "stacks-western.json").read_text())
    expected = json.loads((FIX / "expected" / "hero-simple__stacks-western.json").read_text())

    section = template["content"][0]
    result = normalize_section(section, profile)

    assert json.dumps(result, sort_keys=True) == json.dumps(expected, sort_keys=True)
```

- [ ] **Step 3: Run, confirm pass**

```bash
uv run pytest tests/unit/test_normalize_golden.py -v && uv run ruff check .
```

Expected: 1 green + ruff clean.

- [ ] **Step 4: Commit**

```bash
cd .. && git add mcp-server/tests/fixtures/expected/hero-simple__stacks-western.json mcp-server/tests/unit/test_normalize_golden.py
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "test(mcp): golden regression test for hero-simple × stacks-western

Locks the normalizer output for one canonical input. Any future
change to the six passes that affects this fixture will be caught.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 14: Color overflow → Kit custom_colors (PUT /kit) + integration into section.add

**Files:**
- Modify: `mcp-server/elementor_mcp/core/normalizer/normalize.py` — accept optional `kit_writer_fn`
- Modify: `mcp-server/elementor_mcp/tools/section.py` — accept `normalize=True` + `profile_id`
- Modify: `mcp-server/elementor_mcp/tools/kit.py` — add `kit_promote_custom_colors(client, colors)` helper
- Modify: `mcp-server/elementor_mcp/server.py` — wire section_add to call normalizer
- Test: `mcp-server/tests/unit/test_kit_promote_custom_colors.py`
- Test: `mcp-server/tests/unit/test_section_add_normalizes.py`

Behavior:
- When `section_add` is called with `profile_id` AND `normalize=True` (default), the MCP tool:
  1. Fetches the profile (via `profile_get`).
  2. Calls `normalize_section(section_json, profile)`.
  3. For every entry in `diff.colors_overflow`, calls `kit_promote_custom_colors(client, [...hex])` which:
     - GETs current Kit settings.
     - Adds each new hex to `custom_colors` (deduped by hex; new ids `mcp-custom-<n>`).
     - PUTs Kit settings back.
     - Records the new global ids in the returned diff under `colors_promoted`.
  4. For every entry, walks the section again and converts the overflow color settings to `__globals__` references using the new custom-color ids.
  5. Calls the existing `section_add` REST endpoint with the normalized section + appends diff report to the response.

- [ ] **Step 1: Write failing tests**

`mcp-server/tests/unit/test_kit_promote_custom_colors.py`:

```python
from unittest.mock import MagicMock

from elementor_mcp.envelope import ok
from elementor_mcp.tools.kit import kit_promote_custom_colors


def test_promote_adds_new_colors_to_existing_kit():
    client = MagicMock()
    client.get.return_value = ok({"custom_colors": [{"_id": "muted", "color": "#9F9F9F"}]})
    client.put.return_value = ok({"kit_post_id": 5})

    res = kit_promote_custom_colors(client, hex_colors=["#00FF00", "#FF00FF"])

    assert res.ok is True
    assert len(res.data["promoted"]) == 2
    assert res.data["promoted"][0]["hex"] == "#00FF00"
    assert res.data["promoted"][0]["slot"].startswith("mcp-custom-")

    sent = client.put.call_args.kwargs["json"]
    # Original "muted" preserved + 2 new
    colors = sent["custom_colors"]
    assert len(colors) == 3
    assert any(c["color"] == "#9F9F9F" for c in colors)
    assert any(c["color"] == "#00FF00" for c in colors)


def test_promote_skips_duplicates():
    client = MagicMock()
    client.get.return_value = ok({"custom_colors": [{"_id": "muted", "color": "#9F9F9F"}]})
    client.put.return_value = ok({"kit_post_id": 5})

    res = kit_promote_custom_colors(client, hex_colors=["#9F9F9F", "#00FF00"])

    # Only the new one gets added
    sent = client.put.call_args.kwargs["json"]
    assert len(sent["custom_colors"]) == 2
    assert len(res.data["promoted"]) == 1
    assert res.data["promoted"][0]["hex"] == "#00FF00"


def test_promote_returns_empty_when_no_overflow():
    client = MagicMock()
    res = kit_promote_custom_colors(client, hex_colors=[])
    assert res.ok is True
    assert res.data["promoted"] == []
    client.get.assert_not_called()
    client.put.assert_not_called()
```

`mcp-server/tests/unit/test_section_add_normalizes.py`:

```python
from unittest.mock import MagicMock

from elementor_mcp.envelope import ok
from elementor_mcp.tools.section import section_add


def test_section_add_without_profile_id_skips_normalization():
    client = MagicMock()
    client.post.return_value = ok({"sid": "abc"})
    section_json = {"id": "abc", "elType": "section", "settings": {}, "elements": []}
    res = section_add(client, page_id=1, section_json=section_json)
    assert res.ok is True
    # Existing post endpoint called with raw json
    body = client.post.call_args.kwargs["json"]
    assert body["json"]["id"] == "abc"


def test_section_add_with_profile_id_returns_diff_in_response(monkeypatch):
    """When profile_id is passed, the tool calls a normalize hook before posting."""
    from elementor_mcp.tools import section as section_mod

    called: dict = {}

    def fake_normalize(*, client, section_json, profile_id):
        called["was_called"] = True
        return ok({
            "section": {"id": "abc", "elType": "section", "settings": {"__globals__": {"x": "y"}}, "elements": []},
            "diff": {"colors_remapped": [{"to": "primary"}], "colors_promoted": [], "tablet_stripped": 0},
        })

    monkeypatch.setattr(section_mod, "_normalize_with_kit_overflow", fake_normalize)
    client = MagicMock()
    client.post.return_value = ok({"sid": "abc"})
    section_json = {"id": "abc", "elType": "section", "settings": {"title_color": "#FF0000"}, "elements": []}
    res = section_add(client, page_id=1, section_json=section_json, profile_id=7)
    assert res.ok is True
    assert called.get("was_called") is True
    body = client.post.call_args.kwargs["json"]
    # Normalized section forwarded
    assert "__globals__" in body["json"]["settings"]
    # Diff report attached to result
    assert "diff" in res.data
```

- [ ] **Step 2: Run, confirm fail**

```bash
uv run pytest tests/unit/test_kit_promote_custom_colors.py tests/unit/test_section_add_normalizes.py -v
```

- [ ] **Step 3: Add `kit_promote_custom_colors` to `tools/kit.py`**

```python
import re

from ..envelope import ToolResult, fail, ok
from ..errors import ErrorCode


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def kit_promote_custom_colors(client, *, hex_colors: list[str]) -> ToolResult:
    """Add each new hex to Kit custom_colors (deduped). Returns the slot ids assigned."""
    if not hex_colors:
        return ok({"promoted": []})

    cur = client.get("/kit")
    if not cur.ok:
        return cur
    settings = cur.data if isinstance(cur.data, dict) else {}
    custom = list(settings.get("custom_colors") or [])
    existing_hexes = {c.get("color", "").upper() for c in custom}

    promoted = []
    next_index = sum(1 for c in custom if (c.get("_id") or "").startswith("mcp-custom-")) + 1
    for hex_color in hex_colors:
        normalized = hex_color.upper()
        if normalized in existing_hexes:
            continue
        slot = f"mcp-custom-{next_index}"
        next_index += 1
        custom.append({"_id": slot, "title": slot, "color": normalized})
        promoted.append({"hex": normalized, "slot": slot})
        existing_hexes.add(normalized)

    if not promoted:
        return ok({"promoted": []})

    settings["custom_colors"] = custom
    put = client.put("/kit", json=settings)
    if not put.ok:
        return put
    return ok({"promoted": promoted})
```

- [ ] **Step 4: Modify `tools/section.py` — add normalization hook**

At the top of the file, add:

```python
from ..envelope import ok

def _normalize_with_kit_overflow(
    *, client: "WpClient", section_json: dict, profile_id: int
) -> "ToolResult":
    """Fetch profile, normalize section, promote overflow colors to Kit custom_colors,
    then rewrite section globals to point at the new slots. Returns {section, diff}."""
    from ..core.normalizer.normalize import normalize_section
    from .kit import kit_promote_custom_colors
    from .profile import profile_get

    prof = profile_get(client, profile_id=profile_id)
    if not prof.ok:
        return prof
    profile_data = (prof.data or {}).get("data") or {}

    normalized = normalize_section(section_json, profile_data)
    section = normalized["section"]
    diff = normalized["diff"]

    overflow_hexes = [c["hex"] for c in diff.get("colors_overflow", [])]
    promoted = kit_promote_custom_colors(client, hex_colors=overflow_hexes)
    if not promoted.ok:
        return promoted
    diff["colors_promoted"] = promoted.data.get("promoted", [])

    # Apply the overflow → custom-slot mapping by walking the section again
    slot_by_hex = {p["hex"]: p["slot"] for p in diff["colors_promoted"]}
    if slot_by_hex:
        _swap_overflow_globals(section, slot_by_hex)
    return ok({"section": section, "diff": diff})


def _swap_overflow_globals(node: dict, slot_by_hex: dict[str, str]) -> None:
    settings = node.get("settings") or {}
    for k, v in list(settings.items()):
        if isinstance(v, str) and v.startswith("#") and v.upper() in slot_by_hex:
            slot = slot_by_hex[v.upper()]
            g = settings.setdefault("__globals__", {})
            g[k] = f"globals/colors?id={slot}"
            del settings[k]
    for child in node.get("elements", []) or []:
        _swap_overflow_globals(child, slot_by_hex)
```

Modify `section_add` itself:

```python
def section_add(
    client: WpClient,
    *,
    page_id: int,
    section_json: dict,
    position: int | None = None,
    profile_id: int | None = None,
    normalize: bool = True,
) -> ToolResult:
    diff = None
    if profile_id is not None and normalize:
        normalized = _normalize_with_kit_overflow(
            client=client, section_json=section_json, profile_id=profile_id,
        )
        if not normalized.ok:
            return normalized
        section_json = normalized.data["section"]
        diff = normalized.data["diff"]

    body: dict = {"json": section_json}
    if position is not None:
        body["position"] = position
    result = client.post(f"/pages/{page_id}/sections", json=body)
    if not result.ok:
        return result
    payload = dict(result.data) if isinstance(result.data, dict) else {"sid": None}
    if diff is not None:
        payload["diff"] = diff
    return ok(payload)
```

- [ ] **Step 5: Update server.py `_list()` for new section_add params**

Replace the existing `section_add` Tool definition with:

```python
            Tool(name="section_add", description="Append or insert a new section. When profile_id is set, the section JSON is normalized to the profile (colors → globals, fonts → globals, sizes → typography) and any overflow colors are promoted to Kit custom_colors. A diff report is included in the response.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},
                     "section_json":{"type":"object"},
                     "position":{"type":"integer"},
                     "profile_id":{"type":"integer"},
                     "normalize":{"type":"boolean"},
                 },"required":["page_id","section_json"],"additionalProperties":False}),
```

- [ ] **Step 6: Run all tests + ruff**

```bash
uv run pytest tests/unit -v && uv run ruff check .
```

Expected: All green; ruff clean.

- [ ] **Step 7: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/tools/kit.py mcp-server/elementor_mcp/tools/section.py mcp-server/elementor_mcp/server.py mcp-server/tests/unit/test_kit_promote_custom_colors.py mcp-server/tests/unit/test_section_add_normalizes.py
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "feat(mcp): color overflow → Kit custom_colors + section_add normalization

When section_add is called with a profile_id, the section JSON is
run through the six-pass normalizer. Any colors that don't snap to
the profile palette are auto-promoted to the Kit's custom_colors
via PUT /kit (deduped, with mcp-custom-N slot ids). The original
hardcoded color values are then rewritten as __globals__ references
to the new slots, so they participate in the Kit system going
forward. A diff report describing every change is attached to the
response.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 15: Integration test — normalize + section.add round-trip against wp-env

**Files:**
- Create: `mcp-server/tests/integration/test_normalize_apply.py`

Exercises the full chain against real wp-env: create profile → apply → add a section with hardcoded colors + profile_id → fetch the saved section → assert it uses `__globals__` references.

- [ ] **Step 1: Write the test**

`mcp-server/tests/integration/test_normalize_apply.py`:

```python
import json
import uuid
from pathlib import Path

import pytest

from elementor_mcp.core.wp_client import WpClient
from elementor_mcp.tools.page import page_create, page_delete
from elementor_mcp.tools.profile import profile_apply, profile_create, profile_delete
from elementor_mcp.tools.section import section_add, section_get


FIX = Path(__file__).parent.parent / "fixtures"


def _profile_payload(name: str) -> dict:
    data = json.loads((FIX / "profiles" / "stacks-western.json").read_text())
    data["name"] = name
    return data


def test_section_add_with_profile_normalizes_colors(live_settings):
    client = WpClient(live_settings)

    pname = f"itest-norm-{uuid.uuid4().hex[:6]}"
    p_res = profile_create(client, profile=_profile_payload(pname))
    assert p_res.ok, p_res.error
    pid = p_res.data["id"]
    assert profile_apply(client, profile_id=pid).ok

    pg = page_create(client, title=f"itest-norm-page-{uuid.uuid4().hex[:6]}", profile_id=pid)
    assert pg.ok, pg.error
    page_id = pg.data["id"]

    sid = uuid.uuid4().hex[:8]
    raw_section = {
        "id": sid, "elType": "section",
        "settings": {
            "_title": "Hero",
            "background_color": "#8B4513",    # primary, should snap
            "title_color":      "#00FF00",    # neon green, should overflow
        },
        "elements": [{
            "id": uuid.uuid4().hex[:8], "elType": "widget", "widgetType": "heading",
            "settings": {
                "title": "Test",
                "typography_font_family": "Playfair Display",
                "typography_font_size": {"unit": "px", "size": 64},
            },
            "elements": [],
        }],
    }

    add = section_add(client, page_id=page_id, section_json=raw_section, profile_id=pid)
    assert add.ok, add.error
    assert "diff" in add.data
    diff = add.data["diff"]
    assert any(r.get("to") == "primary" for r in diff.get("colors_remapped", []))
    assert any(p.get("hex") == "#00FF00" for p in diff.get("colors_promoted", []))

    fetched = section_get(client, page_id=page_id, sid=sid)
    assert fetched.ok, fetched.error
    s = fetched.data
    # background_color was snapped to primary
    assert "background_color" not in s["settings"]
    assert s["settings"]["__globals__"]["background_color"] == "globals/colors?id=primary"
    # title_color was promoted to a custom slot
    title_ref = s["settings"]["__globals__"]["title_color"]
    assert title_ref.startswith("globals/colors?id=mcp-custom-")

    # cleanup
    page_delete(client, page_id=page_id)
    profile_delete(client, profile_id=pid)
```

- [ ] **Step 2: Make sure the fixture path is reachable**

Tests use `tests/fixtures/profiles/stacks-western.json` which was already created in Task 9.

- [ ] **Step 3: Run integration test**

```bash
cd mcp-server && EMCP_TEST_API_KEY="emcp_GwcFxWiYj6Lh_WYnzuuo00CMVgB7H31lMcSf7F7gdUI49" EMCP_TEST_WP_URL="http://localhost:8888" uv run pytest tests/integration -v
```

Expected: 5 green (4 from prior phases + 1 new).

- [ ] **Step 4: Commit**

```bash
cd .. && git add mcp-server/tests/integration/test_normalize_apply.py
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "test(mcp): integration test for normalize + section.add roundtrip

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 16: README update + acceptance + tag

**Files:**
- Modify: `README.md` — document new tools + index building step

- [ ] **Step 1: Update README "MCP tools" section**

Replace the existing "MCP tools" block with:

```markdown
## MCP tools (after Phase 1b-2)

- **Auth:** `auth_verify`
- **Profiles:** `profile_list`, `profile_get`, `profile_create`, `profile_update`, `profile_delete`, `profile_apply`
- **Pages:** `page_list`, `page_create`, `page_get`, `page_delete`
- **Sections:** `section_list`, `section_get`, `section_add` (with profile-aware normalization), `section_update`, `section_delete`, `section_duplicate`, `section_reorder`, `section_history`, `section_restore`
- **Kit (raw):** `kit_get`, `kit_set`
- **Images:** `image_generate`, `image_upload`, `image_describe_slot`
- **Templates:** `template_search`, `template_get`, `template_preview`, `template_list_categories`

## Building the template index

After cloning, build the local index from section-express:

```bash
cd mcp-server && uv run python -m elementor_mcp.scripts.build_index \
  --src "../section-express-libr/pack/JSON Files"
```

This creates `mcp-server/elementor_mcp/data/index.db` with one row per template (excluded from git).
```

- [ ] **Step 2: Run full acceptance**

```bash
cd wp-plugin && vendor/bin/phpunit
cd ../mcp-server && uv run ruff check . && uv run pytest tests/unit -v
EMCP_TEST_API_KEY="emcp_GwcFxWiYj6Lh_WYnzuuo00CMVgB7H31lMcSf7F7gdUI49" EMCP_TEST_WP_URL="http://localhost:8888" \
  uv run pytest tests/integration -v
```

Expected:
- PHPUnit: still 85 green (no plugin changes in P1b-2).
- Python unit: ≥ 90 green; ruff clean.
- Integration: 5 green.

- [ ] **Step 3: Push**

```bash
cd .. && git add README.md
git -c user.email="webcuahao@gmail.com" -c user.name="webcuahao" commit -m "docs: P1b-2 tools inventory + index build instructions

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

- [ ] **Step 4: After CI green, tag**

```bash
git tag -a v0.1.2-p1b2 -m "Phase 1b-2: Library indexing + Kit Normalizer

- SQLite library index (FTS5) with Stage B auto-extract
- 4 new template_* MCP tools (search, get, preview, list_categories)
- Six-pass Kit Normalizer:
  - Pass 1: color mapping (LAB ΔE tier policy)
  - Pass 2: font mapping
  - Pass 3: typography size snapping
  - Pass 4: layout (section padding + content width)
  - Pass 5: button defaults
  - tablet stripping (mobile-only responsive)
- Color overflow auto-promoted to Kit custom_colors with mcp-custom-N slot ids
- Diff report attached to section.add responses when profile_id is given
- Golden fixture regression test"
git push --tags
```

---

## P1b-2 Acceptance Criteria

1. `cd wp-plugin && vendor/bin/phpunit` — still 85 green (no regressions).
2. `cd mcp-server && uv run pytest tests/unit -v && uv run ruff check .` — ≥ 90 tests + clean.
3. Integration: 5 green including the new `test_section_add_with_profile_normalizes_colors`.
4. `template_search(query="hero")` returns at least one result from the real section-express library after running `build_index.py`.
5. Calling `section_add(page_id, section_json, profile_id=X)` on a page with hardcoded colors produces a saved section where every recognized color uses `__globals__` references — overflow colors land in the Kit's `custom_colors`.
6. CI three jobs green on master; tag `v0.1.2-p1b2` pushed.

---

## Self-review

**1. Spec coverage:**
- Spec §3 #4 (template indexing two-stage: Stage B + AI augment) — Stage B is fully implemented in this plan (Tasks 1–5). Stage C (AI augment) is deferred to a future phase since it requires the Codex task workflow.
- Spec §3 #10–#13 (color overflow, ΔE tier mapping, diff report) — Tasks 9, 12, 14. ✓
- Spec §3 #11 (mobile-only responsive) — Task 12 (`strip_tablet`). ✓
- Spec §8 template tools (search, get, preview, list_categories) — Task 6. ✓
- Spec §10.1 (Stage B extract: widgets, dims, colors, fonts, categories) — Tasks 3–5. ✓
- Spec §10.3 (SQLite schema with FTS5) — Task 1. ✓
- Spec §10.4 (hybrid search: SQL filter → FTS5 keyword) — Task 6. (Vector rank deferred to P2.)
- Spec §11 (six-pass normalizer) — Tasks 9, 10, 11, 12. ✓
- Spec §11.1 (color overflow → custom_colors) — Task 14. ✓
- Spec §11.3 (diff report shape) — Tasks 12, 14. ✓

Deferred to P1b-3: Kit Mapper Admin UI, MCP HTTP server (FastAPI). Acceptable.

**2. Placeholder scan:** No TBD/TODO/etc. Every step has actual code or commands.

**3. Type consistency:**
- `validate_template` returns `{ok, errors, warnings}` — matches existing Profile_Schema convention.
- `extract_metadata` returns dict with `widgets_used, columns_max, image_count, has_form, has_carousel, has_video, dominant_colors, font_families` — consumed identically by `build_index.py` and `categorize`. ✓
- `normalize_section(section, profile)` returns `{section, diff}` — consumed by `tools/section._normalize_with_kit_overflow`. ✓
- All `passes.pass*` return `(section, diff)` tuples — merged by `merge_diffs`. ✓
- `template_*` tools take `db_path`, `src_dir`, optionally other kwargs; all return `ToolResult`. ✓
- `kit_promote_custom_colors` accepts `hex_colors: list[str]` and returns `{promoted: [{hex, slot}]}` — matches `_swap_overflow_globals` consumer. ✓

No gaps to fix.

---

## Continuation: P1b-3

| Component | Spec sections | Approx tasks |
|---|---|---|
| MCP HTTP server (FastAPI) for admin UI | §17.4 | 4 |
| WP plugin library proxy endpoints | §7.7 | 2 |
| WP admin "Kit Mapper" page (React or vanilla JS) | User request | 4 |
| `kit_mapper.scan(page_id)` + `kit_mapper.apply(page_id, mappings)` tools | User request | 2 |

Approx 12 tasks. Written after P1b-2 ships and CI is green.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-28-elementor-mcp-p1b2-library-normalizer.md`. Two execution options:

1. **Subagent-Driven (recommended)** — Fresh subagent per task, two-stage review, fast iteration. Best for 16 tasks of focused TDD.

2. **Inline Execution** — Run in this session with executing-plans, batch with checkpoints.

Which approach?
