# Elementor MCP — Design Spec

**Date:** 2026-05-27
**Status:** Draft (pending user review)
**Target deployment:** `elementor.leobot.online` (single WP site on VPS)

---

## 1. Overview

A research-driven page-building system that lets an AI agent (Claude / Cursor / Codex) compose, modify, and refine entire Elementor pages from natural-language briefs — including pages designed around an existing brand by crawling the source site.

The system has three components:

1. **Python MCP server** — exposes ~50 tools to agents, holds the template library + search index + image generation + research crawler + normalization logic.
2. **WordPress plugin** (`elementor-mcp-bridge`) — thin PHP layer exposing REST endpoints for Kit profiles, page CRUD, section CRUD on Elementor's `_elementor_data` post meta, and library admin UI.
3. **Template library** — 2,232 existing Elementor JSONs (`section-express-libr/`) plus user imports, indexed in SQLite with both keyword (FTS5) and semantic (sqlite-vec) search.

---

## 2. Goals / Non-goals

**Goals (v1):**
- Profile-first workflow — every creative action checks for a Kit profile first; if none, the agent is required to set or create one.
- One-call page composition from a text brief or a source URL.
- Smart layout selection from the library, content fill (agent-generated or paraphrased from crawled site), image generation at correct dimensions.
- Every inserted section is normalized to the active profile (colors → Kit globals, fonts → Kit globals, sizes → typography scale).
- Library management UI in WP admin: verify, import (JSON / HTML / screenshot / snapshot of existing page), re-index.
- Backup-and-restore for sections (5 versions per page).

**Non-goals (v1):**
- Multi-site management. Single WP site at `elementor.leobot.online`.
- Replacing the Elementor editor. Agent edits via MCP, user can still hand-edit in Elementor (and we respect that on re-normalize).
- Visual page-builder UI for end users (agent IS the UI).
- Translation / multilingual layouts.

---

## 3. Decision log

| # | Decision | Choice |
|---|---|---|
| 1 | Scope of v1 | Core CRUD + Library + Prototyper + Research + Import (full vision) |
| 2 | Image generation | OpenAI `gpt-image-1` with Unsplash fallback when no key |
| 3 | Global Kit workflow | Named profiles managed in WP plugin (CPT `emcp_profile`) |
| 4 | Template indexing | Two-stage: auto-extract metadata (script) + AI augment (delegated to Codex task) |
| 5 | Authentication | Custom API key issued by plugin, bcrypt-stored, mapped to a WP user |
| 6 | Media upload | Standard WP REST `/wp/v2/media` (the API key user has `upload_files` cap) |
| 7 | MCP language | Python |
| 8 | Search method | Hybrid — SQL filter → FTS5 keyword rank → vector semantic rank |
| 9 | Architecture split | MCP-heavy: plugin is thin (auth + raw R/W); MCP holds library + logic |
| 10 | Color overflow during normalize | Promote extras to Kit `custom_colors` (auto-add) |
| 11 | Responsive variants in profile | Desktop + mobile only (skip tablet) |
| 12 | Color mapping policy | Tier-based ΔE in LAB space: <5 auto-snap, 5–15 ask, >15 keep |
| 13 | Diff report | Return per-mutation summary (colors remapped/promoted, fonts, sizes, skipped) |
| 14 | Section backup | 5 versions per page in `_elementor_data_backup_history` postmeta |
| 15 | AI augment funding | Write a Codex task brief (not part of automated install) |
| 16 | Multi-site | Single site v1, accessed at `https://elementor.leobot.online` |

---

## 4. System architecture

