#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "[deploy] Missing .env file. Create it from .env.example first."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source ./.env
set +a

echo "[deploy] Building images..."
docker compose build --pull

echo "[deploy] Launching stack..."
docker compose up -d postgres redis backend-gateway backend-arena backend-feed frontend nginx

echo "[deploy] Running migrations..."
MIGRATION_SERVICE="${MIGRATION_SERVICE:-backend-gateway}"
MIGRATION_CMD="${MIGRATION_CMD:-python -m alembic upgrade head}"
docker compose run --rm "$MIGRATION_SERVICE" sh -lc "$MIGRATION_CMD"

echo "[deploy] Optional seed (set DEPLOY_SEED=1 to enable)"
if [[ "${DEPLOY_SEED:-0}" == "1" ]]; then
  "$ROOT_DIR/scripts/seed-data.sh"
fi

echo "[deploy] Deployment complete"
docker compose ps
