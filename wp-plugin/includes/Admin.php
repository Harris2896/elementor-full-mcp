<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Admin {
    public function register_menu(): void {
        add_menu_page(
            'Elementor MCP',
            'Elementor MCP',
            'manage_options',
            'elementor-mcp',
            [$this, 'render_page'],
            'dashicons-art',
            81
        );
    }

    public function render_page(): void {
        echo '<div class="wrap"><h1>Elementor MCP</h1><p>Phase 0 — admin shell.</p></div>';
    }
}
