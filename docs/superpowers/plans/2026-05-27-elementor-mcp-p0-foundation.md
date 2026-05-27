# Elementor MCP — Phase 0 (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the repo skeleton, a WP plugin that issues bearer API keys and exposes `/auth/verify` + `/health`, and a Python MCP server with a single round-trip tool (`auth_verify`). End state: an agent connected via MCP can call one tool and confirm the WP↔MCP authenticated channel works end-to-end against a local wp-env site.

**Architecture:** PHP WordPress plugin (`elementor-mcp-bridge`) exposes a minimal REST namespace `/wp-json/elementor-mcp/v1/` guarded by bearer-token auth (API keys hashed with `password_hash`, mapped to a WP user). A Python package (`elementor_mcp`) speaks the MCP stdio protocol and calls the plugin via `httpx`. Both sides share a structured response envelope so later phases can extend without re-wiring.

**Tech stack:** PHP 7.4+, WordPress 6.0+, Elementor 3.18+, PHPUnit 9, wp-env (Docker); Python 3.11+, `mcp` SDK, `httpx`, `pydantic`, `pytest`, `pytest-asyncio`, `responses`, `ruff`, `uv`. CI: GitHub Actions.

**Spec reference:** `docs/superpowers/specs/2026-05-27-elementor-mcp-design.md` §3 (decisions), §4 (architecture), §5 (data model), §7.1 + §7.8 (auth flow), §14 (error envelope), §17 (deployment).

**Plan scope:** Phase 0 only. P1 (Core CRUD + normalizer + library), P2 (Prototyper), P3 (Research), P4 (Import) will get their own plans, each written after the prior phase ships and we learn from real usage.

---

## File structure (created by this plan)

```
elementor-full-mcp/
├─ .github/
│  └─ workflows/ci.yml                       # CI: lint + unit + plugin tests
├─ mcp-server/
│  ├─ pyproject.toml                         # Package + deps
│  ├─ ruff.toml                              # Lint config
│  ├─ .env.example                           # WP_URL, WP_API_KEY, log level
│  ├─ elementor_mcp/
│  │  ├─ __init__.py                         # Version
│  │  ├─ server.py                           # MCP stdio entry
│  │  ├─ config.py                           # Env loader (pydantic)
│  │  ├─ envelope.py                         # ToolResult shape + helpers
│  │  ├─ errors.py                           # Error codes enum
│  │  ├─ core/
│  │  │  ├─ __init__.py
│  │  │  └─ wp_client.py                     # httpx wrapper
│  │  └─ tools/
│  │     ├─ __init__.py
│  │     └─ auth.py                          # auth_verify tool
│  └─ tests/
│     ├─ __init__.py
│     ├─ conftest.py                         # Fixtures
│     ├─ unit/
│     │  ├─ test_envelope.py
│     │  ├─ test_config.py
│     │  └─ test_wp_client.py
│     └─ integration/
│        └─ test_auth_verify.py              # Against real wp-env
├─ wp-plugin/
│  ├─ elementor-mcp-bridge.php               # Bootstrap, activation, deactivation
│  ├─ readme.txt                             # WP plugin readme
│  ├─ composer.json                          # PHPUnit + Brain Monkey + WP_Mock
│  ├─ phpunit.xml.dist
│  ├─ includes/
│  │  ├─ class-plugin.php                    # Main class (singleton)
│  │  ├─ class-api-keys.php                  # Key generation + bcrypt storage
│  │  ├─ class-auth.php                      # Bearer filter
│  │  ├─ class-rest-api.php                  # Namespace bootstrap
│  │  └─ class-admin.php                     # Admin menu shell
│  └─ tests/
│     ├─ bootstrap.php
│     └─ unit/
│        ├─ class-test-api-keys.php
│        └─ class-test-auth.php
├─ .wp-env.json                              # wp-env config
├─ docker-compose.override.yml               # (if needed for wp-env volumes)
├─ Makefile                                  # Common commands
├─ README.md                                 # Top-level dev setup
└─ .gitattributes                            # End-of-line normalization
```

**Files modified:**
- `.gitignore` (already exists) — add `wp-plugin/vendor/`, `mcp-server/.venv/`.

---

## Conventions used throughout this plan

**TDD cycle per task:** failing test → run (see fail) → minimal impl → run (see pass) → commit.

**Test commands:**
- Python: `cd mcp-server && uv run pytest <path> -v`
- PHP: `cd wp-plugin && composer test -- --filter <name>`
- Integration (wp-env up first): `cd mcp-server && uv run pytest tests/integration -v`

**Commit message style:** Conventional commits, scope tags `plugin|mcp|infra|test|docs`:
- `feat(plugin): add bearer auth filter`
- `test(mcp): add envelope helpers`
- `chore(infra): wp-env config`

**Branch:** Single `main` branch for P0; no feature branches needed.

**No skip-CI / no --no-verify.** If a hook fails, fix the cause.

---

## P0.1 — Repo scaffolding

**Files:**
- Create: `Makefile`, `README.md`, `.gitattributes`
- Create: `mcp-server/pyproject.toml`, `mcp-server/ruff.toml`, `mcp-server/.env.example`
- Create: `mcp-server/elementor_mcp/__init__.py`
- Create: `wp-plugin/composer.json`, `wp-plugin/phpunit.xml.dist`

- [ ] **Step 1: Create `mcp-server/pyproject.toml`**

```toml
[project]
name = "elementor-mcp"
version = "0.0.1"
description = "MCP server for Elementor page authoring"
requires-python = ">=3.11"
dependencies = [
  "mcp>=1.0.0",
  "httpx>=0.27",
  "pydantic>=2.6",
  "pydantic-settings>=2.2",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "responses>=0.25",
  "ruff>=0.4",
]

[project.scripts]
elementor-mcp = "elementor_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create `mcp-server/ruff.toml`**

```toml
line-length = 100
target-version = "py311"

[lint]
select = ["E", "F", "I", "B", "UP", "SIM"]
ignore = ["E501"]
```

- [ ] **Step 3: Create `mcp-server/.env.example`**

```dotenv
WP_URL=http://localhost:8888
WP_API_KEY=emcp_changeme
LOG_LEVEL=info
HTTP_TIMEOUT=15
```

- [ ] **Step 4: Create `mcp-server/elementor_mcp/__init__.py`**

```python
"""Elementor MCP — Python MCP server for the Elementor page-authoring system."""

