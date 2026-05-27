<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Rest_Profiles {
    const KIT_OPTION = 'elementor_active_kit';
    const KIT_META   = '_elementor_page_settings';

    public function __construct(
        private Profile_Repository $repo,
        private Profile_Schema $schema,
        private Kit_Writer $writer
    ) {}

    public function register_routes(): void {
        $ns = Rest_Api::NS;
        register_rest_route($ns, '/profiles', [
            ['methods'=>'GET',  'callback'=>[$this,'list'],   'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'POST', 'callback'=>[$this,'create'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
        ]);
        register_rest_route($ns, '/profiles/(?P<id>\d+)', [
            ['methods'=>'GET',    'callback'=>[$this,'get'],    'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'PUT',    'callback'=>[$this,'update'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'DELETE', 'callback'=>[$this,'delete'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
        ]);
        register_rest_route($ns, '/profiles/(?P<id>\d+)/apply', [
            'methods'=>'POST', 'callback'=>[$this,'apply'],
            'permission_callback'=>fn()=>current_user_can('edit_posts'),
        ]);
    }

    public function list() {
        return Rest_Api::ok($this->repo->list());
    }

    public function get($req) {
        $id = (int) $req->get_param('id');
        $r  = $this->repo->get($id);
        return $r ? Rest_Api::ok($r) : Rest_Api::fail('emcp_not_found', "Profile {$id} not found", 404);
    }

    public function create($req) {
        $body = $req->get_json_params();
        $v    = $this->schema->validate(is_array($body) ? $body : []);
        if (!$v['ok']) return Rest_Api::fail('emcp_invalid', 'Profile validation failed', 400, $v['errors']);
        $id = $this->repo->create($body);
        return Rest_Api::ok(['id' => $id], $v['warnings']);
    }

    public function update($req) {
        $id   = (int) $req->get_param('id');
        $body = $req->get_json_params();
        $v    = $this->schema->validate(is_array($body) ? $body : []);
        if (!$v['ok']) return Rest_Api::fail('emcp_invalid', 'Profile validation failed', 400, $v['errors']);
        if (!$this->repo->update($id, $body)) {
            return Rest_Api::fail('emcp_not_found', "Profile {$id} not found", 404);
        }
        return Rest_Api::ok(['id' => $id], $v['warnings']);
    }

    public function delete($req) {
        $id = (int) $req->get_param('id');
        return $this->repo->delete($id)
            ? Rest_Api::ok(['id' => $id, 'deleted' => true])
            : Rest_Api::fail('emcp_not_found', "Profile {$id} not found", 404);
    }

    public function apply($req) {
        $id  = (int) $req->get_param('id');
        $row = $this->repo->get($id);
        if (!$row) return Rest_Api::fail('emcp_not_found', "Profile {$id} not found", 404);

        $kit_id = (int) get_option(self::KIT_OPTION, 0);
        if ($kit_id <= 0) return Rest_Api::fail('emcp_internal', 'Elementor active kit not configured', 500);

        $settings = $this->writer->build_settings($row['data']);
        update_post_meta($kit_id, self::KIT_META, $settings);

        return Rest_Api::ok(['kit_post_id' => $kit_id, 'profile_id' => $id]);
    }
}
