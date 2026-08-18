"""Fase 0: prod guards + /health hard-fail on ledger index / env."""

from __future__ import annotations

from uuid import uuid4

from app import app, ensure_schema
from centropic.prod_guards import evaluate_env_guards, prod_guards_enforced


def test_evaluate_env_guards_defaults_ok(monkeypatch):
    monkeypatch.delenv("ASYNC_ANALYZE", raising=False)
    monkeypatch.delenv("ADMIN_BOOTSTRAP", raising=False)
    monkeypatch.delenv("ALLOW_DROP_ANALYSIS_JOBS", raising=False)
    monkeypatch.delenv("SOV_DAILY_BUDGET_CENTS", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/centropic-guards.db")
    monkeypatch.setenv("ALLOW_SQLITE_PROD", "1")
    monkeypatch.setenv("TRUST_PROXY", "1")
    monkeypatch.setenv("BEHIND_NGINX", "1")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "pdl_ntfsec_test")
    monkeypatch.setenv("PADDLE_API_KEY", "pdl_live_test")
    monkeypatch.setenv("PADDLE_PRICE_PLUS_MONTHLY", "pri_plus_test")
    monkeypatch.setenv("HEALTH_DETAIL_TOKEN", "health-test-token")
    monkeypatch.delenv("REQUIRE_SENTRY", raising=False)
    result = evaluate_env_guards()
    assert result["ok"] is True
    assert result["failures"] == []


def test_evaluate_env_guards_rejects_missing_database_url(monkeypatch):
    monkeypatch.setenv("ASYNC_ANALYZE", "1")
    monkeypatch.setenv("ADMIN_BOOTSTRAP", "0")
    monkeypatch.setenv("ALLOW_DROP_ANALYSIS_JOBS", "0")
    monkeypatch.setenv("SOV_DAILY_BUDGET_CENTS", "5000")
    monkeypatch.setenv("TRUST_PROXY", "0")
    monkeypatch.setenv("BEHIND_NGINX", "0")
    monkeypatch.setenv("ALLOW_SQLITE_PROD", "1")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "pdl_ntfsec_test")
    monkeypatch.setenv("PADDLE_API_KEY", "pdl_live_test")
    monkeypatch.setenv("HEALTH_DETAIL_TOKEN", "health-test-token")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    result = evaluate_env_guards()
    assert result["ok"] is False
    assert "DATABASE_URL" in result["failures"]


def test_evaluate_env_guards_rejects_sqlite_without_allow(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/centropic-guards.db")
    monkeypatch.setenv("ALLOW_SQLITE_PROD", "0")
    monkeypatch.setenv("ASYNC_ANALYZE", "1")
    monkeypatch.setenv("ADMIN_BOOTSTRAP", "0")
    monkeypatch.setenv("ALLOW_DROP_ANALYSIS_JOBS", "0")
    monkeypatch.setenv("SOV_DAILY_BUDGET_CENTS", "5000")
    monkeypatch.setenv("TRUST_PROXY", "0")
    monkeypatch.setenv("BEHIND_NGINX", "0")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "pdl_ntfsec_test")
    monkeypatch.setenv("PADDLE_API_KEY", "pdl_live_test")
    monkeypatch.setenv("HEALTH_DETAIL_TOKEN", "health-test-token")
    result = evaluate_env_guards()
    assert result["ok"] is False
    assert "DATABASE_ENGINE" in result["failures"]


