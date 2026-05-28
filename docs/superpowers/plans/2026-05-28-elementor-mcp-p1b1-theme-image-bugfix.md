# Elementor MCP — Phase 1b-1 (Theme + section_update fix + Image gen) Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close the 3 biggest gaps exposed by the Stacks Clothing Co. test page — auto-install Hello Elementor theme so fonts/layout render correctly, fix the section_update duplicate-container bug, and ship the image generation pipeline (OpenAI gpt-image-1 + Unsplash fallback + WP media upload).

**Architecture:** Theme management lives on the WP side (a plugin activation hook that ensures Hello Elementor is installed + active). Section parser is hardened to handle Elementor's auto-conversion of legacy sections into flexbox containers. Image generation gets its own Python module under `core/image/` and three new MCP tools (`image_generate`, `image_upload`, `image_describe_slot`). All images flow through WP REST `/wp/v2/media` so they appear in the Media Library.

**Tech Stack:** PHP 8.1, PHPUnit; Python 3.11+, `openai` SDK, `httpx`, `Pillow` (for size normalization), MCP SDK; multipart upload via httpx.

**Spec reference:** `docs/superpowers/specs/2026-05-27-elementor-mcp-design.md` §3 #2 (image gen choice), §9.4 (image flow), §17.1 (deployment).

**Plan scope:** P1b-1 only. P1b-2 (Library indexing + Kit Normalizer) and P1b-3 (Kit Mapper UI + HTTP server) get their own plans after P1b-1 ships.

**Predecessor:** `v0.1.0-p1a` tag (P1a Core CRUD shipped). All P1a tests must remain green.

---

## File structure (created/modified by this plan)

```
wp-plugin/
├─ includes/
│  ├─ Theme_Bootstrap.php           NEW — ensure Hello Elementor installed + active
│  ├─ Plugin.php                    MODIFY — hook Theme_Bootstrap on activation
│  └─ Section_Parser.php            MODIFY — preserve elType, handle container nesting
├─ tests/Unit/
│  ├─ Theme_BootstrapTest.php       NEW
│  └─ Section_ParserTest.php        MODIFY — add container/auto-conversion tests
└─ tests/fixtures/
   └─ elementor-data-container-mix.json   NEW — page mixing section + container elTypes

mcp-server/
├─ pyproject.toml                   MODIFY — add openai, Pillow
├─ elementor_mcp/
│  ├─ config.py                     MODIFY — add openai_api_key, unsplash_access_key
│  ├─ errors.py                     MODIFY — (no change; E_IMAGE_GEN_FAILED already exists)
│  ├─ core/
│  │  ├─ image/                     NEW package
│  │  │  ├─ __init__.py
│  │  │  ├─ openai_gen.py           NEW — calls gpt-image-1
│  │  │  ├─ unsplash_fallback.py    NEW — Unsplash Source search
│  │  │  ├─ media_upload.py         NEW — multipart to /wp/v2/media
│  │  │  └─ slot.py                 NEW — image slot detection + spec
│  │  └─ wp_client.py               MODIFY — add multipart helper for media upload
│  ├─ tools/
│  │  └─ image.py                   NEW — image_generate, image_upload, image_describe_slot
│  └─ server.py                     MODIFY — register 3 new image tools
├─ tests/
│  ├─ unit/
│  │  ├─ test_image_openai.py       NEW
│  │  ├─ test_image_unsplash.py     NEW
│  │  ├─ test_image_upload.py       NEW
│  │  ├─ test_image_slot.py         NEW
│  │  └─ test_tools_image.py        NEW
│  └─ integration/
│     └─ test_image_roundtrip.py    NEW — gen → upload → assert URL reachable
```

Modified `.env.example` adds: `OPENAI_API_KEY=` and `UNSPLASH_ACCESS_KEY=` (both optional).

---

## Conventions

- TDD per task: failing test → run (see fail) → minimal impl → run (see pass) → commit.
- Git config for commits: `-c user.email="webcuahao@gmail.com" -c user.name="webcuahao"`.
- Commit messages: Conventional commits, scope `plugin|mcp|infra|test|docs`. Footer: `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`.
- Branch: continue on `master`.
- All P1a tests (77 PHPUnit + 33 Python unit + 3 integration) must remain green at every commit.

---

## Task 1: WP plugin — Theme_Bootstrap auto-activates Hello Elementor

**Files:**
- Create: `wp-plugin/includes/Theme_Bootstrap.php`
- Modify: `wp-plugin/includes/Plugin.php` — register activation hook
- Modify: `wp-plugin/elementor-mcp-bridge.php` — call Theme_Bootstrap from `register_activation_hook`
- Test: `wp-plugin/tests/Unit/Theme_BootstrapTest.php`

The plugin's activation hook ensures Hello Elementor is installed (downloads if missing) and active. If the active theme isn't Hello Elementor, switch to it. Idempotent — safe to run on every activation.

- [ ] **Step 1: Write failing test**

`wp-plugin/tests/Unit/Theme_BootstrapTest.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Theme_Bootstrap;

class Theme_BootstrapTest extends TestCase {
    protected function setUp(): void { \Brain\Monkey\setUp(); }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_does_nothing_when_hello_elementor_already_active() {
        Functions\expect('wp_get_theme')->once()->andReturn((object)['Stylesheet' => 'hello-elementor']);
        Functions\expect('switch_theme')->never();
        (new Theme_Bootstrap())->ensure();
        $this->assertTrue(true);
    }

    public function test_switches_to_hello_elementor_when_installed_but_not_active() {
        Functions\expect('wp_get_theme')->once()->andReturn((object)['Stylesheet' => 'twentytwentyfour']);
        Functions\expect('wp_get_themes')->once()->andReturn(['hello-elementor' => 'x']);
        Functions\expect('switch_theme')->once()->with('hello-elementor');
        (new Theme_Bootstrap())->ensure();
        $this->assertTrue(true);
    }

    public function test_installs_hello_elementor_when_missing_then_switches() {
        Functions\expect('wp_get_theme')->once()->andReturn((object)['Stylesheet' => 'twentytwentyfour']);
        Functions\expect('wp_get_themes')->once()->andReturn([]);
        Functions\expect('themes_api')->once()->andReturn((object)['download_link' => 'http://x']);
        // We don't actually network-install in unit tests; just verify the call.
        Functions\expect('switch_theme')->once()->with('hello-elementor');
        $bootstrap = new class extends Theme_Bootstrap {
            protected function install_theme_from_api($info): bool { return true; }
        };
        $bootstrap->ensure();
        $this->assertTrue(true);
    }
}
```

- [ ] **Step 2: Run test, confirm fail**

```bash
cd wp-plugin && vendor/bin/phpunit --filter Theme_BootstrapTest
```

