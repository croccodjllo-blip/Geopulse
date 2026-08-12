#!/usr/bin/env python3
"""Delete analyze pack objects older than ANALYZE_S3_RETENTION_DAYS."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from services.s3_lifecycle import cleanup_expired_packs


def main() -> int:
    result = cleanup_expired_packs(limit=int(os.getenv("ANALYZE_S3_CLEANUP_LIMIT", "2000") or "2000"))
    print(result)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
