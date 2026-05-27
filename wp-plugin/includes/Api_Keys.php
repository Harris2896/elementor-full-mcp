<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Api_Keys {
    const OPTION = 'elementor_mcp_api_keys';
    const PREFIX = 'emcp_';

    public function generate(int $user_id, string $label, array $scopes): array {
        $id     = wp_generate_password(12, false);
        $secret = wp_generate_password(32, false);
        $raw    = self::PREFIX . $id . '_' . $secret;
        $record = [
            'id'         => $id,
            'hash'       => password_hash($secret, PASSWORD_BCRYPT),
            'label'      => sanitize_text_field($label),
            'user_id'    => $user_id,
            'scopes'     => $scopes,
            'created_at' => current_time('mysql'),
            'last_used'  => null,
        ];
        $all = get_option(self::OPTION, []);
        $all[] = $record;
        update_option(self::OPTION, $all);
        return ['raw' => $raw, 'record' => $record];
    }

    public function verify(string $raw): ?array {
        if (strpos($raw, self::PREFIX) !== 0) return null;
        $parts = explode('_', substr($raw, strlen(self::PREFIX)), 2);
        if (count($parts) !== 2) return null;
        [$id, $secret] = $parts;
        $all = get_option(self::OPTION, []);
        foreach ($all as $i => $record) {
            if ($record['id'] === $id && password_verify($secret, $record['hash'])) {
                $all[$i]['last_used'] = current_time('mysql');
                update_option(self::OPTION, $all);
                return $record;
            }
        }
        return null;
    }

    public function list_all(): array {
        $all = get_option(self::OPTION, []);
        return array_map(fn($r) => [
            'id'         => $r['id'],
            'label'      => $r['label'],
            'user_id'    => $r['user_id'],
            'scopes'     => $r['scopes'],
            'created_at' => $r['created_at'],
            'last_used'  => $r['last_used'],
        ], $all);
    }

    public function revoke(string $id): bool {
        $all = get_option(self::OPTION, []);
        $filtered = array_values(array_filter($all, fn($r) => $r['id'] !== $id));
        if (count($filtered) === count($all)) return false;
        update_option(self::OPTION, $filtered);
        return true;
    }
}
