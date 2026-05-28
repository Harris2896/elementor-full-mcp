<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Backup_Store {
    const META_KEY = '_elementor_data_backup_history';
    const MAX_VERSIONS = 5;

    public function snapshot(int $page_id, array $data): int {
        $hist = $this->read($page_id);
        $next_version = (count($hist) > 0 ? $hist[0]['version'] : 0) + 1;
        array_unshift($hist, [
            'version'   => $next_version,
            'timestamp' => current_time('mysql'),
            'data'      => $data,
        ]);
        if (count($hist) > self::MAX_VERSIONS) {
            $hist = array_slice($hist, 0, self::MAX_VERSIONS);
        }
        update_post_meta($page_id, self::META_KEY, wp_json_encode($hist));
        return $next_version;
    }

    public function list(int $page_id): array {
        return array_map(fn($e) => [
            'version'   => $e['version'],
            'timestamp' => $e['timestamp'],
            'sections_count' => is_array($e['data'] ?? null) ? count($e['data']) : 0,
        ], $this->read($page_id));
    }

    public function get(int $page_id, int $version): ?array {
        foreach ($this->read($page_id) as $entry) {
            if ($entry['version'] === $version) return $entry;
        }
        return null;
    }

    private function read(int $page_id): array {
        $raw = get_post_meta($page_id, self::META_KEY, true);
        $decoded = json_decode($raw ?: '[]', true);
        return is_array($decoded) ? $decoded : [];
    }
}