```
CLIENT (Claude / Cursor / Codex)
        │  MCP stdio protocol
        ▼
PYTHON MCP SERVER  (package: elementor_mcp)
  tools/ — exposed MCP tools (~50)
  core/  — wp_client, kit_normalizer, search, image_gen,
           composer, research/
  data/  — templates/ (builtin + imported + rejected),
           index.db (sqlite + sqlite-vec + FTS5)
        │  HTTPS + Bearer api_key
        ▼
WP PLUGIN: elementor-mcp-bridge
  REST: /wp-json/elementor-mcp/v1/
  Admin UI: Elementor MCP page (API keys + profiles + library)
  Hooks: clear Elementor cache after mutation
        │
        ▼
WordPress DB (postmeta, options, CPT) + WP Media
```

### 4.1 Repo layout

```
elementor-full-mcp/
├─ mcp-server/                    Python
│  ├─ pyproject.toml
│  ├─ elementor_mcp/
│  │  ├─ server.py                MCP stdio entry
│  │  ├─ http_server.py           Optional HTTP for admin UI calls
│  │  ├─ tools/                   MCP tool definitions
│  │  ├─ core/
│  │  │  ├─ wp_client.py
│  │  │  ├─ kit_normalizer.py
│  │  │  ├─ search.py
│  │  │  ├─ image_gen.py
│  │  │  ├─ composer.py
│  │  │  ├─ library/              validator, importers, indexer
│  │  │  └─ research/             crawler, brand_extractor, …
│  │  └─ data/
│  │     ├─ templates/{builtin,imported,rejected}
│  │     ├─ index.db
│  │     └─ manifest.json
│  ├─ scripts/
│  │  ├─ build_index.py           Stage B
│  │  ├─ ai_augment.py            Stage C (also used by Codex task)
│  │  └─ verify_library.py
│  └─ tests/
│     ├─ fixtures/                profiles + templates + expected
│     └─ …
├─ wp-plugin/                     PHP
│  ├─ elementor-mcp-bridge.php    bootstrap
│  ├─ includes/
│  │  ├─ class-rest-api.php
│  │  ├─ class-auth.php
│  │  ├─ class-profiles.php
│  │  ├─ class-sections.php
│  │  ├─ class-library-proxy.php
│  │  └─ class-backup.php
│  ├─ admin/                      UI + assets
│  └─ tests/                      PHPUnit
├─ section-express-libr/          existing 2,232 templates
└─ docs/superpowers/specs/        this spec
```

---

## 5. Data model (WordPress side)

**Additions only — no core schema changes.**

### 5.1 Custom Post Type — `emcp_profile`
- `post_title` — profile name (e.g., "SaaS-blue").
- Postmeta `_emcp_profile_data` — full profile JSON (schema in §6).

### 5.2 Options
- `elementor_mcp_api_keys` — array of `{id, hash, label, user_id, scopes, created_at, last_used}` (bcrypt-hashed).
- `elementor_mcp_mcp_url` — URL of the MCP HTTP API endpoint (for admin UI library calls).
- `elementor_mcp_settings` — log level, cache strategy.

### 5.3 Existing Elementor meta (read/write)
- `_elementor_data` — JSON array of top-level sections.
- `_elementor_version`, `_elementor_edit_mode`.
- `_elementor_css` — cached CSS, delete after mutation.
- `_elementor_data_backup_history` — array of last 5 snapshots `{version, timestamp, data}` (added by plugin).
- Kit post (special Elementor CPT) — `system_colors`, `custom_colors`, `system_typography`, `custom_typography`, breakpoints, container width.

---

## 6. Profile JSON schema

