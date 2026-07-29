from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.alerts import deliver_webhook
from services.ssrf import UnsafeURLError


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
    assert result["ok"] is False
    assert result["error"] in {"webhook_https_required"} or result["error"].startswith(
        "ssrf_blocked"
    )


def test_webhook_uses_safe_post_when_https(monkeypatch):
    resp = MagicMock()
    resp.status_code = 204
    resp.text = ""
    with patch("services.alerts.safe_post", return_value=resp) as mock_post:
        # Bypass DNS/public resolve in assert_public_http_url (called before post)
        with patch(
            "services.alerts.assert_public_http_url",
            return_value="https://hooks.example.com/hook",
        ):
            result = deliver_webhook(
                url="https://hooks.example.com/hook",
                secret="sekrit",
                payload={"event": "analysis.alert", "x": 1},
            )
    assert result["ok"] is True
    assert result["status"] == 204
    mock_post.assert_called_once()
    kwargs = mock_post.call_args.kwargs
    assert kwargs["timeout"] == 12
    assert kwargs["max_redirects"] == 0
    assert "X-Centropic-Signature" in kwargs["headers"]
    assert kwargs["headers"]["X-Centropic-Signature"] == kwargs["headers"][
        "X-GeoPulse-Signature"
    ]


def test_webhook_safe_post_ssrf_error():
    with patch(
        "services.alerts.assert_public_http_url",
        return_value="https://hooks.example.com/hook",
    ):
        with patch(
            "services.alerts.safe_post",
            side_effect=UnsafeURLError("rebinding"),
        ):
            result = deliver_webhook(
                url="https://hooks.example.com/hook",
                secret="",
                payload={"event": "analysis.alert"},
            )
    assert result["ok"] is False
    assert "ssrf" in result["error"]
