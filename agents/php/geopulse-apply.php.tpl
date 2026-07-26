<?php
/**
 * GeoPulse Safe Apply Agent (Plus) — standalone PHP
 *
 * 1. Scarica questo file dalla dashboard GeoPulse (già compilato con site id + token)
 * 2. Caricalo nella document root del sito
 * 3. Esegui: php geopulse-apply.php
 *    oppure: curl "https://tuosito.it/geopulse-apply.php?key=CRON_SECRET"
 * 4. Includi geopulse-head.html nel <head> del tema
 *
 * Solo azioni allowlistate: llms.txt, robots.txt, ai.txt, head inject, meta json.
 */
declare(strict_types=1);

const GP_API_BASE = '{{API_BASE}}';
const GP_SITE_ID = {{SITE_ID}};
const GP_TOKEN = '{{TOKEN}}';
const GP_CRON_SECRET = 'change-me';
const GP_DOCROOT = __DIR__;
const GP_HEAD_FILE = __DIR__ . '/geopulse-head.html';

if (PHP_SAPI !== 'cli') {
    $key = $_GET['key'] ?? '';
    if (!hash_equals(GP_CRON_SECRET, (string)$key)) {
        http_response_code(403);
        header('Content-Type: text/plain; charset=utf-8');
        echo "Forbidden\n";
        exit;
    }
}

function gp_request(string $method, string $path, ?array $body = null): array {
    $url = rtrim(GP_API_BASE, '/') . $path;
    $ch = curl_init($url);
    $headers = [
        'Authorization: Bearer ' . GP_TOKEN,
        'Accept: application/json',
        'User-Agent: GeoPulse-SafeApply/1.0',
    ];
    $opts = [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 45,
        CURLOPT_CUSTOMREQUEST => $method,
        CURLOPT_HTTPHEADER => $headers,
    ];
    if ($body !== null) {
        $payload = json_encode($body, JSON_UNESCAPED_UNICODE);
        $headers[] = 'Content-Type: application/json';
        $opts[CURLOPT_HTTPHEADER] = $headers;
        $opts[CURLOPT_POSTFIELDS] = $payload;
    }
    curl_setopt_array($ch, $opts);
    $raw = curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err = curl_error($ch);
    curl_close($ch);
    if ($raw === false) {
        throw new RuntimeException('HTTP error: ' . $err);
    }
    $data = json_decode($raw, true);
    if (!is_array($data)) {
        throw new RuntimeException("Invalid JSON (HTTP $code)");
    }
    if ($code >= 400) {
        $msg = $data['error'] ?? ("HTTP $code");
        throw new RuntimeException((string)$msg);
    }
    return $data;
}

function gp_write_file(string $path, string $content): void {
    $name = basename($path);
    $allowed = ['llms.txt', 'robots.txt', 'ai.txt'];
    if (!in_array($name, $allowed, true)) {
        throw new RuntimeException("File non consentito: $name");
    }
    $target = rtrim(GP_DOCROOT, '/\\') . '/' . $name;
    if (file_put_contents($target, $content) === false) {
        throw new RuntimeException("Impossibile scrivere $target");
    }
}

function gp_inject_head(string $headId, string $html): void {
    $allowed = ['organization_jsonld', 'faq_jsonld', 'meta_pack', 'viewport'];
    if (!in_array($headId, $allowed, true)) {
        throw new RuntimeException("head_id non consentito: $headId");
    }
    $existing = file_exists(GP_HEAD_FILE) ? (string)file_get_contents(GP_HEAD_FILE) : '';
    $start = "<!-- geopulse:$headId -->";
    $end = "<!-- /geopulse:$headId -->";
    $block = $start . "\n" . trim($html) . "\n" . $end;
    if (strpos($existing, $start) !== false) {
        $existing = preg_replace(
            '/' . preg_quote($start, '/') . '.*?' . preg_quote($end, '/') . '/s',
            $block,
            $existing
        ) ?? $block;
    } else {
        $existing = trim($existing) . "\n" . $block . "\n";
    }
    if (file_put_contents(GP_HEAD_FILE, $existing) === false) {
        throw new RuntimeException('Impossibile scrivere geopulse-head.html');
    }
}

$manifest = gp_request('GET', '/api/v1/apply/' . GP_SITE_ID . '/pending');
$actions = $manifest['actions'] ?? [];
$results = [];

foreach ($actions as $action) {
    $id = (string)($action['id'] ?? '');
    $type = (string)($action['type'] ?? '');
    try {
        if ($type === 'write_public_file') {
            gp_write_file((string)$action['path'], (string)$action['content']);
            $results[] = ['id' => $id, 'status' => 'ok', 'detail' => 'written'];
        } elseif ($type === 'inject_head') {
            gp_inject_head((string)$action['head_id'], (string)$action['html']);
            $results[] = ['id' => $id, 'status' => 'ok', 'detail' => 'head injected'];
        } elseif ($type === 'update_meta') {
            $metaFile = GP_DOCROOT . '/geopulse-meta.json';
            file_put_contents(
                $metaFile,
                json_encode($action['fields'] ?? [], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE)
            );
            $results[] = ['id' => $id, 'status' => 'ok', 'detail' => 'meta json written'];
        } else {
            $results[] = ['id' => $id, 'status' => 'skipped', 'detail' => 'unsupported'];
        }
    } catch (Throwable $e) {
        $results[] = ['id' => $id, 'status' => 'error', 'detail' => $e->getMessage()];
    }
}

$ack = gp_request('POST', '/api/v1/apply/' . GP_SITE_ID . '/ack', [
    'results' => $results,
    'agent' => 'php-standalone/1.0',
]);

header('Content-Type: application/json; charset=utf-8');
echo json_encode([
    'applied' => $results,
    'ack' => $ack,
    'hint' => 'Includi geopulse-head.html nel <head> del tema.',
], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
echo "\n";
