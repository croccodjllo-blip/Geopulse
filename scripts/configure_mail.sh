#!/usr/bin/env bash
# Applica credenziali mail su /opt/aio-bot/.env (Resend oppure SMTP).
# Uso (sul VPS):
#   sudo RESEND_API_KEY=re_xxx MAIL_FROM='GeoPulse <noreply@geopulse.it>' \
#     bash scripts/configure_mail.sh
# oppure:
#   sudo SMTP_HOST=smtps.aruba.it SMTP_PORT=465 SMTP_SSL=1 SMTP_STARTTLS=0 \
#     SMTP_USER=noreply@geopulse.it SMTP_PASSWORD='***' \
#     MAIL_FROM='GeoPulse <noreply@geopulse.it>' \
#     bash scripts/configure_mail.sh

set -euo pipefail

ENVF="${ENVF:-/opt/aio-bot/.env}"
SERVICE="${SERVICE:-aio-bot}"

if [[ ! -f "$ENVF" ]]; then
  echo "ERROR: manca $ENVF" >&2
  exit 1
fi

upsert() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENVF"; then
    # Escape sed specials in value carefully via python
    python3 - "$ENVF" "$key" "$val" <<'PY'
import pathlib, sys
path, key, val = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
lines = path.read_text().splitlines()
out, found = [], False
for line in lines:
    if line.startswith(key + "="):
        out.append(f"{key}={val}")
        found = True
    else:
        out.append(line)
if not found:
    out.append(f"{key}={val}")
path.write_text("\n".join(out) + "\n")
PY
  else
    printf '%s=%s\n' "$key" "$val" >>"$ENVF"
  fi
}

MAIL_FROM_VAL="${MAIL_FROM:-GeoPulse <noreply@geopulse.it>}"
upsert MAIL_FROM "$MAIL_FROM_VAL"

if [[ -n "${RESEND_API_KEY:-}" ]]; then
  upsert RESEND_API_KEY "$RESEND_API_KEY"
  # Prefer Resend: clear SMTP so mailer picks Resend
  upsert SMTP_HOST ""
  echo "Configured RESEND_API_KEY (+ MAIL_FROM)"
elif [[ -n "${SMTP_HOST:-}" && -n "${SMTP_USER:-}" && -n "${SMTP_PASSWORD:-}" ]]; then
  upsert SMTP_HOST "$SMTP_HOST"
  upsert SMTP_PORT "${SMTP_PORT:-587}"
  upsert SMTP_USER "$SMTP_USER"
  upsert SMTP_PASSWORD "$SMTP_PASSWORD"
  upsert SMTP_STARTTLS "${SMTP_STARTTLS:-1}"
  upsert SMTP_SSL "${SMTP_SSL:-0}"
  echo "Configured SMTP_* (+ MAIL_FROM)"
else
  echo "ERROR: passa RESEND_API_KEY oppure SMTP_HOST+SMTP_USER+SMTP_PASSWORD" >&2
  exit 1
fi

if command -v systemctl >/dev/null 2>&1; then
  systemctl restart "$SERVICE"
  echo "Restarted $SERVICE"
fi

# Smoke (non invia mail): health + mail_configured via python
if [[ -x /opt/aio-bot/.venv/bin/python ]]; then
  sudo -u aio-bot /opt/aio-bot/.venv/bin/python - <<'PY' || true
from app import app
from services.mailer import mail_configured, mail_from_address
with app.app_context():
    print("mail_configured=", mail_configured())
    print("mail_from=", mail_from_address())
PY
fi
