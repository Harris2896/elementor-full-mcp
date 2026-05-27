<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Auth;
use ElementorMCP\Api_Keys;

class AuthTest extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'wp_generate_password' => fn($len, $special = true, $extra = false) => str_repeat('a', $len),
            'current_time'         => fn($_format) => '2026-05-27 12:00:00',
            'sanitize_text_field'  => fn($s) => trim((string)$s),
            'is_wp_error'          => fn($x) => $x instanceof \WP_Error,
        ]);
    }
    protected function tearDown(): void {
        \Brain\Monkey\tearDown();
        unset($_SERVER['REQUEST_URI'], $_SERVER['HTTP_AUTHORIZATION']);
    }

    public function test_passthrough_when_not_our_namespace() {
        $_SERVER['REQUEST_URI']        = '/wp-json/wp/v2/posts';
        $_SERVER['HTTP_AUTHORIZATION'] = 'Bearer emcp_aaaa_bbbb';
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
        Functions\when('get_option')->justReturn([]);
        $auth = new Auth(new Api_Keys());
        $result = $auth->filter(null);
        $this->assertInstanceOf(\WP_Error::class, $result);
        $this->assertSame('emcp_auth_invalid', $result->get_error_code());
    }

    public function test_sets_current_user_on_success() {
        $store = [];
        Functions\when('get_option')->alias(function ($_k, $default = []) use (&$store) { return $store; });
        Functions\when('update_option')->alias(function ($_k, $v) use (&$store) {
            $store = $v; return true;
        });

        $keys = new Api_Keys();
        $made = $keys->generate(42, 'agent', []);

        $_SERVER['REQUEST_URI']        = '/wp-json/elementor-mcp/v1/health';
        $_SERVER['HTTP_AUTHORIZATION'] = 'Bearer ' . $made['raw'];

        Functions\expect('wp_set_current_user')->once()->with(42);
        $auth = new Auth($keys);
        $this->assertNull($auth->filter(null));
    }

    public function test_passthrough_when_already_authenticated() {
        $_SERVER['REQUEST_URI'] = '/wp-json/elementor-mcp/v1/health';
        $_SERVER['HTTP_AUTHORIZATION'] = 'Bearer emcp_aaaa_bbbb';
        $auth = new Auth(new Api_Keys());
        // Pre-authed (e.g., a cookie session) → upstream value passes through
        $this->assertTrue($auth->filter(true));
    }
}