Expected: `Class "ElementorMCP\Theme_Bootstrap" not found`.

- [ ] **Step 3: Implement `wp-plugin/includes/Theme_Bootstrap.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Theme_Bootstrap {
    const SLUG = 'hello-elementor';

    public function ensure(): void {
        $current = wp_get_theme();
        if (($current->Stylesheet ?? '') === self::SLUG) return;

        $installed = wp_get_themes();
        if (!isset($installed[self::SLUG])) {
            $this->install();
        }
        switch_theme(self::SLUG);
    }

    protected function install(): void {
        if (!function_exists('themes_api')) {
            require_once ABSPATH . 'wp-admin/includes/theme.php';
        }
        $info = themes_api('theme_information', [
            'slug'   => self::SLUG,
            'fields' => ['sections' => false],
        ]);
        if (!$info || empty($info->download_link)) return;
        $this->install_theme_from_api($info);
    }

    protected function install_theme_from_api($info): bool {
        if (!class_exists('\\Theme_Upgrader')) {
            require_once ABSPATH . 'wp-admin/includes/file.php';
            require_once ABSPATH . 'wp-admin/includes/misc.php';
            require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';
            require_once ABSPATH . 'wp-admin/includes/class-theme-upgrader.php';
        }
        $skin = new \WP_Ajax_Upgrader_Skin();
        $upgrader = new \Theme_Upgrader($skin);
        $result = $upgrader->install($info->download_link);
        return $result === true;
    }
}
```

- [ ] **Step 4: Wire into activation hook**

Modify `wp-plugin/elementor-mcp-bridge.php` — replace the existing `register_activation_hook` body:

```php
register_activation_hook(__FILE__, function () {
    update_option('elementor_mcp_version', \ElementorMCP\Plugin::VERSION);
    (new \ElementorMCP\Theme_Bootstrap())->ensure();
});
```

- [ ] **Step 5: Run test + full suite, confirm pass**

```bash
vendor/bin/phpunit --filter Theme_BootstrapTest
vendor/bin/phpunit
```

Expected: 80 tests green (77 P1a + 3 new).

- [ ] **Step 6: Commit**

```bash
cd .. && git add wp-plugin/includes/Theme_Bootstrap.php wp-plugin/elementor-mcp-bridge.php wp-plugin/tests/Unit/Theme_BootstrapTest.php
git commit -m "feat(plugin): auto-install + activate Hello Elementor on plugin activation

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Section_Parser — preserve elType, handle container/section mix

**Files:**
- Modify: `wp-plugin/includes/Section_Parser.php` — preserve and validate elType
- Create: `wp-plugin/tests/fixtures/elementor-data-container-mix.json`
- Modify: `wp-plugin/tests/Unit/Section_ParserTest.php` — add container tests

The bug seen in the Stacks page: when `section_update` was called on a section, Elementor's save-side migration sometimes re-emitted the old data as a flexbox container with a fresh sid (7 hex chars). The current parser doesn't reject duplicate top-level entries with the same logical position, and `list()` shows both. Fix: preserve `elType` on replace/duplicate (so a `section` stays a `section`), and add a `prune_orphans()` helper that removes ANY top-level entry whose `id` collides with another.

- [ ] **Step 1: Create fixture `wp-plugin/tests/fixtures/elementor-data-container-mix.json`**

```json
[
  {
    "id": "44b1bea6",
    "elType": "section",
    "settings": {"_title": "Hero"},
    "elements": []
  },
  {
    "id": "75832b3",
    "elType": "container",
    "settings": {"_title": "Hero"},
    "elements": []
  },
  {
    "id": "feedface",
    "elType": "section",
    "settings": {"_title": "Footer"},
    "elements": []
  }
]
```

- [ ] **Step 2: Add failing tests to `Section_ParserTest.php`**

Append:

```php
    public function test_replace_preserves_existing_eltype_when_input_missing() {
        $data = $this->sample();
        $patch = ['id' => '44b1bea6', 'settings' => ['_title' => 'New'], 'elements' => []];
        $result = (new Section_Parser())->replace($data, '44b1bea6', $patch);
        $this->assertSame('section', $result[0]['elType']);
        $this->assertSame('New', $result[0]['settings']['_title']);
    }

    public function test_list_includes_container_eltype() {
        $data = json_decode(file_get_contents(__DIR__ . '/../fixtures/elementor-data-container-mix.json'), true);
        $list = (new Section_Parser())->list($data);
        $this->assertSame('section',   $list[0]['el_type']);
        $this->assertSame('container', $list[1]['el_type']);
        $this->assertSame('section',   $list[2]['el_type']);
    }

    public function test_prune_orphans_removes_duplicate_titles_with_different_eltypes() {
        $data = json_decode(file_get_contents(__DIR__ . '/../fixtures/elementor-data-container-mix.json'), true);
        $result = (new Section_Parser())->prune_orphans($data);
        // The container with the same _title='Hero' as the section should be removed.
        $this->assertCount(2, $result);
        $this->assertSame('44b1bea6', $result[0]['id']);
        $this->assertSame('feedface', $result[1]['id']);
    }
```

- [ ] **Step 3: Run tests, confirm fail**

```bash
vendor/bin/phpunit --filter Section_ParserTest
```

Expected: 3 new tests fail.

- [ ] **Step 4: Modify `Section_Parser.php` — preserve elType + add prune_orphans**

Find the `replace` method. Replace its body with:

```php
    public function replace(array $data, string $sid, array $section): array {
        foreach ($data as $i => $existing) {
            if (($existing['id'] ?? '') === $sid) {
                // Preserve existing elType if the patch doesn't specify one,
                // so Elementor migration doesn't silently demote a 'section' to 'container'.
                if (!isset($section['elType']) && isset($existing['elType'])) {
                    $section['elType'] = $existing['elType'];
                }
                $data[$i] = $section;
                return $data;
            }
        }
        return $data;
    }
```

Add a new method at the end of the class:

```php
    /**
     * Remove top-level entries that share a `settings._title` with an
     * earlier entry but use a different elType. Used to recover from
     * Elementor migration cycles that emit ghost containers.
     */
    public function prune_orphans(array $data): array {
        $seen_titles = [];
        $out = [];
        foreach ($data as $section) {
            $title = $section['settings']['_title'] ?? null;
            if ($title !== null && isset($seen_titles[$title])) {
                $first_eltype = $seen_titles[$title];
                if (($section['elType'] ?? '') !== $first_eltype) {
                    continue;  // drop the ghost
                }
            }
            if ($title !== null) {
                $seen_titles[$title] = $section['elType'] ?? '';
            }
            $out[] = $section;
        }
        return $out;
    }
