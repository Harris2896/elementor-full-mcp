<?php
/**
 * Plugin Name: Elementor CLI Shim
 * Description: Pre-loads wp-admin/includes/plugin.php so Elementor's promotions
 *   module (and anything else that calls is_plugin_active() at init time) does
 *   not fatal when WordPress is bootstrapped in a non-admin context (WP-CLI,
 *   custom REST handlers, etc.).
 *
 * Lives as a must-use plugin under wp-content/mu-plugins/ so it always loads
 * before regular plugins. Mapped in via .wp-env.json for the test environment.
 */

if (!function_exists('is_plugin_active')) {
    require_once ABSPATH . 'wp-admin/includes/plugin.php';
}
