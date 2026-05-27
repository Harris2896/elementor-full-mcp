<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Rest_Api {
    const NS = 'elementor-mcp/v1';

    public function register_routes(): void {
        register_rest_route(self::NS, '/health', [
            'methods'             => 'GET',
            'callback'            => [$this, 'health'],
            'permission_callback' => '__return_true',
        ]);
        register_rest_route(self::NS, '/auth/verify', [
            'methods'             => 'GET',
            'callback'            => [$this, 'auth_verify'],
            'permission_callback' => fn() => get_current_user_id() > 0,
        ]);

        (new Rest_Profiles(
            new Profile_Repository(),
            new Profile_Schema(),
            new Kit_Writer(),
        ))->register_routes();
    }

    public function health() {
        return self::ok([
            'status'         => 'ok',
            'plugin_version' => Plugin::VERSION,
            'elementor'      => defined('ELEMENTOR_VERSION') ? ELEMENTOR_VERSION : null,
        ]);
    }

    public function auth_verify() {
        $user = wp_get_current_user();
        $caps = array_keys(array_filter((array)($user->allcaps ?? [])));
        return self::ok([
            'user_id' => (int) get_current_user_id(),
            'caps'    => $caps,
            'scopes'  => ['read', 'write'],
        ]);
    }

    public static function ok($data, array $warnings = []) {
        return rest_ensure_response([
            'ok' => true, 'data' => $data, 'warnings' => $warnings, 'error' => null,
        ]);
    }

    public static function fail(string $code, string $message, int $status = 400, array $details = []) {
        $resp = rest_ensure_response([
            'ok' => false, 'data' => null, 'warnings' => [],
            'error' => ['code' => $code, 'message' => $message, 'details' => $details],
        ]);
        if (is_object($resp) && method_exists($resp, 'set_status')) $resp->set_status($status);
        return $resp;
    }
}
