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
        Functions\expect('switch_theme')->once()->with('hello-elementor');
        $bootstrap = new class extends Theme_Bootstrap {
            protected function install_theme_from_api($info): bool { return true; }
        };
        $bootstrap->ensure();
        $this->assertTrue(true);
    }
}
