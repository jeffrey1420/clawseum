#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "[dev] .env created from .env.example"
fi

OVERRIDE_FILE="$(mktemp)"
trap 'rm -f "$OVERRIDE_FILE"' EXIT

cat > "$OVERRIDE_FILE" <<'YAML'
services:
  backend-gateway:
    environment:
      BACKEND_RELOAD: 1
    command: ["sh", "-c", "uvicorn ${GATEWAY_APP_MODULE:-main:app} --host 0.0.0.0 --port 8000 --reload"]
    volumes:
      - ./backend:/app/src

  backend-arena:
    environment:
      BACKEND_RELOAD: 1
    command: ["sh", "-c", "uvicorn ${ARENA_APP_MODULE:-main:app} --host 0.0.0.0 --port 8001 --reload"]
    volumes:
      - ./backend:/app/src

  backend-feed:
    environment:
      BACKEND_RELOAD: 1
    command: ["sh", "-c", "uvicorn ${FEED_APP_MODULE:-main:app} --host 0.0.0.0 --port 8002 --reload"]
    volumes:
      - ./backend:/app/src

  frontend:
    environment:
      NODE_ENV: development
    command: ["sh", "-c", "if [ ! -d node_modules ] || [ -z \"$(ls -A node_modules 2>/dev/null)\" ]; then if [ -f package-lock.json ]; then npm ci; else npm install; fi; fi; npm run dev -- --host 0.0.0.0 --port 3000"]
    volumes:
      - ./frontend:/app
      - /app/node_modules
YAML

echo "[dev] Starting CLAWSEUM in development mode with hot reload..."
docker compose -f docker-compose.yml -f "$OVERRIDE_FILE" up --build
