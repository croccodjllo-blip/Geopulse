#!/usr/bin/env bash
# Deploy AIO-Bot su un server Linux con Docker.
# Uso:
#   ./scripts/deploy.sh                 # build + up locali
#   REMOTE=user@host ./scripts/deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "[deploy] Manca .env — copio da .env.example"
  cp .env.example .env
  echo "[deploy] Imposta almeno FLASK_SECRET_KEY in .env prima della produzione."
fi

# Genera secret se ancora placeholder
if grep -q 'replace-with-a-long-random-string' .env 2>/dev/null || ! grep -q '^FLASK_SECRET_KEY=.\+' .env; then
  SECRET="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"
  if grep -q '^FLASK_SECRET_KEY=' .env; then
    sed -i "s|^FLASK_SECRET_KEY=.*|FLASK_SECRET_KEY=${SECRET}|" .env
  else
    printf '\nFLASK_SECRET_KEY=%s\n' "$SECRET" >> .env
  fi
  echo "[deploy] FLASK_SECRET_KEY generata automaticamente"
fi

REMOTE="${REMOTE:-}"

if [[ -z "$REMOTE" ]]; then
  echo "[deploy] Deploy locale con Docker Compose"
  docker compose build
  docker compose up -d
  docker compose ps
  echo "[deploy] App su http://127.0.0.1:${HOST_PORT:-8000}"
  exit 0
fi

REMOTE_DIR="${REMOTE_DIR:-/opt/aio-bot}"
echo "[deploy] Sync verso ${REMOTE}:${REMOTE_DIR}"

ssh "$REMOTE" "mkdir -p '${REMOTE_DIR}'"
# Mai usare --delete senza escludere data/ e .venv: cancella DB e runtime.
rsync -az --delete \
  --exclude '.venv' \
  --exclude 'venv' \
  --exclude 'data' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.git' \
  --exclude 'database.db' \
  --exclude 'instance' \
  --exclude '.env' \
  "$ROOT/" "${REMOTE}:${REMOTE_DIR}/"

# Copia .env solo se remoto non ce l'ha (mai sovrascrivere secrets di produzione).
ssh "$REMOTE" "test -f '${REMOTE_DIR}/.env' || cp '${REMOTE_DIR}/.env.example' '${REMOTE_DIR}/.env'"

ssh "$REMOTE" "cd '${REMOTE_DIR}' && docker compose build && docker compose up -d && docker compose ps"
echo "[deploy] Completato su ${REMOTE}"
echo "[deploy] Bind 127.0.0.1:HOST_PORT (default 8000). Metti Nginx/Caddy davanti per HTTPS."
