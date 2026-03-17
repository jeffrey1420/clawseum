"""CLAWSEUM Feed Service - Production WebSocket handler."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import (
    APIRouter, 
    WebSocket, 
    WebSocketDisconnect, 
    status,
    HTTPException,
    Query,
    Depends
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from broadcaster import feed_broadcaster, normalize_filters, FeedConnection
from persistence import get_persistence

logger = logging.getLogger(__name__)

# Configuration
HEARTBEAT_INTERVAL_SECONDS = float(os.getenv("WS_HEARTBEAT_INTERVAL_SECONDS", "25"))
HEARTBEAT_TIMEOUT_SECONDS = float(os.getenv("WS_HEARTBEAT_TIMEOUT_SECONDS", "10"))
WS_MAX_CONNECTIONS_PER_IP = int(os.getenv("WS_MAX_CONNECTIONS_PER_IP", "10"))
WS_RATE_LIMIT_MESSAGES = int(os.getenv("WS_RATE_LIMIT_MESSAGES", "30"))  # per minute
WS_RATE_LIMIT_WINDOW = float(os.getenv("WS_RATE_LIMIT_WINDOW", "60"))  # seconds
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Auth setup (optional)
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    logger.warning("PyJWT not installed. JWT authentication disabled.")

# Security
security = HTTPBearer(auto_error=False)

router = APIRouter(tags=["feed-websocket"])

# Connection tracking for IP-based limits
_ip_connections: dict[str, set[str]] = {}
_ip_lock = asyncio.Lock()


class RateLimiter:
    """Simple sliding window rate limiter."""
    
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: list[float] = []
    
    def is_allowed(self) -> bool:
        """Check if request is allowed under rate limit."""
        now = time.time()
        
        # Remove old requests outside window
        cutoff = now - self.window_seconds
        self.requests = [t for t in self.requests if t > cutoff]
        
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        return False
    
    def get_retry_after(self) -> int:
        """Get seconds until next request is allowed."""
        if len(self.requests) < self.max_requests:
            return 0
        
        now = time.time()
        cutoff = now - self.window_seconds
        oldest_valid = min(self.requests) if self.requests else now
        return max(1, int(oldest_valid - cutoff))


class ConnectionContext:
    """Context manager for connection lifecycle."""
    
    def __init__(
        self,
        websocket: WebSocket,
        client_ip: str,
        connection_id: str,
        authenticated: bool = False,
        user_id: str | None = None
    ):
        self.websocket = websocket
        self.client_ip = client_ip
        self.connection_id = connection_id
        self.authenticated = authenticated
        self.user_id = user_id
        self.rate_limiter = RateLimiter(WS_RATE_LIMIT_MESSAGES, WS_RATE_LIMIT_WINDOW)
        self.start_time = time.time()
        self.message_count = 0
    
    def check_rate_limit(self) -> tuple[bool, int]:
        """Check if message is allowed under rate limit."""
        allowed = self.rate_limiter.is_allowed()
        retry_after = 0 if allowed else self.rate_limiter.get_retry_after()
        return allowed, retry_after


async def validate_jwt_token(token: str | None) -> tuple[bool, str | None, dict[str, Any]]:
    """Validate JWT token and return user info."""
    if not token or not JWT_AVAILABLE:
        return False, None, {}
    
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub") or payload.get("user_id")
        return True, user_id, payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return False, None, {"error": "token_expired"}
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return False, None, {"error": "invalid_token"}
    except Exception as e:
        logger.error(f"JWT validation error: {e}")
        return False, None, {"error": "validation_error"}


async def get_client_ip(websocket: WebSocket) -> str:
    """Extract client IP from WebSocket connection."""
    # Try X-Forwarded-For first (for proxied connections)
    forwarded_for = websocket.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    # Try X-Real-IP
    real_ip = websocket.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    
    # Fall back to direct connection
    if websocket.client:
        return websocket.client.host
    
    return "unknown"


async def check_ip_connection_limit(client_ip: str, connection_id: str) -> bool:
    """Check and track IP-based connection limits."""
    async with _ip_lock:
        if client_ip not in _ip_connections:
            _ip_connections[client_ip] = set()
        
        if len(_ip_connections[client_ip]) >= WS_MAX_CONNECTIONS_PER_IP:
            return False
        
        _ip_connections[client_ip].add(connection_id)
        return True


async def release_ip_connection(client_ip: str, connection_id: str) -> None:
    """Release IP connection tracking."""
    async with _ip_lock:
        if client_ip in _ip_connections:
            _ip_connections[client_ip].discard(connection_id)
            if not _ip_connections[client_ip]:
                del _ip_connections[client_ip]


async def _receive_json(websocket: WebSocket) -> dict[str, Any]:
    """Receive and parse JSON message from WebSocket."""
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
        return {"op": "invalid", "raw": payload[:100]}  # Truncate long payloads
    
    return parsed if isinstance(parsed, dict) else {}


async def _handle_client_message(
    websocket: WebSocket,
    connection: FeedConnection,
    ctx: ConnectionContext,
    payload: dict[str, Any]
) -> bool:
    """Handle a client message. Returns False to close connection."""
    op = str(payload.get("op", "")).strip().lower()
    
    # Always allow ping/pong
    if op in {"ping"}:
        await websocket.send_json({
            "op": "pong", 
            "ts": datetime.now(timezone.utc).isoformat(),
            "connection_id": ctx.connection_id
        })
        return True
    
    if op == "pong":
        return True
    
    # Check rate limit for other operations
    allowed, retry_after = ctx.check_rate_limit()
    if not allowed:
        await websocket.send_json({
            "op": "error",
            "code": "rate_limited",
            "message": f"Rate limit exceeded. Retry after {retry_after}s",
            "retry_after": retry_after
        })
        return True  # Keep connection open
    
    ctx.message_count += 1
    
    # Handle subscribe/unsubscribe
    if op in {"subscribe", "unsubscribe"}:
        current = set(connection.filters)
        requested = normalize_filters(payload.get("types", []))
        
        if op == "subscribe":
            updated = current | requested
        else:
            updated = current - requested
        
        connection.filters = updated
        await feed_broadcaster.update_filters(connection.id, updated)
        await websocket.send_json({
            "op": "subscribed", 
            "types": sorted(updated),
            "connection_id": ctx.connection_id
        })
        return True
    
    # Handle filter update (set exact filters)
    if op == "filter":
        requested = normalize_filters(payload.get("types", []))
        connection.filters = requested
        await feed_broadcaster.update_filters(connection.id, requested)
        await websocket.send_json({
            "op": "filtered",
            "types": sorted(requested),
            "connection_id": ctx.connection_id
        })
        return True
    
    # Handle get_recent request (reconnection support)
    if op == "get_recent":
        limit = min(int(payload.get("limit", 50)), 100)
        events = feed_broadcaster.get_recent_events(limit)
        await websocket.send_json({
            "op": "recent_events",
            "events": events,
            "connection_id": ctx.connection_id
        })
        return True
    
    # Handle get_stats request
    if op == "get_stats":
        metrics = feed_broadcaster.metrics
        await websocket.send_json({
            "op": "stats",
            "metrics": metrics,
            "connection_id": ctx.connection_id
        })
        return True
    
    # Handle close/disconnect
    if op in {"close", "disconnect"}:
        return False
    
    # Unknown op
    await websocket.send_json({
        "op": "error", 
        "code": "unknown_op",
        "message": f"Unsupported op: {op}",
        "connection_id": ctx.connection_id
    })
    return True


@router.websocket("/ws/feed")
@router.websocket("/feed")  # compatibility with nginx /ws/ -> / rewrite
async def websocket_feed(
    websocket: WebSocket,
    token: str | None = Query(None, description="JWT auth token"),
    types: str = Query("", description="Comma-separated event types to filter"),
    reconnect: bool = Query(False, description="Set true for reconnection to get missed events")
) -> None:
    """
    WebSocket endpoint for real-time feed.
    
    Query Parameters:
    - token: JWT authentication token (optional if public access allowed)
    - types: Comma-separated event types to filter (e.g., "betrayals,victories")
    - reconnect: Set to true to receive recent missed events on connect
    """
    await websocket.accept()
    
    # Get client IP
    client_ip = await get_client_ip(websocket)
    connection_id = f"ws_{websocket.headers.get('sec-websocket-key', 'unknown')[:16]}"
    
    # Check IP connection limit
    if not await check_ip_connection_limit(client_ip, connection_id):
        await websocket.send_json({
            "op": "error",
            "code": "connection_limit",
            "message": f"Maximum {WS_MAX_CONNECTIONS_PER_IP} connections per IP exceeded"
        })
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    
    try:
        # Authenticate if token provided or required
        authenticated = False
        user_id = None
        token_payload = {}
        
        if token:
            authenticated, user_id, token_payload = await validate_jwt_token(token)
            if not authenticated:
                await websocket.send_json({
                    "op": "error",
                    "code": "auth_failed",
                    "message": "Authentication failed",
                    "details": token_payload.get("error", "unknown")
                })
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        
        # Ensure broadcaster is started
        await feed_broadcaster.ensure_started()
        
        # Parse filters from query params
        query_filters = normalize_filters(types.split(",") if types else [])
        
        # Register connection
        connection = await feed_broadcaster.register(websocket, filters=query_filters)
        
        # Create connection context
        ctx = ConnectionContext(
            websocket=websocket,
            client_ip=client_ip,
            connection_id=connection.id,
            authenticated=authenticated,
            user_id=user_id
        )
        
        # Send initial snapshot
        snapshot = {
            "op": "snapshot",
            "connection_id": connection.id,
            "subscribed_types": sorted(connection.filters),
            "server_time": datetime.now(timezone.utc).isoformat(),
            "authenticated": authenticated,
            "user_id": user_id,
            "heartbeat": {
                "interval_seconds": HEARTBEAT_INTERVAL_SECONDS,
                "timeout_seconds": HEARTBEAT_TIMEOUT_SECONDS,
            },
            "rate_limit": {
                "messages_per_minute": WS_RATE_LIMIT_MESSAGES,
                "window_seconds": WS_RATE_LIMIT_WINDOW,
            }
        }
        
        # If reconnecting, send recent events
        if reconnect:
            recent_events = feed_broadcaster.get_recent_events(50)
            snapshot["recent_events"] = recent_events
            snapshot["reconnected"] = True
        
        await websocket.send_json(snapshot)
        
        # Main message loop
        try:
            while True:
                try:
                    # Wait for message with heartbeat interval
                    message = await asyncio.wait_for(
                        _receive_json(websocket),
                        timeout=HEARTBEAT_INTERVAL_SECONDS
                    )
                    
                    # Handle message
                    keep_open = await _handle_client_message(
                        websocket, connection, ctx, message
                    )
                    
                    if not keep_open:
                        break
                    
                except asyncio.TimeoutError:
                    # Send heartbeat ping
                    await websocket.send_json({
                        "op": "ping",
                        "ts": datetime.now(timezone.utc).isoformat()
                    })
                    
                    # Wait for pong response
                    try:
                        pong_payload = await asyncio.wait_for(
                            _receive_json(websocket),
                            timeout=HEARTBEAT_TIMEOUT_SECONDS
                        )
                        
                        keep_open = await _handle_client_message(
                            websocket, connection, ctx, pong_payload
                        )
                        
                        if not keep_open:
                            break
                            
                    except asyncio.TimeoutError:
                        logger.info(
                            "Closing idle feed socket %s after missed heartbeat", 
                            connection.id
                        )
                        await websocket.close(
                            code=status.WS_1001_GOING_AWAY, 
                            reason="heartbeat timeout"
                        )
                        break
        
        except WebSocketDisconnect:
            logger.debug(f"WebSocket disconnected: {connection.id}")
        except Exception as e:
            logger.exception(f"WebSocket error for {connection.id}: {e}")
            try:
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            except Exception:
                pass
        finally:
            # Cleanup
            await feed_broadcaster.unregister(connection.id)
            
            # Log connection stats
            duration = time.time() - ctx.start_time
            logger.info(
                f"Connection {connection.id} closed. "
                f"Duration: {duration:.1f}s, Messages: {ctx.message_count}, "
                f"IP: {client_ip}"
            )
    
    finally:
        await release_ip_connection(client_ip, connection_id)


@router.get("/ws/stats")
async def get_websocket_stats() -> dict[str, Any]:
    """Get WebSocket connection statistics (admin endpoint)."""
    broadcaster_metrics = feed_broadcaster.metrics
    connection_stats = await feed_broadcaster.get_connection_stats()
    
    # Get IP connection counts
    ip_counts = {ip: len(conns) for ip, conns in _ip_connections.items()}
    
    return {
        "broadcaster": broadcaster_metrics,
        "connections": connection_stats,
        "ip_counts": ip_counts,
        "total_unique_ips": len(_ip_connections),
        "config": {
            "max_connections_per_ip": WS_MAX_CONNECTIONS_PER_IP,
            "rate_limit_messages": WS_RATE_LIMIT_MESSAGES,
            "rate_limit_window": WS_RATE_LIMIT_WINDOW,
            "heartbeat_interval": HEARTBEAT_INTERVAL_SECONDS,
            "heartbeat_timeout": HEARTBEAT_TIMEOUT_SECONDS,
        }
    }
