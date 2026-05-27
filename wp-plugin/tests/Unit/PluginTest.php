<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Plugin;

class PluginTest extends TestCase {
    protected function setUp(): void { \Brain\Monkey\setUp(); }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_singleton_returns_same_instance() {
        $a = Plugin::instance();
        $b = Plugin::instance();
        $this->assertSame($a, $b);
    }

    public function test_init_registers_admin_menu_action() {
        Functions\expect('add_action')->atLeast()->once();
        Functions\expect('add_filter')->atLeast()->once();
        Plugin::instance()->init();
        $this->assertTrue(true);
    }

    public function test_version_is_string() {
        $this->assertIsString(Plugin::VERSION);
    }
}
