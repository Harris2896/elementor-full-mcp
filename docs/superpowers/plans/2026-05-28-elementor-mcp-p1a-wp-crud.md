# Elementor MCP — Phase 1a (WP CRUD + MCP Tools) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship full Profile / Page / Section CRUD on top of `_elementor_data`, with 5-version backup history, the WP-side library-proxy endpoint stubs, and the MCP tools that wrap each REST endpoint. End state: an agent can create a profile, apply it to the Elementor Kit, create a page, add/edit/delete sections via raw JSON, list and restore backups — all via MCP tool calls.

**Architecture:** WP plugin adds a custom post type for profiles (`emcp_profile`), a thin REST namespace already in place, three new endpoint groups (profiles, pages, sections), and helpers for section parsing, backup ring-buffer, cache invalidation, and per-page write locks. Python MCP gains one tool file per endpoint group and registers them in the stdio server alongside the existing `auth_verify`.

**Tech Stack:** PHP 7.4+, WordPress 6.6, PHPUnit 9 + Brain Monkey + WP_Mock; Python 3.11+, `mcp` SDK, `httpx`, `pydantic`, `pytest`, `respx`; CI via the existing GitHub Actions workflow.

**Spec reference:** `docs/superpowers/specs/2026-05-27-elementor-mcp-design.md` §3 #10–#14, §5, §6, §7.2–§7.6, §7.9, §8 (profile, page, section), §9.3, §11.1 (color overflow uses `/kit` PATCH from this plan), §15.

**Plan scope:** Phase 1a only. Phase 1b (Library indexing, Kit normalizer, image gen, library admin UI) will get its own plan after 1a ships.

**Predecessor:** `docs/superpowers/plans/2026-05-27-elementor-mcp-p0-foundation.md` (P0 Foundation — auth + `/auth/verify` + `/health` — must be merged and green before starting).

---

## File structure (created or modified by this plan)

```
wp-plugin/
├─ includes/
│  ├─ Plugin.php                      MODIFY — register CPT + wire new groups
│  ├─ Profile_CPT.php                 NEW — emcp_profile post type registration
│  ├─ Profile_Schema.php              NEW — JSON schema validator
│  ├─ Profile_Repository.php          NEW — load/save profile via postmeta
│  ├─ Kit_Writer.php                  NEW — translate profile → Elementor Kit
│  ├─ Rest_Profiles.php               NEW — /profiles + /profiles/{id}/apply
│  ├─ Rest_Pages.php                  NEW — /pages CRUD
│  ├─ Section_Parser.php              NEW — read/write _elementor_data
│  ├─ Backup_Store.php                NEW — 5-version ring buffer
│  ├─ Cache_Invalidator.php           NEW — Elementor cache clear
│  ├─ Page_Lock.php                   NEW — WP transient per-page write lock
│  ├─ Rest_Sections.php               NEW — /pages/{id}/sections CRUD
│  └─ Rest_Backups.php                NEW — /pages/{id}/backups
├─ tests/Unit/
│  ├─ Profile_CPTTest.php             NEW
│  ├─ Profile_SchemaTest.php          NEW
│  ├─ Profile_RepositoryTest.php      NEW
│  ├─ Kit_WriterTest.php              NEW
│  ├─ Rest_ProfilesTest.php           NEW
│  ├─ Rest_PagesTest.php              NEW
│  ├─ Section_ParserTest.php          NEW
│  ├─ Backup_StoreTest.php            NEW
│  ├─ Page_LockTest.php               NEW
│  ├─ Rest_SectionsTest.php           NEW
│  └─ Rest_BackupsTest.php            NEW
└─ tests/fixtures/
   ├─ profile-saas-blue.json          NEW
   └─ elementor-data-sample.json      NEW — one section with 1 column + heading

mcp-server/
├─ elementor_mcp/
│  ├─ envelope.py                     MODIFY — add ToolError helpers for new codes
│  ├─ errors.py                       MODIFY (none — codes already present)
│  ├─ tools/
│  │  ├─ profile.py                   NEW — 7 profile tools
│  │  ├─ page.py                      NEW — 4 page tools
│  │  ├─ section.py                   NEW — 9 section tools (incl. backup)
│  │  └─ kit.py                       NEW — 2 raw kit tools
│  └─ server.py                       MODIFY — register all new tools
└─ tests/
   ├─ unit/
   │  ├─ test_tools_profile.py        NEW
   │  ├─ test_tools_page.py           NEW
   │  ├─ test_tools_section.py        NEW
   │  └─ test_tools_kit.py            NEW
   └─ integration/
      └─ test_p1a_end_to_end.py       NEW — full round-trip: profile→page→sections
```

---

## Conventions

**TDD cycle per task:** failing test → run (see fail) → minimal impl → run (see pass) → commit.

**Test commands:**
- `cd wp-plugin && vendor/bin/phpunit --filter <ClassName>` — single PHPUnit class
- `cd wp-plugin && vendor/bin/phpunit` — all PHPUnit
- `cd mcp-server && uv run pytest tests/unit/test_<file>.py -v` — single Python test
- `cd mcp-server && uv run pytest tests/unit -v` — all Python unit
- `cd mcp-server && uv run pytest tests/integration -v` — round-trip (needs wp-env up)

**PHP test boilerplate (copy verbatim at top of every new PHPUnit file):**

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
```

Plus a setUp/tearDown that calls Brain Monkey:

```php
protected function setUp(): void { \Brain\Monkey\setUp(); }
protected function tearDown(): void { \Brain\Monkey\tearDown(); }
```

**PSR-4 filename rule:** PHP class `Foo_Bar` → file `Foo_Bar.php` in `wp-plugin/includes/`. PHPUnit test class `Foo_BarTest` → file `Foo_BarTest.php` in `wp-plugin/tests/Unit/`. (P0 already enforces this via `composer.json` autoload.)

**Commit style:** Conventional commits with scope `plugin|mcp|infra|test|docs`. One commit per task at the end.

**Branch:** Continue on `master` per P0 user decision. No feature branches.

**Co-Authored-By footer in every commit:** `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`.

---

## Task 1: Register `emcp_profile` custom post type

**Files:**
- Create: `wp-plugin/includes/Profile_CPT.php`
- Modify: `wp-plugin/includes/Plugin.php` — call CPT register on `init`
- Test: `wp-plugin/tests/Unit/Profile_CPTTest.php`

- [ ] **Step 1: Write failing test**

`wp-plugin/tests/Unit/Profile_CPTTest.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Profile_CPT;

class Profile_CPTTest extends TestCase {
    protected function setUp(): void { \Brain\Monkey\setUp(); }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_register_calls_register_post_type_with_correct_slug() {
        Functions\expect('register_post_type')
            ->once()
            ->with('emcp_profile', \Mockery::on(function ($args) {
                return $args['public'] === false
                    && $args['show_ui'] === false
                    && in_array('title', $args['supports'], true);
            }));
        (new Profile_CPT())->register();
    }

    public function test_post_type_slug_constant() {
        $this->assertSame('emcp_profile', Profile_CPT::POST_TYPE);
    }
}
```

- [ ] **Step 2: Run test, confirm fail**

```bash
cd wp-plugin && vendor/bin/phpunit --filter Profile_CPTTest
```

Expected: `Error: Class "ElementorMCP\Profile_CPT" not found`.

- [ ] **Step 3: Implement `wp-plugin/includes/Profile_CPT.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Profile_CPT {
    const POST_TYPE = 'emcp_profile';

    public function register(): void {
        register_post_type(self::POST_TYPE, [
            'public'              => false,
            'show_ui'             => false,
            'show_in_rest'        => false,
            'exclude_from_search' => true,
            'supports'            => ['title', 'custom-fields'],
            'capability_type'     => 'post',
            'map_meta_cap'        => true,
            'labels'              => [
                'name'          => 'Elementor MCP Profiles',
                'singular_name' => 'Profile',
            ],
        ]);
    }
}
```

- [ ] **Step 4: Wire into Plugin**

Modify `wp-plugin/includes/Plugin.php`. Replace the `init()` body to also register the CPT on `init`:

```php
public function init(): void {
    add_action('init', function () { (new Profile_CPT())->register(); });
    add_action('admin_menu', [$this, 'register_admin_menu']);
    add_action('rest_api_init', [$this, 'register_rest_routes']);
    add_filter('rest_authentication_errors', [$this, 'filter_rest_auth'], 99);
}
```

- [ ] **Step 5: Run test, confirm pass**

```bash
cd wp-plugin && vendor/bin/phpunit --filter Profile_CPTTest
```

Expected: 2 tests green.

- [ ] **Step 6: Commit**

```bash
cd .. && git add wp-plugin/includes/Profile_CPT.php wp-plugin/includes/Plugin.php wp-plugin/tests/Unit/Profile_CPTTest.php
git commit -m "feat(plugin): register emcp_profile custom post type

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Profile JSON schema validator

**Files:**
- Create: `wp-plugin/includes/Profile_Schema.php`
- Create: `wp-plugin/tests/fixtures/profile-saas-blue.json`
- Test: `wp-plugin/tests/Unit/Profile_SchemaTest.php`

- [ ] **Step 1: Create fixture `wp-plugin/tests/fixtures/profile-saas-blue.json`**

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

- [ ] **Step 2: Write failing test**

`wp-plugin/tests/Unit/Profile_SchemaTest.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use PHPUnit\Framework\TestCase;
use ElementorMCP\Profile_Schema;

class Profile_SchemaTest extends TestCase {
    public function test_valid_profile_accepted() {
        $json = file_get_contents(__DIR__ . '/../fixtures/profile-saas-blue.json');
        $data = json_decode($json, true);
        $result = (new Profile_Schema())->validate($data);
        $this->assertTrue($result['ok']);
        $this->assertSame([], $result['errors']);
    }

    public function test_missing_name_rejected() {
        $data = ['colors' => []];
        $result = (new Profile_Schema())->validate($data);
        $this->assertFalse($result['ok']);
        $this->assertContains("missing required field 'name'", $result['errors']);
    }

    public function test_invalid_hex_color_rejected() {
        $data = $this->valid();
        $data['colors']['primary'] = 'not-a-color';
        $result = (new Profile_Schema())->validate($data);
        $this->assertFalse($result['ok']);
        $this->assertContains("invalid hex color for colors.primary: 'not-a-color'", $result['errors']);
    }

    public function test_negative_typography_size_rejected() {
        $data = $this->valid();
        $data['typography']['h1']['size'] = -5;
        $result = (new Profile_Schema())->validate($data);
        $this->assertFalse($result['ok']);
        $this->assertContains("typography.h1.size must be > 0", $result['errors']);
    }

    public function test_unknown_top_level_keys_warn_but_not_fail() {
        $data = $this->valid();
        $data['mystery_field'] = 'hello';
        $result = (new Profile_Schema())->validate($data);
        $this->assertTrue($result['ok']);
        $this->assertContains("unknown field at top level: 'mystery_field'", $result['warnings']);
    }

    private function valid(): array {
        return json_decode(file_get_contents(__DIR__ . '/../fixtures/profile-saas-blue.json'), true);
    }
}
```

- [ ] **Step 3: Run test, confirm fail**

```bash
vendor/bin/phpunit --filter Profile_SchemaTest
```

Expected: class not found.

- [ ] **Step 4: Implement `wp-plugin/includes/Profile_Schema.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Profile_Schema {
    const TOP_LEVEL = ['name','colors','fonts','typography','layout','breakpoints','buttons'];
    const REQUIRED_TOP = ['name','colors','fonts','typography','layout'];
    const REQUIRED_COLORS = ['primary','secondary','text','accent','background'];
    const REQUIRED_TYPO_LEVELS = ['h1','h2','h3','body','small'];

    public function validate(array $data): array {
        $errors = [];
        $warnings = [];

        foreach (self::REQUIRED_TOP as $key) {
            if (!array_key_exists($key, $data)) {
                $errors[] = "missing required field '{$key}'";
            }
        }

        foreach (array_keys($data) as $key) {
            if (!in_array($key, self::TOP_LEVEL, true)) {
                $warnings[] = "unknown field at top level: '{$key}'";
            }
        }

        if (isset($data['colors']) && is_array($data['colors'])) {
            foreach (self::REQUIRED_COLORS as $name) {
                if (!isset($data['colors'][$name])) {
                    $errors[] = "missing required color: colors.{$name}";
                    continue;
                }
                if (!$this->is_hex($data['colors'][$name])) {
                    $errors[] = "invalid hex color for colors.{$name}: '{$data['colors'][$name]}'";
                }
            }
        }

        if (isset($data['typography']) && is_array($data['typography'])) {
            foreach (self::REQUIRED_TYPO_LEVELS as $lvl) {
                if (!isset($data['typography'][$lvl])) {
                    $errors[] = "missing typography level: typography.{$lvl}";
                    continue;
                }
                $t = $data['typography'][$lvl];
                if (!is_int($t['size'] ?? null) || $t['size'] <= 0) {
                    $errors[] = "typography.{$lvl}.size must be > 0";
                }
            }
        }

        return [
            'ok'       => count($errors) === 0,
            'errors'   => $errors,
            'warnings' => $warnings,
        ];
    }

    private function is_hex($value): bool {
        return is_string($value) && (bool) preg_match('/^#[0-9A-Fa-f]{6}$/', $value);
    }
}
```

- [ ] **Step 5: Run test, confirm pass**

```bash
vendor/bin/phpunit --filter Profile_SchemaTest
```

Expected: 5 tests green.

- [ ] **Step 6: Commit**

```bash
cd .. && git add wp-plugin/tests/fixtures/profile-saas-blue.json wp-plugin/includes/Profile_Schema.php wp-plugin/tests/Unit/Profile_SchemaTest.php
git commit -m "feat(plugin): profile JSON schema validator

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Profile repository (load/save via postmeta)

**Files:**
- Create: `wp-plugin/includes/Profile_Repository.php`
- Test: `wp-plugin/tests/Unit/Profile_RepositoryTest.php`

- [ ] **Step 1: Write failing test**

`wp-plugin/tests/Unit/Profile_RepositoryTest.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Profile_Repository;