__version__ = "0.0.1"
```

- [ ] **Step 5: Create `wp-plugin/composer.json`**

```json
{
  "name": "leobot/elementor-mcp-bridge",
  "description": "WordPress bridge plugin for Elementor MCP",
  "type": "wordpress-plugin",
  "license": "MIT",
  "require": {
    "php": ">=7.4"
  },
  "require-dev": {
    "phpunit/phpunit": "^9.6",
    "brain/monkey": "^2.6",
    "10up/wp_mock": "^1.0"
  },
  "autoload": {
    "psr-4": {"ElementorMCP\\": "includes/"}
  },
  "autoload-dev": {
    "psr-4": {"ElementorMCP\\Tests\\": "tests/"}
  },
  "scripts": {
    "test": "phpunit"
  }
}
```

- [ ] **Step 6: Create `wp-plugin/phpunit.xml.dist`**

```xml
<?xml version="1.0"?>
<phpunit bootstrap="tests/bootstrap.php" colors="true" verbose="true">
  <testsuites>
    <testsuite name="unit">
      <directory>tests/unit</directory>
    </testsuite>
  </testsuites>
</phpunit>
```

- [ ] **Step 7: Create `Makefile`**

```makefile
.PHONY: help mcp-install mcp-test mcp-lint plugin-install plugin-test wp-up wp-down

help:
	@echo "mcp-install   - uv pip install -e mcp-server[dev]"
	@echo "mcp-test      - run python tests"
	@echo "mcp-lint      - ruff check"
	@echo "plugin-install- composer install in wp-plugin"
	@echo "plugin-test   - phpunit in wp-plugin"
	@echo "wp-up         - start wp-env"
	@echo "wp-down       - stop wp-env"

mcp-install:
	cd mcp-server && uv venv && uv pip install -e ".[dev]"

mcp-test:
	cd mcp-server && uv run pytest -v

mcp-lint:
	cd mcp-server && uv run ruff check .

plugin-install:
	cd wp-plugin && composer install

plugin-test:
	cd wp-plugin && composer test

wp-up:
	npx wp-env start

wp-down:
	npx wp-env stop
```

- [ ] **Step 8: Create `README.md`**

```markdown
# Elementor MCP

Python MCP server + WordPress plugin for AI-driven Elementor page authoring.

See `docs/superpowers/specs/2026-05-27-elementor-mcp-design.md` for the design.

## Quickstart

```bash
make plugin-install
make mcp-install
make wp-up                 # boots wp-env on http://localhost:8888
# In WP admin (login admin/password): activate "Elementor MCP Bridge",
# go to Elementor MCP → API Keys → Generate, copy the key.
cp mcp-server/.env.example mcp-server/.env  # paste API key
make mcp-test
```
```

- [ ] **Step 9: Create `.gitattributes`**

```
* text=auto eol=lf
*.php text eol=lf
*.py text eol=lf
*.bat text eol=crlf
```

- [ ] **Step 10: Add ignore entries**

Edit `.gitignore` — append:

```
wp-plugin/vendor/
wp-plugin/composer.lock
mcp-server/.venv/
mcp-server/uv.lock
mcp-server/.env
mcp-server/elementor_mcp/data/index.db
.wp-env/
```

- [ ] **Step 11: Commit**

```bash
git add Makefile README.md .gitattributes .gitignore mcp-server/ wp-plugin/composer.json wp-plugin/phpunit.xml.dist
git commit -m "chore(infra): repo scaffolding for mcp-server and wp-plugin"
```

---

## P0.2 — WP plugin bootstrap

**Files:**
- Create: `wp-plugin/elementor-mcp-bridge.php`
- Create: `wp-plugin/includes/class-plugin.php`
- Create: `wp-plugin/readme.txt`
- Test: `wp-plugin/tests/bootstrap.php`, `wp-plugin/tests/unit/class-test-plugin.php`

- [ ] **Step 1: Create `wp-plugin/tests/bootstrap.php`**

```php
<?php
require_once __DIR__ . '/../vendor/autoload.php';
\Brain\Monkey\setUp();
register_shutdown_function(function () { \Brain\Monkey\tearDown(); });
```

- [ ] **Step 2: Write failing test `wp-plugin/tests/unit/class-test-plugin.php`**

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Plugin;

class TestPlugin extends TestCase {
    protected function setUp(): void { \Brain\Monkey\setUp(); }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_singleton_returns_same_instance() {
        $a = Plugin::instance();
        $b = Plugin::instance();
        $this->assertSame($a, $b);
    }

    public function test_init_registers_admin_menu_action() {
        Functions\expect('add_action')->once()->with('admin_menu', \Mockery::any());
        Functions\expect('add_action')->andReturnNull();
        Plugin::instance()->init();
    }

    public function test_version_is_string() {
        $this->assertIsString(Plugin::VERSION);
    }
}
```

- [ ] **Step 3: Run test, confirm fail**

```bash
cd wp-plugin && composer install
composer test -- --filter TestPlugin
```

Expected: failure (class `ElementorMCP\Plugin` not found).

- [ ] **Step 4: Implement `wp-plugin/includes/class-plugin.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Plugin {
    const VERSION = '0.0.1';

    private static ?Plugin $instance = null;

    public static function instance(): self {
        if (self::$instance === null) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    public function init(): void {
        add_action('admin_menu', [$this, 'register_admin_menu']);
        add_action('rest_api_init', [$this, 'register_rest_routes']);
    }

    public function register_admin_menu(): void {
        // Filled in P0.3
    }

    public function register_rest_routes(): void {
        // Filled in P0.6
    }
}
```

- [ ] **Step 5: Implement `wp-plugin/elementor-mcp-bridge.php`**

```php
<?php
/**
 * Plugin Name: Elementor MCP Bridge
 * Description: REST + admin bridge for the Elementor MCP Python server.
 * Version: 0.0.1
 * Author: leobot
 * Requires PHP: 7.4
 * Requires at least: 6.0
 */

defined('ABSPATH') || exit;

require_once __DIR__ . '/vendor/autoload.php';

register_activation_hook(__FILE__, function () {
    update_option('elementor_mcp_version', \ElementorMCP\Plugin::VERSION);
});

register_deactivation_hook(__FILE__, function () {
    // No cleanup yet; keep API keys and profiles on deactivate.
});

add_action('plugins_loaded', function () {
    \ElementorMCP\Plugin::instance()->init();
});
```

- [ ] **Step 6: Create `wp-plugin/readme.txt`**

```
=== Elementor MCP Bridge ===
Requires at least: 6.0
Tested up to: 6.5
Requires PHP: 7.4
License: MIT

REST + admin bridge for the Elementor MCP Python server.
```

- [ ] **Step 7: Run test, confirm pass**

```bash
composer test -- --filter TestPlugin
```

Expected: all three tests green.

- [ ] **Step 8: Commit**

```bash
git add wp-plugin/elementor-mcp-bridge.php wp-plugin/includes/class-plugin.php wp-plugin/tests wp-plugin/readme.txt
git commit -m "feat(plugin): bootstrap class + activation hooks"
```

---

## P0.3 — WP plugin admin menu shell

**Files:**
- Create: `wp-plugin/includes/class-admin.php`
- Modify: `wp-plugin/includes/class-plugin.php` (instantiate Admin)
- Test: `wp-plugin/tests/unit/class-test-admin.php`

