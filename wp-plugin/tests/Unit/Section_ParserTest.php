<?php
namespace ElementorMCP\Tests\Unit;

use PHPUnit\Framework\TestCase;
use ElementorMCP\Section_Parser;

class Section_ParserTest extends TestCase {
    private function sample(): array {
        return json_decode(file_get_contents(__DIR__ . '/../fixtures/elementor-data-sample.json'), true);
    }

    public function test_list_returns_flat_summaries() {
        $list = (new Section_Parser())->list($this->sample());
        $this->assertCount(2, $list);
        $this->assertSame('44b1bea6', $list[0]['sid']);
        $this->assertSame('Hero', $list[0]['title']);
        $this->assertSame(['heading'], $list[0]['widgets']);
    }

    public function test_list_uses_widget_summary_when_no_title() {
        $list = (new Section_Parser())->list($this->sample());
        $this->assertSame('abc12345', $list[1]['sid']);
        $this->assertSame('Untitled', $list[1]['title']);
        $this->assertSame(['image', 'button'], $list[1]['widgets']);
    }

    public function test_get_section_by_id() {
        $section = (new Section_Parser())->get($this->sample(), '44b1bea6');
        $this->assertNotNull($section);
        $this->assertSame('Hero', $section['settings']['_title']);
    }

    public function test_get_returns_null_for_unknown_id() {
        $this->assertNull((new Section_Parser())->get($this->sample(), 'nope'));
    }

    public function test_add_appends_at_default_position() {
        $data = $this->sample();
        $new = ['id' => 'new1', 'elType' => 'section', 'settings' => [], 'elements' => []];
        $result = (new Section_Parser())->add($data, $new);
        $this->assertSame('new1', $result[2]['id']);
    }

    public function test_add_inserts_at_given_position() {
        $data = $this->sample();
        $new = ['id' => 'between', 'elType' => 'section', 'settings' => [], 'elements' => []];
        $result = (new Section_Parser())->add($data, $new, 1);
        $this->assertSame('44b1bea6', $result[0]['id']);
        $this->assertSame('between',  $result[1]['id']);
        $this->assertSame('abc12345', $result[2]['id']);
    }

    public function test_replace_updates_in_place() {
        $data = $this->sample();
        $replaced = ['id' => '44b1bea6', 'elType' => 'section', 'settings' => ['_title' => 'New'], 'elements' => []];
        $result = (new Section_Parser())->replace($data, '44b1bea6', $replaced);
        $this->assertSame('New', $result[0]['settings']['_title']);
        $this->assertCount(2, $result);
    }

    public function test_delete_removes_by_id() {
        $result = (new Section_Parser())->delete($this->sample(), '44b1bea6');
        $this->assertCount(1, $result);
        $this->assertSame('abc12345', $result[0]['id']);
    }

    public function test_duplicate_inserts_after_with_new_id() {
        $result = (new Section_Parser())->duplicate($this->sample(), '44b1bea6');
        $this->assertCount(3, $result);
        $this->assertSame('44b1bea6', $result[0]['id']);
        $this->assertNotSame('44b1bea6', $result[1]['id']);
        $this->assertSame('Hero', $result[1]['settings']['_title']);
    }

    public function test_reorder_rearranges() {
        $result = (new Section_Parser())->reorder($this->sample(), ['abc12345', '44b1bea6']);
        $this->assertSame('abc12345', $result[0]['id']);
        $this->assertSame('44b1bea6', $result[1]['id']);
    }

    public function test_reorder_rejects_mismatched_set() {
        $this->expectException(\InvalidArgumentException::class);
        (new Section_Parser())->reorder($this->sample(), ['44b1bea6']);  // missing one
    }

    public function test_replace_preserves_existing_eltype_when_input_missing() {
        $data = $this->sample();
        $patch = ['id' => '44b1bea6', 'settings' => ['_title' => 'New'], 'elements' => []];
        $result = (new Section_Parser())->replace($data, '44b1bea6', $patch);
        $this->assertSame('section', $result[0]['elType']);
        $this->assertSame('New', $result[0]['settings']['_title']);
    }

    public function test_list_includes_container_eltype() {
        $data = json_decode(file_get_contents(__DIR__ . '/../fixtures/elementor-data-container-mix.json'), true);
        $list = (new Section_Parser())->list($data);
        $this->assertSame('section',   $list[0]['el_type']);
        $this->assertSame('container', $list[1]['el_type']);
        $this->assertSame('section',   $list[2]['el_type']);
    }

    public function test_prune_orphans_removes_duplicate_titles_with_different_eltypes() {
        $data = json_decode(file_get_contents(__DIR__ . '/../fixtures/elementor-data-container-mix.json'), true);
        $result = (new Section_Parser())->prune_orphans($data);
        // The container with the same _title='Hero' as the section should be removed.
        $this->assertCount(2, $result);
        $this->assertSame('44b1bea6', $result[0]['id']);
        $this->assertSame('feedface', $result[1]['id']);
    }
}
