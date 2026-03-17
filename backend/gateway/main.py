"""
CLAWSEUM Gateway API - Main Application
Production-ready FastAPI gateway with middleware and routers.
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from config import get_settings
from database import DatabaseManager, init_database
from auth import APIKeyMiddleware
from models import HealthCheckResponse, ErrorResponse, ErrorDetail

# Import routers
from routers import agents, missions, alliances

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    settings = get_settings()
    
    # Startup
    logger.info(f"Starting CLAWSEUM Gateway API v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.APP_ENV}")
    
    # Initialize database
    await DatabaseManager.initialize()
    
    # Initialize schema (in production, use Alembic migrations instead)
    if settings.is_development:
        await init_database()
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await DatabaseManager.close()
    logger.info("Application shutdown complete")


# Create FastAPI application
def create_application() -> FastAPI:
    """Factory function to create FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Production-ready gateway API for the CLAWSEUM multi-agent arena",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
        default_response_class=JSONResponse
    )
    
    # Add state for startup time
    app.state.start_time = datetime.now(timezone.utc)
    
    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )
    
    # Gzip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """Add unique request ID to each request."""
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    
    # Request timing middleware
    @app.middleware("http")
    async def add_timing(request: Request, call_next):
        """Track request timing."""
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        response.headers["X-Response-Time"] = f"{process_time:.3f}s"
        
        # Log slow requests
        if process_time > 1.0:
            logger.warning(
                "Slow request detected",
                request_id=getattr(request.state, 'request_id', 'unknown'),
                path=request.url.path,
                method=request.method,
                duration=process_time
            )
        
        return response
    
    # Logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log all requests."""
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        logger.info(
            "Request completed",
            request_id=getattr(request.state, 'request_id', 'unknown'),
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration=f"{process_time:.3f}s",
            client_ip=get_remote_address(request),
            user_agent=request.headers.get("user-agent", "unknown")
        )
        
        return response
    
    # Exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle all unhandled exceptions."""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        logger.error(
            "Unhandled exception",
            request_id=request_id,
            error=str(exc),
            exc_info=True
        )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="Internal Server Error",
                message="An unexpected error occurred. Please try again later.",
                request_id=request_id
            ).model_dump()
        )
    
    # Validation error handler
    @app.exception_handler(Exception)
    async def validation_exception_handler(request: Request, exc: Exception):
        """Handle validation errors."""
        from fastapi.exceptions import RequestValidationError
        
        if isinstance(exc, RequestValidationError):
            errors = [
                ErrorDetail(
                    field=".".join(str(x) for x in err.get("loc", [])),
                    message=err.get("msg", ""),
                    code=err.get("type", "")
                )
                for err in exc.errors()
            ]
            
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=ErrorResponse(
                    error="Validation Error",
                    message="Request validation failed",
                    details=errors,
                    request_id=getattr(request.state, 'request_id', 'unknown')
                ).model_dump()
            )
        
        raise exc
    
    return app


# Create the application
app = create_application()


# ============== Health Check Endpoint ==============

@app.get(
    "/health",
    response_model=HealthCheckResponse,
    tags=["Health"],
    summary="Health check endpoint",
    description="Returns application health status and system information."
)
async def health_check(request: Request):
    """Health check endpoint.
    
    Returns:
        Health status, version, environment, and uptime.
    """
    settings = get_settings()
    
    # Calculate uptime
    now = datetime.now(timezone.utc)
    uptime = (now - request.app.state.start_time).total_seconds()
    
    # Check database health
    db_healthy = await DatabaseManager.health_check()
    
    checks = {
        "database": "healthy" if db_healthy else "unhealthy",
        "api": "healthy"
    }
    
    overall_status = "healthy" if db_healthy else "degraded"
    
    return HealthCheckResponse(
        status=overall_status,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        checks=checks,
        uptime_seconds=uptime
    )


# ============== API Routes ==============

app.include_router(agents.router)
app.include_router(missions.router)
app.include_router(alliances.router)


# ============== Root Endpoint ==============

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    settings = get_settings()
    
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "documentation": "/docs" if not settings.is_production else None,
        "health": "/health",
        "endpoints": {
            "agents": "/agents",
            "missions": "/missions",
            "alliances": "/alliances"
        }
    }


# ============== Startup Entry Point ==============

if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=1 if settings.is_development else settings.WORKERS,
        reload=settings.is_development,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True
    )
