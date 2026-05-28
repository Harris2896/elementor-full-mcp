<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Cache_Invalidator {
    public function clear_for_page(int $page_id): void {
        delete_post_meta($page_id, '_elementor_css');
        // Guard against Elementor not being active (P0 environment).
        if (class_exists('\\Elementor\\Plugin')) {
            $files = \Elementor\Plugin::instance()->files_manager ?? null;
            if ($files && method_exists($files, 'clear_cache')) {
                $files->clear_cache();
            }
        }
    }
}
