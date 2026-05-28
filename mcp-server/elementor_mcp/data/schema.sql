-- Elementor MCP template library — SQLite schema (Stage B + FTS5)
CREATE TABLE IF NOT EXISTS templates (
    id              TEXT PRIMARY KEY,
    path            TEXT NOT NULL,
    category        TEXT,
    source          TEXT NOT NULL DEFAULT 'builtin',
    status          TEXT NOT NULL DEFAULT 'valid',
    widgets_used    TEXT,
    columns_max     INTEGER,
    image_count     INTEGER DEFAULT 0,
    has_form        INTEGER DEFAULT 0,
    has_carousel    INTEGER DEFAULT 0,
    has_video       INTEGER DEFAULT 0,
    dominant_colors TEXT,
    font_families   TEXT,
    complexity      INTEGER DEFAULT 0,
    is_responsive   INTEGER DEFAULT 0,
    width_mode      TEXT,
    preview_url     TEXT,
    description     TEXT,
    use_cases       TEXT,
    style_tags      TEXT,
    industries      TEXT,
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
