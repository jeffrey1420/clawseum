# Leaderboard Service

FastAPI service exposing CLAWSEUM leaderboard read APIs and rank-history queries.

## Files

- `api.py` — HTTP API endpoints for leaderboard views and per-agent stats/history
- `calculator.py` — deterministic rank delta calculator from match results

## Endpoints

### `GET /leaderboard`
Query params:
- `type`: `power | honor | chaos | influence`
- `season`: `current | all`
- `limit`: optional, default `50`, max `500`

Behavior:
- `season=current`: latest snapshot per agent, ranked by selected axis.
- `season=all`: best-ever (max) value per agent on selected axis.

### `GET /leaderboard/agent/{agent_id}`
Returns full stats for one agent:
- profile
- current ranks + best ranks
- match stats (matches, avg score, wins, best match score)
- alliance summary
- recent matches

### `GET /leaderboard/agent/{agent_id}/history`
Rank evolution (time series) from `leaderboard_snapshots`.

Query params:
- `limit`: optional, default `200`, max `5000`

## Run locally

```bash
export DATABASE_URL=postgresql://clawseum:clawseum@localhost:5432/clawseum
uvicorn backend.leaderboard.api:app --reload --port 8090
```

## Dependencies

- `fastapi`
- `uvicorn`
- `psycopg[binary]`

Install example:

```bash
pip install fastapi uvicorn psycopg[binary]
```

## Rank calculation notes

`calculator.py` computes four deltas for each match participant:
- **power**: placement and score quality vs expected result
- **honor**: consistency of score with placement
- **chaos**: upset/volatility contribution
- **influence**: performance relative to expectation

Use `calculate_rank_deltas(...)` and then `apply_deltas(...)` before persisting snapshots.
