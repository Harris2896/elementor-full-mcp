<?php
namespace ElementorMCP\Tests\Unit;

use Brain\Monkey\Functions;
use PHPUnit\Framework\TestCase;
use ElementorMCP\Rest_Profiles;
use ElementorMCP\Profile_Repository;
use ElementorMCP\Profile_Schema;
use ElementorMCP\Kit_Writer;

class Rest_ProfilesTest extends TestCase {
    protected function setUp(): void {
        \Brain\Monkey\setUp();
        Functions\stubs([
            'rest_ensure_response' => fn($d) => $d,
            'current_user_can'     => fn($c) => true,
        ]);
    }
    protected function tearDown(): void { \Brain\Monkey\tearDown(); }

    public function test_list_returns_envelope_with_profiles() {
        $repo = $this->createMock(Profile_Repository::class);
        $repo->method('list')->willReturn([['id'=>1,'name'=>'A','created_at'=>null]]);
        $r = (new Rest_Profiles($repo, new Profile_Schema(), new Kit_Writer()))->list();
        $this->assertTrue($r['ok']);
        $this->assertCount(1, $r['data']);
    }

    public function test_get_returns_404_envelope_when_missing() {
        $repo = $this->createMock(Profile_Repository::class);
        $repo->method('get')->with(99)->willReturn(null);
        $req = $this->req(['id' => 99]);
        $r = (new Rest_Profiles($repo, new Profile_Schema(), new Kit_Writer()))->get($req);
        $this->assertFalse($r['ok']);
        $this->assertSame('emcp_not_found', $r['error']['code']);
    }

    public function test_create_validates_and_persists() {
        $repo = $this->createMock(Profile_Repository::class);
        $repo->expects($this->once())->method('create')->willReturn(42);
        $valid = json_decode(file_get_contents(__DIR__ . '/../fixtures/profile-saas-blue.json'), true);
        $req = $this->req([], $valid);
        $r = (new Rest_Profiles($repo, new Profile_Schema(), new Kit_Writer()))->create($req);
        $this->assertTrue($r['ok']);
        $this->assertSame(42, $r['data']['id']);
    }

    public function test_create_rejects_invalid_payload() {
        $repo = $this->createMock(Profile_Repository::class);
        $repo->expects($this->never())->method('create');
        $bad = ['name' => 'X', 'colors' => ['primary' => 'not-hex']];
        $req = $this->req([], $bad);
        $r = (new Rest_Profiles($repo, new Profile_Schema(), new Kit_Writer()))->create($req);
        $this->assertFalse($r['ok']);
        $this->assertSame('emcp_invalid', $r['error']['code']);
    }

    public function test_apply_writes_kit_settings() {
        $repo = $this->createMock(Profile_Repository::class);
        $valid = json_decode(file_get_contents(__DIR__ . '/../fixtures/profile-saas-blue.json'), true);
        $repo->method('get')->with(5)->willReturn(['id'=>5,'name'=>'X','data'=>$valid]);

        $writer = $this->getMockBuilder(Kit_Writer::class)->onlyMethods([])->getMock();

        // Mock the global helpers Apply uses to find + update Kit post.
        Functions\expect('get_option')->andReturn(99);  // fake Kit ID stored in option
        Functions\expect('update_post_meta')->once()
            ->with(99, '_elementor_page_settings', \Mockery::type('array'))
            ->andReturn(true);

        $req = $this->req(['id' => 5]);
        $r = (new Rest_Profiles($repo, new Profile_Schema(), $writer))->apply($req);
        $this->assertTrue($r['ok']);
        $this->assertSame(99, $r['data']['kit_post_id']);
    }

    private function req(array $params, $body = null) {
        return new class($params, $body) {
            public function __construct(private array $params, private $body) {}
            public function get_param($k) { return $this->params[$k] ?? null; }
            public function get_json_params() { return $this->body; }
        };
    }
}
