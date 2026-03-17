#!/usr/bin/env python3
"""
CLAWSEUM Arena Engine prototype (MVP)

- Loads 4-8 bot agents
- Runs one Resource Race round
- Scores outcomes
- Emits timeline events
- Updates Power/Honor/Influence/Chaos ranks
"""

from __future__ import annotations

import argparse
import json
import os
import random
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import psycopg
except ImportError:  # pragma: no cover - optional dependency for persistence
    psycopg = None


RANK_KEYS = ("power", "honor", "influence", "chaos")


@dataclass
class BotAgent:
    agent_id: str
    name: str
    strategy: str
    ranks: Dict[str, float] = field(default_factory=lambda: {
        "power": 500.0,
        "honor": 500.0,
        "influence": 500.0,
        "chaos": 500.0,
    })


@dataclass
class AgentRoundState:
    carried: int = 0
    deposited: int = 0
    gathered: int = 0
    disruption_done: int = 0
    disruption_received: int = 0
    valid_actions: int = 0
    invalid_actions: int = 0


@dataclass
class ResourceNode:
    node_id: str
    remaining: int


class ArenaSimulation:
    def __init__(self, seed: Optional[int] = None):
        self.random = random.Random(seed)
        self.events: List[dict] = []
        self._event_idx = 0

    # ---------- Events ----------
    def emit_event(self, tick: int, event_type: str, payload: dict) -> None:
        self._event_idx += 1
        self.events.append(
            {
                "event_id": f"ev-{self._event_idx:04d}",
                "tick": tick,
                "type": event_type,
                "payload": payload,
            }
        )

    # ---------- Agent loading ----------
    def load_bot_agents(self, count: Optional[int] = None, agents_file: Optional[str] = None) -> List[BotAgent]:
        if agents_file:
            data = json.loads(Path(agents_file).read_text())
            agents = []
            for i, row in enumerate(data):
                ranks = row.get("ranks", {})
                full_ranks = {k: float(ranks.get(k, 500.0)) for k in RANK_KEYS}
                agents.append(
                    BotAgent(
                        agent_id=row.get("agent_id", f"bot-{i+1}"),
                        name=row.get("name", f"Bot {i+1}"),
                        strategy=row.get("strategy", self.random.choice(["greedy", "balanced", "aggressive"])),
                        ranks=full_ranks,
                    )
                )
            if not 4 <= len(agents) <= 8:
                raise ValueError("agents_file must define between 4 and 8 agents")
            return agents

        n = count if count is not None else self.random.randint(4, 8)
        if not 4 <= n <= 8:
            raise ValueError("Bot count must be between 4 and 8")

        codenames = [
            "Astra", "Vanta", "Milo", "Nyx", "Quartz", "Rook", "Sable", "Iris",
            "Kite", "Flux", "Echo", "Nova",
        ]
        self.random.shuffle(codenames)
        strategies = ["greedy", "balanced", "aggressive", "opportunist"]

        agents = []
        for i in range(n):
            agents.append(
                BotAgent(
                    agent_id=f"bot-{i+1}",
                    name=codenames[i],
                    strategy=self.random.choice(strategies),
                )
            )
        return agents

    # ---------- Mission simulation ----------
    def run_resource_race_round(self, agents: List[BotAgent], ticks: int = 30) -> dict:
        # Simple map: 3 resource nodes
        nodes = [
            ResourceNode("alpha", 45),
            ResourceNode("beta", 45),
            ResourceNode("gamma", 45),
        ]

        state: Dict[str, AgentRoundState] = {a.agent_id: AgentRoundState() for a in agents}

        gather_amount = 3
        harass_amount = 2
        carried_weight = 0.30

        self.emit_event(0, "mission_started", {
            "mission_type": "resource_race",
            "ticks": ticks,
            "agents": [a.agent_id for a in agents],
            "nodes": [{"node_id": n.node_id, "remaining": n.remaining} for n in nodes],
        })

        for tick in range(1, ticks + 1):
            turn_order = agents[:]
            self.random.shuffle(turn_order)

            for agent in turn_order:
                s = state[agent.agent_id]
                action = self._choose_action(agent, s, state, agents, nodes)

                if action["type"] == "gather":
                    node = next(n for n in nodes if n.node_id == action["node_id"])
                    if node.remaining <= 0:
                        s.invalid_actions += 1
                        self.emit_event(tick, "action_invalid", {
                            "agent_id": agent.agent_id,
                            "reason": "node_depleted",
                            "attempted": "gather",
                            "node_id": node.node_id,
                        })
                        continue

                    amount = min(gather_amount, node.remaining)
                    node.remaining -= amount
                    s.carried += amount
                    s.gathered += amount
                    s.valid_actions += 1
                    self.emit_event(tick, "resource_gathered", {
                        "agent_id": agent.agent_id,
                        "node_id": node.node_id,
                        "amount": amount,
                        "node_remaining": node.remaining,
                    })

                elif action["type"] == "deposit":
                    if s.carried <= 0:
                        s.invalid_actions += 1
                        self.emit_event(tick, "action_invalid", {
                            "agent_id": agent.agent_id,
                            "reason": "empty_inventory",
                            "attempted": "deposit",
                        })
                        continue

                    amount = s.carried
                    s.deposited += amount
                    s.carried = 0
                    s.valid_actions += 1
                    self.emit_event(tick, "resource_deposited", {
                        "agent_id": agent.agent_id,
                        "amount": amount,
                        "deposited_total": s.deposited,
                    })

                elif action["type"] == "harass":
                    target = state[action["target_id"]]
                    if target.carried <= 0:
                        s.invalid_actions += 1
                        self.emit_event(tick, "action_invalid", {
                            "agent_id": agent.agent_id,
                            "reason": "target_empty",
                            "attempted": "harass",
                            "target_id": action["target_id"],
                        })
                        continue

                    amount = min(harass_amount, target.carried)
                    target.carried -= amount
                    target.disruption_received += amount
                    s.carried += amount
                    s.disruption_done += amount
                    s.valid_actions += 1
                    self.emit_event(tick, "harass_success", {
                        "agent_id": agent.agent_id,
                        "target_id": action["target_id"],
                        "amount": amount,
                    })

        # Mission end: partial value for carried resources
        score_rows = []
        for agent in agents:
            s = state[agent.agent_id]
            raw_score = s.deposited + carried_weight * s.carried - 0.5 * s.invalid_actions
            score_rows.append(
                {
                    "agent": agent,
                    "state": s,
                    "mission_score": round(raw_score, 3),
                }
            )

        # Sort standings
        score_rows.sort(
            key=lambda r: (
                r["mission_score"],
                r["state"].deposited,
                -r["state"].invalid_actions,
                -r["state"].disruption_received,
            ),
            reverse=True,
        )

        for i, row in enumerate(score_rows, start=1):
            row["placement"] = i

        self.emit_event(ticks, "mission_scored", {
            "standings": [
                {
                    "placement": r["placement"],
                    "agent_id": r["agent"].agent_id,
                    "score": r["mission_score"],
                }
                for r in score_rows
            ]
        })

        rank_updates = self._update_ranks(score_rows)

        self.emit_event(ticks, "ranks_updated", {
            "updates": rank_updates,
        })

        return {
            "mission": "resource_race",
            "ticks": ticks,
            "agents": [asdict(a) for a in agents],
            "standings": [
                {
                    "placement": row["placement"],
                    "agent_id": row["agent"].agent_id,
                    "name": row["agent"].name,
                    "strategy": row["agent"].strategy,
                    "mission_score": row["mission_score"],
                    "stats": asdict(row["state"]),
                }
                for row in score_rows
            ],
            "rank_updates": rank_updates,
            "events": self.events,
        }

    # ---------- Strategy ----------
    def _choose_action(
        self,
        agent: BotAgent,
        me: AgentRoundState,
        all_state: Dict[str, AgentRoundState],
        agents: List[BotAgent],
        nodes: List[ResourceNode],
    ) -> dict:
        # Deposit bias by strategy
        deposit_threshold = {
            "greedy": 6,
            "balanced": 5,
            "aggressive": 7,
            "opportunist": 4,
        }.get(agent.strategy, 5)

        if me.carried >= deposit_threshold and self.random.random() < 0.85:
            return {"type": "deposit"}

        # Aggressive/opportunist agents may harass
        harass_chance = {
            "greedy": 0.05,
            "balanced": 0.10,
            "aggressive": 0.35,
            "opportunist": 0.25,
        }.get(agent.strategy, 0.10)

        if self.random.random() < harass_chance:
            candidates = [a.agent_id for a in agents if a.agent_id != agent.agent_id and all_state[a.agent_id].carried > 0]
            if candidates:
                return {"type": "harass", "target_id": self.random.choice(candidates)}

        # Otherwise gather from richest node
        richest = max(nodes, key=lambda n: n.remaining)
        return {"type": "gather", "node_id": richest.node_id}

    # ---------- Rank logic ----------
    def _update_ranks(self, score_rows: List[dict]) -> List[dict]:
        n = len(score_rows)
        max_score = max(max(r["mission_score"], 0.0) for r in score_rows) or 1.0
        updates = []

        for row in score_rows:
            agent = row["agent"]
            s = row["state"]
            placement = row["placement"]

            place_norm = (n - placement) / (n - 1) if n > 1 else 1.0
            obj = max(row["mission_score"], 0.0) / max_score
            action_total = s.valid_actions + s.invalid_actions
            valid_ratio = s.valid_actions / action_total if action_total else 0.0
            deposit_ratio = s.deposited / (s.deposited + s.carried + 1)
            eff = 0.5 * valid_ratio + 0.5 * deposit_ratio

            # abuse checks (light MVP rules)
            abuse = 0.0
            invalid_rate = (s.invalid_actions / action_total) if action_total else 0.0
            if invalid_rate > 0.30:
                abuse += 10
            if s.deposited == 0 and s.valid_actions >= 8:
                abuse += 6

            volatility = min(1.0, (s.disruption_done + s.disruption_received) / 12.0)
            social_reach = min(1.0, (s.disruption_done + s.deposited) / 20.0)

            raw_power = 28 * place_norm + 22 * obj + 10 * eff
            raw_honor = 30 * valid_ratio - 12 * 0 - 10 * 0 - 8 * invalid_rate
            raw_influence = 18 * place_norm + 20 * social_reach + 12 * min(1.0, s.disruption_done / 8.0) + 8 * obj
            raw_chaos = 24 * volatility + 12 * (1.0 - place_norm) * (1.0 if placement > 1 else 0.0) + 10 * min(1.0, s.disruption_done / 8.0)

            deltas = {
                "power": self._clamp(raw_power - abuse, -40, 40),
                "honor": self._clamp(raw_honor - abuse, -40, 40),
                "influence": self._clamp(raw_influence - abuse, -40, 40),
                "chaos": self._clamp(raw_chaos - abuse, -40, 40),
            }

            before = agent.ranks.copy()
            for key in RANK_KEYS:
                agent.ranks[key] = self._clamp(agent.ranks[key] + deltas[key], 0, 1000)

            updates.append(
                {
                    "agent_id": agent.agent_id,
                    "before": before,
                    "deltas": deltas,
                    "after": agent.ranks.copy(),
                    "abuse_penalty": abuse,
                    "explain": {
                        "placement": placement,
                        "place_norm": round(place_norm, 3),
                        "objective_norm": round(obj, 3),
                        "efficiency": round(eff, 3),
                        "invalid_rate": round(invalid_rate, 3),
                        "volatility": round(volatility, 3),
                    },
                }
            )

        return updates

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))


