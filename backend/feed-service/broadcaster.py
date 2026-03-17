"""Redis-backed broadcaster for CLAWSEUM real-time feed."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import uuid4

import redis.asyncio as redis
from fastapi import WebSocket

logger = logging.getLogger(__name__)

DEFAULT_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DEFAULT_CHANNEL = os.getenv("REDIS_PUBSUB_CHANNEL", "clawseum:feed:events")

EVENT_GROUPS: dict[str, set[str]] = {
    "betrayals": {"betrayal_detected", "treaty_broken"},
    "victories": {"mission_completed", "rank_changed", "victory"},
    "alliances": {"alliance_formed", "alliance_dissolved"},
}


@dataclass
class FeedConnection:
    """Represents one connected WebSocket client."""

    id: str
    websocket: WebSocket
    filters: set[str] = field(default_factory=set)

    def matches(self, event: dict[str, Any]) -> bool:
        if not self.filters:
            return True

        event_type = str(event.get("type", "")).strip().lower()
        category = str(event.get("category", "")).strip().lower()

        if category and category in self.filters:
            return True

        if event_type in self.filters:
            return True

        for group, mapped_types in EVENT_GROUPS.items():
            if group in self.filters and event_type in mapped_types:
                return True

        return False


def normalize_filters(raw_filters: Iterable[str] | None) -> set[str]:
    if not raw_filters:
        return set()

    normalized: set[str] = set()
    for item in raw_filters:
        for token in str(item).split(","):
            token = token.strip().lower()
            if token:
                normalized.add(token)

    return normalized


def classify_event(event_type: str | None) -> str:
    value = (event_type or "").strip().lower()
    for group, mapped_types in EVENT_GROUPS.items():
        if value in mapped_types:
            return group
    return "general"


class FeedBroadcaster:
    """Subscribe to Redis Pub/Sub and fan out events to connected clients."""

    def __init__(self, redis_url: str = DEFAULT_REDIS_URL, channels: list[str] | None = None) -> None:
        self.redis_url = redis_url
        self.channels = channels or [DEFAULT_CHANNEL]

        self._redis: redis.Redis | None = None
        self._pubsub: redis.client.PubSub | None = None
        self._subscriber_task: asyncio.Task[None] | None = None

        self._connections: dict[str, FeedConnection] = {}
        self._state_lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._state_lock:
            if self._redis is not None:
                return

            self._redis = redis.from_url(self.redis_url, decode_responses=True)
            self._pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
            await self._pubsub.subscribe(*self.channels)
            self._subscriber_task = asyncio.create_task(self._subscriber_loop(), name="feed-pubsub-loop")
            logger.info("FeedBroadcaster started. Channels=%s", self.channels)

    async def ensure_started(self) -> None:
        if self._redis is None:
            await self.start()

    async def stop(self) -> None:
        task: asyncio.Task[None] | None = None
        async with self._state_lock:
            task = self._subscriber_task
            self._subscriber_task = None

            if self._pubsub is not None:
                await self._pubsub.close()
                self._pubsub = None

            if self._redis is not None:
                await self._redis.aclose()
                self._redis = None

        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def register(self, websocket: WebSocket, filters: set[str] | None = None) -> FeedConnection:
        connection = FeedConnection(id=f"ws_{uuid4().hex}", websocket=websocket, filters=filters or set())
        async with self._state_lock:
            self._connections[connection.id] = connection
        return connection

    async def unregister(self, connection_id: str) -> None:
        async with self._state_lock:
            self._connections.pop(connection_id, None)

    async def update_filters(self, connection_id: str, filters: set[str]) -> None:
        async with self._state_lock:
            conn = self._connections.get(connection_id)
            if conn is not None:
                conn.filters = filters

    async def publish_event(self, event: dict[str, Any], channel: str | None = None) -> int:
        """Publish an event into Redis so every feed node can fan out consistently."""
        await self.ensure_started()
        assert self._redis is not None

        payload = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
        return await self._redis.publish(channel or self.channels[0], payload)

    async def _subscriber_loop(self) -> None:
        while True:
            try:
                if self._pubsub is None:
                    await asyncio.sleep(0.1)
                    continue

                message = await self._pubsub.get_message(timeout=1.0)
                if not message:
                    await asyncio.sleep(0.05)
                    continue

                event = self._coerce_event(message)
                if event is None:
                    continue

                await self._fan_out(event)
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - defensive guard for runtime service loops
                logger.exception("FeedBroadcaster subscriber loop crashed; retrying")
                await asyncio.sleep(1.0)

    def _coerce_event(self, message: dict[str, Any]) -> dict[str, Any] | None:
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

        event.setdefault("occurred_at", datetime.now(timezone.utc).isoformat())
        event.setdefault("category", classify_event(str(event.get("type", ""))))
        if channel:
            event.setdefault("channel", channel)
        return event

    async def _fan_out(self, event: dict[str, Any]) -> None:
        async with self._state_lock:
            connections = list(self._connections.values())

        if not connections:
            return

        stale_connections: list[str] = []

        async def _send(connection: FeedConnection) -> None:
            if not connection.matches(event):
                return
            try:
                await connection.websocket.send_json({"op": "event", "event": event})
            except Exception:
                stale_connections.append(connection.id)

        await asyncio.gather(*(_send(conn) for conn in connections), return_exceptions=True)

        if stale_connections:
            async with self._state_lock:
                for conn_id in stale_connections:
                    self._connections.pop(conn_id, None)


feed_broadcaster = FeedBroadcaster()
