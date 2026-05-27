<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

class Section_Parser {
    public function list(array $data): array {
        $out = [];
        foreach ($data as $section) {
            $widgets = $this->collect_widgets($section);
            $title   = $section['settings']['_title'] ?? '';
            $out[] = [
                'sid'      => $section['id'] ?? '',
                'title'    => $title !== '' ? $title : 'Untitled',
                'el_type'  => $section['elType'] ?? 'section',
                'widgets'  => array_values(array_unique($widgets)),
            ];
        }
        return $out;
    }

    public function get(array $data, string $sid): ?array {
        foreach ($data as $section) {
            if (($section['id'] ?? '') === $sid) return $section;
        }
        return null;
    }

    public function add(array $data, array $section, ?int $position = null): array {
        if ($position === null || $position < 0 || $position > count($data)) {
            $data[] = $section;
            return $data;
        }
        array_splice($data, $position, 0, [$section]);
        return $data;
    }

    public function replace(array $data, string $sid, array $section): array {
        foreach ($data as $i => $existing) {
            if (($existing['id'] ?? '') === $sid) {
                $data[$i] = $section;
                return $data;
            }
        }
        return $data;
    }

    public function delete(array $data, string $sid): array {
        return array_values(array_filter($data, fn($s) => ($s['id'] ?? '') !== $sid));
    }

    public function duplicate(array $data, string $sid): array {
        $index = null;
        foreach ($data as $i => $s) if (($s['id'] ?? '') === $sid) { $index = $i; break; }
        if ($index === null) return $data;
        $copy = $this->rekey_ids($data[$index]);
        array_splice($data, $index + 1, 0, [$copy]);
        return $data;
    }

    public function reorder(array $data, array $order): array {
        $ids = array_map(fn($s) => $s['id'] ?? '', $data);
        if (count(array_diff($ids, $order)) !== 0 || count(array_diff($order, $ids)) !== 0) {
            throw new \InvalidArgumentException('Reorder set must include all and only existing section ids');
        }
        $byId = [];
        foreach ($data as $s) $byId[$s['id']] = $s;
        return array_values(array_map(fn($id) => $byId[$id], $order));
    }

    private function collect_widgets(array $node): array {
        $widgets = [];
        if (($node['elType'] ?? '') === 'widget' && isset($node['widgetType'])) {
            $widgets[] = $node['widgetType'];
        }
        foreach ($node['elements'] ?? [] as $child) {
            $widgets = array_merge($widgets, $this->collect_widgets($child));
        }
        return $widgets;
    }

    /** Recursively assign fresh 8-hex IDs (Elementor format). */
    private function rekey_ids(array $node): array {
        $node['id'] = bin2hex(random_bytes(4));
        if (isset($node['elements']) && is_array($node['elements'])) {
            $node['elements'] = array_map(fn($c) => $this->rekey_ids($c), $node['elements']);
        }
        return $node;
    }
}
