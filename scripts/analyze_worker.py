#!/usr/bin/env python3
"""Worker CLI for the async analyze queue (systemd service / cron / kick).

Modes:
  oneshot (default): process up to ``--limit`` jobs then exit
  ``--loop``: long-running claim loop with ``--concurrency`` parallel claim slots

When ``ANALYZE_QUEUE_BACKEND=redis`` and ``REDIS_URL`` is set, the loop prefers
BRPOP from the Redis list, then claims that AnalysisJob id in Postgres.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import (  # noqa: E402
    OPENAI_API_KEY,
    OPENAI_MODEL,
    app,
    process_pending_analyze_jobs,
)


def _run_batch(limit: int, preferred_job_id: int | None = None) -> dict[str, int]:
    with app.app_context():
        return process_pending_analyze_jobs(
            limit=limit,
            openai_api_key=OPENAI_API_KEY,
            openai_model=OPENAI_MODEL,
            preferred_job_id=preferred_job_id,
            # Dedicated measured worker owns source=measured jobs.
            source_exclude="measured",
        )


def _run_one_slot(preferred_job_id: int | None = None) -> dict[str, int]:
    """Claim and run at most one job (exclusive lease across processes)."""
    return _run_batch(1, preferred_job_id=preferred_job_id)


def _redis_mode() -> bool:
    try:
        from services.analyze_queue import redis_queue_enabled

        return bool(redis_queue_enabled())
    except Exception:
        return False


def run_loop(*, concurrency: int, idle_sleep: float) -> None:
    workers = max(1, int(concurrency))
    sleep_s = max(0.2, float(idle_sleep))
    use_redis = _redis_mode()
    # Reserve a slice of slots for measured follow-ups (rest = crawl).
    # When a dedicated measured worker is running, keep this at 0–2.
    measured_reserve = max(
        0,
        min(
            workers // 4,
            int(os.getenv("MEASURED_WORKER_RESERVE", "0")),
        ),
    )
    crawl_slots = max(1, workers - measured_reserve)
    logging.info(
        "Analyze worker loop starting concurrency=%s crawl_slots=%s "
        "measured_reserve=%s idle_sleep=%.2fs redis_queue=%s",
        workers,
        crawl_slots,
        measured_reserve,
        sleep_s,
        use_redis,
    )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while True:
            preferred_ids: list[int | None] = [None] * workers
            if use_redis:
                try:
                    from services.analyze_queue import pop_batch
                    from services.measured_queue import pop_measured_batch

                    crawl_ids = pop_batch(
                        crawl_slots, block_timeout=max(1.0, sleep_s)
                    )
                    measured_ids: list[int] = []
                    remain = workers - len(crawl_ids)
                    if remain > 0 and measured_reserve > 0:
                        measured_ids = pop_measured_batch(
                            min(remain, measured_reserve),
                            block_timeout=1.0 if not crawl_ids else 0.1,
                        )
                    # If crawl empty, allow measured to fill more slots.
                    if not crawl_ids and remain > len(measured_ids):
                        extra = pop_measured_batch(
                            remain - len(measured_ids),
                            block_timeout=max(1.0, sleep_s),
                        )
                        measured_ids.extend(extra)
                    merged = list(crawl_ids) + list(measured_ids)
                    for i, jid in enumerate(merged[:workers]):
                        preferred_ids[i] = jid
                except Exception:
                    logging.exception("redis pop failed; falling back to DB claim")

            futures = [
                pool.submit(_run_one_slot, preferred_ids[i]) for i in range(workers)
            ]
            totals = {"ok": 0, "error": 0, "empty": 0}
            claimed_any = False
            for fut in as_completed(futures):
                try:
                    stats = fut.result() or {}
                except Exception:
                    logging.exception("analyze worker slot failed")
                    totals["error"] += 1
                    continue
                for key in totals:
                    totals[key] += int(stats.get(key) or 0)
                if int(stats.get("ok") or 0) or int(stats.get("error") or 0):
                    claimed_any = True
            if claimed_any:
                logging.info(
                    "Analyze worker tick ok=%s error=%s empty=%s",
                    totals["ok"],
                    totals["error"],
                    totals["empty"],
                )
            elif not use_redis:
                time.sleep(sleep_s)
            # Redis path already blocked in BRPOP; tiny pause avoids busy spin
            # when all pops timed out and DB was empty.
            elif all(pid is None for pid in preferred_ids):
                time.sleep(min(0.5, sleep_s))


def main() -> int:
    parser = argparse.ArgumentParser(description="GeoPulse async analyze worker")
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.getenv("ANALYZE_BATCH_LIMIT", "5")),
        help="Max jobs to process in oneshot mode",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run forever, claiming jobs with --concurrency parallel slots",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("ANALYZE_WORKER_CONCURRENCY", "16")),
        help="Parallel claim slots in --loop mode (default ANALYZE_WORKER_CONCURRENCY)",
    )
    parser.add_argument(
        "--idle-sleep",
        type=float,
        default=float(os.getenv("ANALYZE_WORKER_IDLE_SLEEP", "2")),
        help="Seconds to sleep when the queue is empty (loop mode)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    if args.loop:
        try:
            run_loop(concurrency=args.concurrency, idle_sleep=args.idle_sleep)
        except KeyboardInterrupt:
            logging.info("Analyze worker loop stopped")
        return 0

    stats = _run_batch(args.limit)
    logging.info(
        "Analyze worker done ok=%s error=%s empty=%s",
        stats["ok"],
        stats["error"],
        stats["empty"],
    )
    print(
        f"ok={stats['ok']} error={stats['error']} empty={stats['empty']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
