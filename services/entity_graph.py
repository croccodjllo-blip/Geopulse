"""Brand Entity Graph — grafo leggero da JSON-LD + pagine crawl."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def _host(url: str) -> str:
    try:
        host = (urlparse(url).netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def build_entity_graph(
    *,
    scraped: dict[str, Any],
    pages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    entity = scraped.get("entity") or {}
    jsonld = scraped.get("jsonld") or {}
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []

    brand = entity.get("brand_name") or scraped.get("title") or scraped.get("domain") or ""
    brand_url = entity.get("brand_url") or scraped.get("final_url") or ""
    org_id = "org:brand"
    nodes.append(
        {
            "id": org_id,
            "type": "Organization",
            "name": brand,
            "url": brand_url,
            "email": entity.get("email") or "",
            "sameAs": entity.get("same_as") or [],
        }
    )

    types = set(jsonld.get("types") or [])
    if "WebSite" in types:
        nodes.append({"id": "website:main", "type": "WebSite", "url": brand_url})
        edges.append({"from": "website:main", "to": org_id, "rel": "publisher"})
    if "SoftwareApplication" in types:
        nodes.append({"id": "software:main", "type": "SoftwareApplication", "name": brand})
        edges.append({"from": "software:main", "to": org_id, "rel": "provider"})
    if "FAQPage" in types:
        nodes.append({"id": "faq:main", "type": "FAQPage"})
        edges.append({"from": "faq:main", "to": org_id, "rel": "about"})

    # Page topics as weak nodes
    for i, p in enumerate((pages or [])[:12]):
        title = (p.get("title") or "").strip()
        url = p.get("url") or ""
        if not title or not url:
            continue
        nid = f"page:{i}"
        nodes.append({"id": nid, "type": "WebPage", "name": title[:120], "url": url})
        edges.append({"from": nid, "to": org_id, "rel": "isPartOf"})

    external_same = [
        s
        for s in (entity.get("same_as") or [])
        if _host(s) and _host(s) != _host(brand_url)
    ]
    completeness = int(entity.get("org_completeness") or 0)
    score = min(
        100,
        completeness * 16
        + (12 if "WebSite" in types else 0)
        + (10 if external_same else 0)
        + (8 if len(nodes) >= 4 else 0),
    )

    if completeness >= 4 and external_same:
        findings.append(
            {
                "category": "aio",
                "severity": "ok",
                "title": "Entity graph solido",
                "detail": f"{len(nodes)} nodi · {len(edges)} relazioni · sameAs esterni {len(external_same)}.",
                "evidence": "measured",
            }
        )
    elif completeness >= 2:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "Entity graph incompleto",
                "detail": "Aggiungi sameAs esterni, SoftwareApplication/FAQ e contatti Organization.",
                "evidence": "estimated",
            }
        )
    else:
        findings.append(
            {
                "category": "aio",
                "severity": "warn",
                "title": "Entity graph debole",
                "detail": "Manca un’Organization chiara collegata al sito.",
                "evidence": "estimated",
            }
        )

    return {
        "brand": brand,
        "score": score,
        "nodes": nodes[:40],
        "edges": edges[:60],
        "external_same_as": external_same[:8],
        "types": sorted(types),
        "findings": findings,
    }
