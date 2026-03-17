"""WebSocket endpoint for CLAWSEUM live feed."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from broadcaster import feed_broadcaster, normalize_filters

logger = logging.getLogger(__name__)

HEARTBEAT_INTERVAL_SECONDS = float(os.getenv("WS_HEARTBEAT_INTERVAL_SECONDS", "25"))
HEARTBEAT_TIMEOUT_SECONDS = float(os.getenv("WS_HEARTBEAT_TIMEOUT_SECONDS", "10"))

router = APIRouter(tags=["feed-websocket"])


async def _receive_json(websocket: WebSocket) -> dict[str, Any]:
    message = await websocket.receive()

    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", status.WS_1000_NORMAL_CLOSURE))

    payload: Any = message.get("text")
    if payload is None and message.get("bytes") is not None:
        payload = message["bytes"].decode("utf-8", errors="replace")

    if payload is None:
        return {}

    if isinstance(payload, dict):
        return payload

    if not isinstance(payload, str):
        return {}

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return {"op": "invalid", "raw": payload}

    return parsed if isinstance(parsed, dict) else {}


@router.websocket("/ws/feed")
@router.websocket("/feed")  # compatibility with nginx /ws/ -> / rewrite
async def websocket_feed(websocket: WebSocket) -> None:
    await websocket.accept()
    await feed_broadcaster.ensure_started()

    query_filters = normalize_filters(websocket.query_params.get("types", "").split(","))
    connection = await feed_broadcaster.register(websocket, filters=query_filters)

    await websocket.send_json(
        {
            "op": "snapshot",
            "connection_id": connection.id,
            "subscribed_types": sorted(connection.filters),
            "server_time": datetime.now(timezone.utc).isoformat(),
            "heartbeat": {
                "interval_seconds": HEARTBEAT_INTERVAL_SECONDS,
                "timeout_seconds": HEARTBEAT_TIMEOUT_SECONDS,
            },
        }
    )

    async def _handle_client_message(payload: dict[str, Any]) -> bool:
        op = str(payload.get("op", "")).strip().lower()

        if op in {"", "event"}:
            return True

        if op == "ping":
            await websocket.send_json({"op": "pong", "ts": datetime.now(timezone.utc).isoformat()})
            return True

        if op == "pong":
            return True

        if op in {"subscribe", "unsubscribe"}:
            current = set(connection.filters)
            requested = normalize_filters(payload.get("types", []))

            if op == "subscribe":
                updated = requested if requested else current
            else:
                updated = current - requested if requested else set()

            connection.filters = updated
            await feed_broadcaster.update_filters(connection.id, updated)
            await websocket.send_json({"op": "subscribed", "types": sorted(updated)})
            return True

        if op in {"close", "disconnect"}:
            return False

        await websocket.send_json({"op": "error", "message": f"Unsupported op: {op}"})
        return True

    try:
        while True:
            try:
                message = await asyncio.wait_for(_receive_json(websocket), timeout=HEARTBEAT_INTERVAL_SECONDS)
                keep_open = await _handle_client_message(message)
                if not keep_open:
                    break
            except asyncio.TimeoutError:
                await websocket.send_json({"op": "ping", "ts": datetime.now(timezone.utc).isoformat()})
                try:
                    pong_payload = await asyncio.wait_for(_receive_json(websocket), timeout=HEARTBEAT_TIMEOUT_SECONDS)
                    keep_open = await _handle_client_message(pong_payload)
                    if not keep_open:
                        break
                except asyncio.TimeoutError:
                    logger.info("Closing idle feed socket %s after missed heartbeat", connection.id)
                    await websocket.close(code=status.WS_1001_GOING_AWAY, reason="heartbeat timeout")
                    break
    except WebSocketDisconnect:
        pass
    finally:
        await feed_broadcaster.unregister(connection.id)
