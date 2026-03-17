"""CLAWSEUM Feed Service - Redis Pub/Sub broadcaster with event persistence."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Iterable
from uuid import uuid4

import redis.asyncio as redis
from fastapi import WebSocket

from events import FeedEvent, event_from_dict, get_event_category, EVENT_TYPE_CATEGORIES

logger = logging.getLogger(__name__)

# Environment configuration
DEFAULT_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DEFAULT_CHANNEL = os.getenv("REDIS_PUBSUB_CHANNEL", "clawseum:feed:events")
REDIS_RETRY_MAX_ATTEMPTS = int(os.getenv("REDIS_RETRY_MAX_ATTEMPTS", "10"))
REDIS_RETRY_BASE_DELAY = float(os.getenv("REDIS_RETRY_BASE_DELAY", "1.0"))
REDIS_RETRY_MAX_DELAY = float(os.getenv("REDIS_RETRY_MAX_DELAY", "60.0"))

# Event persistence settings
MAX_EVENTS_MEMORY = int(os.getenv("MAX_EVENTS_MEMORY", "100"))  # Last N events in memory
EVENT_BATCH_SIZE = int(os.getenv("EVENT_BATCH_SIZE", "100"))
EVENT_FLUSH_INTERVAL = float(os.getenv("EVENT_FLUSH_INTERVAL", "5.0"))

# Event groups for filtering
EVENT_GROUPS: dict[str, set[str]] = {
    "betrayals": {"betrayal_detected", "treaty_broken", "alliance_broken"},
    "victories": {"mission_completed", "rank_changed", "victory", "agent_victory", "agent_promoted"},
    "alliances": {"alliance_formed", "alliance_dissolved"},
    "missions": {"mission_started", "mission_ended", "mission_completed", "mission_failed"},
    "ranks": {"agent_rank_changed", "agent_promoted", "agent_demoted"},
}


@dataclass
class FeedConnection:
    """Represents one connected WebSocket client with rate limiting."""
    id: str
    websocket: WebSocket
    filters: set[str] = field(default_factory=set)
    connected_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    message_count: int = 0
    error_count: int = 0
    
    # Rate limiting
    _rate_limit_tokens: float = field(default=10.0)
    _rate_limit_last_update: float = field(default_factory=time.time)
    RATE_LIMIT_MAX: float = field(default=10.0)  # Max tokens
    RATE_LIMIT_REFILL: float = field(default=10.0)  # Tokens per second
    
    def matches(self, event: dict[str, Any]) -> bool:
        """Check if event matches connection filters."""
        if not self.filters:
            return True
        
        event_type = str(event.get("type", "")).strip().lower()
        category = str(event.get("category", "")).strip().lower()
        
        # Direct type filter
        if event_type in self.filters:
            return True
        
        # Category filter
        if category and category in self.filters:
            return True
        
        # Group filter
        for group, mapped_types in EVENT_GROUPS.items():
            if group in self.filters and event_type in mapped_types:
                return True
        
        return False
    
    def check_rate_limit(self) -> bool:
        """Check and consume rate limit token. Returns True if allowed."""
        now = time.time()
        elapsed = now - self._rate_limit_last_update
        self._rate_limit_last_update = now
        
        # Refill tokens
        self._rate_limit_tokens = min(
            self.RATE_LIMIT_MAX,
            self._rate_limit_tokens + elapsed * self.RATE_LIMIT_REFILL
        )
        
        if self._rate_limit_tokens >= 1.0:
            self._rate_limit_tokens -= 1.0
            return True
        return False
    
    def record_activity(self) -> None:
        """Record client activity."""
        self.last_activity = time.time()
        self.message_count += 1


@dataclass
class RedisConnectionState:
    """Track Redis connection state for reconnection."""
    is_connected: bool = False
    last_connect_attempt: float = 0.0
    connect_attempts: int = 0
    last_error: str = ""


def normalize_filters(raw_filters: Iterable[str] | None) -> set[str]:
    """Normalize filter strings to lowercase set."""
    if not raw_filters:
        return set()
    
    normalized: set[str] = set()
    for item in raw_filters:
        for token in str(item).split(","):
            token = token.strip().lower()
            if token:
                normalized.add(token)
    
    return normalized


class FeedBroadcaster:
    """
    Production-grade Redis Pub/Sub broadcaster.
    
    Features:
    - Automatic reconnection with exponential backoff
    - Event persistence (last N events in memory + optional DB)
    - Rate limiting per connection
    - Connection health monitoring
    - High-concurrency fan-out
    """
    
    def __init__(
        self, 
        redis_url: str = DEFAULT_REDIS_URL, 
        channels: list[str] | None = None,
        persistence: Any | None = None
    ) -> None:
        self.redis_url = redis_url
        self.channels = channels or [DEFAULT_CHANNEL]
        self.persistence = persistence
        
        # Redis clients
        self._redis: redis.Redis | None = None
        self._pubsub: redis.client.PubSub | None = None
        self._subscriber_task: asyncio.Task[None] | None = None
        self._connection_state = RedisConnectionState()
        
        # Connection management
        self._connections: dict[str, FeedConnection] = {}
        self._state_lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()
        
        # Event persistence
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=MAX_EVENTS_MEMORY)
        self._pending_events: list[FeedEvent] = []
        self._persistence_task: asyncio.Task[None] | None = None
        
        # Metrics
        self._metrics = {
            "events_published": 0,
            "events_fanned_out": 0,
            "connections_total": 0,
            "connections_active": 0,
            "redis_reconnects": 0,
            "redis_errors": 0,
        }
    
    @property
    def metrics(self) -> dict[str, Any]:
        """Get current metrics."""
        return {
            **self._metrics,
            "connections_active": len(self._connections),
            "recent_events_stored": len(self._recent_events),
            "redis_connected": self._connection_state.is_connected,
        }
    
    async def start(self) -> None:
        """Start the broadcaster with retry logic."""
        await self._ensure_redis_connection()
        
        # Start persistence flush task
        if self.persistence:
            self._persistence_task = asyncio.create_task(
                self._persistence_flush_loop(),
                name="feed-persistence-loop"
            )
        
        logger.info("FeedBroadcaster started. Channels=%s", self.channels)
    
    async def stop(self) -> None:
        """Stop the broadcaster gracefully."""
        self._shutdown_event.set()
        
        # Cancel subscriber task
        if self._subscriber_task and not self._subscriber_task.done():
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
        
        # Cancel persistence task
        if self._persistence_task and not self._persistence_task.done():
            self._persistence_task.cancel()
            try:
                await self._persistence_task
            except asyncio.CancelledError:
                pass
        
        # Flush pending events
        if self.persistence and self._pending_events:
            await self._flush_pending_events()
        
        # Close Redis connections
        async with self._state_lock:
            if self._pubsub is not None:
                await self._pubsub.close()
                self._pubsub = None
            
            if self._redis is not None:
                await self._redis.aclose()
                self._redis = None
            
            self._connection_state.is_connected = False
        
        logger.info("FeedBroadcaster stopped")
    
    async def ensure_started(self) -> None:
        """Ensure broadcaster is started."""
        if self._redis is None:
            await self.start()
    
    async def _ensure_redis_connection(self) -> bool:
        """Ensure Redis connection with exponential backoff retry."""
        if self._connection_state.is_connected and self._redis is not None:
            try:
                await self._redis.ping()
                return True
            except Exception:
                self._connection_state.is_connected = False
        
        async with self._state_lock:
            # Double-check after acquiring lock
            if self._connection_state.is_connected and self._redis is not None:
                try:
                    await self._redis.ping()
                    return True
                except Exception:
                    self._connection_state.is_connected = False
            
            # Attempt connection with exponential backoff
            for attempt in range(REDIS_RETRY_MAX_ATTEMPTS):
                if self._shutdown_event.is_set():
                    return False
                
                try:
                    self._connection_state.last_connect_attempt = time.time()
                    
                    # Create new Redis connection
                    self._redis = redis.from_url(
                        self.redis_url, 
                        decode_responses=True,
                        socket_connect_timeout=10,
                        socket_keepalive=True,
                        health_check_interval=30,
                    )
                    
                    # Test connection
                    await self._redis.ping()
                    
                    # Create pub/sub
                    self._pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
                    await self._pubsub.subscribe(*self.channels)
                    
                    # Start subscriber task
                    if self._subscriber_task is None or self._subscriber_task.done():
                        self._subscriber_task = asyncio.create_task(
                            self._subscriber_loop(),
                            name="feed-pubsub-loop"
                        )
                    
                    self._connection_state.is_connected = True
                    self._connection_state.connect_attempts = 0
                    self._connection_state.last_error = ""
                    
                    if attempt > 0:
                        self._metrics["redis_reconnects"] += 1
                        logger.info(f"Redis reconnected after {attempt} attempts")
                    
                    return True
                    
                except Exception as e:
                    self._connection_state.connect_attempts += 1
                    self._connection_state.last_error = str(e)
                    self._metrics["redis_errors"] += 1
                    
                    # Clean up failed connection
                    if self._pubsub:
                        try:
                            await self._pubsub.close()
                        except Exception:
                            pass
                        self._pubsub = None
                    
                    if self._redis:
                        try:
                            await self._redis.aclose()
                        except Exception:
                            pass
                        self._redis = None
                    
                    # Calculate backoff delay
                    delay = min(
                        REDIS_RETRY_MAX_DELAY,
                        REDIS_RETRY_BASE_DELAY * (2 ** attempt)
                    )
                    
                    logger.warning(
                        f"Redis connection attempt {attempt + 1}/{REDIS_RETRY_MAX_ATTEMPTS} "
                        f"failed: {e}. Retrying in {delay:.1f}s..."
                    )
                    
                    await asyncio.sleep(delay)
            
            logger.error(f"Failed to connect to Redis after {REDIS_RETRY_MAX_ATTEMPTS} attempts")
            return False
    
    async def _subscriber_loop(self) -> None:
        """Main subscriber loop with automatic reconnection."""
        while not self._shutdown_event.is_set():
            try:
                if not await self._ensure_redis_connection():
                    await asyncio.sleep(REDIS_RETRY_BASE_DELAY)
                    continue
                
                if self._pubsub is None:
                    await asyncio.sleep(0.1)
                    continue
                
                # Get message with timeout
                message = await self._pubsub.get_message(timeout=1.0)
                
                if not message:
                    await asyncio.sleep(0.01)  # Small delay to prevent busy-wait
                    continue
                
                event = self._coerce_event(message)
                if event is None:
                    continue
                
                # Store in recent events
                self._recent_events.append(event)
                self._metrics["events_published"] += 1
                
                # Add to persistence batch
                if self.persistence:
                    try:
                        feed_event = event_from_dict(event)
                        self._pending_events.append(feed_event)
                    except Exception as e:
                        logger.warning(f"Failed to parse event for persistence: {e}")
                
                # Fan out to clients
                await self._fan_out(event)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception(f"Subscriber loop error: {e}")
                self._connection_state.is_connected = False
                self._metrics["redis_errors"] += 1
                await asyncio.sleep(REDIS_RETRY_BASE_DELAY)
    
    async def _persistence_flush_loop(self) -> None:
        """Periodically flush events to persistence."""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=EVENT_FLUSH_INTERVAL
                )
            except asyncio.TimeoutError:
                if self._pending_events:
                    await self._flush_pending_events()
    
    async def _flush_pending_events(self) -> None:
        """Flush pending events to persistence."""
        if not self.persistence or not self._pending_events:
            return
        
        # Take batch of events
        batch = self._pending_events[:EVENT_BATCH_SIZE]
        self._pending_events = self._pending_events[EVENT_BATCH_SIZE:]
        
        try:
            await self.persistence.store_events(batch)
        except Exception as e:
            logger.error(f"Failed to persist {len(batch)} events: {e}")
            # Put back in queue for retry
            self._pending_events = batch + self._pending_events
            # Trim if too large
            if len(self._pending_events) > MAX_EVENTS_MEMORY * 2:
                self._pending_events = self._pending_events[:MAX_EVENTS_MEMORY]
    
    def _coerce_event(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Parse and normalize event from Redis message."""
        raw = message.get("data")
        channel = message.get("channel")
        
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")
        
        if isinstance(raw, str):
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Ignoring non-JSON message on %s", channel)
                return None
        elif isinstance(raw, dict):
            event = raw
        else:
            return None
        
        if not isinstance(event, dict):
            return None
        
        # Normalize event fields
        event.setdefault("event_id", f"evt_{uuid4().hex[:16]}")
        event.setdefault("occurred_at", datetime.now(timezone.utc).isoformat())
        event.setdefault("category", get_event_category(str(event.get("type", ""))))
        if channel:
            event.setdefault("channel", channel)
        
        return event
    
    async def _fan_out(self, event: dict[str, Any]) -> None:
        """Fan out event to all matching connections."""
        async with self._state_lock:
            connections = list(self._connections.values())
        
        if not connections:
            return
        
        stale_connections: list[str] = []
        tasks: list[Coroutine[Any, Any, None]] = []
        
        for connection in connections:
            if not connection.matches(event):
                continue
            
            # Check rate limit
            if not connection.check_rate_limit():
                connection.error_count += 1
                if connection.error_count > 100:
                    stale_connections.append(connection.id)
                continue
            
            tasks.append(self._send_to_connection(connection, event, stale_connections))
        
        # Send concurrently with gather
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            self._metrics["events_fanned_out"] += len(tasks)
        
        # Clean up stale connections
        if stale_connections:
            async with self._state_lock:
                for conn_id in stale_connections:
                    self._connections.pop(conn_id, None)
    
    async def _send_to_connection(
        self, 
        connection: FeedConnection, 
        event: dict[str, Any],
        stale_list: list[str]
    ) -> None:
        """Send event to a single connection."""
        try:
            await connection.websocket.send_json({"op": "event", "event": event})
            connection.record_activity()
        except Exception:
            stale_list.append(connection.id)
    
    async def register(
        self, 
        websocket: WebSocket, 
        filters: set[str] | None = None
    ) -> FeedConnection:
        """Register a new WebSocket connection."""
        connection = FeedConnection(
            id=f"ws_{uuid4().hex}",
            websocket=websocket,
            filters=filters or set()
        )
        
        async with self._state_lock:
            self._connections[connection.id] = connection
            self._metrics["connections_total"] += 1
        
        return connection
    
    async def unregister(self, connection_id: str) -> None:
        """Unregister a WebSocket connection."""
        async with self._state_lock:
            self._connections.pop(connection_id, None)
    
    async def update_filters(self, connection_id: str, filters: set[str]) -> None:
        """Update filters for a connection."""
        async with self._state_lock:
            conn = self._connections.get(connection_id)
            if conn is not None:
                conn.filters = filters
    
    async def publish_event(
        self, 
        event: dict[str, Any] | FeedEvent, 
        channel: str | None = None
    ) -> int:
        """Publish an event to Redis."""
        await self.ensure_started()
        
        # Ensure connection
        if not await self._ensure_redis_connection():
            logger.error("Cannot publish event: Redis not connected")
            return 0
        
        assert self._redis is not None
        
        # Convert FeedEvent to dict if needed
        if isinstance(event, FeedEvent):
            event = event.to_dict()
        
        # Normalize event
        event.setdefault("event_id", f"evt_{uuid4().hex[:16]}")
        event.setdefault("occurred_at", datetime.now(timezone.utc).isoformat())
        event.setdefault("category", get_event_category(str(event.get("type", ""))))
        
        payload = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
        
        try:
            return await self._redis.publish(channel or self.channels[0], payload)
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")
            self._connection_state.is_connected = False
            return 0
    
    def get_recent_events(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent events for new connections."""
        return list(self._recent_events)[-limit:]
    
    async def get_connection_stats(self) -> list[dict[str, Any]]:
        """Get statistics for all connections."""
        async with self._state_lock:
            return [
                {
                    "id": conn.id,
                    "filters": list(conn.filters),
                    "connected_at": conn.connected_at,
                    "last_activity": conn.last_activity,
                    "message_count": conn.message_count,
                    "error_count": conn.error_count,
                    "idle_seconds": time.time() - conn.last_activity,
                }
                for conn in self._connections.values()
            ]


# Global broadcaster instance
feed_broadcaster = FeedBroadcaster()