```json
{
  "name": "SaaS-blue",
  "colors": {
    "primary":    "#0066FF",
    "secondary":  "#00C2A8",
    "text":       "#1A1A1A",
    "accent":     "#FFD60A",
    "background": "#FFFFFF",
    "custom":     [{"name": "muted", "value": "#9F9F9F"}]
  },
  "fonts": {
    "primary":   {"family": "Inter",   "source": "google", "weights": [400,500,700]},
    "secondary": {"family": "Manrope", "source": "google", "weights": [400,700]}
  },
  "typography": {
    "h1":   {"size": 64, "mobile": 36, "weight": 700, "line_height": 1.1},
    "h2":   {"size": 48, "mobile": 28, "weight": 700, "line_height": 1.15},
    "h3":   {"size": 32, "mobile": 22, "weight": 600, "line_height": 1.2},
    "body": {"size": 17, "mobile": 15, "weight": 500, "line_height": 1.6},
    "small":{"size": 14, "mobile": 12, "weight": 500, "line_height": 1.5}
  },
  "layout": {
    "container_width":         1290,
    "content_width":           1200,
    "section_padding":         {"top": 80, "bottom": 80},
    "section_padding_mobile":  {"top": 40, "bottom": 40}
  },
  "breakpoints": {"mobile": 767, "desktop": 1290},
  "buttons":     {"border_radius": 0, "padding_x": 32, "padding_y": 16}
}
```

> Note: only `mobile` responsive variants, no `tablet`. Normalizer strips `*_tablet` keys on input.

---

## 7. REST API endpoints

Namespace: `/wp-json/elementor-mcp/v1/`. All requests require `Authorization: Bearer <api_key>`.

### 7.1 Auth & health
- `GET /auth/verify` → `{user_id, caps, scopes, version}`
- `GET /health` → `{status, elementor_version, plugin_version}`

### 7.2 Profiles
- `GET /profiles`, `GET /profiles/{id}`, `POST /profiles`, `PUT /profiles/{id}`, `DELETE /profiles/{id}`
- `POST /profiles/{id}/apply` — write profile to Elementor Kit settings.

### 7.3 Kit
- `GET /kit` — current Elementor Kit settings.
- `PUT /kit` — replace Kit settings (raw, advanced).

### 7.4 Pages
- `GET /pages?search=&per_page=` → list Elementor-enabled pages.
- `POST /pages` → `{title, profile_id?}` (profile auto-applied if provided).
- `GET /pages/{id}`, `DELETE /pages/{id}`.

### 7.5 Sections (CRUD on `_elementor_data`)
- `GET /pages/{id}/sections` → `[{sid, title, widget_summary}]`.
- `POST /pages/{id}/sections` → `{json | template_id, position?, profile_id?}` (auto-normalize if profile present).
- `GET /pages/{id}/sections/{sid}` → full section JSON.
- `PUT /pages/{id}/sections/{sid}` — replace.
- `DELETE /pages/{id}/sections/{sid}`.
- `POST /pages/{id}/sections/{sid}/duplicate`.
- `POST /pages/{id}/sections/reorder` → `{order:[sid1, sid2,…]}`.

### 7.6 Backup / restore
- `GET /pages/{id}/backups` → list 5 snapshots.
- `POST /pages/{id}/backups/{version}/restore` → revert.

### 7.7 Library admin (proxies to MCP HTTP API)
- `GET /library/stats`.
- `POST /library/verify` → returns `{job_id}`.
- `GET /library/jobs/{job_id}` — progress.
- `POST /library/import/json` — multipart upload.
- `POST /library/import/snapshot` — `{page_id}`.
- `POST /library/import/html` — `{html | url}`.
- `POST /library/import/image` — multipart image.

### 7.8 Authentication flow
1. Admin creates an API key in WP admin → plugin returns raw `emcp_<id>_<secret>` once; stores bcrypt hash + `wp_user_id`.
2. Each request: filter `rest_authentication_errors` parses Bearer, looks up by id prefix, bcrypt-compare, then `wp_set_current_user($user_id)`. WP capability checks proceed normally.

### 7.9 Cache invalidation after mutation
```php
update_post_meta($page_id, '_elementor_data', wp_slash(json_encode($data)));
delete_post_meta($page_id, '_elementor_css');
\Elementor\Plugin::instance()->files_manager->clear_cache();
\Elementor\Core\Files\CSS\Post::create($page_id)->update();
```

---

