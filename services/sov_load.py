"""Global load guards for measured (LLM) Share-of-Voice probes.

Prefers Redis slot semaphore (``services.measured_queue``); falls back to
counting running ``run_measured`` jobs in Postgres when Redis is down.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def max_concurrent_measured() -> int:
    try:
        from services.measured_queue import max_concurrent_measured as _cap

        return _cap()
    except Exception:
        return max(0, int(os.getenv("MAX_CONCURRENT_MEASURED", "16")))


def measured_running_count(AnalysisJob: Any) -> int:
    """Running jobs that requested measured SoV (DB fallback signal)."""
    try:
        q = AnalysisJob.query.filter(AnalysisJob.status == "running")
        if hasattr(AnalysisJob, "source") and hasattr(AnalysisJob, "run_measured"):
            from sqlalchemy import or_

            q = q.filter(
                or_(
                    AnalysisJob.source == "measured",
                    AnalysisJob.run_measured.is_(True),
                )
            )
        elif hasattr(AnalysisJob, "run_measured"):
            q = q.filter(AnalysisJob.run_measured.is_(True))
        return int(q.count())
    except Exception:
        logger.exception("measured_running_count failed")
        return 0


def measured_slots_available(AnalysisJob: Any | None = None) -> bool:
    cap = max_concurrent_measured()
    if cap <= 0:
        return True
    try:
        from services.measured_queue import measured_slots_in_use

        in_use = measured_slots_in_use()
        if in_use is not None:
            return int(in_use) < cap
    except Exception:
        logger.exception("redis measured slot probe failed")
    if AnalysisJob is None:
        return True
    return measured_running_count(AnalysisJob) < cap


def should_shed_measured(*, AnalysisJob: Any | None = None) -> bool:
    """True when measured probes should be skipped on the *inline* path."""
    try:
        from services.measured_queue import should_shed_for_queue_depth

        if should_shed_for_queue_depth():
            logger.info("measured shed: analyze queue depth over threshold")
            return True
    except Exception:
        logger.exception("measured queue-depth shed check failed")
    if not measured_slots_available(AnalysisJob):
        logger.info(
            "measured shed: concurrent measured cap reached (%s)",
            max_concurrent_measured(),
        )
        return True
    return False