def test_evaluate_env_guards_rejects_missing_paddle_webhook(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("ASYNC_ANALYZE", "1")
    monkeypatch.setenv("ADMIN_BOOTSTRAP", "0")
    monkeypatch.setenv("ALLOW_DROP_ANALYSIS_JOBS", "0")
    monkeypatch.setenv("SOV_DAILY_BUDGET_CENTS", "5000")
    monkeypatch.setenv("TRUST_PROXY", "0")
    monkeypatch.setenv("BEHIND_NGINX", "0")
    monkeypatch.setenv("HEALTH_DETAIL_TOKEN", "health-test-token")
    monkeypatch.setenv("PADDLE_API_KEY", "pdl_live_test")
    monkeypatch.delenv("PADDLE_WEBHOOK_SECRET", raising=False)
    result = evaluate_env_guards()
    assert result["ok"] is False
    assert "PADDLE_WEBHOOK_SECRET" in result["failures"]


def test_evaluate_env_guards_rejects_trust_without_nginx(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/centropic-guards.db")
    monkeypatch.setenv("ALLOW_SQLITE_PROD", "1")
    monkeypatch.setenv("ASYNC_ANALYZE", "1")
    monkeypatch.setenv("ADMIN_BOOTSTRAP", "0")
    monkeypatch.setenv("ALLOW_DROP_ANALYSIS_JOBS", "0")
    monkeypatch.setenv("SOV_DAILY_BUDGET_CENTS", "5000")
    monkeypatch.setenv("TRUST_PROXY", "1")
    monkeypatch.setenv("BEHIND_NGINX", "0")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "pdl_ntfsec_test")
    monkeypatch.setenv("PADDLE_API_KEY", "pdl_live_test")
    monkeypatch.setenv("HEALTH_DETAIL_TOKEN", "health-test-token")
    result = evaluate_env_guards()
    assert result["ok"] is False
    assert "TRUST_PROXY_BEHIND_NGINX" in result["failures"]


def test_evaluate_env_guards_rejects_zero_sov_budget(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/centropic-guards.db")
    monkeypatch.setenv("ALLOW_SQLITE_PROD", "1")
    monkeypatch.setenv("ASYNC_ANALYZE", "1")
    monkeypatch.setenv("ADMIN_BOOTSTRAP", "0")
    monkeypatch.setenv("ALLOW_DROP_ANALYSIS_JOBS", "0")
    monkeypatch.setenv("SOV_DAILY_BUDGET_CENTS", "0")
    monkeypatch.setenv("TRUST_PROXY", "0")
    monkeypatch.setenv("BEHIND_NGINX", "0")
    monkeypatch.setenv("PADDLE_WEBHOOK_SECRET", "pdl_ntfsec_test")
    monkeypatch.setenv("PADDLE_API_KEY", "pdl_live_test")
    monkeypatch.setenv("HEALTH_DETAIL_TOKEN", "health-test-token")
    result = evaluate_env_guards()
    assert result["ok"] is False
    assert "SOV_DAILY_BUDGET_CENTS" in result["failures"]


def test_health_hard_fails_without_credit_ledger_index(monkeypatch):
    with app.app_context():
        ensure_schema()
    monkeypatch.setattr("app.CREDIT_LEDGER_PI_INDEX_OK", False, raising=False)
    monkeypatch.setattr(
        "centropic.prod_guards.refresh_credit_ledger_index_ok",
        lambda engine: False,
    )
    monkeypatch.setenv("CENTROPIC_SKIP_PROD_GUARDS", "1")
    client = app.test_client()
    resp = client.get("/health")
    assert resp.status_code == 503
    body = resp.get_json()
    assert body["ok"] is False
    assert "credit_ledger_pi_index" in body["failures"]


def test_health_hard_fails_on_env_when_enforced(monkeypatch):
    with app.app_context():
        ensure_schema()
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/centropic-guards.db")
    monkeypatch.setenv("HEALTH_REQUIRE_PROD_GUARDS", "1")
    monkeypatch.setenv("CENTROPIC_SKIP_PROD_GUARDS", "0")
    monkeypatch.setenv("ASYNC_ANALYZE", "0")
    monkeypatch.setenv("ADMIN_BOOTSTRAP", "0")
    monkeypatch.setenv("ALLOW_DROP_ANALYSIS_JOBS", "0")
    monkeypatch.setenv("SOV_DAILY_BUDGET_CENTS", "5000")
    monkeypatch.setenv("TRUST_PROXY", "0")
    monkeypatch.setenv("BEHIND_NGINX", "0")
    # Bypass pytest auto-skip inside prod_guards_enforced.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(
        "centropic.prod_guards.prod_guards_enforced",
        lambda: True,
    )
    client = app.test_client()
    resp = client.get("/health")
    assert resp.status_code == 503
    body = resp.get_json()
    assert body["ok"] is False
    assert any(x.startswith("env:") for x in body["failures"])


def test_health_ok_after_schema(monkeypatch):
    with app.app_context():
        ensure_schema()
    monkeypatch.setenv("CENTROPIC_SKIP_PROD_GUARDS", "1")
    token = f"fase0-{uuid4().hex}"
    monkeypatch.setenv("HEALTH_DETAIL_TOKEN", token)
    client = app.test_client()
    public = client.get("/health").get_json()
    assert public["ok"] is True
    detail = client.get("/health", headers={"X-Ops-Token": token}).get_json()
    assert detail["credit_ledger_pi_index_ok"] is True
    assert "prod_guards" in detail


def test_prod_guards_skipped_under_pytest_defaults():
    # conftest sets FLASK_DEBUG=1 → enforcement off unless explicitly forced.
    assert prod_guards_enforced() is False
