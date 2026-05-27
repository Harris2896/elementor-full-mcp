<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Plugin {
    const VERSION = '0.0.1';

    private static ?Plugin $instance = null;

    public static function instance(): self {
        if (self::$instance === null) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    public function init(): void {
        add_action('admin_menu', [$this, 'register_admin_menu']);
        add_action('rest_api_init', [$this, 'register_rest_routes']);
        add_filter('rest_authentication_errors', [$this, 'filter_rest_auth'], 99);
    }

    public function register_admin_menu(): void {
        (new Admin())->register_menu();
    }

    public function register_rest_routes(): void {
        (new Rest_Api())->register_routes();
    }

    public function filter_rest_auth($result) {
        static $auth = null;
        if ($auth === null) $auth = new Auth(new Api_Keys());
        return $auth->filter($result);
    }
}
