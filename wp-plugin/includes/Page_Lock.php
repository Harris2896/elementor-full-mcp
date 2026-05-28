<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Page_Lock {
    const TTL = 30;

    public function acquire(int $page_id): ?string {
        $key = $this->key($page_id);
        if (get_transient($key)) return null;
        $token = bin2hex(random_bytes(8));
        set_transient($key, $token, self::TTL);
        return $token;
    }

    public function release(int $page_id, string $token): bool {
        $key = $this->key($page_id);
        $current = get_transient($key);
        if ($current !== $token) return false;
        delete_transient($key);
        return true;
    }

    private function key(int $page_id): string {
        return "emcp_page_lock_{$page_id}";
    }
}
