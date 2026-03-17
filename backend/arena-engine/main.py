"""CLAWSEUM Arena Engine - Main FastAPI Service.

Production-ready FastAPI service with:
- Health check /health
- POST /arena/run — Execute mission simulation
- GET /arena/status/{match_id} — Get match status
- WebSocket /ws/arena/{match_id} — Live match updates
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Arena engine imports
from config import (
    MissionType,
    MatchStatus,
    EventType,
    AgentConfig,
    MatchConfig,
    MissionConfig,
    MatchResult,
    DEFAULT_DATABASE_URL,
    DEFAULT_MATCH_TICKS,
    MIN_AGENTS,
    MAX_AGENTS,
    generate_match_id,
)
from mission_runner import MissionRunner, MissionRunnerFactory
from agent_runtime import AgentRuntime
from scoring import ScoringEngine
from scheduler import MatchScheduler, QuickMatchBuilder, ScheduleFrequency

# Try to import database dependencies
try:
    import psycopg
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False
    psycopg = None

try:
    import redis.asyncio as redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    redis = None

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# =============================================================================
# Global State
# =============================================================================

class ArenaState:
    """Global arena state."""
    def __init__(self):
        self.matches: Dict[str, MatchResult] = {}
        self.active_runners: Dict[str, MissionRunner] = {}
        self.scheduler: Optional[MatchScheduler] = None
        self.agent_runtime: Optional[AgentRuntime] = None
        self.scoring_engine: Optional[ScoringEngine] = None
        self.redis: Optional[Any] = None
        self.database_url: str = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.active_websockets: Dict[str, Set[WebSocket]] = {}

state = ArenaState()


# =============================================================================
# Pydantic Models
# =============================================================================

class AgentConfigRequest(BaseModel):
    """Request model for agent configuration."""
    agent_id: Optional[str] = None
    name: str
    strategy: str = "balanced"
    ranks: Optional[Dict[str, float]] = None
    faction: Optional[str] = None
    is_bot: bool = True


class MissionConfigRequest(BaseModel):
    """Request model for mission configuration."""
    mission_type: str = "resource_race"
    ticks: int = DEFAULT_MATCH_TICKS
    phases: Optional[List[str]] = None
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict)


class RunMatchRequest(BaseModel):
    """Request model for running a match."""
    agents: List[AgentConfigRequest]
    mission: Optional[MissionConfigRequest] = None
    seed: Optional[int] = None
    priority: int = 0


class ScheduleMatchRequest(BaseModel):
    """Request model for scheduling a match."""
    agents: List[AgentConfigRequest]
    mission: Optional[MissionConfigRequest] = None
    seed: Optional[int] = None
    scheduled_at: Optional[str] = None
    frequency: str = "once"
    cron_expression: Optional[str] = None
    max_runs: Optional[int] = None
    priority: int = 0


class MatchResponse(BaseModel):
    """Response model for a match."""
    match_id: str
    status: str
    mission_type: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    standings: Optional[List[Dict[str, Any]]] = None
    events_count: int = 0


class EventPayload(BaseModel):
    """Model for arena events."""
    event_id: str
    tick: int
    type: str
    payload: Dict[str, Any]
    timestamp: str


# =============================================================================
# Lifespan Management
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    logger.info("Starting Arena Engine service...")
    
    state.agent_runtime = AgentRuntime()
    state.scoring_engine = ScoringEngine()
    
    # Initialize scheduler
    async def match_executor(config: MatchConfig):
        """Executor function for the scheduler."""
        runner = MissionRunner(
            match_config=config,
            agent_runtime=state.agent_runtime,
            scoring_engine=state.scoring_engine,
        )
        
        # Add WebSocket broadcasting if there are listeners
        if config.match_id in state.active_websockets:
            runner.add_event_callback(broadcast_event)
        
        result = await runner.run()
        state.matches[config.match_id] = result
        return result
    
    state.scheduler = MatchScheduler(executor=match_executor, max_concurrent=3)
    await state.scheduler.start()
    
    # Initialize Redis if available
    if HAS_REDIS:
        try:
            state.redis = redis.from_url(state.redis_url, decode_responses=True)
            await state.redis.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            state.redis = None
    
    logger.info("Arena Engine service started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Arena Engine service...")
    
    if state.scheduler:
        await state.scheduler.stop()
    
    if state.redis:
        await state.redis.aclose()
    
    logger.info("Arena Engine service stopped")


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="CLAWSEUM Arena Engine",
    description="Production arena engine for CLAWSEUM - mission simulation, scoring, and scheduling",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Helper Functions
# =============================================================================

def _convert_agent_config(req: AgentConfigRequest) -> AgentConfig:
    """Convert request agent config to internal model."""
    return AgentConfig(
        agent_id=req.agent_id or f"agent_{generate_match_id()[:8]}",
        name=req.name,
        strategy=req.strategy,
        ranks=req.ranks or {
            "power": 500.0,
            "honor": 500.0,
            "chaos": 500.0,
            "influence": 500.0,
        },
        faction=req.faction,
        is_bot=req.is_bot,
    )


def _convert_mission_config(req: Optional[MissionConfigRequest]) -> MissionConfig:
    """Convert request mission config to internal model."""
    if req is None:
        return MissionConfig(mission_type=MissionType.RESOURCE_RACE)
    
    phases = None
    if req.phases:
        phases = [MissionType(p) for p in req.phases]
    
    return MissionConfig(
        mission_type=MissionType(req.mission_type),
        ticks=req.ticks,
        phases=phases,
        parameters=req.parameters or {},
    )


async def broadcast_event(match_id: str, event: Dict[str, Any]) -> None:
    """Broadcast an event to all WebSocket clients for a match."""
    if match_id not in state.active_websockets:
        return
    
    disconnected = []
    for ws in state.active_websockets[match_id]:
        try:
            await ws.send_json({
                "op": "event",
                "match_id": match_id,
                "event": event,
            })
        except Exception:
            disconnected.append(ws)
    
    # Clean up disconnected clients
    for ws in disconnected:
        state.active_websockets[match_id].discard(ws)


async def persist_to_database(result: MatchResult) -> None:
    """Persist match results to database."""
    if not HAS_PSYCOPG:
        logger.debug("psycopg not available, skipping database persistence")
        return
    
    try:
        now = datetime.now(timezone.utc)
        
        with psycopg.connect(state.database_url) as conn:
            with conn.cursor() as cur:
                # Insert match
                cur.execute(
                    """
                    INSERT INTO matches (id, type, status, started_at, ended_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        ended_at = EXCLUDED.ended_at
                    """,
                    (
                        result.match_id,
                        result.mission_type.value,
                        result.status.value,
                        result.started_at,
                        result.ended_at,
                    ),
                )
                
                # Insert/update agents
                for agent in result.agents:
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
                            agent.get("public_key"),
                            agent.get("faction", "simulation"),
                        ),
                    )
                
                # Insert participants
                for standing in result.standings:
                    upd = next(
                        (u for u in result.rank_updates if u["agent_id"] == standing["agent_id"]),
                        {}
                    )
                    deltas = upd.get("deltas", {}) if upd else {}
                    
                    cur.execute(
                        """
                        INSERT INTO match_participants (match_id, agent_id, score, rank_delta)
                        VALUES (%s, %s, %s, %s::jsonb)
                        ON CONFLICT (match_id, agent_id) DO UPDATE SET
                            score = EXCLUDED.score,
                            rank_delta = EXCLUDED.rank_delta
                        """,
                        (
                            result.match_id,
                            standing["agent_id"],
                            standing["mission_score"],
                            json.dumps(deltas),
                        ),
                    )
                    
                    # Update leaderboard snapshots
                    after = upd.get("after") if upd else agent.get("ranks")
                    if after:
                        cur.execute(
                            """
                            INSERT INTO leaderboard_snapshots
                                (agent_id, power_rank, honor_rank, chaos_rank, influence_rank, timestamp)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            """,
                            (
                                standing["agent_id"],
                                float(after.get("power", 500.0)),
                                float(after.get("honor", 500.0)),
                                float(after.get("chaos", 500.0)),
                                float(after.get("influence", 500.0)),
                                now,
                            ),
                        )
                
                # Insert events
                for event in result.events:
                    event_id = f"{result.match_id}_{event['event_id']}"
                    cur.execute(
                        """
                        INSERT INTO events (id, type, payload, created_at)
                        VALUES (%s, %s, %s::jsonb, %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (
                            event_id,
                            event["type"],
                            json.dumps({
                                "tick": event.get("tick"),
                                "payload": event.get("payload", {}),
                            }),
                            now,
                        ),
                    )
            
            conn.commit()
            logger.info(f"Persisted match {result.match_id} to database")
    
    except Exception as e:
        logger.error(f"Database persistence error: {e}")
        # Don't raise - database errors shouldn't fail the match


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    scheduler_status = await state.scheduler.get_status() if state.scheduler else {}
    
    return {
        "status": "ok",
        "service": "arena-engine",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scheduler": scheduler_status,
        "database_available": HAS_PSYCOPG,
        "redis_available": HAS_REDIS and state.redis is not None,
    }


@app.post("/arena/run", response_model=MatchResponse)
async def run_match(request: RunMatchRequest) -> MatchResponse:
    """Execute a mission simulation immediately."""
    # Validate agent count
    if not MIN_AGENTS <= len(request.agents) <= MAX_AGENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent count must be between {MIN_AGENTS} and {MAX_AGENTS}",
        )
    
    # Build match config
    match_id = generate_match_id()
    agents = [_convert_agent_config(a) for a in request.agents]
    mission = _convert_mission_config(request.mission)
    
    config = MatchConfig(
        match_id=match_id,
        mission=mission,
        agents=agents,
        seed=request.seed,
    )
    
    logger.info(f"Running match {match_id} with {len(agents)} agents")
    
    # Create and run mission
    runner = MissionRunner(
        match_config=config,
        agent_runtime=state.agent_runtime,
        scoring_engine=state.scoring_engine,
    )
    
    # Store as active runner
    state.active_runners[match_id] = runner
    
    try:
        result = await runner.run()
        state.matches[match_id] = result
        
        # Persist to database
        await persist_to_database(result)
        
        return MatchResponse(
            match_id=match_id,
            status=result.status.value,
            mission_type=result.mission_type.value,
            started_at=result.started_at.isoformat(),
            ended_at=result.ended_at.isoformat() if result.ended_at else None,
            standings=result.standings,
            events_count=len(result.events),
        )
    
    finally:
        # Clean up active runner
        state.active_runners.pop(match_id, None)


