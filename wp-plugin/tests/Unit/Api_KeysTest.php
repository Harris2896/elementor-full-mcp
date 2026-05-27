<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Api_Keys;

class Api_KeysTest extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'wp_generate_password' => function ($len, $special = true, $extra = false) {
                // Deterministic — return distinguishable string per length
                return str_repeat('a', $len);
            },
            'current_time'         => fn($_format) => '2026-05-27 12:00:00',
            'sanitize_text_field'  => fn($s) => trim((string)$s),
        ]);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_generate_returns_raw_key_with_prefix() {
        Functions\when('get_option')->justReturn([]);
        Functions\when('update_option')->justReturn(true);
        $result = (new Api_Keys())->generate(1, 'dev', ['read', 'write']);
        $this->assertStringStartsWith('emcp_', $result['raw']);
        $this->assertSame(1, $result['record']['user_id']);
        $this->assertSame('dev', $result['record']['label']);
    }

    public function test_verify_accepts_correct_key() {
        $store = [];
        Functions\when('get_option')->alias(function ($_k, $default = []) use (&$store) { return $store; });
        Functions\when('update_option')->alias(function ($_k, $v) use (&$store) {
            $store = $v; return true;
        });

        $svc = new Api_Keys();
        $made = $svc->generate(7, 'agent', ['read']);
        $raw = $made['raw'];

        $record = $svc->verify($raw);
        $this->assertNotNull($record);
        $this->assertSame(7, $record['user_id']);
    }

    public function test_verify_rejects_wrong_secret() {
        $store = [];
        Functions\when('get_option')->alias(function ($_k, $default = []) use (&$store) { return $store; });
        Functions\when('update_option')->alias(function ($_k, $v) use (&$store) {
            $store = $v; return true;
        });

        $svc = new Api_Keys();
        $made = $svc->generate(1, 'x', []);
        $tampered = preg_replace('/.$/', 'X', $made['raw']);
        $this->assertNull($svc->verify($tampered));
    }

    public function test_verify_rejects_unknown_id() {
        Functions\when('get_option')->justReturn([]);
        $this->assertNull((new Api_Keys())->verify('emcp_unknownid12_secret'));
    }

    public function test_verify_rejects_malformed_key() {
        $this->assertNull((new Api_Keys())->verify('not_a_key'));
    }
}