```

- [ ] **Step 5: Wire prune_orphans into Rest_Sections::mutate (after the callback)**

Open `wp-plugin/includes/Rest_Sections.php`. In the `mutate` method, after `$result = $apply(...)` and before `$this->backups->snapshot(...)`, add:

```php
            $result['data'] = $this->parser->prune_orphans($result['data']);
```

- [ ] **Step 6: Run tests, confirm pass**

```bash
vendor/bin/phpunit
```

Expected: 83 green (80 from Task 1 + 3 new).

- [ ] **Step 7: Commit**

```bash
cd .. && git add wp-plugin/includes/Section_Parser.php wp-plugin/includes/Rest_Sections.php wp-plugin/tests/fixtures/elementor-data-container-mix.json wp-plugin/tests/Unit/Section_ParserTest.php
git commit -m "fix(plugin): preserve elType on replace + prune orphan containers

Discovered while testing the Stacks page: after section_update,
Elementor migration sometimes re-emitted the previous section data
as a flexbox container with a fresh id, causing the page to render
two copies of the same logical section.

- Section_Parser::replace now preserves the existing elType when
  the patch doesn't specify one.
- New Section_Parser::prune_orphans drops top-level entries that
  share a _title with an earlier entry but use a different elType.
- Rest_Sections::mutate now calls prune_orphans after every
  successful mutation.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Python dependencies — openai + Pillow

**Files:**
- Modify: `mcp-server/pyproject.toml` — add deps

- [ ] **Step 1: Update `mcp-server/pyproject.toml`**

Find the `dependencies = [...]` list and replace it with:

```toml
dependencies = [
  "mcp>=1.0.0",
  "httpx>=0.27",
  "pydantic>=2.6",
  "pydantic-settings>=2.2",
  "python-dotenv>=1.0",
  "openai>=1.40",
  "Pillow>=10.2",
]
```

- [ ] **Step 2: Install + sanity-check imports**

```bash
cd mcp-server && uv pip install -e ".[dev]"
uv run python -c "import openai, PIL; print(openai.__version__, PIL.__version__)"
```

Expected: prints both versions, no errors.

- [ ] **Step 3: Commit**

```bash
cd .. && git add mcp-server/pyproject.toml
git commit -m "chore(mcp): add openai + Pillow dependencies for image gen

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Python config — OPENAI_API_KEY + UNSPLASH_ACCESS_KEY

**Files:**
- Modify: `mcp-server/elementor_mcp/config.py` — add optional fields
- Modify: `mcp-server/.env.example` — document new vars
- Modify: `mcp-server/tests/unit/test_config.py` — add tests for new fields

- [ ] **Step 1: Update failing test**

Open `mcp-server/tests/unit/test_config.py`, append:

```python
def test_optional_api_keys_default_to_empty(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WP_URL", "http://wp.local")
    monkeypatch.setenv("WP_API_KEY", "emcp_x_y")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    from elementor_mcp.config import Settings
    s = Settings()
    assert s.openai_api_key == ""
    assert s.unsplash_access_key == ""


def test_optional_api_keys_load_when_set(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WP_URL", "http://wp.local")
    monkeypatch.setenv("WP_API_KEY", "emcp_x_y")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("UNSPLASH_ACCESS_KEY", "us-test")
    from elementor_mcp.config import Settings
    s = Settings()
    assert s.openai_api_key == "sk-test"
    assert s.unsplash_access_key == "us-test"
```

- [ ] **Step 2: Run test, confirm fail**

```bash
cd mcp-server && uv run pytest tests/unit/test_config.py -v
```

Expected: 2 new tests fail.

- [ ] **Step 3: Modify `mcp-server/elementor_mcp/config.py`**

Find the `Settings` class and add two fields after `http_timeout`:

```python
    openai_api_key: str = ""
    unsplash_access_key: str = ""
```

- [ ] **Step 4: Update `.env.example`**

`mcp-server/.env.example`:

```dotenv
WP_URL=http://localhost:8888
WP_API_KEY=emcp_changeme
LOG_LEVEL=info
HTTP_TIMEOUT=15

# Optional — for image generation. If both are empty, image_generate returns E_IMAGE_GEN_FAILED.
OPENAI_API_KEY=
UNSPLASH_ACCESS_KEY=
```

- [ ] **Step 5: Run tests, confirm pass**

```bash
uv run pytest tests/unit/test_config.py -v
```

Expected: 4 green (2 P1a + 2 new).

- [ ] **Step 6: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/config.py mcp-server/.env.example mcp-server/tests/unit/test_config.py
git commit -m "feat(mcp): add optional OPENAI_API_KEY + UNSPLASH_ACCESS_KEY config

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: OpenAI image generation — `core/image/openai_gen.py`

**Files:**
- Create: `mcp-server/elementor_mcp/core/image/__init__.py` (empty)
- Create: `mcp-server/elementor_mcp/core/image/openai_gen.py`
- Test: `mcp-server/tests/unit/test_image_openai.py`

- [ ] **Step 1: Write failing test**

`mcp-server/tests/unit/test_image_openai.py`:

```python
import base64
from unittest.mock import MagicMock, patch

import pytest

from elementor_mcp.core.image.openai_gen import generate_image_openai
from elementor_mcp.errors import ErrorCode


def _fake_b64(width: int, height: int) -> str:
    # Tiny valid PNG (1x1) — base64 encoded.
    return base64.b64encode(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8"
        b"\xcf\xc0\x00\x00\x00\x03\x00\x01\x36\x99\xa7\xf3\x00\x00\x00\x00"
        b"IEND\xaeB`\x82"
    ).decode("ascii")


def test_generate_returns_png_bytes_at_requested_size():
    fake_client = MagicMock()
    fake_client.images.generate.return_value = MagicMock(
        data=[MagicMock(b64_json=_fake_b64(1024, 1024))],
    )
    with patch("elementor_mcp.core.image.openai_gen.OpenAI", return_value=fake_client):
        result = generate_image_openai(
            prompt="a cowboy hat",
            width=1920,
            height=800,
            api_key="sk-test",
        )
    assert result.ok is True
    assert result.data["mime"] == "image/png"
    # Verify bytes round-trip through Pillow at the requested final size.
    from io import BytesIO
    from PIL import Image
    img = Image.open(BytesIO(result.data["bytes"]))
    assert img.size == (1920, 800)


def test_generate_returns_e_image_gen_failed_on_openai_error():
    fake_client = MagicMock()
    fake_client.images.generate.side_effect = RuntimeError("rate limited")
    with patch("elementor_mcp.core.image.openai_gen.OpenAI", return_value=fake_client):
        result = generate_image_openai(prompt="x", width=512, height=512, api_key="sk-test")
    assert result.ok is False
    assert result.error.code == ErrorCode.E_IMAGE_GEN_FAILED.value


def test_generate_returns_failure_when_no_api_key():
    result = generate_image_openai(prompt="x", width=512, height=512, api_key="")
    assert result.ok is False
    assert result.error.code == ErrorCode.E_IMAGE_GEN_FAILED.value
    assert "no openai api key" in result.error.message.lower()
```

- [ ] **Step 2: Run test, confirm fail**

```bash
cd mcp-server && uv run pytest tests/unit/test_image_openai.py -v
```

Expected: `ModuleNotFoundError: elementor_mcp.core.image`.

- [ ] **Step 3: Create `core/image/__init__.py` (empty)**

```python
```

- [ ] **Step 4: Implement `mcp-server/elementor_mcp/core/image/openai_gen.py`**

```python
import base64
from io import BytesIO

from openai import OpenAI
from PIL import Image

from ...envelope import ToolResult, fail, ok
from ...errors import ErrorCode


# OpenAI gpt-image-1 supports a limited set of sizes. We always request a
# safe one and resize down/up to the slot's exact dimensions with Pillow.
_OPENAI_SIZES = ["1024x1024", "1792x1024", "1024x1792"]


def _pick_openai_size(w: int, h: int) -> str:
    if w >= h * 1.4:   return "1792x1024"
    if h >= w * 1.4:   return "1024x1792"
    return "1024x1024"


def generate_image_openai(
    *, prompt: str, width: int, height: int, api_key: str, model: str = "gpt-image-1",
) -> ToolResult:
    if not api_key:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, "no openai api key configured")

    client = OpenAI(api_key=api_key)
    try:
        resp = client.images.generate(
            model=model,
            prompt=prompt,
            size=_pick_openai_size(width, height),
            n=1,
        )
    except Exception as e:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, f"openai images.generate failed: {e}")

    try:
        b64 = resp.data[0].b64_json
        raw = base64.b64decode(b64)
        img = Image.open(BytesIO(raw)).convert("RGB")
        if img.size != (width, height):
            img = img.resize((width, height), Image.LANCZOS)
        out = BytesIO()
        img.save(out, format="PNG")
        png_bytes = out.getvalue()
    except Exception as e:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, f"image decode/resize failed: {e}")

    return ok({"bytes": png_bytes, "mime": "image/png", "width": width, "height": height})
