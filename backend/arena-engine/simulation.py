"""CLAWSEUM Arena Engine - Simulation Module (Backward Compatible).

This module provides backward compatibility with the original simulation.py API.
It wraps the new arena engine components in the legacy interface.
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Handle both module imports and direct imports
try:
    # Import from new arena engine (when loaded as package)
    from .config import (
        RANK_AXES,
        DEFAULT_RATING,
        AgentConfig,
        AgentState,
        ResourceNode,
        MissionType,
        MatchStatus,
        generate_match_id,
    )
    from .mission_runner import MissionRunnerFactory, ArenaSimulationAdapter
    from .scoring import ScoringEngine
except ImportError:
    # Fallback for direct execution or test loading
    from config import (
        RANK_AXES,
        DEFAULT_RATING,
        AgentConfig,
        AgentState,
        ResourceNode,
        MissionType,
        MatchStatus,
        generate_match_id,
    )
    from mission_runner import MissionRunnerFactory, ArenaSimulationAdapter
    from scoring import ScoringEngine

# Legacy imports for compatibility
RANK_KEYS = RANK_AXES


@dataclass
class BotAgent:
    """Legacy BotAgent dataclass - wraps AgentConfig."""
    agent_id: str
    name: str
    strategy: str
    ranks: Dict[str, float] = field(default_factory=lambda: {
        "power": 500.0,
        "honor": 500.0,
        "influence": 500.0,
        "chaos": 500.0,
    })
    
    def to_config(self) -> AgentConfig:
        """Convert to new AgentConfig."""
        return AgentConfig(
            agent_id=self.agent_id,
            name=self.name,
            strategy=self.strategy,
            ranks=self.ranks.copy(),
            is_bot=True,
        )
    
    @classmethod
    def from_config(cls, config: AgentConfig) -> "BotAgent":
        """Create from AgentConfig."""
        return cls(
            agent_id=config.agent_id,
            name=config.name,
            strategy=config.strategy,
            ranks=config.ranks.copy(),
        )


@dataclass
class AgentRoundState:
    """Legacy AgentRoundState dataclass - wraps AgentState."""
    carried: int = 0
    deposited: int = 0
    gathered: int = 0
    disruption_done: int = 0
    disruption_received: int = 0
    valid_actions: int = 0
    invalid_actions: int = 0
    
    def to_state(self) -> AgentState:
        """Convert to new AgentState."""
        state = AgentState()
        state.carried = self.carried
        state.deposited = self.deposited
        state.gathered = self.gathered
        state.disruption_done = self.disruption_done
        state.disruption_received = self.disruption_received
        state.valid_actions = self.valid_actions
        state.invalid_actions = self.invalid_actions
        return state
    
    @classmethod
    def from_state(cls, state: AgentState) -> "AgentRoundState":
        """Create from AgentState."""
        return cls(
            carried=state.carried,
            deposited=state.deposited,
            gathered=state.gathered,
            disruption_done=state.disruption_done,
            disruption_received=state.disruption_received,
            valid_actions=state.valid_actions,
            invalid_actions=state.invalid_actions,
        )


# ResourceNode is now in config.py - re-export for compatibility
__all__ = [
    "RANK_KEYS",
    "BotAgent",
    "AgentRoundState",
    "ResourceNode",
    "ArenaSimulation",
    "persist_round_to_database",
]


class ArenaSimulation:
    """Legacy ArenaSimulation class - wraps new MissionRunner."""
    
    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        self.random = random.Random(seed)
        self.events: List[dict] = []
        self._event_idx = 0
        self._adapter = ArenaSimulationAdapter(seed=seed)
        self._scoring = ScoringEngine()
    
    def emit_event(self, tick: int, event_type: str, payload: dict) -> None:
        """Legacy event emission (now handled by runner)."""
        self._event_idx += 1
        self.events.append({
            "event_id": f"ev-{self._event_idx:04d}",
            "tick": tick,
            "type": event_type,
            "payload": payload,
        })
    
    def load_bot_agents(
        self,
        count: Optional[int] = None,
        agents_file: Optional[str] = None,
    ) -> List[BotAgent]:
        """Load bot agents (legacy API)."""
        if agents_file:
            import json
            data = json.loads(Path(agents_file).read_text())
            agents = []
            for i, row in enumerate(data):
                ranks = row.get("ranks", {})
                full_ranks = {k: float(ranks.get(k, 500.0)) for k in RANK_KEYS}
                agents.append(BotAgent(
                    agent_id=row.get("agent_id", f"bot-{i+1}"),
                    name=row.get("name", f"Bot {i+1}"),
                    strategy=row.get("strategy", self.random.choice([
                        "greedy", "balanced", "aggressive"
                    ])),
                    ranks=full_ranks,
                ))
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
            agents.append(BotAgent(
                agent_id=f"bot-{i+1}",
                name=codenames[i],
                strategy=self.random.choice(strategies),
            ))
        return agents
    
    def run_resource_race_round(
        self,
        agents: List[BotAgent],
        ticks: int = 30,
    ) -> dict:
        """Run a resource race round (legacy API - async wrapped)."""
        import asyncio
        
        # Convert to new format
        agents_data = [
            {
                "agent_id": a.agent_id,
                "name": a.name,
                "strategy": a.strategy,
                "ranks": a.ranks,
            }
            for a in agents
        ]
        
        # Run using new adapter
        result = asyncio.run(self._adapter.run_resource_race_round(
            agents_data=agents_data,
            ticks=ticks,
        ))
        
        # Convert events to legacy format
        self.events = result.get("events", [])
        
        return result
    
    def _choose_action(
        self,
        agent: BotAgent,
        me: AgentRoundState,
        all_state: Dict[str, AgentRoundState],
        agents: List[BotAgent],
        nodes: List[ResourceNode],
    ) -> dict:
        """Legacy action selection (now handled by agent runtime)."""
        # Simplified legacy logic for compatibility
        deposit_threshold = {
            "greedy": 6,
            "balanced": 5,
            "aggressive": 7,
            "opportunist": 4,
        }.get(agent.strategy, 5)
        
        if me.carried >= deposit_threshold and self.random.random() < 0.85:
            return {"type": "deposit"}
        
        harass_chance = {
            "greedy": 0.05,
            "balanced": 0.10,
            "aggressive": 0.35,
            "opportunist": 0.25,
        }.get(agent.strategy, 0.10)
        
        if self.random.random() < harass_chance:
            candidates = [
                a.agent_id for a in agents
                if a.agent_id != agent.agent_id and all_state[a.agent_id].carried > 0
            ]
            if candidates:
                return {"type": "harass", "target_id": self.random.choice(candidates)}
        
        richest = max(nodes, key=lambda n: n.remaining)
        return {"type": "gather", "node_id": richest.node_id}
    
    def _update_ranks(self, score_rows: List[dict]) -> List[dict]:
        """Legacy rank update (now handled by scoring engine)."""
        # This is now handled internally by the scoring engine
        return [row.get("rank_update", {}) for row in score_rows]
    
    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        """Clamp a value."""
        return max(low, min(high, value))


def persist_round_to_database(result: Dict[str, Any], database_url: str) -> str:
    """Persist round to database (legacy API)."""
    try:
        import psycopg
    except ImportError:
        raise RuntimeError("psycopg is required for database persistence")
    
    import uuid
    
    now = datetime.now(timezone.utc)
    match_id = result.get("match_id") or f"mat_{uuid.uuid4().hex[:16]}"
    
    updates_by_agent = {u["agent_id"]: u for u in result.get("rank_updates", [])}
    agent_rows = {a["agent_id"]: a for a in result.get("agents", [])}
    
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO matches (id, type, status, started_at, ended_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    ended_at = EXCLUDED.ended_at
                """,
                (match_id, result.get("mission", "resource_race"), "completed", now, now),
            )
            
            for agent in result.get("agents", []):
                cur.execute(
                    """
                    INSERT INTO agents (id, name, public_key, faction)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
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
                    ON CONFLICT (match_id, agent_id) DO UPDATE SET
                        score = EXCLUDED.score,
                        rank_delta = EXCLUDED.rank_delta
                    """,
                    (match_id, agent_id, standing.get("mission_score", 0.0), 
                     __import__('json').dumps(deltas)),
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
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        event_id,
                        event.get("type", "unknown"),
                        __import__('json').dumps({
                            "tick": event.get("tick"),
                            "payload": event.get("payload", {}),
                        }),
                        now,
                    ),
                )
        
        conn.commit()
    
    return match_id


def main() -> None:
    """CLI entry point (backward compatible)."""
    import argparse
    import json
    import os
    
    parser = argparse.ArgumentParser(description="Run one CLAWSEUM Resource Race round")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--count", type=int, default=None, help="Bot count (4-8)")
    parser.add_argument("--agents-file", type=str, default=None, help="JSON file with agents")
    parser.add_argument("--json-out", type=str, default=None, help="Output JSON path")
    parser.add_argument("--persist-db", action="store_true", help="Persist to DB")
    parser.add_argument("--database-url", type=str, default=None, help="PostgreSQL DSN")
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
            raise RuntimeError("Database persistence requested but no DSN provided")
        
        match_id = persist_round_to_database(result, database_url)
        print(f"Persisted match to database: {match_id}")


if __name__ == "__main__":
    main()
