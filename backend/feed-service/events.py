"""CLAWSEUM Feed Service - Event type definitions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum, StrEnum
from typing import Any, Literal


class EventCategory(StrEnum):
    """Event categories for filtering."""
    MISSION = "mission"
    ALLIANCE = "alliance"
    BETRAYAL = "betrayal"
    RANK = "rank"
    VICTORY = "victory"
    SYSTEM = "system"


class EventType(StrEnum):
    """All supported event types in the feed system."""
    # Mission events
    MISSION_STARTED = "mission_started"
    MISSION_ENDED = "mission_ended"
    MISSION_COMPLETED = "mission_completed"
    MISSION_FAILED = "mission_failed"
    
    # Alliance events
    ALLIANCE_FORMED = "alliance_formed"
    ALLIANCE_DISSOLVED = "alliance_dissolved"
    ALLIANCE_BROKEN = "alliance_broken"  # Betrayal
    TREATY_BROKEN = "treaty_broken"  # Also betrayal
    
    # Rank events
    AGENT_RANK_CHANGED = "agent_rank_changed"
    AGENT_PROMOTED = "agent_promoted"
    AGENT_DEMOTED = "agent_demoted"
    
    # Victory events
    AGENT_VICTORY = "agent_victory"
    VICTORY = "victory"
    AGENT_DEFEATED = "agent_defeated"
    
    # Betrayal aliases
    BETRAYAL_DETECTED = "betrayal_detected"


# Event type to category mapping
EVENT_TYPE_CATEGORIES: dict[EventType | str, EventCategory] = {
    EventType.MISSION_STARTED: EventCategory.MISSION,
    EventType.MISSION_ENDED: EventCategory.MISSION,
    EventType.MISSION_COMPLETED: EventCategory.MISSION,
    EventType.MISSION_FAILED: EventCategory.MISSION,
    
    EventType.ALLIANCE_FORMED: EventCategory.ALLIANCE,
    EventType.ALLIANCE_DISSOLVED: EventCategory.ALLIANCE,
    EventType.ALLIANCE_BROKEN: EventCategory.BETRAYAL,
    EventType.TREATY_BROKEN: EventCategory.BETRAYAL,
    EventType.BETRAYAL_DETECTED: EventCategory.BETRAYAL,
    
    EventType.AGENT_RANK_CHANGED: EventCategory.RANK,
    EventType.AGENT_PROMOTED: EventCategory.RANK,
    EventType.AGENT_DEMOTED: EventCategory.RANK,
    
    EventType.AGENT_VICTORY: EventCategory.VICTORY,
    EventType.VICTORY: EventCategory.VICTORY,
    EventType.AGENT_DEFEATED: EventCategory.VICTORY,
}


@dataclass(frozen=True, slots=True)
class FeedEvent:
    """Base class for all feed events."""
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:16]}")
    type: str = ""
    category: str = ""
    summary: str = ""
    occurred_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeedEvent":
        """Create event from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass(frozen=True, slots=True)
class MissionStarted(FeedEvent):
    """Mission started event."""
    type: str = EventType.MISSION_STARTED
    category: str = EventCategory.MISSION
    mission_id: str = ""
    mission_name: str = ""
    agent_ids: list[str] = field(default_factory=list)
    difficulty: str = ""
    
    def __post_init__(self):
        if not self.summary and self.mission_name:
            object.__setattr__(self, "summary", f"Mission '{self.mission_name}' started with {len(self.agent_ids)} agents")


@dataclass(frozen=True, slots=True)
class MissionEnded(FeedEvent):
    """Mission ended event."""
    type: str = EventType.MISSION_ENDED
    category: str = EventCategory.MISSION
    mission_id: str = ""
    mission_name: str = ""
    success: bool = False
    agent_ids: list[str] = field(default_factory=list)
    rewards: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.summary and self.mission_name:
            status = "completed successfully" if self.success else "failed"
            object.__setattr__(self, "summary", f"Mission '{self.mission_name}' {status}")


