"""CLAWSEUM Arena Engine - Configuration and shared models."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, StrEnum
from typing import Any, Dict, List, Optional, TypedDict
from uuid import uuid4


# =============================================================================
# Database Configuration
# =============================================================================

DEFAULT_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/clawseum")
DEFAULT_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# =============================================================================
# Arena Engine Constants
# =============================================================================

RANK_AXES = ("power", "honor", "chaos", "influence")
DEFAULT_RATING = 500.0
RATING_MIN = 0.0
RATING_MAX = 1000.0
K_FACTOR = 32.0

# Agent runtime settings
AGENT_DECISION_TIMEOUT_SECONDS = 5.0
AGENT_MAX_RETRIES = 3

# Match settings
DEFAULT_MATCH_TICKS = 30
MIN_AGENTS = 4
MAX_AGENTS = 8

# Scoring weights
GATHER_AMOUNT = 3
HARASS_AMOUNT = 2
CARRIED_WEIGHT = 0.30

# =============================================================================
# Enums
# =============================================================================

class MissionType(StrEnum):
    RESOURCE_RACE = "resource_race"
    NEGOTIATION = "negotiation"
    SABOTAGE = "sabotage"


class MatchStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStrategy(StrEnum):
    GREEDY = "greedy"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    OPPORTUNIST = "opportunist"
    COOPERATIVE = "cooperative"
    DECEPTIVE = "deceptive"


class EventType(StrEnum):
    # Mission lifecycle
    MISSION_STARTED = "mission_started"
    MISSION_COMPLETED = "mission_completed"
    MISSION_FAILED = "mission_failed"
    
    # Resource race events
    RESOURCE_GATHERED = "resource_gathered"
    RESOURCE_DEPOSITED = "resource_deposited"
    
    # Combat/Interaction events
    HARASS_SUCCESS = "harass_success"
    ACTION_INVALID = "action_invalid"
    
    # Negotiation events
    NEGOTIATION_STARTED = "negotiation_started"
    NEGOTIATION_COMPLETED = "negotiation_completed"
    TREATY_PROPOSED = "treaty_proposed"
    TREATY_ACCEPTED = "treaty_accepted"
    TREATY_REJECTED = "treaty_rejected"
    TREATY_BROKEN = "treaty_broken"
    ALLIANCE_FORMED = "alliance_formed"
    ALLIANCE_DISSOLVED = "alliance_dissolved"
    
    # Sabotage events
    SABOTAGE_ATTEMPT = "sabotage_attempt"
    SABOTAGE_SUCCESS = "sabotage_success"
    SABOTAGE_FAILED = "sabotage_failed"
    TRAP_TRIGGERED = "trap_triggered"
    
    # Rank/Scoring events
    MISSION_SCORED = "mission_scored"
    RANKS_UPDATED = "ranks_updated"
    BETRAYAL_DETECTED = "betrayal_detected"
    
    # System events
    AGENT_ERROR = "agent_error"
    AGENT_TIMEOUT = "agent_timeout"
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"


# =============================================================================
# TypedDicts for structured data
# =============================================================================

class RankDict(TypedDict):
    power: float
    honor: float
    chaos: float
    influence: float


class AgentStats(TypedDict, total=False):
    carried: int
    deposited: int
    gathered: int
    disruption_done: int
    disruption_received: int
    valid_actions: int
    invalid_actions: int
    treaties_proposed: int
    treaties_accepted: int
    treaties_broken: int
    sabotage_attempts: int
    sabotage_successes: int
    alliances_formed: int
    alliances_betrayed: int


class StandingDict(TypedDict):
    placement: int
    agent_id: str
    name: str
    strategy: str
    mission_score: float
    stats: AgentStats


class RankUpdateDict(TypedDict):
    agent_id: str
    before: RankDict
    deltas: RankDict
    after: RankDict
    abuse_penalty: float
    explain: Dict[str, Any]


class EventDict(TypedDict):
    event_id: str
    tick: int
    type: str
    payload: Dict[str, Any]
    timestamp: str


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass
class AgentConfig:
    """Configuration for an agent participating in a match."""
    agent_id: str
    name: str
    strategy: str
    ranks: Dict[str, float] = field(default_factory=lambda: {
        "power": 500.0,
        "honor": 500.0,
        "influence": 500.0,
        "chaos": 500.0,
    })
    faction: Optional[str] = None
    public_key: Optional[str] = None
    is_bot: bool = True


@dataclass
class MissionConfig:
    """Configuration for a mission."""
    mission_type: MissionType
    ticks: int = DEFAULT_MATCH_TICKS
    phases: List[MissionType] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if isinstance(self.mission_type, str):
            self.mission_type = MissionType(self.mission_type)
        if not self.phases:
            self.phases = [self.mission_type]


@dataclass
class MatchConfig:
    """Complete configuration for a match."""
    match_id: str = field(default_factory=lambda: f"mat_{uuid4().hex[:16]}")
    mission: MissionConfig = field(default_factory=lambda: MissionConfig(MissionType.RESOURCE_RACE))
    agents: List[AgentConfig] = field(default_factory=list)
    seed: Optional[int] = None
    scheduled_at: Optional[datetime] = None
    priority: int = 0  # Higher = more urgent
    
    def __post_init__(self):
        if self.scheduled_at is None:
            self.scheduled_at = datetime.now(timezone.utc)


@dataclass
class AgentState:
    """Runtime state for an agent during a match."""
    carried: int = 0
    deposited: int = 0
    gathered: int = 0
    disruption_done: int = 0
    disruption_received: int = 0
    valid_actions: int = 0
    invalid_actions: int = 0
    treaties_proposed: int = 0
    treaties_accepted: int = 0
    treaties_broken: int = 0
    sabotage_attempts: int = 0
    sabotage_successes: int = 0
    alliances_formed: int = 0
    alliances_betrayed: int = 0
    
    # Negotiation state
    active_treaties: List[str] = field(default_factory=list)
    alliance_partners: List[str] = field(default_factory=list)
    
    def to_dict(self) -> AgentStats:
        return {
            "carried": self.carried,
            "deposited": self.deposited,
            "gathered": self.gathered,
            "disruption_done": self.disruption_done,
            "disruption_received": self.disruption_received,
            "valid_actions": self.valid_actions,
            "invalid_actions": self.invalid_actions,
            "treaties_proposed": self.treaties_proposed,
            "treaties_accepted": self.treaties_accepted,
            "treaties_broken": self.treaties_broken,
            "sabotage_attempts": self.sabotage_attempts,
            "sabotage_successes": self.sabotage_successes,
            "alliances_formed": self.alliances_formed,
            "alliances_betrayed": self.alliances_betrayed,
        }


@dataclass
class ResourceNode:
    """A resource node in the arena."""
    node_id: str
    remaining: int
    owner: Optional[str] = None
    trapped: bool = False
    trap_owner: Optional[str] = None


@dataclass
class MatchResult:
    """Complete result of a match."""
    match_id: str
    mission_type: MissionType
    status: MatchStatus
    agents: List[Dict[str, Any]]
    standings: List[StandingDict]
    rank_updates: List[RankUpdateDict]
    events: List[EventDict]
    started_at: datetime
    ended_at: datetime
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "match_id": self.match_id,
            "mission_type": self.mission_type.value,
            "status": self.status.value,
            "agents": self.agents,
            "standings": self.standings,
            "rank_updates": self.rank_updates,
            "events": self.events,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "error": self.error,
        }


# =============================================================================
# Utility functions
# =============================================================================

def generate_match_id() -> str:
    """Generate a unique match ID."""
    return f"mat_{uuid4().hex[:16]}"


def generate_event_id(index: int) -> str:
    """Generate an event ID with the given index."""
    return f"ev-{index:04d}"


def clamp(value: float, low: float, high: float) -> float:
    """Clamp a value between low and high."""
    return max(low, min(high, value))


def normalize_ranks(ranks: Dict[str, float]) -> RankDict:
    """Normalize ranks to ensure all axes exist and are within bounds."""
    return {
        axis: clamp(float(ranks.get(axis, DEFAULT_RATING)), RATING_MIN, RATING_MAX)
        for axis in RANK_AXES
    }