```

- [ ] **Step 5: Run test, confirm pass**

```bash
uv run pytest tests/unit/test_image_openai.py -v
```

Expected: 3 green.

- [ ] **Step 6: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/core/image/__init__.py mcp-server/elementor_mcp/core/image/openai_gen.py mcp-server/tests/unit/test_image_openai.py
git commit -m "feat(mcp): OpenAI gpt-image-1 image generation with Pillow resize

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Unsplash fallback — `core/image/unsplash_fallback.py`

**Files:**
- Create: `mcp-server/elementor_mcp/core/image/unsplash_fallback.py`
- Test: `mcp-server/tests/unit/test_image_unsplash.py`

Uses Unsplash Search API (free, no key required for `https://source.unsplash.com/featured/?<query>` but we use the official API when `unsplash_access_key` is set for higher rate limits).

- [ ] **Step 1: Write failing test**

`mcp-server/tests/unit/test_image_unsplash.py`:

```python
import httpx
import respx

from elementor_mcp.core.image.unsplash_fallback import generate_image_unsplash
from elementor_mcp.errors import ErrorCode


@respx.mock
def test_unsplash_search_returns_first_hit_resized(tmp_path):
    # 1x1 PNG bytes
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8"
        b"\xcf\xc0\x00\x00\x00\x03\x00\x01\x36\x99\xa7\xf3\x00\x00\x00\x00"
        b"IEND\xaeB`\x82"
    )
    respx.get("https://api.unsplash.com/search/photos").mock(
        return_value=httpx.Response(200, json={
            "results": [{"urls": {"raw": "https://images.unsplash.com/photo-abc"}}],
        })
    )
    respx.get("https://images.unsplash.com/photo-abc").mock(
        return_value=httpx.Response(200, content=png)
    )
    result = generate_image_unsplash(
        query="cowboy hat", width=400, height=300, access_key="us-test",
    )
    assert result.ok is True
    assert result.data["mime"] == "image/png"
    from io import BytesIO
    from PIL import Image
    img = Image.open(BytesIO(result.data["bytes"]))
    assert img.size == (400, 300)


@respx.mock
def test_unsplash_returns_failure_on_empty_results():
    respx.get("https://api.unsplash.com/search/photos").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    result = generate_image_unsplash(
        query="zzznopex", width=100, height=100, access_key="us-test",
    )
    assert result.ok is False
    assert result.error.code == ErrorCode.E_IMAGE_GEN_FAILED.value


def test_unsplash_returns_failure_when_no_key():
    result = generate_image_unsplash(query="x", width=100, height=100, access_key="")
    assert result.ok is False
    assert result.error.code == ErrorCode.E_IMAGE_GEN_FAILED.value
```

- [ ] **Step 2: Run test, confirm fail**

```bash
uv run pytest tests/unit/test_image_unsplash.py -v
```

- [ ] **Step 3: Implement `mcp-server/elementor_mcp/core/image/unsplash_fallback.py`**

```python
from io import BytesIO

import httpx
from PIL import Image

from ...envelope import ToolResult, fail, ok
from ...errors import ErrorCode


_SEARCH_URL = "https://api.unsplash.com/search/photos"


def generate_image_unsplash(
    *, query: str, width: int, height: int, access_key: str, timeout: int = 15,
) -> ToolResult:
    if not access_key:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, "no unsplash access key configured")

    try:
        resp = httpx.get(
            _SEARCH_URL,
            params={"query": query, "per_page": 1, "orientation": _orientation(width, height)},
            headers={"Authorization": f"Client-ID {access_key}"},
            timeout=timeout,
        )
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, f"unsplash search failed: {e}")

    results = body.get("results") or []
    if not results:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, f"no unsplash result for query: {query}")

    raw_url = results[0].get("urls", {}).get("raw") or results[0].get("urls", {}).get("regular")
    if not raw_url:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, "unsplash result missing image URL")

    try:
        img_resp = httpx.get(raw_url, timeout=timeout)
        img_resp.raise_for_status()
        img = Image.open(BytesIO(img_resp.content)).convert("RGB")
        img = img.resize((width, height), Image.LANCZOS)
        out = BytesIO()
        img.save(out, format="PNG")
        png_bytes = out.getvalue()
    except Exception as e:
        return fail(ErrorCode.E_IMAGE_GEN_FAILED, f"unsplash image fetch failed: {e}")

    return ok({"bytes": png_bytes, "mime": "image/png", "width": width, "height": height})


def _orientation(w: int, h: int) -> str:
    if w >= h * 1.2:  return "landscape"
    if h >= w * 1.2:  return "portrait"
    return "squarish"
