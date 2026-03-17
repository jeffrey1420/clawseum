#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

AGENTS="${SEED_AGENT_COUNT:-24}"
MATCHES="${SEED_MATCH_COUNT:-72}"
OUT_DIR="${SEED_OUTPUT_DIR:-data/seed}"

if [[ -n "${SEED_CMD:-}" ]]; then
  echo "[seed] Running custom seed command in backend-gateway container..."
  docker compose run --rm backend-gateway sh -lc "$SEED_CMD"
  exit 0
fi

mkdir -p "$OUT_DIR"

echo "[seed] Generating demo dataset (${AGENTS} agents / ${MATCHES} matches)..."
python3 - <<PY
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

agents_n = int(${AGENTS})
matches_n = int(${MATCHES})
out = Path("${OUT_DIR}")
out.mkdir(parents=True, exist_ok=True)

rng = random.Random(42)
factions = ["EMBER", "OBSIDIAN", "AURORA", "TIDAL", "NOVA", "VANGUARD"]
strategies = ["aggressive", "diplomatic", "opportunistic", "defensive", "chaotic"]

agents = []
for i in range(agents_n):
    handle = f"agent_{i+1:03d}"
    agents.append({
        "id": i + 1,
        "handle": handle,
        "display_name": handle.replace("_", "-").upper(),
        "faction": rng.choice(factions),
        "strategy": rng.choice(strategies),
        "power_rank": rng.randint(900, 1300),
        "honor_rank": rng.randint(900, 1300),
    })

matches = []
now = datetime.now(timezone.utc)
for i in range(matches_n):
    a, b = rng.sample(agents, 2)
    winner = rng.choice([a, b])
    loser = b if winner["id"] == a["id"] else a
    matches.append({
        "id": i + 1,
        "started_at": (now - timedelta(minutes=15 * (matches_n - i))).isoformat(),
        "mission": rng.choice(["resource_race", "treaty_break", "sabotage_defense"]),
        "winner_agent_id": winner["id"],
        "loser_agent_id": loser["id"],
        "duration_seconds": rng.randint(120, 1800),
        "betrayal": rng.random() < 0.22,
        "spectator_votes": rng.randint(0, 4000),
    })

with (out / "agents.jsonl").open("w", encoding="utf-8") as f:
    for row in agents:
        f.write(json.dumps(row) + "\\n")

with (out / "matches.jsonl").open("w", encoding="utf-8") as f:
    for row in matches:
        f.write(json.dumps(row) + "\\n")

with (out / "seed-summary.json").open("w", encoding="utf-8") as f:
    json.dump({"agents": agents_n, "matches": matches_n, "generated_at": now.isoformat()}, f, indent=2)
PY

echo "[seed] Files created in ${OUT_DIR}/"

if [[ "${SEED_PUSH_TO_API:-0}" == "1" ]]; then
  echo "[seed] SEED_PUSH_TO_API=1 set. Pushing payloads to gateway seed endpoint..."
  curl -fsS -X POST "${SEED_API_URL:-http://localhost:8000/admin/seed}" \
    -H 'Content-Type: application/json' \
    --data-binary @"${OUT_DIR}/seed-summary.json" || {
    echo "[seed] Warning: API seed push failed. Dataset files are still generated."
  }
fi
