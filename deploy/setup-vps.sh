#!/usr/bin/env bash
# One-shot LeadMagnet bootstrap for a fresh Ubuntu/Debian VPS.
#
# Usage (production with HTTPS — this is the recommended path):
#   sudo DOMAIN=leadmagnet.example.com ACME_EMAIL=you@example.com ./setup-vps.sh
#
# Usage (skip the domain — IP-only, no HTTPS, for tinkering only):
#   sudo NO_DOMAIN=1 ./setup-vps.sh
#
# What it does:
#   1. Installs Docker + compose plugin if missing.
#   2. Opens firewall ports 22, 80, 443.
#   3. Pre-flights DNS so Caddy doesn't burn a cert-acquisition rate-limit.
#   4. Clones (or pulls) this repo into /opt/leadmagnet.
#   5. Generates a strong .env on first run.
#   6. Brings up the stack with the prod profile (Caddy + Let's Encrypt).
#   7. Waits for the cert + smoke-tests the public URL.
#
# Safe to re-run: existing .env is preserved.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/havijavi/leadmagnet.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/leadmagnet}"
DOMAIN="${DOMAIN:-}"
ACME_EMAIL="${ACME_EMAIL:-}"
NO_DOMAIN="${NO_DOMAIN:-}"

# ---- preconditions --------------------------------------------------------

if [[ $EUID -ne 0 ]]; then
  echo "ERR: please run as root (sudo)." >&2
  exit 1
fi

if [[ -z "$DOMAIN" && -z "$NO_DOMAIN" ]]; then
  cat >&2 <<EOF
ERR: DOMAIN is required for production. LeadMagnet handles auth, leads, and
     email — running it on a bare IP without HTTPS is a bad idea.

  Recommended:
     sudo DOMAIN=leadmagnet.example.com ACME_EMAIL=you@example.com $0

  If you really want to skip the domain (IP-only, HTTP only), pass NO_DOMAIN=1:
     sudo NO_DOMAIN=1 $0

EOF
  exit 1
fi

if [[ -n "$DOMAIN" && -z "$ACME_EMAIL" ]]; then
  echo "ERR: ACME_EMAIL is required when DOMAIN is set (Let's Encrypt needs it)." >&2
  exit 1
fi

# ---- DNS pre-flight -------------------------------------------------------

if [[ -n "$DOMAIN" ]]; then
  echo "==> DNS pre-flight for $DOMAIN"
  apt-get install -y dnsutils >/dev/null 2>&1 || true
  resolved_ip=$(dig +short "$DOMAIN" A | tail -n1 || true)
  vps_ip=$(curl -fsSL https://ifconfig.me 2>/dev/null || curl -fsSL https://ipv4.icanhazip.com 2>/dev/null || true)
  if [[ -z "$resolved_ip" ]]; then
    echo "  WARN: $DOMAIN does not resolve. Add an A record pointing at this VPS BEFORE continuing,"
    echo "        or Caddy will burn rate-limit attempts trying to acquire a certificate."
    read -rp "  Continue anyway? [y/N] " ok
    [[ "${ok,,}" == "y" ]] || exit 1
  elif [[ -n "$vps_ip" && "$resolved_ip" != "$vps_ip" ]]; then
    echo "  WARN: $DOMAIN currently resolves to $resolved_ip but this VPS appears to be $vps_ip."
    echo "        DNS may still be propagating; cert acquisition will retry but may take time."
    read -rp "  Continue anyway? [y/N] " ok
    [[ "${ok,,}" == "y" ]] || exit 1
  else
    echo "  OK: $DOMAIN → $resolved_ip"
  fi
fi

# ---- packages -------------------------------------------------------------

echo "==> Installing prerequisites"
apt-get update -y
apt-get install -y curl git ca-certificates gnupg ufw openssl

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/gpg" \
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

# ---- firewall -------------------------------------------------------------

echo "==> Configuring firewall"
ufw allow OpenSSH || true
ufw allow 80/tcp || true
ufw allow 443/tcp || true
yes | ufw enable >/dev/null 2>&1 || true

# ---- repo ------------------------------------------------------------------

echo "==> Cloning repo to $INSTALL_DIR"
if [[ -d "$INSTALL_DIR/.git" ]]; then
  git -C "$INSTALL_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"
mkdir -p secrets

# ---- env -------------------------------------------------------------------

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
    sed -i "s|^ACME_EMAIL=.*|ACME_EMAIL=$ACME_EMAIL|" .env
    # Frontend talks to backend at the SAME origin in production — Caddy
    # routes /api/* to the backend container.
    sed -i "s|^NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=https://$DOMAIN|" .env
  fi

  cat <<EOF

------------------------------------------------------------
  Generated secrets (saved to $INSTALL_DIR/.env):
    ADMIN_TOKEN  = $ADMIN_TOKEN

  ADMIN_TOKEN is your break-glass superuser bearer token.
  Keep it safe. On first dashboard visit you'll create the
  first admin USER ACCOUNT (email + password); that's what
  you sign in with day-to-day.
------------------------------------------------------------

EOF
else
  echo "==> .env already exists — leaving alone."
fi

# ---- bring up the stack ---------------------------------------------------

PROFILE_ARGS=()
if [[ -n "$DOMAIN" ]]; then
  PROFILE_ARGS+=(--profile prod)
fi

echo "==> Building and starting LeadMagnet"
docker compose "${PROFILE_ARGS[@]}" up -d --build

# ---- post-deploy verification ---------------------------------------------

echo "==> Waiting for backend to come up"
for i in $(seq 1 60); do
  if docker compose exec -T backend curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "  backend OK"
    break
  fi
  sleep 2
  if [[ $i -eq 60 ]]; then
    echo "  WARN: backend didn't respond on /health within 120s. Check 'docker compose logs backend'."
  fi
done

if [[ -n "$DOMAIN" ]]; then
  echo "==> Verifying public URL https://$DOMAIN/health"
  for i in $(seq 1 30); do
    if curl -fsSL "https://$DOMAIN/health" >/dev/null 2>&1; then
      echo "  public URL OK"
      break
    fi
    if [[ $i -eq 30 ]]; then
      echo "  WARN: https://$DOMAIN/health not reachable yet."
      echo "        Caddy may still be acquiring the certificate. Tail logs with:"
      echo "          docker compose logs -f caddy"
    fi
    sleep 4
  done
fi

# ---- summary --------------------------------------------------------------

cat <<EOF

============================================================
  LeadMagnet deployed.

EOF
if [[ -n "$DOMAIN" ]]; then
cat <<EOF
  Dashboard:   https://$DOMAIN
  API docs:    https://$DOMAIN/docs
  Health:      https://$DOMAIN/health

  Open the dashboard now — you'll be sent to /setup to
  create the first admin user (email + password).

EOF
else
cat <<EOF
  Dashboard:   http://<vps-ip>:3000
  API docs:    http://<vps-ip>:8000/docs

  Re-run with DOMAIN=... ACME_EMAIL=... to enable HTTPS via Caddy.

EOF
fi
cat <<EOF
  Secrets are in $INSTALL_DIR/.env — back this file up.
  Update the stack later with: cd $INSTALL_DIR && ./deploy/update.sh
============================================================
EOF
