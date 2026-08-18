"""Pre-auth IP rate limit on /api/v1 (before API-key lookup)."""

from __future__ import annotations

from uuid import uuid4

from app import app


def test_api_v1_preauth_ip_rate_limit(monkeypatch):
    # Isolate this test's bucket from other API tests on 127.0.0.1.
    probe_ip = f"203.0.113.{uuid4().int % 200 + 1}"
    monkeypatch.setattr("app.client_ip", lambda: probe_ip)
    monkeypatch.setattr("app.API_V1_IP_LIMIT", 3)
    monkeypatch.setattr("app.API_V1_IP_WINDOW", 3600)

    client = app.test_client()
    codes: list[int] = []
    for i in range(5):
        resp = client.get(
            "/api/v1/sites",
            headers={"X-Api-Key": f"ct_junk_{i}"},
        )
        codes.append(resp.status_code)

    assert codes[0] == 401
    assert codes[1] == 401
    assert codes[2] == 401
    assert codes[3] == 429
    assert (client.get("/api/v1/sites", headers={"X-Api-Key": "ct_x"}).get_json() or {}).get(
        "error"
    ) == "rate_limited"
