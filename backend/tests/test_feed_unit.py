"""CLAWSEUM Feed Service - Comprehensive Unit Tests.

Tests for:
- events.py — Event creation, serialization, all event types
- broadcaster.py — Redis pub/sub fanout, retry logic, rate limiting
- websocket.py — Connection manager, auth, heartbeat, reconnection
- persistence.py — Event storage, queries, stats (mock DB)
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import pytest

# Add feed-service to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
FEED_SERVICE_DIR = PROJECT_ROOT / "backend" / "feed-service"
if str(FEED_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(FEED_SERVICE_DIR))

# Import modules under test
from events import (
    EventCategory,
    EventType,
    EVENT_TYPE_CATEGORIES,
    FeedEvent,
    MissionStarted,
    MissionEnded,
    MissionCompleted,
    MissionFailed,
    AllianceFormed,
    AllianceDissolved,
    AllianceBroken,
    TreatyBroken,
    BetrayalDetected,
    AgentRankChanged,
    AgentPromoted,
    AgentDemoted,
    AgentVictory,
    Victory,
    AgentDefeated,
    EVENT_CLASSES,
    get_event_category,
    create_event,
    event_from_dict,
)
from broadcaster import (
    FeedConnection,
    FeedBroadcaster,
    RedisConnectionState,
    normalize_filters,
    EVENT_GROUPS,
)
from persistence import (
    EventStats,
    PostgreSQLPersistence,
    InMemoryPersistence,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_event_data() -> dict[str, Any]:
    """Sample event data for testing."""
    return {
        "event_id": "evt_test1234567890",
        "type": "mission_started",
        "category": "mission",
        "summary": "Test mission started",
        "occurred_at": "2024-01-15T10:30:00+00:00",
        "metadata": {"key": "value"},
    }


@pytest.fixture
def mock_websocket() -> AsyncMock:
    """Create a mock WebSocket connection."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.client = Mock(host="127.0.0.1")
    ws.headers = {}
    return ws


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.ping = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    redis.pubsub = MagicMock()
    redis.aclose = AsyncMock()
    
    # Mock pubsub
    pubsub = AsyncMock()
    pubsub.subscribe = AsyncMock()
    pubsub.close = AsyncMock()
    pubsub.get_message = AsyncMock(return_value=None)
    redis.pubsub.return_value = pubsub
    
    return redis


@pytest.fixture
def feed_connection(mock_websocket: AsyncMock) -> FeedConnection:
    """Create a sample feed connection."""
    return FeedConnection(
        id="test_conn_123",
        websocket=mock_websocket,
        filters={"missions", "victories"},
    )


@pytest.fixture
def mock_persistence() -> AsyncMock:
    """Create a mock persistence backend."""
    persistence = AsyncMock()
    persistence.store_event = AsyncMock(return_value=True)
    persistence.store_events = AsyncMock(return_value=1)
    persistence.get_recent_events = AsyncMock(return_value=[])
    persistence.get_event_stats = AsyncMock(return_value=EventStats())
    return persistence


# =============================================================================
# Test Events Module
# =============================================================================

class TestEventTypes:
    """Test event type definitions and enums."""

    def test_event_category_enum(self):
        """Test EventCategory enum values."""
        assert EventCategory.MISSION == "mission"
        assert EventCategory.ALLIANCE == "alliance"
        assert EventCategory.BETRAYAL == "betrayal"
        assert EventCategory.RANK == "rank"
        assert EventCategory.VICTORY == "victory"
        assert EventCategory.SYSTEM == "system"

    def test_event_type_enum(self):
        """Test EventType enum values."""
        assert EventType.MISSION_STARTED == "mission_started"
        assert EventType.ALLIANCE_FORMED == "alliance_formed"
        assert EventType.AGENT_RANK_CHANGED == "agent_rank_changed"
        assert EventType.AGENT_VICTORY == "agent_victory"

    def test_event_type_category_mapping(self):
        """Test that event types map to correct categories."""
        assert EVENT_TYPE_CATEGORIES[EventType.MISSION_STARTED] == EventCategory.MISSION
        assert EVENT_TYPE_CATEGORIES[EventType.ALLIANCE_BROKEN] == EventCategory.BETRAYAL
        assert EVENT_TYPE_CATEGORIES[EventType.TREATY_BROKEN] == EventCategory.BETRAYAL
        assert EVENT_TYPE_CATEGORIES[EventType.AGENT_PROMOTED] == EventCategory.RANK
        assert EVENT_TYPE_CATEGORIES[EventType.VICTORY] == EventCategory.VICTORY


class TestFeedEvent:
    """Test FeedEvent base class."""

    def test_event_creation_defaults(self):
        """Test event creation with default values."""
        event = FeedEvent(type="test_type")
        
        assert event.type == "test_type"
        assert event.event_id.startswith("evt_")
        assert len(event.event_id) == 20  # "evt_" + 16 hex chars
        assert event.category == ""
        assert event.summary == ""
        assert isinstance(event.occurred_at, str)
        assert event.metadata == {}

    def test_event_to_dict(self, sample_event_data: dict[str, Any]):
        """Test event serialization to dict."""
        event = FeedEvent(**sample_event_data)
        data = event.to_dict()
        
        assert data["event_id"] == sample_event_data["event_id"]
        assert data["type"] == sample_event_data["type"]
        assert data["metadata"] == sample_event_data["metadata"]

    def test_event_from_dict(self, sample_event_data: dict[str, Any]):
        """Test event deserialization from dict."""
        event = FeedEvent.from_dict(sample_event_data)
        
        assert event.event_id == sample_event_data["event_id"]
        assert event.type == sample_event_data["type"]

    def test_event_from_dict_extra_fields(self):
        """Test that extra fields are ignored during deserialization."""
        data = {
            "event_id": "evt_123",
            "type": "test",
            "extra_field": "should_be_ignored",
            "another_extra": 123,
        }
        event = FeedEvent.from_dict(data)
        
        assert event.event_id == "evt_123"
        assert event.type == "test"


class TestMissionEvents:
    """Test mission-related event classes."""

    def test_mission_started_creation(self):
        """Test MissionStarted event creation."""
        event = MissionStarted(
            mission_id="mission_001",
            mission_name="Test Mission",
            agent_ids=["agent_1", "agent_2"],
            difficulty="hard",
        )
        
        assert event.type == EventType.MISSION_STARTED
        assert event.category == EventCategory.MISSION
        assert event.mission_id == "mission_001"
        assert event.mission_name == "Test Mission"
        assert len(event.agent_ids) == 2
        assert "Test Mission" in event.summary
        assert "2 agents" in event.summary

    def test_mission_started_summary_auto_generation(self):
        """Test that summary is auto-generated if not provided."""
        event = MissionStarted(
            mission_name="Secret Op",
            agent_ids=["a1", "a2", "a3"],
        )
        assert "Secret Op" in event.summary
        assert "3 agents" in event.summary

    def test_mission_ended_creation(self):
        """Test MissionEnded event creation."""
        event = MissionEnded(
            mission_id="mission_001",
            mission_name="Test Mission",
            success=True,
            agent_ids=["agent_1"],
            rewards={"points": 100},
        )
        
        assert event.type == EventType.MISSION_ENDED
        assert event.success is True
        assert event.rewards == {"points": 100}
        assert "completed successfully" in event.summary

    def test_mission_failed_creation(self):
        """Test MissionFailed event creation."""
        event = MissionFailed(
            mission_id="mission_002",
            mission_name="Failed Mission",
            agent_ids=["agent_1"],
        )
        
        assert event.type == EventType.MISSION_FAILED
        assert event.success is False
        assert "failed" in event.summary

    def test_mission_completed_creation(self):
        """Test MissionCompleted event creation."""
        event = MissionCompleted(
            mission_id="mission_003",
            mission_name="Completed Mission",
        )
        
        assert event.type == EventType.MISSION_COMPLETED
        assert event.success is True


