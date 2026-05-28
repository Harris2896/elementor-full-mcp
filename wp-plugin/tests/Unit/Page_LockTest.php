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
