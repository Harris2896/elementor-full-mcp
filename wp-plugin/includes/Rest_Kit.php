<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Rest_Kit {
    const KIT_OPTION = 'elementor_active_kit';
    const KIT_META   = '_elementor_page_settings';

    public function register_routes(): void {
        $ns = Rest_Api::NS;
        register_rest_route($ns, '/kit', [
            ['methods'=>'GET', 'callback'=>[$this,'get'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'PUT', 'callback'=>[$this,'put'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
        ]);
    }

    public function get($req) {
        $id = (int) get_option(self::KIT_OPTION, 0);
        if ($id <= 0) return Rest_Api::fail('emcp_internal', 'Elementor active kit not configured', 500);
        $settings = get_post_meta($id, self::KIT_META, true);
        return Rest_Api::ok(is_array($settings) ? $settings : []);
    }

    public function put($req) {
        $id = (int) get_option(self::KIT_OPTION, 0);
        if ($id <= 0) return Rest_Api::fail('emcp_internal', 'Elementor active kit not configured', 500);
        $body = $req->get_json_params() ?? [];
        update_post_meta($id, self::KIT_META, $body);
        return Rest_Api::ok(['kit_post_id' => $id]);
    }
}
