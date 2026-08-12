"""Environment-backed runtime configuration."""

from __future__ import annotations

import os
from pathlib import Path

from services.analyzer import ABS_MAX_CRAWL_PAGES
from services.analysis_store import DEFAULT_RESCAN_HOUR

_PKG_DIR = Path(__file__).resolve().parent
BASE_DIR = str(_PKG_DIR.parent)

# Piano Free: 1 sito + 2 analisi lifetime (nessun reset giornaliero).
FREE_TOTAL_ANALYSES = max(1, int(os.getenv("FREE_TOTAL_ANALYSES", "2")))
MAX_SITES_FREE = max(1, int(os.getenv("MAX_SITES_FREE", "1")))
PRO_DAILY_ANALYSES = max(FREE_TOTAL_ANALYSES, int(os.getenv("PRO_DAILY_ANALYSES", "200")))
# Business (agenzie) inherits historical MAX_SITES_PRO; Plus startups get a tighter cap.
MAX_SITES_BUSINESS = max(MAX_SITES_FREE, int(os.getenv("MAX_SITES_PRO", "50")))
MAX_SITES_PRO = MAX_SITES_BUSINESS  # alias for older call sites / env docs
MAX_SITES_PLUS = max(
    MAX_SITES_FREE,
    min(MAX_SITES_BUSINESS, int(os.getenv("MAX_SITES_PLUS", "5"))),
)
FREE_CRAWL_PAGES = max(1, min(20, int(os.getenv("FREE_CRAWL_PAGES", "8"))))
_PRO_CRAWL_RAW = int(os.getenv("PRO_CRAWL_PAGES", "120"))
PRO_CRAWL_UNLIMITED = _PRO_CRAWL_RAW <= 0
PRO_CRAWL_PAGES = (
    ABS_MAX_CRAWL_PAGES
    if PRO_CRAWL_UNLIMITED
    else max(FREE_CRAWL_PAGES, min(ABS_MAX_CRAWL_PAGES, _PRO_CRAWL_RAW))
)
_PRO_DEEP_RAW = int(os.getenv("PRO_DEEP_CRAWL_PAGES", "500"))
PRO_DEEP_CRAWL_PAGES = max(
    PRO_CRAWL_PAGES if not PRO_CRAWL_UNLIMITED else FREE_CRAWL_PAGES,
    min(ABS_MAX_CRAWL_PAGES, max(1, _PRO_DEEP_RAW)),
)
PLUS_YEARLY_EUR = float(os.environ.get("PLUS_YEARLY_EUR", "143.90"))
BUSINESS_MONTHLY_EUR = float(os.environ.get("BUSINESS_MONTHLY_EUR", "49.99"))
BUSINESS_YEARLY_EUR = float(
    os.environ.get("BUSINESS_YEARLY_EUR", f"{BUSINESS_MONTHLY_EUR * 12 * 0.8:.2f}")
)
FREE_HISTORY_LIMIT = max(5, int(os.getenv("FREE_HISTORY_LIMIT", "10")))
PRO_HISTORY_LIMIT = max(FREE_HISTORY_LIMIT, int(os.getenv("PRO_HISTORY_LIMIT", "100")))
PACK_EMAIL_DAILY_LIMIT = max(1, int(os.getenv("PACK_EMAIL_DAILY_LIMIT", "10")))
ADMIN_EMAIL = (os.getenv("ADMIN_EMAIL") or "admin@centropic.ai").strip().lower()
ADMIN_PASSWORD = (os.getenv("ADMIN_PASSWORD") or "").strip()
ADMIN_NAME = os.getenv("ADMIN_NAME") or "Admin Centropic"
ADMIN_BOOTSTRAP = os.getenv("ADMIN_BOOTSTRAP", "0") == "1"
ASYNC_ANALYZE = os.getenv("ASYNC_ANALYZE", "1") == "1"
MEASURED_SOV_ON_ANALYZE = os.getenv("MEASURED_SOV_ON_ANALYZE", "1") == "1"
ANALYSIS_SOV_PROMPTS = 8
EMAIL_VERIFY_HOURS = max(1, int(os.getenv("EMAIL_VERIFY_HOURS", "48")))
ANALYZE_BATCH_LIMIT = max(1, int(os.getenv("ANALYZE_BATCH_LIMIT", "5")))
PASSWORD_RESET_HOURS = max(1, int(os.getenv("PASSWORD_RESET_HOURS", "2")))
SITE_AUTHOR_NAME = (os.getenv("SITE_AUTHOR_NAME") or "Engineering Factory").strip()
SITE_AUTHOR_TITLE = (
    os.getenv("SITE_AUTHOR_TITLE") or "Proprietario · Responsabile contenuti e prodotto"
).strip()
SITE_AUTHOR_URL = (
    os.getenv("SITE_AUTHOR_URL") or "https://www.engineeringfactory.app/"
).strip().rstrip("/") + "/"
SITE_OWNER_NAME = (os.getenv("SITE_OWNER_NAME") or SITE_AUTHOR_NAME).strip()
SITE_OWNER_URL = (os.getenv("SITE_OWNER_URL") or SITE_AUTHOR_URL).strip()

# Observability
SENTRY_DSN = (os.getenv("SENTRY_DSN") or "").strip()
METRICS_ENABLED = os.getenv("METRICS_ENABLED", "1") == "1"


def resolve_database_uri(raw: str | None) -> str:
    """Always use an absolute path for SQLite (avoid Flask instance/)."""
    uri = (raw or "").strip() or ("sqlite:///" + os.path.join(BASE_DIR, "database.db"))
    if uri.startswith("sqlite:///") and not uri.startswith("sqlite:////"):
        rel = uri.removeprefix("sqlite:///")
        if rel != ":memory:" and not os.path.isabs(rel):
            uri = "sqlite:///" + os.path.join(BASE_DIR, rel)
    return uri
