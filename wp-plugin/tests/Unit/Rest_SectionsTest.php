<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Rest_Sections;
use ElementorMCP\Section_Parser;
use ElementorMCP\Backup_Store;
use ElementorMCP\Cache_Invalidator;
use ElementorMCP\Page_Lock;

class Rest_SectionsTest extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'rest_ensure_response' => fn($d) => $d,
            'current_user_can'     => fn($c) => true,
            'sanitize_text_field'  => fn($s) => trim((string)$s),
            'wp_slash'             => fn($s) => $s,
            'wp_json_encode'       => fn($v) => json_encode($v),
            'current_time'         => fn($_f) => '2026-05-28 10:00:00',
        ]);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_list_returns_summaries() {
        $sample = json_decode(file_get_contents(__DIR__ . '/../fixtures/elementor-data-sample.json'), true);
        Functions\when('get_post')->justReturn((object)['ID'=>1, 'post_type'=>'page']);
        Functions\when('get_post_meta')->alias(function ($id, $key, $single) use ($sample) {
            if ($key === '_elementor_edit_mode') return 'builder';
            if ($key === '_elementor_data') return json_encode($sample);
            return '';
        });
        $r = $this->svc()->list($this->req(['id' => 1]));
        $this->assertTrue($r['ok']);
        $this->assertCount(2, $r['data']);
    }

    public function test_add_snapshots_before_writing_and_clears_cache() {
        $sample = json_decode(file_get_contents(__DIR__ . '/../fixtures/elementor-data-sample.json'), true);
        $meta_store = ['_elementor_edit_mode' => 'builder', '_elementor_data' => json_encode($sample), '_elementor_data_backup_history' => ''];

        Functions\when('get_transient')->justReturn(false);  // lock open
        Functions\when('set_transient')->justReturn(true);
        Functions\when('delete_transient')->justReturn(true);
        Functions\when('get_post')->justReturn((object)['ID'=>1, 'post_type'=>'page']);
        Functions\when('get_post_meta')->alias(function ($id, $key, $single) use (&$meta_store) {
            return $meta_store[$key] ?? '';
        });
        Functions\when('update_post_meta')->alias(function ($id, $key, $value) use (&$meta_store) {
            $meta_store[$key] = $value; return true;
        });
        Functions\expect('delete_post_meta')->once()->with(1, '_elementor_css');

        $body = ['json' => ['id' => 'new1', 'elType' => 'section', 'settings' => [], 'elements' => []]];
        $r = $this->svc()->add($this->req(['id' => 1], $body));
        $this->assertTrue($r['ok']);
        $this->assertSame('new1', $r['data']['sid']);
        // Backup was created
        $hist = json_decode($meta_store['_elementor_data_backup_history'], true);
        $this->assertCount(1, $hist);
    }

    public function test_add_returns_locked_when_lock_unavailable() {
        Functions\when('get_transient')->justReturn('someone-else');  // already locked
        $body = ['json' => ['id' => 'x', 'elType' => 'section', 'settings' => [], 'elements' => []]];
        $r = $this->svc()->add($this->req(['id' => 1], $body));
        $this->assertFalse($r['ok']);
        $this->assertSame('emcp_locked', $r['error']['code']);
    }

    public function test_delete_removes_section_and_saves() {
        $sample = json_decode(file_get_contents(__DIR__ . '/../fixtures/elementor-data-sample.json'), true);
        $meta_store = ['_elementor_edit_mode' => 'builder', '_elementor_data' => json_encode($sample), '_elementor_data_backup_history' => ''];

        Functions\when('get_transient')->justReturn(false);
        Functions\when('set_transient')->justReturn(true);
        Functions\when('delete_transient')->justReturn(true);
        Functions\when('get_post')->justReturn((object)['ID'=>1, 'post_type'=>'page']);
        Functions\when('get_post_meta')->alias(function ($id, $key, $single) use (&$meta_store) {
            return $meta_store[$key] ?? '';
        });
        Functions\when('update_post_meta')->alias(function ($id, $key, $value) use (&$meta_store) {
            $meta_store[$key] = $value; return true;
        });
        Functions\expect('delete_post_meta')->once()->with(1, '_elementor_css');

        $r = $this->svc()->delete($this->req(['id' => 1, 'sid' => '44b1bea6']));
        $this->assertTrue($r['ok']);
        // Verify section was actually removed
        $saved = json_decode($meta_store['_elementor_data'], true);
        $this->assertCount(1, $saved);
        $this->assertSame('abc12345', $saved[0]['id']);
    }

    private function svc(): Rest_Sections {
        return new Rest_Sections(
            new Section_Parser(),
            new Backup_Store(),
            new Cache_Invalidator(),
            new Page_Lock(),
        );
    }

    private function req(array $params, $body = null) {
        return new class($params, $body) {
            public function __construct(private array $params, private $body) {}
            public function get_param($k) { return $this->params[$k] ?? null; }
            public function get_json_params() { return $this->body; }
        };
    }
}
