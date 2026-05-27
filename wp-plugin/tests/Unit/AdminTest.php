<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Admin;

class AdminTest extends TestCase {
    protected function setUp(): void { \Brain\Monkey\setUp(); }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_register_menu_adds_top_level_page() {
        Functions\expect('add_menu_page')
            ->once()
            ->with('Elementor MCP', 'Elementor MCP', 'manage_options', 'elementor-mcp', \Mockery::type('callable'), 'dashicons-art', 81);
        (new Admin())->register_menu();
        $this->assertTrue(true);
    }
}
