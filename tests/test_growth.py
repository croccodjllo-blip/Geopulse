"""Growth helpers: trial, referral codes, sample report, email builders."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from services.growth import (
    REFERRAL_BONUS_CENTS,
    TRIAL_DAYS,
    build_analysis_complete_email,
    build_free_exhausted_email,
    build_low_balance_email,
    build_trial_started_email,
    new_referral_code,
    sample_report_payload,
    trial_ends_at,
    trial_is_active,
)


def test_referral_code_shape():
    code = new_referral_code()
    assert isinstance(code, str)
    assert 6 <= len(code) <= 12
    assert code == code.lower()


def test_referral_bonus_is_20_tokens():
    assert REFERRAL_BONUS_CENTS == 200


def test_trial_active_window():
    now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
    ends = trial_ends_at(days=TRIAL_DAYS, now=now)
    user = SimpleNamespace(trial_ends_at=ends)
    assert trial_is_active(user, now=now)
    assert not trial_is_active(user, now=ends + timedelta(seconds=1))
    assert not trial_is_active(SimpleNamespace(trial_ends_at=None), now=now)


def test_sample_report_payload_shape():
    report = sample_report_payload()
    assert report["aio_score"] >= 0
    assert len(report["critical_findings"]) >= 3
    assert report["pack"] == ["centropic-fix.html"]


def test_email_builders_contain_cta():
    _, subj, body = build_analysis_complete_email(
        to_email="a@b.co",
        name="Ada Lovelace",
        domain="example.com",
        aio_score=61,
        geo_score=55,
        rating="CCC",
        findings=[{"severity": "critical", "title": "llms.txt", "detail": "manca"}],
        dashboard_url="https://centropic.ai/dashboard",
        pricing_url="https://centropic.ai/prezzi",
    )
    assert "example.com" in subj
    assert "llms.txt" in body
    assert "centropic.ai/prezzi" in body

    _, _, low = build_low_balance_email(
        to_email="a@b.co",
        name="Ada",
        balance_tokens=12.0,
        topup_url="https://centropic.ai/token",
        pricing_url="https://centropic.ai/prezzi",
    )
    assert "12" in low

    _, _, free = build_free_exhausted_email(
        to_email="a@b.co",
        name="Ada",
        pricing_url="https://centropic.ai/prezzi",
    )
    assert "Plus" in free

    ends = trial_ends_at(days=7)
    _, _, trial = build_trial_started_email(
        to_email="a@b.co",
        name="Ada",
        ends_at=ends,
        dashboard_url="https://centropic.ai/dashboard",
    )
    assert "7 giorni" in trial or "Plus trial" in trial


def test_transaction_grants_plus_yearly(monkeypatch):
    import services.paddle_billing as pb

    monkeypatch.setenv("PADDLE_PRICE_PLUS_MONTHLY", "pri_month")
    monkeypatch.setenv("PADDLE_PRICE_PLUS_YEARLY", "pri_year")
    assert pb.transaction_grants_plus(
        {"items": [{"price_id": "pri_year", "price": {"id": "pri_year"}}]}
    )
    assert pb.transaction_grants_plus(
        {"items": [{"price_id": "pri_month", "price": {"id": "pri_month"}}]}
    )
    assert not pb.transaction_grants_plus(
        {"items": [{"price_id": "pri_other", "price": {"id": "pri_other"}}]}
    )
