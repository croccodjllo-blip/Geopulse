from __future__ import annotations


def test_client_ip_ignores_forged_headers():
    from app import app, client_ip

    with app.test_request_context(
        "/",
        environ_base={"REMOTE_ADDR": "203.0.113.10"},
        headers={"X-Real-IP": "198.51.100.1", "X-Forwarded-For": "198.51.100.1"},
    ):
        assert client_ip() == "203.0.113.10"


def test_absolute_url_uses_public_site(monkeypatch):
    import app as app_mod

    monkeypatch.setattr(app_mod, "PUBLIC_SITE_URL", "https://centropic.ai")
    with app_mod.app.test_request_context(
        "/",
        headers={"Host": "evil.example", "X-Forwarded-Host": "evil.example"},
    ):
        assert app_mod.public_base_url() == "https://centropic.ai"
        url = app_mod.absolute_url("login")
        assert url.startswith("https://centropic.ai/")
        assert "evil.example" not in url