- [ ] **Step 1: Write failing test**

`wp-plugin/tests/unit/class-test-admin.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Admin;

class TestAdmin extends TestCase {
    protected function setUp(): void { \Brain\Monkey\setUp(); }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_register_menu_adds_top_level_page() {
        Functions\expect('add_menu_page')
            ->once()
            ->with('Elementor MCP', 'Elementor MCP', 'manage_options', 'elementor-mcp', \Mockery::type('callable'), 'dashicons-art', 81);
        (new Admin())->register_menu();
    }
}
```

- [ ] **Step 2: Run test, confirm fail**

```bash
composer test -- --filter TestAdmin
```

- [ ] **Step 3: Implement `wp-plugin/includes/class-admin.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Admin {
    public function register_menu(): void {
        add_menu_page(
            'Elementor MCP',
            'Elementor MCP',
            'manage_options',
            'elementor-mcp',
            [$this, 'render_page'],
            'dashicons-art',
            81
        );
    }

    public function render_page(): void {
        echo '<div class="wrap"><h1>Elementor MCP</h1><p>Phase 0 — admin shell.</p></div>';
    }
}
```

- [ ] **Step 4: Wire into Plugin**

Edit `wp-plugin/includes/class-plugin.php`, replace `register_admin_menu` body:

```php
public function register_admin_menu(): void {
    (new Admin())->register_menu();
}
```

- [ ] **Step 5: Run test, confirm pass**

```bash
composer test -- --filter TestAdmin
```

- [ ] **Step 6: Commit**

```bash
git add wp-plugin/includes/class-admin.php wp-plugin/includes/class-plugin.php wp-plugin/tests/unit/class-test-admin.php
git commit -m "feat(plugin): admin menu shell"
```

---

## P0.4 — API key generation + bcrypt storage

**Files:**
- Create: `wp-plugin/includes/class-api-keys.php`
- Test: `wp-plugin/tests/unit/class-test-api-keys.php`

API keys have shape `emcp_<id>_<secret>` where `<id>` is a 12-char URL-safe random string used to look up the row, and `<secret>` is a 32-char URL-safe random string that gets `password_hash`'d. We store an array of `{id, hash, label, user_id, scopes, created_at, last_used}` in option `elementor_mcp_api_keys`.

- [ ] **Step 1: Write failing test**

`wp-plugin/tests/unit/class-test-api-keys.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Api_Keys;

class TestApiKeys extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'wp_generate_password' => fn($len, $special = true) => str_repeat('a', $len),
            'current_time'         => 'mysql',
            'sanitize_text_field'  => fn($s) => trim((string)$s),
        ]);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_generate_returns_raw_key_with_prefix() {
        Functions\expect('get_option')->andReturn([]);
        Functions\expect('update_option')->once();
        $result = (new Api_Keys())->generate(1, 'dev', ['read', 'write']);
        $this->assertStringStartsWith('emcp_', $result['raw']);
        $this->assertSame(1, $result['record']['user_id']);
        $this->assertSame('dev', $result['record']['label']);
    }

    public function test_verify_accepts_correct_key() {
        $svc = new Api_Keys();
        Functions\expect('get_option')->andReturn([]);
        Functions\expect('update_option');
        $made = $svc->generate(7, 'agent', ['read']);
        $raw = $made['raw'];
        Functions\expect('get_option')->andReturn([$made['record']]);
        Functions\expect('update_option');
        $record = $svc->verify($raw);
        $this->assertNotNull($record);
        $this->assertSame(7, $record['user_id']);
    }

    public function test_verify_rejects_wrong_secret() {
        $svc = new Api_Keys();
        Functions\expect('get_option')->andReturn([]);
        Functions\expect('update_option');
        $made = $svc->generate(1, 'x', []);
        $tampered = preg_replace('/.$/', 'X', $made['raw']);
        Functions\expect('get_option')->andReturn([$made['record']]);
        $this->assertNull($svc->verify($tampered));
    }

    public function test_verify_rejects_unknown_id() {
        Functions\expect('get_option')->andReturn([]);
        $this->assertNull((new Api_Keys())->verify('emcp_unknownid12_secret'));
    }

    public function test_verify_rejects_malformed_key() {
        $this->assertNull((new Api_Keys())->verify('not_a_key'));
    }
}
```

- [ ] **Step 2: Run test, confirm fail**

```bash
composer test -- --filter TestApiKeys
```

- [ ] **Step 3: Implement `wp-plugin/includes/class-api-keys.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Api_Keys {
    const OPTION = 'elementor_mcp_api_keys';
    const PREFIX = 'emcp_';

    public function generate(int $user_id, string $label, array $scopes): array {
        $id     = wp_generate_password(12, false);
        $secret = wp_generate_password(32, false);
        $raw    = self::PREFIX . $id . '_' . $secret;
        $record = [
            'id'         => $id,
            'hash'       => password_hash($secret, PASSWORD_BCRYPT),
            'label'      => sanitize_text_field($label),
            'user_id'    => $user_id,
            'scopes'     => $scopes,
            'created_at' => current_time('mysql'),
            'last_used'  => null,
        ];
        $all = get_option(self::OPTION, []);
        $all[] = $record;
        update_option(self::OPTION, $all);
        return ['raw' => $raw, 'record' => $record];
    }

    public function verify(string $raw): ?array {
        if (strpos($raw, self::PREFIX) !== 0) return null;
        $parts = explode('_', substr($raw, strlen(self::PREFIX)), 2);
        if (count($parts) !== 2) return null;
        [$id, $secret] = $parts;
        $all = get_option(self::OPTION, []);
        foreach ($all as $i => $record) {
            if ($record['id'] === $id && password_verify($secret, $record['hash'])) {
                $all[$i]['last_used'] = current_time('mysql');
                update_option(self::OPTION, $all);
                return $record;
            }
        }
        return null;
    }

    public function list_all(): array {
        $all = get_option(self::OPTION, []);
        return array_map(fn($r) => [
            'id'         => $r['id'],
            'label'      => $r['label'],
            'user_id'    => $r['user_id'],
            'scopes'     => $r['scopes'],
            'created_at' => $r['created_at'],
            'last_used'  => $r['last_used'],
        ], $all);
    }

    public function revoke(string $id): bool {
        $all = get_option(self::OPTION, []);
        $filtered = array_values(array_filter($all, fn($r) => $r['id'] !== $id));
        if (count($filtered) === count($all)) return false;
        update_option(self::OPTION, $filtered);
        return true;
    }
}
```

- [ ] **Step 4: Run test, confirm pass**

```bash
composer test -- --filter TestApiKeys
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add wp-plugin/includes/class-api-keys.php wp-plugin/tests/unit/class-test-api-keys.php
git commit -m "feat(plugin): API key generation, verification, revoke"
```

---

## P0.5 — Bearer auth filter

