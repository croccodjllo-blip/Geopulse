"""PLG guest preview: hero URL → partial report → claim on register."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app import (
    AnalysisRun,
    GuestPreview,
    SiteAnalysis,
    User,
    app,
    db,
    ensure_schema,
)
from services.preview_analyze import (
    claim_guest_preview,
    pick_preview_findings,
    public_preview_payload,
    run_guest_preview,
)


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        ensure_schema()
        with app.test_client() as c:
            yield c


def test_pick_preview_findings_prefers_critical():
    findings = [
        {"severity": "info", "title": "Note", "detail": "x"},
        {"severity": "warn", "title": "Warn A", "detail": "w"},
        {"severity": "critical", "title": "Crit A", "detail": "c1"},
        {"severity": "critical", "title": "Crit B", "detail": "c2"},
        {"severity": "critical", "title": "Crit C", "detail": "c3"},
    ]
    picked = pick_preview_findings(findings, limit=2)
    assert len(picked) == 2
    assert picked[0]["title"] == "Crit A"
    assert picked[1]["title"] == "Crit B"


def test_public_preview_payload_hides_pack(monkeypatch):
    preview = GuestPreview(
        token="tok123",
        url="https://example.com/",
        domain="example.com",
        status="done",
        aio_score=44,
        geo_score=51,
        findings_json=json.dumps(
            [
                {"severity": "critical", "title": "llms.txt assente", "detail": "manca"},
                {"severity": "warn", "title": "robots", "detail": "gptbot"},
            ]
        ),
        result_json="{}",
        pack_json=json.dumps({"llms.txt": "SECRET_PACK"}),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
    )
    payload = public_preview_payload(preview)
    blob = json.dumps(payload)
    assert "SECRET_PACK" not in blob
    assert payload["aio_score"] == 44
    assert len(payload["findings_preview"]) == 2


def test_run_guest_preview_stores_scores(monkeypatch):
    with app.app_context():
        ensure_schema()

        def fake_analyze(url, max_pages=1, **kwargs):
            return {
                "scraped": {
                    "domain": "example.com",
                    "title": "Example",
                    "description": "Demo",
                    "final_url": url,
                },
                "aio_score": 61,
                "geo_score": 55,
                "findings": [
                    {
                        "severity": "critical",
                        "title": "llms.txt assente",
                        "detail": "Nessun file",
                    }
                ],
                "pages": [],
                "probes": {"llms": {"ok": False, "status": 404, "url": url + "llms.txt"}},
                "signals": {},
            }

        monkeypatch.setattr(
            "services.analyzer.analyze_site", fake_analyze
        )
        monkeypatch.setattr(
            "services.geo_suite.run_geo_suite",
            lambda **kwargs: kwargs.get("result") or {},
        )
        monkeypatch.setattr(
            "services.artifacts.build_optimization_pack",
            lambda *a, **k: {
                "llms.txt": "# demo",
                "centropic-fix.html": "<html></html>",
            },
        )

        preview = GuestPreview(
            token=f"t-{uuid4().hex[:12]}",
            url="https://example.com/",
            domain="example.com",
            status="pending",
            findings_json="[]",
            result_json="{}",
            pack_json="{}",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.session.add(preview)
        db.session.commit()
        run_guest_preview(
            db_session=db.session, GuestPreview=GuestPreview, preview_id=preview.id
        )
        db.session.refresh(preview)
        assert preview.status == "done"
        assert preview.aio_score == 61
        assert "llms.txt assente" in (preview.findings_json or "")
        pack = json.loads(preview.pack_json)
        assert "llms.txt" in pack


def test_claim_guest_preview_creates_site(monkeypatch):
    with app.app_context():
        ensure_schema()
        user = User(
            email=f"plg-{uuid4().hex}@example.com",
            name="PLG",
            plan="free",
            credit_balance_cents=0,
        )
        user.set_password("PlgTest!23456")
        db.session.add(user)
        db.session.commit()

        preview = GuestPreview(
            token=f"claim-{uuid4().hex[:10]}",
            url="https://claim-demo.example/",
            domain="claim-demo.example",
            status="done",
            aio_score=40,
            geo_score=42,
            findings_json=json.dumps(
                [{"severity": "critical", "title": "Gap", "detail": "x"}]
            ),
            result_json=json.dumps(
                {
                    "scraped": {"domain": "claim-demo.example", "title": "Demo"},
                    "aio_score": 40,
                    "geo_score": 42,
                    "findings": [{"severity": "critical", "title": "Gap", "detail": "x"}],
                }
            ),
            pack_json=json.dumps(
                {
                    "llms.txt": "# claimed",
                    "centropic-fix.html": "<html>fix</html>",
                }
            ),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.session.add(preview)
        db.session.commit()

        site = claim_guest_preview(
            db_session=db.session,
            GuestPreview=GuestPreview,
            SiteAnalysis=SiteAnalysis,
            AnalysisRun=AnalysisRun,
            user=user,
            token=preview.token,
        )
        assert site is not None
        assert site.user_id == user.id
        assert site.aio_score == 40
        assert site.llms_txt == "# claimed"
        run = AnalysisRun.query.filter_by(site_id=site.id).first()
        assert run is not None
        assert run.source == "preview"


def test_preview_start_rejects_private_url(client):
    resp = client.post("/anteprima", data={"url": "http://127.0.0.1/"}, follow_redirects=False)
    assert resp.status_code in {302, 303}
    assert "/anteprima/" not in (resp.headers.get("Location") or "")


def test_landing_has_hero_url_form(client):
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'action="/anteprima"' in html
    assert 'name="url"' in html
    assert "Analizza gratis" in html
    assert "tuodominio.it" in html
    # Primary hero CTA is the URL form, not a hard jump to /register.
    hero = html.split('id="hero-brand"', 1)[-1].split("section-band", 1)[0]
    assert "hero-url-form" in hero
    assert 'href="/register"' not in hero
