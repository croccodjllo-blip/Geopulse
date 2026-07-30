"""ETA heuristics for the analyze processing overlay."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.analyze_eta import (
    compute_analyze_eta,
    estimate_total_seconds,
    format_eta_label,
)


def test_estimate_scales_with_pages_and_measured():
    small = estimate_total_seconds(max_pages=8, run_measured=False)
    big = estimate_total_seconds(max_pages=2000, run_measured=False)
    measured = estimate_total_seconds(max_pages=8, run_measured=True)
    assert 20 <= small <= 45
    assert big > small
    assert measured > small
    # Huge budgets are soft-capped so ETA stays human.
    assert big < 200


def test_format_eta_label_ranges():
    assert "secondi" in format_eta_label(40) or "s" in format_eta_label(40)
    assert "minuto" in format_eta_label(70)
    assert format_eta_label(8) == "Quasi fatto"


def test_compute_pending_and_crawl_progress():
    now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    pending = compute_analyze_eta(
        status="pending",
        max_pages=8,
        run_measured=False,
        created_at=now,
        now=now,
    )
    assert pending["eta_seconds"] >= 20
    assert pending["hint"]

    started = now - timedelta(seconds=20)
    crawl = compute_analyze_eta(
        status="running",
        max_pages=40,
        run_measured=True,
        progress_done=10,
        progress_total=40,
        progress_phase="crawl",
        started_at=started,
        created_at=started,
        now=now,
    )
    assert crawl["progress"]["done"] == 10
    assert "Crawl 10/40" in (crawl["hint"] or "")
    assert crawl["eta_seconds"] > 0


def test_done_job_has_zero_eta():
    out = compute_analyze_eta(status="done", max_pages=8)
    assert out["eta_seconds"] == 0
    assert out["eta_label"] == ""
