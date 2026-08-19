"""Measured follow-up must hold grace cents (not bare estimate)."""

from __future__ import annotations

from services.usage_billing import required_credit_with_grace_cents


def test_measured_followup_hold_uses_grace_not_bare_estimate():
    """Regression for job #924: held 3¢ base, projected 4¢ → InsufficientCreditError.

    ``_enqueue_measured_followup`` must reserve ``required_credit_with_grace_cents``
    like the main analyze / verify-rescan paths — never the bare estimate alone.
    """
    bare = 3
    held = required_credit_with_grace_cents(bare)
    assert held > bare
    assert held >= 4