class TestAllianceEvents:
    """Test alliance-related event classes."""

    def test_alliance_formed_creation(self):
        """Test AllianceFormed event creation."""
        event = AllianceFormed(
            alliance_id="alliance_001",
            alliance_name="The Alliance",
            agent_ids=["agent_1", "agent_2", "agent_3"],
            terms={"duration": "30d"},
        )
        
        assert event.type == EventType.ALLIANCE_FORMED
        assert event.category == EventCategory.ALLIANCE
        assert event.alliance_name == "The Alliance"
        assert "The Alliance" in event.summary

    def test_alliance_formed_summary_without_name(self):
        """Test AllianceFormed summary when no name provided."""
        event = AllianceFormed(
            agent_ids=["agent_a", "agent_b", "agent_c", "agent_d", "agent_e"],
        )
        assert "agent_a, agent_b, agent_c" in event.summary
        assert "2 others" in event.summary

    def test_alliance_dissolved_creation(self):
        """Test AllianceDissolved event creation."""
        event = AllianceDissolved(
            alliance_id="alliance_001",
            reason="Strategy change",
        )
        
        assert event.type == EventType.ALLIANCE_DISSOLVED
        assert "Strategy change" in event.summary

    def test_alliance_broken_creation(self):
        """Test AllianceBroken (betrayal) event creation."""
        event = AllianceBroken(
            alliance_id="alliance_001",
            betrayer_id="agent_traitor",
            victim_ids=["agent_1", "agent_2"],
            reason="Double-cross",
            severity="critical",
        )
        
        assert event.type == EventType.ALLIANCE_BROKEN
        assert event.category == EventCategory.BETRAYAL
        assert event.betrayer_id == "agent_traitor"
        assert "BETRAYAL" in event.summary
        assert "💀" in event.summary
        assert event.severity == "critical"

    def test_treaty_broken_creation(self):
        """Test TreatyBroken event creation."""
        event = TreatyBroken(
            betrayer_id="agent_x",
            victim_ids=["agent_y"],
        )
        
        assert event.type == EventType.TREATY_BROKEN
        assert event.category == EventCategory.BETRAYAL

    def test_betrayal_detected_creation(self):
        """Test BetrayalDetected event creation."""
        event = BetrayalDetected(
            betrayer_id="bad_agent",
            victim_ids=["victim_1"],
        )
        
        assert event.type == EventType.BETRAYAL_DETECTED


class TestRankEvents:
    """Test rank-related event classes."""

    def test_agent_rank_changed_promotion(self):
        """Test AgentRankChanged for promotion."""
        event = AgentRankChanged(
            agent_id="agent_1",
            old_rank=5,
            new_rank=6,
            rank_name="Master",
            reason="Victory in arena",
        )
        
        assert event.type == EventType.AGENT_RANK_CHANGED
        assert event.category == EventCategory.RANK
        assert "promoted" in event.summary
        assert "rank 6" in event.summary
        assert "Master" in event.summary

    def test_agent_rank_changed_demotion(self):
        """Test AgentRankChanged for demotion."""
        event = AgentRankChanged(
            agent_id="agent_1",
            old_rank=10,
            new_rank=8,
            rank_name="Novice",
        )
        
        assert "demoted" in event.summary

    def test_agent_promoted_creation(self):
        """Test AgentPromoted event creation."""
        event = AgentPromoted(
            agent_id="agent_1",
            old_rank=1,
            new_rank=2,
        )
        
        assert event.type == EventType.AGENT_PROMOTED
        assert event.category == EventCategory.RANK

    def test_agent_demoted_creation(self):
        """Test AgentDemoted event creation."""
        event = AgentDemoted(
            agent_id="agent_1",
            old_rank=5,
            new_rank=4,
        )
        
        assert event.type == EventType.AGENT_DEMOTED


class TestVictoryEvents:
    """Test victory-related event classes."""

    def test_agent_victory_creation(self):
        """Test AgentVictory event creation."""
        event = AgentVictory(
            agent_id="champion_agent",
            victory_type="arena_dominance",
            score=1500,
            rank_achieved=1,
        )
        
        assert event.type == EventType.AGENT_VICTORY
        assert event.category == EventCategory.VICTORY
        assert "🏆 VICTORY" in event.summary
        assert "champion_agent" in event.summary
        assert "arena_dominance" in event.summary
        assert "1500" in event.summary

    def test_victory_creation(self):
        """Test generic Victory event creation."""
        event = Victory(
            agent_id="winner",
            victory_type="mission_master",
            score=5000,
        )
        
        assert event.type == EventType.VICTORY

    def test_agent_defeated_creation(self):
        """Test AgentDefeated event creation."""
        event = AgentDefeated(
            agent_id="loser_agent",
            defeated_by="winner_agent",
            final_score=100,
        )
        
        assert event.type == EventType.AGENT_DEFEATED
        assert event.category == EventCategory.VICTORY
        assert "loser_agent" in event.summary
        assert "winner_agent" in event.summary


class TestEventFactory:
    """Test event factory functions."""

    def test_get_event_category_direct_mapping(self):
        """Test category lookup with direct mappings."""
        assert get_event_category("mission_started") == "mission"
        assert get_event_category("alliance_formed") == "alliance"
        assert get_event_category("agent_rank_changed") == "rank"

    def test_get_event_category_betrayal_group(self):
        """Test betrayal group mappings."""
        assert get_event_category("alliance_broken") == "betrayal"
        assert get_event_category("treaty_broken") == "betrayal"
        assert get_event_category("betrayal_detected") == "betrayal"

    def test_get_event_category_victory_group(self):
        """Test victory group mappings."""
        assert get_event_category("victory") == "victory"
        assert get_event_category("agent_victory") == "victory"
        assert get_event_category("mission_completed") == "victory"

    def test_get_event_category_unknown_type(self):
        """Test unknown event type returns system category."""
        assert get_event_category("unknown_event_type") == "system"

    def test_create_event_known_type(self):
        """Test factory creates correct event type."""
        event = create_event("mission_started", mission_name="Test", agent_ids=["a1"])
        
        assert isinstance(event, MissionStarted)
        assert event.type == "mission_started"
        assert event.mission_name == "Test"

    def test_create_event_unknown_type(self):
        """Test factory falls back to FeedEvent for unknown types."""
        event = create_event("unknown_custom_type", summary="Custom event")
        
        assert isinstance(event, FeedEvent)
        assert event.type == "unknown_custom_type"
        assert event.summary == "Custom event"

    def test_event_from_dict_mission_started(self):
        """Test deserializing MissionStarted from dict."""
        data = {
            "type": "mission_started",
            "mission_id": "m123",
            "mission_name": "Test Mission",
            "agent_ids": ["a1", "a2"],
            "difficulty": "hard",
        }
        event = event_from_dict(data)
        
        assert isinstance(event, MissionStarted)
        assert event.mission_id == "m123"
        assert event.difficulty == "hard"

    def test_event_from_dict_with_extra_fields(self):
        """Test that extra fields are filtered out during deserialization."""
        data = {
            "type": "feed_event",
            "event_id": "evt_123",
            "extra_field": "ignored",
        }
        event = event_from_dict(data)
        
        assert isinstance(event, FeedEvent)
        assert event.event_id == "evt_123"


# =============================================================================
# Test Broadcaster Module
# =============================================================================

class TestNormalizeFilters:
    """Test filter normalization."""

    def test_empty_filters(self):
        """Test with empty/None filters."""
        assert normalize_filters(None) == set()
        assert normalize_filters([]) == set()
        assert normalize_filters("") == set()

    def test_single_filter(self):
        """Test with single filter."""
        assert normalize_filters(["missions"]) == {"missions"}
        assert normalize_filters("missions") == {"missions"}

    def test_comma_separated_filters(self):
        """Test parsing comma-separated filters."""
        assert normalize_filters(["missions,victories"]) == {"missions", "victories"}
        assert normalize_filters(["missions, victories, alliances"]) == {"missions", "victories", "alliances"}

    def test_case_normalization(self):
        """Test that filters are lowercased."""
        assert normalize_filters(["MISSIONS", "Victories"]) == {"missions", "victories"}


class TestFeedConnection:
    """Test FeedConnection class."""

    def test_connection_creation(self, mock_websocket: AsyncMock):
        """Test connection initialization."""
        conn = FeedConnection(
            id="test_123",
            websocket=mock_websocket,
            filters={"missions"},
        )
        
        assert conn.id == "test_123"
        assert conn.websocket == mock_websocket
        assert conn.filters == {"missions"}
        assert conn.message_count == 0
        assert conn.error_count == 0

    def test_matches_no_filters(self, mock_websocket: AsyncMock):
        """Test that connection with no filters matches all events."""
        conn = FeedConnection(id="test", websocket=mock_websocket, filters=set())
        
        assert conn.matches({"type": "mission_started"}) is True
        assert conn.matches({"type": "victory"}) is True

    def test_matches_type_filter(self, mock_websocket: AsyncMock):
        """Test type-based filtering."""
        conn = FeedConnection(id="test", websocket=mock_websocket, filters={"mission_started"})
        
        assert conn.matches({"type": "mission_started"}) is True
        assert conn.matches({"type": "mission_ended"}) is False

    def test_matches_category_filter(self, mock_websocket: AsyncMock):
        """Test category-based filtering."""
        conn = FeedConnection(id="test", websocket=mock_websocket, filters={"mission"})
        
        assert conn.matches({"type": "mission_started", "category": "mission"}) is True
        assert conn.matches({"type": "victory", "category": "victory"}) is False

    def test_matches_group_filter(self, mock_websocket: AsyncMock):
        """Test group-based filtering (e.g., 'betrayals')."""
        conn = FeedConnection(id="test", websocket=mock_websocket, filters={"betrayals"})
        
        assert conn.matches({"type": "betrayal_detected"}) is True
        assert conn.matches({"type": "treaty_broken"}) is True
        assert conn.matches({"type": "mission_started"}) is False

    def test_rate_limit_initial_tokens(self, mock_websocket: AsyncMock):
        """Test that connection starts with max tokens."""
        conn = FeedConnection(id="test", websocket=mock_websocket)
        
        # Should allow up to RATE_LIMIT_MAX (10) requests immediately
        for _ in range(10):
            assert conn.check_rate_limit() is True
        
        # 11th request should be blocked
        assert conn.check_rate_limit() is False

    def test_rate_limit_refill(self, mock_websocket: AsyncMock):
        """Test that tokens refill over time."""
        conn = FeedConnection(id="test", websocket=mock_websocket)
        
        # Consume all tokens
        for _ in range(10):
            conn.check_rate_limit()
        
        assert conn.check_rate_limit() is False
        
        # Simulate time passing
        conn._rate_limit_last_update -= 1.0  # 1 second ago
        
        # Should have refilled some tokens
        assert conn.check_rate_limit() is True

    def test_record_activity(self, mock_websocket: AsyncMock):
        """Test activity recording."""
        conn = FeedConnection(id="test", websocket=mock_websocket)
        
        initial_count = conn.message_count
        conn.record_activity()
        
        assert conn.message_count == initial_count + 1
        assert conn.last_activity > conn.connected_at


