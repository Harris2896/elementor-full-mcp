<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Rest_Sections {
    public function __construct(
        private Section_Parser $parser,
        private Backup_Store $backups,
        private Cache_Invalidator $cache,
        private Page_Lock $lock,
    ) {}

    public function register_routes(): void {
        $ns = Rest_Api::NS;
        register_rest_route($ns, '/pages/(?P<id>\d+)/sections', [
            ['methods'=>'GET',  'callback'=>[$this,'list'],  'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'POST', 'callback'=>[$this,'add'],   'permission_callback'=>fn()=>current_user_can('edit_posts')],
        ]);
        register_rest_route($ns, '/pages/(?P<id>\d+)/sections/(?P<sid>[a-z0-9]+)', [
            ['methods'=>'GET',    'callback'=>[$this,'get'],    'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'PUT',    'callback'=>[$this,'update'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
            ['methods'=>'DELETE', 'callback'=>[$this,'delete'], 'permission_callback'=>fn()=>current_user_can('edit_posts')],
        ]);
        register_rest_route($ns, '/pages/(?P<id>\d+)/sections/(?P<sid>[a-z0-9]+)/duplicate', [
            'methods'=>'POST', 'callback'=>[$this,'duplicate'],
            'permission_callback'=>fn()=>current_user_can('edit_posts'),
        ]);
        register_rest_route($ns, '/pages/(?P<id>\d+)/sections/reorder', [
            'methods'=>'POST', 'callback'=>[$this,'reorder'],
            'permission_callback'=>fn()=>current_user_can('edit_posts'),
        ]);
    }

    public function list($req) {
        $page = $this->load_page($req); if (is_array($page) && isset($page['_fail'])) return $page['_fail'];
        return Rest_Api::ok($this->parser->list($page['data']));
    }

    public function get($req) {
        $page = $this->load_page($req); if (is_array($page) && isset($page['_fail'])) return $page['_fail'];
        $sid = (string) $req->get_param('sid');
        $section = $this->parser->get($page['data'], $sid);
        return $section
            ? Rest_Api::ok($section)
            : Rest_Api::fail('emcp_not_found', "Section {$sid} not found", 404);
    }

    public function add($req) {
        return $this->mutate($req, function ($data, $req) {
            $body = $req->get_json_params() ?? [];
            $json = $body['json'] ?? null;
            if (!is_array($json) || !isset($json['id'])) {
                return ['fail' => Rest_Api::fail('emcp_invalid', 'Missing section JSON with id', 400)];
            }
            $position = isset($body['position']) ? (int) $body['position'] : null;
            $updated = $this->parser->add($data, $json, $position);
            return ['data' => $updated, 'response' => Rest_Api::ok(['sid' => $json['id']])];
        });
    }

    public function update($req) {
        return $this->mutate($req, function ($data, $req) {
            $sid  = (string) $req->get_param('sid');
            $body = $req->get_json_params() ?? [];
            $json = $body['json'] ?? null;
            if (!is_array($json)) return ['fail' => Rest_Api::fail('emcp_invalid', 'Missing section JSON', 400)];
            $json['id'] = $sid;
            if (!$this->parser->get($data, $sid)) {
                return ['fail' => Rest_Api::fail('emcp_not_found', "Section {$sid} not found", 404)];
            }
            $updated = $this->parser->replace($data, $sid, $json);
            return ['data' => $updated, 'response' => Rest_Api::ok(['sid' => $sid])];
        });
    }

    public function delete($req) {
        return $this->mutate($req, function ($data, $req) {
            $sid = (string) $req->get_param('sid');
            if (!$this->parser->get($data, $sid)) {
                return ['fail' => Rest_Api::fail('emcp_not_found', "Section {$sid} not found", 404)];
            }
            $updated = $this->parser->delete($data, $sid);
            return ['data' => $updated, 'response' => Rest_Api::ok(['sid' => $sid, 'deleted' => true])];
        });
    }

    public function duplicate($req) {
        return $this->mutate($req, function ($data, $req) {
            $sid = (string) $req->get_param('sid');
            if (!$this->parser->get($data, $sid)) {
                return ['fail' => Rest_Api::fail('emcp_not_found', "Section {$sid} not found", 404)];
            }
            $updated = $this->parser->duplicate($data, $sid);
            return ['data' => $updated, 'response' => Rest_Api::ok(['sid' => $sid, 'duplicated' => true])];
        });
    }

    public function reorder($req) {
        return $this->mutate($req, function ($data, $req) {
            $body = $req->get_json_params() ?? [];
            $order = $body['order'] ?? null;
            if (!is_array($order)) return ['fail' => Rest_Api::fail('emcp_invalid', 'Missing order array', 400)];
            try {
                $updated = $this->parser->reorder($data, $order);
            } catch (\InvalidArgumentException $e) {
                return ['fail' => Rest_Api::fail('emcp_invalid', $e->getMessage(), 400)];
            }
            return ['data' => $updated, 'response' => Rest_Api::ok(['reordered' => true])];
        });
    }

    /** Common mutation pipeline: lock -> snapshot -> callback -> save -> cache clear -> unlock. */
    private function mutate($req, callable $apply) {
        $page_id = (int) $req->get_param('id');

        $token = $this->lock->acquire($page_id);
        if ($token === null) return Rest_Api::fail('emcp_locked', "Page {$page_id} is being modified", 423);

        try {
            $page = $this->load_page($req);
            if (is_array($page) && isset($page['_fail'])) return $page['_fail'];

            $result = $apply($page['data'], $req);
            if (isset($result['fail'])) return $result['fail'];

            $result['data'] = $this->parser->prune_orphans($result['data']);

            $this->backups->snapshot($page_id, $page['data']);
            update_post_meta($page_id, '_elementor_data', wp_slash(wp_json_encode($result['data'])));
            $this->cache->clear_for_page($page_id);

            return $result['response'];
        } finally {
            $this->lock->release($page_id, $token);
        }
    }

    /** Returns either ['data' => array] or ['_fail' => Response]. */
    private function load_page($req): array {
        $id = (int) $req->get_param('id');
        $post = get_post($id);
        $edit = get_post_meta($id, '_elementor_edit_mode', true);
        if (!$post || $edit !== 'builder') {
            return ['_fail' => Rest_Api::fail('emcp_not_found', "Page {$id} not found", 404)];
        }
        $data = json_decode(get_post_meta($id, '_elementor_data', true) ?: '[]', true);
        return ['data' => is_array($data) ? $data : []];
    }
}
