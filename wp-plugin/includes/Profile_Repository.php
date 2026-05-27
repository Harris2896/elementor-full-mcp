<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Profile_Repository {
    const META_KEY = '_emcp_profile_data';

    public function create(array $data): int {
        $id = wp_insert_post([
            'post_type'   => Profile_CPT::POST_TYPE,
            'post_title'  => sanitize_text_field($data['name'] ?? ''),
            'post_status' => 'publish',
        ]);
        if (is_wp_error($id) || !$id) {
            $msg = is_wp_error($id) ? $id->get_error_message() : 'wp_insert_post returned 0';
            throw new \RuntimeException("Failed to create profile: {$msg}");
        }
        update_post_meta((int) $id, self::META_KEY, wp_slash(wp_json_encode($data)));
        return (int) $id;
    }

    public function get(int $id): ?array {
        $post = get_post($id);
        if (!$post || $post->post_type !== Profile_CPT::POST_TYPE) return null;
        $raw  = get_post_meta($id, self::META_KEY, true);
        $data = json_decode($raw ?: '{}', true);
        return [
            'id'    => $id,
            'name'  => $post->post_title,
            'data'  => is_array($data) ? $data : [],
        ];
    }

    public function update(int $id, array $data): bool {
        $post = get_post($id);
        if (!$post || $post->post_type !== Profile_CPT::POST_TYPE) return false;
        $result = wp_update_post([
            'ID'         => $id,
            'post_title' => sanitize_text_field($data['name'] ?? $post->post_title),
        ]);
        if (is_wp_error($result) || !$result) return false;
        update_post_meta($id, self::META_KEY, wp_slash(wp_json_encode($data)));
        return true;
    }

    public function delete(int $id): bool {
        $post = get_post($id);
        if (!$post || $post->post_type !== Profile_CPT::POST_TYPE) return false;
        $r = wp_delete_post($id, true);
        return $r !== false && $r !== null;
    }

    public function list(): array {
        $posts = get_posts([
            'post_type'      => Profile_CPT::POST_TYPE,
            'post_status'    => 'publish',
            'posts_per_page' => 200,
            'orderby'        => 'title',
            'order'          => 'ASC',
        ]);
        return array_map(fn($p) => [
            'id'         => $p->ID,
            'name'       => $p->post_title,
            'created_at' => $p->post_date_gmt ?? null,
        ], $posts);
    }
}