class TestRedisConnectionState:
    """Test RedisConnectionState tracking."""

    def test_initial_state(self):
        """Test initial connection state."""
        state = RedisConnectionState()
        
        assert state.is_connected is False
        assert state.connect_attempts == 0
        assert state.last_connect_attempt == 0.0
        assert state.last_error == ""


class TestFeedBroadcaster:
    """Test FeedBroadcaster class with mocked Redis."""

    @pytest.fixture
    async def broadcaster(self, mock_persistence: AsyncMock) -> AsyncGenerator[FeedBroadcaster, None]:
        """Create a broadcaster with mocked Redis."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(
                redis_url="redis://localhost:6379/0",
                channels=["test:channel"],
                persistence=mock_persistence,
            )
            yield broadcaster

    @pytest.mark.asyncio
    async def test_broadcaster_initialization(self, mock_persistence: AsyncMock):
        """Test broadcaster initialization."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock()
            mock_redis.pubsub = MagicMock(return_value=AsyncMock())
            mock_redis_module.from_url = AsyncMock(return_value=mock_redis)
            
            broadcaster = FeedBroadcaster(
                redis_url="redis://localhost:6379/0",
                persistence=mock_persistence,
            )
            
            assert broadcaster.redis_url == "redis://localhost:6379/0"
            assert broadcaster._recent_events.maxlen == 100  # MAX_EVENTS_MEMORY default

    @pytest.mark.asyncio
    async def test_register_connection(self, mock_websocket: AsyncMock, mock_persistence: AsyncMock):
        """Test registering a WebSocket connection."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            conn = await broadcaster.register(mock_websocket, filters={"missions"})
            
            assert conn.id in broadcaster._connections
            assert broadcaster._connections[conn.id].filters == {"missions"}
            assert broadcaster._metrics["connections_total"] == 1

    @pytest.mark.asyncio
    async def test_unregister_connection(self, mock_websocket: AsyncMock, mock_persistence: AsyncMock):
        """Test unregistering a connection."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            conn = await broadcaster.register(mock_websocket)
            
            assert conn.id in broadcaster._connections
            
            await broadcaster.unregister(conn.id)
            assert conn.id not in broadcaster._connections

    @pytest.mark.asyncio
    async def test_update_filters(self, mock_websocket: AsyncMock, mock_persistence: AsyncMock):
        """Test updating connection filters."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            conn = await broadcaster.register(mock_websocket, filters={"missions"})
            
            await broadcaster.update_filters(conn.id, {"victories", "betrayals"})
            
            assert broadcaster._connections[conn.id].filters == {"victories", "betrayals"}

    @pytest.mark.asyncio
    async def test_get_recent_events(self, mock_persistence: AsyncMock):
        """Test getting recent events."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            
            # Add some events
            broadcaster._recent_events.append({"type": "test1"})
            broadcaster._recent_events.append({"type": "test2"})
            
            recent = broadcaster.get_recent_events(limit=10)
            
            assert len(recent) == 2
            assert recent[0]["type"] == "test1"

    @pytest.mark.asyncio
    async def test_publish_event_dict(self, mock_redis: AsyncMock, mock_persistence: AsyncMock):
        """Test publishing a dict event."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_instance = AsyncMock()
            mock_redis_instance.ping = AsyncMock()
            mock_redis_instance.pubsub = MagicMock(return_value=AsyncMock())
            mock_redis_instance.publish = AsyncMock(return_value=1)
            mock_redis_module.from_url = AsyncMock(return_value=mock_redis_instance)
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            
            # Mock _ensure_redis_connection to return True
            broadcaster._connection_state.is_connected = True
            broadcaster._redis = mock_redis_instance
            
            event = {"type": "test_event", "data": "value"}
            result = await broadcaster.publish_event(event)
            
            assert result == 1
            mock_redis_instance.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_event_feed_event(self, mock_persistence: AsyncMock):
        """Test publishing a FeedEvent."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_instance = AsyncMock()
            mock_redis_instance.ping = AsyncMock()
            mock_redis_instance.pubsub = MagicMock(return_value=AsyncMock())
            mock_redis_instance.publish = AsyncMock(return_value=1)
            mock_redis_module.from_url = AsyncMock(return_value=mock_redis_instance)
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            broadcaster._connection_state.is_connected = True
            broadcaster._redis = mock_redis_instance
            
            event = MissionStarted(mission_name="Test")
            result = await broadcaster.publish_event(event)
            
            assert result == 1
            mock_redis_instance.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_event_redis_not_connected(self, mock_persistence: AsyncMock):
        """Test publishing when Redis is not connected."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(side_effect=Exception("Connection failed"))
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            broadcaster._connection_state.is_connected = False
            
            # Mock _ensure_redis_connection to return False
            with patch.object(broadcaster, '_ensure_redis_connection', return_value=False):
                event = {"type": "test"}
                result = await broadcaster.publish_event(event)
                
                assert result == 0

    @pytest.mark.asyncio
    async def test_fan_out_with_matching_filter(self, mock_websocket: AsyncMock, mock_persistence: AsyncMock):
        """Test fan out to connection with matching filter."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            conn = await broadcaster.register(mock_websocket, filters={"mission"})
            
            event = {"type": "mission_started", "category": "mission", "data": "test"}
            await broadcaster._fan_out(event)
            
            mock_websocket.send_json.assert_called_once()
            call_args = mock_websocket.send_json.call_args[0][0]
            assert call_args["op"] == "event"
            assert call_args["event"]["type"] == "mission_started"

    @pytest.mark.asyncio
    async def test_fan_out_with_non_matching_filter(self, mock_websocket: AsyncMock, mock_persistence: AsyncMock):
        """Test fan out doesn't send to connection with non-matching filter."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            conn = await broadcaster.register(mock_websocket, filters={"victory"})
            
            event = {"type": "mission_started", "category": "mission"}
            await broadcaster._fan_out(event)
            
            mock_websocket.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_fan_out_rate_limit_exceeded(self, mock_websocket: AsyncMock, mock_persistence: AsyncMock):
        """Test that rate-limited connections still receive but error count increases."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            conn = await broadcaster.register(mock_websocket, filters=set())
            
            # Consume all rate limit tokens
            for _ in range(10):
                conn.check_rate_limit()
            
            assert conn.check_rate_limit() is False
            
            # Event should still be sent (rate limit check just increments error count)
            event = {"type": "test"}
            await broadcaster._fan_out(event)

    @pytest.mark.asyncio
    async def test_coerce_event_valid_json(self, mock_persistence: AsyncMock):
        """Test coercing valid JSON message."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            
            message = {
                "data": '{"type": "mission_started", "mission_name": "Test"}',
                "channel": "test:channel",
            }
            
            result = broadcaster._coerce_event(message)
            
            assert result is not None
            assert result["type"] == "mission_started"
            assert result["channel"] == "test:channel"
            assert "event_id" in result
            assert "occurred_at" in result
            assert "category" in result

    @pytest.mark.asyncio
    async def test_coerce_event_bytes(self, mock_persistence: AsyncMock):
        """Test coercing bytes message."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            
            message = {
                "data": b'{"type": "victory"}',
                "channel": "test:channel",
            }
            
            result = broadcaster._coerce_event(message)
            
            assert result is not None
            assert result["type"] == "victory"

    @pytest.mark.asyncio
    async def test_coerce_event_invalid_json(self, mock_persistence: AsyncMock):
        """Test coercing invalid JSON message."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            
            message = {
                "data": "not valid json",
                "channel": "test:channel",
            }
            
            result = broadcaster._coerce_event(message)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_coerce_event_dict(self, mock_persistence: AsyncMock):
        """Test coercing dict message."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            
            message = {
                "data": {"type": "alliance_formed"},
            }
            
            result = broadcaster._coerce_event(message)
            
            assert result is not None
            assert result["type"] == "alliance_formed"

    @pytest.mark.asyncio
    async def test_get_connection_stats(self, mock_websocket: AsyncMock, mock_persistence: AsyncMock):
        """Test getting connection statistics."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            conn = await broadcaster.register(mock_websocket, filters={"missions"})
            
            stats = await broadcaster.get_connection_stats()
            
            assert len(stats) == 1
            assert stats[0]["id"] == conn.id
            assert stats[0]["filters"] == ["missions"]
            assert "connected_at" in stats[0]
            assert "idle_seconds" in stats[0]

    @pytest.mark.asyncio
    async def test_metrics_property(self, mock_websocket: AsyncMock, mock_persistence: AsyncMock):
        """Test metrics property returns correct values."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            await broadcaster.register(mock_websocket)
            
            metrics = broadcaster.metrics
            
            assert "connections_active" in metrics
            assert metrics["connections_active"] == 1
            assert "recent_events_stored" in metrics
            assert "redis_connected" in metrics

    @pytest.mark.asyncio
    async def test_flush_pending_events(self, mock_persistence: AsyncMock):
        """Test flushing pending events to persistence."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            event = MissionStarted(mission_name="Test")
            broadcaster._pending_events = [event]
            
            await broadcaster._flush_pending_events()
            
            mock_persistence.store_events.assert_called_once_with([event])
            assert len(broadcaster._pending_events) == 0

    @pytest.mark.asyncio
    async def test_flush_pending_events_no_persistence(self):
        """Test flushing when persistence is None."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=None)
            event = MissionStarted(mission_name="Test")
            broadcaster._pending_events = [event]
            
            # Should not raise
            await broadcaster._flush_pending_events()
            
            # Events should remain in queue
            assert len(broadcaster._pending_events) == 1

    @pytest.mark.asyncio
    async def test_flush_pending_events_with_error(self, mock_persistence: AsyncMock):
        """Test flush retry on persistence error."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            mock_persistence.store_events = AsyncMock(side_effect=Exception("DB error"))
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            event = MissionStarted(mission_name="Test")
            broadcaster._pending_events = [event]
            
            await broadcaster._flush_pending_events()
            
            # Event should be put back in queue
            assert len(broadcaster._pending_events) == 1


class TestFeedBroadcasterRedisRetry:
    """Test Redis reconnection logic."""

    @pytest.mark.asyncio
    async def test_ensure_redis_connection_success(self, mock_persistence: AsyncMock):
        """Test successful Redis connection."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock()
            mock_pubsub = AsyncMock()
            mock_pubsub.subscribe = AsyncMock()
            mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
            mock_redis_module.from_url = AsyncMock(return_value=mock_redis)
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            result = await broadcaster._ensure_redis_connection()
            
            assert result is True
            assert broadcaster._connection_state.is_connected is True

    @pytest.mark.asyncio
    async def test_ensure_redis_connection_already_connected(self, mock_persistence: AsyncMock):
        """Test when already connected."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock()
            mock_redis_module.from_url = AsyncMock(return_value=mock_redis)
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            broadcaster._connection_state.is_connected = True
            broadcaster._redis = mock_redis
            
            result = await broadcaster._ensure_redis_connection()
            
            assert result is True
            mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_redis_connection_retry_then_success(self, mock_persistence: AsyncMock):
        """Test retry logic eventually succeeds."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock()
            mock_pubsub = AsyncMock()
            mock_pubsub.subscribe = AsyncMock()
            mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
            
            # Fail first 2 attempts, succeed on 3rd
            call_count = 0
            def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise Exception("Connection refused")
                return mock_redis
            
            mock_redis_module.from_url = Mock(side_effect=side_effect)
            
            with patch("asyncio.sleep", new=AsyncMock()):
                broadcaster = FeedBroadcaster(persistence=mock_persistence)
                result = await broadcaster._ensure_redis_connection()
                
                assert result is True
                assert call_count == 3
                assert broadcaster._metrics["redis_reconnects"] == 1

    @pytest.mark.asyncio
    async def test_ensure_redis_connection_all_attempts_fail(self, mock_persistence: AsyncMock):
        """Test when all retry attempts fail."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = Mock(side_effect=Exception("Always fails"))
            
            with patch("asyncio.sleep", new=AsyncMock()):
                broadcaster = FeedBroadcaster(persistence=mock_persistence)
                
                # Reduce retry attempts for faster test
                with patch("broadcaster.REDIS_RETRY_MAX_ATTEMPTS", 2):
                    result = await broadcaster._ensure_redis_connection()
                
                assert result is False
                assert broadcaster._connection_state.is_connected is False

    @pytest.mark.asyncio
    async def test_ensure_redis_connection_shutdown_requested(self, mock_persistence: AsyncMock):
        """Test connection attempt when shutdown is requested."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(side_effect=Exception("Should not be called"))
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            broadcaster._shutdown_event.set()
            
            with patch("asyncio.sleep", new=AsyncMock()):
                result = await broadcaster._ensure_redis_connection()
                
                assert result is False


