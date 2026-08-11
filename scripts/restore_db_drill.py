#!/usr/bin/env python3
"""Non-destructive Postgres restore drill.

Creates a temporary database from the latest ``database-*.dump``, runs a
sanity query, then drops the temp DB. Never touches production DATABASE_URL.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = val.strip().strip("'").strip('"')


def parse_pg(url: str) -> dict[str, str]:
    u = urlparse(url.replace("postgresql+psycopg", "postgresql", 1))
    return {
        "host": u.hostname or "127.0.0.1",
        "port": str(u.port or 5432),
        "user": unquote(u.username or "postgres"),
        "password": unquote(u.password or ""),
        "dbname": (u.path or "/").lstrip("/") or "postgres",
    }


def run(cmd: list[str], env: dict[str, str]) -> None:
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"command failed ({proc.returncode}): {' '.join(cmd)}\n{err[:800]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Centropic Postgres restore drill")
    parser.add_argument("--env-file", default=os.environ.get("ENV_FILE", "/opt/aio-bot/.env"))
    parser.add_argument(
        "--backup-dir",
        default=os.environ.get("BACKUP_DIR", "/opt/aio-bot/data/backups"),
    )
    parser.add_argument(
        "--dump",
        default="",
        help="Explicit .dump path (default: newest database-*.dump)",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Do not DROP the temp database (debug only)",
    )
    args = parser.parse_args()
    load_env_file(Path(args.env_file))

    database_url = (os.environ.get("DATABASE_URL") or "").strip()
    if not database_url.startswith(("postgresql", "postgres")):
        print("DATABASE_URL is not Postgres — drill skipped", file=sys.stderr)
        return 2

    cfg = parse_pg(database_url)
    backup_dir = Path(args.backup_dir)
    if args.dump:
        dump = Path(args.dump)
    else:
        dumps = sorted(backup_dir.glob("database-*.dump"), key=lambda p: p.stat().st_mtime)
        if not dumps:
            print(f"No dumps in {backup_dir}", file=sys.stderr)
            return 1
        dump = dumps[-1]
    if not dump.is_file() or dump.stat().st_size <= 0:
        print(f"Dump missing/empty: {dump}", file=sys.stderr)
        return 1

    temp_db = f"centropic_restore_drill_{os.getpid()}"
    env = os.environ.copy()
    if cfg["password"]:
        env["PGPASSWORD"] = cfg["password"]
    base = [
        "--host",
        cfg["host"],
        "--port",
        cfg["port"],
        "--username",
        cfg["user"],
    ]

    print(f"Drill source dump: {dump} ({dump.stat().st_size} bytes)")
    print(f"Temp database: {temp_db}")

    # Create temp DB via maintenance connection to the app DB's cluster.
    run(
        ["psql", *base, "--dbname", cfg["dbname"], "-v", "ON_ERROR_STOP=1", "-c", f'CREATE DATABASE "{temp_db}"'],
        env,
    )
    try:
        run(
            [
                "pg_restore",
                *base,
                "--dbname",
                temp_db,
                "--no-owner",
                "--no-acl",
                "--clean",
                "--if-exists",
                str(dump),
            ],
            env,
        )
        proc = subprocess.run(
            [
                "psql",
                *base,
                "--dbname",
                temp_db,
                "-v",
                "ON_ERROR_STOP=1",
                "-tAc",
                "SELECT count(*) FROM users;",
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise SystemExit(f"sanity query failed: {(proc.stderr or proc.stdout or '')[:400]}")
        count = (proc.stdout or "").strip()
        print(f"Restore drill OK — users_count={count}")
    finally:
        if not args.keep_temp:
            run(
                [
                    "psql",
                    *base,
                    "--dbname",
                    cfg["dbname"],
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    f'DROP DATABASE IF EXISTS "{temp_db}" WITH (FORCE);',
                ],
                env,
            )
            print(f"Dropped temp database {temp_db}")
        else:
            print(f"Kept temp database {temp_db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
