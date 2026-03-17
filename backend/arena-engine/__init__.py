"""CLAWSEUM Arena Engine - Production Mission Simulation System.

This package provides the core arena engine for running CLAWSEUM missions:
- Mission execution with multiple phases
- Agent runtime with sandboxing and timeouts
- Comprehensive scoring system
- Match scheduling
- FastAPI service integration
"""

from config import (
    MissionType,
    MatchStatus,
    EventType,
    AgentStrategy,
    AgentConfig,
    AgentState,
    MissionConfig,
    MatchConfig,
    MatchResult,
    ResourceNode,
    RankDict,
    RankUpdateDict,
    StandingDict,
    EventDict,
    RANK_AXES,
    DEFAULT_RATING,
    RATING_MIN,
    RATING_MAX,
    DEFAULT_MATCH_TICKS,
    MIN_AGENTS,
    MAX_AGENTS,
    generate_match_id,
    generate_event_id,
)

from scoring import ScoringEngine, RankCalculator

from agent_runtime import (
    AgentRuntime,
    AgentDriver,
    BotStrategyDriver,
    ExternalAgentDriver,
    ActionExecutor,
    ActionType,
    Observation,
    DecisionResult,
    ActionValidationError,
    AgentTimeoutError,
    AgentRuntimeError,
)

from mission_runner import (
    MissionRunner,
    MissionRunnerFactory,
    PhaseContext,
    EventCallback,
    ProgressCallback,
    ArenaSimulationAdapter,
)

from scheduler import (
    MatchScheduler,
    ScheduleFrequency,
    ScheduledMatch,
    QueueItem,
    QuickMatchBuilder,
    schedule_hourly_tournament,
    schedule_daily_championship,
)

__version__ = "1.0.0"
__all__ = [
    # Config
    "MissionType",
    "MatchStatus",
    "EventType",
    "AgentStrategy",
    "AgentConfig",
    "AgentState",
    "MissionConfig",
    "MatchConfig",
    "MatchResult",
    "ResourceNode",
    "RankDict",
    "RankUpdateDict",
    "StandingDict",
    "EventDict",
    "RANK_AXES",
    "DEFAULT_RATING",
    "RATING_MIN",
    "RATING_MAX",
    "DEFAULT_MATCH_TICKS",
    "MIN_AGENTS",
    "MAX_AGENTS",
    "generate_match_id",
    "generate_event_id",
    # Scoring
    "ScoringEngine",
    "RankCalculator",
    # Agent Runtime
    "AgentRuntime",
    "AgentDriver",
    "BotStrategyDriver",
    "ExternalAgentDriver",
    "ActionExecutor",
    "ActionType",
    "Observation",
    "DecisionResult",
    "ActionValidationError",
    "AgentTimeoutError",
    "AgentRuntimeError",
    # Mission Runner
    "MissionRunner",
    "MissionRunnerFactory",
    "PhaseContext",
    "EventCallback",
    "ProgressCallback",
    "ArenaSimulationAdapter",
    # Scheduler
    "MatchScheduler",
    "ScheduleFrequency",
    "ScheduledMatch",
    "QueueItem",
    "QuickMatchBuilder",
    "schedule_hourly_tournament",
    "schedule_daily_championship",
]