class TestFeedBroadcasterStop:
    """Test broadcaster graceful shutdown."""

    @pytest.mark.asyncio
    async def test_stop_gracefully(self, mock_persistence: AsyncMock):
        """Test graceful shutdown."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis = AsyncMock()
            mock_redis.aclose = AsyncMock()
            mock_pubsub = AsyncMock()
            mock_pubsub.close = AsyncMock()
            mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
            mock_redis_module.from_url = AsyncMock(return_value=mock_redis)
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            broadcaster._redis = mock_redis
            broadcaster._pubsub = mock_pubsub
            broadcaster._connection_state.is_connected = True
            
            await broadcaster.stop()
            
            assert broadcaster._connection_state.is_connected is False
            mock_pubsub.close.assert_called_once()
            mock_redis.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks(self, mock_persistence: AsyncMock):
        """Test that stop cancels running tasks."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            
            # Create a mock task
            mock_task = AsyncMock()
            mock_task.done = Mock(return_value=False)
            mock_task.cancel = Mock()
            broadcaster._subscriber_task = mock_task
            broadcaster._persistence_task = mock_task
            
            await broadcaster.stop()
            
            assert broadcaster._shutdown_event.is_set()
            mock_task.cancel.assert_called()


# =============================================================================
# Test Persistence Module
# =============================================================================

class TestEventStats:
    """Test EventStats dataclass."""

    def test_default_initialization(self):
        """Test EventStats with default values."""
        stats = EventStats()
        
        assert stats.total_events == 0
        assert stats.events_by_type == {}
        assert stats.events_by_category == {}
        assert stats.events_by_hour == {}
        assert stats.top_agents == []

    def test_custom_initialization(self):
        """Test EventStats with custom values."""
        stats = EventStats(
            total_events=100,
            events_by_type={"mission": 50},
            events_by_category={"mission": 50},
        )
        
        assert stats.total_events == 100
        assert stats.events_by_type == {"mission": 50}


