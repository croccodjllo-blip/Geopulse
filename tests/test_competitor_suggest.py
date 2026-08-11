"""Auto competitor suggestion for Plus snapshot."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.competitor_suggest import (
    _snippet_context,
    normalize_competitor_url,
    suggest_competitors,
)
from services.ssrf import UnsafeURLError


def test_normalize_skips_same_host_and_social():
    assert normalize_competitor_url("https://centropic.ai/foo", seed_host="centropic.ai") is None
    assert normalize_competitor_url("https://facebook.com/x", seed_host="centropic.ai") is None
    assert (
        normalize_competitor_url("surferseo.com", seed_host="centropic.ai")
        == "https://surferseo.com/"
    )


def test_suggest_centropic_uses_vertical_seeds(monkeypatch):
    monkeypatch.setattr(
        "services.competitor_suggest._snippet_context",
        lambda url, timeout=12.0: {
            "url": url,
            "domain": "centropic.ai",
            "title": "Centropic",
            "description": "AIO GEO",
            "outbound_hosts": "",
        },
    )
    monkeypatch.setattr(
        "services.competitor_suggest.assert_public_http_url",
        lambda url, resolve=True: url if url.startswith("http") else "https://" + url,
    )
    out = suggest_competitors("https://centropic.ai/", api_key="", limit=3)
    assert out["domain"] == "centropic.ai"
    assert len(out["competitors"]) == 3
    joined = " ".join(out["competitors"])
    assert "surferseo.com" in joined
    assert "peec.ai" in joined
    assert "otterly.ai" in joined
    assert out["source"] in {"seed", "mixed", "heuristic"}


def test_snippet_context_uses_safe_get_not_raw_redirects():
    resp = MagicMock()
    resp.status_code = 200
    resp.text = "<title>Safe</title><meta name='description' content='ok'>"
    with patch(
        "services.competitor_suggest.assert_public_http_url",
        return_value="https://example.com/",
    ):
        with patch("services.competitor_suggest.safe_get", return_value=resp) as mock_get:
            with patch("services.competitor_suggest.requests.get") as raw_get:
                out = _snippet_context("https://example.com/")
    assert out["title"] == "Safe"
    mock_get.assert_called_once()
    assert mock_get.call_args.kwargs.get("max_redirects") == 3
    raw_get.assert_not_called()


def test_snippet_context_blocks_ssrf_redirect_target():
    with patch(
        "services.competitor_suggest.assert_public_http_url",
        return_value="https://open-redirect.example/",
    ):
        with patch(
            "services.competitor_suggest.safe_get",
            side_effect=UnsafeURLError("private hop"),
        ):
            out = _snippet_context("https://open-redirect.example/")
    assert out["title"] == ""
    assert out["description"] == ""


def test_suggest_skips_llm_when_allow_llm_false(monkeypatch):
    monkeypatch.setattr(
        "services.competitor_suggest._snippet_context",
        lambda url, timeout=12.0: {
            "url": url,
            "domain": "example.com",
            "title": "Example",
            "description": "demo",
            "outbound_hosts": "rival.example",
        },
    )
    monkeypatch.setattr(
        "services.competitor_suggest.assert_public_http_url",
        lambda url, resolve=True: url if url.startswith("http") else "https://" + url,
    )
    called = {"llm": 0}

    def _boom(*_a, **_k):
        called["llm"] += 1
        raise AssertionError("LLM must not run when allow_llm=False")

    monkeypatch.setattr("services.competitor_suggest._llm_competitors", _boom)
    out = suggest_competitors(
        "https://example.com/",
        api_key="sk-test",
        allow_llm=False,
        limit=3,
    )
    assert called["llm"] == 0
    assert out.get("llm_skipped") is True
    assert out["competitors"]