@app.get("/arena/status/{match_id}")
async def get_match_status(match_id: str) -> Dict[str, Any]:
    """Get the status of a match."""
    # Check completed matches
    if match_id in state.matches:
        result = state.matches[match_id]
        return {
            "match_id": match_id,
            "status": result.status.value,
            "mission_type": result.mission_type.value,
            "started_at": result.started_at.isoformat(),
            "ended_at": result.ended_at.isoformat() if result.ended_at else None,
            "standings": result.standings,
            "rank_updates": result.rank_updates,
            "events_count": len(result.events),
            "agents": result.agents,
        }
    
    # Check active runners
    if match_id in state.active_runners:
        runner = state.active_runners[match_id]
        return {
            "match_id": match_id,
            "status": runner.status.value,
            "mission_type": runner.config.mission.mission_type.value,
            "current_tick": runner._current_tick,
            "total_ticks": runner.config.mission.ticks,
            "agents": [{"agent_id": a.agent_id, "name": a.name} for a in runner.agents.values()],
        }
    
    # Check database
    if HAS_PSYCOPG:
        try:
            with psycopg.connect(state.database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, type, status, started_at, ended_at FROM matches WHERE id = %s",
                        (match_id,)
                    )
                    row = cur.fetchone()
                    if row:
                        return {
                            "match_id": row[0],
                            "mission_type": row[1],
                            "status": row[2],
                            "started_at": row[3].isoformat() if row[3] else None,
                            "ended_at": row[4].isoformat() if row[4] else None,
                            "note": "Detailed results available in completed matches cache",
                        }
        except Exception as e:
            logger.error(f"Database query error: {e}")
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Match {match_id} not found",
    )


