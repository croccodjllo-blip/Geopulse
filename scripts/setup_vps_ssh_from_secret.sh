#!/usr/bin/env bash
# Install VPS deploy SSH key from Cursor Cloud Agent secret VPS_SSH_PRIVATE_KEY,
# or reuse ~/.ssh/id_ed25519_centropic_vps when it already exists (snapshot).
# Safe to run from environment install/start; no-ops if neither is present.
set -euo pipefail

mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

KEY="$HOME/.ssh/id_ed25519_centropic_vps"

if [[ -n "${VPS_SSH_PRIVATE_KEY:-}" ]]; then
  # Normalize possible escaped newlines from secret UIs.
  printf '%s\n' "$VPS_SSH_PRIVATE_KEY" | sed 's/\r$//' | awk '
    BEGIN { inkey=0 }
    /^-----BEGIN/ { inkey=1 }
    { if (inkey) print }
    /^-----END/ { inkey=0 }
  ' > "$KEY"
  # Fallback if secret was pasted without BEGIN markers (raw key body unlikely for ed25519 OpenSSH).
  if [[ ! -s "$KEY" ]]; then
    printf '%s\n' "$VPS_SSH_PRIVATE_KEY" > "$KEY"
  fi
  chmod 600 "$KEY"
elif [[ ! -s "$KEY" ]]; then
  echo "[vps-ssh] VPS_SSH_PRIVATE_KEY not set and no existing key — skip"
  exit 0
fi

# Ensure OpenSSH format ends with newline.
if [[ -n "$(tail -c1 "$KEY" | tr -d '\n' || true)" ]]; then
  printf '\n' >> "$KEY"
fi

# Host key for Centropic VPS (IONOS).
if ! grep -q '82.165.79.212' "$HOME/.ssh/known_hosts" 2>/dev/null; then
  ssh-keyscan -H 82.165.79.212 >> "$HOME/.ssh/known_hosts" 2>/dev/null || true
  chmod 644 "$HOME/.ssh/known_hosts"
fi

# Force this identity for the vps git remote.
CFG="$HOME/.ssh/config"
touch "$CFG"
chmod 600 "$CFG"
if ! grep -q 'Host centropic-vps' "$CFG" 2>/dev/null; then
  cat >> "$CFG" <<'EOF'

Host centropic-vps
  HostName 82.165.79.212
  User root
  IdentityFile ~/.ssh/id_ed25519_centropic_vps
  IdentitiesOnly yes
EOF
fi

# Point git remote "vps" at SSH alias if present in repo.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if git remote get-url vps >/dev/null 2>&1; then
    git remote set-url vps "ssh://centropic-vps/opt/git/geopulse.git"
  else
    git remote add vps "ssh://centropic-vps/opt/git/geopulse.git" || true
  fi
fi

echo "[vps-ssh] key installed; test with: git ls-remote vps HEAD"
