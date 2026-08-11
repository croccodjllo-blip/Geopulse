#!/usr/bin/env python3
"""Worker CLI per re-scan periodico Plus/Business (da systemd timer / cron)."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import (  # noqa: E402
    OPENAI_API_KEY,
    OPENAI_MODEL,
    MEASURED_SOV_ON_ANALYZE,
    AlertDelivery,
    AnalysisRun,
    CreditLedger,
    SiteAnalysis,
    SovSnapshot,
    UsageEvent,
    User,
    analyses_today,
    app,
    db,
)
from services.citation_monitor import is_sov_usage_call, sov_prompt_limit  # noqa: E402
from services.rescan import process_due_rescans  # noqa: E402
from services.sov_budget import (  # noqa: E402
    SovDailyBudgetExceeded,
    assert_sov_budget_allows,
    sov_ledger_description,
    sov_spent_today_cents,
)
from services.usage_billing import (  # noqa: E402
    InsufficientCreditError,
    debit_cents_from_usage,
    deduct_credit,
    estimate_analysis_cost,
    get_balance_cents,
    has_sufficient_credit,
    hold_credit,
    is_unlimited_user,
    record_actual_usage,
    release_hold,
    required_credit_with_grace_cents,
    consume_hold,
)


def _engine_flags() -> dict[str, object]:
    return {
        "has_openai": bool(OPENAI_API_KEY),
        "has_perplexity": bool(os.getenv("PERPLEXITY_API_KEY")),
        "has_anthropic": bool(
            os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        ),
        "has_gemini": bool(
            os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_AI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        ),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
        "has_xai": bool(os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")),
        "xai_model": os.getenv("XAI_MODEL")
        or os.getenv("GROK_MODEL")
        or "grok-4-1-fast-non-reasoning",
        "has_azure": bool(
            os.getenv("AZURE_AI_PROJECT_ENDPOINT")
            or os.getenv("FOUNDRY_PROJECT_ENDPOINT")
        ),
        "azure_model": os.getenv("AZURE_AI_MODEL")
        or os.getenv("FOUNDRY_MODEL_NAME")
        or "gpt-4o-mini",
    }


def make_rescan_usage_callback(user: object):
    """Per-owner prepaid debit for every LLM call during scheduled rescan."""
    user_id = int(user.id)  # type: ignore[attr-defined]

    def _cb(*, provider: str, model: str, input_tokens: int, output_tokens: int) -> None:
        with app.app_context():
            owner = db.session.get(User, user_id)
            if owner is None:
                raise RuntimeError(f"rescan usage: user {user_id} missing")
            charged = record_actual_usage(
                db.session,
                UsageEvent,
                user_id=owner.id,
                analysis_run_id=None,
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            debit = debit_cents_from_usage(charged)
            if debit <= 0:
                return
            if is_sov_usage_call():
                spent = sov_spent_today_cents(db.session, CreditLedger, owner.id)
                try:
                    assert_sov_budget_allows(owner, spent, debit)
                except SovDailyBudgetExceeded as exc:
                    raise InsufficientCreditError(str(exc)) from exc
                description = sov_ledger_description(
                    "RESCAN SoV", provider=provider, model=model
                )
            else:
                description = f"RESCAN usage {provider}:{model}"
            deduct_credit(
                db.session,
                CreditLedger,
                owner,
                analysis_run_id=None,
                cost_eur_cents=debit,
                description=description,
            )
            consume_hold(db.session, owner, amount_cents=debit)
            db.session.commit()

    return _cb


def _rescan_credit_preflight(user: object) -> tuple[bool, str]:
    """Skip scheduled rescan when prepaid balance cannot cover estimate."""
    if is_unlimited_user(user):
        return True, ""
    flags = _engine_flags()
    est = estimate_analysis_cost(
        openai_model=OPENAI_MODEL,
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
        perplexity_model=os.getenv("PERPLEXITY_MODEL", "sonar"),
        run_measured=bool(MEASURED_SOV_ON_ANALYZE),
        n_prompts=int(sov_prompt_limit()),
        **flags,  # type: ignore[arg-type]
    )
    if has_sufficient_credit(user, est):
        # Also skip when daily SoV budget is already exhausted.
        try:
            spent = sov_spent_today_cents(db.session, CreditLedger, int(user.id))  # type: ignore[attr-defined]
            from services.sov_budget import sov_budget_status

            status = sov_budget_status(user, spent)
            if (
                bool(MEASURED_SOV_ON_ANALYZE)
                and not status["unlimited"]
                and int(status["remaining_cents"]) <= 0
            ):
                return False, "budget SoV giornaliero esaurito"
        except Exception:
            logging.exception("rescan SoV budget preflight failed")
            return False, "budget SoV non verificabile"
        return True, ""
    need = required_credit_with_grace_cents(est.service_cost_eur_cents)
    bal = get_balance_cents(user)
    return False, f"credito insufficiente per rescan (saldo {bal}, richiesti ~{need})"


def _hold_for_user(user: object, amount: int) -> int:
    held = hold_credit(
        db.session,
        CreditLedger,
        user,
        amount_cents=int(amount),
        description="Riserva rescan schedulato",
    )
    db.session.commit()
    return int(held or 0)


def _release_for_user(user: object, amount: int) -> None:
    release_hold(db.session, user, amount_cents=int(amount))
    db.session.commit()


def _estimate_cents(user: object) -> int:
    del user
    flags = _engine_flags()
    est = estimate_analysis_cost(
        openai_model=OPENAI_MODEL,
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
        perplexity_model=os.getenv("PERPLEXITY_MODEL", "sonar"),
        run_measured=bool(MEASURED_SOV_ON_ANALYZE),
        n_prompts=int(sov_prompt_limit()),
        **flags,  # type: ignore[arg-type]
    )
    return required_credit_with_grace_cents(est.service_cost_eur_cents)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Centropic Plus/Business periodic re-scan worker"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.getenv("RESCAN_BATCH_LIMIT", "20")),
        help="Max siti da processare in questo run",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    with app.app_context():
        stats = process_due_rescans(
            db_session=db.session,
            SiteAnalysis=SiteAnalysis,
            AnalysisRun=AnalysisRun,
            User=User,
            openai_api_key=OPENAI_API_KEY,
            openai_model=OPENAI_MODEL,
            limit=args.limit,
            daily_limit_for=lambda u: u.daily_limit,
            runs_today_for=analyses_today,
            # Plus-only gate is inside pipeline; Free sites are already filtered.
            measured=bool(MEASURED_SOV_ON_ANALYZE),
            usage_callback_factory=make_rescan_usage_callback,
            credit_preflight=_rescan_credit_preflight,
            hold_credit_fn=_hold_for_user,
            release_hold_fn=_release_for_user,
            estimate_cents_fn=_estimate_cents,
            SovSnapshot=SovSnapshot,
            AlertDelivery=AlertDelivery,
            UsageEvent=UsageEvent,
        )
        logging.info(
            "Rescan worker done ok=%s error=%s skipped=%s measured=%s billed=1",
            stats["ok"],
            stats["error"],
            stats["skipped"],
            bool(MEASURED_SOV_ON_ANALYZE),
        )
        print(
            f"ok={stats['ok']} error={stats['error']} skipped={stats['skipped']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
