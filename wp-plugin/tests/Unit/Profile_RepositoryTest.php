<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Profile_Repository;

class Profile_RepositoryTest extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'sanitize_text_field' => fn($s) => trim((string)$s),
            'wp_slash'            => fn($s) => $s,
            'wp_unslash'          => fn($s) => $s,
            'wp_json_encode'      => fn($v) => json_encode($v),
        ]);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_create_inserts_post_and_meta() {
        Functions\stubs(['is_wp_error' => fn($x) => $x instanceof \WP_Error]);
        $data = ['name' => 'SaaS-blue', 'colors' => []];
        Functions\expect('wp_insert_post')->once()
            ->with(\Mockery::on(function ($args) {
                return $args['post_type'] === 'emcp_profile'
                    && $args['post_title'] === 'SaaS-blue'
                    && $args['post_status'] === 'publish';
            }))
            ->andReturn(101);
        Functions\expect('update_post_meta')->once()
            ->with(101, '_emcp_profile_data', \Mockery::on(fn($s) => is_string($s) && json_decode($s, true) === $data));
        $id = (new Profile_Repository())->create($data);
        $this->assertSame(101, $id);
    }

    public function test_get_returns_null_when_post_not_found() {
        Functions\expect('get_post')->once()->with(404)->andReturn(null);
        $this->assertNull((new Profile_Repository())->get(404));
    }

    public function test_get_returns_decoded_data() {
        Functions\expect('get_post')->once()->with(7)
            ->andReturn((object)['ID' => 7, 'post_type' => 'emcp_profile', 'post_title' => 'X']);
        Functions\expect('get_post_meta')->once()
            ->with(7, '_emcp_profile_data', true)
            ->andReturn('{"name":"X","colors":{}}');
        $r = (new Profile_Repository())->get(7);
        $this->assertSame(7, $r['id']);
        $this->assertSame('X', $r['data']['name']);
    }

    public function test_update_replaces_postmeta() {
        Functions\stubs(['is_wp_error' => fn($x) => $x instanceof \WP_Error]);
        $data = ['name' => 'New', 'colors' => []];
        Functions\expect('get_post')->once()->with(8)
            ->andReturn((object)['ID' => 8, 'post_type' => 'emcp_profile']);
        Functions\expect('wp_update_post')->once()->with(\Mockery::on(function ($args) {
            return $args['ID'] === 8 && $args['post_title'] === 'New';
        }))->andReturn(8);
        Functions\expect('update_post_meta')->once()
            ->with(8, '_emcp_profile_data', \Mockery::on(fn($s) => is_string($s) && json_decode($s, true) === $data));
        $ok = (new Profile_Repository())->update(8, $data);
        $this->assertTrue($ok);
    }

    public function test_create_throws_when_wp_insert_post_returns_wp_error() {
        Functions\stubs(['is_wp_error' => fn($x) => $x instanceof \WP_Error]);
        Functions\expect('wp_insert_post')->once()->andReturn(new \WP_Error('db_error', 'fail'));
        $this->expectException(\RuntimeException::class);
        (new \ElementorMCP\Profile_Repository())->create(['name' => 'X', 'colors' => []]);
    }

    public function test_update_returns_false_when_wp_update_post_errors() {
        Functions\stubs(['is_wp_error' => fn($x) => $x instanceof \WP_Error]);
        Functions\expect('get_post')->once()->with(8)
            ->andReturn((object)['ID' => 8, 'post_type' => 'emcp_profile']);
        Functions\expect('wp_update_post')->once()->andReturn(new \WP_Error('db_error', 'fail'));
        Functions\expect('update_post_meta')->never();
        $this->assertFalse((new \ElementorMCP\Profile_Repository())->update(8, ['name' => 'New']));
    }

    public function test_update_returns_false_for_wrong_post_type() {
        Functions\expect('get_post')->once()->with(9)
            ->andReturn((object)['ID' => 9, 'post_type' => 'post']);
        $this->assertFalse((new Profile_Repository())->update(9, ['name' => 'x']));
    }

    public function test_delete_only_works_on_profile_post() {
        Functions\expect('get_post')->once()->with(10)
            ->andReturn((object)['ID' => 10, 'post_type' => 'emcp_profile']);
        Functions\expect('wp_delete_post')->once()->with(10, true)->andReturn((object)[]);
        $this->assertTrue((new Profile_Repository())->delete(10));
    }

    public function test_list_returns_array_of_summaries() {
        Functions\expect('get_posts')->once()
            ->with(\Mockery::on(fn($a) => $a['post_type'] === 'emcp_profile'))
            ->andReturn([
                (object)['ID' => 1, 'post_title' => 'A', 'post_date_gmt' => '2026-05-28 00:00:00'],
                (object)['ID' => 2, 'post_title' => 'B', 'post_date_gmt' => '2026-05-28 01:00:00'],
            ]);
        $list = (new Profile_Repository())->list();
        $this->assertCount(2, $list);
        $this->assertSame('A', $list[0]['name']);
    }
}
