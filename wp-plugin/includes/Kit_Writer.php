<?php
namespace ElementorMCP;

defined('ABSPATH') || exit;

/**
 * Translate a profile (Elementor MCP shape) into the settings array
 * that the Elementor Kit post stores under postmeta _elementor_page_settings.
 */
class Kit_Writer {
    public function build_settings(array $profile): array {
        $colors = $profile['colors'] ?? [];
        $fonts  = $profile['fonts'] ?? [];
        $typo   = $profile['typography'] ?? [];
        $layout = $profile['layout'] ?? [];
        $bp     = $profile['breakpoints'] ?? ['mobile' => 767, 'desktop' => 1290];
        $btn    = $profile['buttons'] ?? [];

        $settings = [];

        // System colors (Elementor's 4 defaults; we map 4, push the rest to custom).
        $settings['system_colors'] = [
            ['_id' => 'primary',   'title' => 'Primary',   'color' => $colors['primary']   ?? '#000000'],
            ['_id' => 'secondary', 'title' => 'Secondary', 'color' => $colors['secondary'] ?? '#000000'],
            ['_id' => 'text',      'title' => 'Text',      'color' => $colors['text']      ?? '#000000'],
            ['_id' => 'accent',    'title' => 'Accent',    'color' => $colors['accent']    ?? '#000000'],
        ];

        // Profile background goes to custom (Elementor lacks a system "background" slot).
        $custom = [
            ['_id' => 'background', 'title' => 'Background', 'color' => $colors['background'] ?? '#FFFFFF'],
        ];
        foreach (($colors['custom'] ?? []) as $i => $c) {
            $custom[] = [
                '_id'   => $this->slug($c['name'] ?? "custom-$i"),
                'title' => $c['name'] ?? "Custom $i",
                'color' => $c['value'] ?? '#000000',
            ];
        }
        $settings['custom_colors'] = $custom;

        // System typography (Elementor: 4 defaults; we map primary, secondary).
        $settings['system_typography'] = [
            $this->typo_block('primary',   $fonts['primary']   ?? null, $typo['body'] ?? null),
            $this->typo_block('secondary', $fonts['secondary'] ?? null, $typo['body'] ?? null),
            $this->typo_block('text',      $fonts['primary']   ?? null, $typo['body'] ?? null),
            $this->typo_block('accent',    $fonts['secondary'] ?? null, $typo['h2']   ?? null),
        ];
        $settings['custom_typography'] = [];

        // Body defaults (Elementor reads body_* keys for global body styles).
        if (isset($typo['body'])) {
            $this->set_typo($settings, 'body', $fonts['primary'] ?? null, $typo['body']);
        }

        // Heading levels h1..h3 + small — Elementor uses prefixed keys.
        foreach (['h1','h2','h3'] as $h) {
            if (!empty($typo[$h])) $this->set_typo($settings, $h, $fonts['primary'] ?? null, $typo[$h]);
        }
        if (!empty($typo['small'])) $this->set_typo($settings, 'small', $fonts['primary'] ?? null, $typo['small']);

        // Layout
        $settings['container_width'] = [
            'unit'  => 'px',
            'size'  => $layout['container_width'] ?? 1290,
            'sizes' => [],
        ];
        $settings['space_between_widgets'] = [
            'top'        => $layout['section_padding']['top']    ?? 80,
            'right'      => 0,
            'bottom'     => $layout['section_padding']['bottom'] ?? 80,
            'left'       => 0,
            'unit'       => 'px',
            'isLinked'   => false,
        ];

        // Breakpoints
        $settings['viewport_md'] = $bp['mobile']  ?? 767;
        $settings['viewport_lg'] = $bp['desktop'] ?? 1290;

        // Button defaults
        if ($btn) {
            $settings['button_border_radius'] = [
                'unit' => 'px',
                'top'  => $btn['border_radius'] ?? 0,
                'right'=> $btn['border_radius'] ?? 0,
                'bottom'=> $btn['border_radius'] ?? 0,
                'left' => $btn['border_radius'] ?? 0,
                'isLinked' => true,
            ];
            $settings['button_text_padding'] = [
                'unit' => 'px',
                'top'        => $btn['padding_y'] ?? 16,
                'right'      => $btn['padding_x'] ?? 32,
                'bottom'     => $btn['padding_y'] ?? 16,
                'left'       => $btn['padding_x'] ?? 32,
                'isLinked'   => false,
            ];
        }

        return $settings;
    }

    private function typo_block(string $id, ?array $font, ?array $size): array {
        return [
            '_id'                     => $id,
            'title'                   => ucfirst($id),
            'typography_typography'   => 'custom',
            'typography_font_family'  => $font['family']  ?? '',
            'typography_font_size'    => ['unit'=>'px','size'=>$size['size'] ?? 17,'sizes'=>[]],
            'typography_font_weight'  => (string)($size['weight'] ?? 500),
            'typography_line_height'  => ['unit'=>'em','size'=>$size['line_height'] ?? 1.6,'sizes'=>[]],
        ];
    }

    private function set_typo(array &$settings, string $level, ?array $font, array $tp): void {
        $prefix = "{$level}_";
        $settings["{$prefix}typography_typography"]  = 'custom';
        $settings["{$prefix}typography_font_family"] = $font['family'] ?? '';
        $settings["{$prefix}typography_font_size"]   = ['unit'=>'px','size'=>$tp['size'] ?? 17,'sizes'=>[]];
        $settings["{$prefix}typography_font_size_mobile"] = ['unit'=>'px','size'=>$tp['mobile'] ?? ($tp['size'] ?? 17),'sizes'=>[]];
        $settings["{$prefix}typography_font_weight"] = (string)($tp['weight'] ?? 500);
        $settings["{$prefix}typography_line_height"] = ['unit'=>'em','size'=>$tp['line_height'] ?? 1.4,'sizes'=>[]];
    }

    private function slug(string $name): string {
        $slug = strtolower(preg_replace('/[^a-z0-9]+/i', '-', $name));
        return trim($slug, '-') ?: 'custom';
    }
}
