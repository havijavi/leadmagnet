#!/usr/bin/env bash
# Smoke-test a running LeadMagnet deployment.
#
# Usage:
#   ./verify.sh                        # uses DOMAIN from ./.env
#   DOMAIN=leadmagnet.example.com ./verify.sh
#
# Exits non-zero on any failed check. Suitable for monitoring crons.
set -euo pipefail

cd "$(dirname "$0")/.."

# Pull DOMAIN from .env if not already in the environment.
if [[ -z "${DOMAIN:-}" && -f .env ]]; then
  DOMAIN=$(grep -E '^DOMAIN=' .env | tail -n1 | cut -d= -f2- | tr -d ' ')
fi

if [[ -z "${DOMAIN:-}" ]]; then
  BASE="http://localhost:8000"
  echo "No DOMAIN set — checking local backend at $BASE."
else
  BASE="https://$DOMAIN"
  echo "Checking public URL $BASE."
fi

failed=0
check() {
  local label="$1"; local url="$2"
  if curl -fsS --max-time 10 "$url" >/dev/null 2>&1; then
    echo "  OK    $label  ($url)"
  else
    echo "  FAIL  $label  ($url)"
    failed=$((failed + 1))
  fi
}

check "/health"         "$BASE/health"
check "/docs"           "$BASE/docs"
check "/openapi.json"   "$BASE/openapi.json"
check "/api/auth/needs-setup"  "$BASE/api/auth/needs-setup"

# Container statuses
echo
echo "Container status:"
docker compose ps --format "  {{.Service}}\t{{.State}}\t{{.Status}}" | column -t -s $'\t' || true

if [[ $failed -gt 0 ]]; then
  echo
  echo "$failed check(s) failed."
  echo "Tail relevant logs with:  docker compose logs -f caddy backend frontend"
  exit 1
fi

echo
echo "All checks passed."
