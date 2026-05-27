<?php
require_once __DIR__ . '/../vendor/autoload.php';

if (!class_exists('\\WP_Error')) {
    class WP_Error {
        public string $code;
        public string $message;
        public array $data;
        public function __construct(string $code = '', string $message = '', array $data = []) {
            $this->code = $code;
            $this->message = $message;
            $this->data = $data;
        }
        public function get_error_code()    { return $this->code; }
        public function get_error_message() { return $this->message; }
    }
}

if (!defined('ABSPATH')) {
    define('ABSPATH', '/tmp/');
}
