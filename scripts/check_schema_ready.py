#!/usr/bin/env python3
"""Fail closed if DB schema is not ready for a production restart.

Used by the git post-receive hook before ``systemctl restart``.
Checks:
  1. Alembic is at head (when alembic is installed / migrations present)
  2. credit_ledger payment-idempotency unique index exists
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def _check_alembic() -> None:
    ini = ROOT / "alembic.ini"
    versions = ROOT / "migrations" / "versions"
    if not ini.is_file() or not versions.is_dir():
        print("check_schema_ready: alembic artifacts missing", file=sys.stderr)
        raise SystemExit(2)
    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from sqlalchemy import create_engine
    except Exception as exc:
        print(f"check_schema_ready: alembic import failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    from app import resolve_database_uri

    url = resolve_database_uri(os.getenv("DATABASE_URL"))
    cfg = Config(str(ini))
    script = ScriptDirectory.from_config(cfg)
    heads = set(script.get_heads())
    engine = create_engine(url)
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current = set(context.get_current_heads())
    if current != heads:
        print(
            f"check_schema_ready: alembic not at head "
            f"(current={sorted(current) or ['<empty>']}, "
            f"heads={sorted(heads)})",
            file=sys.stderr,
        )
        raise SystemExit(3)
    print(f"check_schema_ready: alembic ok @ {','.join(sorted(heads))}")


def _check_ledger_index() -> None:
    from sqlalchemy import create_engine

    from app import resolve_database_uri
    from centropic.prod_guards import (
        CREDIT_LEDGER_PI_INDEX,
        credit_ledger_pi_index_present,
    )

    url = resolve_database_uri(os.getenv("DATABASE_URL"))
    engine = create_engine(url)
    if not credit_ledger_pi_index_present(engine):
        print(
            f"check_schema_ready: missing index {CREDIT_LEDGER_PI_INDEX}",
            file=sys.stderr,
        )
        raise SystemExit(4)
    print(f"check_schema_ready: index {CREDIT_LEDGER_PI_INDEX} ok")


def main() -> None:
    skip_alembic = (os.getenv("SKIP_ALEMBIC_CHECK") or "").strip() in {
        "1",
        "true",
        "yes",
    }
    if not skip_alembic:
        _check_alembic()
    _check_ledger_index()
    print("check_schema_ready: OK")


if __name__ == "__main__":
    main()