class Profile_RepositoryTest extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'sanitize_text_field' => fn($s) => trim((string)$s),
            'wp_slash'            => fn($s) => $s,
            'wp_unslash'          => fn($s) => $s,
        ]);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_create_inserts_post_and_meta() {
        Functions\expect('wp_insert_post')->once()
            ->with(\Mockery::on(function ($args) {
                return $args['post_type'] === 'emcp_profile'
                    && $args['post_title'] === 'SaaS-blue'
                    && $args['post_status'] === 'publish';
            }))
            ->andReturn(101);
        Functions\expect('update_post_meta')->once()
            ->with(101, '_emcp_profile_data', \Mockery::type('string'));
        $data = ['name' => 'SaaS-blue', 'colors' => []];
        $id = (new Profile_Repository())->create($data);
        $this->assertSame(101, $id);
    }

    public function test_get_returns_null_when_post_not_found() {
        Functions\expect('get_post')->once()->with(404)->andReturn(null);
        $this->assertNull((new Profile_Repository())->get(404));
    }

    public function test_get_returns_decoded_data() {
        Functions\expect('get_post')->once()->with(7)
            ->andReturn((object)['ID' => 7, 'post_type' => 'emcp_profile', 'post_title' => 'X']);
        Functions\expect('get_post_meta')->once()
            ->with(7, '_emcp_profile_data', true)
            ->andReturn('{"name":"X","colors":{}}');
        $r = (new Profile_Repository())->get(7);
        $this->assertSame(7, $r['id']);
        $this->assertSame('X', $r['data']['name']);
    }

    public function test_update_replaces_postmeta() {
        Functions\expect('get_post')->once()->with(8)
            ->andReturn((object)['ID' => 8, 'post_type' => 'emcp_profile']);
        Functions\expect('wp_update_post')->once()->with(\Mockery::on(function ($args) {
            return $args['ID'] === 8 && $args['post_title'] === 'New';
        }));
        Functions\expect('update_post_meta')->once()
            ->with(8, '_emcp_profile_data', \Mockery::type('string'));
        $ok = (new Profile_Repository())->update(8, ['name' => 'New', 'colors' => []]);
        $this->assertTrue($ok);
    }

    public function test_update_returns_false_for_wrong_post_type() {
        Functions\expect('get_post')->once()->with(9)
            ->andReturn((object)['ID' => 9, 'post_type' => 'post']);
        $this->assertFalse((new Profile_Repository())->update(9, ['name' => 'x']));
    }

    public function test_delete_only_works_on_profile_post() {
        Functions\expect('get_post')->once()->with(10)
            ->andReturn((object)['ID' => 10, 'post_type' => 'emcp_profile']);
        Functions\expect('wp_delete_post')->once()->with(10, true)->andReturn((object)[]);
        $this->assertTrue((new Profile_Repository())->delete(10));
    }

    public function test_list_returns_array_of_summaries() {
        Functions\expect('get_posts')->once()
            ->with(\Mockery::on(fn($a) => $a['post_type'] === 'emcp_profile'))
            ->andReturn([
                (object)['ID' => 1, 'post_title' => 'A', 'post_date_gmt' => '2026-05-28 00:00:00'],
                (object)['ID' => 2, 'post_title' => 'B', 'post_date_gmt' => '2026-05-28 01:00:00'],
            ]);
        $list = (new Profile_Repository())->list();
        $this->assertCount(2, $list);
        $this->assertSame('A', $list[0]['name']);
    }
}
```

- [ ] **Step 2: Run test, confirm fail**

```bash
vendor/bin/phpunit --filter Profile_RepositoryTest
```

- [ ] **Step 3: Implement `wp-plugin/includes/Profile_Repository.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Profile_Repository {
    const META_KEY = '_emcp_profile_data';

    public function create(array $data): int {
        $id = wp_insert_post([
            'post_type'   => Profile_CPT::POST_TYPE,
            'post_title'  => sanitize_text_field($data['name'] ?? ''),
            'post_status' => 'publish',
        ]);
        update_post_meta((int) $id, self::META_KEY, wp_slash(wp_json_encode($data)));
        return (int) $id;
    }

    public function get(int $id): ?array {
        $post = get_post($id);
        if (!$post || $post->post_type !== Profile_CPT::POST_TYPE) return null;
        $raw  = get_post_meta($id, self::META_KEY, true);
        $data = json_decode($raw ?: '{}', true);
        return [
            'id'    => $id,
            'name'  => $post->post_title,
            'data'  => is_array($data) ? $data : [],
        ];
    }

    public function update(int $id, array $data): bool {
        $post = get_post($id);
        if (!$post || $post->post_type !== Profile_CPT::POST_TYPE) return false;
        wp_update_post([
            'ID'         => $id,
            'post_title' => sanitize_text_field($data['name'] ?? $post->post_title),
        ]);
        update_post_meta($id, self::META_KEY, wp_slash(wp_json_encode($data)));
        return true;
    }

    public function delete(int $id): bool {
        $post = get_post($id);
        if (!$post || $post->post_type !== Profile_CPT::POST_TYPE) return false;
        $r = wp_delete_post($id, true);
        return $r !== false && $r !== null;
    }

    public function list(): array {
        $posts = get_posts([
            'post_type'      => Profile_CPT::POST_TYPE,
            'post_status'    => 'publish',
            'posts_per_page' => 200,
            'orderby'        => 'title',
            'order'          => 'ASC',
        ]);
        return array_map(fn($p) => [
            'id'         => $p->ID,
            'name'       => $p->post_title,
            'created_at' => $p->post_date_gmt ?? null,
        ], $posts);
    }
}
```

Note: `wp_json_encode` and `wp_slash` need stubs in tests. Add to the `Functions\stubs` in setUp:

```php
'wp_json_encode' => fn($v) => json_encode($v),
```

Update the test's setUp accordingly.

- [ ] **Step 4: Run test, confirm pass**

```bash
vendor/bin/phpunit --filter Profile_RepositoryTest
```

Expected: 7 tests green.

- [ ] **Step 5: Commit**

```bash
cd .. && git add wp-plugin/includes/Profile_Repository.php wp-plugin/tests/Unit/Profile_RepositoryTest.php
git commit -m "feat(plugin): profile repository (CRUD via postmeta)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Kit Writer — translate profile to Elementor Kit settings

**Files:**
- Create: `wp-plugin/includes/Kit_Writer.php`
- Test: `wp-plugin/tests/Unit/Kit_WriterTest.php`

Elementor stores Kit settings in a post of type `elementor_library` with meta `_elementor_page_settings`. The Kit ID is `Elementor\Plugin::$instance->kits_manager->get_active_id()`. To avoid coupling tests to Elementor classes, we'll inject the Kit ID and the settings reader/writer as callables.

- [ ] **Step 1: Write failing test**

`wp-plugin/tests/Unit/Kit_WriterTest.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use PHPUnit\Framework\TestCase;
use ElementorMCP\Kit_Writer;

class Kit_WriterTest extends TestCase {
    public function test_translates_profile_to_kit_settings_array() {
        $profile = json_decode(file_get_contents(__DIR__ . '/../fixtures/profile-saas-blue.json'), true);
        $writer  = new Kit_Writer();
        $settings = $writer->build_settings($profile);

        // system colors
        $primary = $this->find_color($settings['system_colors'], 'primary');
        $this->assertSame('#0066FF', $primary['color']);

        // custom colors (the 'muted' entry from profile.colors.custom)
        $muted = $this->find_color($settings['custom_colors'], 'muted');
        $this->assertSame('#9F9F9F', $muted['color']);

        // system typography
        $primaryFont = $this->find_typo($settings['system_typography'], 'primary');
        $this->assertSame('Inter', $primaryFont['typography_font_family']);

        // layout
        $this->assertSame(1290, $settings['container_width']['size']);
        $this->assertSame(80, $settings['space_between_widgets']['top']);

        // breakpoints
        $this->assertSame(767, $settings['viewport_md']);
    }

    public function test_h1_typography_maps_to_kit_h1_settings() {
        $profile = json_decode(file_get_contents(__DIR__ . '/../fixtures/profile-saas-blue.json'), true);
        $settings = (new Kit_Writer())->build_settings($profile);
        $this->assertSame(64,   $settings['body_typography_font_size']['size'] ?? null,    'body size default');
        // h1 stored under prefixed key
        $this->assertSame(64,   $settings['h1_typography_font_size']['size']);
        $this->assertSame(36,   $settings['h1_typography_font_size_mobile']['size']);
    }

    private function find_color(array $list, string $id): array {
        foreach ($list as $c) if ($c['_id'] === $id) return $c;
        $this->fail("color '$id' not found");
    }

    private function find_typo(array $list, string $id): array {
        foreach ($list as $t) if ($t['_id'] === $id) return $t;
        $this->fail("typo '$id' not found");
    }
}
```

- [ ] **Step 2: Run test, confirm fail**

```bash
vendor/bin/phpunit --filter Kit_WriterTest
```

- [ ] **Step 3: Implement `wp-plugin/includes/Kit_Writer.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

/**
 * Translate a profile (Elementor MCP shape) into the settings array
 * that the Elementor Kit post stores under postmeta _elementor_page_settings.
 */
class Kit_Writer {
    public function build_settings(array $profile): array {
        $colors = $profile['colors'] ?? [];
        $fonts  = $profile['fonts'] ?? [];
        $typo   = $profile['typography'] ?? [];
        $layout = $profile['layout'] ?? [];
        $bp     = $profile['breakpoints'] ?? ['mobile' => 767, 'desktop' => 1290];
        $btn    = $profile['buttons'] ?? [];

        $settings = [];

        // System colors (Elementor's 4 defaults; we map 4, push the rest to custom).
        $settings['system_colors'] = [
            ['_id' => 'primary',   'title' => 'Primary',   'color' => $colors['primary']   ?? '#000000'],
            ['_id' => 'secondary', 'title' => 'Secondary', 'color' => $colors['secondary'] ?? '#000000'],
            ['_id' => 'text',      'title' => 'Text',      'color' => $colors['text']      ?? '#000000'],
            ['_id' => 'accent',    'title' => 'Accent',    'color' => $colors['accent']    ?? '#000000'],
        ];

        // Profile background goes to custom (Elementor lacks a system "background" slot).
        $custom = [
            ['_id' => 'background', 'title' => 'Background', 'color' => $colors['background'] ?? '#FFFFFF'],
        ];
        foreach (($colors['custom'] ?? []) as $i => $c) {
            $custom[] = [
                '_id'   => $this->slug($c['name'] ?? "custom-$i"),
                'title' => $c['name'] ?? "Custom $i",
                'color' => $c['value'] ?? '#000000',
            ];
        }
        $settings['custom_colors'] = $custom;

        // System typography (Elementor: 4 defaults; we map primary, secondary).
        $settings['system_typography'] = [
            $this->typo_block('primary',   $fonts['primary']   ?? null, $typo['body'] ?? null),
            $this->typo_block('secondary', $fonts['secondary'] ?? null, $typo['body'] ?? null),
            $this->typo_block('text',      $fonts['primary']   ?? null, $typo['body'] ?? null),
            $this->typo_block('accent',    $fonts['secondary'] ?? null, $typo['h2']   ?? null),
        ];
        $settings['custom_typography'] = [];

        // Body defaults (Elementor reads body_* keys for global body styles).
        if (isset($typo['body'])) {
            $this->set_typo($settings, 'body', $fonts['primary'] ?? null, $typo['body']);
        }

        // Heading levels h1..h3 + small — Elementor uses prefixed keys.
        foreach (['h1','h2','h3'] as $h) {
            if (!empty($typo[$h])) $this->set_typo($settings, $h, $fonts['primary'] ?? null, $typo[$h]);
        }
        if (!empty($typo['small'])) $this->set_typo($settings, 'small', $fonts['primary'] ?? null, $typo['small']);

        // Layout
        $settings['container_width'] = [
            'unit'  => 'px',
            'size'  => $layout['container_width'] ?? 1290,
            'sizes' => [],
        ];
        $settings['space_between_widgets'] = [
            'top'        => $layout['section_padding']['top']    ?? 80,
            'right'      => 0,
            'bottom'     => $layout['section_padding']['bottom'] ?? 80,
            'left'       => 0,
            'unit'       => 'px',
            'isLinked'   => false,
        ];

        // Breakpoints
        $settings['viewport_md'] = $bp['mobile']  ?? 767;
        $settings['viewport_lg'] = $bp['desktop'] ?? 1290;

        // Button defaults
        if ($btn) {
            $settings['button_border_radius'] = [
                'unit' => 'px',
                'top'  => $btn['border_radius'] ?? 0,
                'right'=> $btn['border_radius'] ?? 0,
                'bottom'=> $btn['border_radius'] ?? 0,
                'left' => $btn['border_radius'] ?? 0,
                'isLinked' => true,
            ];
            $settings['button_text_padding'] = [
                'unit' => 'px',
                'top'        => $btn['padding_y'] ?? 16,
                'right'      => $btn['padding_x'] ?? 32,
                'bottom'     => $btn['padding_y'] ?? 16,
                'left'       => $btn['padding_x'] ?? 32,
                'isLinked'   => false,
            ];
        }

        return $settings;
    }

    private function typo_block(string $id, ?array $font, ?array $size): array {
        return [
            '_id'                     => $id,
            'title'                   => ucfirst($id),
            'typography_typography'   => 'custom',
            'typography_font_family'  => $font['family']  ?? '',
            'typography_font_size'    => ['unit'=>'px','size'=>$size['size'] ?? 17,'sizes'=>[]],
            'typography_font_weight'  => (string)($size['weight'] ?? 500),
            'typography_line_height'  => ['unit'=>'em','size'=>$size['line_height'] ?? 1.6,'sizes'=>[]],
        ];
    }

    private function set_typo(array &$settings, string $level, ?array $font, array $tp): void {
        $prefix = "{$level}_";
        $settings["{$prefix}typography_typography"]  = 'custom';
        $settings["{$prefix}typography_font_family"] = $font['family'] ?? '';
        $settings["{$prefix}typography_font_size"]   = ['unit'=>'px','size'=>$tp['size'] ?? 17,'sizes'=>[]];
        $settings["{$prefix}typography_font_size_mobile"] = ['unit'=>'px','size'=>$tp['mobile'] ?? ($tp['size'] ?? 17),'sizes'=>[]];
        $settings["{$prefix}typography_font_weight"] = (string)($tp['weight'] ?? 500);
        $settings["{$prefix}typography_line_height"] = ['unit'=>'em','size'=>$tp['line_height'] ?? 1.4,'sizes'=>[]];
    }

    private function slug(string $name): string {
        $slug = strtolower(preg_replace('/[^a-z0-9]+/i', '-', $name));
        return trim($slug, '-') ?: 'custom';
    }
}
```

- [ ] **Step 4: Run test, confirm pass**

```bash
vendor/bin/phpunit --filter Kit_WriterTest
```

Expected: 2 tests green.

- [ ] **Step 5: Commit**

```bash
cd .. && git add wp-plugin/includes/Kit_Writer.php wp-plugin/tests/Unit/Kit_WriterTest.php
git commit -m "feat(plugin): Kit_Writer translates profile to Elementor Kit settings

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Profile REST endpoints (GET/POST/PUT/DELETE/apply)

**Files:**
- Create: `wp-plugin/includes/Rest_Profiles.php`
- Modify: `wp-plugin/includes/Rest_Api.php` — register new routes
- Test: `wp-plugin/tests/Unit/Rest_ProfilesTest.php`

- [ ] **Step 1: Write failing test**

`wp-plugin/tests/Unit/Rest_ProfilesTest.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Rest_Profiles;
use ElementorMCP\Profile_Repository;
use ElementorMCP\Profile_Schema;
use ElementorMCP\Kit_Writer;

