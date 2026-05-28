<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Theme_Bootstrap {
    const SLUG = 'hello-elementor';

    public function ensure(): void {
        $current = wp_get_theme();
        if (($current->Stylesheet ?? '') === self::SLUG) return;

        $installed = wp_get_themes();
        if (!isset($installed[self::SLUG])) {
            $this->install();
        }
        switch_theme(self::SLUG);
    }

    protected function install(): void {
        if (!function_exists('themes_api')) {
            require_once ABSPATH . 'wp-admin/includes/theme.php';
        }
        $info = themes_api('theme_information', [
            'slug'   => self::SLUG,
            'fields' => ['sections' => false],
        ]);
        if (!$info || empty($info->download_link)) return;
        $this->install_theme_from_api($info);
    }

    protected function install_theme_from_api($info): bool {
        if (!class_exists('\\Theme_Upgrader')) {
            require_once ABSPATH . 'wp-admin/includes/file.php';
            require_once ABSPATH . 'wp-admin/includes/misc.php';
            require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';
            require_once ABSPATH . 'wp-admin/includes/class-theme-upgrader.php';
        }
        $skin = new \WP_Ajax_Upgrader_Skin();
        $upgrader = new \Theme_Upgrader($skin);
        $result = $upgrader->install($info->download_link);
        return $result === true;
    }
}