## 8. MCP tools catalog

All tools return `{ok, data, warnings, error?}`.

### Profile guard
- `check_profile_ready()` — status + suggestions.
- `suggest_profile_from_brief(brief)`.

### Profiles
- `profile.list`, `profile.get`, `profile.create`, `profile.update`, `profile.delete`, `profile.apply`, `profile.preview`.

### Pages
- `page.list`, `page.create`, `page.get`, `page.delete`.

### Sections
- `section.list`, `section.get`, `section.add`, `section.update`, `section.delete`, `section.duplicate`, `section.reorder`, `section.history`, `section.restore`.

### Templates
- `template.search(query, category?, filters?, k=5)`.
- `template.get(id)`, `template.preview(id)`, `template.list_categories()`.

### Prototyper
- `prototyper.compose_page(brief, profile_id?, dry_run=false)`.
- `prototyper.compose_from_url(url, target_page, profile_id?)`.
- `prototyper.suggest_sections(brief|dossier)`.
- `prototyper.replace_section(page_id, sid, intent)`.

### Image generation
- `image.generate({prompt, w, h, style?})`.
- `image.upload(file_path | url)`.
- `image.suggest_for_slot(slot_spec, brief|dossier)`.

### Research
- `research.crawl_site(url, depth=2)` — returns dossier (cached 24 h).
- `research.get_brand(url)` — brand signals only (fast).
- `research.suggest_profile(url | dossier)`.
- `research.extract_existing_page(url, page_type)`.

### Library (HTTP API, also exposed via tools for power-users)
- `library.stats`, `library.verify`, `library.import_json`, `library.import_snapshot`, `library.import_html`, `library.import_image`.

### Profile guard policy
Tools that **must** call `check_profile_ready()` first: `prototyper.*`, `page.create`, `section.add` (when no profile id supplied). Browse / read-only tools do not require it.

---

## 9. Core flows

### 9.1 `prototyper.compose_page(brief)`
1. **Profile guard** — if no profile exists, return `E_NO_PROFILE` with three suggestions (use existing preset / create from brief / set up via wizard). Tool aborts.
2. **Intent analysis** — small LLM call to produce a section plan from the brief.
3. **Template picking** — for each section in the plan, call hybrid search with `category` + `intent` + `profile.tone`.
4. **Content fill** — extract text slots from each chosen template; generate text aligned with brief + brand.
5. **Image generation** — for each image slot, generate at the slot's exact dimensions (OpenAI `gpt-image-1`, fallback Unsplash by intent keywords); upload to WP via `/wp/v2/media`; swap URL into JSON.
6. **Normalize to profile** — apply six-pass kit normalizer (§11).
7. **Assemble + save** — create the page (if new), `section.add` each in order; apply profile to Kit.
8. Return `{page_id, edit_url, preview_url, sections_added, plan, diff_report}`.

### 9.2 `prototyper.compose_from_url(url, target_page)` — research-driven
- **Step 0 — Research**: crawl the site, extract brand signals (logo, colors, fonts, industry), content samples, layout vibe (screenshot + vision analysis).
- **Step 0.5 — Profile auto-derive**: if no profile selected, propose `"<sitename>-derived"` profile from the crawled signals; ask user to confirm or override.
- Subsequent steps mirror 9.1, with two enrichments:
  - Step 2 plan uses crawled content as "must-include" topics + tone examples.
  - Step 4 text generation **paraphrases** crawled copy rather than inventing.
  - Step 5 image prompts gain brand context (industry, palette).

### 9.3 Section CRUD
- `section.add(page_id, json|template_id, profile_id?)`:
  - If `template_id`, hydrate JSON from library.
  - If `profile_id` present, run kit normalizer.
  - Snapshot current `_elementor_data` to backup history.
  - Append section, save, clear cache, return new sid + diff report.

