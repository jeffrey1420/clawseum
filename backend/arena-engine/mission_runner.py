"""CLAWSEUM Arena Engine - Mission Runner.

Mission execution system:
- Load mission configuration
- Initialize agents from DB
- Execute mission phases (Resource Race, Negotiation, Sabotage)
- Real-time event generation
- Final scoring and rank updates
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Tuple

from config import (
    MissionType,
    MatchStatus,
    EventType,
    AgentConfig,
    AgentState,
    MissionConfig,
    MatchConfig,
    MatchResult,
    ResourceNode,
    StandingDict,
    RankUpdateDict,
    EventDict,
    DEFAULT_MATCH_TICKS,
    MIN_AGENTS,
    MAX_AGENTS,
    GATHER_AMOUNT,
    HARASS_AMOUNT,
    CARRIED_WEIGHT,
    generate_event_id,
)
from agent_runtime import (
    AgentRuntime,
    Observation,
    ActionExecutor,
    DecisionResult,
)
from scoring import ScoringEngine

logger = logging.getLogger(__name__)


EventCallback = Callable[[str, EventDict], Coroutine[Any, Any, None]]
ProgressCallback = Callable[[str, Dict[str, Any]], Coroutine[Any, Any, None]]


@dataclass
class PhaseContext:
    """Context for executing a mission phase."""
    phase_type: MissionType
    tick_start: int
    tick_end: int
    parameters: Dict[str, Any] = field(default_factory=dict)


class MissionRunner:
    """Runner for executing complete missions with multiple phases."""
    
    def __init__(
        self,
        match_config: MatchConfig,
        agent_runtime: Optional[AgentRuntime] = None,
        scoring_engine: Optional[ScoringEngine] = None,
        database: Optional[Any] = None,
        rng: Optional[random.Random] = None,
    ):
        self.config = match_config
        self.match_id = match_config.match_id
        self.rng = rng or random.Random(match_config.seed)
        self.agent_runtime = agent_runtime or AgentRuntime(rng=self.rng)
        self.scoring_engine = scoring_engine or ScoringEngine()
        self.action_executor = ActionExecutor(rng=self.rng)
        self.database = database
        
        # Runtime state
        self.status = MatchStatus.PENDING
        self.agents: Dict[str, AgentConfig] = {}
        self.agent_states: Dict[str, AgentState] = {}
        self.nodes: List[ResourceNode] = []
        self.events: List[EventDict] = []
        self._event_index = 0
        self._current_tick = 0
        self._phase_contexts: List[PhaseContext] = []
        
        # Callbacks for real-time updates
        self._event_callbacks: List[EventCallback] = []
        self._progress_callbacks: List[ProgressCallback] = []
        
        # Timing
        self.started_at: Optional[datetime] = None
        self.ended_at: Optional[datetime] = None
    
    def add_event_callback(self, callback: EventCallback) -> None:
        """Add a callback for real-time event updates."""
        self._event_callbacks.append(callback)
    
    def add_progress_callback(self, callback: ProgressCallback) -> None:
        """Add a callback for progress updates."""
        self._progress_callbacks.append(callback)
    
    async def _emit_event(self, tick: int, event_type: EventType, payload: Dict[str, Any]) -> EventDict:
        """Emit an event and notify callbacks."""
        self._event_index += 1
        event: EventDict = {
            "event_id": generate_event_id(self._event_index),
            "tick": tick,
            "type": event_type.value,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.events.append(event)
        
        # Notify callbacks
        for callback in self._event_callbacks:
            try:
                await callback(self.match_id, event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")
        
        return event
    
    async def _emit_progress(self, state: str, data: Dict[str, Any]) -> None:
        """Emit a progress update."""
        progress = {
            "match_id": self.match_id,
            "state": state,
            "tick": self._current_tick,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data,
        }
        
        for callback in self._progress_callbacks:
            try:
                await callback(self.match_id, progress)
            except Exception as e:
                logger.error(f"Progress callback error: {e}")
    
    async def initialize(self) -> None:
        """Initialize the mission: load agents and set up state."""
        logger.info(f"Initializing mission {self.match_id}")
        self.status = MatchStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)
        
        # Validate agent count
        agent_list = self.config.agents
        if not MIN_AGENTS <= len(agent_list) <= MAX_AGENTS:
            raise ValueError(f"Agent count must be between {MIN_AGENTS} and {MAX_AGENTS}")
        
        # Initialize agents
        for agent_config in agent_list:
            self.agents[agent_config.agent_id] = agent_config
            self.agent_states[agent_config.agent_id] = AgentState()
        
        # Initialize resource nodes
        self._initialize_nodes()
        
        # Build phase contexts
        self._build_phase_contexts()
        
        # Emit initialization event
        await self._emit_event(
            0,
            EventType.MISSION_STARTED,
            {
                "mission_type": self.config.mission.mission_type.value,
                "phases": [p.value for p in self.config.mission.phases],
                "ticks": self.config.mission.ticks,
                "agents": [a.agent_id for a in agent_list],
                "nodes": [{"node_id": n.node_id, "remaining": n.remaining} for n in self.nodes],
            }
        )
        
        await self._emit_progress("initialized", {
            "agent_count": len(agent_list),
            "phase_count": len(self._phase_contexts),
        })
    
    def _initialize_nodes(self) -> None:
        """Initialize resource nodes based on mission configuration."""
        node_config = self.config.mission.parameters.get("nodes", {})
        node_count = node_config.get("count", 3)
        node_resources = node_config.get("resources_per_node", 45)
        
        node_names = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta"]
        self.nodes = [
            ResourceNode(
                node_id=node_names[i],
                remaining=node_resources,
            )
            for i in range(min(node_count, len(node_names)))
        ]
    
    def _build_phase_contexts(self) -> None:
        """Build phase execution contexts."""
        ticks_per_phase = self.config.mission.ticks // max(len(self.config.mission.phases), 1)
        
        for i, phase_type in enumerate(self.config.mission.phases):
            tick_start = i * ticks_per_phase + 1
            tick_end = (i + 1) * ticks_per_phase if i < len(self.config.mission.phases) - 1 else self.config.mission.ticks
            
            self._phase_contexts.append(PhaseContext(
                phase_type=phase_type,
                tick_start=tick_start,
                tick_end=tick_end,
                parameters=self.config.mission.parameters.get(phase_type.value, {}),
            ))
    
    async def run(self) -> MatchResult:
        """Run the complete mission."""
        try:
            await self.initialize()
            
            # Execute each phase
            for phase_ctx in self._phase_contexts:
                await self._execute_phase(phase_ctx)
            
            # Calculate final results
            result = await self._finalize()
            return result
            
        except Exception as e:
            logger.exception(f"Mission {self.match_id} failed: {e}")
            self.status = MatchStatus.FAILED
            self.ended_at = datetime.now(timezone.utc)
            
            # Emit failure event
            await self._emit_event(
                self._current_tick,
                EventType.MISSION_FAILED,
                {"error": str(e), "traceback": str(e.__traceback__)},
            )
            
            return MatchResult(
                match_id=self.match_id,
                mission_type=self.config.mission.mission_type,
                status=MatchStatus.FAILED,
                agents=[self._agent_to_dict(a) for a in self.agents.values()],
                standings=[],
                rank_updates=[],
                events=self.events,
                started_at=self.started_at or datetime.now(timezone.utc),
                ended_at=self.ended_at,
                error=str(e),
            )
    
    async def _execute_phase(self, phase_ctx: PhaseContext) -> None:
        """Execute a single mission phase."""
        logger.info(f"Executing phase {phase_ctx.phase_type.value} for mission {self.match_id}")
        
        await self._emit_event(
            self._current_tick,
            EventType.PHASE_STARTED,
            {
                "phase": phase_ctx.phase_type.value,
                "tick_start": phase_ctx.tick_start,
                "tick_end": phase_ctx.tick_end,
            }
        )
        
        if phase_ctx.phase_type == MissionType.RESOURCE_RACE:
            await self._execute_resource_race_phase(phase_ctx)
        elif phase_ctx.phase_type == MissionType.NEGOTIATION:
            await self._execute_negotiation_phase(phase_ctx)
        elif phase_ctx.phase_type == MissionType.SABOTAGE:
            await self._execute_sabotage_phase(phase_ctx)
        
        await self._emit_event(
            self._current_tick,
            EventType.PHASE_COMPLETED,
            {"phase": phase_ctx.phase_type.value}
        )
    
    async def _execute_resource_race_phase(self, phase_ctx: PhaseContext) -> None:
        """Execute a resource race phase."""
        for tick in range(phase_ctx.tick_start, phase_ctx.tick_end + 1):
            self._current_tick = tick
            
            # Random turn order
            turn_order = list(self.agents.values())
            self.rng.shuffle(turn_order)
            
            for agent in turn_order:
                await self._execute_agent_turn(agent, tick, "resource_race")
            
            # Progress update every 5 ticks
            if tick % 5 == 0:
                await self._emit_progress("running", {
                    "phase": "resource_race",
                    "tick": tick,
                    "total_ticks": self.config.mission.ticks,
                })
    
    async def _execute_negotiation_phase(self, phase_ctx: PhaseContext) -> None:
        """Execute a negotiation phase."""
        # Negotiation happens in rounds with all agents participating
        negotiation_rounds = phase_ctx.parameters.get("rounds", 5)
        
        for round_num in range(negotiation_rounds):
            tick = phase_ctx.tick_start + round_num
            self._current_tick = tick
            
            turn_order = list(self.agents.values())
            self.rng.shuffle(turn_order)
            
            for agent in turn_order:
                await self._execute_agent_turn(agent, tick, "negotiation")
            
            await self._emit_progress("running", {
                "phase": "negotiation",
                "round": round_num + 1,
                "total_rounds": negotiation_rounds,
            })
    
    async def _execute_sabotage_phase(self, phase_ctx: PhaseContext) -> None:
        """Execute a sabotage phase."""
        sabotage_ticks = phase_ctx.tick_end - phase_ctx.tick_start + 1
        
        for i in range(sabotage_ticks):
            tick = phase_ctx.tick_start + i
            self._current_tick = tick
            
            turn_order = list(self.agents.values())
            self.rng.shuffle(turn_order)
            
            for agent in turn_order:
                await self._execute_agent_turn(agent, tick, "sabotage")
            
            await self._emit_progress("running", {
                "phase": "sabotage",
                "tick": i + 1,
                "total_ticks": sabotage_ticks,
            })
    
    async def _execute_agent_turn(
        self,
        agent: AgentConfig,
        tick: int,
        phase: str,
    ) -> None:
        """Execute a single agent's turn."""
        agent_state = self.agent_states[agent.agent_id]
        
        # Build observation
        observation = Observation(
            tick=tick,
            phase=phase,
            own_state=agent_state,
            visible_agents=[a.agent_id for a in self.agents.values() if a.agent_id != agent.agent_id],
            visible_nodes=self.nodes,
            recent_events=self.events[-10:],  # Last 10 events
            available_actions=self._get_available_actions(phase),
        )
        
        # Get decision from agent
        decision = await self.agent_runtime.execute_decision(
            agent_config=agent,
            observation=observation,
            context={"match_id": self.match_id, "phase": phase},
        )
        
        if not decision.success:
            # Emit error event
            await self._emit_event(
                tick,
                EventType.AGENT_ERROR,
                {
                    "agent_id": agent.agent_id,
                    "error": decision.error,
                    "fallback_action": decision.action,
                }
            )
        
        # Execute action
        result = self.action_executor.execute(
            action=decision.action,
            agent_id=agent.agent_id,
            agent_states=self.agent_states,
            nodes=self.nodes,
            gather_amount=GATHER_AMOUNT,
            harass_amount=HARASS_AMOUNT,
        )
        
        # Emit appropriate event based on action
        await self._emit_action_event(tick, agent.agent_id, decision.action, result)
    
    def _get_available_actions(self, phase: str) -> List[Any]:
        """Get available actions for a phase."""
        from agent_runtime import ActionType
        
        if phase == "resource_race":
            return [ActionType.GATHER, ActionType.DEPOSIT, ActionType.HARASS]
        elif phase == "negotiation":
            return [ActionType.NEGOTIATE, ActionType.ALLY, ActionType.BETRAY]
        elif phase == "sabotage":
            return [ActionType.SABOTAGE, ActionType.DEFEND]
        return []
    
    async def _emit_action_event(
        self,
        tick: int,
        agent_id: str,
        action: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        """Emit the appropriate event for an action."""
        action_type = action.get("type")
        
        if not result.get("success"):
            await self._emit_event(
                tick,
                EventType.ACTION_INVALID,
                {
                    "agent_id": agent_id,
                    "attempted": action_type,
                    "reason": result.get("error", "unknown"),
                    "target_id": action.get("target_id"),
                    "node_id": action.get("node_id"),
                }
            )
            return
        
        event_map = {
            "gather": EventType.RESOURCE_GATHERED,
            "deposit": EventType.RESOURCE_DEPOSITED,
            "harass": EventType.HARASS_SUCCESS,
            "sabotage": EventType.SABOTAGE_SUCCESS if result.get("result") == "success" else EventType.SABOTAGE_ATTEMPT,
            "ally": EventType.ALLIANCE_FORMED if result.get("accepted") else EventType.TREATY_REJECTED,
            "betray": EventType.BETRAYAL_DETECTED,
            "defend": EventType.ACTION_INVALID,  # Defend doesn't emit normally
            "skip": EventType.ACTION_INVALID,
        }
        
        event_type = event_map.get(action_type)
        if event_type:
            payload = {
                "agent_id": agent_id,
                **{k: v for k, v in result.items() if k not in ("success", "action")},
            }
            await self._emit_event(tick, event_type, payload)
    
    async def _finalize(self) -> MatchResult:
        """Finalize the mission: calculate scores and update ranks."""
        logger.info(f"Finalizing mission {self.match_id}")
        
        # Calculate scores
        agent_scores: List[Tuple[str, float, AgentState]] = []
        for agent_id, agent in self.agents.items():
            state = self.agent_states[agent_id]
            raw_score = (
                state.deposited +
                CARRIED_WEIGHT * state.carried -
                0.5 * state.invalid_actions +
                0.1 * state.gathered
            )
            agent_scores.append((agent_id, raw_score, state))
        
        # Calculate standings
        standings = self.scoring_engine.calculate_standings(
            agent_scores,
            self.agents,
        )
        
        # Emit scored event
        await self._emit_event(
            self._current_tick,
            EventType.MISSION_SCORED,
            {
                "standings": [
                    {
                        "placement": s["placement"],
                        "agent_id": s["agent_id"],
                        "score": s["mission_score"],
                    }
                    for s in standings
                ]
            }
        )
        
        # Calculate rank updates
        rank_updates = self.scoring_engine.calculate_all_updates(
            standings,
            self.agent_states,
            self.agents,
        )
        
        # Update agent configs with new ranks
        for update in rank_updates:
            agent = self.agents.get(update["agent_id"])
            if agent:
                agent.ranks = update["after"]
        
        # Emit ranks updated event
        await self._emit_event(
            self._current_tick,
            EventType.RANKS_UPDATED,
            {"updates": rank_updates}
        )
        
        # Set final status
        self.status = MatchStatus.COMPLETED
        self.ended_at = datetime.now(timezone.utc)
        
        await self._emit_progress("completed", {
            "standings_count": len(standings),
            "events_count": len(self.events),
        })
        
        # Build result
        return MatchResult(
            match_id=self.match_id,
            mission_type=self.config.mission.mission_type,
            status=MatchStatus.COMPLETED,
            agents=[self._agent_to_dict(a) for a in self.agents.values()],
            standings=standings,
            rank_updates=rank_updates,
            events=self.events,
            started_at=self.started_at or datetime.now(timezone.utc),
            ended_at=self.ended_at,
        )
    
    def _agent_to_dict(self, agent: AgentConfig) -> Dict[str, Any]:
        """Convert agent config to dict."""
        return {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "strategy": agent.strategy,
            "ranks": agent.ranks,
            "faction": agent.faction,
            "is_bot": agent.is_bot,
        }


class MissionRunnerFactory:
    """Factory for creating mission runners."""
    
    @staticmethod
    def create(
        mission_type: MissionType,
        agents: List[AgentConfig],
        ticks: int = DEFAULT_MATCH_TICKS,
        seed: Optional[int] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> MissionRunner:
        """Create a mission runner with the given configuration."""
        config = MatchConfig(
            mission=MissionConfig(
                mission_type=mission_type,
                ticks=ticks,
                phases=[mission_type],
                parameters=parameters or {},
            ),
            agents=agents,
            seed=seed,
        )
        
        return MissionRunner(config, rng=random.Random(seed))
    
    @staticmethod
    def create_multi_phase(
        phases: List[MissionType],
        agents: List[AgentConfig],
        ticks: int = DEFAULT_MATCH_TICKS,
        seed: Optional[int] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> MissionRunner:
        """Create a mission runner with multiple phases."""
        config = MatchConfig(
            mission=MissionConfig(
                mission_type=phases[0] if phases else MissionType.RESOURCE_RACE,
                ticks=ticks,
                phases=phases,
                parameters=parameters or {},
            ),
            agents=agents,
            seed=seed,
        )
        
        return MissionRunner(config, rng=random.Random(seed))


# Backward compatibility with existing simulation.py
class ArenaSimulationAdapter:
    """Adapter to provide simulation.py-compatible interface."""
    
    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        self.rng = random.Random(seed)
    
    async def run_resource_race_round(
        self,
        agents_data: List[Dict[str, Any]],
        ticks: int = 30,
    ) -> Dict[str, Any]:
        """Run a resource race round (compatible with simulation.py interface)."""
        # Convert agents data to AgentConfig
        agents = []
        for i, data in enumerate(agents_data):
            agents.append(AgentConfig(
                agent_id=data.get("agent_id", f"bot-{i+1}"),
                name=data.get("name", f"Bot {i+1}"),
                strategy=data.get("strategy", "balanced"),
                ranks=data.get("ranks", {}),
            ))
        
        # Create and run mission
        runner = MissionRunnerFactory.create(
            mission_type=MissionType.RESOURCE_RACE,
            agents=agents,
            ticks=ticks,
            seed=self.seed,
        )
        
        result = await runner.run()
        return result.to_dict()
