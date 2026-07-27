#!/usr/bin/env python3
"""Backup SQLite di GeoPulse (safe online con WAL).

Copia database.db (+ -wal/-shm se presenti) in BACKUP_DIR con timestamp.
Mantiene gli ultimi KEEP backup.
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def resolve_db_path(database_url: str | None, base_dir: Path) -> Path:
    uri = (database_url or "").strip()
    if not uri:
        return base_dir / "database.db"
    if uri.startswith("sqlite:////"):
        return Path(uri.removeprefix("sqlite:////"))
    if uri.startswith("sqlite:///"):
        rel = uri.removeprefix("sqlite:///")
        if rel == ":memory:":
            raise SystemExit("Cannot backup :memory: database")
        p = Path(rel)
        return p if p.is_absolute() else base_dir / p
    raise SystemExit(f"Unsupported DATABASE_URL for backup: {uri}")


def backup_sqlite(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Online backup API — safe with concurrent readers/writers
    src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=30)
    try:
        dst_conn = sqlite3.connect(str(dest), timeout=30)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def prune(backup_dir: Path, pattern: str, keep: int) -> None:
    files = sorted(backup_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        try:
            old.unlink()
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup GeoPulse SQLite DB")
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

    # Lightweight .env load
    env_path = Path(args.env_file)
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("'").strip('"')
            os.environ.setdefault(key, val)

    base_dir = Path(os.environ.get("AIO_BOT_DIR", "/opt/aio-bot"))
    db_path = resolve_db_path(os.environ.get("DATABASE_URL"), base_dir)
    if not db_path.is_file():
        # local dev fallback
        alt = Path(__file__).resolve().parents[1] / "database.db"
        if alt.is_file():
            db_path = alt
        else:
            print(f"DB not found: {db_path}", file=sys.stderr)
            return 1

    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = backup_dir / f"database-{stamp}.db"
    backup_sqlite(db_path, dest)
    # Also copy sidecar if present (best-effort; online backup already consistent)
    for suffix in ("-wal", "-shm"):
        side = Path(str(db_path) + suffix)
        if side.is_file():
            shutil.copy2(side, Path(str(dest) + suffix))

    prune(backup_dir, "database-*.db", max(1, args.keep))
    print(f"Backup OK → {dest} ({dest.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
