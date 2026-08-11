#!/bin/sh
# Centropic container entrypoint: SQLite must stay single-worker.
# Refuse to start unless Alembic is at head and billing index exists.
set -eu

PORT="${PORT:-8000}"
DB_URL="${DATABASE_URL:-sqlite:////data/database.db}"
WORKERS="${WEB_CONCURRENCY:-2}"
THREADS="${WEB_THREADS:-4}"

case "$DB_URL" in
  sqlite:*|SQLite:*)
    if [ "$WORKERS" != "1" ]; then
      echo "centropic: DATABASE_URL is SQLite — forcing WEB_CONCURRENCY=1 (was $WORKERS)" >&2
      WORKERS=1
    fi
    ;;
esac

if [ "${SKIP_SCHEMA_CHECK:-0}" != "1" ]; then
  echo "centropic: alembic upgrade head"
  alembic upgrade head
  echo "centropic: check_schema_ready"
  python scripts/check_schema_ready.py
fi

exec gunicorn \
  --bind "0.0.0.0:${PORT}" \
  --workers "${WORKERS}" \
  --threads "${THREADS}" \
  --timeout 120 \
  "app:app"
