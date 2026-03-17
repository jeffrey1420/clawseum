"""CLAWSEUM Feed Service - Production FastAPI application."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse

from broadcaster import feed_broadcaster
from websocket import router as websocket_router
from persistence import get_persistence, create_persistence
from events import (
    MissionStarted, MissionEnded, MissionCompleted, MissionFailed,
    AllianceFormed, AllianceDissolved, AllianceBroken, TreatyBroken, BetrayalDetected,
    AgentRankChanged, AgentPromoted, AgentDemoted,
    AgentVictory, Victory, AgentDefeated
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Service metadata
SERVICE_NAME = "clawseum-feed-service"
SERVICE_VERSION = "1.0.0"
START_TIME = time.time()

# Health check configuration
HEALTH_CHECK_TIMEOUT = float(os.getenv("HEALTH_CHECK_TIMEOUT", "5.0"))


class ServiceState:
    """Track service state for health checks."""
    def __init__(self):
        self.is_ready = False
        self.is_healthy = False
        self.startup_errors: list[str] = []
        self.redis_connected = False
        self.db_connected = False
        self.last_health_check = 0.0


service_state = ServiceState()


async def check_redis_health() -> tuple[bool, str]:
    """Check Redis connection health."""
    try:
        import redis.asyncio as redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        client = redis.from_url(redis_url, socket_connect_timeout=2)
        await client.ping()
        await client.aclose()
        return True, ""
    except Exception as e:
        return False, str(e)


async def check_database_health() -> tuple[bool, str]:
    """Check database connection health."""
    try:
        database_url = os.getenv("DATABASE_URL", "")
        if not database_url or database_url == "memory":
            return True, "Using in-memory persistence"
        
        import asyncpg
        conn = await asyncpg.connect(database_url, timeout=2)
        await conn.execute("SELECT 1")
        await conn.close()
        return True, ""
    except Exception as e:
        return False, str(e)


async def perform_health_checks() -> dict:
    """Perform all health checks."""
    checks = {
        "redis": {"status": "unknown", "error": None},
        "database": {"status": "unknown", "error": None},
    }
    
    # Check Redis
    redis_ok, redis_error = await check_redis_health()
    checks["redis"] = {
        "status": "healthy" if redis_ok else "unhealthy",
        "error": redis_error if not redis_ok else None
    }
    service_state.redis_connected = redis_ok
    
    # Check Database
    db_ok, db_error = await check_database_health()
    checks["database"] = {
        "status": "healthy" if db_ok else "unhealthy",
        "error": db_error if not db_ok else None
    }
    service_state.db_connected = db_ok
    
    # Overall health
    service_state.is_healthy = redis_ok and db_ok
    service_state.last_health_check = time.time()
    
    return checks


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan manager.
    
    Handles:
    - Startup: Initialize broadcaster, persistence, and health checks
    - Shutdown: Graceful cleanup of resources
    """
    logger.info(f"Starting {SERVICE_NAME} v{SERVICE_VERSION}...")
    
    try:
        # Initialize persistence layer
        logger.info("Initializing persistence layer...")
        persistence = await create_persistence()
        
        # Attach persistence to broadcaster
        feed_broadcaster.persistence = persistence
        
        # Start broadcaster (includes Redis connection)
        logger.info("Starting broadcaster...")
        await feed_broadcaster.start()
        
        # Perform initial health check
        logger.info("Performing initial health checks...")
        await perform_health_checks()
        
        service_state.is_ready = True
        service_state.is_healthy = True
        
        uptime = time.time() - START_TIME
        logger.info(f"{SERVICE_NAME} started successfully in {uptime:.2f}s")
        
        yield
        
    except Exception as e:
        service_state.startup_errors.append(str(e))
        logger.exception(f"Failed to start {SERVICE_NAME}: {e}")
        raise
    
    finally:
        # Shutdown
        logger.info(f"Shutting down {SERVICE_NAME}...")
        service_state.is_ready = False
        service_state.is_healthy = False
        
        # Stop broadcaster
        try:
            await feed_broadcaster.stop()
            logger.info("Broadcaster stopped")
        except Exception as e:
            logger.error(f"Error stopping broadcaster: {e}")
        
        # Close persistence
        try:
            persistence = feed_broadcaster.persistence
            if persistence and hasattr(persistence, 'close'):
                await persistence.close()
                logger.info("Persistence layer closed")
        except Exception as e:
            logger.error(f"Error closing persistence: {e}")
        
        logger.info(f"{SERVICE_NAME} shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="CLAWSEUM Feed Service",
    version=SERVICE_VERSION,
    description="Production real-time event feed service for CLAWSEUM",
    lifespan=lifespan,
    docs_url="/docs" if os.getenv("ENABLE_DOCS", "false").lower() == "true" else None,
    redoc_url="/redoc" if os.getenv("ENABLE_DOCS", "false").lower() == "true" else None,
)