class Rest_ProfilesTest extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'rest_ensure_response' => fn($d) => $d,
            'current_user_can'     => fn($c) => true,
        ]);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_list_returns_envelope_with_profiles() {
        $repo = $this->createMock(Profile_Repository::class);
        $repo->method('list')->willReturn([['id'=>1,'name'=>'A','created_at'=>null]]);
        $r = (new Rest_Profiles($repo, new Profile_Schema(), new Kit_Writer()))->list();
        $this->assertTrue($r['ok']);
        $this->assertCount(1, $r['data']);
    }

    public function test_get_returns_404_envelope_when_missing() {
        $repo = $this->createMock(Profile_Repository::class);
        $repo->method('get')->with(99)->willReturn(null);
        $req = $this->req(['id' => 99]);
        $r = (new Rest_Profiles($repo, new Profile_Schema(), new Kit_Writer()))->get($req);
        $this->assertFalse($r['ok']);
        $this->assertSame('emcp_not_found', $r['error']['code']);
    }

    public function test_create_validates_and_persists() {
        $repo = $this->createMock(Profile_Repository::class);
        $repo->expects($this->once())->method('create')->willReturn(42);
        $valid = json_decode(file_get_contents(__DIR__ . '/../fixtures/profile-saas-blue.json'), true);
        $req = $this->req([], $valid);
        $r = (new Rest_Profiles($repo, new Profile_Schema(), new Kit_Writer()))->create($req);
        $this->assertTrue($r['ok']);
        $this->assertSame(42, $r['data']['id']);
    }

    public function test_create_rejects_invalid_payload() {
        $repo = $this->createMock(Profile_Repository::class);
        $repo->expects($this->never())->method('create');
        $bad = ['name' => 'X', 'colors' => ['primary' => 'not-hex']];
        $req = $this->req([], $bad);
        $r = (new Rest_Profiles($repo, new Profile_Schema(), new Kit_Writer()))->create($req);
        $this->assertFalse($r['ok']);
        $this->assertSame('emcp_invalid', $r['error']['code']);
    }

    public function test_apply_writes_kit_settings() {
        $repo = $this->createMock(Profile_Repository::class);
        $valid = json_decode(file_get_contents(__DIR__ . '/../fixtures/profile-saas-blue.json'), true);
        $repo->method('get')->with(5)->willReturn(['id'=>5,'name'=>'X','data'=>$valid]);

        $writer = $this->getMockBuilder(Kit_Writer::class)->onlyMethods([])->getMock();

        // Mock the global helpers Apply uses to find + update Kit post.
        Functions\expect('get_option')->andReturn(99);  // fake Kit ID stored in option
        Functions\expect('update_post_meta')->once()
            ->with(99, '_elementor_page_settings', \Mockery::type('array'))
            ->andReturn(true);

        $req = $this->req(['id' => 5]);
        $r = (new Rest_Profiles($repo, new Profile_Schema(), $writer))->apply($req);
        $this->assertTrue($r['ok']);
        $this->assertSame(99, $r['data']['kit_post_id']);
    }

    private function req(array $params, $body = null) {
        // Lightweight WP_REST_Request stub
        return new class($params, $body) {
            public function __construct(private array $params, private $body) {}
            public function get_param($k) { return $this->params[$k] ?? null; }
            public function get_json_params() { return $this->body; }
        };
    }
}
```

- [ ] **Step 2: Run test, confirm fail**

```bash
vendor/bin/phpunit --filter Rest_ProfilesTest
```

- [ ] **Step 3: Implement `wp-plugin/includes/Rest_Profiles.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Rest_Profiles {
    const KIT_OPTION = 'elementor_active_kit';
    const KIT_META   = '_elementor_page_settings';

    public function __construct(
        private Profile_Repository $repo,
        private Profile_Schema $schema,
        private Kit_Writer $writer
    ) {}

    public function register_routes(): void {
        $ns = Rest_Api::NS;
        register_rest_route($ns, '/profiles', [
            ['methods'=>'GET',  'callback'=>[$this,'list'],   'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'POST', 'callback'=>[$this,'create'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
        ]);
        register_rest_route($ns, '/profiles/(?P<id>\d+)', [
            ['methods'=>'GET',    'callback'=>[$this,'get'],    'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'PUT',    'callback'=>[$this,'update'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'DELETE', 'callback'=>[$this,'delete'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
        ]);
        register_rest_route($ns, '/profiles/(?P<id>\d+)/apply', [
            'methods'=>'POST', 'callback'=>[$this,'apply'],
            'permission_callback'=>fn()=>current_user_can('edit_posts'),
        ]);
    }

    public function list() {
        return Rest_Api::ok($this->repo->list());
    }

    public function get($req) {
        $id = (int) $req->get_param('id');
        $r  = $this->repo->get($id);
        return $r ? Rest_Api::ok($r) : Rest_Api::fail('emcp_not_found', "Profile {$id} not found", 404);
    }

    public function create($req) {
        $body = $req->get_json_params();
        $v    = $this->schema->validate(is_array($body) ? $body : []);
        if (!$v['ok']) return Rest_Api::fail('emcp_invalid', 'Profile validation failed', 400, $v['errors']);
        $id = $this->repo->create($body);
        return Rest_Api::ok(['id' => $id], $v['warnings']);
    }

    public function update($req) {
        $id   = (int) $req->get_param('id');
        $body = $req->get_json_params();
        $v    = $this->schema->validate(is_array($body) ? $body : []);
        if (!$v['ok']) return Rest_Api::fail('emcp_invalid', 'Profile validation failed', 400, $v['errors']);
        if (!$this->repo->update($id, $body)) {
            return Rest_Api::fail('emcp_not_found', "Profile {$id} not found", 404);
        }
        return Rest_Api::ok(['id' => $id], $v['warnings']);
    }

    public function delete($req) {
        $id = (int) $req->get_param('id');
        return $this->repo->delete($id)
            ? Rest_Api::ok(['id' => $id, 'deleted' => true])
            : Rest_Api::fail('emcp_not_found', "Profile {$id} not found", 404);
    }

    public function apply($req) {
        $id  = (int) $req->get_param('id');
        $row = $this->repo->get($id);
        if (!$row) return Rest_Api::fail('emcp_not_found', "Profile {$id} not found", 404);

        $kit_id = (int) get_option(self::KIT_OPTION, 0);
        if ($kit_id <= 0) return Rest_Api::fail('emcp_internal', 'Elementor active kit not configured', 500);

        $settings = $this->writer->build_settings($row['data']);
        update_post_meta($kit_id, self::KIT_META, $settings);

        return Rest_Api::ok(['kit_post_id' => $kit_id, 'profile_id' => $id]);
    }
}
```

- [ ] **Step 4: Modify `Rest_Api` — add `NS` constant, `ok()`/`fail()` static helpers, wire profile routes**

Open `wp-plugin/includes/Rest_Api.php`. Replace its body with:

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Rest_Api {
    const NS = 'elementor-mcp/v1';

    public function register_routes(): void {
        register_rest_route(self::NS, '/health', [
            'methods'             => 'GET',
            'callback'            => [$this, 'health'],
            'permission_callback' => '__return_true',
        ]);
        register_rest_route(self::NS, '/auth/verify', [
            'methods'             => 'GET',
            'callback'            => [$this, 'auth_verify'],
            'permission_callback' => fn() => get_current_user_id() > 0,
        ]);

        (new Rest_Profiles(
            new Profile_Repository(),
            new Profile_Schema(),
            new Kit_Writer(),
        ))->register_routes();
    }

    public function health() {
        return self::ok([
            'status'         => 'ok',
            'plugin_version' => Plugin::VERSION,
            'elementor'      => defined('ELEMENTOR_VERSION') ? ELEMENTOR_VERSION : null,
        ]);
    }

    public function auth_verify() {
        $user = wp_get_current_user();
        $caps = array_keys(array_filter((array)($user->allcaps ?? [])));
        return self::ok([
            'user_id' => (int) get_current_user_id(),
            'caps'    => $caps,
            'scopes'  => ['read', 'write'],
        ]);
    }

    public static function ok($data, array $warnings = []) {
        return rest_ensure_response([
            'ok' => true, 'data' => $data, 'warnings' => $warnings, 'error' => null,
        ]);
    }

    public static function fail(string $code, string $message, int $status = 400, array $details = []) {
        $resp = rest_ensure_response([
            'ok' => false, 'data' => null, 'warnings' => [],
            'error' => ['code' => $code, 'message' => $message, 'details' => $details],
        ]);
        if (method_exists($resp, 'set_status')) $resp->set_status($status);
        return $resp;
    }
}
```

The existing `Rest_ApiTest` continues to pass — `health()` and `auth_verify()` now route through the static `ok()` helper that returns the same envelope shape.

- [ ] **Step 5: Run all tests, confirm pass**

```bash
vendor/bin/phpunit
```

Expected: P0 tests (17) plus the new 5 Profile tests = 22 green.

- [ ] **Step 6: Commit**

```bash
cd .. && git add wp-plugin/includes/Rest_Profiles.php wp-plugin/includes/Rest_Api.php wp-plugin/tests/Unit/Rest_ProfilesTest.php
git commit -m "feat(plugin): /profiles CRUD + /profiles/{id}/apply

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: MCP `profile.*` tools

**Files:**
- Create: `mcp-server/elementor_mcp/tools/profile.py`
- Modify: `mcp-server/elementor_mcp/server.py` — register profile tools
- Test: `mcp-server/tests/unit/test_tools_profile.py`

- [ ] **Step 1: Write failing test**

`mcp-server/tests/unit/test_tools_profile.py`:

```python
from unittest.mock import MagicMock

from elementor_mcp.envelope import fail, ok
from elementor_mcp.errors import ErrorCode
from elementor_mcp.tools.profile import (
    profile_apply,
    profile_create,
    profile_delete,
    profile_get,
    profile_list,
    profile_update,
)


def test_profile_list_delegates():
    client = MagicMock()
    client.get.return_value = ok([{"id": 1, "name": "A"}])
    res = profile_list(client)
    client.get.assert_called_once_with("/profiles")
    assert res.ok is True


def test_profile_get_uses_path_param():
    client = MagicMock()
    client.get.return_value = ok({"id": 7, "name": "X", "data": {}})
    res = profile_get(client, profile_id=7)
    client.get.assert_called_once_with("/profiles/7")
    assert res.data["id"] == 7


def test_profile_create_posts_payload():
    client = MagicMock()
    client.post.return_value = ok({"id": 42})
    payload = {"name": "X", "colors": {}}
    res = profile_create(client, profile=payload)
    client.post.assert_called_once_with("/profiles", json=payload)
    assert res.data["id"] == 42


def test_profile_update_puts_payload():
    client = MagicMock()
    client.put.return_value = ok({"id": 5})
    res = profile_update(client, profile_id=5, profile={"name": "Y", "colors": {}})
    client.put.assert_called_once_with("/profiles/5", json={"name": "Y", "colors": {}})
    assert res.ok is True


def test_profile_delete_calls_delete():
    client = MagicMock()
    client.delete.return_value = ok({"id": 6, "deleted": True})
    res = profile_delete(client, profile_id=6)
    client.delete.assert_called_once_with("/profiles/6")


def test_profile_apply_posts_empty_body():
    client = MagicMock()
    client.post.return_value = ok({"kit_post_id": 99, "profile_id": 5})
    res = profile_apply(client, profile_id=5)
    client.post.assert_called_once_with("/profiles/5/apply", json={})
    assert res.data["kit_post_id"] == 99


def test_profile_get_propagates_404():
    client = MagicMock()
    client.get.return_value = fail(ErrorCode.E_INTERNAL, "Profile 99 not found")
    res = profile_get(client, profile_id=99)
    assert res.ok is False
```

- [ ] **Step 2: Run test, confirm fail**

```bash
cd mcp-server && uv run pytest tests/unit/test_tools_profile.py -v
```

- [ ] **Step 3: Implement `mcp-server/elementor_mcp/tools/profile.py`**

```python
from ..core.wp_client import WpClient
from ..envelope import ToolResult


def profile_list(client: WpClient) -> ToolResult:
    return client.get("/profiles")


def profile_get(client: WpClient, *, profile_id: int) -> ToolResult:
    return client.get(f"/profiles/{profile_id}")


def profile_create(client: WpClient, *, profile: dict) -> ToolResult:
    return client.post("/profiles", json=profile)


def profile_update(client: WpClient, *, profile_id: int, profile: dict) -> ToolResult:
    return client.put(f"/profiles/{profile_id}", json=profile)


def profile_delete(client: WpClient, *, profile_id: int) -> ToolResult:
    return client.delete(f"/profiles/{profile_id}")


def profile_apply(client: WpClient, *, profile_id: int) -> ToolResult:
    return client.post(f"/profiles/{profile_id}/apply", json={})
```

- [ ] **Step 4: Register tools in `mcp-server/elementor_mcp/server.py`**

Find the existing `@server.list_tools()` and `@server.call_tool()` decorators in `server.py`. Replace the body of `_list()` and `_call()` as follows:

```python
    @server.list_tools()
    async def _list() -> list[Tool]:
        return [
            Tool(
                name="auth_verify",
                description="Verify the configured WP_API_KEY works. Returns the WP user it maps to.",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            Tool(
                name="profile_list",
                description="List all Kit profiles available on the configured site.",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
            ),
            Tool(
                name="profile_get",
                description="Get one profile by ID.",
                inputSchema={
                    "type": "object",
                    "properties": {"profile_id": {"type": "integer"}},
                    "required": ["profile_id"], "additionalProperties": False,
                },
            ),
            Tool(
                name="profile_create",
                description="Create a new profile. Body must conform to profile schema.",
                inputSchema={
                    "type": "object",
                    "properties": {"profile": {"type": "object"}},
                    "required": ["profile"], "additionalProperties": False,
                },
            ),
            Tool(
                name="profile_update",
                description="Replace a profile (full body).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "profile_id": {"type": "integer"},
                        "profile":    {"type": "object"},
                    },
                    "required": ["profile_id", "profile"], "additionalProperties": False,
                },
            ),
            Tool(
                name="profile_delete",
                description="Delete a profile by ID.",
                inputSchema={
                    "type": "object",
                    "properties": {"profile_id": {"type": "integer"}},
                    "required": ["profile_id"], "additionalProperties": False,
                },
            ),
            Tool(
                name="profile_apply",
                description="Write the profile's colors/fonts/typography into the active Elementor Kit.",
                inputSchema={
                    "type": "object",
                    "properties": {"profile_id": {"type": "integer"}},
                    "required": ["profile_id"], "additionalProperties": False,
                },
            ),
        ]

    @server.call_tool()
    async def _call(name: str, arguments: dict) -> list[TextContent]:
        from .tools.profile import (
            profile_list, profile_get, profile_create,
            profile_update, profile_delete, profile_apply,
        )
        if name == "auth_verify":     result = auth_verify(client)
        elif name == "profile_list":  result = profile_list(client)
        elif name == "profile_get":   result = profile_get(client, **arguments)
        elif name == "profile_create":result = profile_create(client, **arguments)
        elif name == "profile_update":result = profile_update(client, **arguments)
        elif name == "profile_delete":result = profile_delete(client, **arguments)
        elif name == "profile_apply": result = profile_apply(client, **arguments)
        else:
            return [TextContent(type="text", text=json.dumps({
                "ok": False,
                "error": {"code": "E_INTERNAL", "message": f"unknown tool: {name}"},
            }))]
        return [TextContent(type="text", text=result.model_dump_json())]
```

- [ ] **Step 5: Run unit tests, confirm pass**

```bash
uv run pytest tests/unit -v
```

Expected: P0's 12 tests + 7 new profile tests = 19 green.

- [ ] **Step 6: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/tools/profile.py mcp-server/elementor_mcp/server.py mcp-server/tests/unit/test_tools_profile.py
git commit -m "feat(mcp): profile.* tools (list/get/create/update/delete/apply)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Pages REST (GET list, POST create, GET one, DELETE) + Page_Lookup helper

**Files:**
- Create: `wp-plugin/includes/Rest_Pages.php`
- Modify: `wp-plugin/includes/Rest_Api.php` — wire pages
- Test: `wp-plugin/tests/Unit/Rest_PagesTest.php`

Pages are WP posts of type `page` or `post` with Elementor data (`_elementor_edit_mode` = `builder`). We only list those.

- [ ] **Step 1: Write failing test**

`wp-plugin/tests/Unit/Rest_PagesTest.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Rest_Pages;

class Rest_PagesTest extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'rest_ensure_response' => fn($d) => $d,
            'current_user_can'     => fn($c) => true,
            'sanitize_text_field'  => fn($s) => trim((string)$s),
        ]);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_list_returns_only_elementor_pages() {
        Functions\expect('get_posts')->once()
            ->with(\Mockery::on(fn($a) =>
                $a['meta_key'] === '_elementor_edit_mode'
                && $a['meta_value'] === 'builder'
            ))
            ->andReturn([
                (object)['ID' => 10, 'post_title' => 'Home', 'post_status' => 'publish'],
            ]);
        Functions\expect('get_permalink')->andReturn('http://x/home');
        Functions\expect('get_post_meta')->andReturn([]); // sections count = 0
        $r = (new Rest_Pages())->list($this->req([]));
        $this->assertTrue($r['ok']);
        $this->assertSame('Home', $r['data'][0]['title']);
    }

    public function test_create_inserts_page_with_elementor_meta() {
        Functions\expect('wp_insert_post')->once()->with(\Mockery::on(function ($args) {
            return $args['post_type'] === 'page' && $args['post_title'] === 'Landing';
        }))->andReturn(33);
        Functions\expect('update_post_meta')->once()->with(33, '_elementor_edit_mode', 'builder');
        Functions\expect('update_post_meta')->once()->with(33, '_elementor_template_type', 'wp-page');
        Functions\expect('update_post_meta')->once()->with(33, '_elementor_data', '[]');
        Functions\expect('get_permalink')->andReturn('http://x/landing');
        $req = $this->req([], ['title' => 'Landing']);
        $r = (new Rest_Pages())->create($req);
        $this->assertTrue($r['ok']);
        $this->assertSame(33, $r['data']['id']);
    }

    public function test_get_returns_page_meta_and_sections_count() {
        Functions\expect('get_post')->with(7)
            ->andReturn((object)['ID' => 7, 'post_type' => 'page', 'post_title' => 'T', 'post_status' => 'publish']);
        Functions\expect('get_post_meta')->with(7, '_elementor_edit_mode', true)->andReturn('builder');
        Functions\expect('get_post_meta')->with(7, '_elementor_data', true)
            ->andReturn(json_encode([['id'=>'a'], ['id'=>'b']]));
        Functions\expect('get_permalink')->andReturn('http://x/t');
        $r = (new Rest_Pages())->get($this->req(['id' => 7]));
        $this->assertTrue($r['ok']);
        $this->assertSame(2, $r['data']['sections_count']);
    }

    public function test_get_returns_404_for_non_elementor_post() {
        Functions\expect('get_post')->with(8)
            ->andReturn((object)['ID' => 8, 'post_type' => 'page']);
        Functions\expect('get_post_meta')->with(8, '_elementor_edit_mode', true)->andReturn('');
        $r = (new Rest_Pages())->get($this->req(['id' => 8]));
        $this->assertFalse($r['ok']);
        $this->assertSame('emcp_not_found', $r['error']['code']);
    }

    public function test_delete_removes_page() {
        Functions\expect('get_post')->with(9)
            ->andReturn((object)['ID' => 9, 'post_type' => 'page']);
        Functions\expect('get_post_meta')->with(9, '_elementor_edit_mode', true)->andReturn('builder');
        Functions\expect('wp_delete_post')->once()->with(9, true)->andReturn((object)[]);
        $r = (new Rest_Pages())->delete($this->req(['id' => 9]));
        $this->assertTrue($r['ok']);
    }

    private function req(array $params, $body = null) {
        return new class($params, $body) {
            public function __construct(private array $params, private $body) {}
            public function get_param($k) { return $this->params[$k] ?? null; }
            public function get_json_params() { return $this->body; }
        };
    }
}
```

- [ ] **Step 2: Run test, confirm fail**

```bash
vendor/bin/phpunit --filter Rest_PagesTest
```

- [ ] **Step 3: Implement `wp-plugin/includes/Rest_Pages.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Rest_Pages {
    public function register_routes(): void {
        $ns = Rest_Api::NS;
        register_rest_route($ns, '/pages', [
            ['methods'=>'GET',  'callback'=>[$this,'list'],   'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'POST', 'callback'=>[$this,'create'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
        ]);
        register_rest_route($ns, '/pages/(?P<id>\d+)', [
            ['methods'=>'GET',    'callback'=>[$this,'get'],    'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'DELETE', 'callback'=>[$this,'delete'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
        ]);
    }

    public function list($req) {
        $posts = get_posts([
            'post_type'      => ['page', 'post'],
            'posts_per_page' => 100,
            'meta_key'       => '_elementor_edit_mode',
            'meta_value'     => 'builder',
        ]);
        $out = [];
        foreach ($posts as $p) {
            $data = get_post_meta($p->ID, '_elementor_data', true);
            $sections = json_decode($data ?: '[]', true);
            $out[] = [
                'id'              => (int) $p->ID,
                'title'           => $p->post_title,
                'status'          => $p->post_status,
                'edit_url'        => admin_url("post.php?post={$p->ID}&action=elementor"),
                'preview_url'     => get_permalink($p->ID),
                'sections_count'  => is_array($sections) ? count($sections) : 0,
            ];
        }
        return Rest_Api::ok($out);
    }

    public function create($req) {
        $body  = $req->get_json_params() ?? [];
        $title = sanitize_text_field($body['title'] ?? 'Untitled');
        $id = wp_insert_post([
            'post_type'   => 'page',
            'post_title'  => $title,
            'post_status' => 'publish',
        ]);
        update_post_meta($id, '_elementor_edit_mode', 'builder');
        update_post_meta($id, '_elementor_template_type', 'wp-page');
        update_post_meta($id, '_elementor_data', '[]');
        return Rest_Api::ok([
            'id'          => (int) $id,
            'title'       => $title,
            'edit_url'    => admin_url("post.php?post={$id}&action=elementor"),
            'preview_url' => get_permalink($id),
        ]);
    }

    public function get($req) {
        $id   = (int) $req->get_param('id');
        $post = get_post($id);
        $edit = get_post_meta($id, '_elementor_edit_mode', true);
        if (!$post || $edit !== 'builder') {
            return Rest_Api::fail('emcp_not_found', "Page {$id} not found or not an Elementor page", 404);
        }
        $sections = json_decode(get_post_meta($id, '_elementor_data', true) ?: '[]', true);
        return Rest_Api::ok([
            'id'              => $id,
            'title'           => $post->post_title,
            'status'          => $post->post_status,
            'edit_url'        => admin_url("post.php?post={$id}&action=elementor"),
            'preview_url'     => get_permalink($id),
            'sections_count'  => is_array($sections) ? count($sections) : 0,
        ]);
    }

    public function delete($req) {
        $id = (int) $req->get_param('id');
        $post = get_post($id);
        $edit = get_post_meta($id, '_elementor_edit_mode', true);
        if (!$post || $edit !== 'builder') {
            return Rest_Api::fail('emcp_not_found', "Page {$id} not found", 404);
        }
        wp_delete_post($id, true);
        return Rest_Api::ok(['id' => $id, 'deleted' => true]);
    }
}
```

- [ ] **Step 4: Wire in `Rest_Api::register_routes()`**

After the line `(new Rest_Profiles(...)`, add:

```php
        (new Rest_Pages())->register_routes();
```

- [ ] **Step 5: Run all tests, confirm pass**

```bash
vendor/bin/phpunit
```

Expected: 27 green (22 + 5 new).

- [ ] **Step 6: Commit**

```bash
cd .. && git add wp-plugin/includes/Rest_Pages.php wp-plugin/includes/Rest_Api.php wp-plugin/tests/Unit/Rest_PagesTest.php
git commit -m "feat(plugin): /pages CRUD endpoints

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 8: MCP `page.*` tools

**Files:**
- Create: `mcp-server/elementor_mcp/tools/page.py`
- Modify: `mcp-server/elementor_mcp/server.py` — register page tools
- Test: `mcp-server/tests/unit/test_tools_page.py`

- [ ] **Step 1: Write failing test**

`mcp-server/tests/unit/test_tools_page.py`:

```python
from unittest.mock import MagicMock

from elementor_mcp.envelope import ok
from elementor_mcp.tools.page import page_create, page_delete, page_get, page_list


def test_page_list_passes_no_params_by_default():
    client = MagicMock()
    client.get.return_value = ok([])
    page_list(client)
    client.get.assert_called_once_with("/pages", params=None)


def test_page_list_passes_search_and_per_page():
    client = MagicMock()
    client.get.return_value = ok([])
    page_list(client, search="about", per_page=10)
    client.get.assert_called_once_with("/pages", params={"search": "about", "per_page": 10})


def test_page_create_sends_title_and_profile_id():
    client = MagicMock()
    client.post.return_value = ok({"id": 4})
    page_create(client, title="Landing", profile_id=2)
    client.post.assert_called_once_with("/pages", json={"title": "Landing", "profile_id": 2})


def test_page_create_omits_profile_when_none():
    client = MagicMock()
    client.post.return_value = ok({"id": 5})
    page_create(client, title="X")
    client.post.assert_called_once_with("/pages", json={"title": "X"})


def test_page_get_and_delete():
    client = MagicMock()
    client.get.return_value = ok({"id": 7})
    client.delete.return_value = ok({"deleted": True})
    page_get(client, page_id=7)
    page_delete(client, page_id=7)
    client.get.assert_called_with("/pages/7")
    client.delete.assert_called_with("/pages/7")
```

- [ ] **Step 2: Run test, confirm fail**

```bash
uv run pytest tests/unit/test_tools_page.py -v
```

- [ ] **Step 3: Implement `mcp-server/elementor_mcp/tools/page.py`**

```python
from ..core.wp_client import WpClient
from ..envelope import ToolResult


def page_list(client: WpClient, *, search: str | None = None, per_page: int | None = None) -> ToolResult:
    params = {}
    if search is not None:   params["search"] = search
    if per_page is not None: params["per_page"] = per_page
    return client.get("/pages", params=params or None)


def page_create(client: WpClient, *, title: str, profile_id: int | None = None) -> ToolResult:
    body = {"title": title}
    if profile_id is not None:
        body["profile_id"] = profile_id
    return client.post("/pages", json=body)


def page_get(client: WpClient, *, page_id: int) -> ToolResult:
    return client.get(f"/pages/{page_id}")


def page_delete(client: WpClient, *, page_id: int) -> ToolResult:
    return client.delete(f"/pages/{page_id}")
```

- [ ] **Step 4: Register page tools in `server.py`**

Inside the `_list()` function, append:

```python
            Tool(name="page_list",
                 description="List Elementor-enabled pages.",
                 inputSchema={"type":"object","properties":{
                     "search":{"type":"string"},
                     "per_page":{"type":"integer"},
                 },"additionalProperties":False}),
            Tool(name="page_create",
                 description="Create a new Elementor-enabled page.",
                 inputSchema={"type":"object","properties":{
                     "title":{"type":"string"},
                     "profile_id":{"type":"integer"},
                 },"required":["title"],"additionalProperties":False}),
            Tool(name="page_get",
                 description="Get one page by ID.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},
                 },"required":["page_id"],"additionalProperties":False}),
            Tool(name="page_delete",
                 description="Delete a page by ID.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},
                 },"required":["page_id"],"additionalProperties":False}),
```

Inside the `_call()` function, in the if/elif chain (before the else), add:

```python
        elif name == "page_list":   result = page_list(client, **arguments)
        elif name == "page_create": result = page_create(client, **arguments)
        elif name == "page_get":    result = page_get(client, **arguments)
        elif name == "page_delete": result = page_delete(client, **arguments)
```

And add to the imports inside `_call()`:

```python
        from .tools.page import page_list, page_create, page_get, page_delete
```

- [ ] **Step 5: Run all unit tests, confirm pass**

```bash
uv run pytest tests/unit -v
```

Expected: 24 green (19 + 5 new).

- [ ] **Step 6: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/tools/page.py mcp-server/elementor_mcp/server.py mcp-server/tests/unit/test_tools_page.py
git commit -m "feat(mcp): page.* tools (list/create/get/delete)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 9: Section parser — read flat section summaries from `_elementor_data`

**Files:**
- Create: `wp-plugin/includes/Section_Parser.php`
- Create: `wp-plugin/tests/fixtures/elementor-data-sample.json`
- Test: `wp-plugin/tests/Unit/Section_ParserTest.php`

`_elementor_data` is a JSON array of top-level sections. Each has `id` (hex string), `elType` = `section` or `container`, `settings` (incl. `_title` sometimes), and `elements` (children).

- [ ] **Step 1: Create fixture `wp-plugin/tests/fixtures/elementor-data-sample.json`**

```json
[
  {
    "id": "44b1bea6",
    "elType": "section",
    "settings": {"_title": "Hero"},
    "elements": [
      {
        "id": "21589f32",
        "elType": "column",
        "settings": {"_column_size": 100},
        "elements": [
          {"id": "5e524b85", "elType": "widget", "widgetType": "heading",
           "settings": {"title": "Welcome"}, "elements": []}
        ]
      }
    ]
  },
  {
    "id": "abc12345",
    "elType": "section",
    "settings": {},
    "elements": [
      {"id": "c1", "elType": "column", "settings": {}, "elements": [
        {"id": "w1", "elType": "widget", "widgetType": "image",   "settings": {}, "elements": []},
        {"id": "w2", "elType": "widget", "widgetType": "button",  "settings": {}, "elements": []}
      ]}
    ]
  }
]
```

- [ ] **Step 2: Write failing test**

`wp-plugin/tests/Unit/Section_ParserTest.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use PHPUnit\Framework\TestCase;
use ElementorMCP\Section_Parser;

class Section_ParserTest extends TestCase {
    private function sample(): array {
        return json_decode(file_get_contents(__DIR__ . '/../fixtures/elementor-data-sample.json'), true);
    }

    public function test_list_returns_flat_summaries() {
        $list = (new Section_Parser())->list($this->sample());
        $this->assertCount(2, $list);
        $this->assertSame('44b1bea6', $list[0]['sid']);
        $this->assertSame('Hero', $list[0]['title']);
        $this->assertSame(['heading'], $list[0]['widgets']);
    }

    public function test_list_uses_widget_summary_when_no_title() {
        $list = (new Section_Parser())->list($this->sample());
        $this->assertSame('abc12345', $list[1]['sid']);
        $this->assertSame('Untitled', $list[1]['title']);
        $this->assertSame(['image', 'button'], $list[1]['widgets']);
    }

    public function test_get_section_by_id() {
        $section = (new Section_Parser())->get($this->sample(), '44b1bea6');
        $this->assertNotNull($section);
        $this->assertSame('Hero', $section['settings']['_title']);
    }

    public function test_get_returns_null_for_unknown_id() {
        $this->assertNull((new Section_Parser())->get($this->sample(), 'nope'));
    }

    public function test_add_appends_at_default_position() {
        $data = $this->sample();
        $new = ['id' => 'new1', 'elType' => 'section', 'settings' => [], 'elements' => []];
        $result = (new Section_Parser())->add($data, $new);
        $this->assertSame('new1', $result[2]['id']);
    }

    public function test_add_inserts_at_given_position() {
        $data = $this->sample();
        $new = ['id' => 'between', 'elType' => 'section', 'settings' => [], 'elements' => []];
        $result = (new Section_Parser())->add($data, $new, 1);
        $this->assertSame('44b1bea6', $result[0]['id']);
        $this->assertSame('between',  $result[1]['id']);
        $this->assertSame('abc12345', $result[2]['id']);
    }

    public function test_replace_updates_in_place() {
        $data = $this->sample();
        $replaced = ['id' => '44b1bea6', 'elType' => 'section', 'settings' => ['_title' => 'New'], 'elements' => []];
        $result = (new Section_Parser())->replace($data, '44b1bea6', $replaced);
        $this->assertSame('New', $result[0]['settings']['_title']);
        $this->assertCount(2, $result);
    }

    public function test_delete_removes_by_id() {
        $result = (new Section_Parser())->delete($this->sample(), '44b1bea6');
        $this->assertCount(1, $result);
        $this->assertSame('abc12345', $result[0]['id']);
    }

    public function test_duplicate_inserts_after_with_new_id() {
        $result = (new Section_Parser())->duplicate($this->sample(), '44b1bea6');
        $this->assertCount(3, $result);
        $this->assertSame('44b1bea6', $result[0]['id']);
        $this->assertNotSame('44b1bea6', $result[1]['id']);
        $this->assertSame('Hero', $result[1]['settings']['_title']);
    }

    public function test_reorder_rearranges() {
        $result = (new Section_Parser())->reorder($this->sample(), ['abc12345', '44b1bea6']);
        $this->assertSame('abc12345', $result[0]['id']);
        $this->assertSame('44b1bea6', $result[1]['id']);
    }

    public function test_reorder_rejects_mismatched_set() {
        $this->expectException(\InvalidArgumentException::class);
        (new Section_Parser())->reorder($this->sample(), ['44b1bea6']);  // missing one
    }
}
```

- [ ] **Step 3: Run test, confirm fail**

```bash
vendor/bin/phpunit --filter Section_ParserTest
```

- [ ] **Step 4: Implement `wp-plugin/includes/Section_Parser.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Section_Parser {
    public function list(array $data): array {
        $out = [];
        foreach ($data as $section) {
            $widgets = $this->collect_widgets($section);
            $title   = $section['settings']['_title'] ?? '';
            $out[] = [
                'sid'      => $section['id'] ?? '',
                'title'    => $title !== '' ? $title : 'Untitled',
                'el_type'  => $section['elType'] ?? 'section',
                'widgets'  => array_values(array_unique($widgets)),
            ];
        }
        return $out;
    }

    public function get(array $data, string $sid): ?array {
        foreach ($data as $section) {
            if (($section['id'] ?? '') === $sid) return $section;
        }
        return null;
    }

    public function add(array $data, array $section, ?int $position = null): array {
        if ($position === null || $position < 0 || $position > count($data)) {
            $data[] = $section;
            return $data;
        }
        array_splice($data, $position, 0, [$section]);
        return $data;
    }

    public function replace(array $data, string $sid, array $section): array {
        foreach ($data as $i => $existing) {
            if (($existing['id'] ?? '') === $sid) {
                $data[$i] = $section;
                return $data;
            }
        }
        return $data;
    }

    public function delete(array $data, string $sid): array {
        return array_values(array_filter($data, fn($s) => ($s['id'] ?? '') !== $sid));
    }

    public function duplicate(array $data, string $sid): array {
        $index = null;
        foreach ($data as $i => $s) if (($s['id'] ?? '') === $sid) { $index = $i; break; }
        if ($index === null) return $data;
        $copy = $this->rekey_ids($data[$index]);
        array_splice($data, $index + 1, 0, [$copy]);
        return $data;
    }

    public function reorder(array $data, array $order): array {
        $ids = array_map(fn($s) => $s['id'] ?? '', $data);
        if (count(array_diff($ids, $order)) !== 0 || count(array_diff($order, $ids)) !== 0) {
            throw new \InvalidArgumentException('Reorder set must include all and only existing section ids');
        }
        $byId = [];
        foreach ($data as $s) $byId[$s['id']] = $s;
        return array_values(array_map(fn($id) => $byId[$id], $order));
    }

    private function collect_widgets(array $node): array {
        $widgets = [];
        if (($node['elType'] ?? '') === 'widget' && isset($node['widgetType'])) {
            $widgets[] = $node['widgetType'];
        }
        foreach ($node['elements'] ?? [] as $child) {
            $widgets = array_merge($widgets, $this->collect_widgets($child));
        }
        return $widgets;
    }

    /** Recursively assign fresh 8-hex IDs (Elementor format). */
    private function rekey_ids(array $node): array {
        $node['id'] = bin2hex(random_bytes(4));
        if (isset($node['elements']) && is_array($node['elements'])) {
            $node['elements'] = array_map(fn($c) => $this->rekey_ids($c), $node['elements']);
        }
        return $node;
    }
}
```

- [ ] **Step 5: Run test, confirm pass**

```bash
vendor/bin/phpunit --filter Section_ParserTest
```

Expected: 11 tests green.

- [ ] **Step 6: Commit**

```bash
cd .. && git add wp-plugin/includes/Section_Parser.php wp-plugin/tests/fixtures/elementor-data-sample.json wp-plugin/tests/Unit/Section_ParserTest.php
git commit -m "feat(plugin): section parser (list/get/add/replace/delete/duplicate/reorder)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 10: Backup ring buffer (5-version postmeta history)

**Files:**
- Create: `wp-plugin/includes/Backup_Store.php`
- Test: `wp-plugin/tests/Unit/Backup_StoreTest.php`

History is stored as a JSON array under postmeta `_elementor_data_backup_history`, newest first, max 5 entries. Each entry: `{version, timestamp, data}`.

- [ ] **Step 1: Write failing test**

`wp-plugin/tests/Unit/Backup_StoreTest.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Backup_Store;

class Backup_StoreTest extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs(['current_time' => fn($_f) => '2026-05-28 10:00:00']);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_snapshot_adds_entry_with_incremented_version() {
        $store_meta = [];
        Functions\when('get_post_meta')->alias(function ($pid, $key, $single) use (&$store_meta) {
            return $store_meta[$key] ?? '';
        });
        Functions\when('update_post_meta')->alias(function ($pid, $key, $value) use (&$store_meta) {
            $store_meta[$key] = $value; return true;
        });
        Functions\when('get_post_meta')->alias(function ($pid, $key, $single) use (&$store_meta) {
            return $store_meta[$key] ?? '';
        });

        $store = new Backup_Store();
        $store->snapshot(1, [['id'=>'a']]);
        $store->snapshot(1, [['id'=>'a'], ['id'=>'b']]);
        $hist = $store->list(1);
        $this->assertCount(2, $hist);
        $this->assertSame(2, $hist[0]['version']);
        $this->assertSame(1, $hist[1]['version']);
    }

    public function test_snapshot_caps_at_5_entries() {
        $store_meta = [];
        Functions\when('get_post_meta')->alias(function ($pid, $key, $single) use (&$store_meta) {
            return $store_meta[$key] ?? '';
        });
        Functions\when('update_post_meta')->alias(function ($pid, $key, $value) use (&$store_meta) {
            $store_meta[$key] = $value; return true;
        });

        $store = new Backup_Store();
        for ($i = 0; $i < 7; $i++) $store->snapshot(1, [['id' => "v$i"]]);
        $hist = $store->list(1);
        $this->assertCount(5, $hist);
        $this->assertSame(7, $hist[0]['version']);
        $this->assertSame(3, $hist[4]['version']);
    }

    public function test_get_returns_specific_version() {
        $store_meta = [];
        Functions\when('get_post_meta')->alias(fn($pid,$key,$single)=>$store_meta[$key] ?? '');
        Functions\when('update_post_meta')->alias(function($pid,$key,$v) use (&$store_meta){
            $store_meta[$key]=$v; return true;
        });
        $store = new Backup_Store();
        $store->snapshot(1, [['id'=>'first']]);
        $store->snapshot(1, [['id'=>'second']]);
        $entry = $store->get(1, 1);
        $this->assertSame('first', $entry['data'][0]['id']);
    }

    public function test_get_returns_null_for_missing_version() {
        Functions\when('get_post_meta')->justReturn('');
        $this->assertNull((new Backup_Store())->get(1, 99));
    }
}
```

- [ ] **Step 2: Run test, confirm fail**

```bash
vendor/bin/phpunit --filter Backup_StoreTest
```

- [ ] **Step 3: Implement `wp-plugin/includes/Backup_Store.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Backup_Store {
    const META_KEY = '_elementor_data_backup_history';
    const MAX_VERSIONS = 5;

    public function snapshot(int $page_id, array $data): int {
        $hist = $this->read($page_id);
        $next_version = (count($hist) > 0 ? $hist[0]['version'] : 0) + 1;
        array_unshift($hist, [
            'version'   => $next_version,
            'timestamp' => current_time('mysql'),
            'data'      => $data,
        ]);
        if (count($hist) > self::MAX_VERSIONS) {
            $hist = array_slice($hist, 0, self::MAX_VERSIONS);
        }
        update_post_meta($page_id, self::META_KEY, wp_json_encode($hist));
        return $next_version;
    }

    public function list(int $page_id): array {
        return array_map(fn($e) => [
            'version'   => $e['version'],
            'timestamp' => $e['timestamp'],
            'sections_count' => is_array($e['data'] ?? null) ? count($e['data']) : 0,
        ], $this->read($page_id));
    }

    public function get(int $page_id, int $version): ?array {
        foreach ($this->read($page_id) as $entry) {
            if ($entry['version'] === $version) return $entry;
        }
        return null;
    }

    private function read(int $page_id): array {
        $raw = get_post_meta($page_id, self::META_KEY, true);
        $decoded = json_decode($raw ?: '[]', true);
        return is_array($decoded) ? $decoded : [];
    }
}
```

Test setUp also needs `wp_json_encode` stubbed:

Add to setUp `Functions\stubs([... 'wp_json_encode' => fn($v) => json_encode($v),])`.

- [ ] **Step 4: Run test, confirm pass**

```bash
vendor/bin/phpunit --filter Backup_StoreTest
```

Expected: 4 tests green.

- [ ] **Step 5: Commit**

```bash
cd .. && git add wp-plugin/includes/Backup_Store.php wp-plugin/tests/Unit/Backup_StoreTest.php
git commit -m "feat(plugin): backup ring buffer for _elementor_data (5 versions)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 11: Cache invalidator + per-page write lock

**Files:**
- Create: `wp-plugin/includes/Cache_Invalidator.php`
- Create: `wp-plugin/includes/Page_Lock.php`
- Test: `wp-plugin/tests/Unit/Page_LockTest.php` (cache invalidator is too thin to unit test alone — covered by integration)

- [ ] **Step 1: Implement `wp-plugin/includes/Cache_Invalidator.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Cache_Invalidator {
    public function clear_for_page(int $page_id): void {
        delete_post_meta($page_id, '_elementor_css');
        // Guard against Elementor not being active (P0 environment).
        if (class_exists('\\Elementor\\Plugin')) {
            $files = \Elementor\Plugin::instance()->files_manager ?? null;
            if ($files && method_exists($files, 'clear_cache')) {
                $files->clear_cache();
            }
        }
    }
}
```

- [ ] **Step 2: Write failing test for `Page_Lock`**

`wp-plugin/tests/Unit/Page_LockTest.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Page_Lock;

class Page_LockTest extends TestCase {
    protected function setUp(): void { \Brain\Monkey\setUp(); }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_acquire_returns_token_when_lock_open() {
        Functions\expect('get_transient')->once()->andReturn(false);
        Functions\expect('set_transient')->once()
            ->with('emcp_page_lock_5', \Mockery::type('string'), 30)
            ->andReturn(true);
        $token = (new Page_Lock())->acquire(5);
        $this->assertIsString($token);
        $this->assertNotEmpty($token);
    }

    public function test_acquire_returns_null_when_already_locked() {
        Functions\expect('get_transient')->once()->andReturn('some-other-token');
        $this->assertNull((new Page_Lock())->acquire(5));
    }

    public function test_release_only_clears_matching_token() {
        Functions\expect('get_transient')->once()->andReturn('my-token');
        Functions\expect('delete_transient')->once()->with('emcp_page_lock_5');
        $this->assertTrue((new Page_Lock())->release(5, 'my-token'));
    }

    public function test_release_returns_false_when_token_does_not_match() {
        Functions\expect('get_transient')->once()->andReturn('other-token');
        $this->assertFalse((new Page_Lock())->release(5, 'my-token'));
    }
}
```

- [ ] **Step 3: Run test, confirm fail**

```bash
vendor/bin/phpunit --filter Page_LockTest
```

- [ ] **Step 4: Implement `wp-plugin/includes/Page_Lock.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Page_Lock {
    const TTL = 30;

    public function acquire(int $page_id): ?string {
        $key = $this->key($page_id);
        if (get_transient($key)) return null;
        $token = bin2hex(random_bytes(8));
        set_transient($key, $token, self::TTL);
        return $token;
    }

    public function release(int $page_id, string $token): bool {
        $key = $this->key($page_id);
        $current = get_transient($key);
        if ($current !== $token) return false;
        delete_transient($key);
        return true;
    }

    private function key(int $page_id): string {
        return "emcp_page_lock_{$page_id}";
    }
}
```

- [ ] **Step 5: Run test, confirm pass**

```bash
vendor/bin/phpunit --filter Page_LockTest
```

- [ ] **Step 6: Commit**

```bash
cd .. && git add wp-plugin/includes/Cache_Invalidator.php wp-plugin/includes/Page_Lock.php wp-plugin/tests/Unit/Page_LockTest.php
git commit -m "feat(plugin): cache invalidator + per-page write lock

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 12: Section REST endpoints (list, get, add, update, delete, duplicate, reorder)

**Files:**
- Create: `wp-plugin/includes/Rest_Sections.php`
- Modify: `wp-plugin/includes/Rest_Api.php` — wire sections
- Test: `wp-plugin/tests/Unit/Rest_SectionsTest.php`

This is the largest endpoint group. It composes `Section_Parser`, `Backup_Store`, `Cache_Invalidator`, and `Page_Lock` for every mutation.

- [ ] **Step 1: Write failing test**

`wp-plugin/tests/Unit/Rest_SectionsTest.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Rest_Sections;
use ElementorMCP\Section_Parser;
use ElementorMCP\Backup_Store;
use ElementorMCP\Cache_Invalidator;
use ElementorMCP\Page_Lock;

class Rest_SectionsTest extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'rest_ensure_response' => fn($d) => $d,
            'current_user_can'     => fn($c) => true,
            'sanitize_text_field'  => fn($s) => trim((string)$s),
            'wp_slash'             => fn($s) => $s,
            'wp_json_encode'       => fn($v) => json_encode($v),
        ]);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_list_returns_summaries() {
        $sample = json_decode(file_get_contents(__DIR__ . '/../fixtures/elementor-data-sample.json'), true);
        Functions\expect('get_post')->andReturn((object)['ID'=>1, 'post_type'=>'page']);
        Functions\expect('get_post_meta')->with(1, '_elementor_edit_mode', true)->andReturn('builder');
        Functions\expect('get_post_meta')->with(1, '_elementor_data', true)->andReturn(json_encode($sample));
        $svc = $this->svc();
        $r = $svc->list($this->req(['id' => 1]));
        $this->assertTrue($r['ok']);
        $this->assertCount(2, $r['data']);
    }

    public function test_add_snapshots_before_writing_and_clears_cache() {
        $sample = json_decode(file_get_contents(__DIR__ . '/../fixtures/elementor-data-sample.json'), true);

        // Lock acquire
        Functions\expect('get_transient')->andReturn(false);
        Functions\expect('set_transient')->once();
        // Page lookup
        Functions\expect('get_post')->andReturn((object)['ID'=>1, 'post_type'=>'page']);
        Functions\expect('get_post_meta')->with(1, '_elementor_edit_mode', true)->andReturn('builder');
        Functions\expect('get_post_meta')->with(1, '_elementor_data', true)->andReturn(json_encode($sample));
        // Backup snapshot
        Functions\expect('get_post_meta')->with(1, '_elementor_data_backup_history', true)->andReturn('');
        Functions\expect('update_post_meta')->once()->with(1, '_elementor_data_backup_history', \Mockery::type('string'));
        Functions\stubs(['current_time' => fn() => '2026-05-28 10:00:00']);
        // Save new data
        Functions\expect('update_post_meta')->once()->with(1, '_elementor_data', \Mockery::type('string'));
        // Cache clear
        Functions\expect('delete_post_meta')->once()->with(1, '_elementor_css');
        // Lock release
        Functions\expect('get_transient')->andReturn(\Mockery::type('string'));
        Functions\expect('delete_transient')->once();

        $body = ['json' => ['id' => 'new1', 'elType' => 'section', 'settings' => [], 'elements' => []]];
        $r = $this->svc()->add($this->req(['id' => 1], $body));
        $this->assertTrue($r['ok']);
        $this->assertSame('new1', $r['data']['sid']);
    }

    public function test_add_returns_locked_when_lock_unavailable() {
        Functions\expect('get_transient')->andReturn('someone-else');  // already locked
        $body = ['json' => ['id' => 'x', 'elType' => 'section', 'settings' => [], 'elements' => []]];
        $r = $this->svc()->add($this->req(['id' => 1], $body));
        $this->assertFalse($r['ok']);
        $this->assertSame('emcp_locked', $r['error']['code']);
    }

    public function test_delete_removes_section_and_saves() {
        $sample = json_decode(file_get_contents(__DIR__ . '/../fixtures/elementor-data-sample.json'), true);

        Functions\expect('get_transient')->andReturn(false);
        Functions\expect('set_transient')->once();
        Functions\expect('get_post')->andReturn((object)['ID'=>1, 'post_type'=>'page']);
        Functions\expect('get_post_meta')->with(1, '_elementor_edit_mode', true)->andReturn('builder');
        Functions\expect('get_post_meta')->with(1, '_elementor_data', true)->andReturn(json_encode($sample));
        Functions\expect('get_post_meta')->with(1, '_elementor_data_backup_history', true)->andReturn('');
        Functions\expect('update_post_meta')->atLeast()->once();
        Functions\expect('delete_post_meta')->once()->with(1, '_elementor_css');
        Functions\expect('get_transient')->andReturn(\Mockery::type('string'));
        Functions\expect('delete_transient')->once();
        Functions\stubs(['current_time' => fn() => '2026-05-28 10:00:00']);

        $r = $this->svc()->delete($this->req(['id' => 1, 'sid' => '44b1bea6']));
        $this->assertTrue($r['ok']);
    }

    private function svc(): Rest_Sections {
        return new Rest_Sections(
            new Section_Parser(),
            new Backup_Store(),
            new Cache_Invalidator(),
            new Page_Lock(),
        );
    }

    private function req(array $params, $body = null) {
        return new class($params, $body) {
            public function __construct(private array $params, private $body) {}
            public function get_param($k) { return $this->params[$k] ?? null; }
            public function get_json_params() { return $this->body; }
        };
    }
}
```

- [ ] **Step 2: Run test, confirm fail**

```bash
vendor/bin/phpunit --filter Rest_SectionsTest
```

- [ ] **Step 3: Implement `wp-plugin/includes/Rest_Sections.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Rest_Sections {
    public function __construct(
        private Section_Parser $parser,
        private Backup_Store $backups,
        private Cache_Invalidator $cache,
        private Page_Lock $lock,
    ) {}

    public function register_routes(): void {
        $ns = Rest_Api::NS;
        register_rest_route($ns, '/pages/(?P<id>\d+)/sections', [
            ['methods'=>'GET',  'callback'=>[$this,'list'],  'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'POST', 'callback'=>[$this,'add'],   'permission_callback'=>fn()=>current_user_can('edit_posts')],
        ]);
        register_rest_route($ns, '/pages/(?P<id>\d+)/sections/(?P<sid>[a-z0-9]+)', [
            ['methods'=>'GET',    'callback'=>[$this,'get'],    'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'PUT',    'callback'=>[$this,'update'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'DELETE', 'callback'=>[$this,'delete'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
        ]);
        register_rest_route($ns, '/pages/(?P<id>\d+)/sections/(?P<sid>[a-z0-9]+)/duplicate', [
            'methods'=>'POST', 'callback'=>[$this,'duplicate'],
            'permission_callback'=>fn()=>current_user_can('edit_posts'),
        ]);
        register_rest_route($ns, '/pages/(?P<id>\d+)/sections/reorder', [
            'methods'=>'POST', 'callback'=>[$this,'reorder'],
            'permission_callback'=>fn()=>current_user_can('edit_posts'),
        ]);
    }

    public function list($req) {
        $page = $this->load_page($req); if (is_array($page) && isset($page['_fail'])) return $page['_fail'];
        return Rest_Api::ok($this->parser->list($page['data']));
    }

    public function get($req) {
        $page = $this->load_page($req); if (is_array($page) && isset($page['_fail'])) return $page['_fail'];
        $sid = (string) $req->get_param('sid');
        $section = $this->parser->get($page['data'], $sid);
        return $section
            ? Rest_Api::ok($section)
            : Rest_Api::fail('emcp_not_found', "Section {$sid} not found", 404);
    }

    public function add($req) {
        return $this->mutate($req, function ($data, $req) {
            $body = $req->get_json_params() ?? [];
            $json = $body['json'] ?? null;
            if (!is_array($json) || !isset($json['id'])) {
                return ['fail' => Rest_Api::fail('emcp_invalid', 'Missing section JSON with id', 400)];
            }
            $position = isset($body['position']) ? (int) $body['position'] : null;
            $updated = $this->parser->add($data, $json, $position);
            return ['data' => $updated, 'response' => Rest_Api::ok(['sid' => $json['id']])];
        });
    }

    public function update($req) {
        return $this->mutate($req, function ($data, $req) {
            $sid  = (string) $req->get_param('sid');
            $body = $req->get_json_params() ?? [];
            $json = $body['json'] ?? null;
            if (!is_array($json)) return ['fail' => Rest_Api::fail('emcp_invalid', 'Missing section JSON', 400)];
            $json['id'] = $sid;
            if (!$this->parser->get($data, $sid)) {
                return ['fail' => Rest_Api::fail('emcp_not_found', "Section {$sid} not found", 404)];
            }
            $updated = $this->parser->replace($data, $sid, $json);
            return ['data' => $updated, 'response' => Rest_Api::ok(['sid' => $sid])];
        });
    }

    public function delete($req) {
        return $this->mutate($req, function ($data, $req) {
            $sid = (string) $req->get_param('sid');
            if (!$this->parser->get($data, $sid)) {
                return ['fail' => Rest_Api::fail('emcp_not_found', "Section {$sid} not found", 404)];
            }
            $updated = $this->parser->delete($data, $sid);
            return ['data' => $updated, 'response' => Rest_Api::ok(['sid' => $sid, 'deleted' => true])];
        });
    }

    public function duplicate($req) {
        return $this->mutate($req, function ($data, $req) {
            $sid = (string) $req->get_param('sid');
            if (!$this->parser->get($data, $sid)) {
                return ['fail' => Rest_Api::fail('emcp_not_found', "Section {$sid} not found", 404)];
            }
            $updated = $this->parser->duplicate($data, $sid);
            return ['data' => $updated, 'response' => Rest_Api::ok(['sid' => $sid, 'duplicated' => true])];
        });
    }

    public function reorder($req) {
        return $this->mutate($req, function ($data, $req) {
            $body = $req->get_json_params() ?? [];
            $order = $body['order'] ?? null;
            if (!is_array($order)) return ['fail' => Rest_Api::fail('emcp_invalid', 'Missing order array', 400)];
            try {
                $updated = $this->parser->reorder($data, $order);
            } catch (\InvalidArgumentException $e) {
                return ['fail' => Rest_Api::fail('emcp_invalid', $e->getMessage(), 400)];
            }
            return ['data' => $updated, 'response' => Rest_Api::ok(['reordered' => true])];
        });
    }

    /** Common mutation pipeline: lock → snapshot → callback → save → cache clear → unlock. */
    private function mutate($req, callable $apply) {
        $page_id = (int) $req->get_param('id');

        $token = $this->lock->acquire($page_id);
        if ($token === null) return Rest_Api::fail('emcp_locked', "Page {$page_id} is being modified", 423);

        try {
            $page = $this->load_page($req);
            if (is_array($page) && isset($page['_fail'])) return $page['_fail'];

            $result = $apply($page['data'], $req);
            if (isset($result['fail'])) return $result['fail'];

            $this->backups->snapshot($page_id, $page['data']);
            update_post_meta($page_id, '_elementor_data', wp_slash(wp_json_encode($result['data'])));
            $this->cache->clear_for_page($page_id);

            return $result['response'];
        } finally {
            $this->lock->release($page_id, $token);
        }
    }

    /** Returns either ['data' => array] or ['_fail' => Response]. */
    private function load_page($req): array {
        $id = (int) $req->get_param('id');
        $post = get_post($id);
        $edit = get_post_meta($id, '_elementor_edit_mode', true);
        if (!$post || $edit !== 'builder') {
            return ['_fail' => Rest_Api::fail('emcp_not_found', "Page {$id} not found", 404)];
        }
        $data = json_decode(get_post_meta($id, '_elementor_data', true) ?: '[]', true);
        return ['data' => is_array($data) ? $data : []];
    }
}
```

- [ ] **Step 4: Wire into `Rest_Api::register_routes()`**

After the Rest_Pages wiring, add:

```php
        (new Rest_Sections(
            new Section_Parser(),
            new Backup_Store(),
            new Cache_Invalidator(),
            new Page_Lock(),
        ))->register_routes();
```

- [ ] **Step 5: Run all tests, confirm pass**

```bash
vendor/bin/phpunit
```

Expected: ~37 tests green (previous 27 + 4 sections).

- [ ] **Step 6: Commit**

```bash
cd .. && git add wp-plugin/includes/Rest_Sections.php wp-plugin/includes/Rest_Api.php wp-plugin/tests/Unit/Rest_SectionsTest.php
git commit -m "feat(plugin): /pages/{id}/sections CRUD with lock + backup + cache clear

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 13: Backup REST endpoints (list + restore)

**Files:**
- Create: `wp-plugin/includes/Rest_Backups.php`
- Modify: `wp-plugin/includes/Rest_Api.php` — wire backups
- Test: `wp-plugin/tests/Unit/Rest_BackupsTest.php`

- [ ] **Step 1: Write failing test**

`wp-plugin/tests/Unit/Rest_BackupsTest.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Rest_Backups;
use ElementorMCP\Backup_Store;
use ElementorMCP\Cache_Invalidator;
use ElementorMCP\Page_Lock;

class Rest_BackupsTest extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'rest_ensure_response' => fn($d) => $d,
            'current_user_can'     => fn($c) => true,
            'wp_slash'             => fn($s) => $s,
            'wp_json_encode'       => fn($v) => json_encode($v),
            'current_time'         => fn() => '2026-05-28 10:00:00',
        ]);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_list_returns_summaries() {
        Functions\expect('get_post')->andReturn((object)['ID'=>1, 'post_type'=>'page']);
        Functions\expect('get_post_meta')->with(1, '_elementor_edit_mode', true)->andReturn('builder');
        Functions\expect('get_post_meta')->with(1, '_elementor_data_backup_history', true)
            ->andReturn(json_encode([
                ['version'=>2,'timestamp'=>'b','data'=>[['id'=>'x']]],
                ['version'=>1,'timestamp'=>'a','data'=>[]],
            ]));
        $r = $this->svc()->list($this->req(['id'=>1]));
        $this->assertTrue($r['ok']);
        $this->assertCount(2, $r['data']);
        $this->assertSame(2, $r['data'][0]['version']);
        $this->assertSame(1, $r['data'][0]['sections_count']);
    }

    public function test_restore_replaces_current_with_snapshot_and_snapshots_again() {
        Functions\expect('get_transient')->andReturn(false);
        Functions\expect('set_transient')->once();
        Functions\expect('get_post')->andReturn((object)['ID'=>1, 'post_type'=>'page']);
        Functions\expect('get_post_meta')->with(1, '_elementor_edit_mode', true)->andReturn('builder');
        Functions\expect('get_post_meta')->with(1, '_elementor_data', true)->andReturn('[]');
        Functions\expect('get_post_meta')->with(1, '_elementor_data_backup_history', true)
            ->andReturn(json_encode([['version'=>1,'timestamp'=>'a','data'=>[['id'=>'old']]]]));
        Functions\expect('update_post_meta')->atLeast()->once();
        Functions\expect('delete_post_meta')->once()->with(1, '_elementor_css');
        Functions\expect('get_transient')->andReturn(\Mockery::any());
        Functions\expect('delete_transient')->once();

        $r = $this->svc()->restore($this->req(['id'=>1, 'version'=>1]));
        $this->assertTrue($r['ok']);
        $this->assertSame(1, $r['data']['restored_from_version']);
    }

    public function test_restore_returns_404_on_unknown_version() {
        Functions\expect('get_transient')->andReturn(false);
        Functions\expect('set_transient')->once();
        Functions\expect('get_post')->andReturn((object)['ID'=>1, 'post_type'=>'page']);
        Functions\expect('get_post_meta')->with(1, '_elementor_edit_mode', true)->andReturn('builder');
        Functions\expect('get_post_meta')->with(1, '_elementor_data', true)->andReturn('[]');
        Functions\expect('get_post_meta')->with(1, '_elementor_data_backup_history', true)->andReturn('[]');
        Functions\expect('get_transient')->andReturn(\Mockery::any());
        Functions\expect('delete_transient')->once();

        $r = $this->svc()->restore($this->req(['id'=>1, 'version'=>99]));
        $this->assertFalse($r['ok']);
        $this->assertSame('emcp_not_found', $r['error']['code']);
    }

    private function svc(): Rest_Backups {
        return new Rest_Backups(new Backup_Store(), new Cache_Invalidator(), new Page_Lock());
    }

    private function req(array $params) {
        return new class($params) {
            public function __construct(private array $params) {}
            public function get_param($k) { return $this->params[$k] ?? null; }
        };
    }
}
```

- [ ] **Step 2: Run test, confirm fail**

```bash
vendor/bin/phpunit --filter Rest_BackupsTest
```

- [ ] **Step 3: Implement `wp-plugin/includes/Rest_Backups.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Rest_Backups {
    public function __construct(
        private Backup_Store $store,
        private Cache_Invalidator $cache,
        private Page_Lock $lock,
    ) {}

    public function register_routes(): void {
        $ns = Rest_Api::NS;
        register_rest_route($ns, '/pages/(?P<id>\d+)/backups', [
            'methods'=>'GET', 'callback'=>[$this,'list'],
            'permission_callback'=>fn()=>current_user_can('edit_posts'),
        ]);
        register_rest_route($ns, '/pages/(?P<id>\d+)/backups/(?P<version>\d+)/restore', [
            'methods'=>'POST', 'callback'=>[$this,'restore'],
            'permission_callback'=>fn()=>current_user_can('edit_posts'),
        ]);
    }

    public function list($req) {
        $page_id = (int) $req->get_param('id');
        if (!$this->is_elementor_page($page_id)) {
            return Rest_Api::fail('emcp_not_found', "Page {$page_id} not found", 404);
        }
        return Rest_Api::ok($this->store->list($page_id));
    }

    public function restore($req) {
        $page_id = (int) $req->get_param('id');
        $version = (int) $req->get_param('version');

        $token = $this->lock->acquire($page_id);
        if ($token === null) return Rest_Api::fail('emcp_locked', "Page {$page_id} is being modified", 423);

        try {
            if (!$this->is_elementor_page($page_id)) {
                return Rest_Api::fail('emcp_not_found', "Page {$page_id} not found", 404);
            }

            $entry = $this->store->get($page_id, $version);
            if (!$entry) return Rest_Api::fail('emcp_not_found', "Backup version {$version} not found", 404);

            // Snapshot the current state so restore itself is reversible.
            $current = json_decode(get_post_meta($page_id, '_elementor_data', true) ?: '[]', true);
            $this->store->snapshot($page_id, is_array($current) ? $current : []);

            update_post_meta($page_id, '_elementor_data', wp_slash(wp_json_encode($entry['data'])));
            $this->cache->clear_for_page($page_id);

            return Rest_Api::ok([
                'restored_from_version' => $version,
                'sections_count'        => count($entry['data']),
            ]);
        } finally {
            $this->lock->release($page_id, $token);
        }
    }

    private function is_elementor_page(int $page_id): bool {
        $post = get_post($page_id);
        return $post && get_post_meta($page_id, '_elementor_edit_mode', true) === 'builder';
    }
}
```

- [ ] **Step 4: Wire into `Rest_Api::register_routes()`**

After Rest_Sections wiring, add:

```php
        (new Rest_Backups(new Backup_Store(), new Cache_Invalidator(), new Page_Lock()))->register_routes();
```

- [ ] **Step 5: Run all tests, confirm pass**

```bash
vendor/bin/phpunit
```

Expected: ~40 green.

- [ ] **Step 6: Commit**

```bash
cd .. && git add wp-plugin/includes/Rest_Backups.php wp-plugin/includes/Rest_Api.php wp-plugin/tests/Unit/Rest_BackupsTest.php
git commit -m "feat(plugin): /pages/{id}/backups list + restore

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 14: MCP `section.*` tools (CRUD + duplicate + reorder + history + restore)

**Files:**
- Create: `mcp-server/elementor_mcp/tools/section.py`
- Modify: `mcp-server/elementor_mcp/server.py` — register section tools
- Test: `mcp-server/tests/unit/test_tools_section.py`

- [ ] **Step 1: Write failing test**

`mcp-server/tests/unit/test_tools_section.py`:

```python
from unittest.mock import MagicMock

from elementor_mcp.envelope import ok
from elementor_mcp.tools.section import (
    section_add, section_delete, section_duplicate, section_get,
    section_history, section_list, section_reorder, section_restore,
    section_update,
)


def test_section_list():
    client = MagicMock()
    client.get.return_value = ok([])
    section_list(client, page_id=1)
    client.get.assert_called_once_with("/pages/1/sections")


def test_section_get():
    client = MagicMock()
    client.get.return_value = ok({})
    section_get(client, page_id=1, sid="abc")
    client.get.assert_called_once_with("/pages/1/sections/abc")


def test_section_add_with_position():
    client = MagicMock()
    client.post.return_value = ok({"sid": "new"})
    json_blob = {"id": "new", "elType": "section", "settings": {}, "elements": []}
    section_add(client, page_id=1, section_json=json_blob, position=2)
    client.post.assert_called_once_with("/pages/1/sections", json={"json": json_blob, "position": 2})


def test_section_add_omits_position_when_none():
    client = MagicMock()
    client.post.return_value = ok({"sid": "new"})
    section_add(client, page_id=1, section_json={"id": "x"})
    client.post.assert_called_once_with("/pages/1/sections", json={"json": {"id": "x"}})


def test_section_update():
    client = MagicMock()
    client.put.return_value = ok({"sid": "a"})
    section_update(client, page_id=1, sid="a", section_json={"id": "a"})
    client.put.assert_called_once_with("/pages/1/sections/a", json={"json": {"id": "a"}})


def test_section_delete_duplicate_reorder():
    client = MagicMock()
    client.delete.return_value = ok({})
    client.post.return_value = ok({})
    section_delete(client, page_id=1, sid="a")
    section_duplicate(client, page_id=1, sid="a")
    section_reorder(client, page_id=1, order=["b", "a"])
    client.delete.assert_called_with("/pages/1/sections/a")
    assert client.post.call_args_list[0].args == ("/pages/1/sections/a/duplicate",)
    assert client.post.call_args_list[1].args == ("/pages/1/sections/reorder",)
    assert client.post.call_args_list[1].kwargs == {"json": {"order": ["b", "a"]}}


def test_section_history_and_restore():
    client = MagicMock()
    client.get.return_value = ok([])
    client.post.return_value = ok({})
    section_history(client, page_id=1)
    section_restore(client, page_id=1, version=2)
    client.get.assert_called_with("/pages/1/backups")
    client.post.assert_called_with("/pages/1/backups/2/restore", json={})
```

- [ ] **Step 2: Run test, confirm fail**

```bash
uv run pytest tests/unit/test_tools_section.py -v
```

- [ ] **Step 3: Implement `mcp-server/elementor_mcp/tools/section.py`**

```python
from ..core.wp_client import WpClient
from ..envelope import ToolResult


def section_list(client: WpClient, *, page_id: int) -> ToolResult:
    return client.get(f"/pages/{page_id}/sections")


def section_get(client: WpClient, *, page_id: int, sid: str) -> ToolResult:
    return client.get(f"/pages/{page_id}/sections/{sid}")


def section_add(
    client: WpClient, *, page_id: int, section_json: dict, position: int | None = None,
) -> ToolResult:
    body = {"json": section_json}
    if position is not None:
        body["position"] = position
    return client.post(f"/pages/{page_id}/sections", json=body)


def section_update(client: WpClient, *, page_id: int, sid: str, section_json: dict) -> ToolResult:
    return client.put(f"/pages/{page_id}/sections/{sid}", json={"json": section_json})


def section_delete(client: WpClient, *, page_id: int, sid: str) -> ToolResult:
    return client.delete(f"/pages/{page_id}/sections/{sid}")


def section_duplicate(client: WpClient, *, page_id: int, sid: str) -> ToolResult:
    return client.post(f"/pages/{page_id}/sections/{sid}/duplicate")


def section_reorder(client: WpClient, *, page_id: int, order: list[str]) -> ToolResult:
    return client.post(f"/pages/{page_id}/sections/reorder", json={"order": order})


def section_history(client: WpClient, *, page_id: int) -> ToolResult:
    return client.get(f"/pages/{page_id}/backups")


def section_restore(client: WpClient, *, page_id: int, version: int) -> ToolResult:
    return client.post(f"/pages/{page_id}/backups/{version}/restore", json={})
```

- [ ] **Step 4: Register tools in `server.py`**

Inside `_list()`, append the following Tool entries:

```python
            Tool(name="section_list", description="List flat section summaries for a page.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},
                 },"required":["page_id"],"additionalProperties":False}),
            Tool(name="section_get", description="Get a single section's full JSON.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},"sid":{"type":"string"},
                 },"required":["page_id","sid"],"additionalProperties":False}),
            Tool(name="section_add", description="Append or insert a new section.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},
                     "section_json":{"type":"object"},
                     "position":{"type":"integer"},
                 },"required":["page_id","section_json"],"additionalProperties":False}),
            Tool(name="section_update", description="Replace a section by id.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},"sid":{"type":"string"},
                     "section_json":{"type":"object"},
                 },"required":["page_id","sid","section_json"],"additionalProperties":False}),
            Tool(name="section_delete", description="Delete a section by id.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},"sid":{"type":"string"},
                 },"required":["page_id","sid"],"additionalProperties":False}),
            Tool(name="section_duplicate", description="Duplicate a section in place (right after).",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},"sid":{"type":"string"},
                 },"required":["page_id","sid"],"additionalProperties":False}),
            Tool(name="section_reorder", description="Reorder sections.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},
                     "order":{"type":"array","items":{"type":"string"}},
                 },"required":["page_id","order"],"additionalProperties":False}),
            Tool(name="section_history", description="List the last 5 backups for a page.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},
                 },"required":["page_id"],"additionalProperties":False}),
            Tool(name="section_restore", description="Restore a backup version.",
                 inputSchema={"type":"object","properties":{
                     "page_id":{"type":"integer"},"version":{"type":"integer"},
                 },"required":["page_id","version"],"additionalProperties":False}),
