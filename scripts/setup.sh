#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    echo "[setup] .env created from .env.example"
  else
    echo "[setup] .env and .env.example not found. Aborting."
    exit 1
  fi
fi

set -a
# shellcheck disable=SC1091
source ./.env
set +a

echo "[setup] Starting data services (Postgres + Redis)..."
docker compose up -d postgres redis

echo "[setup] Waiting for Postgres..."
for _ in {1..40}; do
  if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-clawseum}" -d "${POSTGRES_DB:-clawseum}" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "[setup] Running migrations..."
MIGRATION_SERVICE="${MIGRATION_SERVICE:-backend-gateway}"
MIGRATION_CMD="${MIGRATION_CMD:-python -m alembic upgrade head}"
if ! docker compose run --rm "$MIGRATION_SERVICE" sh -lc "$MIGRATION_CMD"; then
  echo "[setup] Migration command failed. Set MIGRATION_CMD to your project command and retry."
  exit 1
fi

echo "[setup] Seeding demo data..."
"$ROOT_DIR/scripts/seed-data.sh"

echo "[setup] Starting full stack..."
docker compose up -d backend-gateway backend-arena backend-feed frontend nginx

echo "[setup] Complete. App available at http://localhost:${NGINX_PORT:-80}"
