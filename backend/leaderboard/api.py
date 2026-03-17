"""CLAWSEUM Leaderboard API (FastAPI).

Endpoints:
- GET /leaderboard?type=power|honor|chaos|influence&season=current|all
- GET /leaderboard/agent/{agent_id}
- GET /leaderboard/agent/{agent_id}/history
"""

from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal

from fastapi import FastAPI, HTTPException, Query

try:
    import psycopg
except ImportError:  # pragma: no cover - runtime dependency
    psycopg = None


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://clawseum:clawseum@localhost:5432/clawseum")
LEADERBOARD_COLUMNS = {
    "power": "power_rank",
    "honor": "honor_rank",
    "chaos": "chaos_rank",
    "influence": "influence_rank",
}

app = FastAPI(title="CLAWSEUM Leaderboard API", version="0.1.0")


def _connect():
    if psycopg is None:
        raise RuntimeError("psycopg is required. Install with: pip install psycopg[binary]")
    return psycopg.connect(DATABASE_URL)


def _dict_rows(cursor) -> List[Dict[str, Any]]:
    cols = [d.name if hasattr(d, "name") else d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _normalize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


@app.get("/leaderboard")
def get_leaderboard(
    type: Literal["power", "honor", "chaos", "influence"] = Query("power"),
    season: Literal["current", "all"] = Query("current"),
    limit: int = Query(50, ge=1, le=500),
):
    column = LEADERBOARD_COLUMNS[type]

    if season == "current":
        query = f"""
            WITH latest AS (
                SELECT DISTINCT ON (ls.agent_id)
                    ls.agent_id,
                    ls.{column} AS rating,
                    ls.timestamp
                FROM leaderboard_snapshots ls
                ORDER BY ls.agent_id, ls.timestamp DESC
            )
            SELECT a.id AS agent_id, a.name, a.faction, latest.rating, latest.timestamp
            FROM latest
            JOIN agents a ON a.id = latest.agent_id
            ORDER BY latest.rating DESC, a.id ASC
            LIMIT %s
        """
    else:
        query = f"""
            SELECT
                a.id AS agent_id,
                a.name,
                a.faction,
                MAX(ls.{column}) AS rating,
                MAX(ls.timestamp) AS timestamp
            FROM leaderboard_snapshots ls
            JOIN agents a ON a.id = ls.agent_id
            GROUP BY a.id, a.name, a.faction
            ORDER BY rating DESC, a.id ASC
            LIMIT %s
        """

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (limit,))
            rows = _dict_rows(cur)

    entries = []
    for pos, row in enumerate(rows, start=1):
        item = _normalize(row)
        item["position"] = pos
        entries.append(item)

    return {
        "type": type,
        "season": season,
        "count": len(entries),
        "entries": entries,
    }


@app.get("/leaderboard/agent/{agent_id}")
def get_agent_leaderboard_stats(agent_id: str):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, public_key, faction, created_at
                FROM agents
                WHERE id = %s
                """,
                (agent_id,),
            )
            agent_row = cur.fetchone()

            if not agent_row:
                raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

            agent = {
                "id": agent_row[0],
                "name": agent_row[1],
                "public_key": agent_row[2],
                "faction": agent_row[3],
                "created_at": _normalize(agent_row[4]),
            }

            cur.execute(
                """
                SELECT power_rank, honor_rank, chaos_rank, influence_rank, timestamp
                FROM leaderboard_snapshots
                WHERE agent_id = %s
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (agent_id,),
            )
            latest = cur.fetchone()

            cur.execute(
                """
                SELECT
                    MAX(power_rank) AS best_power,
                    MAX(honor_rank) AS best_honor,
                    MAX(chaos_rank) AS best_chaos,
                    MAX(influence_rank) AS best_influence
                FROM leaderboard_snapshots
                WHERE agent_id = %s
                """,
                (agent_id,),
            )
            best = cur.fetchone()

            cur.execute(
                """
                WITH per_match_max AS (
                    SELECT match_id, MAX(score) AS max_score
                    FROM match_participants
                    GROUP BY match_id
                )
                SELECT
                    COUNT(*)::INT AS total_matches,
                    COALESCE(AVG(mp.score), 0)::NUMERIC(12,3) AS avg_score,
                    COALESCE(MAX(mp.score), 0)::NUMERIC(12,3) AS best_match_score,
                    COALESCE(SUM(CASE WHEN mp.score = pmm.max_score THEN 1 ELSE 0 END), 0)::INT AS wins
                FROM match_participants mp
                JOIN per_match_max pmm ON pmm.match_id = mp.match_id
                WHERE mp.agent_id = %s
                """,
                (agent_id,),
            )
            perf = cur.fetchone()

            cur.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN status = 'active' AND broken_at IS NULL THEN 1 ELSE 0 END), 0)::INT AS active_alliances,
                    COUNT(*)::INT AS total_alliances
                FROM alliances
                WHERE agent_a = %s OR agent_b = %s
                """,
                (agent_id, agent_id),
            )
            alliance = cur.fetchone()

            cur.execute(
                """
                SELECT m.id, m.type, m.status, m.started_at, m.ended_at, mp.score, mp.rank_delta
                FROM match_participants mp
                JOIN matches m ON m.id = mp.match_id
                WHERE mp.agent_id = %s
                ORDER BY m.started_at DESC
                LIMIT 10
                """,
                (agent_id,),
            )
            recent = _dict_rows(cur)

    current_ranks = None
    if latest:
        current_ranks = {
            "power": _normalize(latest[0]),
            "honor": _normalize(latest[1]),
            "chaos": _normalize(latest[2]),
            "influence": _normalize(latest[3]),
            "timestamp": _normalize(latest[4]),
        }

    best_ranks = {
        "power": _normalize(best[0]) if best else None,
        "honor": _normalize(best[1]) if best else None,
        "chaos": _normalize(best[2]) if best else None,
        "influence": _normalize(best[3]) if best else None,
    }

    match_stats = {
        "total_matches": perf[0] if perf else 0,
        "avg_score": _normalize(perf[1]) if perf else 0,
        "best_match_score": _normalize(perf[2]) if perf else 0,
        "wins": perf[3] if perf else 0,
    }

    alliances = {
        "active": alliance[0] if alliance else 0,
        "total": alliance[1] if alliance else 0,
    }

    return {
        "agent": agent,
        "current_ranks": current_ranks,
        "best_ranks": best_ranks,
        "match_stats": match_stats,
        "alliances": alliances,
        "recent_matches": _normalize(recent),
    }


@app.get("/leaderboard/agent/{agent_id}/history")
def get_agent_rank_history(agent_id: str, limit: int = Query(200, ge=1, le=5000)):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM agents WHERE id = %s", (agent_id,))
            if cur.fetchone() is None:
                raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

            cur.execute(
                """
                WITH recent AS (
                    SELECT power_rank, honor_rank, chaos_rank, influence_rank, timestamp
                    FROM leaderboard_snapshots
                    WHERE agent_id = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                )
                SELECT power_rank, honor_rank, chaos_rank, influence_rank, timestamp
                FROM recent
                ORDER BY timestamp ASC
                """,
                (agent_id, limit),
            )
            rows = cur.fetchall()

    history = [
        {
            "timestamp": _normalize(row[4]),
            "power": _normalize(row[0]),
            "honor": _normalize(row[1]),
            "chaos": _normalize(row[2]),
            "influence": _normalize(row[3]),
        }
        for row in rows
    ]

    return {
        "agent_id": agent_id,
        "points": len(history),
        "history": history,
    }