```

Inside `_call()`, expand the if/elif chain:

```python
        from .tools.section import (
            section_list, section_get, section_add, section_update,
            section_delete, section_duplicate, section_reorder,
            section_history, section_restore,
        )
        # ...
        elif name == "section_list":      result = section_list(client, **arguments)
        elif name == "section_get":       result = section_get(client, **arguments)
        elif name == "section_add":       result = section_add(client, **arguments)
        elif name == "section_update":    result = section_update(client, **arguments)
        elif name == "section_delete":    result = section_delete(client, **arguments)
        elif name == "section_duplicate": result = section_duplicate(client, **arguments)
        elif name == "section_reorder":   result = section_reorder(client, **arguments)
        elif name == "section_history":   result = section_history(client, **arguments)
        elif name == "section_restore":   result = section_restore(client, **arguments)
```

- [ ] **Step 5: Run unit tests, confirm pass**

```bash
uv run pytest tests/unit -v
```

Expected: 31 green (24 previous + 7 new section tests).

- [ ] **Step 6: Commit**

```bash
cd .. && git add mcp-server/elementor_mcp/tools/section.py mcp-server/elementor_mcp/server.py mcp-server/tests/unit/test_tools_section.py
git commit -m "feat(mcp): section.* tools (CRUD + duplicate + reorder + history + restore)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 15: MCP `kit.*` tools (raw kit get/set passthrough)

