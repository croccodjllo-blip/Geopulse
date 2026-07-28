"""Measured Share-of-Voice via LLM prompt probes.

Compat layer: delegates to citation_monitor (multi-engine).
Measured analysis is a Plus-only product capability.
"""

from __future__ import annotations

from typing import Any

from services.citation_monitor import (
    citation_monitor_available as measured_sov_available,
    run_citation_monitor,
    run_measured_sov,
)


def user_can_run_measured(user: Any | None) -> bool:
    """True solo per piani Plus/pro/admin (is_pro). Free → solo SoV proxy."""
    if user is None:
        return False
    return bool(getattr(user, "is_pro", False))


def should_run_measured(
    *,
    user: Any | None,
    requested: bool = False,
    env_enabled: bool = True,
) -> bool:
    """Gate unico: env + Plus + connector API disponibili + richiesta esplicita."""
    return bool(
        requested
        and env_enabled
        and user_can_run_measured(user)
        and measured_sov_available()
    )


__all__ = [
    "measured_sov_available",
    "run_measured_sov",
    "run_citation_monitor",
    "user_can_run_measured",
    "should_run_measured",
]