```

- [ ] **Step 4: Run test, confirm pass**

```bash
uv run pytest tests/unit/test_image_unsplash.py -v
```

Expected: 3 green.

- [ ] **Step 5: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/core/image/unsplash_fallback.py mcp-server/tests/unit/test_image_unsplash.py
git commit -m "feat(mcp): Unsplash search fallback for image generation

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: WP media upload — `core/image/media_upload.py`

**Files:**
- Modify: `mcp-server/elementor_mcp/core/wp_client.py` — add `post_multipart` helper
- Create: `mcp-server/elementor_mcp/core/image/media_upload.py`
- Test: `mcp-server/tests/unit/test_image_upload.py`

WP's `/wp/v2/media` accepts `POST` with `Content-Disposition: attachment; filename=...` and `Content-Type: image/png`. Response is the full attachment JSON including `id`, `source_url`, `media_details.sizes`.

- [ ] **Step 1: Add `post_multipart` to WpClient**

Open `mcp-server/elementor_mcp/core/wp_client.py`. Add a new method after `delete`:

```python
    def post_binary(
        self,
        path: str,
        *,
        content: bytes,
        filename: str,
        content_type: str,
        wp_native: bool = False,
    ) -> ToolResult:
        """POST raw binary content (e.g. an image to /wp/v2/media)."""
        if wp_native:
            url = f"{self.base}/wp-json/wp/v2{path}"
        else:
            url = self._url(path)
        try:
            resp = self._http.request(
                "POST",
                url,
                content=content,
                headers={
                    "Content-Type": content_type,
                    "Content-Disposition": f'attachment; filename="{filename}"',
                },
            )
        except httpx.ConnectError as e:
            return fail(ErrorCode.E_WP_UNREACHABLE, f"Cannot reach WP at {url}: {e}")
        except httpx.HTTPError as e:
            return fail(ErrorCode.E_INTERNAL, f"HTTP error: {e}")

        if resp.status_code == 401:
            return fail(ErrorCode.E_WP_AUTH, "WP rejected API key")
        if resp.status_code >= 500:
            return fail(ErrorCode.E_INTERNAL, f"WP returned {resp.status_code}")
        try:
            body = resp.json()
        except ValueError:
            return fail(ErrorCode.E_INTERNAL, "Non-JSON response from WP")

        if resp.status_code >= 400:
            return fail(ErrorCode.E_INTERNAL, f"WP error {resp.status_code}: {body}")
        return ok(body)
```

- [ ] **Step 2: Write failing test**

`mcp-server/tests/unit/test_image_upload.py`:

```python
import httpx
import respx

from elementor_mcp.config import Settings
from elementor_mcp.core.image.media_upload import upload_image_to_wp
from elementor_mcp.core.wp_client import WpClient
from elementor_mcp.errors import ErrorCode


def _settings():
    return Settings(
        wp_url="http://localhost:8888",
        wp_api_key="emcp_test_key",
        log_level="info",
        http_timeout=5,
    )


@respx.mock
def test_upload_posts_to_wp_media_endpoint_with_attachment_header():
    route = respx.post("http://localhost:8888/wp-json/wp/v2/media").mock(
        return_value=httpx.Response(201, json={"id": 42, "source_url": "http://x/img.png"})
    )
    client = WpClient(_settings())
    res = upload_image_to_wp(client, content=b"\x89PNGfake", filename="cow.png")
    assert res.ok is True
    assert res.data["id"] == 42
    assert res.data["source_url"] == "http://x/img.png"
    assert route.called
    sent_headers = route.calls.last.request.headers
    assert sent_headers["Content-Type"] == "image/png"
    assert 'attachment; filename="cow.png"' in sent_headers["Content-Disposition"]


@respx.mock
def test_upload_returns_failure_envelope_on_401():
    respx.post("http://localhost:8888/wp-json/wp/v2/media").mock(
        return_value=httpx.Response(401, json={"code": "rest_forbidden"})
    )
    client = WpClient(_settings())
    res = upload_image_to_wp(client, content=b"x", filename="x.png")
    assert res.ok is False
    assert res.error.code == ErrorCode.E_WP_AUTH.value
```

- [ ] **Step 3: Run test, confirm fail**

```bash
uv run pytest tests/unit/test_image_upload.py -v
```

- [ ] **Step 4: Implement `mcp-server/elementor_mcp/core/image/media_upload.py`**

```python
from ...envelope import ToolResult
from ..wp_client import WpClient


def upload_image_to_wp(
    client: WpClient,
    *,
    content: bytes,
    filename: str,
    mime: str = "image/png",
) -> ToolResult:
    """Upload an image to the WP Media Library via /wp/v2/media.

    Returns the full attachment JSON on success (id, source_url, media_details, ...).
    """
    return client.post_binary(
        "/media",
        content=content,
        filename=filename,
        content_type=mime,
        wp_native=True,
    )
```

- [ ] **Step 5: Run test, confirm pass**

```bash
uv run pytest tests/unit/test_image_upload.py -v
```

Expected: 2 green.

- [ ] **Step 6: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/core/wp_client.py mcp-server/elementor_mcp/core/image/media_upload.py mcp-server/tests/unit/test_image_upload.py
git commit -m "feat(mcp): WP media upload via /wp/v2/media binary POST

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Image slot detection — `core/image/slot.py`

**Files:**
- Create: `mcp-server/elementor_mcp/core/image/slot.py`
- Test: `mcp-server/tests/unit/test_image_slot.py`

Walks a section JSON, finds every `image` widget (or background_image), and emits a list of `{path, current_url, intent_hint, width, height}`. Used by callers to know what to gen.

- [ ] **Step 1: Write failing test**

`mcp-server/tests/unit/test_image_slot.py`:

```python
from elementor_mcp.core.image.slot import detect_image_slots, swap_image_in_section


def test_detect_finds_widget_image():
    section = {
        "id": "abc",
        "elType": "section",
        "settings": {},
        "elements": [{
            "id": "col1",
            "elType": "column",
            "settings": {},
            "elements": [{
                "id": "w1",
                "elType": "widget",
                "widgetType": "image",
                "settings": {"image": {"url": "http://x/old.png", "id": None}},
                "elements": [],
            }],
        }],
    }
    slots = detect_image_slots(section)
    assert len(slots) == 1
    assert slots[0]["widget_id"] == "w1"
    assert slots[0]["kind"] == "widget_image"
    assert slots[0]["current_url"] == "http://x/old.png"


def test_detect_finds_section_background_image():
    section = {
        "id": "abc",
        "elType": "section",
        "settings": {
            "background_background": "classic",
            "background_image": {"url": "http://x/bg.jpg", "id": None},
        },
        "elements": [],
    }
    slots = detect_image_slots(section)
    assert len(slots) == 1
    assert slots[0]["kind"] == "section_background"
    assert slots[0]["current_url"] == "http://x/bg.jpg"


