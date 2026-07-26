"""Export avanzato: CSV storico e ZIP multi-sito / singolo run."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime
from typing import Any, Iterable


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.isoformat()


def runs_to_csv(runs: Iterable[Any]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "run_id",
            "site_id",
            "domain",
            "url",
            "aio_score",
            "geo_score",
            "rating_code",
            "rating_score",
            "source",
            "findings_count",
            "created_at",
            "page_title",
        ]
    )
    for run in runs:
        rating = run.rating if hasattr(run, "rating") else {}
        findings = run.findings if hasattr(run, "findings") else []
        writer.writerow(
            [
                run.id,
                getattr(run, "site_id", ""),
                run.domain,
                run.url,
                run.aio_score if run.aio_score is not None else "",
                run.geo_score if run.geo_score is not None else "",
                rating.get("code", ""),
                rating.get("score", ""),
                getattr(run, "source", "manual"),
                len(findings) if isinstance(findings, list) else 0,
                _iso(run.created_at),
                run.page_title or "",
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")


def pack_zip_bytes(entity: Any) -> bytes:
    """ZIP pack da SiteAnalysis o AnalysisRun."""
    buffer = io.BytesIO()
    rating = entity.rating if hasattr(entity, "rating") else {}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("llms.txt", entity.llms_txt or "")
        zf.writestr("organization.jsonld.html", entity.json_ld_artifact or "")
        faq = getattr(entity, "faq_artifact", None) or ""
        if faq:
            zf.writestr("faq.jsonld.html", faq)
        zf.writestr("meta-pack.html", entity.meta_pack_artifact or "")
        zf.writestr("robots.txt", entity.robots_artifact or "")
        report = {
            "url": entity.url,
            "domain": entity.domain,
            "aio_score": entity.aio_score,
            "geo_score": entity.geo_score,
            "pages_analyzed": getattr(entity, "pages_analyzed", 1),
            "pages": entity.crawl_pages if hasattr(entity, "crawl_pages") else [],
            "rating": rating.get("code"),
            "rating_score": rating.get("score"),
            "rating_label": rating.get("label"),
            "findings": entity.findings if hasattr(entity, "findings") else [],
            "notes": entity.analysis_notes,
            "source": getattr(entity, "source", "manual"),
            "generated_at": _iso(entity.created_at) or None,
        }
        zf.writestr(
            "report.json",
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        )
    return buffer.getvalue()


def multi_site_zip(sites: Iterable[Any]) -> bytes:
    """Un ZIP con una cartella per dominio/sito (stato corrente)."""
    buffer = io.BytesIO()
    used_names: set[str] = set()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for site in sites:
            base = (site.domain or f"site-{site.id}").replace(":", "_").replace("/", "_")
            folder = base
            n = 2
            while folder in used_names:
                folder = f"{base}-{n}"
                n += 1
            used_names.add(folder)
            pack = pack_zip_bytes(site)
            # Estrae i file del pack nella cartella
            inner = io.BytesIO(pack)
            with zipfile.ZipFile(inner, "r") as src:
                for info in src.infolist():
                    zf.writestr(f"{folder}/{info.filename}", src.read(info.filename))
            # Indice leggero
            zf.writestr(
                f"{folder}/INDEX.txt",
                (
                    f"GeoPulse export\n"
                    f"URL: {site.url}\n"
                    f"Domain: {site.domain}\n"
                    f"AIO: {site.aio_score}\n"
                    f"GEO: {site.geo_score}\n"
                    f"Updated: {_iso(site.created_at)}\n"
                ),
            )
    return buffer.getvalue()