**Files:**
- Create: `wp-plugin/includes/class-auth.php`
- Modify: `wp-plugin/includes/class-plugin.php` (register filter)
- Test: `wp-plugin/tests/unit/class-test-auth.php`

The filter only fires inside our REST namespace and only when the existing auth chain hasn't produced a logged-in user. It looks up the API key, calls `wp_set_current_user($user_id)`, and returns `null` to let the request continue.

- [ ] **Step 1: Write failing test**

`wp-plugin/tests/unit/class-test-auth.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Auth;
use ElementorMCP\Api_Keys;

class TestAuth extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'wp_generate_password' => fn($len, $special = true) => str_repeat('a', $len),
            'current_time'         => 'mysql',
            'sanitize_text_field'  => fn($s) => trim((string)$s),
            'is_wp_error'          => fn($x) => $x instanceof \WP_Error,
        ]);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_passthrough_when_not_our_namespace() {
        $_SERVER['REQUEST_URI']            = '/wp-json/wp/v2/posts';
        $_SERVER['HTTP_AUTHORIZATION']     = 'Bearer emcp_aaaa_bbbb';
        $auth = new Auth(new Api_Keys());
        $this->assertNull($auth->filter(null));
    }

    public function test_passthrough_when_no_bearer_header() {
        $_SERVER['REQUEST_URI'] = '/wp-json/elementor-mcp/v1/health';
        unset($_SERVER['HTTP_AUTHORIZATION']);
        $auth = new Auth(new Api_Keys());
        $this->assertNull($auth->filter(null));
    }

    public function test_returns_wp_error_when_bearer_invalid() {
        $_SERVER['REQUEST_URI']        = '/wp-json/elementor-mcp/v1/health';
        $_SERVER['HTTP_AUTHORIZATION'] = 'Bearer emcp_unknown_secret';
        Functions\expect('get_option')->andReturn([]);
        $auth = new Auth(new Api_Keys());
        $result = $auth->filter(null);
        $this->assertInstanceOf(\WP_Error::class, $result);
        $this->assertSame('emcp_auth_invalid', $result->get_error_code());
    }

    public function test_sets_current_user_on_success() {
        $keys = new Api_Keys();
        Functions\expect('get_option')->andReturn([]);
        Functions\expect('update_option');
        $made = $keys->generate(42, 'agent', []);
        $_SERVER['REQUEST_URI']        = '/wp-json/elementor-mcp/v1/health';
        $_SERVER['HTTP_AUTHORIZATION'] = 'Bearer ' . $made['raw'];
        Functions\expect('get_option')->andReturn([$made['record']]);
        Functions\expect('update_option');
        Functions\expect('wp_set_current_user')->once()->with(42);
        $auth = new Auth($keys);
        $this->assertNull($auth->filter(null));
    }
}
```

Note: this test references `\WP_Error`. Add a minimal stub at the top of `tests/bootstrap.php`:

```php
if (!class_exists('\\WP_Error')) {
    class WP_Error {
        public function __construct(public string $code = '', public string $message = '', public array $data = []) {}
        public function get_error_code()    { return $this->code; }
        public function get_error_message() { return $this->message; }
    }
}
```

- [ ] **Step 2: Run test, confirm fail**

```bash
composer test -- --filter TestAuth
```

- [ ] **Step 3: Implement `wp-plugin/includes/class-auth.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Auth {
    const NAMESPACE = 'elementor-mcp/v1';

    public function __construct(private Api_Keys $keys) {}

    public function filter($result) {
        // Already authenticated by another mechanism — passthrough.
        if (!is_null($result)) return $result;

        $uri = $_SERVER['REQUEST_URI'] ?? '';
        if (strpos($uri, '/wp-json/' . self::NAMESPACE . '/') === false
            && strpos($uri, '/index.php?rest_route=/' . self::NAMESPACE . '/') === false) {
            return null;
        }

        $header = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
        if (stripos($header, 'Bearer ') !== 0) return null;
        $raw = substr($header, 7);

        $record = $this->keys->verify($raw);
        if ($record === null) {
            return new \WP_Error(
                'emcp_auth_invalid',
                'Invalid API key',
                ['status' => 401]
            );
        }

        wp_set_current_user((int) $record['user_id']);
        return null;
    }
}
```

- [ ] **Step 4: Wire into Plugin**

Edit `wp-plugin/includes/class-plugin.php`. Add to `init()`:

```php
public function init(): void {
    add_action('admin_menu', [$this, 'register_admin_menu']);
    add_action('rest_api_init', [$this, 'register_rest_routes']);
    add_filter('rest_authentication_errors',
        [new Auth(new Api_Keys()), 'filter'],
        99
    );
}
```

- [ ] **Step 5: Run test, confirm pass**

```bash
composer test -- --filter TestAuth
```

- [ ] **Step 6: Commit**

```bash
git add wp-plugin/includes/class-auth.php wp-plugin/includes/class-plugin.php wp-plugin/tests/bootstrap.php wp-plugin/tests/unit/class-test-auth.php
git commit -m "feat(plugin): bearer auth filter mapping API key to WP user"
```

---

## P0.6 — REST namespace + `/health` + `/auth/verify`

**Files:**
- Create: `wp-plugin/includes/class-rest-api.php`
- Modify: `wp-plugin/includes/class-plugin.php` (instantiate Rest_Api)
- Test: `wp-plugin/tests/unit/class-test-rest-api.php`

- [ ] **Step 1: Write failing test**

`wp-plugin/tests/unit/class-test-rest-api.php`:

```php
<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Rest_Api;

class TestRestApi extends TestCase {
    protected function setUp(): void { \Brain\Monkey\setUp(); }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_register_routes_calls_register_rest_route_for_health_and_verify() {
        Functions\expect('register_rest_route')
            ->once()
            ->with('elementor-mcp/v1', '/health', \Mockery::type('array'));
        Functions\expect('register_rest_route')
            ->once()
            ->with('elementor-mcp/v1', '/auth/verify', \Mockery::type('array'));
        (new Rest_Api())->register_routes();
    }

    public function test_health_response_has_status_ok() {
        Functions\stubs(['rest_ensure_response' => fn($d) => $d]);
        $body = (new Rest_Api())->health();
        $this->assertSame('ok', $body['data']['status']);
        $this->assertSame('0.0.1', $body['data']['plugin_version']);
        $this->assertTrue($body['ok']);
    }

    public function test_verify_response_returns_current_user_id() {
        Functions\expect('get_current_user_id')->andReturn(42);
        Functions\stubs([
            'rest_ensure_response' => fn($d) => $d,
            'wp_get_current_user'  => fn() => (object)['allcaps' => ['edit_posts' => true]],
        ]);
        $body = (new Rest_Api())->auth_verify();
        $this->assertTrue($body['ok']);
        $this->assertSame(42, $body['data']['user_id']);
        $this->assertSame(['edit_posts'], $body['data']['caps']);
    }
}
```

