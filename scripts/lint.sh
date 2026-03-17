#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[lint] Python style checks (ruff + black)..."
python3 -m ruff check backend/tests backend/leaderboard backend/arena-engine/simulation.py
python3 -m black --check backend/tests

echo "[lint] Lint checks passed."