class TestInMemoryPersistence:
    """Test InMemoryPersistence backend."""

    @pytest.fixture
    async def inmem_persistence(self) -> AsyncGenerator[InMemoryPersistence, None]:
        """Create an in-memory persistence instance."""
        persistence = InMemoryPersistence(max_events=100)
        yield persistence

    @pytest.mark.asyncio
    async def test_store_event(self, inmem_persistence: InMemoryPersistence):
        """Test storing a single event."""
        event = MissionStarted(mission_id="m1", agent_ids=["a1"])
        
        result = await inmem_persistence.store_event(event)
        
        assert result is True
        assert event.event_id in inmem_persistence._events

    @pytest.mark.asyncio
    async def test_store_event_extracts_agent_ids(self, inmem_persistence: InMemoryPersistence):
        """Test that agent IDs are extracted and stored."""
        event = AllianceBroken(
            betrayer_id="betrayer",
            victim_ids=["victim1", "victim2"],
        )
        
        await inmem_persistence.store_event(event)
        
        assert "betrayer" in inmem_persistence._agent_events
        assert "victim1" in inmem_persistence._agent_events
        assert "victim2" in inmem_persistence._agent_events

    @pytest.mark.asyncio
    async def test_store_events_batch(self, inmem_persistence: InMemoryPersistence):
        """Test storing multiple events."""
        events = [
            MissionStarted(mission_id=f"m{i}")
            for i in range(5)
        ]
        
        result = await inmem_persistence.store_events(events)
        
        assert result == 5
        assert len(inmem_persistence._events) == 5

    @pytest.mark.asyncio
    async def test_store_events_max_limit(self, inmem_persistence: InMemoryPersistence):
        """Test that old events are removed when max limit reached."""
        persistence = InMemoryPersistence(max_events=3)
        
        events = [
            MissionStarted(mission_id=f"m{i}")
            for i in range(5)
        ]
        
        for event in events:
            await persistence.store_event(event)
        
        # Only 3 events should remain (max_events)
        assert len(persistence._events) == 3

    @pytest.mark.asyncio
    async def test_get_recent_events(self, inmem_persistence: InMemoryPersistence):
        """Test getting recent events."""
        # Store events with different timestamps
        event1 = MissionStarted(mission_id="m1")
        await inmem_persistence.store_event(event1)
        
        event2 = MissionCompleted(mission_id="m2")
        await asyncio.sleep(0.01)  # Small delay
        await inmem_persistence.store_event(event2)
        
        recent = await inmem_persistence.get_recent_events(limit=10)
        
        assert len(recent) == 2
        # Most recent first
        assert recent[0].mission_id == "m2"

    @pytest.mark.asyncio
    async def test_get_recent_events_with_type_filter(self, inmem_persistence: InMemoryPersistence):
        """Test filtering by event type."""
        await inmem_persistence.store_event(MissionStarted(mission_id="m1"))
        await inmem_persistence.store_event(AgentVictory(agent_id="a1"))
        await inmem_persistence.store_event(MissionCompleted(mission_id="m2"))
        
        recent = await inmem_persistence.get_recent_events(
            limit=10,
            event_types=["mission_started", "mission_completed"]
        )
        
        assert len(recent) == 2
        assert all(e.type in ["mission_started", "mission_completed"] for e in recent)

    @pytest.mark.asyncio
    async def test_get_recent_events_with_category_filter(self, inmem_persistence: InMemoryPersistence):
        """Test filtering by category."""
        await inmem_persistence.store_event(MissionStarted(mission_id="m1"))
        await inmem_persistence.store_event(AgentVictory(agent_id="a1"))
        
        recent = await inmem_persistence.get_recent_events(
            limit=10,
            categories=["victory"]
        )
        
        assert len(recent) == 1
        assert recent[0].category == "victory"

    @pytest.mark.asyncio
    async def test_get_events_by_timerange(self, inmem_persistence: InMemoryPersistence):
        """Test getting events within time range."""
        now = datetime.now(timezone.utc)
        
        event = MissionStarted(mission_id="m1")
        await inmem_persistence.store_event(event)
        
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)
        
        events = await inmem_persistence.get_events_by_timerange(start, end)
        
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_get_events_by_timerange_with_type_filter(self, inmem_persistence: InMemoryPersistence):
        """Test time range with type filter."""
        now = datetime.now(timezone.utc)
        
        await inmem_persistence.store_event(MissionStarted(mission_id="m1"))
        await inmem_persistence.store_event(AgentVictory(agent_id="a1"))
        
        events = await inmem_persistence.get_events_by_timerange(
            now - timedelta(hours=1),
            now + timedelta(hours=1),
            event_types=["mission_started"]
        )
        
        assert len(events) == 1
        assert events[0].type == "mission_started"

    @pytest.mark.asyncio
    async def test_get_event_stats(self, inmem_persistence: InMemoryPersistence):
        """Test getting event statistics."""
        await inmem_persistence.store_event(MissionStarted(mission_id="m1"))
        await inmem_persistence.store_event(MissionCompleted(mission_id="m2"))
        await inmem_persistence.store_event(AgentVictory(agent_id="a1"))
        
        stats = await inmem_persistence.get_event_stats()
        
        assert stats.total_events == 3
        assert stats.events_by_type.get("mission_started") == 1
        assert stats.events_by_type.get("mission_completed") == 1
        assert stats.events_by_type.get("agent_victory") == 1

    @pytest.mark.asyncio
    async def test_get_agent_stats(self, inmem_persistence: InMemoryPersistence):
        """Test getting statistics for a specific agent."""
        await inmem_persistence.store_event(MissionStarted(mission_id="m1", agent_ids=["agent_1", "agent_2"]))
        await inmem_persistence.store_event(AgentVictory(agent_id="agent_1"))
        
        stats = await inmem_persistence.get_agent_stats("agent_1")
        
        assert stats["agent_id"] == "agent_1"
        assert stats["total_events"] == 2
        assert "mission_started" in stats["events_by_type"]
        assert "agent_victory" in stats["events_by_type"]


class TestPostgreSQLPersistenceMocked:
    """Test PostgreSQLPersistence with mocked asyncpg."""

    @pytest.fixture
    async def pg_persistence(self) -> AsyncGenerator[PostgreSQLPersistence, None]:
        """Create PostgreSQL persistence with mocked pool."""
        persistence = PostgreSQLPersistence("postgresql://test:test@localhost/test")
        
        # Mock pool
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_pool.close = AsyncMock()
        
        persistence._pool = mock_pool
        persistence._mock_conn = mock_conn  # Save for tests
        
        yield persistence

    @pytest.mark.asyncio
    async def test_store_event(self, pg_persistence: PostgreSQLPersistence):
        """Test storing a single event."""
        event = MissionStarted(mission_id="m1", agent_ids=["a1"])
        
        pg_persistence._mock_conn.execute = AsyncMock(return_value="INSERT 0 1")
        
        result = await pg_persistence.store_event(event)
        
        assert result is True
        assert pg_persistence._mock_conn.execute.call_count >= 2  # Main + agent_events

    @pytest.mark.asyncio
    async def test_store_event_failure(self, pg_persistence: PostgreSQLPersistence):
        """Test store event when DB fails."""
        event = MissionStarted(mission_id="m1")
        
        pg_persistence._mock_conn.execute = AsyncMock(side_effect=Exception("DB error"))
        
        result = await pg_persistence.store_event(event)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_store_events_batch(self, pg_persistence: PostgreSQLPersistence):
        """Test batch event storage."""
        events = [MissionStarted(mission_id=f"m{i}") for i in range(3)]
        
        pg_persistence._mock_conn.execute = AsyncMock(return_value="INSERT 0 1")
        
        result = await pg_persistence.store_events(events)
        
        assert result == 3

    @pytest.mark.asyncio
    async def test_get_recent_events(self, pg_persistence: PostgreSQLPersistence):
        """Test getting recent events."""
        mock_row = MagicMock()
        mock_row.__getitem__ = Mock(side_effect=lambda key: {
            "event_id": "evt_123",
            "type": "mission_started",
            "category": "mission",
            "summary": "Test",
            "occurred_at": datetime.now(timezone.utc),
            "metadata": "{}",
        }.get(key))
        
        pg_persistence._mock_conn.fetch = AsyncMock(return_value=[mock_row])
        
        events = await pg_persistence.get_recent_events(limit=10)
        
        assert len(events) == 1
        assert events[0].event_id == "evt_123"

    @pytest.mark.asyncio
    async def test_get_recent_events_with_filters(self, pg_persistence: PostgreSQLPersistence):
        """Test getting recent events with filters."""
        pg_persistence._mock_conn.fetch = AsyncMock(return_value=[])
        
        events = await pg_persistence.get_recent_events(
            limit=10,
            event_types=["mission_started"],
            categories=["mission"]
        )
        
        # Check that the query was constructed with filters
        call_args = pg_persistence._mock_conn.fetch.call_args
        query = call_args[0][0]
        assert "type IN" in query
        assert "category IN" in query

    @pytest.mark.asyncio
    async def test_get_events_by_timerange(self, pg_persistence: PostgreSQLPersistence):
        """Test getting events by time range."""
        pg_persistence._mock_conn.fetch = AsyncMock(return_value=[])
        
        start = datetime.now(timezone.utc) - timedelta(days=1)
        end = datetime.now(timezone.utc)
        
        events = await pg_persistence.get_events_by_timerange(start, end)
        
        assert len(events) == 0
        pg_persistence._mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_event_stats(self, pg_persistence: PostgreSQLPersistence):
        """Test getting event statistics."""
        mock_total = MagicMock()
        mock_total.__getitem__ = Mock(return_value=100)
        
        pg_persistence._mock_conn.fetchrow = AsyncMock(return_value=mock_total)
        pg_persistence._mock_conn.fetch = AsyncMock(return_value=[])
        
        stats = await pg_persistence.get_event_stats()
        
        assert stats.total_events == 100

    @pytest.mark.asyncio
    async def test_get_agent_stats(self, pg_persistence: PostgreSQLPersistence):
        """Test getting agent statistics."""
        mock_total = MagicMock()
        mock_total.__getitem__ = Mock(return_value=5)
        
        pg_persistence._mock_conn.fetchrow = AsyncMock(return_value=mock_total)
        pg_persistence._mock_conn.fetch = AsyncMock(return_value=[])
        
        stats = await pg_persistence.get_agent_stats("agent_1")
        
        assert stats["agent_id"] == "agent_1"
        assert stats["total_events"] == 5

    @pytest.mark.asyncio
    async def test_cleanup_old_events(self, pg_persistence: PostgreSQLPersistence):
        """Test cleaning up old events."""
        pg_persistence._mock_conn.execute = AsyncMock(return_value="DELETE 50")
        
        result = await pg_persistence.cleanup_old_events(days_to_keep=30)
        
        assert result == 50

    @pytest.mark.asyncio
    async def test_initialize_creates_schema(self, pg_persistence: PostgreSQLPersistence):
        """Test initialization creates database schema."""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool
            
            persistence = PostgreSQLPersistence("postgresql://test:test@localhost/test")
            
            # Initialize should create pool and schema
            await persistence.initialize()
            
            mock_create_pool.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_pool(self, pg_persistence: PostgreSQLPersistence):
        """Test closing the connection pool."""
        await pg_persistence.close()
        
        pg_persistence._pool.close.assert_called_once()
        assert pg_persistence._pool is None


