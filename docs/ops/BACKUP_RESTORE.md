# Centropic — Backup & restore (Postgres)

## Backup (prod)
- Timer: `aio-bot-backup.timer` → daily `scripts/backup_db.py`
- Output: `/opt/aio-bot/data/backups/database-YYYYMMDDTHHMMSSZ.dump` (`pg_dump -Fc`)
- Retention: `BACKUP_KEEP` (default 14)

Manual:
```bash
cd /opt/aio-bot
sudo -u aio-bot .venv/bin/python scripts/backup_db.py
```

## Restore drill (non-destructive — run monthly)
Creates a **temporary** database from the newest dump, counts users, drops it.
Never writes into production `DATABASE_URL`.

```bash
cd /opt/aio-bot
sudo -u aio-bot .venv/bin/python scripts/restore_db_drill.py
# optional: --dump /path/to/database-….dump
```

Exit `0` = OK. Exit `2` = not Postgres (skip). Exit `1` = failure.

## Emergency restore to a new DB (human-gated)
1. Provision empty DB e.g. `centropic_restore`.
2. `pg_restore --no-owner --no-acl --dbname=centropic_restore /opt/aio-bot/data/backups/<dump>`
3. Point a staging `DATABASE_URL` at it; verify `/health` + admin login.
4. Only then cut over DNS/app env (maintenance window).

## Deploy note (analyze safety)
`post-receive` restarts `aio-bot` then starts `aio-bot-analyze.service` so pending/stale jobs resume. Prefer not deploying mid long measured-SoV runs; reclaim floor is 2–5 minutes if a worker dies.
