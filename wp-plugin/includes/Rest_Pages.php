<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Rest_Pages {
    public function register_routes(): void {
        $ns = Rest_Api::NS;
        register_rest_route($ns, '/pages', [
            ['methods'=>'GET',  'callback'=>[$this,'list'],   'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'POST', 'callback'=>[$this,'create'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
        ]);
        register_rest_route($ns, '/pages/(?P<id>\d+)', [
            ['methods'=>'GET',    'callback'=>[$this,'get'],    'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'DELETE', 'callback'=>[$this,'delete'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
        ]);
    }

    public function list($req) {
        $posts = get_posts([
            'post_type'      => ['page', 'post'],
            'posts_per_page' => 100,
            'meta_key'       => '_elementor_edit_mode',
            'meta_value'     => 'builder',
        ]);
        $out = [];
        foreach ($posts as $p) {
            $data = get_post_meta($p->ID, '_elementor_data', true);
            $sections = json_decode($data ?: '[]', true);
            $out[] = [
                'id'              => (int) $p->ID,
                'title'           => $p->post_title,
                'status'          => $p->post_status,
                'edit_url'        => admin_url("post.php?post={$p->ID}&action=elementor"),
                'preview_url'     => get_permalink($p->ID),
                'sections_count'  => is_array($sections) ? count($sections) : 0,
            ];
        }
        return Rest_Api::ok($out);
    }

    public function create($req) {
        $body  = $req->get_json_params() ?? [];
        $title = sanitize_text_field($body['title'] ?? 'Untitled');
        $id = wp_insert_post([
            'post_type'   => 'page',
            'post_title'  => $title,
            'post_status' => 'publish',
        ]);
        if (is_wp_error($id) || !$id) {
            return Rest_Api::fail('emcp_internal', 'Failed to create page', 500);
        }
        update_post_meta($id, '_elementor_edit_mode', 'builder');
        update_post_meta($id, '_elementor_template_type', 'wp-page');
        update_post_meta($id, '_elementor_data', '[]');
        return Rest_Api::ok([
            'id'          => (int) $id,
            'title'       => $title,
            'edit_url'    => admin_url("post.php?post={$id}&action=elementor"),
            'preview_url' => get_permalink($id),
        ]);
    }

    public function get($req) {
        $id   = (int) $req->get_param('id');
        $post = get_post($id);
        $edit = get_post_meta($id, '_elementor_edit_mode', true);
        if (!$post || $edit !== 'builder') {
            return Rest_Api::fail('emcp_not_found', "Page {$id} not found or not an Elementor page", 404);
        }
        $sections = json_decode(get_post_meta($id, '_elementor_data', true) ?: '[]', true);
        return Rest_Api::ok([
            'id'              => $id,
            'title'           => $post->post_title,
            'status'          => $post->post_status,
            'edit_url'        => admin_url("post.php?post={$id}&action=elementor"),
            'preview_url'     => get_permalink($id),
            'sections_count'  => is_array($sections) ? count($sections) : 0,
        ]);
    }

    public function delete($req) {
        $id = (int) $req->get_param('id');
        $post = get_post($id);
        $edit = get_post_meta($id, '_elementor_edit_mode', true);
        if (!$post || $edit !== 'builder') {
            return Rest_Api::fail('emcp_not_found', "Page {$id} not found", 404);
        }
        wp_delete_post($id, true);
        return Rest_Api::ok(['id' => $id, 'deleted' => true]);
    }
}
