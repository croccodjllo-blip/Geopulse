<?php
/**
 * Plugin Name: GeoPulse Safe Apply
 * Description: Applica solo ottimizzazioni GeoPulse allowlistate (piano Plus).
 * Version: 1.0.0
 *
 * Installa come MU-plugin: wp-content/mu-plugins/geopulse-safe-apply.php
 * Poi visita: wp-admin/?geopulse_run=1 (da admin) oppure usa il bottone in dashboard WP.
 */
declare(strict_types=1);

if (!defined('ABSPATH')) {
    exit;
}

const GP_API_BASE = '{{API_BASE}}';
const GP_SITE_ID = {{SITE_ID}};
const GP_TOKEN = '{{TOKEN}}';

add_action('wp_head', static function (): void {
    $file = ABSPATH . 'geopulse-head.html';
    if (is_readable($file)) {
        echo "\n<!-- GeoPulse head -->\n";
        echo file_get_contents($file);
        echo "\n";
    }
}, 2);

add_action('admin_notices', static function (): void {
    if (!current_user_can('manage_options')) {
        return;
    }
    $url = wp_nonce_url(admin_url('admin-post.php?action=geopulse_safe_apply'), 'geopulse_safe_apply');
    echo '<div class="notice notice-info"><p><strong>GeoPulse Safe Apply</strong> — ';
    echo '<a class="button button-primary" href="' . esc_url($url) . '">Applica ottimizzazioni sicure</a></p></div>';
});

add_action('admin_post_geopulse_safe_apply', 'geopulse_run_safe_apply');

function geopulse_run_safe_apply(): void {
    if (!current_user_can('manage_options')) {
        wp_die('Forbidden', 403);
    }
    check_admin_referer('geopulse_safe_apply');
    try {
        geopulse_apply_now();
        $status = 'ok';
    } catch (Throwable $e) {
        $status = 'error';
    }
    wp_safe_redirect(add_query_arg('geopulse_apply', $status, admin_url('index.php')));
    exit;
}

function geopulse_http(string $method, string $path, ?array $body = null): array {
    $args = [
        'method' => $method,
        'timeout' => 45,
        'headers' => [
            'Authorization' => 'Bearer ' . GP_TOKEN,
            'Accept' => 'application/json',
        ],
    ];
    if ($body !== null) {
        $args['headers']['Content-Type'] = 'application/json';
        $args['body'] = wp_json_encode($body);
    }
    $res = wp_remote_request(rtrim(GP_API_BASE, '/') . $path, $args);
    if (is_wp_error($res)) {
        throw new RuntimeException($res->get_error_message());
    }
    $code = (int) wp_remote_retrieve_response_code($res);
    $data = json_decode((string) wp_remote_retrieve_body($res), true);
    if (!is_array($data) || $code >= 400) {
        throw new RuntimeException(is_array($data) ? (string) ($data['error'] ?? "HTTP $code") : "HTTP $code");
    }
    return $data;
}

function geopulse_apply_now(): array {
    $manifest = geopulse_http('GET', '/api/v1/apply/' . GP_SITE_ID . '/pending');
    $results = [];
    foreach (($manifest['actions'] ?? []) as $action) {
        $id = (string) ($action['id'] ?? '');
        $type = (string) ($action['type'] ?? '');
        try {
            if ($type === 'write_public_file') {
                $name = basename((string) $action['path']);
                if (!in_array($name, ['llms.txt', 'robots.txt', 'ai.txt'], true)) {
                    throw new RuntimeException('file non consentito');
                }
                $ok = file_put_contents(ABSPATH . $name, (string) $action['content']);
                if ($ok === false) {
                    throw new RuntimeException('write failed');
                }
                $results[] = ['id' => $id, 'status' => 'ok', 'detail' => $name];
            } elseif ($type === 'inject_head') {
                $headId = (string) $action['head_id'];
                $file = ABSPATH . 'geopulse-head.html';
                $existing = is_readable($file) ? (string) file_get_contents($file) : '';
                $start = "<!-- geopulse:$headId -->";
                $end = "<!-- /geopulse:$headId -->";
                $block = $start . "\n" . trim((string) $action['html']) . "\n" . $end;
                if (strpos($existing, $start) !== false) {
                    $existing = preg_replace(
                        '/' . preg_quote($start, '/') . '.*?' . preg_quote($end, '/') . '/s',
                        $block,
                        $existing
                    ) ?? $block;
                } else {
                    $existing = trim($existing) . "\n" . $block . "\n";
                }
                file_put_contents($file, $existing);
                $results[] = ['id' => $id, 'status' => 'ok', 'detail' => $headId];
            } elseif ($type === 'update_meta') {
                $fields = $action['fields'] ?? [];
                if (!empty($fields['title'])) {
                    update_option('blogname', sanitize_text_field((string) $fields['title']));
                }
                if (!empty($fields['description'])) {
                    update_option('blogdescription', sanitize_text_field((string) $fields['description']));
                }
                $results[] = ['id' => $id, 'status' => 'ok', 'detail' => 'wp options'];
            } else {
                $results[] = ['id' => $id, 'status' => 'skipped', 'detail' => 'unsupported'];
            }
        } catch (Throwable $e) {
            $results[] = ['id' => $id, 'status' => 'error', 'detail' => $e->getMessage()];
        }
    }
    $ack = geopulse_http('POST', '/api/v1/apply/' . GP_SITE_ID . '/ack', [
        'results' => $results,
        'agent' => 'wordpress-mu/1.0',
    ]);
    return ['status' => 'done', 'results' => $results, 'ack' => $ack];
}
