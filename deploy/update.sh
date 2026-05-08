#!/usr/bin/env bash
# Pull new code, rebuild, restart. Run from /opt/leadmagnet on the VPS.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
docker compose up -d --build
docker image prune -f
echo "Updated."