@app.get("/arena/matches")
async def list_matches(
    limit: int = 10,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List recent matches."""
    matches = []
    
    for match_id, result in sorted(
        state.matches.items(),
        key=lambda x: x[1].ended_at or x[1].started_at,
        reverse=True
    )[:limit]:
        if status is None or result.status.value == status:
            matches.append({
                "match_id": match_id,
                "status": result.status.value,
                "mission_type": result.mission_type.value,
                "started_at": result.started_at.isoformat(),
                "ended_at": result.ended_at.isoformat() if result.ended_at else None,
                "agents_count": len(result.agents),
            })
    
    return matches


@app.post("/arena/schedule")
async def schedule_match(request: ScheduleMatchRequest) -> Dict[str, str]:
    """Schedule a match for future execution."""
    if not state.scheduler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler not available",
        )
    
    # Build match config
    agents = [_convert_agent_config(a) for a in request.agents]
    mission = _convert_mission_config(request.mission)
    
    scheduled_at = None
    if request.scheduled_at:
        scheduled_at = datetime.fromisoformat(request.scheduled_at)
    
    config = MatchConfig(
        match_id=generate_match_id(),
        mission=mission,
        agents=agents,
        seed=request.seed,
        scheduled_at=scheduled_at,
        priority=request.priority,
    )
    
    frequency = ScheduleFrequency(request.frequency)
    
    schedule_id = await state.scheduler.schedule(
        match_config=config,
        priority=request.priority,
        frequency=frequency,
        cron_expression=request.cron_expression,
        max_runs=request.max_runs,
    )
    
    return {
        "schedule_id": schedule_id,
        "match_id": config.match_id,
        "scheduled_at": config.scheduled_at.isoformat() if config.scheduled_at else None,
    }


@app.get("/arena/schedule/{schedule_id}")
async def get_schedule(schedule_id: str) -> Dict[str, Any]:
    """Get schedule details."""
    if not state.scheduler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler not available",
        )
    
    schedule = await state.scheduler.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found",
        )
    
    return {
        "schedule_id": schedule.schedule_id,
        "enabled": schedule.enabled,
        "frequency": schedule.frequency.value,
        "scheduled_at": schedule.scheduled_at.isoformat(),
        "next_run": schedule.next_run.isoformat() if schedule.next_run else None,
        "run_count": schedule.run_count,
        "max_runs": schedule.max_runs,
        "priority": schedule.priority,
        "match_config": {
            "match_id": schedule.match_config.match_id,
            "mission_type": schedule.match_config.mission.mission_type.value,
            "ticks": schedule.match_config.mission.ticks,
        },
    }


@app.get("/arena/schedules")
async def list_schedules() -> List[Dict[str, Any]]:
    """List all schedules."""
    if not state.scheduler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler not available",
        )
    
    schedules = await state.scheduler.list_schedules(enabled_only=False)
    return [
        {
            "schedule_id": s.schedule_id,
            "enabled": s.enabled,
            "frequency": s.frequency.value,
            "next_run": s.next_run.isoformat() if s.next_run else None,
            "run_count": s.run_count,
        }
        for s in schedules
    ]


@app.delete("/arena/schedule/{schedule_id}")
async def unschedule_match(schedule_id: str) -> Dict[str, bool]:
    """Cancel a scheduled match."""
    if not state.scheduler:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler not available",
        )
    
    success = await state.scheduler.unschedule(schedule_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found",
        )
    
    return {"cancelled": True}


# =============================================================================
# WebSocket Endpoints
# =============================================================================

@app.websocket("/ws/arena/{match_id}")
async def websocket_arena(websocket: WebSocket, match_id: str) -> None:
    """WebSocket endpoint for live match updates."""
    await websocket.accept()
    
    # Register client
    if match_id not in state.active_websockets:
        state.active_websockets[match_id] = set()
    state.active_websockets[match_id].add(websocket)
    
    try:
        # Send initial state
        if match_id in state.matches:
            result = state.matches[match_id]
            await websocket.send_json({
                "op": "snapshot",
                "match_id": match_id,
                "status": result.status.value,
                "mission_type": result.mission_type.value,
                "standings": result.standings,
                "events": result.events[-100:],  # Last 100 events
            })
        elif match_id in state.active_runners:
            runner = state.active_runners[match_id]
            await websocket.send_json({
                "op": "snapshot",
                "match_id": match_id,
                "status": runner.status.value,
                "current_tick": runner._current_tick,
                "agents": [{"agent_id": a.agent_id, "name": a.name} for a in runner.agents.values()],
            })
        else:
            await websocket.send_json({
                "op": "error",
                "message": f"Match {match_id} not found",
            })
            return
        
        # Keep connection alive and handle client messages
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=30.0
                )
                
                op = message.get("op", "").lower()
                
                if op == "ping":
                    await websocket.send_json({
                        "op": "pong",
                        "ts": datetime.now(timezone.utc).isoformat(),
                    })
                
                elif op == "subscribe":
                    # Client can subscribe to specific event types
                    event_types = message.get("types", [])
                    await websocket.send_json({
                        "op": "subscribed",
                        "types": event_types,
                    })
                
                elif op == "close":
                    break
            
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "op": "ping",
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
    
    except WebSocketDisconnect:
        logger.debug(f"WebSocket disconnected for match {match_id}")
    
    except Exception as e:
        logger.error(f"WebSocket error for match {match_id}: {e}")
    
    finally:
        # Unregister client
        if match_id in state.active_websockets:
            state.active_websockets[match_id].discard(websocket)
            if not state.active_websockets[match_id]:
                del state.active_websockets[match_id]


# =============================================================================
# Quick Match Endpoints
# =============================================================================

@app.post("/arena/quick/{mission_type}")
async def quick_match(
    mission_type: str,
    agent_count: int = 4,
    ticks: int = DEFAULT_MATCH_TICKS,
    seed: Optional[int] = None,
) -> MatchResponse:
    """Start a quick match with random bots."""
    try:
        mtype = MissionType(mission_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mission type: {mission_type}",
        )
    
    config = QuickMatchBuilder.resource_race(
        agent_count=agent_count,
        ticks=ticks,
        seed=seed,
    )
    
    # Override mission type if different
    if mtype != MissionType.RESOURCE_RACE:
        config.mission.mission_type = mtype
        config.mission.phases = [mtype]
    
    logger.info(f"Starting quick {mission_type} match with {agent_count} agents")
    
    runner = MissionRunner(
        match_config=config,
        agent_runtime=state.agent_runtime,
        scoring_engine=state.scoring_engine,
    )
    
    state.active_runners[config.match_id] = runner
    
    try:
        result = await runner.run()
        state.matches[config.match_id] = result
        await persist_to_database(result)
        
        return MatchResponse(
            match_id=config.match_id,
            status=result.status.value,
            mission_type=result.mission_type.value,
            started_at=result.started_at.isoformat(),
            ended_at=result.ended_at.isoformat() if result.ended_at else None,
            standings=result.standings,
            events_count=len(result.events),
        )
    
    finally:
        state.active_runners.pop(config.match_id, None)


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(app, host=host, port=port)
