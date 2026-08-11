"""Re-scan periodico per siti Pro con schedule attivo."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from services.analyze_pipeline import run_analysis_pipeline

logger = logging.getLogger(__name__)

UsageCallback = Callable[..., None]
UsageCallbackFactory = Callable[[Any], UsageCallback]
EstimateFactory = Callable[[Any], Any]  # returns object with service_cost_eur_cents


def due_sites_query(SiteAnalysis: Any, User: Any, *, now: datetime | None = None):
    """Siti Pro/admin con interval attivo e next_rescan_at scaduto."""
    now = now or datetime.now(timezone.utc)
    return (
        SiteAnalysis.query.join(User, SiteAnalysis.user_id == User.id)
        .filter(
            SiteAnalysis.rescan_interval.in_(("daily", "weekly")),
            SiteAnalysis.next_rescan_at.isnot(None),
            SiteAnalysis.next_rescan_at <= now,
            User.plan.in_(("plus", "pro", "business", "admin")),
        )
        .order_by(SiteAnalysis.next_rescan_at.asc())
    )


def claim_due_site(
    db_session: Any,
    SiteAnalysis: Any,
    site_id: int,
    *,
    now: datetime | None = None,
    claim_horizon_hours: int = 20,
) -> bool:
    """Atomically claim a due site by advancing ``next_rescan_at``.

    Prevents overlapping rescan timer ticks from running the same site twice.
    Returns True only for the winner of the race.
    """
    now = now or datetime.now(timezone.utc)
    claimed_until = now + timedelta(hours=max(1, int(claim_horizon_hours)))
    n = (
        db_session.query(SiteAnalysis)
        .filter(
            SiteAnalysis.id == int(site_id),
            SiteAnalysis.next_rescan_at.isnot(None),
            SiteAnalysis.next_rescan_at <= now,
        )
        .update({"next_rescan_at": claimed_until}, synchronize_session=False)
    )
    if n:
        db_session.commit()
        return True
    db_session.rollback()
    return False


def process_due_rescans(
    *,
    db_session: Any,
    SiteAnalysis: Any,
    AnalysisRun: Any,
    User: Any,
    openai_api_key: str = "",
    openai_model: str = "gpt-4o-mini",
    limit: int = 20,
    daily_limit_for: Callable[[Any], int] | None = None,
    runs_today_for: Callable[[int], int] | None = None,
    measured: bool = False,
    public_base: str = "https://centropic.ai",
    SovSnapshot: Any | None = None,
    AlertDelivery: Any | None = None,
    UsageEvent: Any | None = None,
    usage_callback: UsageCallback | None = None,
    usage_callback_factory: UsageCallbackFactory | None = None,
    credit_preflight: Callable[[Any], tuple[bool, str]] | None = None,
    hold_credit_fn: Callable[[Any, int], int] | None = None,
    release_hold_fn: Callable[[Any, int], None] | None = None,
    estimate_cents_fn: Callable[[Any], int] | None = None,
) -> dict[str, int]:
    """Esegue i re-scan scaduti via pipeline completa (suite + alert).

    Billing:
      - Prefer ``usage_callback_factory(user)`` (per-owner debit).
      - Fallback ``usage_callback`` (shared).
      - Measured SoV requires a billing callback.
      - Pack/artifact LLM always receives the billing callback when present
        so OpenAI spend is never free on scheduled rescans.
      - ``credit_preflight(user) -> (ok, message)`` skips when balance is low.
      - Optional hold/release callbacks reserve prepaid spend for the run.
    """
    from services.analysis_store import mark_rescan_error

    stats = {"ok": 0, "error": 0, "skipped": 0}
    now = datetime.now(timezone.utc)
    sites = due_sites_query(SiteAnalysis, User, now=now).limit(max(1, limit)).all()

    has_any_billing = callable(usage_callback_factory) or callable(usage_callback)
    if measured and not has_any_billing:
        logger.warning(
            "Scheduled measured SoV disabled: no usage_callback (refuse free LLM spend)"
        )
    if openai_api_key and not has_any_billing:
        logger.warning(
            "Scheduled rescan has OpenAI key but no usage_callback — "
            "pack LLM calls will not be billed (callback absent)"
        )

    for site in sites:
        user = db_session.get(User, site.user_id)
        if user is None or not getattr(user, "is_pro", False):
            stats["skipped"] += 1
            continue

        if daily_limit_for and runs_today_for:
            if runs_today_for(user.id) >= daily_limit_for(user):
                logger.info(
                    "Skip rescan site_id=%s user_id=%s: daily limit",
                    site.id,
                    user.id,
                )
                stats["skipped"] += 1
                continue

        if callable(credit_preflight):
            ok_credit, credit_msg = credit_preflight(user)
            if not ok_credit:
                logger.info(
                    "Skip rescan site_id=%s user_id=%s: %s",
                    site.id,
                    user.id,
                    credit_msg,
                )
                mark_rescan_error(db_session, site, (credit_msg or "credito insufficiente")[:500])
                stats["skipped"] += 1
                continue

        if not claim_due_site(db_session, SiteAnalysis, site.id, now=now):
            stats["skipped"] += 1
            continue

        # Refresh after claim so persist_analysis sees current row.
        site = db_session.get(SiteAnalysis, site.id)
        if site is None:
            stats["skipped"] += 1
            continue

        held = 0
        if callable(hold_credit_fn) and callable(estimate_cents_fn):
            try:
                need = max(1, int(estimate_cents_fn(user)))
                held = int(hold_credit_fn(user, need) or 0)
            except Exception as exc:
                mark_rescan_error(db_session, site, f"hold fallito: {exc}"[:500])
                stats["skipped"] += 1
                continue

        if callable(usage_callback_factory):
            billing_cb: UsageCallback | None = usage_callback_factory(user)
        elif callable(usage_callback):
            billing_cb = usage_callback
        else:
            billing_cb = None

        # Track leftover of THIS rescan hold only — never release concurrent
        # dashboard/API holds that share the user's global credit_held_cents.
        held_left = held

        def _track_hold(cb: UsageCallback | None) -> UsageCallback | None:
            if cb is None or held <= 0:
                return cb

            def _wrapped(**kwargs: Any) -> None:
                nonlocal held_left
                from services.usage_billing import get_held_cents

                owner_before = db_session.get(User, user.id)
                before = int(get_held_cents(owner_before) or 0) if owner_before else 0
                cb(**kwargs)
                owner_after = db_session.get(User, user.id)
                after = int(get_held_cents(owner_after) or 0) if owner_after else before
                dropped = max(0, before - after)
                if dropped:
                    held_left = max(0, int(held_left) - dropped)

            return _wrapped

        billing_cb = _track_hold(billing_cb)
        run_measured = bool(measured) and callable(billing_cb)

        try:
            run_analysis_pipeline(
                db_session=db_session,
                SiteAnalysis=SiteAnalysis,
                AnalysisRun=AnalysisRun,
                user=user,
                url=site.url,
                openai_api_key=openai_api_key,
                openai_model=openai_model,
                competitor_urls=[],
                run_measured=run_measured,
                measured_env_enabled=True,
                source="scheduled",
                public_base=public_base,
                usage_callback=billing_cb,
                SovSnapshot=SovSnapshot,
                AlertDelivery=AlertDelivery,
                UsageEvent=UsageEvent,
                organization_id=getattr(site, "organization_id", None),
            )
            stats["ok"] += 1
            logger.info("Rescan ok site_id=%s url=%s", site.id, site.url)
        except Exception as exc:
            mark_rescan_error(db_session, site, str(exc)[:500])
            stats["error"] += 1
            logger.exception("Rescan failed site_id=%s", site.id)
        finally:
            if held_left > 0 and callable(release_hold_fn):
                try:
                    owner = db_session.get(User, user.id)
                    if owner is not None:
                        from services.usage_billing import get_held_cents

                        # Cap by global held so we never drive held negative,
                        # but never release more than this rescan still owns.
                        rem_global = int(get_held_cents(owner) or 0)
                        to_release = min(int(held_left), rem_global)
                        if to_release > 0:
                            release_hold_fn(owner, to_release)
                except Exception:
                    logger.exception("rescan release_hold failed site_id=%s", site.id)

    return stats
