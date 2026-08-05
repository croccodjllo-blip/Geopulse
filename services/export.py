"""Export avanzato: CSV storico e ZIP multi-sito / singolo run."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime
from typing import Any, Iterable

from services.artifacts import UNIFIED_FIX_FILENAME, unified_fix_html_from_entity
from services.security import csv_cell


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
                csv_cell(run.domain),
                csv_cell(run.url),
                run.aio_score if run.aio_score is not None else "",
                run.geo_score if run.geo_score is not None else "",
                csv_cell(rating.get("code", "")),
                rating.get("score", ""),
                csv_cell(getattr(run, "source", "manual")),
                len(findings) if isinstance(findings, list) else 0,
                _iso(run.created_at),
                csv_cell(run.page_title or ""),
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")


def pack_fix_html_bytes(entity: Any) -> bytes:
    """Single HTML file that consolidates every optimization fix."""
    return unified_fix_html_from_entity(entity).encode("utf-8")


def pack_fix_filename(entity: Any) -> str:
    domain = (getattr(entity, "domain", None) or "site").replace(":", "_").replace("/", "_")
    return f"centropic-{domain}-fix.html"


def pack_zip_bytes(entity: Any) -> bytes:
    """ZIP pack with exactly one file: the unified Centropic fix HTML."""
    buffer = io.BytesIO()
    html = pack_fix_html_bytes(entity)
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(UNIFIED_FIX_FILENAME, html)
    return buffer.getvalue()


def multi_site_zip(sites: Iterable[Any]) -> bytes:
    """Un ZIP con una cartella per dominio/sito (un solo fix.html ciascuno)."""
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
            zf.writestr(
                f"{folder}/{UNIFIED_FIX_FILENAME}",
                pack_fix_html_bytes(site),
            )
    return buffer.getvalue()
