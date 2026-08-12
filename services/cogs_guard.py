"""FinOps: COGS guards — ban unpaid third-party enrichers without price rows.

SerpAPI / embedding SaaS / PDF generators must not be wired into analyze
without an entry in ``usage_billing._PRICE_TABLE`` (or explicit env override).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Providers that imply metered third-party COGS outside our LLM table.
_BANNED_IMPORT_PATTERNS = (
    r"\bimport\s+serpapi\b",
    r"\bfrom\s+serpapi\b",
    r"\bSERPAPI_API_KEY\b",
    r"openai\.embeddings\.create",
    r"\bEmbedding\b.*pinecone",
    r"\bcohere\.Client\b",
    r"\bfrom\s+pdfshift\b",
    r"\bPDFSHIFT\b",
)

_SCAN_GLOBS = (
    "services/**/*.py",
    "app.py",
    "centropic/**/*.py",
)


def cogs_guard_enabled() -> bool:
    raw = (os.getenv("COGS_UNPRICED_GUARD") or "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def scan_unpriced_cogs(root: Path | None = None) -> list[str]:
    """Return human-readable hits for banned unpriced integrations."""
    if not cogs_guard_enabled():
        return []
    base = root or Path(__file__).resolve().parents[1]
    hits: list[str] = []
    compiled = [re.compile(p) for p in _BANNED_IMPORT_PATTERNS]
    files: list[Path] = []
    for glob in _SCAN_GLOBS:
        files.extend(base.glob(glob))
    for path in sorted(set(files)):
        if not path.is_file():
            continue
        if "test_" in path.name or path.name == "cogs_guard.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for cre in compiled:
            if cre.search(text):
                hits.append(f"{path.relative_to(base)}: matches {cre.pattern}")
    return hits


def assert_no_unpriced_cogs(root: Path | None = None) -> None:
    hits = scan_unpriced_cogs(root)
    if hits:
        raise AssertionError(
            "Unpriced third-party COGS detected (add usage_billing prices or remove):\n"
            + "\n".join(hits)
        )
