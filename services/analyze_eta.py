"""Estimate remaining analysis time for the processing overlay."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# Soft cap: huge crawl budgets (admin 2000) rarely fill on typical sites, and
# the UI estimate would otherwise look absurd. Live progress refines this.
_ETA_PAGE_CAP = 80


def expected_crawl_pages(max_pages: int | None) -> int:
    try:
        n = int(max_pages or 1)
    except (TypeError, ValueError):
        n = 1
    return max(1, min(n, _ETA_PAGE_CAP))


def estimate_total_seconds(
    *,
    max_pages: int | None = 8,
    run_measured: bool = False,
    competitor_count: int = 0,
) -> int:
    """Heuristic wall-clock budget before live progress is available."""
    pages = expected_crawl_pages(max_pages)
    # Seed scrape + root probes + scoring + pack
    base = 14
    crawl = 0 if pages <= 1 else int(5 + (pages - 1) * 1.15)
    measured = 28 if run_measured else 0
    competitors = max(0, int(competitor_count)) * 6
    return max(20, base + crawl + measured + competitors)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _elapsed_seconds(
    *,
    status: str,
    started_at: datetime | None,
    created_at: datetime | None,
    now: datetime,
) -> float:
    if status == "pending":
        origin = _as_utc(created_at) or now
    else:
        origin = _as_utc(started_at) or _as_utc(created_at) or now
    return max(0.0, (now - origin).total_seconds())


def format_eta_label(seconds: int | None, *, lang: str = "it") -> str:
    if seconds is None:
        return ""
    s = max(0, int(seconds))
    if s < 15:
        return "Quasi fatto" if lang == "it" else "Almost done"
    if s < 60:
        lo = max(15, (s // 10) * 10)
        hi = lo + 20
        return f"Circa {lo}–{hi} s" if lang == "it" else f"About {lo}–{hi} s"
    minutes = max(1, round(s / 60))
    if minutes == 1:
        return "Circa 1 minuto" if lang == "it" else "About 1 minute"
    if minutes <= 8:
        return f"Circa {minutes} minuti" if lang == "it" else f"About {minutes} minutes"
    return (
        "Diversi minuti (sito grande o SoV measured)"
        if lang == "it"
        else "Several minutes (large site or measured SoV)"
    )


def compute_analyze_eta(
    *,
    status: str,
    max_pages: int | None = 8,
    run_measured: bool = False,
    competitor_count: int = 0,
    progress_done: int | None = None,
    progress_total: int | None = None,
    progress_phase: str | None = None,
    started_at: datetime | None = None,
    created_at: datetime | None = None,
    now: datetime | None = None,
    lang: str = "it",
) -> dict[str, Any]:
    """Return ETA fields for job status JSON / overlay hint."""
    now = now or datetime.now(timezone.utc)
    status = (status or "").strip().lower()

    if status in {"done", "error"}:
        return {
            "eta_seconds": 0,
            "eta_label": "",
            "eta_total_seconds": 0,
            "hint": None,
            "progress": {
                "done": int(progress_done or 0),
                "total": int(progress_total or 0),
                "phase": progress_phase or status,
            },
        }

    total = estimate_total_seconds(
        max_pages=max_pages,
        run_measured=bool(run_measured),
        competitor_count=competitor_count,
    )
    elapsed = _elapsed_seconds(
        status=status, started_at=started_at, created_at=created_at, now=now
    )

    done = max(0, int(progress_done or 0))
    target = max(0, int(progress_total or 0))
    phase = (progress_phase or ("queue" if status == "pending" else "crawl")).strip()

    # Progress-based fraction of the crawl-heavy part of the job.
    if status == "pending":
        remaining = total + 5
        fraction = 0.0
    elif phase == "pack":
        remaining = max(5, int(12 - elapsed * 0.05))
        fraction = 0.92
    elif phase in {"geo", "score", "probe"}:
        remaining = max(8, int(total * 0.22))
        fraction = 0.75
    elif target > 0 and done >= 0:
        # Crawl in progress: blend page fraction with wall clock.
        crawl_frac = min(0.95, done / max(target, 1))
        # Crawl ≈ 55% of budget, then geo/pack take the rest.
        fraction = 0.08 + crawl_frac * 0.55
        remaining = max(8, int(total * (1.0 - fraction)))
        if done > 0 and elapsed > 5:
            # Pace from observed crawl speed (pages/sec → remaining pages).
            rate = done / elapsed
            if rate > 0.05:
                left_pages = max(0, target - done)
                pace_rem = left_pages / rate
                post_crawl = 12 + (28 if run_measured else 8)
                remaining = max(8, int(0.55 * remaining + 0.45 * (pace_rem + post_crawl)))
    else:
        fraction = min(0.9, elapsed / max(total, 1))
        remaining = max(8, int(total - elapsed))

    # If the job already overran the heuristic, keep a soft moving target.
    if status == "running" and elapsed > total * 0.9:
        remaining = max(remaining, int(max(25, elapsed * 0.2)))

    remaining = int(min(max(remaining, 5), 900))
    label = format_eta_label(remaining, lang=lang)

    if status == "pending":
        hint = f"In coda · stima totale ~{format_eta_label(total, lang=lang).lower()}"
        if lang != "it":
            hint = f"Queued · total estimate {format_eta_label(total, lang=lang).lower()}"
    elif target > 0 and phase == "crawl":
        hint = f"Crawl {done}/{target} · {label} rimanenti"
        if lang != "it":
            hint = f"Crawl {done}/{target} · {label} remaining"
    elif phase in {"geo", "score", "probe"}:
        hint = f"Scoring / SoV · {label}"
        if lang != "it":
            hint = f"Scoring / SoV · {label}"
    elif phase == "pack":
        hint = f"Pack artifact · {label}"
    else:
        hint = label

    return {
        "eta_seconds": remaining,
        "eta_label": label,
        "eta_total_seconds": total,
        "elapsed_seconds": int(elapsed),
        "hint": hint,
        "progress": {"done": done, "total": target, "phase": phase, "fraction": round(fraction, 3)},
    }
