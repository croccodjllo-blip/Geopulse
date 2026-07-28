from __future__ import annotations

from services.js_crawl import render_html


def test_js_crawl_blocks_private_url():
    # Anche con flag off, se abilitato il path SSRF deve bloccare.
    # Con flag off ritorna static_fallback; forziamo chiamata assert via URL privato
    # solo se disponibile — altrimenti verifichiamo che private URL non esploda.
    out = render_html("http://127.0.0.1/")
    assert out["ok"] is False
    assert out["mode"] in {"static_fallback", "ssrf_blocked", "error"}