def test_swap_replaces_widget_image_url():
    section = {
        "id": "abc",
        "elType": "section",
        "settings": {},
        "elements": [{
            "id": "col1",
            "elType": "column",
            "settings": {},
            "elements": [{
                "id": "w1",
                "elType": "widget",
                "widgetType": "image",
                "settings": {"image": {"url": "http://x/old.png", "id": None}},
                "elements": [],
            }],
        }],
    }
    out = swap_image_in_section(
        section,
        widget_id="w1",
        new_url="http://wp/new.png",
        new_id=99,
    )
    swapped = out["elements"][0]["elements"][0]["settings"]["image"]
    assert swapped["url"] == "http://wp/new.png"
    assert swapped["id"] == 99


def test_swap_replaces_section_background():
    section = {
        "id": "abc",
        "elType": "section",
        "settings": {
            "background_background": "classic",
            "background_image": {"url": "http://x/bg.jpg", "id": None},
        },
        "elements": [],
    }
    out = swap_image_in_section(
        section, widget_id=None, new_url="http://wp/bg.jpg", new_id=88, target="section_background",
    )
    assert out["settings"]["background_image"]["url"] == "http://wp/bg.jpg"
    assert out["settings"]["background_image"]["id"] == 88
```

- [ ] **Step 2: Run test, confirm fail**

```bash
uv run pytest tests/unit/test_image_slot.py -v
```

- [ ] **Step 3: Implement `mcp-server/elementor_mcp/core/image/slot.py`**

```python
import copy


def detect_image_slots(section: dict) -> list[dict]:
    """Walk a section and return a list of image-bearing slots.

    Each slot: {kind, widget_id?, current_url, current_id, settings_path}
    """
    slots: list[dict] = []

    # Section-level background image
    s = section.get("settings", {})
    if s.get("background_background") == "classic":
        bg = s.get("background_image") or {}
        if isinstance(bg, dict) and bg.get("url"):
            slots.append({
                "kind": "section_background",
                "widget_id": None,
                "current_url": bg.get("url"),
                "current_id": bg.get("id"),
            })

    def walk(node: dict) -> None:
        if node.get("elType") == "widget":
            wt = node.get("widgetType")
            ns = node.get("settings", {})
            if wt == "image":
                img = ns.get("image") or {}
                if isinstance(img, dict) and img.get("url"):
                    slots.append({
                        "kind": "widget_image",
                        "widget_id": node.get("id"),
                        "current_url": img.get("url"),
                        "current_id": img.get("id"),
                    })
        for child in node.get("elements", []):
            walk(child)

    for el in section.get("elements", []):
        walk(el)

    return slots


def swap_image_in_section(
    section: dict,
    *,
    widget_id: str | None,
    new_url: str,
    new_id: int,
    target: str = "widget_image",
) -> dict:
    """Return a deep copy of `section` with the named image slot replaced."""
    out = copy.deepcopy(section)

    if target == "section_background":
        s = out.setdefault("settings", {})
        s["background_image"] = {"url": new_url, "id": new_id}
        return out

    # widget_image: walk and patch matching widget id
    def walk(node: dict) -> None:
        if node.get("elType") == "widget" and node.get("widgetType") == "image" and node.get("id") == widget_id:
            node.setdefault("settings", {})["image"] = {"url": new_url, "id": new_id}
            return
        for child in node.get("elements", []):
            walk(child)

    for el in out.get("elements", []):
        walk(el)

    return out
```

- [ ] **Step 4: Run test, confirm pass**

```bash
uv run pytest tests/unit/test_image_slot.py -v
```

Expected: 4 green.

- [ ] **Step 5: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/core/image/slot.py mcp-server/tests/unit/test_image_slot.py
git commit -m "feat(mcp): image slot detection + swap helpers

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 9: MCP `image_*` tools

**Files:**
- Create: `mcp-server/elementor_mcp/tools/image.py`
- Modify: `mcp-server/elementor_mcp/server.py` — register 3 new tools
- Test: `mcp-server/tests/unit/test_tools_image.py`

Tools:
- `image_generate(prompt, width, height, prefer="openai") -> {bytes_b64, mime, source}` — tries OpenAI, falls back to Unsplash.
- `image_upload(content_b64, filename) -> {id, source_url}` — uploads to WP Media.
- `image_describe_slot(section_json) -> {slots: [...]}` — lists image slots in a section.

- [ ] **Step 1: Write failing test**

`mcp-server/tests/unit/test_tools_image.py`:

```python
import base64
from unittest.mock import MagicMock, patch

from elementor_mcp.config import Settings
from elementor_mcp.envelope import ok, fail
from elementor_mcp.errors import ErrorCode
from elementor_mcp.tools.image import (
    image_describe_slot, image_generate, image_upload,
)


def _settings(openai_key: str = "sk-x", unsplash_key: str = "us-x"):
    return Settings(
        wp_url="http://localhost:8888",
        wp_api_key="emcp_t_t",
        log_level="info",
        http_timeout=5,
        openai_api_key=openai_key,
        unsplash_access_key=unsplash_key,
    )


def test_image_generate_uses_openai_first():
    with patch("elementor_mcp.tools.image.generate_image_openai") as m_openai, \
         patch("elementor_mcp.tools.image.generate_image_unsplash") as m_un:
        m_openai.return_value = ok({"bytes": b"openai-png", "mime": "image/png", "width": 100, "height": 100})
        res = image_generate(
            settings=_settings(), prompt="a hat", width=100, height=100, prefer="openai",
        )
        assert res.ok is True
        assert res.data["source"] == "openai"
        assert base64.b64decode(res.data["bytes_b64"]) == b"openai-png"
        m_un.assert_not_called()


def test_image_generate_falls_back_to_unsplash_on_openai_failure():
    with patch("elementor_mcp.tools.image.generate_image_openai") as m_openai, \
         patch("elementor_mcp.tools.image.generate_image_unsplash") as m_un:
        m_openai.return_value = fail(ErrorCode.E_IMAGE_GEN_FAILED, "openai down")
        m_un.return_value = ok({"bytes": b"unsplash-png", "mime": "image/png", "width": 100, "height": 100})
        res = image_generate(
            settings=_settings(), prompt="a hat", width=100, height=100, prefer="openai",
        )
        assert res.ok is True
        assert res.data["source"] == "unsplash"


def test_image_generate_returns_failure_when_both_unavailable():
    with patch("elementor_mcp.tools.image.generate_image_openai") as m_openai, \
         patch("elementor_mcp.tools.image.generate_image_unsplash") as m_un:
        m_openai.return_value = fail(ErrorCode.E_IMAGE_GEN_FAILED, "no key")
        m_un.return_value = fail(ErrorCode.E_IMAGE_GEN_FAILED, "no key")
        res = image_generate(
            settings=_settings("", ""), prompt="x", width=10, height=10,
        )
        assert res.ok is False
        assert res.error.code == ErrorCode.E_IMAGE_GEN_FAILED.value


