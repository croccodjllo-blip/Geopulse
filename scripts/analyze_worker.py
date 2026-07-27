#!/usr/bin/env python3
"""Worker CLI per coda analisi async (systemd timer / cron)."""

from __future__ import annotations

import argparse
import logging
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import (  # noqa: E402
    OPENAI_API_KEY,
    OPENAI_MODEL,
    app,
    process_pending_analyze_jobs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="GeoPulse async analyze worker")
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.getenv("ANALYZE_BATCH_LIMIT", "5")),
        help="Max job da processare in questo run",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    with app.app_context():
        stats = process_pending_analyze_jobs(
            limit=args.limit,
            openai_api_key=OPENAI_API_KEY,
            openai_model=OPENAI_MODEL,
        )
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
