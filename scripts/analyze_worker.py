#!/usr/bin/env python3
"""Worker CLI for the async analyze queue (systemd service / cron / kick).

Modes:
  oneshot (default): process up to ``--limit`` jobs then exit
  ``--loop``: long-running claim loop with ``--concurrency`` parallel claim slots
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


def _run_batch(limit: int) -> dict[str, int]:
    with app.app_context():
        return process_pending_analyze_jobs(
            limit=limit,
            openai_api_key=OPENAI_API_KEY,
            openai_model=OPENAI_MODEL,
        )


def _run_one_slot() -> dict[str, int]:
    """Claim and run at most one job (exclusive lease across processes)."""
    return _run_batch(1)


def run_loop(*, concurrency: int, idle_sleep: float) -> None:
    workers = max(1, int(concurrency))
    sleep_s = max(0.2, float(idle_sleep))
    logging.info(
        "Analyze worker loop starting concurrency=%s idle_sleep=%.2fs",
        workers,
        sleep_s,
    )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while True:
            futures = [pool.submit(_run_one_slot) for _ in range(workers)]
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
            else:
                time.sleep(sleep_s)


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
        default=int(os.getenv("ANALYZE_WORKER_CONCURRENCY", "4")),
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
