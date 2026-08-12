#!/usr/bin/env bash
# Install local MinIO for ANALYZE_ARTIFACT_STORE=s3 (loopback only).
set -euo pipefail
ROOT="${AIO_BOT_DIR:-/opt/aio-bot}"
BIN="$ROOT/bin"
DATA="$ROOT/data/minio"
ENVF="$ROOT/deploy/minio.env"
BUCKET="${ANALYZE_S3_BUCKET:-centropic-analyze-packs}"
ARCH=$(uname -m)
case "$ARCH" in
  x86_64|amd64) MINIO_ARCH=amd64; MC_ARCH=amd64 ;;
  aarch64|arm64) MINIO_ARCH=arm64; MC_ARCH=arm64 ;;
  *) echo "unsupported arch: $ARCH" >&2; exit 1 ;;
esac

mkdir -p "$BIN" "$DATA" "$ROOT/deploy"
if [[ ! -x "$BIN/minio" ]]; then
  curl -fsSL "https://dl.min.io/server/minio/release/linux-${MINIO_ARCH}/minio" -o "$BIN/minio"
  chmod +x "$BIN/minio"
fi
if [[ ! -x "$BIN/mc" ]]; then
  curl -fsSL "https://dl.min.io/client/mc/release/linux-${MC_ARCH}/mc" -o "$BIN/mc"
  chmod +x "$BIN/mc"
fi

if [[ ! -f "$ENVF" ]]; then
  ROOT_USER="centropic$(openssl rand -hex 4)"
  ROOT_PASS="$(openssl rand -hex 24)"
  cat >"$ENVF" <<EOV
MINIO_ROOT_USER=${ROOT_USER}
MINIO_ROOT_PASSWORD=${ROOT_PASS}
EOV
  chmod 600 "$ENVF"
  chown aio-bot:aio-bot "$ENVF" 2>/dev/null || true
fi
# shellcheck disable=SC1090
source "$ENVF"
chown -R aio-bot:aio-bot "$DATA" "$BIN/minio" "$BIN/mc" 2>/dev/null || true

install -m 644 "$ROOT/deploy/aio-bot-minio.service" /etc/systemd/system/aio-bot-minio.service
systemctl daemon-reload
systemctl enable --now aio-bot-minio.service
sleep 2
systemctl is-active aio-bot-minio.service

"$BIN/mc" alias set local http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
"$BIN/mc" mb -p "local/${BUCKET}" || true
"$BIN/mc" anonymous set none "local/${BUCKET}" >/dev/null || true

DOTENV="$ROOT/.env"
upsert() {
  local k="$1" v="$2"
  if grep -q "^${k}=" "$DOTENV"; then
    sed -i "s|^${k}=.*|${k}=${v}|" "$DOTENV"
  else
    echo "${k}=${v}" >>"$DOTENV"
  fi
}
upsert ANALYZE_ARTIFACT_STORE s3
upsert ANALYZE_S3_BUCKET "$BUCKET"
upsert ANALYZE_S3_PREFIX analyze-packs
upsert ANALYZE_S3_REGION eu-central-1
upsert ANALYZE_S3_ENDPOINT_URL http://127.0.0.1:9000
upsert AWS_ACCESS_KEY_ID "$MINIO_ROOT_USER"
upsert AWS_SECRET_ACCESS_KEY "$MINIO_ROOT_PASSWORD"
upsert AWS_DEFAULT_REGION eu-central-1
upsert ANALYZE_ARTIFACT_DB_LEAN 1

echo "MinIO ready: bucket=${BUCKET} endpoint=http://127.0.0.1:9000"
