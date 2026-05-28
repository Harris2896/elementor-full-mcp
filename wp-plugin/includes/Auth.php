<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Auth {
    const NS = 'elementor-mcp/v1';

    private Api_Keys $keys;

    public function __construct(Api_Keys $keys) {
        $this->keys = $keys;
    }

    public function filter($result) {
        // Already authenticated by another mechanism — passthrough.
        if (!is_null($result)) return $result;

        $uri = $_SERVER['REQUEST_URI'] ?? '';
        $matches_our_ns = strpos($uri, '/wp-json/' . self::NS . '/') !== false
            || strpos($uri, 'rest_route=/' . self::NS . '/') !== false;
        // Also authenticate WP media upload route so image_upload via /wp/v2/media works
        $matches_media   = strpos($uri, '/wp-json/wp/v2/media') !== false
            || strpos($uri, 'rest_route=/wp/v2/media') !== false;
        if (!$matches_our_ns && !$matches_media) {
            return null;
        }

        $header = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
        if (stripos($header, 'Bearer ') !== 0) return null;
        $raw = substr($header, 7);

        $record = $this->keys->verify($raw);
        if ($record === null) {
            return new \WP_Error(
                'emcp_auth_invalid',
                'Invalid API key',
                ['status' => 401]
            );
        }

        wp_set_current_user((int) $record['user_id']);
        return null;
    }
}
