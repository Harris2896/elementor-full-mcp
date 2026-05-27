<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Profile_Schema {
    const TOP_LEVEL = ['name','colors','fonts','typography','layout','breakpoints','buttons'];
    const REQUIRED_TOP = ['name','colors','fonts','typography','layout'];
    const REQUIRED_COLORS = ['primary','secondary','text','accent','background'];
    const REQUIRED_TYPO_LEVELS = ['h1','h2','h3','body','small'];

    public function validate(array $data): array {
        $errors = [];
        $warnings = [];

        foreach (self::REQUIRED_TOP as $key) {
            if (!array_key_exists($key, $data)) {
                $errors[] = "missing required field '{$key}'";
            }
        }

        foreach (array_keys($data) as $key) {
            if (!in_array($key, self::TOP_LEVEL, true)) {
                $warnings[] = "unknown field at top level: '{$key}'";
            }
        }

        if (isset($data['colors'])) {
            if (!is_array($data['colors'])) {
                $errors[] = "colors must be an object";
            } else {
                foreach (self::REQUIRED_COLORS as $name) {
                    if (!isset($data['colors'][$name])) {
                        $errors[] = "missing required color: colors.{$name}";
                        continue;
                    }
                    if (!$this->is_hex($data['colors'][$name])) {
                        $errors[] = "invalid hex color for colors.{$name}: '{$data['colors'][$name]}'";
                    }
                }
            }
        }

        if (isset($data['typography'])) {
            if (!is_array($data['typography'])) {
                $errors[] = "typography must be an object";
            } else {
                foreach (self::REQUIRED_TYPO_LEVELS as $lvl) {
                    if (!isset($data['typography'][$lvl])) {
                        $errors[] = "missing typography level: typography.{$lvl}";
                        continue;
                    }
                    $t = $data['typography'][$lvl];
                    if (!is_array($t)) {
                        $errors[] = "typography.{$lvl} must be an object";
                        continue;
                    }
                    if (!is_int($t['size'] ?? null) || $t['size'] <= 0) {
                        $errors[] = "typography.{$lvl}.size must be > 0";
                    }
                }
            }
        }

        return [
            'ok'       => count($errors) === 0,
            'errors'   => $errors,
            'warnings' => $warnings,
        ];
    }

    private function is_hex($value): bool {
        return is_string($value) && (bool) preg_match('/^#[0-9A-Fa-f]{6}$/', $value);
    }
}
