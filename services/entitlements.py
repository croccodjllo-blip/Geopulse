"""Central plan entitlements for Centropic (Free / Plus / Business).

Single source of truth for feature gates and soft limits so routes,
templates and workers do not drift.

Ladder (sales):
  Free      — prove AIO/GEO on one domain
  Plus      — startups running their own brands continuously
  Business  — agencies: everything (API, white-label, scale sites)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CAPABILITIES = (
    "multi_site",
    "full_crawl",
    "competitors",
    "measured_sov",
    "prompt_bank",
    "scheduled_rescan",
    "api_access",
    "agency_whitelabel",
    "full_edge_signals",
    "extended_history",
    "pack_email",
    "alerts_webhook",
)

# Plus = continuous brand optimization. Business exclusives = agency toolkit.
BUSINESS_ONLY_CAPABILITIES = frozenset(
    {
        "api_access",
        "agency_whitelabel",
    }
)

PLUS_CAPABILITIES = frozenset(
    c for c in CAPABILITIES if c not in BUSINESS_ONLY_CAPABILITIES
)

BUSINESS_CAPABILITIES = frozenset(CAPABILITIES)

PAID_PLANS = frozenset({"plus", "pro", "business"})


@dataclass(frozen=True)
class PlanEntitlements:
    plan: str
    label: str
    is_pro: bool
    is_business: bool
    max_sites: int
    analysis_limit: int
    analysis_limit_lifetime: bool
    crawl_pages: int
    crawl_unlimited: bool
    history_limit: int
    capabilities: frozenset[str]

    def can(self, capability: str) -> bool:
        return capability in self.capabilities

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan,
            "label": self.label,
            "is_pro": self.is_pro,
            "is_business": self.is_business,
            "max_sites": self.max_sites,
            "analysis_limit": self.analysis_limit,
            "analysis_limit_lifetime": self.analysis_limit_lifetime,
            "crawl_pages": self.crawl_pages,
            "crawl_unlimited": self.crawl_unlimited,
            "history_limit": self.history_limit,
            "capabilities": sorted(self.capabilities),
        }


def _plan_key(user: Any | None) -> str:
    if user is None:
        return "anonymous"
    if getattr(user, "is_admin", False) or (getattr(user, "plan", "") or "").lower() == "admin":
        return "admin"
    raw = (getattr(user, "plan", "") or "").lower()
    if raw == "business" or getattr(user, "is_business", False):
        return "business"
    if getattr(user, "is_pro", False) or raw in {"plus", "pro"}:
        return "plus"
    return "free"


def entitlements_for(
    user: Any | None,
    *,
    max_sites_free: int,
    max_sites_pro: int,
    free_total_analyses: int,
    pro_daily_analyses: int,
    free_crawl_pages: int,
    pro_crawl_pages: int,
    pro_crawl_unlimited: bool,
    free_history_limit: int,
    pro_history_limit: int,
    max_sites_plus: int | None = None,
) -> PlanEntitlements:
    """Resolve entitlements.

    ``max_sites_pro`` = Business (and Admin) site cap.
    ``max_sites_plus`` = Plus/startup cap (defaults to min(5, max_sites_pro)).
    """
    key = _plan_key(user)
    plus_sites = (
        int(max_sites_plus)
        if max_sites_plus is not None
        else max(max_sites_free, min(5, int(max_sites_pro)))
    )

    if key == "admin":
        return PlanEntitlements(
            plan="admin",
            label="Admin",
            is_pro=True,
            is_business=True,
            max_sites=max_sites_pro,
            analysis_limit=pro_daily_analyses,
            analysis_limit_lifetime=False,
            crawl_pages=pro_crawl_pages,
            crawl_unlimited=bool(pro_crawl_unlimited),
            history_limit=pro_history_limit,
            capabilities=BUSINESS_CAPABILITIES,
        )

    if key == "business":
        return PlanEntitlements(
            plan="business",
            label="Business",
            is_pro=True,
            is_business=True,
            max_sites=max_sites_pro,
            analysis_limit=pro_daily_analyses,
            analysis_limit_lifetime=False,
            crawl_pages=pro_crawl_pages,
            crawl_unlimited=bool(pro_crawl_unlimited),
            history_limit=pro_history_limit,
            capabilities=BUSINESS_CAPABILITIES,
        )

    if key == "plus":
        return PlanEntitlements(
            plan="plus",
            label="Plus",
            is_pro=True,
            is_business=False,
            max_sites=plus_sites,
            analysis_limit=pro_daily_analyses,
            analysis_limit_lifetime=False,
            crawl_pages=pro_crawl_pages,
            crawl_unlimited=bool(pro_crawl_unlimited),
            history_limit=pro_history_limit,
            capabilities=PLUS_CAPABILITIES,
        )

    return PlanEntitlements(
        plan="free" if key == "free" else "anonymous",
        label="Free",
        is_pro=False,
        is_business=False,
        max_sites=max_sites_free,
        analysis_limit=free_total_analyses,
        analysis_limit_lifetime=True,
        crawl_pages=free_crawl_pages,
        crawl_unlimited=False,
        history_limit=free_history_limit,
        capabilities=frozenset({"pack_email"}),
    )


def require_capability(ents: PlanEntitlements, capability: str) -> str | None:
    """Return a user-facing block message, or None if allowed."""
    if ents.can(capability):
        return None
    labels = {
        "multi_site": "più siti",
        "full_crawl": "crawl intero sito",
        "competitors": "snapshot competitor",
        "measured_sov": "SoV measured / citation monitor",
        "prompt_bank": "prompt bank personalizzato",
        "scheduled_rescan": "re-scan schedulato",
        "api_access": "API key pubblica",
        "agency_whitelabel": "white-label agenzia",
        "full_edge_signals": "Edge Signals completo",
        "extended_history": "storico esteso",
        "alerts_webhook": "alert email e webhook",
    }
    feature = labels.get(capability, capability)
    if capability in BUSINESS_ONLY_CAPABILITIES:
        return (
            f"{feature.capitalize()} è riservato al piano Business. "
            "Plus copre l’ottimizzazione continua del tuo brand; Business aggiunge "
            "API, white-label e scala multi-cliente."
        )
    return (
        f"{feature.capitalize()} è riservato a Plus o Business. "
        "Sul Free restano score, findings e pack sullo stesso dominio."
    )
