<?php
namespace ElementorMCP\Tests\Unit;

use PHPUnit\Framework\TestCase;
use ElementorMCP\Profile_Schema;

class Profile_SchemaTest extends TestCase {
    public function test_valid_profile_accepted() {
        $json = file_get_contents(__DIR__ . '/../fixtures/profile-saas-blue.json');
        $data = json_decode($json, true);
        $result = (new Profile_Schema())->validate($data);
        $this->assertTrue($result['ok']);
        $this->assertSame([], $result['errors']);
    }

    public function test_missing_name_rejected() {
        $data = ['colors' => []];
        $result = (new Profile_Schema())->validate($data);
        $this->assertFalse($result['ok']);
        $this->assertContains("missing required field 'name'", $result['errors']);
    }

    public function test_invalid_hex_color_rejected() {
        $data = $this->valid();
        $data['colors']['primary'] = 'not-a-color';
        $result = (new Profile_Schema())->validate($data);
        $this->assertFalse($result['ok']);
        $this->assertContains("invalid hex color for colors.primary: 'not-a-color'", $result['errors']);
    }

    public function test_negative_typography_size_rejected() {
        $data = $this->valid();
        $data['typography']['h1']['size'] = -5;
        $result = (new Profile_Schema())->validate($data);
        $this->assertFalse($result['ok']);
        $this->assertContains("typography.h1.size must be > 0", $result['errors']);
    }

    public function test_unknown_top_level_keys_warn_but_not_fail() {
        $data = $this->valid();
        $data['mystery_field'] = 'hello';
        $result = (new Profile_Schema())->validate($data);
        $this->assertTrue($result['ok']);
        $this->assertContains("unknown field at top level: 'mystery_field'", $result['warnings']);
    }

    public function test_non_array_colors_rejected() {
        $data = $this->valid();
        $data['colors'] = 'red';
        $result = (new Profile_Schema())->validate($data);
        $this->assertFalse($result['ok']);
        $this->assertContains("colors must be an object", $result['errors']);
    }

    public function test_non_array_typography_level_rejected() {
        $data = $this->valid();
        $data['typography']['h1'] = 'huge';
        $result = (new Profile_Schema())->validate($data);
        $this->assertFalse($result['ok']);
        $this->assertContains("typography.h1 must be an object", $result['errors']);
    }

    private function valid(): array {
        return json_decode(file_get_contents(__DIR__ . '/../fixtures/profile-saas-blue.json'), true);
    }
}