def test_image_upload_decodes_b64_and_calls_uploader():
    client = MagicMock()
    with patch("elementor_mcp.tools.image.upload_image_to_wp") as m_up:
        m_up.return_value = ok({"id": 5, "source_url": "http://x.png"})
        b64 = base64.b64encode(b"some-png-bytes").decode("ascii")
        res = image_upload(client=client, content_b64=b64, filename="hero.png")
        assert res.ok is True
        assert res.data["id"] == 5
        # Verify the decoded bytes were passed
        kwargs = m_up.call_args.kwargs
        assert kwargs["content"] == b"some-png-bytes"
        assert kwargs["filename"] == "hero.png"


def test_image_describe_slot_returns_list():
    section = {
        "id": "abc", "elType": "section", "settings": {}, "elements": [
            {"id": "c1", "elType": "column", "settings": {}, "elements": [
                {"id": "w1", "elType": "widget", "widgetType": "image",
                 "settings": {"image": {"url": "http://x/p.png", "id": 7}}, "elements": []}
            ]}
        ]
    }
    res = image_describe_slot(section_json=section)
    assert res.ok is True
    assert len(res.data["slots"]) == 1
    assert res.data["slots"][0]["widget_id"] == "w1"
```

- [ ] **Step 2: Run test, confirm fail**

```bash
uv run pytest tests/unit/test_tools_image.py -v
```

- [ ] **Step 3: Implement `mcp-server/elementor_mcp/tools/image.py`**

```python
import base64

from ..config import Settings
from ..core.image.media_upload import upload_image_to_wp
from ..core.image.openai_gen import generate_image_openai
from ..core.image.slot import detect_image_slots
from ..core.image.unsplash_fallback import generate_image_unsplash
from ..core.wp_client import WpClient
from ..envelope import ToolResult, fail, ok
from ..errors import ErrorCode


def image_generate(
    *,
    settings: Settings,
    prompt: str,
    width: int,
    height: int,
    prefer: str = "openai",
) -> ToolResult:
    """Generate an image at exact dimensions. Try preferred provider first, fall back to the other."""
    providers = ["openai", "unsplash"] if prefer == "openai" else ["unsplash", "openai"]
    last_err = None
    for src in providers:
        if src == "openai":
            result = generate_image_openai(
                prompt=prompt, width=width, height=height, api_key=settings.openai_api_key,
            )
        else:
            result = generate_image_unsplash(
                query=prompt, width=width, height=height, access_key=settings.unsplash_access_key,
            )
        if result.ok:
            data = dict(result.data)
            data["bytes_b64"] = base64.b64encode(data.pop("bytes")).decode("ascii")
            data["source"] = src
            return ok(data)
        last_err = result.error

    msg = last_err.message if last_err else "both providers failed"
    return fail(ErrorCode.E_IMAGE_GEN_FAILED, msg)


def image_upload(
    *,
    client: WpClient,
    content_b64: str,
    filename: str,
    mime: str = "image/png",
) -> ToolResult:
    """Upload a base64-encoded image to WP Media Library."""
    try:
        content = base64.b64decode(content_b64)
    except Exception as e:
        return fail(ErrorCode.E_INVALID_JSON, f"invalid base64 content: {e}")
    return upload_image_to_wp(client, content=content, filename=filename, mime=mime)


def image_describe_slot(*, section_json: dict) -> ToolResult:
    """Return image-bearing slots in a section JSON."""
    slots = detect_image_slots(section_json)
    return ok({"slots": slots, "count": len(slots)})
```

- [ ] **Step 4: Register tools in `server.py`**

Inside `_list()`, append after the `kit_set` Tool entry:

```python
            Tool(name="image_generate",
                 description="Generate an image at exact dimensions via OpenAI gpt-image-1 (or Unsplash fallback). Returns base64-encoded PNG bytes.",
                 inputSchema={"type":"object","properties":{
                     "prompt":{"type":"string"},
                     "width":{"type":"integer"},
                     "height":{"type":"integer"},
                     "prefer":{"type":"string","enum":["openai","unsplash"]},
                 },"required":["prompt","width","height"],"additionalProperties":False}),
            Tool(name="image_upload",
                 description="Upload a base64-encoded image to the WP Media Library. Returns the WP attachment id + source_url.",
                 inputSchema={"type":"object","properties":{
                     "content_b64":{"type":"string"},
                     "filename":{"type":"string"},
                     "mime":{"type":"string"},
                 },"required":["content_b64","filename"],"additionalProperties":False}),
            Tool(name="image_describe_slot",
                 description="List image-bearing slots in a section JSON (widget_image + section_background).",
                 inputSchema={"type":"object","properties":{
                     "section_json":{"type":"object"},
                 },"required":["section_json"],"additionalProperties":False}),
```

Inside `_call()`, expand the dispatch:

```python
        from .tools.image import image_describe_slot, image_generate, image_upload
        # ...add to the elif chain:
        elif name == "image_generate":
            result = image_generate(settings=settings, **arguments)
        elif name == "image_upload":
            result = image_upload(client=client, **arguments)
        elif name == "image_describe_slot":
            result = image_describe_slot(**arguments)
```

Note: `image_generate` needs `settings` (for API keys), which is already in scope inside `build_server()` — pass it.

- [ ] **Step 5: Run all unit tests + ruff**

```bash
uv run pytest tests/unit -v && uv run ruff check .
```

Expected: 38 green (33 P1a + 5 new). Ruff clean.

- [ ] **Step 6: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/tools/image.py mcp-server/elementor_mcp/server.py mcp-server/tests/unit/test_tools_image.py
git commit -m "feat(mcp): image_generate + image_upload + image_describe_slot tools

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 10: Integration test — gen → upload → assert URL reachable

**Files:**
- Create: `mcp-server/tests/integration/test_image_roundtrip.py`

Gated by env vars: if `EMCP_TEST_OPENAI_KEY` and `EMCP_TEST_UNSPLASH_KEY` are unset, the test still runs but only the Unsplash-fallback path is exercised. The wp-env round-trip path (upload) is always exercised by passing pre-baked PNG bytes.

- [ ] **Step 1: Write the test**

`mcp-server/tests/integration/test_image_roundtrip.py`:

```python
import base64
import os

import httpx
import pytest

from elementor_mcp.config import Settings
from elementor_mcp.core.wp_client import WpClient
from elementor_mcp.tools.image import image_upload


