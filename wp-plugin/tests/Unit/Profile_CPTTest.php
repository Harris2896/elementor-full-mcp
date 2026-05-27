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