# Include WebSocket router
app.include_router(websocket_router)


@app.get("/health", tags=["health"])
async def health_check() -> JSONResponse:
    """
    Health check endpoint for load balancers and monitoring.
    
    Returns:
    - 200 OK if service is healthy
    - 503 Service Unavailable if service is not ready or unhealthy
    """
    if not service_state.is_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "service": SERVICE_NAME,
                "version": SERVICE_VERSION,
                "errors": service_state.startup_errors
            }
        )
    
    # Perform health checks if stale
    if time.time() - service_state.last_health_check > HEALTH_CHECK_TIMEOUT:
        await perform_health_checks()
    
    if service_state.is_healthy:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "healthy",
                "service": SERVICE_NAME,
                "version": SERVICE_VERSION,
                "uptime_seconds": time.time() - START_TIME,
                "checks": {
                    "redis": "connected" if service_state.redis_connected else "disconnected",
                    "database": "connected" if service_state.db_connected else "disconnected"
                }
            }
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": SERVICE_NAME,
                "version": SERVICE_VERSION,
                "checks": await perform_health_checks()
            }
        )


@app.get("/ready", tags=["health"])
async def readiness_check() -> JSONResponse:
    """
    Readiness check for Kubernetes.
    
    Returns 200 when service is ready to accept traffic.
    """
    if service_state.is_ready:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ready",
                "service": SERVICE_NAME
            }
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "service": SERVICE_NAME
            }
        )