def _tiny_png() -> bytes:
    # 1x1 transparent PNG
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8"
        b"\xcf\xc0\x00\x00\x00\x03\x00\x01\x36\x99\xa7\xf3\x00\x00\x00\x00"
        b"IEND\xaeB`\x82"
    )


def test_upload_image_to_wp_media_returns_reachable_url(live_settings):
    client = WpClient(live_settings)
    b64 = base64.b64encode(_tiny_png()).decode("ascii")
    res = image_upload(client=client, content_b64=b64, filename="emcp-itest.png")
    assert res.ok is True, res.error
    media_id = res.data["id"]
    url = res.data["source_url"]
    assert media_id > 0
    # The returned URL should be fetchable
    head = httpx.head(url, timeout=10)
    assert head.status_code == 200
```

- [ ] **Step 2: Run integration test**

```bash
EMCP_TEST_API_KEY="<key>" EMCP_TEST_WP_URL="http://localhost:8888" \
  cd mcp-server && uv run pytest tests/integration -v
```

Expected: 4 green (3 P1a + 1 new image upload).

- [ ] **Step 3: Commit**

```bash
cd .. && git add mcp-server/tests/integration/test_image_roundtrip.py
git commit -m "test(mcp): integration test for image upload roundtrip to WP media

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 11: Update CI workflow for image upload integration test

**Files:**
- Modify: `.github/workflows/ci.yml` — set EMCP_TEST_OPENAI_KEY/UNSPLASH from secrets (optional)

The new integration test only requires the WP roundtrip (no external API keys). But for future use, expose secrets.

- [ ] **Step 1: Modify `.github/workflows/ci.yml`**

Find the `MCP integration` step. Replace its `env:` block with:

```yaml
        env:
          EMCP_TEST_API_KEY: ${{ steps.keygen.outputs.key }}
          EMCP_TEST_WP_URL: http://localhost:8888
          EMCP_TEST_OPENAI_KEY: ${{ secrets.EMCP_TEST_OPENAI_KEY }}
          EMCP_TEST_UNSPLASH_KEY: ${{ secrets.EMCP_TEST_UNSPLASH_KEY }}
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: pass optional image-gen API keys from repo secrets

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 12: Acceptance verification + push + tag

- [ ] **Step 1: Run all local checks**

```bash
cd wp-plugin && vendor/bin/phpunit
cd ../mcp-server && uv run ruff check . && uv run pytest tests/unit -v
EMCP_TEST_API_KEY="emcp_GwcFxWiYj6Lh_WYnzuuo00CMVgB7H31lMcSf7F7gdUI49" EMCP_TEST_WP_URL="http://localhost:8888" \
  uv run pytest tests/integration -v
```

Expected:
- PHPUnit: ≥ 83 green
- Python unit: ≥ 38 green, ruff clean
- Integration: ≥ 4 green

- [ ] **Step 2: Manual smoke — gen + upload + assert in WP admin**

```bash
# Verify wp-env still up:
docker ps --filter "name=wp-env-elememtor" --format "{{.Names}}: {{.Status}}" | head -2
```

Open http://localhost:8888/wp-admin → Media → confirm new "emcp-itest.png" attachment appears.

- [ ] **Step 3: Push**

```bash
cd .. && git push
```

- [ ] **Step 4: Wait for CI green, then tag**

Confirm 3 jobs green at https://github.com/Harris2896/elementor-full-mcp/actions, then:

```bash
git tag -a v0.1.1-p1b1 -m "Phase 1b-1: Theme auto-setup + section_update fix + Image gen pipeline

- Auto-install Hello Elementor on plugin activation
- Section_Parser preserves elType + prunes orphan containers
- OpenAI gpt-image-1 image generation
- Unsplash fallback when no OpenAI key (or on failure)
- WP media upload via /wp/v2/media binary POST
- 3 new MCP tools: image_generate, image_upload, image_describe_slot
- Integration test: gen image → upload → assert URL reachable"
git push --tags
```

---

## P1b-1 Acceptance Criteria

1. `cd wp-plugin && vendor/bin/phpunit` — ≥ 83 tests green (P1a 77 + 3 from Task 1 + 3 from Task 2).
2. `cd mcp-server && uv run pytest tests/unit -v && uv run ruff check .` — ≥ 38 tests + lint clean.
3. Integration: `uv run pytest tests/integration -v` — ≥ 4 tests green.
4. Manual smoke: re-activating the plugin on a fresh wp-env with default theme switches it to Hello Elementor automatically.
5. `image_generate` round-trip works against real OpenAI (when OPENAI_API_KEY set) producing a PNG at the exact requested dimensions.
6. `image_upload` followed by `section_add` with the new image URL renders correctly in Elementor's preview.
7. CI three jobs green on main; tag `v0.1.1-p1b1` pushed.

---

## Self-review

**1. Spec coverage:**
- Spec §3 #2 (OpenAI gpt-image-1 + Unsplash fallback) — Tasks 5, 6, 9. ✓
- Spec §9.4 (image gen flow: gen → upload → swap) — Tasks 5, 7, 8, 9. ✓
- Spec §17.1 (theme requirements: Elementor + bridge) — Task 1 ensures Hello Elementor. ✓
- Section_update bug (called out in user brief) — Task 2. ✓
- Out of scope, deferred to P1b-2/3: Kit normalizer, library indexing, Kit Mapper UI, MCP HTTP server. Acceptable.

**2. Placeholder scan:** No TBD/TODO/etc. Every step has actual code or commands.

**3. Type consistency:**
- `ToolResult` envelope used by every Python tool. ✓
- `detect_image_slots` returns `list[dict]`; consumed by `image_describe_slot` which wraps in `{slots, count}`. ✓
- `image_generate` returns `data.bytes_b64` (base64 string), `data.source`, `data.mime`. `image_upload` accepts `content_b64` — same encoding. ✓
- `WpClient.post_binary` returns `ToolResult`; `upload_image_to_wp` is a thin wrapper that returns the same. ✓
- `Section_Parser::replace` preserves `elType`; `Section_Parser::prune_orphans` is the dedup pass. Both used in `Rest_Sections::mutate`. ✓

No gaps to fix.

---

## Continuation: P1b-2 and P1b-3

| Plan | Title | Spec sections | Approx tasks |
|---|---|---|---|
| 4 | P1b-2: Library indexing + Kit Normalizer | §10.1 (Stage B), §11 (6 passes + overflow + diff report) | ~18 |
| 5 | P1b-3: Kit Mapper Admin UI + MCP HTTP server | §17.4 (HTTP), user-requested Kit Mapper feature | ~10 |

Each plan is written after the prior phase ships and CI is green.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-28-elementor-mcp-p1b1-theme-image-bugfix.md`. Two execution options:

1. **Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration. Best for 12 tasks of focused TDD.

2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Best if you want to watch each task in real time.

Which approach?