**Files:**
- Create: `mcp-server/elementor_mcp/tools/kit.py`
- Test: `mcp-server/tests/unit/test_tools_kit.py`
- Modify: `mcp-server/elementor_mcp/server.py`

These tools wrap §7.3 endpoints (GET /kit, PUT /kit). The WP plugin already exposes them via Rest_Profiles::apply path; for raw kit access we add a small new endpoint group. Skipping the WP side for Phase 1a and treating these as MCP-only stubs that POST through `/profiles/{id}/apply` would couple things — instead we add real `/kit` endpoints here.

Add `Rest_Kit.php` first.

- [ ] **Step 1: Write failing test** — `wp-plugin/tests/Unit/Rest_KitTest.php`

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Rest_Kit;

class Rest_KitTest extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'rest_ensure_response' => fn($d) => $d,
            'current_user_can'     => fn($c) => true,
        ]);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_get_returns_kit_settings() {
        Functions\expect('get_option')->with('elementor_active_kit', 0)->andReturn(11);
        Functions\expect('get_post_meta')->with(11, '_elementor_page_settings', true)
            ->andReturn(['system_colors' => [['_id' => 'primary', 'color' => '#000']]]);
        $r = (new Rest_Kit())->get($this->req([]));
        $this->assertTrue($r['ok']);
        $this->assertSame('#000', $r['data']['system_colors'][0]['color']);
    }

    public function test_put_replaces_settings() {
        Functions\expect('get_option')->with('elementor_active_kit', 0)->andReturn(11);
        Functions\expect('update_post_meta')->once()->with(11, '_elementor_page_settings', ['x' => 1]);
        $r = (new Rest_Kit())->put($this->req([], ['x' => 1]));
        $this->assertTrue($r['ok']);
    }

    public function test_returns_500_when_no_active_kit() {
        Functions\expect('get_option')->with('elementor_active_kit', 0)->andReturn(0);
        $r = (new Rest_Kit())->get($this->req([]));
        $this->assertFalse($r['ok']);
        $this->assertSame('emcp_internal', $r['error']['code']);
    }

    private function req(array $params, $body = null) {
        return new class($params, $body) {
            public function __construct(private array $params, private $body) {}
            public function get_param($k) { return $this->params[$k] ?? null; }
            public function get_json_params() { return $this->body; }
        };
    }
}
```

- [ ] **Step 2: Run test, confirm fail**

```bash
cd wp-plugin && vendor/bin/phpunit --filter Rest_KitTest
```

- [ ] **Step 3: Implement `wp-plugin/includes/Rest_Kit.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Rest_Kit {
    const KIT_OPTION = 'elementor_active_kit';
    const KIT_META   = '_elementor_page_settings';

    public function register_routes(): void {
        $ns = Rest_Api::NS;
        register_rest_route($ns, '/kit', [
            ['methods'=>'GET', 'callback'=>[$this,'get'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'PUT', 'callback'=>[$this,'put'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
        ]);
    }

    public function get($req) {
        $id = (int) get_option(self::KIT_OPTION, 0);
        if ($id <= 0) return Rest_Api::fail('emcp_internal', 'Elementor active kit not configured', 500);
        $settings = get_post_meta($id, self::KIT_META, true);
        return Rest_Api::ok(is_array($settings) ? $settings : []);
    }

    public function put($req) {
        $id = (int) get_option(self::KIT_OPTION, 0);
        if ($id <= 0) return Rest_Api::fail('emcp_internal', 'Elementor active kit not configured', 500);
        $body = $req->get_json_params() ?? [];
        update_post_meta($id, self::KIT_META, $body);
        return Rest_Api::ok(['kit_post_id' => $id]);
    }
}
```

Wire in `Rest_Api::register_routes()`:

```php
        (new Rest_Kit())->register_routes();
```

- [ ] **Step 4: Run plugin tests, confirm green**

```bash
vendor/bin/phpunit
```

- [ ] **Step 5: Write Python failing test `mcp-server/tests/unit/test_tools_kit.py`**

```python
from unittest.mock import MagicMock

from elementor_mcp.envelope import ok
from elementor_mcp.tools.kit import kit_get, kit_set


def test_kit_get():
    client = MagicMock()
    client.get.return_value = ok({})
    kit_get(client)
    client.get.assert_called_once_with("/kit")


def test_kit_set():
    client = MagicMock()
    client.put.return_value = ok({"kit_post_id": 11})
    kit_set(client, settings={"a": 1})
    client.put.assert_called_once_with("/kit", json={"a": 1})
```

- [ ] **Step 6: Implement `mcp-server/elementor_mcp/tools/kit.py`**

```python
from ..core.wp_client import WpClient
from ..envelope import ToolResult


def kit_get(client: WpClient) -> ToolResult:
    return client.get("/kit")


def kit_set(client: WpClient, *, settings: dict) -> ToolResult:
    return client.put("/kit", json=settings)
```

Register in `server.py` `_list()`:

```python
            Tool(name="kit_get", description="Read the current Elementor Kit settings.",
                 inputSchema={"type":"object","properties":{},"additionalProperties":False}),
            Tool(name="kit_set", description="Replace the Elementor Kit settings (raw, advanced).",
                 inputSchema={"type":"object","properties":{
                     "settings":{"type":"object"},
                 },"required":["settings"],"additionalProperties":False}),
```

Register in `_call()`:

```python
        from .tools.kit import kit_get, kit_set
        # ...
        elif name == "kit_get": result = kit_get(client)
        elif name == "kit_set": result = kit_set(client, **arguments)
```

- [ ] **Step 7: Run all unit tests, confirm green**

```bash
cd mcp-server && uv run pytest tests/unit -v
```

Expected: 33 green.

- [ ] **Step 8: Commit**

```bash
cd .. && git add wp-plugin/includes/Rest_Kit.php wp-plugin/includes/Rest_Api.php wp-plugin/tests/Unit/Rest_KitTest.php mcp-server/elementor_mcp/tools/kit.py mcp-server/elementor_mcp/server.py mcp-server/tests/unit/test_tools_kit.py
git commit -m "feat(plugin+mcp): /kit raw get/set + kit.* MCP tools

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 16: End-to-end integration test (Profile → Page → Sections → Backup → Restore)

**Files:**
- Create: `mcp-server/tests/integration/test_p1a_end_to_end.py`

This test depends on wp-env running and `EMCP_TEST_API_KEY` set, the same setup used by the existing P0 integration test.

- [ ] **Step 1: Write the test**

```python
import os
import uuid

import pytest

from elementor_mcp.core.wp_client import WpClient
from elementor_mcp.tools.kit import kit_get
from elementor_mcp.tools.page import page_create, page_delete, page_get
from elementor_mcp.tools.profile import (
    profile_apply, profile_create, profile_delete, profile_get, profile_list,
)
from elementor_mcp.tools.section import (
    section_add, section_delete, section_get, section_history,
    section_list, section_reorder, section_restore,
)


@pytest.fixture
def client(live_settings):
    return WpClient(live_settings)


def _profile_payload(name: str) -> dict:
    return {
        "name": name,
        "colors": {"primary":"#0066FF","secondary":"#00C2A8","text":"#1A1A1A","accent":"#FFD60A","background":"#FFFFFF","custom":[]},
        "fonts": {"primary":{"family":"Inter","source":"google","weights":[400,700]},"secondary":{"family":"Manrope","source":"google","weights":[400,700]}},
        "typography": {
            "h1":{"size":64,"mobile":36,"weight":700,"line_height":1.1},
            "h2":{"size":48,"mobile":28,"weight":700,"line_height":1.15},
            "h3":{"size":32,"mobile":22,"weight":600,"line_height":1.2},
            "body":{"size":17,"mobile":15,"weight":500,"line_height":1.6},
            "small":{"size":14,"mobile":12,"weight":500,"line_height":1.5},
        },
        "layout":{"container_width":1290,"content_width":1200,"section_padding":{"top":80,"bottom":80},"section_padding_mobile":{"top":40,"bottom":40}},
        "breakpoints":{"mobile":767,"desktop":1290},
        "buttons":{"border_radius":0,"padding_x":32,"padding_y":16},
    }


def _section_json(sid: str, title: str) -> dict:
    return {
        "id": sid,
        "elType": "section",
        "settings": {"_title": title},
        "elements": [],
    }


def test_full_roundtrip(client):
    # 1. Create + apply profile
    profile_name = f"itest-{uuid.uuid4().hex[:6]}"
    created = profile_create(client, profile=_profile_payload(profile_name))
    assert created.ok, created.error
    pid = created.data["id"]

    fetched = profile_get(client, profile_id=pid)
    assert fetched.ok and fetched.data["name"] == profile_name

    applied = profile_apply(client, profile_id=pid)
    assert applied.ok and applied.data["kit_post_id"] > 0

    # Verify kit settings reflect profile
    kit = kit_get(client)
    assert kit.ok and len(kit.data.get("system_colors", [])) >= 4

    # 2. Create page
    page_title = f"itest-page-{uuid.uuid4().hex[:6]}"
    created_page = page_create(client, title=page_title, profile_id=pid)
    assert created_page.ok, created_page.error
    page_id = created_page.data["id"]

    # 3. Add two sections
    sid_a = uuid.uuid4().hex[:8]
    sid_b = uuid.uuid4().hex[:8]
    assert section_add(client, page_id=page_id, section_json=_section_json(sid_a, "A")).ok
    assert section_add(client, page_id=page_id, section_json=_section_json(sid_b, "B")).ok

    listed = section_list(client, page_id=page_id)
    assert listed.ok and len(listed.data) == 2

    # 4. Reorder, then delete one
    assert section_reorder(client, page_id=page_id, order=[sid_b, sid_a]).ok
    after_reorder = section_list(client, page_id=page_id)
    assert after_reorder.data[0]["sid"] == sid_b

    assert section_delete(client, page_id=page_id, sid=sid_a).ok

    # 5. Backup history should have entries from the mutations above
    history = section_history(client, page_id=page_id)
    assert history.ok and len(history.data) >= 1
    last_version = history.data[0]["version"]

    # 6. Restore — sections_count should match the snapshot at that version
    restored = section_restore(client, page_id=page_id, version=last_version)
    assert restored.ok

    # 7. Cleanup
    assert page_delete(client, page_id=page_id).ok
    assert profile_delete(client, profile_id=pid).ok
```

- [ ] **Step 2: Run integration test**

```bash
# Ensure wp-env is up (re-use docker-compose from P0)
docker compose -f "$HOME/.wp-env/wp-env-elememtor-full-mcp-44381f72/docker-compose.yml" up -d
EMCP_TEST_API_KEY="<your-key>" EMCP_TEST_WP_URL="http://localhost:8888" \
  cd mcp-server && uv run pytest tests/integration -v
```

Expected: P0 integration tests (2) + new end-to-end test = 3 green.

- [ ] **Step 3: Commit**

```bash
cd .. && git add mcp-server/tests/integration/test_p1a_end_to_end.py
git commit -m "test(mcp): end-to-end profile + page + section + backup roundtrip

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 17: README quickstart for Phase 1a

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the existing Quickstart block in README.md**

```markdown
## Quickstart

```bash
make plugin-install
make mcp-install
make wp-up                 # boots wp-env on http://localhost:8888
docker exec wp-env-elememtor-full-mcp-44381f72-cli-1 wp plugin activate wp-plugin
docker exec wp-env-elememtor-full-mcp-44381f72-cli-1 wp rewrite structure '/%postname%/'

# Mint an API key:
KEY=$(docker exec wp-env-elememtor-full-mcp-44381f72-cli-1 \
  wp eval 'require_once ABSPATH . "wp-content/plugins/wp-plugin/elementor-mcp-bridge.php"; \
           echo (new \ElementorMCP\Api_Keys())->generate(1, "dev", ["read","write"])["raw"];')
echo "$KEY"

# Configure MCP:
cp mcp-server/.env.example mcp-server/.env
# edit .env, paste $KEY into WP_API_KEY

# Register with Claude Code:
claude mcp add elementor -s user -- python -m elementor_mcp.server

# Verify integration:
make plugin-test    # 40+ PHPUnit tests
make mcp-test       # 30+ pytest tests
EMCP_TEST_API_KEY="$KEY" EMCP_TEST_WP_URL=http://localhost:8888 \
  cd mcp-server && uv run pytest tests/integration -v
```

After P1a, you have these MCP tools:
- `auth_verify`
- `profile_list`, `profile_get`, `profile_create`, `profile_update`, `profile_delete`, `profile_apply`
- `page_list`, `page_create`, `page_get`, `page_delete`
- `section_list`, `section_get`, `section_add`, `section_update`, `section_delete`,
  `section_duplicate`, `section_reorder`, `section_history`, `section_restore`
- `kit_get`, `kit_set`
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: P1a quickstart + tool inventory

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 18: Acceptance check (all P1a gates green) + push

**Files:** _none_

This is a verification-only task. Run every check, push, and confirm CI is green.

- [ ] **Step 1: Run PHPUnit**

```bash
cd wp-plugin && vendor/bin/phpunit
```

Expected: ≥ 40 tests green.

- [ ] **Step 2: Run Python unit + ruff**

```bash
cd mcp-server && uv run ruff check . && uv run pytest tests/unit -v
```

Expected: lint clean + ≥ 33 tests green.

- [ ] **Step 3: Run integration**

```bash
EMCP_TEST_API_KEY="<key>" EMCP_TEST_WP_URL="http://localhost:8888" \
  uv run pytest tests/integration -v
```

Expected: 3 tests green (P0 round-trip × 2 + P1a end-to-end).

- [ ] **Step 4: Push and confirm CI**

```bash
cd .. && git push
```

Open https://github.com/Harris2896/elementor-full-mcp/actions and confirm all three jobs green.

- [ ] **Step 5: Tag the release**

```bash
git tag -a v0.1.0-p1a -m "Phase 1a: WP CRUD + MCP tools (profiles, pages, sections, backups, raw kit)"
git push --tags
```

---

## P1a Acceptance Criteria

All of the following must hold before declaring Phase 1a complete:

1. `cd wp-plugin && vendor/bin/phpunit` — ≥ 40 unit tests green across the 11 test classes added (`Profile_CPT`, `Profile_Schema`, `Profile_Repository`, `Kit_Writer`, `Rest_Profiles`, `Rest_Pages`, `Section_Parser`, `Backup_Store`, `Page_Lock`, `Rest_Sections`, `Rest_Backups`, `Rest_Kit`) plus the original P0 tests.
2. `cd mcp-server && uv run pytest tests/unit -v` — ≥ 33 tests green; `uv run ruff check .` clean.
3. `EMCP_TEST_API_KEY=… uv run pytest tests/integration -v` — 3 tests green including the end-to-end roundtrip.
4. Manual smoke: `curl -H "Authorization: Bearer $KEY" http://localhost:8888/wp-json/elementor-mcp/v1/profiles` returns `{"ok":true,"data":[]}`.
5. After `POST /profiles` then `POST /profiles/{id}/apply`, `GET /kit` returns Kit settings with `system_colors[0].color == "#0066FF"`.
6. After `POST /pages/{id}/sections` then `GET /pages/{id}/sections`, the list reflects the addition.
7. Backup history accumulates as mutations happen; restoring an older version reproduces its state.
8. CI on `main` shows three green jobs.
9. README quickstart works from a fresh clone of the repo.

---

## Self-review

**1. Spec coverage (P1a portion of spec):**
- §3 #10 (color overflow) — promotion of colors to Kit `custom_colors` is implemented by `Kit_Writer` (Task 4). The auto-promote-on-normalize part lives in P1b's normalizer.
- §3 #11 (mobile-only responsive) — `Kit_Writer` only emits `*_mobile` suffix; `Profile_Schema` does not require tablet. ✓
- §3 #12, #13 (color tier ΔE + diff report) — these belong to the normalizer (P1b). ✓ deferred.
- §3 #14 (5-version backup) — `Backup_Store` (Task 10) + `Rest_Backups` (Task 13). ✓
- §5 (data model: emcp_profile CPT + postmeta) — Task 1, Task 3. ✓
- §5.3 (_elementor_data_backup_history postmeta) — Task 10. ✓
- §6 (profile JSON schema) — Task 2 validates it, Task 4 translates it. ✓
- §7.2 profiles — Task 5. ✓
- §7.3 kit — Task 15. ✓
- §7.4 pages — Task 7. ✓
- §7.5 sections — Task 12. ✓
- §7.6 backups — Task 13. ✓
- §7.7 library admin — explicitly out of scope (P1b).
- §7.8 auth flow — already done in P0.
- §7.9 cache invalidation — Task 11 (Cache_Invalidator) + integration in every mutation in Task 12, Task 13. ✓
- §8 tools (profile, page, section, kit) — Tasks 6, 8, 14, 15. ✓
- §9.3 section CRUD flow with normalize hook — section.add accepts profile_id in §7.5; the normalize call happens here as a no-op because the normalizer arrives in P1b. The endpoint still records profile_id in the response for future use. Note: in Task 12, the `add` endpoint does not currently honor `profile_id` parameter — added as gap to fix in P1b alongside normalizer.
- §15 backup history shape — matches Task 10's `{version, timestamp, data}`. ✓

Spec items deferred to P1b (acceptable since this is P1a): #4 (template indexing), §10 (library), §11 (full kit normalizer), §12 (library imports), library admin UI.

**2. Placeholder scan:** No "TBD/TODO/etc." in the plan. Every step has the actual code or command. ✓

**3. Type consistency:**
- `Rest_Api::ok($data, $warnings = [])` and `Rest_Api::fail($code, $message, $status = 400, $details = [])` — signatures stable across every endpoint. ✓
- `Section_Parser::reorder` throws `\InvalidArgumentException`; `Rest_Sections::reorder` catches it and returns `emcp_invalid`. ✓
- All MCP tool functions return `ToolResult` (the P0 envelope). ✓
- `Profile_Repository::get(int $id): ?array` shape `{id, name, data}` — consumed identically by `Rest_Profiles::get` and `Rest_Profiles::apply`. ✓
- `Backup_Store::list` returns `{version, timestamp, sections_count}`; `Backup_Store::get` returns `{version, timestamp, data}` — both match the spec §15 / §7.6. ✓

No issues to fix inline. P1a is internally consistent.

---

## Continuation: Plan 3 (P1b)

Plan 3 will cover the remaining P1 scope:

| Component | Spec sections | Approx tasks |
|---|---|---|
| Library Stage B (auto-extract metadata) + heuristic categories + `build_index.py` | §10.1 | 6 |
| SQLite schema + FTS5 setup | §10.3 | 2 |
| Hybrid search (FTS5 only — vectors in P2) + `template.*` tools | §10.4 | 3 |
| Kit normalizer six passes + color overflow + diff report + integration into `section.add` | §11 | 10 |
| Image generation (OpenAI gpt-image-1 + Unsplash fallback) + WP media upload + `image.*` tools | §9.4 | 4 |
| MCP `http_server` (FastAPI) + WP plugin library proxy endpoints | §17.4, §7.7 | 4 |
| Library admin UI in WP (stats, verify, JSON upload, snapshot existing page, API keys, profile list) | §12 | 6 |
| `verify_library.py` script + manifest.json | §12.1 | 2 |

Total: ~37 tasks. To be written after P1a ships and CI is green.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-28-elementor-mcp-p1a-wp-crud.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for 18 tasks of dense PHP + Python TDD work.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Best if you want to watch each task in real time (~3-5 hours of continuous tool calls).

**Which approach?**
