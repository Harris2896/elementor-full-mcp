<?php
namespace ElementorMCP\Tests\Unit;

use PHPUnit\Framework\TestCase;
use ElementorMCP\Kit_Writer;

class Kit_WriterTest extends TestCase {
    public function test_translates_profile_to_kit_settings_array() {
        $profile = json_decode(file_get_contents(__DIR__ . '/../fixtures/profile-saas-blue.json'), true);
        $writer  = new Kit_Writer();
        $settings = $writer->build_settings($profile);

        // system colors
        $primary = $this->find_color($settings['system_colors'], 'primary');
        $this->assertSame('#0066FF', $primary['color']);

        // custom colors (the 'muted' entry from profile.colors.custom)
        $muted = $this->find_color($settings['custom_colors'], 'muted');
        $this->assertSame('#9F9F9F', $muted['color']);

        // system typography
        $primaryFont = $this->find_typo($settings['system_typography'], 'primary');
        $this->assertSame('Inter', $primaryFont['typography_font_family']);

        // layout
        $this->assertSame(1290, $settings['container_width']['size']);
        $this->assertSame(80, $settings['space_between_widgets']['top']);

        // breakpoints
        $this->assertSame(767, $settings['viewport_md']);
    }

    public function test_h1_typography_maps_to_kit_h1_settings() {
        $profile = json_decode(file_get_contents(__DIR__ . '/../fixtures/profile-saas-blue.json'), true);
        $settings = (new Kit_Writer())->build_settings($profile);
        $this->assertSame(64,   $settings['h1_typography_font_size']['size']);
        $this->assertSame(36,   $settings['h1_typography_font_size_mobile']['size']);
    }

    private function find_color(array $list, string $id): array {
        foreach ($list as $c) if ($c['_id'] === $id) return $c;
        $this->fail("color '$id' not found");
    }

    private function find_typo(array $list, string $id): array {
        foreach ($list as $t) if ($t['_id'] === $id) return $t;
        $this->fail("typo '$id' not found");
    }
}