- [ ] **Step 2: Run test, confirm fail**

```bash
composer test -- --filter TestRestApi
```

- [ ] **Step 3: Implement `wp-plugin/includes/class-rest-api.php`**

```php
<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Rest_Api {
    const NAMESPACE = 'elementor-mcp/v1';

    public function register_routes(): void {
        register_rest_route(self::NAMESPACE, '/health', [
            'methods'             => 'GET',
            'callback'            => [$this, 'health'],
            'permission_callback' => '__return_true',
        ]);
        register_rest_route(self::NAMESPACE, '/auth/verify', [
            'methods'             => 'GET',
            'callback'            => [$this, 'auth_verify'],
            'permission_callback' => fn() => get_current_user_id() > 0,
        ]);
    }

    public function health(): array {
        return $this->envelope(true, [
            'status'         => 'ok',
            'plugin_version' => Plugin::VERSION,
            'elementor'      => defined('ELEMENTOR_VERSION') ? ELEMENTOR_VERSION : null,
        ]);
    }

    public function auth_verify(): array {
        $user = wp_get_current_user();
        $caps = array_keys(array_filter((array)($user->allcaps ?? [])));
        return $this->envelope(true, [
            'user_id' => (int) get_current_user_id(),
            'caps'    => $caps,
            'scopes'  => ['read', 'write'],
        ]);
    }

    private function envelope(bool $ok, $data = null, array $warnings = [], ?array $error = null): array {
        return rest_ensure_response([
            'ok'       => $ok,
            'data'     => $data,
            'warnings' => $warnings,
            'error'    => $error,
        ]);
    }
}
```

- [ ] **Step 4: Wire into Plugin**

Edit `wp-plugin/includes/class-plugin.php`, replace `register_rest_routes` body:

```php
public function register_rest_routes(): void {
    (new Rest_Api())->register_routes();
}
```

- [ ] **Step 5: Run test, confirm pass**

```bash
composer test -- --filter TestRestApi
```

- [ ] **Step 6: Commit**

```bash
git add wp-plugin/includes/class-rest-api.php wp-plugin/includes/class-plugin.php wp-plugin/tests/unit/class-test-rest-api.php
git commit -m "feat(plugin): REST endpoints /health and /auth/verify"
```

---

## P0.7 — wp-env config + manual smoke test

**Files:**
- Create: `.wp-env.json`

- [ ] **Step 1: Create `.wp-env.json`**

```json
{
  "core": "WordPress/WordPress#6.5",
  "phpVersion": "8.1",
  "plugins": [
    "./wp-plugin",
    "https://downloads.wordpress.org/plugin/elementor.zip"
  ],
  "config": {
    "WP_DEBUG": true,
    "WP_DEBUG_LOG": true
  },
  "mappings": {
    "wp-content/uploads": "./.wp-env/uploads"
  },
  "port": 8888,
  "testsPort": 8889
}
```

- [ ] **Step 2: Boot wp-env**

```bash
make wp-up
```

Wait until `http://localhost:8888` returns the WP install page. Activate the plugin:

```bash
npx wp-env run cli wp plugin activate elementor-mcp-bridge
npx wp-env run cli wp plugin activate elementor
```

- [ ] **Step 3: Generate an API key via WP-CLI eval**

```bash
npx wp-env run cli wp eval '
require_once ABSPATH . "wp-content/plugins/elementor-mcp-bridge/elementor-mcp-bridge.php";
$k = (new \ElementorMCP\Api_Keys())->generate(1, "dev", ["read","write"]);
echo $k["raw"];
'
```

Save the printed `emcp_<id>_<secret>`.

- [ ] **Step 4: Manual smoke**

```bash
curl -sf http://localhost:8888/wp-json/elementor-mcp/v1/health
# expect: {"ok":true,"data":{"status":"ok","plugin_version":"0.0.1",...},"warnings":[],"error":null}

curl -sf -H "Authorization: Bearer <PASTE_KEY>" \
  http://localhost:8888/wp-json/elementor-mcp/v1/auth/verify
# expect: {"ok":true,"data":{"user_id":1,"caps":[...],"scopes":["read","write"]},...}
```

If both calls succeed, the WP side is functional.

- [ ] **Step 5: Commit**

```bash
git add .wp-env.json
git commit -m "chore(infra): wp-env config for local dev (Elementor + bridge)"
```

---

## P0.8 — Python: response envelope helpers

**Files:**
- Create: `mcp-server/elementor_mcp/envelope.py`
- Create: `mcp-server/elementor_mcp/errors.py`
- Test: `mcp-server/tests/unit/test_envelope.py`

- [ ] **Step 1: Write failing test**

`mcp-server/tests/unit/test_envelope.py`:

```python
from elementor_mcp.envelope import ToolResult, ok, fail
from elementor_mcp.errors import ErrorCode


def test_ok_envelope_shape():
    r = ok({"x": 1}, warnings=["w"])
    assert r.ok is True
    assert r.data == {"x": 1}
    assert r.warnings == ["w"]
    assert r.error is None
    d = r.model_dump()
    assert d == {"ok": True, "data": {"x": 1}, "warnings": ["w"], "error": None}


def test_fail_envelope_shape():
    r = fail(ErrorCode.E_NO_PROFILE, "no profile yet", fix_hint="create one")
    assert r.ok is False
    assert r.data is None
    assert r.error is not None
    assert r.error.code == "E_NO_PROFILE"
    assert r.error.fix_hint == "create one"


def test_parse_envelope_from_dict():
    r = ToolResult.model_validate({
        "ok": True, "data": {"hello": "world"}, "warnings": [], "error": None
    })
    assert r.data == {"hello": "world"}


def test_error_codes_have_strings():
    assert ErrorCode.E_WP_AUTH.value == "E_WP_AUTH"
    assert ErrorCode.E_WP_UNREACHABLE.value == "E_WP_UNREACHABLE"
```

- [ ] **Step 2: Install deps + run test, confirm fail**

```bash
make mcp-install
cd mcp-server && uv run pytest tests/unit/test_envelope.py -v
```

Expected: `ModuleNotFoundError: elementor_mcp.envelope`.

- [ ] **Step 3: Implement `mcp-server/elementor_mcp/errors.py`**

```python
from enum import Enum


class ErrorCode(str, Enum):
    E_NO_PROFILE       = "E_NO_PROFILE"
    E_WP_AUTH          = "E_WP_AUTH"
    E_WP_UNREACHABLE   = "E_WP_UNREACHABLE"
    E_PAGE_NOT_FOUND   = "E_PAGE_NOT_FOUND"
    E_SECTION_NOT_FOUND= "E_SECTION_NOT_FOUND"
    E_INVALID_JSON     = "E_INVALID_JSON"
    E_TEMPLATE_NOT_FOUND = "E_TEMPLATE_NOT_FOUND"
    E_IMAGE_GEN_FAILED = "E_IMAGE_GEN_FAILED"
    E_NORMALIZE_PARTIAL= "E_NORMALIZE_PARTIAL"
    E_CRAWL_BLOCKED    = "E_CRAWL_BLOCKED"
    E_BACKUP_FAILED    = "E_BACKUP_FAILED"
    E_RESTORE_FAILED   = "E_RESTORE_FAILED"
    E_INTERNAL         = "E_INTERNAL"
```