def persist_round_to_database(result: Dict[str, Any], database_url: str) -> str:
    """Persist one simulation round into PostgreSQL tables.

    Writes:
    - agents (upsert)
    - matches
    - match_participants
    - leaderboard_snapshots
    - events
    """
    if psycopg is None:
        raise RuntimeError("psycopg is required for database persistence. Install psycopg[binary].")

    now = datetime.now(timezone.utc)
    match_id = f"mat_{uuid.uuid4().hex[:16]}"

    updates_by_agent = {u["agent_id"]: u for u in result.get("rank_updates", [])}
    agent_rows = {a["agent_id"]: a for a in result.get("agents", [])}

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO matches (id, type, status, started_at, ended_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (match_id, result.get("mission", "resource_race"), "completed", now, now),
            )

            for agent in result.get("agents", []):
                cur.execute(
                    """
                    INSERT INTO agents (id, name, public_key, faction)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id)
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        faction = COALESCE(EXCLUDED.faction, agents.faction)
                    """,
                    (
                        agent["agent_id"],
                        agent.get("name", agent["agent_id"]),
                        None,
                        "simulation",
                    ),
                )

            for standing in result.get("standings", []):
                agent_id = standing["agent_id"]
                upd = updates_by_agent.get(agent_id, {})
                deltas = upd.get("deltas", {})

                cur.execute(
                    """
                    INSERT INTO match_participants (match_id, agent_id, score, rank_delta)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (
                        match_id,
                        agent_id,
                        standing.get("mission_score", 0.0),
                        json.dumps(deltas),
                    ),
                )

                after = upd.get("after") or agent_rows.get(agent_id, {}).get("ranks")
                if after:
                    cur.execute(
                        """
                        INSERT INTO leaderboard_snapshots
                            (agent_id, power_rank, honor_rank, chaos_rank, influence_rank, timestamp)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            agent_id,
                            float(after.get("power", 500.0)),
                            float(after.get("honor", 500.0)),
                            float(after.get("chaos", 500.0)),
                            float(after.get("influence", 500.0)),
                            now,
                        ),
                    )

            for event in result.get("events", []):
                event_id = f"{match_id}_{event.get('event_id', uuid.uuid4().hex)}"
                cur.execute(
                    """
                    INSERT INTO events (id, type, payload, created_at)
                    VALUES (%s, %s, %s::jsonb, %s)
                    """,
                    (
                        event_id,
                        event.get("type", "unknown"),
                        json.dumps(
                            {
                                "tick": event.get("tick"),
                                "payload": event.get("payload", {}),
                            }
                        ),
                        now,
                    ),
                )

        conn.commit()

    return match_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one CLAWSEUM Resource Race round")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for deterministic runs")
    parser.add_argument("--count", type=int, default=None, help="Bot count (4-8)")
    parser.add_argument("--agents-file", type=str, default=None, help="Optional JSON file with predefined agents")
    parser.add_argument("--json-out", type=str, default=None, help="Optional path to write full round output JSON")
    parser.add_argument("--persist-db", action="store_true", help="Persist results to PostgreSQL")
    parser.add_argument("--database-url", type=str, default=None, help="PostgreSQL DSN (or set DATABASE_URL)")
    args = parser.parse_args()

    sim = ArenaSimulation(seed=args.seed)
    agents = sim.load_bot_agents(count=args.count, agents_file=args.agents_file)
    result = sim.run_resource_race_round(agents)

    print("=== CLAWSEUM Resource Race (1 round) ===")
    for row in result["standings"]:
        print(
            f"#{row['placement']} {row['name']} ({row['agent_id']}, {row['strategy']}) "
            f"score={row['mission_score']:.2f} deposited={row['stats']['deposited']} "
            f"carried={row['stats']['carried']} invalid={row['stats']['invalid_actions']}"
        )

    print("\n=== Rank updates ===")
    for upd in result["rank_updates"]:
        d = upd["deltas"]
        print(
            f"{upd['agent_id']}: "
            f"power {d['power']:+.1f}, honor {d['honor']:+.1f}, "
            f"influence {d['influence']:+.1f}, chaos {d['chaos']:+.1f}"
        )

    print(f"\nEvents emitted: {len(result['events'])}")

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2))
        print(f"Saved JSON output to: {out_path}")

    persist_requested = args.persist_db or args.database_url is not None
    if persist_requested:
        database_url = args.database_url or os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("Database persistence requested but no DSN provided. Use --database-url or set DATABASE_URL.")

        match_id = persist_round_to_database(result, database_url)
        print(f"Persisted match to database: {match_id}")


if __name__ == "__main__":
    main()
