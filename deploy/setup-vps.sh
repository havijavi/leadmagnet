#!/usr/bin/env bash
# One-shot LeadMagnet bootstrap for a fresh Ubuntu/Debian VPS (Contabo, Hetzner, etc.).
#
# Usage:
#   sudo DOMAIN=leadmagnet.example.com ACME_EMAIL=you@example.com ./setup-vps.sh
#
# What it does:
#   1. Installs Docker + compose plugin if missing.
#   2. Clones (or pulls) this repo into /opt/leadmagnet.
#   3. Generates a strong .env with random secrets if none exists.
#   4. Brings the stack up with the prod profile (Caddy + Let's Encrypt).
#
# Safe to re-run.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/havijavi/leadmagnet.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/leadmagnet}"
DOMAIN="${DOMAIN:-}"
ACME_EMAIL="${ACME_EMAIL:-}"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (sudo)." >&2
  exit 1
fi

echo "==> Installing prerequisites"
apt-get update -y
apt-get install -y curl git ca-certificates gnupg ufw

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/$(. /etc/os-release && echo "$ID") \
$(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
fi

echo "==> Configuring firewall"
ufw allow OpenSSH || true
ufw allow 80/tcp || true
ufw allow 443/tcp || true
yes | ufw enable || true

echo "==> Cloning repo to $INSTALL_DIR"
if [[ -d "$INSTALL_DIR/.git" ]]; then
  git -C "$INSTALL_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

if [[ ! -f .env ]]; then
  echo "==> Generating .env"
  cp .env.example .env
  ADMIN_TOKEN=$(openssl rand -hex 32)
  JWT_SECRET=$(openssl rand -hex 32)
  POSTGRES_PASSWORD=$(openssl rand -hex 16)
  sed -i "s|^ADMIN_TOKEN=.*|ADMIN_TOKEN=$ADMIN_TOKEN|" .env
  sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" .env
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$POSTGRES_PASSWORD|" .env
  if [[ -n "$DOMAIN" ]]; then
    sed -i "s|^DOMAIN=.*|DOMAIN=$DOMAIN|" .env
    sed -i "s|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=https://$DOMAIN|" .env
  fi
  if [[ -n "$ACME_EMAIL" ]]; then
    sed -i "s|^ACME_EMAIL=.*|ACME_EMAIL=$ACME_EMAIL|" .env
  fi
  echo
  echo "----------------------------------------------"
  echo "  Generated ADMIN_TOKEN: $ADMIN_TOKEN"
  echo "  Keep this safe — it is a SUPERUSER bearer token (bypasses login)."
  echo "  On first dashboard visit you'll be asked to create the first admin"
  echo "  account; after that, sign in with email + password as normal."
  echo "----------------------------------------------"
  echo
fi

PROFILE_ARGS=()
if [[ -n "$DOMAIN" ]]; then
  PROFILE_ARGS+=(--profile prod)
fi

echo "==> Starting stack"
docker compose "${PROFILE_ARGS[@]}" up -d --build

echo
echo "==> Done."
if [[ -n "$DOMAIN" ]]; then
  echo "Open https://$DOMAIN once DNS resolves to this VPS."
else
  echo "Open http://<vps-ip>:3000 (frontend) and http://<vps-ip>:8000/docs (API)."
  echo "Set DOMAIN + ACME_EMAIL and re-run this script to enable HTTPS via Caddy."
fi
