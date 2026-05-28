<?php
/**
 * Plugin Name: Elementor MCP Bridge
 * Description: REST + admin bridge for the Elementor MCP Python server.
 * Version: 0.0.1
 * Author: leobot
 * Requires PHP: 7.4
 * Requires at least: 6.0
 */

defined('ABSPATH') || exit;

require_once __DIR__ . '/vendor/autoload.php';

register_activation_hook(__FILE__, function () {
    update_option('elementor_mcp_version', \ElementorMCP\Plugin::VERSION);
    (new \ElementorMCP\Theme_Bootstrap())->ensure();
});

register_deactivation_hook(__FILE__, function () {
    // No cleanup yet; keep API keys and profiles on deactivate.
});

add_action('plugins_loaded', function () {
    \ElementorMCP\Plugin::instance()->init();
});
