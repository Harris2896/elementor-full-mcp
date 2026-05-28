<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Backup_Store;

class Backup_StoreTest extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'current_time'   => fn($_f) => '2026-05-28 10:00:00',
            'wp_json_encode' => fn($v) => json_encode($v),
        ]);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_snapshot_adds_entry_with_incremented_version() {
        $store_meta = [];
        Functions\when('get_post_meta')->alias(function ($pid, $key, $single) use (&$store_meta) {
            return $store_meta[$key] ?? '';
        });
        Functions\when('update_post_meta')->alias(function ($pid, $key, $value) use (&$store_meta) {
            $store_meta[$key] = $value; return true;
        });

        $store = new Backup_Store();
        $store->snapshot(1, [['id'=>'a']]);
        $store->snapshot(1, [['id'=>'a'], ['id'=>'b']]);
        $hist = $store->list(1);
        $this->assertCount(2, $hist);
        $this->assertSame(2, $hist[0]['version']);
        $this->assertSame(1, $hist[1]['version']);
    }

    public function test_snapshot_caps_at_5_entries() {
        $store_meta = [];
        Functions\when('get_post_meta')->alias(function ($pid, $key, $single) use (&$store_meta) {
            return $store_meta[$key] ?? '';
        });
        Functions\when('update_post_meta')->alias(function ($pid, $key, $value) use (&$store_meta) {
            $store_meta[$key] = $value; return true;
        });

        $store = new Backup_Store();
        for ($i = 0; $i < 7; $i++) $store->snapshot(1, [['id' => "v$i"]]);
        $hist = $store->list(1);
        $this->assertCount(5, $hist);
        $this->assertSame(7, $hist[0]['version']);
        $this->assertSame(3, $hist[4]['version']);
    }

    public function test_get_returns_specific_version() {
        $store_meta = [];
        Functions\when('get_post_meta')->alias(function ($pid, $key, $single) use (&$store_meta) {
            return $store_meta[$key] ?? '';
        });
        Functions\when('update_post_meta')->alias(function($pid,$key,$v) use (&$store_meta){
            $store_meta[$key]=$v; return true;
        });
        $store = new Backup_Store();
        $store->snapshot(1, [['id'=>'first']]);
        $store->snapshot(1, [['id'=>'second']]);
        $entry = $store->get(1, 1);
        $this->assertSame('first', $entry['data'][0]['id']);
    }

    public function test_get_returns_null_for_missing_version() {
        Functions\when('get_post_meta')->justReturn('');
        $this->assertNull((new Backup_Store())->get(1, 99));
    }
}
