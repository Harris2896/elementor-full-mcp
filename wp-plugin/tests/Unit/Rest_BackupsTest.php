<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Rest_Backups;
use ElementorMCP\Backup_Store;
use ElementorMCP\Cache_Invalidator;
use ElementorMCP\Page_Lock;

class Rest_BackupsTest extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'rest_ensure_response' => fn($d) => $d,
            'current_user_can'     => fn($c) => true,
            'wp_slash'             => fn($s) => $s,
            'wp_json_encode'       => fn($v) => json_encode($v),
            'current_time'         => fn($_f) => '2026-05-28 10:00:00',
        ]);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_list_returns_summaries() {
        Functions\when('get_post')->justReturn((object)['ID'=>1, 'post_type'=>'page']);
        Functions\when('get_post_meta')->alias(function ($id, $key, $single) {
            if ($key === '_elementor_edit_mode') return 'builder';
            if ($key === '_elementor_data_backup_history') {
                return json_encode([
                    ['version'=>2,'timestamp'=>'b','data'=>[['id'=>'x']]],
                    ['version'=>1,'timestamp'=>'a','data'=>[]],
                ]);
            }
            return '';
        });
        $r = $this->svc()->list($this->req(['id'=>1]));
        $this->assertTrue($r['ok']);
        $this->assertCount(2, $r['data']);
        $this->assertSame(2, $r['data'][0]['version']);
        $this->assertSame(1, $r['data'][0]['sections_count']);
    }

    public function test_restore_replaces_current_with_snapshot_and_snapshots_again() {
        $meta_store = [
            '_elementor_edit_mode' => 'builder',
            '_elementor_data' => '[]',
            '_elementor_data_backup_history' => json_encode([
                ['version'=>1,'timestamp'=>'a','data'=>[['id'=>'old']]],
            ]),
        ];

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

        $r = $this->svc()->restore($this->req(['id'=>1, 'version'=>1]));
        $this->assertTrue($r['ok']);
        $this->assertSame(1, $r['data']['restored_from_version']);
        // _elementor_data was replaced with the snapshot data
        $current = json_decode($meta_store['_elementor_data'], true);
        $this->assertSame('old', $current[0]['id']);
    }

    public function test_restore_returns_404_on_unknown_version() {
        Functions\when('get_transient')->justReturn(false);
        Functions\when('set_transient')->justReturn(true);
        Functions\when('delete_transient')->justReturn(true);
        Functions\when('get_post')->justReturn((object)['ID'=>1, 'post_type'=>'page']);
        Functions\when('get_post_meta')->alias(function ($id, $key, $single) {
            if ($key === '_elementor_edit_mode') return 'builder';
            if ($key === '_elementor_data') return '[]';
            if ($key === '_elementor_data_backup_history') return '[]';
            return '';
        });

        $r = $this->svc()->restore($this->req(['id'=>1, 'version'=>99]));
        $this->assertFalse($r['ok']);
        $this->assertSame('emcp_not_found', $r['error']['code']);
    }

    private function svc(): Rest_Backups {
        return new Rest_Backups(new Backup_Store(), new Cache_Invalidator(), new Page_Lock());
    }

    private function req(array $params) {
        return new class($params) {
            public function __construct(private array $params) {}
            public function get_param($k) { return $this->params[$k] ?? null; }
        };
    }
}
