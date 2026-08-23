#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap: Python deps + VPS SSH wiring.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -r requirements.txt
bash scripts/setup_vps_ssh_from_secret.sh
echo "[cloud-agent-install] ok"
