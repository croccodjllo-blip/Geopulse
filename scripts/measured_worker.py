#!/usr/bin/env python3
"""Dedicated worker for deferred measured (LLM) SoV jobs.

Pops only from ``centropic:analyze:measured:p*`` Redis lanes and claims the
matching AnalysisJob in Postgres. Use alongside crawl workers so measured
scale does not steal crawl slots.

Env:
  MEASURED_WORKER_CONCURRENCY   default 50 (target fleet × hosts ≈ 100)
  MEASURED_WORKER_IDLE_SLEEP    default 2
  MAX_CONCURRENT_MEASURED       global Redis slot cap (default 100)
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


def _run_one(preferred_job_id: int | None = None) -> dict[str, int]:
    with app.app_context():
        return process_pending_analyze_jobs(
            limit=1,
            openai_api_key=OPENAI_API_KEY,
            openai_model=OPENAI_MODEL,
            preferred_job_id=preferred_job_id,
            source_filter="measured",
        )


def _redis_ok() -> bool:
    try:
        from services.analyze_queue import redis_queue_enabled

        return bool(redis_queue_enabled())
    except Exception:
        return False


def run_loop(*, concurrency: int, idle_sleep: float) -> None:
    workers = max(1, int(concurrency))
    sleep_s = max(0.2, float(idle_sleep))
    use_redis = _redis_ok()
    logging.info(
        "Measured worker loop concurrency=%s idle_sleep=%.2fs redis=%s",
        workers,
        sleep_s,
        use_redis,
    )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while True:
            preferred_ids: list[int | None] = [None] * workers
            if use_redis:
                try:
                    from services.measured_queue import pop_measured_batch

                    ids = pop_measured_batch(
                        workers, block_timeout=max(1.0, sleep_s)
                    )
                    for i, jid in enumerate(ids):
                        preferred_ids[i] = jid
                except Exception:
                    logging.exception("measured redis pop failed")

            futures = [
                pool.submit(_run_one, preferred_ids[i]) for i in range(workers)
            ]
            totals = {"ok": 0, "error": 0, "empty": 0}
            claimed_any = False
            for fut in as_completed(futures):
                try:
                    stats = fut.result() or {}
                except Exception:
                    logging.exception("measured worker slot failed")
                    totals["error"] += 1
                    continue
                for key in totals:
                    totals[key] += int(stats.get(key) or 0)
                if int(stats.get("ok") or 0) or int(stats.get("error") or 0):
                    claimed_any = True
            if claimed_any:
                logging.info(
                    "Measured worker tick ok=%s error=%s empty=%s",
                    totals["ok"],
                    totals["error"],
                    totals["empty"],
                )
            elif not use_redis:
                time.sleep(sleep_s)
            elif all(pid is None for pid in preferred_ids):
                time.sleep(min(0.5, sleep_s))


def main() -> int:
    parser = argparse.ArgumentParser(description="Centropic measured SoV worker")
    parser.add_argument("--loop", action="store_true", help="Long-running loop")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=int(os.getenv("MEASURED_WORKER_CONCURRENCY", "50")),
    )
    parser.add_argument(
        "--idle-sleep",
        type=float,
        default=float(os.getenv("MEASURED_WORKER_IDLE_SLEEP", "2")),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.getenv("MEASURED_BATCH_LIMIT", "5")),
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if args.loop:
        run_loop(concurrency=args.concurrency, idle_sleep=args.idle_sleep)
        return 0
    stats = _run_one(None) if args.limit <= 1 else None
    if args.limit > 1:
        with app.app_context():
            stats = process_pending_analyze_jobs(
                limit=args.limit,
                openai_api_key=OPENAI_API_KEY,
                openai_model=OPENAI_MODEL,
                source_filter="measured",
            )
    logging.info("Measured oneshot %s", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
