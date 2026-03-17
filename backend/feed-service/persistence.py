"""CLAWSEUM Feed Service - PostgreSQL event persistence."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, AsyncIterator, Protocol

import asyncpg
from asyncpg import Pool, Connection

from events import FeedEvent, event_from_dict, get_event_category

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://clawseum:clawseum@localhost:5432/clawseum_feed"
)

# Connection pool settings for high concurrency
POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "5"))
POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "50"))
POOL_MAX_INACTIVE_TIME = int(os.getenv("DB_POOL_MAX_INACTIVE_TIME", "300"))
POOL_MAX_QUERIES = int(os.getenv("DB_POOL_MAX_QUERIES", "50000"))


@dataclass
class EventStats:
    """Event statistics aggregate."""
    total_events: int = 0
    events_by_type: dict[str, int] = None  # type: ignore
    events_by_category: dict[str, int] = None  # type: ignore
    events_by_hour: dict[str, int] = None  # type: ignore
    top_agents: list[dict[str, Any]] = None  # type: ignore
    
    def __post_init__(self):
        if self.events_by_type is None:
            self.events_by_type = {}
        if self.events_by_category is None:
            self.events_by_category = {}
        if self.events_by_hour is None:
            self.events_by_hour = {}
        if self.top_agents is None:
            self.top_agents = []


class PersistenceBackend(Protocol):
    """Protocol for persistence backends."""
    
    async def store_event(self, event: FeedEvent) -> bool:
        """Store a single event."""
        ...
    
    async def store_events(self, events: list[FeedEvent]) -> int:
        """Store multiple events."""
        ...
    
    async def get_recent_events(
        self, 
        limit: int = 100, 
        event_types: list[str] | None = None,
        categories: list[str] | None = None
    ) -> list[FeedEvent]:
        """Get recent events with optional filtering."""
        ...
    
    async def get_events_by_timerange(
        self,
        start: datetime,
        end: datetime,
        event_types: list[str] | None = None,
        limit: int = 1000
    ) -> list[FeedEvent]:
        """Get events within a time range."""
        ...
    
    async def get_event_stats(
        self,
        start: datetime | None = None,
        end: datetime | None = None
    ) -> EventStats:
        """Get event statistics."""
        ...
    
    async def get_agent_stats(self, agent_id: str) -> dict[str, Any]:
        """Get statistics for a specific agent."""
        ...


class PostgreSQLPersistence:
    """PostgreSQL-based event persistence."""
    
    def __init__(self, database_url: str = DEFAULT_DATABASE_URL) -> None:
        self.database_url = database_url
        self._pool: Pool | None = None
        self._lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """Initialize the database pool and schema."""
        async with self._lock:
            if self._pool is not None:
                return
            
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=POOL_MIN_SIZE,
                max_size=POOL_MAX_SIZE,
                max_inactive_time=POOL_MAX_INACTIVE_TIME,
                max_queries=POOL_MAX_QUERIES,
                command_timeout=30,
            )
            
            await self._create_schema()
            logger.info("PostgreSQL persistence initialized")
    
    async def close(self) -> None:
        """Close the database pool."""
        async with self._lock:
            if self._pool is not None:
                await self._pool.close()
                self._pool = None
                logger.info("PostgreSQL persistence closed")
    
    async def _create_schema(self) -> None:
        """Create database schema if not exists."""
        async with self._pool.acquire() as conn:  # type: ignore
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS feed_events (
                    event_id VARCHAR(32) PRIMARY KEY,
                    type VARCHAR(64) NOT NULL,
                    category VARCHAR(32) NOT NULL,
                    summary TEXT,
                    occurred_at TIMESTAMPTZ NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feed_events_occurred_at 
                ON feed_events(occurred_at DESC)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feed_events_type 
                ON feed_events(type)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feed_events_category 
                ON feed_events(category)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_feed_events_type_time 
                ON feed_events(type, occurred_at DESC)
            """)
            
            # Agent events tracking
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_events (
                    id SERIAL PRIMARY KEY,
                    agent_id VARCHAR(64) NOT NULL,
                    event_id VARCHAR(32) REFERENCES feed_events(event_id) ON DELETE CASCADE,
                    event_type VARCHAR(64) NOT NULL,
                    occurred_at TIMESTAMPTZ NOT NULL
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_events_agent_id 
                ON agent_events(agent_id, occurred_at DESC)
            """)
            
            # Event aggregation table for fast stats
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS event_hourly_stats (
                    hour TIMESTAMP NOT NULL,
                    event_type VARCHAR(64) NOT NULL,
                    category VARCHAR(32) NOT NULL,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (hour, event_type)
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_hourly_stats_hour 
                ON event_hourly_stats(hour DESC)
            """)
    
    @asynccontextmanager
    async def _acquire_conn(self) -> AsyncIterator[Connection]:
        """Acquire connection from pool with timeout."""
        if self._pool is None:
            raise RuntimeError("PostgreSQL persistence not initialized")
        
        async with self._pool.acquire() as conn:
            yield conn
    
    def _extract_agent_ids(self, event: FeedEvent) -> list[str]:
        """Extract agent IDs from event metadata."""
        agent_ids = []
        
        # Common field names for agent IDs
        for field in ["agent_id", "betrayer_id", "defeated_by"]:
            if hasattr(event, field):
                value = getattr(event, field)
                if value:
                    agent_ids.append(value)
        
        # Check agent_ids list
        if hasattr(event, "agent_ids"):
            ids = getattr(event, "agent_ids")
            if isinstance(ids, list):
                agent_ids.extend(ids)
        
        # Check victim_ids for betrayals
        if hasattr(event, "victim_ids"):
            victims = getattr(event, "victim_ids")
            if isinstance(victims, list):
                agent_ids.extend(victims)
        
        return list(set(agent_ids))  # Remove duplicates
    
    async def store_event(self, event: FeedEvent) -> bool:
        """Store a single event."""
        try:
            async with self._acquire_conn() as conn:
                await conn.execute(
                    """
                    INSERT INTO feed_events (event_id, type, category, summary, occurred_at, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (event_id) DO NOTHING
                    """,
                    event.event_id,
                    event.type,
                    event.category or get_event_category(event.type),
                    event.summary,
                    datetime.fromisoformat(event.occurred_at.replace('Z', '+00:00')),
                    json.dumps(event.metadata or {})
                )
                
                # Store agent associations
                agent_ids = self._extract_agent_ids(event)
                for agent_id in agent_ids:
                    await conn.execute(
                        """
                        INSERT INTO agent_events (agent_id, event_id, event_type, occurred_at)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT DO NOTHING
                        """,
                        agent_id,
                        event.event_id,
                        event.type,
                        datetime.fromisoformat(event.occurred_at.replace('Z', '+00:00'))
                    )
                
                return True
        except Exception as e:
            logger.error(f"Failed to store event {event.event_id}: {e}")
            return False
    
    async def store_events(self, events: list[FeedEvent]) -> int:
        """Store multiple events efficiently using COPY."""
        if not events:
            return 0
        
        try:
            async with self._acquire_conn() as conn:
                # Use transaction for batch insert
                async with conn.transaction():
                    inserted = 0
                    for event in events:
                        result = await conn.execute(
                            """
                            INSERT INTO feed_events (event_id, type, category, summary, occurred_at, metadata)
                            VALUES ($1, $2, $3, $4, $5, $6)
                            ON CONFLICT (event_id) DO NOTHING
                            """,
                            event.event_id,
                            event.type,
                            event.category or get_event_category(event.type),
                            event.summary,
                            datetime.fromisoformat(event.occurred_at.replace('Z', '+00:00')),
                            json.dumps(event.metadata or {})
                        )
                        if result != "INSERT 0 0":
                            inserted += 1
                    
                    # Store agent associations
                    for event in events:
                        agent_ids = self._extract_agent_ids(event)
                        for agent_id in agent_ids:
                            await conn.execute(
                                """
                                INSERT INTO agent_events (agent_id, event_id, event_type, occurred_at)
                                VALUES ($1, $2, $3, $4)
                                ON CONFLICT DO NOTHING
                                """,
                                agent_id,
                                event.event_id,
                                event.type,
                                datetime.fromisoformat(event.occurred_at.replace('Z', '+00:00'))
                            )
                    
                    return inserted
        except Exception as e:
            logger.error(f"Failed to store {len(events)} events: {e}")
            return 0
    
    async def get_recent_events(
        self, 
        limit: int = 100, 
        event_types: list[str] | None = None,
        categories: list[str] | None = None
    ) -> list[FeedEvent]:
        """Get recent events with optional filtering."""
        try:
            async with self._acquire_conn() as conn:
                query = "SELECT * FROM feed_events WHERE 1=1"
                params = []
                
                if event_types:
                    placeholders = ', '.join(f'${i+1}' for i in range(len(event_types)))
                    query += f" AND type IN ({placeholders})"
                    params.extend(event_types)
                
                if categories:
                    placeholders = ', '.join(f'${len(params)+i+1}' for i in range(len(categories)))
                    query += f" AND category IN ({placeholders})"
                    params.extend(categories)
                
                query += f" ORDER BY occurred_at DESC LIMIT ${len(params)+1}"
                params.append(limit)
                
                rows = await conn.fetch(query, *params)
                
                events = []
                for row in rows:
                    event_data = {
                        "event_id": row["event_id"],
                        "type": row["type"],
                        "category": row["category"],
                        "summary": row["summary"],
                        "occurred_at": row["occurred_at"].isoformat(),
                        "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
                    }
                    events.append(event_from_dict(event_data))
                
                return events
        except Exception as e:
            logger.error(f"Failed to get recent events: {e}")
            return []
    
    async def get_events_by_timerange(
        self,
        start: datetime,
        end: datetime,
        event_types: list[str] | None = None,
        limit: int = 1000
    ) -> list[FeedEvent]:
        """Get events within a time range."""
        try:
            async with self._acquire_conn() as conn:
                query = """
                    SELECT * FROM feed_events 
                    WHERE occurred_at >= $1 AND occurred_at <= $2
                """
                params = [start, end]
                
                if event_types:
                    placeholders = ', '.join(f'${len(params)+i+1}' for i in range(len(event_types)))
                    query += f" AND type IN ({placeholders})"
                    params.extend(event_types)
                
                query += f" ORDER BY occurred_at DESC LIMIT ${len(params)+1}"
                params.append(limit)
                
                rows = await conn.fetch(query, *params)
                
                events = []
                for row in rows:
                    event_data = {
                        "event_id": row["event_id"],
                        "type": row["type"],
                        "category": row["category"],
                        "summary": row["summary"],
                        "occurred_at": row["occurred_at"].isoformat(),
                        "metadata": json.loads(row["metadata"]) if row["metadata"] else {}
                    }
                    events.append(event_from_dict(event_data))
                
                return events
        except Exception as e:
            logger.error(f"Failed to get events by timerange: {e}")
            return []
    
    async def get_event_stats(
        self,
        start: datetime | None = None,
        end: datetime | None = None
    ) -> EventStats:
        """Get event statistics."""
        try:
            async with self._acquire_conn() as conn:
                start = start or datetime.now() - timedelta(days=1)
                end = end or datetime.now()
                
                # Total events
                total_row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) as total FROM feed_events 
                    WHERE occurred_at >= $1 AND occurred_at <= $2
                    """,
                    start, end
                )
                total = total_row["total"] if total_row else 0
                
                # Events by type
                type_rows = await conn.fetch(
                    """
                    SELECT type, COUNT(*) as count FROM feed_events 
                    WHERE occurred_at >= $1 AND occurred_at <= $2
                    GROUP BY type
                    """,
                    start, end
                )
                events_by_type = {row["type"]: row["count"] for row in type_rows}
                
                # Events by category
                cat_rows = await conn.fetch(
                    """
                    SELECT category, COUNT(*) as count FROM feed_events 
                    WHERE occurred_at >= $1 AND occurred_at <= $2
                    GROUP BY category
                    """,
                    start, end
                )
                events_by_category = {row["category"]: row["count"] for row in cat_rows}
                
                # Events by hour
                hour_rows = await conn.fetch(
                    """
                    SELECT date_trunc('hour', occurred_at) as hour, COUNT(*) as count 
                    FROM feed_events 
                    WHERE occurred_at >= $1 AND occurred_at <= $2
                    GROUP BY date_trunc('hour', occurred_at)
                    ORDER BY hour
                    """,
                    start, end
                )
                events_by_hour = {row["hour"].isoformat(): row["count"] for row in hour_rows}
                
                # Top agents
                top_agents_rows = await conn.fetch(
                    """
                    SELECT agent_id, COUNT(*) as event_count,
                           COUNT(*) FILTER (WHERE event_type LIKE '%victory%') as victories,
                           COUNT(*) FILTER (WHERE event_type LIKE '%betrayal%' OR event_type LIKE '%broken%') as betrayals
                    FROM agent_events 
                    WHERE occurred_at >= $1 AND occurred_at <= $2
                    GROUP BY agent_id
                    ORDER BY event_count DESC
                    LIMIT 10
                    """,
                    start, end
                )
                top_agents = [
                    {
                        "agent_id": row["agent_id"],
                        "event_count": row["event_count"],
                        "victories": row["victories"],
                        "betrayals": row["betrayals"]
                    }
                    for row in top_agents_rows
                ]
                
                return EventStats(
                    total_events=total,
                    events_by_type=events_by_type,
                    events_by_category=events_by_category,
                    events_by_hour=events_by_hour,
                    top_agents=top_agents
                )
        except Exception as e:
            logger.error(f"Failed to get event stats: {e}")
            return EventStats()
    
    async def get_agent_stats(self, agent_id: str) -> dict[str, Any]:
        """Get statistics for a specific agent."""
        try:
            async with self._acquire_conn() as conn:
                # Total events
                total_row = await conn.fetchrow(
                    "SELECT COUNT(*) as total FROM agent_events WHERE agent_id = $1",
                    agent_id
                )
                total = total_row["total"] if total_row else 0
                
                # Events by type
                type_rows = await conn.fetch(
                    """
                    SELECT event_type, COUNT(*) as count 
                    FROM agent_events 
                    WHERE agent_id = $1
                    GROUP BY event_type
                    """,
                    agent_id
                )
                events_by_type = {row["event_type"]: row["count"] for row in type_rows}
                
                # Recent events
                recent_rows = await conn.fetch(
                    """
                    SELECT e.* FROM feed_events e
                    JOIN agent_events ae ON e.event_id = ae.event_id
                    WHERE ae.agent_id = $1
                    ORDER BY e.occurred_at DESC
                    LIMIT 20
                    """,
                    agent_id
                )
                recent_events = [
                    {
                        "event_id": row["event_id"],
                        "type": row["type"],
                        "summary": row["summary"],
                        "occurred_at": row["occurred_at"].isoformat()
                    }
                    for row in recent_rows
                ]
                
                return {
                    "agent_id": agent_id,
                    "total_events": total,
                    "events_by_type": events_by_type,
                    "recent_events": recent_events
                }
        except Exception as e:
            logger.error(f"Failed to get agent stats for {agent_id}: {e}")
            return {"agent_id": agent_id, "total_events": 0, "events_by_type": {}, "recent_events": []}
    
    async def cleanup_old_events(self, days_to_keep: int = 30) -> int:
        """Clean up events older than specified days."""
        try:
            async with self._acquire_conn() as conn:
                cutoff = datetime.now() - timedelta(days=days_to_keep)
                result = await conn.execute(
                    "DELETE FROM feed_events WHERE occurred_at < $1",
                    cutoff
                )
                # Result format: "DELETE <count>"
                count = int(result.split()[1]) if result else 0
                logger.info(f"Cleaned up {count} old events")
                return count
        except Exception as e:
            logger.error(f"Failed to cleanup old events: {e}")
            return 0


class InMemoryPersistence:
    """In-memory persistence for testing or development."""
    
    def __init__(self, max_events: int = 10000) -> None:
        self._events: dict[str, FeedEvent] = {}
        self._agent_events: dict[str, list[str]] = {}  # agent_id -> event_ids
        self._max_events = max_events
        self._lock = asyncio.Lock()
    
    async def store_event(self, event: FeedEvent) -> bool:
        """Store a single event."""
        async with self._lock:
            self._events[event.event_id] = event
            
            # Extract and store agent associations
            agent_ids = self._extract_agent_ids(event)
            for agent_id in agent_ids:
                if agent_id not in self._agent_events:
                    self._agent_events[agent_id] = []
                self._agent_events[agent_id].append(event.event_id)
            
            # Trim if over limit
            if len(self._events) > self._max_events:
                oldest_key = next(iter(self._events))
                del self._events[oldest_key]
            
            return True
    
    async def store_events(self, events: list[FeedEvent]) -> int:
        """Store multiple events."""
        count = 0
        for event in events:
            if await self.store_event(event):
                count += 1
        return count
    
    async def get_recent_events(
        self, 
        limit: int = 100, 
        event_types: list[str] | None = None,
        categories: list[str] | None = None
    ) -> list[FeedEvent]:
        """Get recent events."""
        async with self._lock:
            events = sorted(
                self._events.values(),
                key=lambda e: e.occurred_at,
                reverse=True
            )
            
            filtered = []
            for event in events:
                if event_types and event.type not in event_types:
                    continue
                if categories and event.category not in categories:
                    continue
                filtered.append(event)
                if len(filtered) >= limit:
                    break
            
            return filtered
    
    async def get_events_by_timerange(
        self,
        start: datetime,
        end: datetime,
        event_types: list[str] | None = None,
        limit: int = 1000
    ) -> list[FeedEvent]:
        """Get events within a time range."""
        async with self._lock:
            events = []
            for event in self._events.values():
                event_time = datetime.fromisoformat(event.occurred_at.replace('Z', '+00:00'))
                if start <= event_time <= end:
                    if event_types and event.type not in event_types:
                        continue
                    events.append(event)
                    if len(events) >= limit:
                        break
            
            return sorted(events, key=lambda e: e.occurred_at, reverse=True)
    
    async def get_event_stats(
        self,
        start: datetime | None = None,
        end: datetime | None = None
    ) -> EventStats:
        """Get event statistics."""
        async with self._lock:
            events = list(self._events.values())
            
            if start and end:
                events = [
                    e for e in events 
                    if start <= datetime.fromisoformat(e.occurred_at.replace('Z', '+00:00')) <= end
                ]
            
            stats = EventStats(total_events=len(events))
            
            for event in events:
                stats.events_by_type[event.type] = stats.events_by_type.get(event.type, 0) + 1
                stats.events_by_category[event.category] = stats.events_by_category.get(event.category, 0) + 1
            
            return stats
    
    async def get_agent_stats(self, agent_id: str) -> dict[str, Any]:
        """Get statistics for a specific agent."""
        async with self._lock:
            event_ids = self._agent_events.get(agent_id, [])
            events = [self._events[eid] for eid in event_ids if eid in self._events]
            
            events_by_type = {}
            for event in events:
                events_by_type[event.type] = events_by_type.get(event.type, 0) + 1
            
            return {
                "agent_id": agent_id,
                "total_events": len(events),
                "events_by_type": events_by_type,
                "recent_events": [e.to_dict() for e in sorted(events, key=lambda e: e.occurred_at, reverse=True)[:20]]
            }
    
    def _extract_agent_ids(self, event: FeedEvent) -> list[str]:
        """Extract agent IDs from event."""
        agent_ids = []
        for field in ["agent_id", "betrayer_id", "defeated_by"]:
            if hasattr(event, field):
                value = getattr(event, field)
                if value:
                    agent_ids.append(value)
        
        if hasattr(event, "agent_ids"):
            ids = getattr(event, "agent_ids")
            if isinstance(ids, list):
                agent_ids.extend(ids)
        
        if hasattr(event, "victim_ids"):
            victims = getattr(event, "victim_ids")
            if isinstance(victims, list):
                agent_ids.extend(victims)
        
        return list(set(agent_ids))


# Factory function
async def create_persistence() -> PersistenceBackend:
    """Create appropriate persistence backend."""
    database_url = os.getenv("DATABASE_URL", "")
    
    if database_url and database_url != "memory":
        persistence = PostgreSQLPersistence(database_url)
        await persistence.initialize()
        return persistence
    else:
        return InMemoryPersistence()


# Global persistence instance
_persistence_instance: PersistenceBackend | None = None


async def get_persistence() -> PersistenceBackend:
    """Get or create global persistence instance."""
    global _persistence_instance
    if _persistence_instance is None:
        _persistence_instance = await create_persistence()
    return _persistence_instance
