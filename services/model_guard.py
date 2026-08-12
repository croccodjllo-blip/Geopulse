"""FinOps: allow only cheap LLM models unless explicitly overridden.

Blocks accidental use of opus/sonnet/gpt-4 (non-mini) in production so
PLATFORM_SPREAD margins are not erased by premium model COGS.
"""

from __future__ import annotations

import logging
import os
import re

logger = logging.getLogger(__name__)

# Default allowlist: flash / mini / haiku / sonar / grok-fast class.
_DEFAULT_ALLOW = (
    "gpt-4o-mini",
    "gpt-3.5-turbo",
    "claude-haiku",
    "claude-3-haiku",
    "claude-3-5-haiku",
    "claude-haiku-4-5",
    "sonar",
    "sonar-pro",
    "gemini-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "grok-4-1-fast",
    "grok-fast",
)

_DEFAULT_DENY_SUBSTR = (
    "opus",
    "sonnet",
    "gpt-4-turbo",
    "gpt-4o-2024",  # full 4o, not mini
    "o1-",
    "o3-",
)


def model_guard_enabled() -> bool:
    raw = (os.getenv("LLM_MODEL_GUARD") or "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def _allow_patterns() -> list[str]:
    raw = (os.getenv("LLM_MODEL_ALLOWLIST") or "").strip()
    if not raw:
        return list(_DEFAULT_ALLOW)
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def _deny_patterns() -> list[str]:
    raw = (os.getenv("LLM_MODEL_DENYLIST") or "").strip()
    if not raw:
        return list(_DEFAULT_DENY_SUBSTR)
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def is_model_allowed(model: str) -> bool:
    if not model_guard_enabled():
        return True
    m = (model or "").strip().lower()
    if not m:
        return True
    for d in _deny_patterns():
        if d and d in m:
            # gpt-4o-mini contains neither deny nor is denied by gpt-4o-2024
            if d == "gpt-4o-2024" and "mini" in m:
                continue
            if "mini" in m and "gpt-4" in d:
                continue
            return False
    allow = _allow_patterns()
    for a in allow:
        if a and a in m:
            return True
    return False


def guard_model(model: str, *, fallback: str) -> str:
    """Return ``model`` if allowed, else ``fallback`` (must itself be cheap)."""
    if is_model_allowed(model):
        return model
    fb = fallback or "gpt-4o-mini"
    logger.warning(
        "LLM model guard blocked %r — using fallback %r (set LLM_MODEL_GUARD=0 to disable)",
        model,
        fb,
    )
    return fb
