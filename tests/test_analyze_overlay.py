from __future__ import annotations


def test_analyze_overlay_partial_renders_on_dashboard(monkeypatch):
    from app import app

    # Minimal render of the partial in isolation via Jinja
    with app.app_context():
        html = app.jinja_env.get_template("partials/analyze_overlay.html").render(
            pending_job=None,
            url_for=lambda *a, **k: "/x",
            _=lambda s: s,
        )
    assert 'data-analyze-overlay' in html
    assert 'analyze-orbit' in html
    assert 'Elaborazione in corso' in html


def test_analyze_overlay_auto_open_attrs_when_job():
    from types import SimpleNamespace
    from app import app

    job = SimpleNamespace(id=9, status="running", url="https://example.com")
    with app.test_request_context("/dashboard"):
        html = app.jinja_env.get_template("partials/analyze_overlay.html").render(
            pending_job=job,
            url_for=lambda endpoint, **k: f"/{endpoint}/{k.get('job_id', '')}",
            _=lambda s: s,
        )
    assert 'data-auto-open="1"' in html
    assert "https://example.com" in html
    assert 'data-phase="running"' in html
