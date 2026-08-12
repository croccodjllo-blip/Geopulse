"""Growth helpers: referral codes, sample report, email builders."""

from __future__ import annotations

from services.growth import (
    REFERRAL_BONUS_CENTS,
    build_analysis_complete_email,
    build_free_exhausted_email,
    build_low_balance_email,
    new_referral_code,
    sample_report_payload,
)


def test_referral_code_shape():
    code = new_referral_code()
    assert isinstance(code, str)
    assert 6 <= len(code) <= 12
    assert code == code.lower()


def test_referral_bonus_is_20_tokens():
    assert REFERRAL_BONUS_CENTS == 200


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

    free_to, free_subj, free = build_free_exhausted_email(
        to_email="a@b.co",
        name="Ada",
        pricing_url="https://centropic.ai/prezzi",
    )
    assert free_to == "a@b.co"
    assert "Plus" in free_subj
    assert "centropic.ai/prezzi" in free
    assert "trial" not in free.lower()
    assert "7 giorni" not in free


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