# =============================================================================
# Test WebSocket Module
# =============================================================================

# Import websocket module components
import importlib.util

websocket_path = FEED_SERVICE_DIR / "websocket.py"
if websocket_path.exists():
    spec = importlib.util.spec_from_file_location("websocket_module", websocket_path)
    websocket_module = importlib.util.module_from_spec(spec)
    sys.modules["websocket_module"] = websocket_module
    spec.loader.exec_module(websocket_module)
    
    RateLimiter = websocket_module.RateLimiter
    ConnectionContext = websocket_module.ConnectionContext
    normalize_filters_ws = websocket_module.normalize_filters
    validate_jwt_token = websocket_module.validate_jwt_token
    get_client_ip = websocket_module.get_client_ip
    check_ip_connection_limit = websocket_module.check_ip_connection_limit
    release_ip_connection = websocket_module.release_ip_connection
    _handle_client_message = websocket_module._handle_client_message
    _receive_json = websocket_module._receive_json


class TestRateLimiter:
    """Test WebSocket rate limiter."""

    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        
        assert limiter.max_requests == 10
        assert limiter.window_seconds == 60
        assert limiter.requests == []

    def test_is_allowed_under_limit(self):
        """Test that requests are allowed under the limit."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        
        assert limiter.is_allowed() is True
        assert limiter.is_allowed() is True
        assert limiter.is_allowed() is True
        assert len(limiter.requests) == 3

    def test_is_allowed_over_limit(self):
        """Test that requests are blocked over the limit."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        limiter.is_allowed()
        limiter.is_allowed()
        
        assert limiter.is_allowed() is False

    def test_is_allowed_window_expires(self):
        """Test that old requests are cleared from window."""
        limiter = RateLimiter(max_requests=2, window_seconds=0.01)
        
        limiter.is_allowed()
        limiter.is_allowed()
        assert limiter.is_allowed() is False
        
        # Wait for window to expire
        time.sleep(0.02)
        
        assert limiter.is_allowed() is True

    def test_get_retry_after_no_wait(self):
        """Test retry after when under limit."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        
        assert limiter.get_retry_after() == 0

    def test_get_retry_after_over_limit(self):
        """Test retry after calculation when over limit."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        
        limiter.is_allowed()
        
        retry_after = limiter.get_retry_after()
        assert retry_after > 0


class TestConnectionContext:
    """Test WebSocket connection context."""

    @pytest.fixture
    def connection_context(self, mock_websocket: AsyncMock) -> ConnectionContext:
        """Create a connection context."""
        return ConnectionContext(
            websocket=mock_websocket,
            client_ip="127.0.0.1",
            connection_id="conn_123",
            authenticated=True,
            user_id="user_456",
        )

    def test_context_initialization(self, connection_context: ConnectionContext):
        """Test context initialization."""
        assert connection_context.client_ip == "127.0.0.1"
        assert connection_context.connection_id == "conn_123"
        assert connection_context.authenticated is True
        assert connection_context.user_id == "user_456"
        assert connection_context.message_count == 0

    def test_check_rate_limit_allowed(self, connection_context: ConnectionContext):
        """Test rate limit check when allowed."""
        # Within limit
        for _ in range(29):  # Default is 30 per minute
            connection_context.rate_limiter.is_allowed()
        
        allowed, retry_after = connection_context.check_rate_limit()
        
        assert allowed is True
        assert retry_after == 0

    def test_check_rate_limit_denied(self, connection_context: ConnectionContext):
        """Test rate limit check when denied."""
        # Exceed limit
        for _ in range(30):
            connection_context.rate_limiter.is_allowed()
        
        allowed, retry_after = connection_context.check_rate_limit()
        
        assert allowed is False
        assert retry_after > 0


class TestNormalizeFiltersWS:
    """Test filter normalization in websocket module."""

    def test_empty_filters(self):
        """Test with no filters."""
        assert normalize_filters_ws(None) == set()
        assert normalize_filters_ws([]) == set()

    def test_single_string_filter(self):
        """Test with single string filter."""
        assert normalize_filters_ws("missions") == {"missions"}

    def test_list_filters(self):
        """Test with list of filters."""
        assert normalize_filters_ws(["missions", "victories"]) == {"missions", "victories"}

    def test_comma_separated(self):
        """Test with comma-separated filters."""
        assert normalize_filters_ws(["missions,victories"]) == {"missions", "victories"}


class TestValidateJWTToken:
    """Test JWT token validation."""

    @pytest.mark.asyncio
    async def test_no_token(self):
        """Test validation with no token."""
        authenticated, user_id, payload = await validate_jwt_token(None)
        
        assert authenticated is False
        assert user_id is None

    @pytest.mark.asyncio
    async def test_jwt_not_available(self):
        """Test when PyJWT is not available."""
        with patch("websocket_module.JWT_AVAILABLE", False):
            authenticated, user_id, payload = await validate_jwt_token("some_token")
            
            assert authenticated is False
            assert user_id is None

    @pytest.mark.asyncio
    async def test_valid_token(self):
        """Test validation with valid token."""
        # Mock jwt.decode
        with patch("websocket_module.jwt") as mock_jwt:
            mock_jwt.decode.return_value = {"sub": "user_123", "user_id": "user_123"}
            
            authenticated, user_id, payload = await validate_jwt_token("valid_token")
            
            assert authenticated is True
            assert user_id == "user_123"

    @pytest.mark.asyncio
    async def test_expired_token(self):
        """Test validation with expired token."""
        with patch("websocket_module.jwt") as mock_jwt:
            mock_jwt.ExpiredSignatureError = Exception
            mock_jwt.decode.side_effect = Exception("Expired")
            
            authenticated, user_id, payload = await validate_jwt_token("expired_token")
            
            assert authenticated is False
            assert payload.get("error") == "token_expired"

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        """Test validation with invalid token."""
        with patch("websocket_module.jwt") as mock_jwt:
            mock_jwt.InvalidTokenError = Exception
            mock_jwt.decode.side_effect = Exception("Invalid")
            
            authenticated, user_id, payload = await validate_jwt_token("invalid_token")
            
            assert authenticated is False
            assert payload.get("error") == "invalid_token"


class TestGetClientIP:
    """Test client IP extraction."""

    @pytest.mark.asyncio
    async def test_x_forwarded_for(self, mock_websocket: AsyncMock):
        """Test extracting IP from X-Forwarded-For header."""
        mock_websocket.headers = {"x-forwarded-for": "192.168.1.1, 10.0.0.1"}
        
        ip = await get_client_ip(mock_websocket)
        
        assert ip == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_x_real_ip(self, mock_websocket: AsyncMock):
        """Test extracting IP from X-Real-IP header."""
        mock_websocket.headers = {"x-real-ip": "192.168.1.2"}
        
        ip = await get_client_ip(mock_websocket)
        
        assert ip == "192.168.1.2"

    @pytest.mark.asyncio
    async def test_direct_connection(self, mock_websocket: AsyncMock):
        """Test extracting IP from direct connection."""
        mock_websocket.headers = {}
        mock_websocket.client = Mock(host="192.168.1.3")
        
        ip = await get_client_ip(mock_websocket)
        
        assert ip == "192.168.1.3"

    @pytest.mark.asyncio
    async def test_unknown(self, mock_websocket: AsyncMock):
        """Test fallback to unknown."""
        mock_websocket.headers = {}
        mock_websocket.client = None
        
        ip = await get_client_ip(mock_websocket)
        
        assert ip == "unknown"