### 9.4 Image generation
```
image.generate(prompt, w, h):
  if OPENAI_API_KEY:
    out = openai.images.generate(model="gpt-image-1", prompt, size=f"{w}x{h}")
    return upload_to_wp(out.data[0].b64_json)
  else:
    keyword = extract_keyword(prompt)
    photo = unsplash.search(keyword).first()
    cropped = resize_crop(photo, w, h)
    return upload_to_wp(cropped)
```

---

## 10. Template indexing pipeline

### 10.1 Stage B — Auto-extract (script `build_index.py`)
For every JSON in `templates/builtin/`:
- Validate schema. Quarantine broken files to `rejected/`.
- Extract: `widgets_used`, `columns_max`, `image_count`, `image_dimensions`, `has_form`, `has_carousel`, `has_video`, `dominant_colors`, `font_families`, `complexity`, `is_responsive`, `width_mode`.
- Heuristic `category` detection:
  - 1 large h1 + button (± image) → `hero`
  - 3–4 columns + icons → `features`
  - pricing-table widget → `pricing`
  - quote + avatar → `testimonial`
  - form widget → `contact`
  - multi-col text links → `footer`
  - nav-menu widget → `navbar`
  - logo grid → `social-proof`
  - fallback → `section-general`
- Insert into SQLite `templates` table.

### 10.2 Stage C — AI augment (delegated to Codex task)
A separate Codex task brief (committed under `docs/codex-tasks/ai-augment.md`) instructs Codex CLI to:
1. Read all rows with `augmented = 0` and `category != 'section-general'` (Tier 1, ~1,500).
2. For each, render a prose summary of the structure.
3. Call Claude/GPT to produce `{description, category_confidence, use_cases, style_tags, industries, color_scheme}`.
4. Generate `text-embedding-3-small` (1536d) on description.
5. `UPDATE templates SET … augmented=1` and insert into `templates_vec`.
6. Resumable: process in batches, commit progress.
Budget guideline: ~\$5–10 total. Lazy augment for Tier 2 occurs on search miss.

### 10.3 SQLite schema
```sql
CREATE TABLE templates (
  id TEXT PRIMARY KEY,
  path TEXT,
  category TEXT,
  source TEXT,                -- builtin | imported | snapshot
  status TEXT,                -- valid | warning | broken
  widgets_used JSON,
  columns_max INTEGER,
  image_count INTEGER,
  has_form INTEGER, has_carousel INTEGER, has_video INTEGER,
  dominant_colors JSON, font_families JSON,
  complexity INTEGER, is_responsive INTEGER, width_mode TEXT,
  preview_url TEXT,
  description TEXT, use_cases JSON, style_tags JSON,
  industries JSON, color_scheme TEXT,
  augmented INTEGER DEFAULT 0,
  schema_version TEXT, validated_at TEXT, imported_at TEXT
);

CREATE VIRTUAL TABLE templates_fts USING fts5(
  id UNINDEXED, description, use_cases, style_tags, industries,
  content='templates'
);

CREATE VIRTUAL TABLE templates_vec USING vec0(
  id TEXT PRIMARY KEY, embedding FLOAT[1536]
);

CREATE INDEX idx_category ON templates(category);
CREATE INDEX idx_source   ON templates(source);
```

### 10.4 Hybrid search algorithm
1. **SQL hard filter** — narrow by `category`, `has_image`, status, etc.
2. **FTS5 keyword rank** — `bm25()` ordering within filter, top 50.
3. **Vector semantic rank** — cosine distance from query embedding, top k.
Result returned with hydrated metadata for the agent.

---

## 11. Kit normalizer (six passes)

Input: section JSON + active profile. Output: normalized JSON + diff report.