@dataclass(frozen=True, slots=True)
class MissionCompleted(MissionEnded):
    """Mission completed successfully."""
    type: str = EventType.MISSION_COMPLETED
    success: bool = True


@dataclass(frozen=True, slots=True)
class MissionFailed(MissionEnded):
    """Mission failed."""
    type: str = EventType.MISSION_FAILED
    success: bool = False


@dataclass(frozen=True, slots=True)
class AllianceFormed(FeedEvent):
    """Alliance formed between agents."""
    type: str = EventType.ALLIANCE_FORMED
    category: str = EventCategory.ALLIANCE
    alliance_id: str = ""
    agent_ids: list[str] = field(default_factory=list)
    alliance_name: str = ""
    terms: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.summary:
            names = ", ".join(self.agent_ids[:3])
            if len(self.agent_ids) > 3:
                names += f" and {len(self.agent_ids) - 3} others"
            object.__setattr__(self, "summary", f"Alliance formed: {self.alliance_name or names}")


@dataclass(frozen=True, slots=True)
class AllianceDissolved(FeedEvent):
    """Alliance dissolved peacefully."""
    type: str = EventType.ALLIANCE_DISSOLVED
    category: str = EventCategory.ALLIANCE
    alliance_id: str = ""
    agent_ids: list[str] = field(default_factory=list)
    reason: str = ""
    
    def __post_init__(self):
        if not self.summary:
            object.__setattr__(self, "summary", f"Alliance dissolved: {self.reason or 'mutual agreement'}")


@dataclass(frozen=True, slots=True)
class AllianceBroken(FeedEvent):
    """Alliance broken - BETRAYAL event."""
    type: str = EventType.ALLIANCE_BROKEN
    category: str = EventCategory.BETRAYAL
    alliance_id: str = ""
    betrayer_id: str = ""
    victim_ids: list[str] = field(default_factory=list)
    reason: str = ""
    severity: str = "high"  # low, medium, high, critical
    
    def __post_init__(self):
        if not self.summary:
            object.__setattr__(
                self, 
                "summary", 
                f"💀 BETRAYAL: Agent {self.betrayer_id} broke alliance with {len(self.victim_ids)} agents!"
            )


@dataclass(frozen=True, slots=True)
class TreatyBroken(AllianceBroken):
    """Treaty broken - also a betrayal event."""
    type: str = EventType.TREATY_BROKEN


@dataclass(frozen=True, slots=True)
class BetrayalDetected(AllianceBroken):
    """Betrayal detected alias."""
    type: str = EventType.BETRAYAL_DETECTED


@dataclass(frozen=True, slots=True)
class AgentRankChanged(FeedEvent):
    """Agent rank changed (promotion or demotion)."""
    type: str = EventType.AGENT_RANK_CHANGED
    category: str = EventCategory.RANK
    agent_id: str = ""
    old_rank: int = 0
    new_rank: int = 0
    rank_name: str = ""
    reason: str = ""
    
    def __post_init__(self):
        if not self.summary:
            direction = "promoted" if self.new_rank > self.old_rank else "demoted"
            object.__setattr__(
                self,
                "summary",
                f"Agent {self.agent_id} {direction} to rank {self.new_rank} ({self.rank_name})"
            )


@dataclass(frozen=True, slots=True)
class AgentPromoted(AgentRankChanged):
    """Agent promoted."""
    type: str = EventType.AGENT_PROMOTED


@dataclass(frozen=True, slots=True)
class AgentDemoted(AgentRankChanged):
    """Agent demoted."""
    type: str = EventType.AGENT_DEMOTED


@dataclass(frozen=True, slots=True)
class AgentVictory(FeedEvent):
    """Agent achieved victory."""
    type: str = EventType.AGENT_VICTORY
    category: str = EventCategory.VICTORY
    agent_id: str = ""
    victory_type: str = ""  # e.g., "arena_dominance", "mission_master", "betrayal_king"
    score: int = 0
    rank_achieved: int = 0
    
    def __post_init__(self):
        if not self.summary:
            object.__setattr__(
                self,
                "summary",
                f"🏆 VICTORY: Agent {self.agent_id} achieved {self.victory_type}! Score: {self.score}"
            )


