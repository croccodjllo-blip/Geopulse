"""International dialing prefixes for registration phone field."""

from __future__ import annotations

import re

# Curated E.164 country calling codes (label IT-first for Centropic).
PHONE_PREFIX_CHOICES: list[tuple[str, str]] = [
    ("+39", "Italia (+39)"),
    ("+33", "Francia (+33)"),
    ("+49", "Germania (+49)"),
    ("+34", "Spagna (+34)"),
    ("+41", "Svizzera (+41)"),
    ("+43", "Austria (+43)"),
    ("+32", "Belgio (+32)"),
    ("+31", "Paesi Bassi (+31)"),
    ("+351", "Portogallo (+351)"),
    ("+44", "Regno Unito (+44)"),
    ("+353", "Irlanda (+353)"),
    ("+1", "USA / Canada (+1)"),
    ("+55", "Brasile (+55)"),
    ("+54", "Argentina (+54)"),
    ("+52", "Messico (+52)"),
    ("+57", "Colombia (+57)"),
    ("+56", "Cile (+56)"),
    ("+51", "Perù (+51)"),
    ("+61", "Australia (+61)"),
    ("+64", "Nuova Zelanda (+64)"),
    ("+81", "Giappone (+81)"),
    ("+82", "Corea del Sud (+82)"),
    ("+86", "Cina (+86)"),
    ("+852", "Hong Kong (+852)"),
    ("+65", "Singapore (+65)"),
    ("+91", "India (+91)"),
    ("+971", "Emirati Arabi (+971)"),
    ("+966", "Arabia Saudita (+966)"),
    ("+972", "Israele (+972)"),
    ("+90", "Turchia (+90)"),
    ("+48", "Polonia (+48)"),
    ("+420", "Cechia (+420)"),
    ("+36", "Ungheria (+36)"),
    ("+40", "Romania (+40)"),
    ("+30", "Grecia (+30)"),
    ("+46", "Svezia (+46)"),
    ("+47", "Norvegia (+47)"),
    ("+45", "Danimarca (+45)"),
    ("+358", "Finlandia (+358)"),
    ("+7", "Russia / Kazakistan (+7)"),
    ("+380", "Ucraina (+380)"),
    ("+27", "Sudafrica (+27)"),
    ("+234", "Nigeria (+234)"),
    ("+212", "Marocco (+212)"),
    ("+216", "Tunisia (+216)"),
    ("+20", "Egitto (+20)"),
]

DEFAULT_PHONE_PREFIX = "+39"

_ALLOWED_PREFIXES = frozenset(code for code, _ in PHONE_PREFIX_CHOICES)
_NATIONAL_RE = re.compile(r"[^\d]")


def normalize_phone_prefix(raw: str | None) -> str:
    code = (raw or "").strip()
    if not code:
        return DEFAULT_PHONE_PREFIX
    if not code.startswith("+"):
        code = f"+{code}"
    if code in _ALLOWED_PREFIXES:
        return code
    return DEFAULT_PHONE_PREFIX


def compose_phone(prefix: str | None, national: str | None) -> str | None:
    """Build stored phone ``+CC NNNNN`` or None when national is empty.

    If the national part already starts with ``+``, keep it as-is (user pasted
    a full international number) and ignore the selected prefix.
    """
    national_raw = (national or "").strip()
    if not national_raw:
        return None
    if national_raw.startswith("+"):
        digits = _NATIONAL_RE.sub("", national_raw)
        if len(digits) < 6:
            return None
        return f"+{digits}"[:40]

    digits = _NATIONAL_RE.sub("", national_raw)
    if not digits:
        return None
    # Drop a single leading 0 (national trunk prefix) before attaching E.164 CC.
    if digits.startswith("0") and len(digits) > 1:
        digits = digits.lstrip("0") or digits
    if len(digits) < 4:
        return None
    cc = normalize_phone_prefix(prefix).lstrip("+")
    composed = f"+{cc}{digits}"
    return composed[:40]
