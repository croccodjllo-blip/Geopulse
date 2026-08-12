"""Regression: starting analyze from dashboard must not NameError on SoV prompts."""

from __future__ import annotations

from pathlib import Path

from app import _estimate_sov_prompts, app


def test_estimate_sov_prompts_returns_int():
    n = _estimate_sov_prompts()
    assert isinstance(n, int)
    assert n >= 1


def test_app_py_does_not_call_bare_sov_prompt_limit():
    """Billing estimate paths must use _estimate_sov_prompts (import-safe)."""
    src = Path("app.py").read_text(encoding="utf-8")
    bare = [
        line
        for line in src.splitlines()
        if "sov_prompt_limit()" in line
        and "from services.citation_monitor import sov_prompt_limit" not in line
        and "return int(sov_prompt_limit())" not in line
    ]
    assert bare == [], bare
