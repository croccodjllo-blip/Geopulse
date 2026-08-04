"""GEO token display helpers.

Internal ledger stays in EUR cents. Product unit for users:

  1 GEO token == 1 EUR cent == €0.01
  1000 token == €10.00
"""

from __future__ import annotations


GEO_TOKEN_EUR_CENTS = 1
GEO_TOKENS_PER_EURO = 100


def cents_to_tokens(cents: int | None) -> int:
    """Convert ledger cents to GEO tokens (1:1)."""
    return int(cents or 0)


def tokens_to_cents(tokens: int | None) -> int:
    return int(tokens or 0) * GEO_TOKEN_EUR_CENTS


def format_token_amount(cents: int | None, *, with_unit: bool = True, signed: bool = False) -> str:
    """Human-readable token amount for UI (Italian thousands separator)."""
    n = int(cents or 0)
    sign = ""
    if signed and n > 0:
        sign = "+"
    elif n < 0:
        sign = "−"
        n = abs(n)
    body = f"{n:,}".replace(",", ".")
    if with_unit:
        unit = "token" if n == 1 else "token"
        return f"{sign}{body} {unit}"
    return f"{sign}{body}"


def format_tokens_short(cents: int | None) -> str:
    """Compact sidebar form, e.g. ``1.250 tok``."""
    n = int(cents or 0)
    body = f"{n:,}".replace(",", ".")
    return f"{body} tok"
