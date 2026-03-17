#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[test] Running backend unit/API tests..."
PYTHONPATH="$ROOT_DIR/backend:${PYTHONPATH:-}" python3 -m pytest backend/tests -q

echo "[test] Running frontend build check..."
cd "$ROOT_DIR/frontend"
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
npm run build

cd "$ROOT_DIR"
if command -v docker >/dev/null 2>&1; then
  echo "[test] Validating Docker Compose file..."
  docker compose -f docker-compose.yml config -q
else
  echo "[test] Docker is not installed; skipping docker-compose validation."
fi

echo "[test] All checks passed."