class TestIPConnectionLimit:
    """Test IP-based connection limiting."""

    @pytest.mark.asyncio
    async def test_check_ip_connection_under_limit(self):
        """Test allowing connection under limit."""
        with patch("websocket_module._ip_lock", asyncio.Lock()):
            result = await check_ip_connection_limit("192.168.1.1", "conn_1")
            assert result is True

    @pytest.mark.asyncio
    async def test_check_ip_connection_over_limit(self):
        """Test blocking connection over limit."""
        with patch("websocket_module._ip_lock", asyncio.Lock()):
            with patch("websocket_module.WS_MAX_CONNECTIONS_PER_IP", 2):
                # Add existing connections
                with patch("websocket_module._ip_connections", {"192.168.1.1": {"conn_1", "conn_2"}}):
                    result = await check_ip_connection_limit("192.168.1.1", "conn_3")
                    assert result is False

    @pytest.mark.asyncio
    async def test_release_ip_connection(self):
        """Test releasing IP connection."""
        with patch("websocket_module._ip_lock", asyncio.Lock()):
            with patch("websocket_module._ip_connections", {"192.168.1.1": {"conn_1", "conn_2"}}):
                await release_ip_connection("192.168.1.1", "conn_1")


class TestReceiveJSON:
    """Test WebSocket JSON message receiving."""

    @pytest.mark.asyncio
    async def test_receive_valid_json(self, mock_websocket: AsyncMock):
        """Test receiving valid JSON message."""
        mock_websocket.receive = AsyncMock(return_value={
            "type": "websocket.receive",
            "text": '{"op": "ping"}',
        })
        
        result = await _receive_json(mock_websocket)
        
        assert result == {"op": "ping"}

    @pytest.mark.asyncio
    async def test_receive_bytes(self, mock_websocket: AsyncMock):
        """Test receiving bytes message."""
        mock_websocket.receive = AsyncMock(return_value={
            "type": "websocket.receive",
            "bytes": b'{"op": "pong"}',
        })
        
        result = await _receive_json(mock_websocket)
        
        assert result == {"op": "pong"}

    @pytest.mark.asyncio
    async def test_receive_invalid_json(self, mock_websocket: AsyncMock):
        """Test receiving invalid JSON."""
        mock_websocket.receive = AsyncMock(return_value={
            "type": "websocket.receive",
            "text": "not json",
        })
        
        result = await _receive_json(mock_websocket)
        
        assert result["op"] == "invalid"

    @pytest.mark.asyncio
    async def test_receive_disconnect(self, mock_websocket: AsyncMock):
        """Test receiving disconnect message."""
        mock_websocket.receive = AsyncMock(return_value={
            "type": "websocket.disconnect",
            "code": 1000,
        })
        
        with pytest.raises(Exception):  # WebSocketDisconnect
            await _receive_json(mock_websocket)

    @pytest.mark.asyncio
    async def test_receive_empty(self, mock_websocket: AsyncMock):
        """Test receiving empty message."""
        mock_websocket.receive = AsyncMock(return_value={
            "type": "websocket.receive",
        })
        
        result = await _receive_json(mock_websocket)
        
        assert result == {}


class TestHandleClientMessage:
    """Test client message handling."""

    @pytest.fixture
    def mock_connection(self, mock_websocket: AsyncMock) -> FeedConnection:
        """Create a mock feed connection."""
        return FeedConnection(
            id="conn_123",
            websocket=mock_websocket,
            filters=set(),
        )

    @pytest.fixture
    def mock_context(self, mock_websocket: AsyncMock) -> ConnectionContext:
        """Create a mock connection context."""
        return ConnectionContext(
            websocket=mock_websocket,
            client_ip="127.0.0.1",
            connection_id="conn_123",
        )

    @pytest.mark.asyncio
    async def test_handle_ping(
        self,
        mock_websocket: AsyncMock,
        mock_connection: FeedConnection,
        mock_context: ConnectionContext,
    ):
        """Test handling ping message."""
        result = await _handle_client_message(
            mock_websocket,
            mock_connection,
            mock_context,
            {"op": "ping"},
        )
        
        assert result is True
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["op"] == "pong"

    @pytest.mark.asyncio
    async def test_handle_pong(
        self,
        mock_websocket: AsyncMock,
        mock_connection: FeedConnection,
        mock_context: ConnectionContext,
    ):
        """Test handling pong message."""
        result = await _handle_client_message(
            mock_websocket,
            mock_connection,
            mock_context,
            {"op": "pong"},
        )
        
        assert result is True
        mock_websocket.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_subscribe(
        self,
        mock_websocket: AsyncMock,
        mock_connection: FeedConnection,
        mock_context: ConnectionContext,
    ):
        """Test handling subscribe message."""
        with patch("websocket_module.feed_broadcaster") as mock_broadcaster:
            mock_broadcaster.update_filters = AsyncMock()
            
            result = await _handle_client_message(
                mock_websocket,
                mock_connection,
                mock_context,
                {"op": "subscribe", "types": ["missions", "victories"]},
            )
            
            assert result is True
            assert "missions" in mock_connection.filters
            assert "victories" in mock_connection.filters

    @pytest.mark.asyncio
    async def test_handle_unsubscribe(
        self,
        mock_websocket: AsyncMock,
        mock_connection: FeedConnection,
        mock_context: ConnectionContext,
    ):
        """Test handling unsubscribe message."""
        mock_connection.filters = {"missions", "victories"}
        
        with patch("websocket_module.feed_broadcaster") as mock_broadcaster:
            mock_broadcaster.update_filters = AsyncMock()
            
            result = await _handle_client_message(
                mock_websocket,
                mock_connection,
                mock_context,
                {"op": "unsubscribe", "types": ["missions"]},
            )
            
            assert result is True
            assert "missions" not in mock_connection.filters
            assert "victories" in mock_connection.filters

    @pytest.mark.asyncio
    async def test_handle_filter(
        self,
        mock_websocket: AsyncMock,
        mock_connection: FeedConnection,
        mock_context: ConnectionContext,
    ):
        """Test handling filter update message."""
        mock_connection.filters = {"old_filter"}
        
        with patch("websocket_module.feed_broadcaster") as mock_broadcaster:
            mock_broadcaster.update_filters = AsyncMock()
            
            result = await _handle_client_message(
                mock_websocket,
                mock_connection,
                mock_context,
                {"op": "filter", "types": ["new_filter"]},
            )
            
            assert result is True
            assert mock_connection.filters == {"new_filter"}

    @pytest.mark.asyncio
    async def test_handle_get_recent(
        self,
        mock_websocket: AsyncMock,
        mock_connection: FeedConnection,
        mock_context: ConnectionContext,
    ):
        """Test handling get_recent message."""
        with patch("websocket_module.feed_broadcaster") as mock_broadcaster:
            mock_broadcaster.get_recent_events.return_value = [{"type": "test"}]
            
            result = await _handle_client_message(
                mock_websocket,
                mock_connection,
                mock_context,
                {"op": "get_recent", "limit": 10},
            )
            
            assert result is True
            mock_websocket.send_json.assert_called_once()
            call_args = mock_websocket.send_json.call_args[0][0]
            assert call_args["op"] == "recent_events"
            assert len(call_args["events"]) == 1

    @pytest.mark.asyncio
    async def test_handle_get_stats(
        self,
        mock_websocket: AsyncMock,
        mock_connection: FeedConnection,
        mock_context: ConnectionContext,
    ):
        """Test handling get_stats message."""
        with patch("websocket_module.feed_broadcaster") as mock_broadcaster:
            mock_broadcaster.metrics = {"test": "metric"}
            
            result = await _handle_client_message(
                mock_websocket,
                mock_connection,
                mock_context,
                {"op": "get_stats"},
            )
            
            assert result is True
            mock_websocket.send_json.assert_called_once()
            call_args = mock_websocket.send_json.call_args[0][0]
            assert call_args["op"] == "stats"

    @pytest.mark.asyncio
    async def test_handle_close(
        self,
        mock_websocket: AsyncMock,
        mock_connection: FeedConnection,
        mock_context: ConnectionContext,
    ):
        """Test handling close message."""
        result = await _handle_client_message(
            mock_websocket,
            mock_connection,
            mock_context,
            {"op": "close"},
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_handle_rate_limited(
        self,
        mock_websocket: AsyncMock,
        mock_connection: FeedConnection,
        mock_context: ConnectionContext,
    ):
        """Test rate limit response."""
        # Exhaust rate limit
        for _ in range(30):
            mock_context.rate_limiter.is_allowed()
        
        result = await _handle_client_message(
            mock_websocket,
            mock_connection,
            mock_context,
            {"op": "get_stats"},  # Non-ping op to trigger rate limit
        )
        
        assert result is True
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["op"] == "error"
        assert call_args["code"] == "rate_limited"

    @pytest.mark.asyncio
    async def test_handle_unknown_op(
        self,
        mock_websocket: AsyncMock,
        mock_connection: FeedConnection,
        mock_context: ConnectionContext,
    ):
        """Test handling unknown operation."""
        result = await _handle_client_message(
            mock_websocket,
            mock_connection,
            mock_context,
            {"op": "unknown_op"},
        )
        
        assert result is True
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["op"] == "error"
        assert call_args["code"] == "unknown_op"


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_mission_started_empty_agents(self):
        """Test MissionStarted with empty agent list."""
        event = MissionStarted(mission_name="Solo Mission", agent_ids=[])
        assert "0 agents" in event.summary or "Solo Mission" in event.summary

    def test_alliance_formed_single_agent(self):
        """Test AllianceFormed with single agent."""
        event = AllianceFormed(agent_ids=["solo_agent"])
        assert "solo_agent" in event.summary
        assert "and" not in event.summary  # Should not have "and others"

    def test_alliance_broken_no_victims(self):
        """Test AllianceBroken with no victims."""
        event = AllianceBroken(betrayer_id="traitor", victim_ids=[])
        assert "traitor" in event.summary
        assert "0 agents" in event.summary

    def test_event_immutability(self):
        """Test that frozen dataclasses are immutable."""
        event = FeedEvent(type="test")
        
        with pytest.raises(Exception):  # FrozenInstanceError
            event.type = "modified"

    def test_broadcaster_send_to_connection_error(self, mock_websocket: AsyncMock, mock_persistence: AsyncMock):
        """Test handling send error to connection."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            conn = FeedConnection(id="test", websocket=mock_websocket)
            
            mock_websocket.send_json = AsyncMock(side_effect=Exception("Connection closed"))
            
            stale_list = []
            asyncio.run(broadcaster._send_to_connection(conn, {"type": "test"}, stale_list))
            
            assert conn.id in stale_list

    @pytest.mark.asyncio
    async def test_persistence_acquire_conn_not_initialized(self):
        """Test acquiring connection when not initialized."""
        persistence = PostgreSQLPersistence("postgresql://test:test@localhost/test")
        # Don't initialize
        
        with pytest.raises(RuntimeError, match="not initialized"):
            async with persistence._acquire_conn():
                pass

    @pytest.mark.asyncio
    async def test_get_recent_events_db_error(self):
        """Test handling DB error in get_recent_events."""
        persistence = PostgreSQLPersistence("postgresql://test:test@localhost/test")
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(side_effect=Exception("DB error"))
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        persistence._pool = mock_pool
        
        events = await persistence.get_recent_events()
        
        assert events == []

    @pytest.mark.asyncio
    async def test_get_event_stats_db_error(self):
        """Test handling DB error in get_event_stats."""
        persistence = PostgreSQLPersistence("postgresql://test:test@localhost/test")
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        persistence._pool = mock_pool
        
        stats = await persistence.get_event_stats()
        
        assert stats.total_events == 0
        assert stats.events_by_type == {}

    def test_event_groups_definition(self):
        """Test EVENT_GROUPS constant."""
        assert "betrayals" in EVENT_GROUPS
        assert "victories" in EVENT_GROUPS
        assert "alliances" in EVENT_GROUPS
        assert "missions" in EVENT_GROUPS
        assert "ranks" in EVENT_GROUPS
        
        assert "betrayal_detected" in EVENT_GROUPS["betrayals"]
        assert "mission_completed" in EVENT_GROUPS["victories"]

    @pytest.mark.asyncio
    async def test_broadcaster_graceful_shutdown_with_pending_events(self, mock_persistence: AsyncMock):
        """Test graceful shutdown with pending events."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis = AsyncMock()
            mock_redis.aclose = AsyncMock()
            mock_pubsub = AsyncMock()
            mock_pubsub.close = AsyncMock()
            mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
            mock_redis_module.from_url = AsyncMock(return_value=mock_redis)
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            broadcaster._redis = mock_redis
            broadcaster._pubsub = mock_pubsub
            broadcaster._connection_state.is_connected = True
            
            # Add pending events
            event = MissionStarted(mission_id="m1")
            broadcaster._pending_events = [event]
            
            await broadcaster.stop()
            
            # Should flush pending events
            mock_persistence.store_events.assert_called_once_with([event])

    @pytest.mark.asyncio
    async def test_websocket_malformed_event_handling(self, mock_websocket: AsyncMock):
        """Test handling malformed events in broadcaster."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster()
            
            # Malformed message
            message = {"data": None}
            result = broadcaster._coerce_event(message)
            assert result is None
            
            # Non-dict data
            message = {"data": 12345}
            result = broadcaster._coerce_event(message)
            assert result is None

    @pytest.mark.asyncio  
    async def test_fan_out_no_connections(self, mock_persistence: AsyncMock):
        """Test fan out with no connections."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            
            # Should not raise with no connections
            await broadcaster._fan_out({"type": "test"})

    @pytest.mark.asyncio
    async def test_persistence_cleanup_old_events_error(self):
        """Test cleanup error handling."""
        persistence = PostgreSQLPersistence("postgresql://test:test@localhost/test")
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("Cleanup error"))
        mock_pool.acquire = MagicMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        persistence._pool = mock_pool
        
        result = await persistence.cleanup_old_events(days_to_keep=30)
        
        assert result == 0