| Pass | Target keys | Action |
|---|---|---|
| 1. Colors | `*_color`, `*_text_color`, `background_color`, gradient stops | LAB ΔE distance to profile colors. <5 → snap to global. 5–15 → ask (warning). >15 → promote to Kit `custom_colors` (POST /kit) and use new global reference. |
| 2. Fonts | `typography_font_family` | Match profile.fonts.primary/secondary by exact family name → `__globals__["typography_typography"] = "globals/typography?id=primary|secondary"`. Remove `typography_typography:"custom"`. Unknown family → leave hardcoded. |
| 3. Typography sizes | `typography_font_size`, weight, line-height | Classify by size (≥56 → h1; ≥40 → h2; ≥28 → h3; ≥18 → body; else small). Set typography global reference. Remove hardcoded size/weight/line-height. |
| 4. Section padding | top-level section `padding`, `padding_mobile` | Snap to `profile.layout.section_padding[_mobile]` if within tolerance. |
| 5. Content width | section `content_width` | Snap to `profile.layout.content_width` if Δ ≤ 100px. |
| 6. Button defaults | button widget settings | `border_radius`, `text_padding` from `profile.buttons`. Typography → primary global. Background → primary color global. |

### 11.1 Color overflow policy
When a section uses more colors than the profile defines:
- Extras are auto-promoted to `custom_colors` in the Elementor Kit (one POST `/kit` patch per normalize call, deduped by hex).
- Naming: `custom-1`, `custom-2`, … Plugin maintains the next index per Kit.

