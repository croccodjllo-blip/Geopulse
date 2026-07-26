#!/usr/bin/env python3
"""Worker CLI per re-scan periodico Pro (da systemd timer / cron)."""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Permette: python scripts/rescan_worker.py da root progetto
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import (  # noqa: E402
    OPENAI_API_KEY,
    OPENAI_MODEL,
    AnalysisRun,
    SiteAnalysis,
    User,
    analyses_today,
    app,
    db,
)
from services.rescan import process_due_rescans  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="GeoPulse Pro periodic re-scan worker")
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.getenv("RESCAN_BATCH_LIMIT", "20")),
        help="Max siti da processare in questo run",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    with app.app_context():
        stats = process_due_rescans(
            db_session=db.session,
            SiteAnalysis=SiteAnalysis,
            AnalysisRun=AnalysisRun,
            User=User,
            openai_api_key=OPENAI_API_KEY,
            openai_model=OPENAI_MODEL,
            limit=args.limit,
            daily_limit_for=lambda u: u.daily_limit,
            runs_today_for=analyses_today,
        )
        logging.info(
            "Rescan worker done ok=%s error=%s skipped=%s",
            stats["ok"],
            stats["error"],
            stats["skipped"],
        )
        print(
            f"ok={stats['ok']} error={stats['error']} skipped={stats['skipped']}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
