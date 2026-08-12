#!/usr/bin/env python3
"""Capacity check / dry stress for measured SoV scale-to-100.

Usage (on VPS or local with env)::

    python scripts/stress_measured_capacity.py
    python scripts/stress_measured_capacity.py --enqueue 0   # config only

Does not call external LLMs. Validates env caps and optionally enqueues
N synthetic measured jobs for an existing plus user (ops use).
"""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--enqueue", type=int, default=0, help="Synthetic jobs to push")
    parser.add_argument("--user-id", type=int, default=0)
    parser.add_argument("--url", default="")
    args = parser.parse_args()

    from services.jobs import MAX_RUNNING_ANALYZE_JOBS
    from services.measured_queue import (
        max_concurrent_measured,
        measured_defer_enabled,
        measured_queue_depth,
        measured_slots_in_use,
    )

    print("MEASURED_DEFER", measured_defer_enabled())
    print("MAX_CONCURRENT_MEASURED", max_concurrent_measured())
    print("MAX_RUNNING_ANALYZE_JOBS", MAX_RUNNING_ANALYZE_JOBS)
    print(
        "MEASURED_WORKER_CONCURRENCY",
        os.getenv("MEASURED_WORKER_CONCURRENCY", "50"),
    )
    print("measured_queue_depth", measured_queue_depth())
    print("measured_slots_in_use", measured_slots_in_use())

    ok = True
    if max_concurrent_measured() < 100 and max_concurrent_measured() != 0:
        print("WARN: MAX_CONCURRENT_MEASURED < 100")
        ok = False
    if MAX_RUNNING_ANALYZE_JOBS and MAX_RUNNING_ANALYZE_JOBS < 100:
        print("WARN: MAX_RUNNING_ANALYZE_JOBS < 100")
        ok = False
    if not measured_defer_enabled():
        print("WARN: MEASURED_DEFER is off — measured runs inline with crawl")
        ok = False

    if args.enqueue > 0:
        if not args.user_id or not args.url:
            print("ERROR: --enqueue requires --user-id and --url")
            return 2
        os.environ.setdefault("FLASK_DEBUG", "1")
        from app import AnalysisJob, User, app, db, enqueue_analysis

        with app.app_context():
            user = db.session.get(User, int(args.user_id))
            if user is None:
                print("ERROR: user not found")
                return 2
            for i in range(int(args.enqueue)):
                enqueue_analysis(
                    db.session,
                    AnalysisJob,
                    user_id=user.id,
                    url=args.url,
                    max_pages=1,
                    run_measured=True,
                    source="measured",
                    plan=getattr(user, "plan", "plus"),
                    is_admin=bool(getattr(user, "is_admin", False)),
                )
            print("enqueued", args.enqueue, "measured jobs")
            print("measured_queue_depth", measured_queue_depth())

    print("PASS" if ok else "CHECK")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
