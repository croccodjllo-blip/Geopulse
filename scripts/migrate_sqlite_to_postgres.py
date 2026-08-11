#!/usr/bin/env python3
"""Copy Centropic data from SQLite into an empty Postgres schema.

Prerequisites (caller):
  1. Postgres database created and reachable
  2. Target schema created (``db.create_all`` + ``alembic upgrade head``)
  3. App stopped (or brief write freeze) so the SQLite snapshot is consistent

Usage:
  DATABASE_URL_SQLITE=sqlite:////path/to/database.db \\
  DATABASE_URL=postgresql+psycopg://user:pass@127.0.0.1:5432/centropic \\
  python scripts/migrate_sqlite_to_postgres.py [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from sqlalchemy import MetaData, create_engine, inspect, select, text
from sqlalchemy.engine import Engine


# Prefer parent-before-child when FKs are enforced; also used for reporting.
PREFERRED_ORDER = (
    "users",
    "organizations",
    "organization_members",
    "site_analyses",
    "analysis_runs",
    "analysis_jobs",
    "credit_ledger",
    "usage_events",
    "sov_snapshots",
    "edge_hits",
    "alert_deliveries",
    "guest_previews",
    "alembic_version",
)


def _url(name: str, fallback: str = "") -> str:
    return (os.getenv(name) or fallback or "").strip()


def _table_names(engine: Engine) -> list[str]:
    insp = inspect(engine)
    names = [t for t in insp.get_table_names() if not t.startswith("sqlite_")]
    ordered = [t for t in PREFERRED_ORDER if t in names]
    rest = sorted(t for t in names if t not in ordered)
    return ordered + rest


def _row_count(engine: Engine, table: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar() or 0)


def _reset_sequences(pg: Engine, tables: list[str]) -> None:
    """Align Postgres serial/identity sequences to MAX(id)."""
    with pg.begin() as conn:
        for table in tables:
            cols = {c["name"] for c in inspect(pg).get_columns(table)}
            if "id" not in cols:
                continue
            conn.execute(
                text(
                    f"""
                    SELECT setval(
                      pg_get_serial_sequence('"{table}"', 'id'),
                      COALESCE((SELECT MAX(id) FROM "{table}"), 1),
                      true
                    )
                    """
                )
            )


def copy_all(*, sqlite_url: str, postgres_url: str, dry_run: bool = False) -> dict[str, Any]:
    if not sqlite_url.startswith("sqlite"):
        raise SystemExit(f"DATABASE_URL_SQLITE must be sqlite://…, got {sqlite_url[:32]}")
    if not postgres_url.startswith("postgresql"):
        raise SystemExit(
            f"DATABASE_URL must be postgresql…, got {postgres_url.split(':', 1)[0]}"
        )

    src = create_engine(sqlite_url)
    dst = create_engine(postgres_url)

    src_tables = set(_table_names(src))
    dst_tables = set(_table_names(dst))
    missing = sorted(src_tables - dst_tables)
    if missing:
        raise SystemExit(
            "Postgres schema missing tables (run create_all/alembic first): "
            + ", ".join(missing)
        )

    report: dict[str, Any] = {"tables": {}, "dry_run": dry_run}
    order = [t for t in _table_names(src) if t in dst_tables]

    src_meta = MetaData()
    src_meta.reflect(bind=src, only=order)
    dst_meta = MetaData()
    dst_meta.reflect(bind=dst, only=order)

    if dry_run:
        for table in order:
            report["tables"][table] = {
                "src": _row_count(src, table),
                "dst_before": _row_count(dst, table),
            }
        return report

    # Bypass FK checks during bulk load.
    with dst.begin() as conn:
        conn.execute(text("SET session_replication_role = replica"))

        for table in order:
            src_t = src_meta.tables[table]
            dst_t = dst_meta.tables[table]
            src_n = _row_count(src, table)
            dst_before = _row_count(dst, table)
            if dst_before > 0:
                raise SystemExit(
                    f"Target table {table!r} is not empty ({dst_before} rows). "
                    "Aborting to avoid duplicates."
                )

            with src.connect() as sconn:
                rows = sconn.execute(select(src_t)).mappings().all()

            inserted = 0
            if rows:
                # Only columns present on both sides.
                src_cols = {c.name for c in src_t.columns}
                dst_cols = {c.name for c in dst_t.columns}
                cols = [c for c in src_t.columns.keys() if c in dst_cols]
                payload = [{c: row[c] for c in cols} for row in rows]
                # Chunk inserts
                chunk = 500
                for i in range(0, len(payload), chunk):
                    conn.execute(insert(dst_t), payload[i : i + chunk])
                inserted = len(payload)

            report["tables"][table] = {
                "src": src_n,
                "inserted": inserted,
                "dst_after": inserted,
            }

        conn.execute(text("SET session_replication_role = DEFAULT"))

    _reset_sequences(dst, order)

    # Verify counts
    mismatches = []
    for table in order:
        s = _row_count(src, table)
        d = _row_count(dst, table)
        report["tables"][table]["dst_final"] = d
        if s != d:
            mismatches.append(f"{table}: sqlite={s} postgres={d}")
    if mismatches:
        raise SystemExit("Row count mismatch after copy:\n  " + "\n  ".join(mismatches))

    report["ok"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--sqlite-url",
        default=_url("DATABASE_URL_SQLITE")
        or _url("SQLITE_URL")
        or "sqlite:////opt/aio-bot/data/database.db",
    )
    parser.add_argument(
        "--postgres-url",
        default=_url("DATABASE_URL_POSTGRES") or _url("DATABASE_URL"),
    )
    args = parser.parse_args()
    if not args.postgres_url:
        print("Set DATABASE_URL (postgres) or pass --postgres-url", file=sys.stderr)
        return 2

    report = copy_all(
        sqlite_url=args.sqlite_url,
        postgres_url=args.postgres_url,
        dry_run=args.dry_run,
    )
    for name, info in report["tables"].items():
        print(f"{name}: {info}")
    print("ok" if report.get("ok") or args.dry_run else "done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