# =============================================================================
# Integration-style Tests
# =============================================================================

class TestIntegrationScenarios:
    """Integration-style tests combining multiple components."""

    @pytest.mark.asyncio
    async def test_full_event_flow(self, mock_websocket: AsyncMock):
        """Test full event flow: create -> publish -> fan out."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis = AsyncMock()
            mock_redis.ping = AsyncMock()
            mock_redis.publish = AsyncMock(return_value=1)
            mock_pubsub = AsyncMock()
            mock_pubsub.subscribe = AsyncMock()
            mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
            mock_redis_module.from_url = AsyncMock(return_value=mock_redis)
            
            # Create event
            event = MissionStarted(
                mission_id="m123",
                mission_name="Test Mission",
                agent_ids=["agent_1", "agent_2"],
            )
            
            # Create broadcaster
            broadcaster = FeedBroadcaster()
            broadcaster._connection_state.is_connected = True
            broadcaster._redis = mock_redis
            
            # Register connection
            conn = await broadcaster.register(mock_websocket, filters={"mission"})
            
            # Publish event
            result = await broadcaster.publish_event(event)
            assert result == 1

    @pytest.mark.asyncio
    async def test_reconnection_scenario(self, mock_websocket: AsyncMock):
        """Test reconnection with missed events."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster()
            
            # Add some recent events
            for i in range(5):
                broadcaster._recent_events.append({
                    "type": "mission_started",
                    "mission_id": f"m{i}",
                })
            
            # Get recent events (simulating reconnection)
            recent = broadcaster.get_recent_events(limit=10)
            
            assert len(recent) == 5

    def test_all_event_classes_in_factory(self):
        """Test that all event classes are registered in factory."""
        expected_types = [
            "mission_started",
            "mission_ended",
            "mission_completed",
            "mission_failed",
            "alliance_formed",
            "alliance_dissolved",
            "alliance_broken",
            "treaty_broken",
            "betrayal_detected",
            "agent_rank_changed",
            "agent_promoted",
            "agent_demoted",
            "agent_victory",
            "victory",
            "agent_defeated",
        ]
        
        for event_type in expected_types:
            assert event_type in EVENT_CLASSES, f"{event_type} not in EVENT_CLASSES"
            
            # Should be able to create event
            event = create_event(event_type)
            assert isinstance(event, FeedEvent)

    @pytest.mark.asyncio
    async def test_concurrent_connections(self, mock_persistence: AsyncMock):
        """Test handling multiple concurrent connections."""
        with patch("broadcaster.redis") as mock_redis_module:
            mock_redis_module.from_url = AsyncMock(return_value=AsyncMock())
            
            broadcaster = FeedBroadcaster(persistence=mock_persistence)
            
            connections = []
            for i in range(10):
                ws = AsyncMock()
                conn = await broadcaster.register(ws, filters={"missions"})
                connections.append(conn)
            
            assert len(broadcaster._connections) == 10
            assert broadcaster._metrics["connections_total"] == 10
            
            # Fan out to all
            event = {"type": "mission_started", "category": "mission"}
            await broadcaster._fan_out(event)
            
            # Each connection should have received the event
            for ws in [c.websocket for c in connections]:
                ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_persistence_round_trip(self):
        """Test storing and retrieving events."""
        persistence = InMemoryPersistence()
        
        # Store events
        events = [
            MissionStarted(mission_id="m1", agent_ids=["a1"]),
            AgentVictory(agent_id="a1", victory_type="test"),
            AllianceBroken(betrayer_id="a2", victim_ids=["a3"]),
        ]
        
        for event in events:
            await persistence.store_event(event)
        
        # Retrieve and verify
        recent = await persistence.get_recent_events(limit=10)
        assert len(recent) == 3
        
        # Filter by type
        missions = await persistence.get_recent_events(
            limit=10,
            event_types=["mission_started"]
        )
        assert len(missions) == 1
        
        # Get stats
        stats = await persistence.get_event_stats()
        assert stats.total_events == 3
        assert "mission_started" in stats.events_by_type
        assert "agent_victory" in stats.events_by_type
        assert "alliance_broken" in stats.events_by_type
        
        # Get agent stats
        agent_stats = await persistence.get_agent_stats("a1")
        assert agent_stats["total_events"] == 2  # Mission + Victory