@app.get("/metrics", tags=["monitoring"])
async def metrics() -> PlainTextResponse:
    """
    Prometheus-compatible metrics endpoint.
    
    Returns metrics in Prometheus exposition format.
    """
    metrics_data = []
    
    # Service info
    metrics_data.append(f'# HELP {SERVICE_NAME}_info Service information')
    metrics_data.append(f'# TYPE {SERVICE_NAME}_info gauge')
    metrics_data.append(f'{SERVICE_NAME}_info{{version="{SERVICE_VERSION}"}} 1')
    
    # Uptime
    uptime = time.time() - START_TIME
    metrics_data.append(f'# HELP {SERVICE_NAME}_uptime_seconds Service uptime in seconds')
    metrics_data.append(f'# TYPE {SERVICE_NAME}_uptime_seconds gauge')
    metrics_data.append(f'{SERVICE_NAME}_uptime_seconds {uptime}')
    
    # Broadcaster metrics
    broadcaster_metrics = feed_broadcaster.metrics
    
    metrics_data.append(f'# HELP {SERVICE_NAME}_events_published_total Total events published')
    metrics_data.append(f'# TYPE {SERVICE_NAME}_events_published_total counter')
    metrics_data.append(f'{SERVICE_NAME}_events_published_total {broadcaster_metrics.get("events_published", 0)}')
    
    metrics_data.append(f'# HELP {SERVICE_NAME}_events_fanned_out_total Total events fanned out to clients')
    metrics_data.append(f'# TYPE {SERVICE_NAME}_events_fanned_out_total counter')
    metrics_data.append(f'{SERVICE_NAME}_events_fanned_out_total {broadcaster_metrics.get("events_fanned_out", 0)}')
    
    metrics_data.append(f'# HELP {SERVICE_NAME}_connections_total Total WebSocket connections')
    metrics_data.append(f'# TYPE {SERVICE_NAME}_connections_total counter')
    metrics_data.append(f'{SERVICE_NAME}_connections_total {broadcaster_metrics.get("connections_total", 0)}')
    
    metrics_data.append(f'# HELP {SERVICE_NAME}_connections_active Active WebSocket connections')
    metrics_data.append(f'# TYPE {SERVICE_NAME}_connections_active gauge')
    metrics_data.append(f'{SERVICE_NAME}_connections_active {broadcaster_metrics.get("connections_active", 0)}')
    
    metrics_data.append(f'# HELP {SERVICE_NAME}_recent_events_stored Recent events in memory')
    metrics_data.append(f'# TYPE {SERVICE_NAME}_recent_events_stored gauge')
    metrics_data.append(f'{SERVICE_NAME}_recent_events_stored {broadcaster_metrics.get("recent_events_stored", 0)}')
    
    metrics_data.append(f'# HELP {SERVICE_NAME}_redis_connected Redis connection status')
    metrics_data.append(f'# TYPE {SERVICE_NAME}_redis_connected gauge')
    metrics_data.append(f'{SERVICE_NAME}_redis_connected {1 if broadcaster_metrics.get("redis_connected", False) else 0}')
    
    metrics_data.append(f'# HELP {SERVICE_NAME}_redis_reconnects_total Total Redis reconnections')
    metrics_data.append(f'# TYPE {SERVICE_NAME}_redis_reconnects_total counter')
    metrics_data.append(f'{SERVICE_NAME}_redis_reconnects_total {broadcaster_metrics.get("redis_reconnects", 0)}')
    
    metrics_data.append(f'# HELP {SERVICE_NAME}_redis_errors_total Total Redis errors')
    metrics_data.append(f'# TYPE {SERVICE_NAME}_redis_errors_total counter')
    metrics_data.append(f'{SERVICE_NAME}_redis_errors_total {broadcaster_metrics.get("redis_errors", 0)}')
    
    return PlainTextResponse(
        content="\n".join(metrics_data) + "\n",
        media_type="text/plain"
    )


@app.get("/api/v1/events/recent", tags=["events"])
async def get_recent_events(
    limit: int = 100,
    event_types: str | None = None,
    categories: str | None = None
) -> JSONResponse:
    """
    Get recent events from persistence.
    
    Query Parameters:
    - limit: Maximum number of events (default: 100, max: 1000)
    - event_types: Comma-separated event types to filter
    - categories: Comma-separated categories to filter
    """
    limit = min(max(limit, 1), 1000)
    
    type_list = event_types.split(",") if event_types else None
    category_list = categories.split(",") if categories else None
    
    persistence = await get_persistence()
    events = await persistence.get_recent_events(
        limit=limit,
        event_types=type_list,
        categories=category_list
    )
    
    return JSONResponse(content={
        "events": [e.to_dict() for e in events],
        "count": len(events)
    })


@app.get("/api/v1/events/stats", tags=["events"])
async def get_event_stats() -> JSONResponse:
    """Get event statistics from persistence."""
    persistence = await get_persistence()
    stats = await persistence.get_event_stats()
    
    return JSONResponse(content={
        "total_events": stats.total_events,
        "events_by_type": stats.events_by_type,
        "events_by_category": stats.events_by_category,
        "events_by_hour": stats.events_by_hour,
        "top_agents": stats.top_agents
    })


@app.get("/api/v1/agents/{agent_id}/stats", tags=["agents"])
async def get_agent_stats(agent_id: str) -> JSONResponse:
    """Get statistics for a specific agent."""
    persistence = await get_persistence()
    stats = await persistence.get_agent_stats(agent_id)
    
    return JSONResponse(content=stats)


@app.get("/", tags=["info"])
async def root() -> JSONResponse:
    """Service root endpoint."""
    return JSONResponse(content={
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "status": "healthy" if service_state.is_healthy else "unhealthy",
        "endpoints": {
            "websocket": "/ws/feed",
            "health": "/health",
            "ready": "/ready",
            "metrics": "/metrics",
            "events_recent": "/api/v1/events/recent",
            "events_stats": "/api/v1/events/stats",
        }
    })


# Error handlers
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle generic exceptions."""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )
