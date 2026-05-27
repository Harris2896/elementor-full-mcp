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
    }

    public function health() {
        return $this->envelope(true, [
            'status'         => 'ok',
            'plugin_version' => Plugin::VERSION,
            'elementor'      => defined('ELEMENTOR_VERSION') ? ELEMENTOR_VERSION : null,
        ]);
    }

    public function auth_verify() {
        $user = wp_get_current_user();
        $caps = array_keys(array_filter((array)($user->allcaps ?? [])));
        return $this->envelope(true, [
            'user_id' => (int) get_current_user_id(),
            'caps'    => $caps,
            'scopes'  => ['read', 'write'],
        ]);
    }

    private function envelope(bool $ok, $data = null, array $warnings = [], ?array $error = null) {
        return rest_ensure_response([
            'ok'       => $ok,
            'data'     => $data,
            'warnings' => $warnings,
            'error'    => $error,
        ]);
    }
}
