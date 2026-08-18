#!/usr/bin/env python3
"""Backup Centropic DB: Postgres (pg_dump) or SQLite (online WAL API).

Writes timestamped files under BACKUP_DIR and prunes to BACKUP_KEEP.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse


def load_env_file(env_path: Path) -> None:
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'").strip('"')
        os.environ.setdefault(key, val)


def resolve_sqlite_path(database_url: str | None, base_dir: Path) -> Path:
    """Resolve SQLite path from DATABASE_URL."""
    uri = (database_url or "").strip()
    if not uri:
        return base_dir / "database.db"
    if uri.startswith("sqlite:////"):
        return Path("/" + uri.removeprefix("sqlite:////"))
    if uri.startswith("sqlite:///"):
        rel = uri.removeprefix("sqlite:///")
        if rel == ":memory:":
            raise SystemExit("Cannot backup :memory: database")
        p = Path(rel)
        return p if p.is_absolute() else base_dir / p
    raise SystemExit(f"Unsupported SQLite DATABASE_URL: {uri}")


def backup_sqlite(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=30)
    try:
        dst_conn = sqlite3.connect(str(dest), timeout=30)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def _parse_postgres_url(url: str) -> dict[str, str]:
    """Parse postgresql[+driver]://user:pass@host:port/db into pg_dump bits."""
    raw = (url or "").strip()
    if raw.startswith("postgresql+"):
        # sqlalchemy style → urllib-friendly
        raw = "postgresql://" + raw.split("://", 1)[1]
    if not raw.startswith(("postgresql://", "postgres://")):
        raise SystemExit(f"Not a Postgres DATABASE_URL: {url[:48]}")
    parsed = urlparse(raw)
    db = (parsed.path or "").lstrip("/")
    if not db:
        raise SystemExit("Postgres DATABASE_URL missing database name")
    return {
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "host": parsed.hostname or "127.0.0.1",
        "port": str(parsed.port or 5432),
        "dbname": unquote(db),
    }


def backup_postgres(database_url: str, dest: Path) -> None:
    """Custom-format pg_dump (-Fc), restorable with pg_restore."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cfg = _parse_postgres_url(database_url)
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise SystemExit("pg_dump not found on PATH (install postgresql-client)")

    env = os.environ.copy()
    if cfg["password"]:
        env["PGPASSWORD"] = cfg["password"]
    cmd = [
        pg_dump,
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--file",
        str(dest),
        "--host",
        cfg["host"],
        "--port",
        cfg["port"],
        "--username",
        cfg["user"] or "postgres",
        "--dbname",
        cfg["dbname"],
    ]
    proc = subprocess.run(
        cmd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"pg_dump failed ({proc.returncode}): {err[:800]}")
    if not dest.is_file() or dest.stat().st_size <= 0:
        raise SystemExit(f"pg_dump produced empty file: {dest}")


def prune(backup_dir: Path, patterns: tuple[str, ...], keep: int) -> None:
    files: list[Path] = []
    for pattern in patterns:
        files.extend(backup_dir.glob(pattern))
    files = sorted(set(files), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        try:
            old.unlink()
        except OSError:
            pass
        # Drop orphan sqlite sidecars for pruned .db dumps
        for suffix in ("-wal", "-shm"):
            side = Path(str(old) + suffix)
            if side.is_file():
                try:
                    side.unlink()
                except OSError:
                    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup Centropic database")
    parser.add_argument(
        "--env-file",
        default=os.environ.get("ENV_FILE", "/opt/aio-bot/.env"),
        help="Path to .env (optional)",
    )
    parser.add_argument(
        "--backup-dir",
        default=os.environ.get("BACKUP_DIR", "/opt/aio-bot/data/backups"),
    )
    parser.add_argument("--keep", type=int, default=int(os.environ.get("BACKUP_KEEP", "14")))
    args = parser.parse_args()

    load_env_file(Path(args.env_file))
    base_dir = Path(os.environ.get("AIO_BOT_DIR", "/opt/aio-bot"))
    database_url = (os.environ.get("DATABASE_URL") or "").strip()
    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if database_url.startswith(("postgresql", "postgres")):
        dest = backup_dir / f"database-{stamp}.dump"
        backup_postgres(database_url, dest)
        prune(backup_dir, ("database-*.dump", "database-*.db"), max(1, args.keep))
        print(f"Backup OK (postgres) → {dest} ({dest.stat().st_size} bytes)")
        return 0

    # SQLite path (dev / emergency)
    db_path = resolve_sqlite_path(database_url or None, base_dir)
    if not db_path.is_file():
        alt = Path(__file__).resolve().parents[1] / "database.db"
        if alt.is_file():
            db_path = alt
        else:
            print(f"DB not found: {db_path}", file=sys.stderr)
            return 1

    dest = backup_dir / f"database-{stamp}.db"
    backup_sqlite(db_path, dest)
    for suffix in ("-wal", "-shm"):
        side = Path(str(db_path) + suffix)
        if side.is_file():
            shutil.copy2(side, Path(str(dest) + suffix))

    prune(backup_dir, ("database-*.db", "database-*.dump"), max(1, args.keep))
    print(f"Backup OK (sqlite) → {dest} ({dest.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
