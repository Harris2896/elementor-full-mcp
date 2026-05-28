<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Rest_Backups {
    public function __construct(
        private Backup_Store $store,
        private Cache_Invalidator $cache,
        private Page_Lock $lock,
    ) {}

    public function register_routes(): void {
        $ns = Rest_Api::NS;
        register_rest_route($ns, '/pages/(?P<id>\d+)/backups', [
            'methods'=>'GET', 'callback'=>[$this,'list'],
            'permission_callback'=>fn()=>current_user_can('edit_posts'),
        ]);
        register_rest_route($ns, '/pages/(?P<id>\d+)/backups/(?P<version>\d+)/restore', [
            'methods'=>'POST', 'callback'=>[$this,'restore'],
            'permission_callback'=>fn()=>current_user_can('edit_posts'),
        ]);
    }

    public function list($req) {
        $page_id = (int) $req->get_param('id');
        if (!$this->is_elementor_page($page_id)) {
            return Rest_Api::fail('emcp_not_found', "Page {$page_id} not found", 404);
        }
        return Rest_Api::ok($this->store->list($page_id));
    }

    public function restore($req) {
        $page_id = (int) $req->get_param('id');
        $version = (int) $req->get_param('version');

        $token = $this->lock->acquire($page_id);
        if ($token === null) return Rest_Api::fail('emcp_locked', "Page {$page_id} is being modified", 423);

        try {
            if (!$this->is_elementor_page($page_id)) {
                return Rest_Api::fail('emcp_not_found', "Page {$page_id} not found", 404);
            }

            $entry = $this->store->get($page_id, $version);
            if (!$entry) return Rest_Api::fail('emcp_not_found', "Backup version {$version} not found", 404);

            // Snapshot the current state so restore itself is reversible.
            $current = json_decode(get_post_meta($page_id, '_elementor_data', true) ?: '[]', true);
            $this->store->snapshot($page_id, is_array($current) ? $current : []);

            update_post_meta($page_id, '_elementor_data', wp_slash(wp_json_encode($entry['data'])));
            $this->cache->clear_for_page($page_id);

            return Rest_Api::ok([
                'restored_from_version' => $version,
                'sections_count'        => count($entry['data']),
            ]);
        } finally {
            $this->lock->release($page_id, $token);
        }
    }

    private function is_elementor_page(int $page_id): bool {
        $post = get_post($page_id);
        return $post && get_post_meta($page_id, '_elementor_edit_mode', true) === 'builder';
    }
}
