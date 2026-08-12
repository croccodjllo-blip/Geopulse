"""Global load guards for measured (LLM) Share-of-Voice probes.

Keeps Stimato/crawl/pack on the critical path while shedding or capping
Misurato under burst so the platform can scale toward ~100 concurrent crawls.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def max_concurrent_measured() -> int:
    """0 = unlimited measured slots among running jobs."""
    return max(0, int(os.getenv("MAX_CONCURRENT_MEASURED", "16")))


def measured_running_count(AnalysisJob: Any) -> int:
    """Running jobs that requested measured SoV (best-effort load signal)."""
    try:
        q = AnalysisJob.query.filter(AnalysisJob.status == "running")
        if hasattr(AnalysisJob, "run_measured"):
            q = q.filter(AnalysisJob.run_measured.is_(True))
        return int(q.count())
    except Exception:
        logger.exception("measured_running_count failed")
        return 0


def measured_slots_available(AnalysisJob: Any | None = None) -> bool:
    cap = max_concurrent_measured()
    if cap <= 0:
        return True
    if AnalysisJob is None:
        return True
    return measured_running_count(AnalysisJob) < cap


def should_shed_measured(*, AnalysisJob: Any | None = None) -> bool:
    """Return True when measured probes should be skipped this run."""
    try:
        from services.analyze_queue import measured_shed_due_to_queue

        if measured_shed_due_to_queue():
            logger.info("measured shed: analyze queue depth over threshold")
            return True
    except Exception:
        logger.exception("measured queue-depth shed check failed")
    if AnalysisJob is not None and not measured_slots_available(AnalysisJob):
        logger.info(
            "measured shed: concurrent measured cap reached (%s)",
            max_concurrent_measured(),
        )
        return True
    return False
