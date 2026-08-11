"""Recover customer credits when a job billed but delivered no report."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def job_refund_idempotency_key(job_id: int) -> str:
    return f"job-refund:{int(job_id)}"


def job_has_deliverable(
    job: Any,
    *,
    SiteAnalysis: Any | None = None,
) -> bool:
    """True when the customer already has a usable site/report for this job."""
    if getattr(job, "site_id", None):
        return True
    if SiteAnalysis is None:
        return False
    try:
        site = (
            SiteAnalysis.query.filter_by(
                user_id=int(job.user_id),
                url=str(job.url),
            )
            .order_by(SiteAnalysis.updated_at.desc())
            .first()
        )
    except Exception:
        logger.exception("job_has_deliverable lookup failed job=%s", getattr(job, "id", "?"))
        return False
    return site is not None


def refund_failed_job_billing(
    db_session: Any,
    CreditLedger: Any,
    user: Any,
    job: Any,
    *,
    SiteAnalysis: Any | None = None,
    topup_credit_fn: Any,
) -> int:
    """Credit back ``job.billed_cents`` when error job has no deliverable.

    Idempotent via ``stripe_payment_intent = job-refund:<id>``.
    Returns cents refunded (0 if skipped/already done).
    """
    if (getattr(job, "status", None) or "") != "error":
        return 0
    billed = int(getattr(job, "billed_cents", 0) or 0)
    if billed <= 0 or user is None:
        return 0
    if job_has_deliverable(job, SiteAnalysis=SiteAnalysis):
        return 0

    key = job_refund_idempotency_key(int(job.id))
    already = (
        db_session.query(CreditLedger)
        .filter_by(stripe_payment_intent=key)
        .first()
    )
    if already is not None:
        return 0

    topup_credit_fn(
        db_session,
        CreditLedger,
        user,
        amount_eur_cents=billed,
        description=f"Rimborso job #{job.id} fallito senza report",
        stripe_payment_intent=key,
    )
    # Keep billed_cents for audit; annotate error for ops.
    err = (getattr(job, "error", None) or "").strip()
    note = f"[crediti rimborsati: {billed} cent]"
    if note not in err:
        job.error = f"{err} {note}".strip()[:500]
    logger.warning(
        "Refunded undelivered billed job id=%s user=%s cents=%s",
        job.id,
        getattr(user, "id", None),
        billed,
    )
    return billed


def clear_paid_alert_settings(user: Any) -> bool:
    """Strip Plus/Business alert channels when the account falls back to Free."""
    changed = False
    if getattr(user, "alert_email_enabled", False):
        user.alert_email_enabled = False
        changed = True
    if (getattr(user, "webhook_url", None) or "").strip():
        user.webhook_url = None
        changed = True
    if (getattr(user, "webhook_secret", None) or "").strip():
        user.webhook_secret = None
        changed = True
    return changed