- [ ] **Step 4: Implement `mcp-server/elementor_mcp/envelope.py`**

```python
from typing import Any

from pydantic import BaseModel

from .errors import ErrorCode


class ToolError(BaseModel):
    code: str
    message: str
    fix_hint: str | None = None


class ToolResult(BaseModel):
    ok: bool
    data: Any = None
    warnings: list[str] = []
    error: ToolError | None = None


def ok(data: Any = None, *, warnings: list[str] | None = None) -> ToolResult:
    return ToolResult(ok=True, data=data, warnings=warnings or [])


def fail(code: ErrorCode, message: str, *, fix_hint: str | None = None) -> ToolResult:
    return ToolResult(
        ok=False,
        error=ToolError(code=code.value, message=message, fix_hint=fix_hint),
    )
```

- [ ] **Step 5: Run test, confirm pass**

```bash
uv run pytest tests/unit/test_envelope.py -v
```

- [ ] **Step 6: Commit**

```bash
git add mcp-server/elementor_mcp/envelope.py mcp-server/elementor_mcp/errors.py mcp-server/tests/unit/test_envelope.py
git commit -m "feat(mcp): tool-result envelope + error codes"
```

---

## P0.9 — Python: config loader

**Files:**
- Create: `mcp-server/elementor_mcp/config.py`
- Test: `mcp-server/tests/unit/test_config.py`

- [ ] **Step 1: Write failing test**

`mcp-server/tests/unit/test_config.py`:

```python
import pytest
from elementor_mcp.config import Settings


def test_loads_from_env(monkeypatch):
    monkeypatch.setenv("WP_URL", "http://wp.local")
    monkeypatch.setenv("WP_API_KEY", "emcp_aaaa_bbbb")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("HTTP_TIMEOUT", "30")
    s = Settings()
    assert str(s.wp_url) == "http://wp.local/"
    assert s.wp_api_key == "emcp_aaaa_bbbb"
    assert s.log_level == "debug"
    assert s.http_timeout == 30


def test_missing_required_raises(monkeypatch):
    monkeypatch.delenv("WP_URL", raising=False)
    monkeypatch.delenv("WP_API_KEY", raising=False)
    with pytest.raises(ValueError):
        Settings(_env_file=None)
```

- [ ] **Step 2: Run test, confirm fail**

```bash
uv run pytest tests/unit/test_config.py -v
```

- [ ] **Step 3: Implement `mcp-server/elementor_mcp/config.py`**

```python
from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    wp_url: HttpUrl
    wp_api_key: str
    log_level: str = "info"
    http_timeout: int = 15


def load() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run test, confirm pass**

```bash
uv run pytest tests/unit/test_config.py -v
```

- [ ] **Step 5: Commit**

```bash
git add mcp-server/elementor_mcp/config.py mcp-server/tests/unit/test_config.py
git commit -m "feat(mcp): pydantic settings loader"
```

---

## P0.10 — Python: WP client wrapper

**Files:**
- Create: `mcp-server/elementor_mcp/core/__init__.py` (empty)
- Create: `mcp-server/elementor_mcp/core/wp_client.py`
- Create: `mcp-server/tests/conftest.py`
- Test: `mcp-server/tests/unit/test_wp_client.py`

- [ ] **Step 1: Write `mcp-server/tests/conftest.py`**

```python
import pytest
from elementor_mcp.config import Settings


@pytest.fixture
def settings():
    return Settings(
        wp_url="http://localhost:8888",
        wp_api_key="emcp_test_key",
        log_level="info",
        http_timeout=5,
    )
```

- [ ] **Step 2: Write failing test**

`mcp-server/tests/unit/test_wp_client.py`:

```python
import pytest
import responses

from elementor_mcp.core.wp_client import WpClient
from elementor_mcp.errors import ErrorCode


@responses.activate
def test_get_returns_envelope_on_success(settings):
    responses.add(
        responses.GET,
        "http://localhost:8888/wp-json/elementor-mcp/v1/health",
        json={"ok": True, "data": {"status": "ok"}, "warnings": [], "error": None},
        status=200,
    )
    client = WpClient(settings)
    res = client.get("/health")
    assert res.ok is True
    assert res.data == {"status": "ok"}


@responses.activate
def test_get_sends_bearer_header(settings):
    responses.add(
        responses.GET,
        "http://localhost:8888/wp-json/elementor-mcp/v1/auth/verify",
        json={"ok": True, "data": {"user_id": 1}, "warnings": [], "error": None},
        status=200,
    )
    WpClient(settings).get("/auth/verify")
    assert "Bearer emcp_test_key" in responses.calls[0].request.headers["Authorization"]


@responses.activate
def test_get_returns_fail_envelope_on_401(settings):
    responses.add(
        responses.GET,
        "http://localhost:8888/wp-json/elementor-mcp/v1/auth/verify",
        json={"code": "emcp_auth_invalid", "message": "Invalid API key"},
        status=401,
    )
    res = WpClient(settings).get("/auth/verify")
    assert res.ok is False
    assert res.error.code == ErrorCode.E_WP_AUTH.value


@responses.activate
def test_get_returns_fail_envelope_on_connection_error(settings):
    res = WpClient(settings).get("/health")
    assert res.ok is False
    assert res.error.code == ErrorCode.E_WP_UNREACHABLE.value
```

- [ ] **Step 3: Run test, confirm fail**

```bash
uv run pytest tests/unit/test_wp_client.py -v
```

- [ ] **Step 4: Implement `mcp-server/elementor_mcp/core/__init__.py`**

```python
```

- [ ] **Step 5: Implement `mcp-server/elementor_mcp/core/wp_client.py`**

```python
from typing import Any

import httpx

from ..config import Settings
from ..envelope import ToolResult, fail, ok
from ..errors import ErrorCode

NAMESPACE = "/wp-json/elementor-mcp/v1"


class WpClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base = str(settings.wp_url).rstrip("/")
        self._http = httpx.Client(
            timeout=settings.http_timeout,
            headers={"Authorization": f"Bearer {settings.wp_api_key}"},
        )

    def _url(self, path: str) -> str:
        return f"{self.base}{NAMESPACE}{path}"

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> ToolResult:
        return self._request("GET", path, params=params)

    def post(self, path: str, *, json: dict[str, Any] | None = None) -> ToolResult:
        return self._request("POST", path, json=json)

    def put(self, path: str, *, json: dict[str, Any] | None = None) -> ToolResult:
        return self._request("PUT", path, json=json)

    def delete(self, path: str) -> ToolResult:
        return self._request("DELETE", path)

    def _request(self, method: str, path: str, **kw: Any) -> ToolResult:
        url = self._url(path)
        try:
            resp = self._http.request(method, url, **kw)
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

        # Plugin always returns an envelope shape; if it doesn't, wrap it.
        if isinstance(body, dict) and "ok" in body:
            return ToolResult.model_validate(body)
        if resp.status_code >= 400:
            return fail(ErrorCode.E_INTERNAL, f"WP error {resp.status_code}: {body}")
        return ok(body)

    def close(self) -> None:
        self._http.close()
```

- [ ] **Step 6: Run test, confirm pass**

```bash
uv run pytest tests/unit/test_wp_client.py -v
```

Expected: 4 tests pass.

- [ ] **Step 7: Commit**

```bash
git add mcp-server/elementor_mcp/core/ mcp-server/tests/conftest.py mcp-server/tests/unit/test_wp_client.py
git commit -m "feat(mcp): WP REST client with bearer auth + envelope normalization"
```

---

## P0.11 — Python: first MCP tool (`auth_verify`)

**Files:**
- Create: `mcp-server/elementor_mcp/tools/__init__.py`
- Create: `mcp-server/elementor_mcp/tools/auth.py`
- Create: `mcp-server/elementor_mcp/server.py`
- Test: `mcp-server/tests/unit/test_tools_auth.py`

The MCP `Skill`-side framing: each tool is an async function decorated/registered with the MCP server. Output is the JSON-serialized `ToolResult`.

- [ ] **Step 1: Write failing test**

`mcp-server/tests/unit/test_tools_auth.py`:

```python
from unittest.mock import MagicMock

from elementor_mcp.envelope import ToolResult, ok
from elementor_mcp.tools.auth import auth_verify


def test_auth_verify_delegates_to_wp_client(settings):
    client = MagicMock()
    client.get.return_value = ok({"user_id": 7, "caps": ["edit_posts"], "scopes": ["read"]})
    result: ToolResult = auth_verify(client)
    client.get.assert_called_once_with("/auth/verify")
    assert result.ok is True
    assert result.data["user_id"] == 7


def test_auth_verify_propagates_failure(settings):
    client = MagicMock()
    from elementor_mcp.envelope import fail
    from elementor_mcp.errors import ErrorCode
    client.get.return_value = fail(ErrorCode.E_WP_AUTH, "Invalid API key")
    result = auth_verify(client)
    assert result.ok is False
    assert result.error.code == "E_WP_AUTH"
```

- [ ] **Step 2: Run test, confirm fail**

```bash
uv run pytest tests/unit/test_tools_auth.py -v
```

- [ ] **Step 3: Implement `mcp-server/elementor_mcp/tools/__init__.py`**

```python
```

- [ ] **Step 4: Implement `mcp-server/elementor_mcp/tools/auth.py`**

```python
from ..core.wp_client import WpClient
from ..envelope import ToolResult


def auth_verify(client: WpClient) -> ToolResult:
    """Verify the WP API key works and return the WP user mapped to it."""
    return client.get("/auth/verify")
```

- [ ] **Step 5: Implement `mcp-server/elementor_mcp/server.py`**

```python
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .config import load
from .core.wp_client import WpClient
from .tools.auth import auth_verify


def build_server() -> Server:
    settings = load()
    client = WpClient(settings)
    server: Server = Server("elementor-mcp")

    @server.list_tools()
    async def _list() -> list[Tool]:
        return [
            Tool(
                name="auth_verify",
                description="Verify the configured WP_API_KEY works. Returns the WP user it maps to.",
                inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
            ),
        ]

    @server.call_tool()
    async def _call(name: str, arguments: dict) -> list[TextContent]:
        if name == "auth_verify":
            result = auth_verify(client)
        else:
            return [TextContent(type="text", text=json.dumps({
                "ok": False,
                "error": {"code": "E_INTERNAL", "message": f"unknown tool: {name}"},
            }))]
        return [TextContent(type="text", text=result.model_dump_json())]

    return server


