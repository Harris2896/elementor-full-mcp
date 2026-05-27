<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Rest_Pages;

class Rest_PagesTest extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'rest_ensure_response' => fn($d) => $d,
            'current_user_can'     => fn($c) => true,
            'sanitize_text_field'  => fn($s) => trim((string)$s),
            'admin_url'            => fn($p) => "http://wp.local/wp-admin/{$p}",
            'is_wp_error'          => fn($x) => $x instanceof \WP_Error,
        ]);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_list_returns_only_elementor_pages() {
        Functions\expect('get_posts')->once()
            ->with(\Mockery::on(fn($a) =>
                $a['meta_key'] === '_elementor_edit_mode'
                && $a['meta_value'] === 'builder'
            ))
            ->andReturn([
                (object)['ID' => 10, 'post_title' => 'Home', 'post_status' => 'publish'],
            ]);
        Functions\expect('get_permalink')->andReturn('http://x/home');
        Functions\expect('get_post_meta')->andReturn('[]'); // sections count = 0
        $r = (new Rest_Pages())->list($this->req([]));
        $this->assertTrue($r['ok']);
        $this->assertSame('Home', $r['data'][0]['title']);
    }

    public function test_create_inserts_page_with_elementor_meta() {
        Functions\expect('wp_insert_post')->once()->with(\Mockery::on(function ($args) {
            return $args['post_type'] === 'page' && $args['post_title'] === 'Landing';
        }))->andReturn(33);
        Functions\expect('update_post_meta')->once()->with(33, '_elementor_edit_mode', 'builder');
        Functions\expect('update_post_meta')->once()->with(33, '_elementor_template_type', 'wp-page');
        Functions\expect('update_post_meta')->once()->with(33, '_elementor_data', '[]');
        Functions\expect('get_permalink')->andReturn('http://x/landing');
        $req = $this->req([], ['title' => 'Landing']);
        $r = (new Rest_Pages())->create($req);
        $this->assertTrue($r['ok']);
        $this->assertSame(33, $r['data']['id']);
    }

    public function test_create_returns_500_on_wp_insert_post_error() {
        Functions\expect('wp_insert_post')->once()
            ->andReturn(new \WP_Error('db_err', 'insert failed'));
        $req = $this->req([], ['title' => 'X']);
        $r = (new Rest_Pages())->create($req);
        $this->assertFalse($r['ok']);
        $this->assertSame('emcp_internal', $r['error']['code']);
    }

    public function test_get_returns_page_meta_and_sections_count() {
        Functions\expect('get_post')->with(7)
            ->andReturn((object)['ID' => 7, 'post_type' => 'page', 'post_title' => 'T', 'post_status' => 'publish']);
        Functions\expect('get_post_meta')->andReturnUsing(function ($id, $key, $single) {
            if ($key === '_elementor_edit_mode') return 'builder';
            if ($key === '_elementor_data')      return json_encode([['id'=>'a'], ['id'=>'b']]);
            return '';
        });
        Functions\expect('get_permalink')->andReturn('http://x/t');
        $r = (new Rest_Pages())->get($this->req(['id' => 7]));
        $this->assertTrue($r['ok']);
        $this->assertSame(2, $r['data']['sections_count']);
    }

    public function test_get_returns_404_for_non_elementor_post() {
        Functions\expect('get_post')->with(8)
            ->andReturn((object)['ID' => 8, 'post_type' => 'page']);
        Functions\expect('get_post_meta')->with(8, '_elementor_edit_mode', true)->andReturn('');
        $r = (new Rest_Pages())->get($this->req(['id' => 8]));
        $this->assertFalse($r['ok']);
        $this->assertSame('emcp_not_found', $r['error']['code']);
    }

    public function test_delete_removes_page() {
        Functions\expect('get_post')->with(9)
            ->andReturn((object)['ID' => 9, 'post_type' => 'page']);
        Functions\expect('get_post_meta')->with(9, '_elementor_edit_mode', true)->andReturn('builder');
        Functions\expect('wp_delete_post')->once()->with(9, true)->andReturn((object)[]);
        $r = (new Rest_Pages())->delete($this->req(['id' => 9]));
        $this->assertTrue($r['ok']);
    }

    private function req(array $params, $body = null) {
        return new class($params, $body) {
            public function __construct(private array $params, private $body) {}
            public function get_param($k) { return $this->params[$k] ?? null; }
            public function get_json_params() { return $this->body; }
        };
    }
}