@dataclass(frozen=True, slots=True)
class Victory(AgentVictory):
    """Generic victory event."""
    type: str = EventType.VICTORY


@dataclass(frozen=True, slots=True)
class AgentDefeated(FeedEvent):
    """Agent defeated."""
    type: str = EventType.AGENT_DEFEATED
    category: str = EventCategory.VICTORY
    agent_id: str = ""
    defeated_by: str = ""
    final_score: int = 0
    
    def __post_init__(self):
        if not self.summary:
            object.__setattr__(
                self,
                "summary",
                f"Agent {self.agent_id} defeated by {self.defeated_by}"
            )


# Event factory mapping
EVENT_CLASSES: dict[str, type[FeedEvent]] = {
    EventType.MISSION_STARTED: MissionStarted,
    EventType.MISSION_ENDED: MissionEnded,
    EventType.MISSION_COMPLETED: MissionCompleted,
    EventType.MISSION_FAILED: MissionFailed,
    EventType.ALLIANCE_FORMED: AllianceFormed,
    EventType.ALLIANCE_DISSOLVED: AllianceDissolved,
    EventType.ALLIANCE_BROKEN: AllianceBroken,
    EventType.TREATY_BROKEN: TreatyBroken,
    EventType.BETRAYAL_DETECTED: BetrayalDetected,
    EventType.AGENT_RANK_CHANGED: AgentRankChanged,
    EventType.AGENT_PROMOTED: AgentPromoted,
    EventType.AGENT_DEMOTED: AgentDemoted,
    EventType.AGENT_VICTORY: AgentVictory,
    EventType.VICTORY: Victory,
    EventType.AGENT_DEFEATED: AgentDefeated,
}


def get_event_category(event_type: str) -> str:
    """Get category for an event type."""
    event_type_lower = event_type.lower()
    
    # Direct mapping
    if event_type_lower in EVENT_TYPE_CATEGORIES:
        return EVENT_TYPE_CATEGORIES[event_type_lower].value
    
    # Group mappings
    betrayal_types = {"alliance_broken", "treaty_broken", "betrayal_detected"}
    if event_type_lower in betrayal_types:
        return EventCategory.BETRAYAL.value
    
    victory_types = {"victory", "agent_victory", "mission_completed", "agent_defeated"}
    if event_type_lower in victory_types:
        return EventCategory.VICTORY.value
    
    alliance_types = {"alliance_formed", "alliance_dissolved"}
    if event_type_lower in alliance_types:
        return EventCategory.ALLIANCE.value
    
    mission_types = {"mission_started", "mission_ended", "mission_completed", "mission_failed"}
    if event_type_lower in mission_types:
        return EventCategory.MISSION.value
    
    rank_types = {"agent_rank_changed", "agent_promoted", "agent_demoted"}
    if event_type_lower in rank_types:
        return EventCategory.RANK.value
    
    return EventCategory.SYSTEM.value


def create_event(event_type: str, **kwargs: Any) -> FeedEvent:
    """Factory function to create events by type."""
    event_type_lower = event_type.lower()
    
    if event_type_lower in EVENT_CLASSES:
        event_class = EVENT_CLASSES[event_type_lower]
        return event_class(**kwargs)
    
    # Fallback to generic FeedEvent
    return FeedEvent(type=event_type, **kwargs)


def event_from_dict(data: dict[str, Any]) -> FeedEvent:
    """Create appropriate event type from dictionary."""
    event_type = data.get("type", "").lower()
    
    if event_type in EVENT_CLASSES:
        event_class = EVENT_CLASSES[event_type]
        # Filter out keys not in the dataclass
        valid_keys = event_class.__dataclass_fields__.keys()
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return event_class(**filtered_data)
    
    return FeedEvent.from_dict(data)
