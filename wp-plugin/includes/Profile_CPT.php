<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Profile_CPT {
    const POST_TYPE = 'emcp_profile';

    public function register(): void {
        register_post_type(self::POST_TYPE, [
            'public'              => false,
            'show_ui'             => false,
            'show_in_rest'        => false,
            'exclude_from_search' => true,
            'supports'            => ['title', 'custom-fields'],
            'capability_type'     => 'post',
            'map_meta_cap'        => true,
            'labels'              => [
                'name'          => 'Elementor MCP Profiles',
                'singular_name' => 'Profile',
            ],
        ]);
    }
}