### 11.2 Responsive policy
- Strip all `*_tablet` keys (we don't model tablet at the profile level).
- Preserve and normalize `*_mobile` against `profile.typography.*.mobile` and `profile.layout.section_padding_mobile`.

### 11.3 Diff report shape
```json
{
  "colors_remapped": [{"from": "#0066FF", "to": "primary", "delta_e": 2.1}],
  "colors_promoted": [{"hex": "#FF6B35", "added_as": "custom-1"}],
  "fonts_remapped": [{"from": "Manrope", "to": "primary"}],
  "sizes_snapped": [{"from": 52, "to": "h1", "px": 64}],
  "padding_snapped": [{"section": "44b1bea6", "delta": 40}],
  "tablet_stripped": 12,
  "skipped_unknown": [{"widget": "exotic-widget", "reason": "unmapped"}]
}
```

### 11.4 Color distance math
Use `colormath`'s `delta_e_cie2000` on sRGB→LAB conversions. Threshold constants live in `core/kit_normalizer.py` (`DELTA_SNAP = 5`, `DELTA_ASK = 15`).

---

## 12. Library management

### 12.1 Verify
`scripts/verify_library.py` (also exposed as `library.verify`):
- Scan all files, validate Elementor schema.
- Auto-migrate deprecated widget names where mapping is known.
- Move broken files to `rejected/`, with reason in `manifest.json`.
- Rebuild index.

### 12.2 Import — four sources
| Source | v1? | Implementation |
|---|---|---|
| Upload JSON | ✓ | Validate schema, save under `imported/<uuid>.json`, index. |
| Snapshot existing page | ✓ | Read `_elementor_data` from a page on the same WP, save as template. |
| Paste HTML / URL | ✓ | BeautifulSoup parse → AI assist (Claude/GPT) maps DOM → closest matching template or composed JSON. Preview before save. |
| Upload screenshot | ✓ | GPT-4V / Claude vision analyzes layout → either suggests matching templates from the library or generates new JSON; preview before save. |

> All four are in v1 per user decision. HTML/image importers depend on LLM calls and are gated by `OPENAI_API_KEY` / Anthropic key being available.

### 12.3 Admin UI flow
Single admin page "Elementor MCP":
- Stats bar (counts, last verify, broken count).
- Buttons: Verify, Re-index, Rebuild AI tags.
- Import form (radio: source type) + preview pane.
- Library browser with filters (category, source, valid status).
- API key manager.
- Profile manager (list + edit JSON).

---

## 13. Research module

Module: `core/research/`.

### 13.1 Components
- `crawler.py` — async fetch with `httpx`, configurable depth (default 2), candidate path heuristics by language (e.g., `/about`, `/gioi-thieu`).
- `brand_extractor.py` — logo lookup, color extraction from inline + linked CSS, font detection from `<link>` Google Fonts + `@font-face`, industry inference from `<meta>` + schema.org.
- `content_extractor.py` — `readability-lxml` for clean main content; headings; product/service lists.
- `layout_sniffer.py` — Playwright headless screenshot → AI vision categorization (`minimal | dense | corporate | modern | playful`).
- `voice_analyzer.py` — small LLM call on text samples → tone summary + voice tags.
- `profile_deriver.py` — dossier → profile candidate JSON.

### 13.2 Research dossier shape
```json
{
  "brand": {"name": "...", "logo": "url", "colors": [...], "fonts": [...], "industry": "...", "voice": "..."},
  "existing": {"about_copy": "...", "products": [...], "mission": "...", "values": [...]},
  "layout_vibe": "corporate-clean",
  "target_audience_inferred": "B2B businesses",
  "cached_at": "ISO timestamp"
}
```

### 13.3 Caching & ethics
- Dossier cached 24 h (keyed by URL) in `data/research_cache.db`.
- Screenshots cached 30 d.
- Respect `robots.txt`. UA: `ElementorMCP/1.0 (+https://github.com/<repo>)`.
- Rate limit: 1 request/sec per host. Max 5 pages per crawl by default.

---

## 14. Error handling

### 14.1 Tool result envelope
```json
{
  "ok": false,
  "data": null,
  "warnings": [],
  "error": {"code": "E_NO_PROFILE", "message": "...", "fix_hint": "..."}
}
```

### 14.2 Error codes
`E_NO_PROFILE`, `E_WP_AUTH`, `E_WP_UNREACHABLE`, `E_PAGE_NOT_FOUND`, `E_SECTION_NOT_FOUND`, `E_INVALID_JSON`, `E_TEMPLATE_NOT_FOUND`, `E_IMAGE_GEN_FAILED` (fallback used → still `ok: true` with warning), `E_NORMALIZE_PARTIAL`, `E_CRAWL_BLOCKED`, `E_BACKUP_FAILED`, `E_RESTORE_FAILED`.

### 14.3 Plugin-side patterns
- Every endpoint wrapped in try/catch, returns `WP_REST_Response` with code + message.
- Schema validation via `register_rest_route` `args` definitions.
- Section writes are atomic: WP transient lock per page_id (5 s ttl) prevents concurrent mutation.
- Custom logger writes to `wp-content/elementor-mcp-logs/yyyy-mm-dd.log`, rotated 7 days.

### 14.4 Recovery
- `prototyper.compose_page` is atomic: snapshot existing `_elementor_data` first; on any subsequent failure, restore and delete the new page if just created.
- `section.add/update/delete` always push current state into `_elementor_data_backup_history` (5 versions max) before write.

---

## 15. Backup & restore

- After each mutation, prepend `{version, timestamp, data}` to `_elementor_data_backup_history`; truncate to 5 entries.
- `GET /pages/{id}/backups` → list `{version, timestamp, sections_count}` only.
- `POST /pages/{id}/backups/{version}/restore` → replace `_elementor_data`, clear cache, and push the prior state into history (so restore itself is reversible).

---

## 16. Testing strategy

### 16.1 WP plugin
- **Unit (PHPUnit + Brain Monkey + WP_Mock):** auth filter, REST schema validation, section parsing, cache invalidation, backup ring-buffer.
- **Integration (wp-env Docker):** real WP, end-to-end REST calls; concurrent-write lock test; profile→Kit translation correctness.

### 16.2 MCP server
- **Unit (pytest, no network):**
  - Normalizer six passes — golden fixture tests (`fixtures/templates/L1.json` × `fixtures/profiles/saas-blue.json` → `fixtures/expected/L1__saas-blue.normalized.json`).
  - Color ΔE math.
  - Indexer metadata extraction on a sample of 20 representative templates.
  - Hybrid search ranking with mocked vectors.
  - Research crawler with mocked HTML.
- **Integration (mocked WP):** full compose flow with `responses` mocking WP REST.
- **E2E (nightly, slow):** real WP + real MCP + Playwright screenshot of composed pages.

### 16.3 CI (GitHub Actions)
- Lint (ruff + phpcs).
- Unit on every push.
- Integration on PR.
- E2E nightly + on release tags.
- Coverage gate: 80% on `core/` modules.

---

## 17. Deployment

### 17.1 WP plugin
- Distribute as `elementor-mcp-bridge.zip`.
- Install on `elementor.leobot.online`.
- Activate, open the "Elementor MCP" admin page.
- Generate first API key (shown once).
- Set MCP HTTP API URL if running library mgmt server.
- Requirements: Elementor ≥ 3.18, PHP ≥ 7.4, WP ≥ 6.0.

### 17.2 MCP server (per-developer machine)
```bash
git clone …
cd mcp-server
uv venv && uv pip install -e .
cp .env.example .env   # fill WP_URL, WP_API_KEY, OPENAI_API_KEY (optional), UNSPLASH_ACCESS_KEY (optional)
python scripts/build_index.py          # Stage B (~5 min)
# Stage C: run the Codex task per docs/codex-tasks/ai-augment.md
```

### 17.3 Register MCP with the agent
```bash
# Claude Code (per-user)
claude mcp add elementor -s user -- python -m elementor_mcp.server
```
For Cursor / Codex, add the equivalent entry in their MCP config.

### 17.4 Optional HTTP server (for admin UI library calls)
```bash
python -m elementor_mcp.http_server --port 8765
```
Set `elementor_mcp_mcp_url=http://localhost:8765` in WP options (or the public URL if MCP runs on the VPS).

### 17.5 `.env`
```
WP_URL=https://elementor.leobot.online
WP_API_KEY=emcp_xxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-…               # optional, fallback to Unsplash
UNSPLASH_ACCESS_KEY=…             # optional, for fallback image source
ANTHROPIC_API_KEY=sk-…            # optional, for vision import + voice analysis
CACHE_DIR=~/.cache/elementor-mcp
LOG_LEVEL=info
```

---

## 18. Timeline

| Phase | Scope | Duration |
|---|---|---|
| 0 | Repo skeleton, WP plugin auth + REST scaffold, MCP bootstrap, wp-env dev environment | 1 week |
| 1 | Profile CRUD, section CRUD, library Stage B, FTS5 keyword search, normalizer (six passes + custom_colors overflow), image gen with fallback, library admin UI for JSON upload + snapshot + verify, backup/restore | 2–3 weeks |
| 2 | Stage C augmentation (delegated to Codex), sqlite-vec setup, hybrid search, `prototyper.compose_page`, `prototyper.suggest_sections`, `prototyper.replace_section`, profile auto-derive | 1–2 weeks |
| 3 | `core/research/` module, crawler, brand extractor, voice analyzer, layout sniffer (Playwright + vision), `prototyper.compose_from_url` | 1–2 weeks |
| 4 | Library import from HTML + screenshot (vision), section history UI in admin | 1–2 weeks |

**Total: 6–10 weeks** for full v1 vision (all four phases).

---

## 19. Open items / non-blocking

- Define exactly which Elementor widgets are first-class supported vs best-effort. (Spec assumes core widgets; can expand.)
- Decide whether the MCP HTTP server runs on the same VPS as WP (recommended for the admin UI roundtrip).
- Codex task brief (`docs/codex-tasks/ai-augment.md`) — to be written separately as part of Phase 2 kickoff.
- Future: multi-site mode (out of v1 scope).
- Future: collaborative locks if multiple agents work on the same page simultaneously.
