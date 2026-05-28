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
