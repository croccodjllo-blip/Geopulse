from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app import CreditLedger, User, app, db, ensure_schema
from services.sov_budget import (
    SovDailyBudgetExceeded,
    assert_sov_budget_allows,
    sov_budget_status,
    sov_spent_today_cents,
)


def _user() -> User:
    user = User(
        email=f"sov-budget-{uuid4().hex}@example.com",
        name="Budget test",
        plan="plus",
        credit_balance_cents=1_000,
        credit_held_cents=0,
    )
    user.set_password("x" * 12)
    db.session.add(user)
    db.session.commit()
    return user


def _ledger(
    user: User,
    *,
    amount_cents: int,
    description: str,
    created_at: datetime,
) -> None:
    db.session.add(
        CreditLedger(
            user_id=user.id,
            amount_cents=amount_cents,
            balance_after_cents=1_000,
            description=description,
            created_at=created_at,
        )
    )


def test_spent_today_counts_only_matching_debits():
    with app.app_context():
        ensure_schema()
        user = _user()
        now = datetime.now(timezone.utc)
        _ledger(
            user,
            amount_cents=-7,
            description="[sov] SoV citation usage openai:gpt-4o-mini",
            created_at=now,
        )
        _ledger(
            user,
            amount_cents=-3,
            description="API usage realtime ANTHROPIC:claude-haiku",
            created_at=now,
        )
        _ledger(
            user,
            amount_cents=-9,
            description="JOB usage realtime openai:gpt-4o-mini",
            created_at=now,
        )
        _ledger(
            user,
            amount_cents=-11,
            description="Crawl tecnico",
            created_at=now,
        )
        _ledger(
            user,
            amount_cents=50,
            description="Ricarica OpenAI",
            created_at=now,
        )
        _ledger(
            user,
            amount_cents=-13,
            description="[sov] Citation probe storico",
            created_at=now - timedelta(days=1),
        )
        db.session.commit()

        # Only today's tagged SoV row (7). Provider-named pack/job usage excluded.
        assert sov_spent_today_cents(db.session, CreditLedger, user.id) == 7


def test_budget_status_zero_is_unlimited(monkeypatch):
    monkeypatch.setenv("SOV_DAILY_BUDGET_CENTS", "0")
    status = sov_budget_status(object(), 37)
    assert status == {
        "budget_cents": 0,
        "spent_cents": 37,
        "remaining_cents": 0,
        "unlimited": True,
    }
    assert_sov_budget_allows(object(), 37, 10_000)


def test_budget_status_and_exact_limit(monkeypatch):
    monkeypatch.setenv("SOV_DAILY_BUDGET_CENTS", "100")
    status = sov_budget_status(object(), 65)
    assert status == {
        "budget_cents": 100,
        "spent_cents": 65,
        "remaining_cents": 35,
        "unlimited": False,
    }
    assert_sov_budget_allows(object(), 65, 35)


def test_budget_rejects_next_debit_over_limit(monkeypatch):
    monkeypatch.setenv("SOV_DAILY_BUDGET_CENTS", "100")
    with pytest.raises(SovDailyBudgetExceeded, match="Budget SoV giornaliero"):
        assert_sov_budget_allows(object(), 95, 6)


def test_invalid_or_negative_budget_falls_back(monkeypatch):
    # Invalid → treated as default-safe capped value path via except → 5000? 
    # Code sets configured=5000 on ValueError; negative clamps to 0 (unlimited).
    monkeypatch.setenv("SOV_DAILY_BUDGET_CENTS", "non-un-numero")
    assert sov_budget_status(object(), 1)["budget_cents"] == 5000
    assert sov_budget_status(object(), 1)["unlimited"] is False
    monkeypatch.setenv("SOV_DAILY_BUDGET_CENTS", "-50")
    assert sov_budget_status(object(), 1)["unlimited"] is True
    assert sov_budget_status(object(), 1)["budget_cents"] == 0


def test_citation_callback_runs_in_sov_usage_context(monkeypatch):
    import services.citation_monitor as citation_monitor

    observed: list[bool] = []

    def fake_openai(prompts, needles, usage_callback=None):
        assert usage_callback is not None
        usage_callback(
            provider="openai",
            model="test-model",
            input_tokens=1,
            output_tokens=1,
        )
        return {
            "available": True,
            "mention_rate": 100,
            "hits": 1,
            "samples": 1,
            "details": [],
        }

    def capture_usage(**kwargs):
        del kwargs
        observed.append(citation_monitor.is_sov_usage_call())

    monkeypatch.setattr(citation_monitor, "_sov_engine_parallelism", lambda: 1)
    monkeypatch.setattr(citation_monitor, "_probe_openai", fake_openai)
    for name in (
        "_probe_perplexity",
        "_probe_anthropic",
        "_probe_gemini",
        "_probe_xai",
        "_probe_copilot",
    ):
        monkeypatch.setattr(
            citation_monitor,
            name,
            lambda *args, **kwargs: {
                "available": False,
                "reason": "test",
                "details": [],
            },
        )

    citation_monitor.run_citation_monitor(
        brand="Centropic",
        domain="centropic.ai",
        prompts=["test"],
        usage_callback=capture_usage,
    )

    assert observed == [True]
    assert citation_monitor.is_sov_usage_call() is False
