"""Business API: site metrics, run history, OpenAPI, tenant isolation."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app import AnalysisRun, SiteAnalysis, User, app, db, ensure_schema, generate_api_key
from services.api_metrics import pack_checksums, pack_ready_payload, site_metrics_payload


def _biz_user(*, plan: str = "business") -> tuple[User, str]:
    raw, _prefix, digest = generate_api_key()
    user = User(
        email=f"api-metrics-{plan}-{uuid4().hex}@example.com",
        name="API Metrics",
        plan=plan,
    )
    user.set_password("ApiMetrics!23456")
    user.email_verified_at = datetime.now(timezone.utc)
    user.api_key_hash = digest
    db.session.add(user)
    db.session.commit()
    return user, raw


def test_site_metrics_payload_has_cvi_checksums_no_bodies():
    site = SiteAnalysis(
        user_id=1,
        url="https://example.com/",
        domain="example.com",
        aio_score=80,
        geo_score=76,
        findings_json='[{"severity":"warn","title":"JSON-LD incompleto","category":"schema"}]',
        llms_txt="# example.com\n",
        json_ld_artifact='{"@type":"Organization"}',
        robots_artifact="User-agent: *\nAllow: /\n",
        crawl_pages_json='{"signals":{"sov_measured":{"brand_mention_rate":34,"evidence":"measured","engines":[]}}}',
    )
    payload = site_metrics_payload(site)
    assert payload["schema"] == "centropic.site/v1"
    assert payload["scores"]["aio"] == 80
    assert payload["scores"]["cvi"] in {"DD", "CC", "BB", "AA"}
    assert payload["criticality"]["warn"] == 1
    assert payload["sov"]["brand_mention_rate"] == 34
    assert "llms.txt" in payload["pack"]["checksums"]
    assert "# example.com" not in str(payload)
    assert "public_token" not in str(payload)


def test_pack_ready_payload_is_idempotent_and_bodyless():
    site = SiteAnalysis(
        id=12,
        user_id=1,
        url="https://example.com/",
        domain="example.com",
        llms_txt="hello",
        public_token="tok_test_apply",
        signals_hosted=True,
        signals_version=3,
    )
    payload = pack_ready_payload(
        site, public_base="https://centropic.ai", edge_full=True, run_id=99
    )
    assert payload["event"] == "pack.ready"
    assert payload["idempotency_key"] == "12:3"
    assert payload["checksums"]["llms.txt"] == pack_checksums(site)["llms.txt"]
    assert "hello" not in str(payload["checksums"])
    assert payload["endpoints"]["llms_txt"].endswith("/e/tok_test_apply/llms.txt")


def test_api_v1_site_metrics_and_runs_acl():
    with app.app_context():
        ensure_schema()
        biz, key = _biz_user()
        plus, plus_key = _biz_user(plan="plus")
        other, other_key = _biz_user()
        site = SiteAnalysis(
            user_id=biz.id,
            url=f"https://metrics-{uuid4().hex}.example.com/",
            domain="metrics.example.com",
            aio_score=70,
            geo_score=68,
            findings_json="[]",
            llms_txt="User-agent: *",
        )
        db.session.add(site)
        db.session.flush()
        run = AnalysisRun(
            site_id=site.id,
            user_id=biz.id,
            url=site.url,
            domain=site.domain,
            aio_score=70,
            geo_score=68,
            findings_json="[]",
            source="api",
        )
        db.session.add(run)
        db.session.commit()
        site_id = site.id
        other_id = other.id

        client = app.test_client()
        openapi = client.get("/api/v1/openapi.json")
        assert openapi.status_code == 200
        spec = openapi.get_json()
        assert "/api/v1/sites/{site_id}" in spec["paths"]

        denied = client.get(
            f"/api/v1/sites/{site_id}",
            headers={"Authorization": f"Bearer {plus_key}"},
        )
        assert denied.status_code == 403
        assert denied.get_json()["error"] == "business_required"

        foreign = client.get(
            f"/api/v1/sites/{site_id}",
            headers={"Authorization": f"Bearer {other_key}"},
        )
        assert foreign.status_code == 404

        ok = client.get(
            f"/api/v1/sites/{site_id}",
            headers={"Authorization": f"Bearer {key}"},
        )
        assert ok.status_code == 200
        body = ok.get_json()
        assert body["ok"] is True
        assert body["scores"]["aio"] == 70
        assert body["pack"]["checksums"]["llms.txt"]
        assert "User-agent" not in ok.get_data(as_text=True)

        runs = client.get(
            f"/api/v1/sites/{site_id}/runs",
            headers={"Authorization": f"Bearer {key}"},
        )
        assert runs.status_code == 200
        assert runs.get_json()["runs"][0]["source"] == "api"

        # other business user must not list our runs
        stolen = client.get(
            f"/api/v1/sites/{site_id}/runs",
            headers={"Authorization": f"Bearer {other_key}"},
        )
        assert stolen.status_code == 404
        assert other_id  # keep user row used
