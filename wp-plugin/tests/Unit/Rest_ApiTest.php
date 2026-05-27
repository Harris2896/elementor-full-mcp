<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Rest_Api;

class Rest_ApiTest extends TestCase {
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
        $this->assertTrue(true);
    }

    public function test_health_response_has_status_ok() {
        Functions\when('rest_ensure_response')->alias(fn($d) => $d);
        $body = (new Rest_Api())->health();
        $this->assertSame('ok', $body['data']['status']);
        $this->assertSame('0.0.1', $body['data']['plugin_version']);
        $this->assertTrue($body['ok']);
    }

    public function test_verify_response_returns_current_user_id() {
        Functions\when('get_current_user_id')->justReturn(42);
        Functions\when('rest_ensure_response')->alias(fn($d) => $d);
        Functions\when('wp_get_current_user')->alias(fn() => (object)['allcaps' => ['edit_posts' => true, 'do_nothing' => false]]);
        $body = (new Rest_Api())->auth_verify();
        $this->assertTrue($body['ok']);
        $this->assertSame(42, $body['data']['user_id']);
        $this->assertSame(['edit_posts'], $body['data']['caps']);
    }
}