def main() -> None:
    import asyncio

    async def _run():
        server = build_server()
        async with stdio_server() as (read, write):
            await server.run(
                read,
                write,
                server.create_initialization_options(),
            )

    asyncio.run(_run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run unit test, confirm pass**

```bash
uv run pytest tests/unit/test_tools_auth.py -v
```

- [ ] **Step 7: Manual MCP smoke (optional)**

In a terminal with a `.env` filled and wp-env running:

```bash
cd mcp-server && uv run python -m elementor_mcp.server
# Process should wait on stdin without crashing.
# Ctrl+C to exit.
```

- [ ] **Step 8: Commit**

```bash
git add mcp-server/elementor_mcp/tools/ mcp-server/elementor_mcp/server.py mcp-server/tests/unit/test_tools_auth.py
git commit -m "feat(mcp): auth_verify tool + stdio server entry point"
```

---

## P0.12 — Integration test against wp-env

**Files:**
- Create: `mcp-server/tests/integration/__init__.py`
- Create: `mcp-server/tests/integration/test_auth_verify.py`
- Create: `mcp-server/tests/integration/conftest.py`

This test requires wp-env running and a real API key in env var `EMCP_TEST_API_KEY`. It's skipped if the env vars aren't set, so CI can run it conditionally.

- [ ] **Step 1: Write `mcp-server/tests/integration/conftest.py`**

```python
import os

import pytest

from elementor_mcp.config import Settings


@pytest.fixture
def live_settings():
    api_key = os.environ.get("EMCP_TEST_API_KEY")
    wp_url  = os.environ.get("EMCP_TEST_WP_URL", "http://localhost:8888")
    if not api_key:
        pytest.skip("EMCP_TEST_API_KEY not set — skipping integration test")
    return Settings(
        wp_url=wp_url,
        wp_api_key=api_key,
        log_level="info",
        http_timeout=10,
    )
```

- [ ] **Step 2: Write integration test**

`mcp-server/tests/integration/test_auth_verify.py`:

```python
from elementor_mcp.core.wp_client import WpClient
from elementor_mcp.tools.auth import auth_verify


def test_health_endpoint_reachable(live_settings):
    client = WpClient(live_settings)
    res = client.get("/health")
    assert res.ok is True, res.error
    assert res.data["status"] == "ok"


def test_auth_verify_returns_user_id(live_settings):
    client = WpClient(live_settings)
    res = auth_verify(client)
    assert res.ok is True, res.error
    assert isinstance(res.data["user_id"], int)
    assert res.data["user_id"] > 0
```

- [ ] **Step 3: Run integration test**

```bash
# Generate key (if not already done in P0.7):
KEY=$(npx wp-env run cli wp eval '
require_once ABSPATH . "wp-content/plugins/elementor-mcp-bridge/elementor-mcp-bridge.php";
echo (new \ElementorMCP\Api_Keys())->generate(1, "ci", ["read","write"])["raw"];
' | tr -d '\r')
EMCP_TEST_API_KEY="$KEY" EMCP_TEST_WP_URL="http://localhost:8888" \
  uv run pytest tests/integration -v
```

Expected: both tests pass.

- [ ] **Step 4: Commit**

```bash
git add mcp-server/tests/integration/
git commit -m "test(mcp): integration round-trip against wp-env"
```

---

## P0.13 — CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create the workflow**

```yaml
name: ci

on:
  push:
  pull_request:

jobs:
  mcp:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: mcp-server } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install uv
      - run: uv venv && uv pip install -e ".[dev]"
      - run: uv run ruff check .
      - run: uv run pytest tests/unit -v

  plugin:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: wp-plugin } }
    steps:
      - uses: actions/checkout@v4
      - uses: shivammathur/setup-php@v2
        with:
          php-version: '8.1'
          tools: composer
      - run: composer install --no-interaction --no-progress
      - run: composer test

  integration:
    runs-on: ubuntu-latest
    needs: [mcp, plugin]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: npm i -g @wordpress/env
      - run: wp-env start
      - name: Activate plugins
        run: |
          wp-env run cli wp plugin activate elementor-mcp-bridge
          wp-env run cli wp plugin activate elementor
      - name: Mint API key
        id: keygen
        run: |
          KEY=$(wp-env run cli wp eval '
            require_once ABSPATH . "wp-content/plugins/elementor-mcp-bridge/elementor-mcp-bridge.php";
            echo (new \ElementorMCP\Api_Keys())->generate(1, "ci", ["read","write"])["raw"];
          ' | tr -d '\r\n')
          echo "key=$KEY" >> "$GITHUB_OUTPUT"
      - name: MCP integration
        working-directory: mcp-server
        env:
          EMCP_TEST_API_KEY: ${{ steps.keygen.outputs.key }}
          EMCP_TEST_WP_URL: http://localhost:8888
        run: |
          pip install uv
          uv venv && uv pip install -e ".[dev]"
          uv run pytest tests/integration -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: lint + unit + plugin + integration"
```

- [ ] **Step 3: Push and verify CI green**

```bash
git push origin main
gh run watch
```

Expected: three jobs (`mcp`, `plugin`, `integration`) all green.

---

## P0 Acceptance Criteria (definition of done)

All of the following must hold before declaring Phase 0 complete:

1. `make plugin-install && composer test` — green (≥ 14 unit tests across `TestPlugin`, `TestAdmin`, `TestApiKeys`, `TestAuth`, `TestRestApi`).
2. `make mcp-install && make mcp-test` — green (≥ 11 unit tests across `test_envelope`, `test_config`, `test_wp_client`, `test_tools_auth`).
3. `make wp-up` + activate Elementor + activate bridge → admin page "Elementor MCP" appears in WP admin menu.
4. `curl /wp-json/elementor-mcp/v1/health` returns `{"ok":true,...}` with no auth.
5. With a freshly minted API key, `curl -H 'Authorization: Bearer …' /wp-json/elementor-mcp/v1/auth/verify` returns `{"ok":true, "data":{"user_id":1, …}}`.
6. Same key in `mcp-server/.env`, `uv run pytest tests/integration -v` is green.
7. CI workflow is green on `main`.
8. README documents the 5-command quickstart and it actually works from a fresh clone.

---

## Self-review

**1. Spec coverage (P0 portion of spec):**
- §4 architecture (client/MCP/plugin/DB layers) — Tasks P0.1–P0.13 stand up the skeleton.
- §5.2 options.elementor_mcp_api_keys — Task P0.4.
- §7.1 GET /auth/verify, GET /health — Task P0.6.
- §7.8 authentication flow — Tasks P0.4, P0.5.
- §14.1 tool result envelope — Tasks P0.8.
- §14.2 error codes E_WP_AUTH, E_WP_UNREACHABLE, E_INTERNAL — Tasks P0.8, P0.10.
- §17.1 plugin install steps — README + P0.7.
- §17.2 MCP server install + .env — P0.1.
- §17.3 registering MCP with the agent — covered as a manual step in README only (no automation needed in P0).
- Cache invalidation, profiles, sections, normalizer, library, prototyper, research, import — explicitly OUT of scope for P0. Will appear in P1+ plans.

No P0 gaps.

**2. Placeholder scan:** no TBD/TODO/ "implement later"/ "appropriate error handling" / "similar to Task N" found. Every code step shows actual code.

**3. Type consistency:**
- `Api_Keys::generate` returns `['raw' => string, 'record' => array]` — used identically in P0.4 tests and P0.7 WP-CLI script. ✓
- `Auth` constructor takes `Api_Keys` — `Plugin::init` passes `new Api_Keys()`. ✓
- `Rest_Api::envelope` shape `{ok, data, warnings, error}` matches Python `ToolResult` in `envelope.py`. ✓
- `WpClient.get/post/put/delete` all return `ToolResult`. `auth_verify` consumes `WpClient.get` → `ToolResult` — consistent. ✓
- `ErrorCode.E_WP_AUTH` value `"E_WP_AUTH"` matched in `test_wp_client.test_get_returns_fail_envelope_on_401`. ✓

No issues to fix.

---

## Continuation: Plans P1–P4

When P0 ships and CI is green, request the next plan. Approximate scopes:

| Plan | Title | Spec sections | Tasks (estimated) | Effort |
|---|---|---|---|---|
| 2 | P1 Core MVP — profiles, pages, section CRUD, library Stage B, keyword search, Kit normalizer (six passes + custom_colors overflow), image gen, backup/restore, library admin UI | §3 #10–#14, §5, §6, §7.2–§7.7, §8 (profile, page, section, template, image, library), §9.3–§9.4, §10.1, §11, §12, §15 | ~45 | 2–3 weeks |
| 3 | P2 Prototyper — Stage C AI augment (via Codex task brief), sqlite-vec setup, hybrid search, compose_page (7-step flow), suggest_sections, replace_section, profile auto-derive | §3 #4, §8 prototyper, §9.1, §10.2–§10.4 | ~18 | 1–2 weeks |
| 4 | P3 Research-driven compose — `core/research/` (crawler, brand/voice/layout), Playwright headless, `compose_from_url` | §8 research, §9.2, §13 | ~16 | 1–2 weeks |
| 5 | P4 Library import (HTML + screenshot) — vision-based importers, preview-and-save UI | §12.2 rows 3–4 | ~12 | 1–2 weeks |

Each subsequent plan should be written in this same TDD bite-sized format and saved under `docs/superpowers/plans/`.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-27-elementor-mcp-p0-foundation.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for staying focused across 13 tasks.

2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Best if you want to watch each task in real time.

Which approach?
