#!/usr/bin/env python3
"""Print Fase 0 production env + schema guard status (local or on the VPS)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from centropic.prod_guards import evaluate_env_guards, refresh_credit_ledger_index_ok


def main() -> int:
    from sqlalchemy import create_engine

    from app import resolve_database_uri

    env = evaluate_env_guards()
    url = resolve_database_uri(os.getenv("DATABASE_URL"))
    index_ok = False
    index_error = None
    try:
        engine = create_engine(url)
        index_ok = refresh_credit_ledger_index_ok(engine)
    except Exception as exc:  # pragma: no cover - ops helper
        index_error = str(exc)

    payload = {
        "env_guards": env,
        "credit_ledger_pi_index_ok": index_ok,
        "credit_ledger_pi_index_error": index_error,
        "ok": bool(env["ok"] and index_ok),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
