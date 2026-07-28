from __future__ import annotations

from services.alerts import deliver_webhook


def test_webhook_blocks_ssrf_loopback():
    result = deliver_webhook(
        url="http://127.0.0.1/hook",
        secret="s",
        payload={"event": "analysis.alert"},
    )
    assert result["ok"] is False
    assert "ssrf" in result["error"]


def test_webhook_requires_https():
    result = deliver_webhook(
        url="http://example.com/hook",
        secret="s",
        payload={"event": "analysis.alert"},
    )
    # example.com is public; http is rejected by policy
    assert result["ok"] is False
    assert result["error"] in {"webhook_https_required"} or result["error"].startswith(
        "ssrf_blocked"
    )
