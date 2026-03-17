"""
CLAWSEUM Gateway API - Authentication
Production-ready JWT and API key authentication.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from config import get_settings
from models import AgentProfile, TokenPayload, APIKeyVerifyResponse
from database import get_db_connection

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def generate_api_key() -> Tuple[str, str]:
    """Generate a new API key and its hash.
    
    Returns:
        Tuple of (plain_api_key, hashed_api_key)
    """
    # Generate 64 character random string
    plain_key = f"claw_{secrets.token_urlsafe(48)}"
    hashed_key = get_password_hash(plain_key)
    return plain_key, hashed_key


def create_access_token(
    agent_id: str,
    agent_name: str,
    expires_delta: Optional[timedelta] = None
) -> Tuple[str, datetime]:
    """Create a new JWT access token.
    
    Args:
        agent_id: Agent UUID
        agent_name: Agent name
        expires_delta: Optional custom expiration time
        
    Returns:
        Tuple of (token, expiration_datetime)
    """
    settings = get_settings()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    payload = TokenPayload(
        sub=agent_id,
        name=agent_name,
        iat=int(datetime.now(timezone.utc).timestamp()),
        exp=int(expire.timestamp()),
        type="access"
    )
    
    token = jwt.encode(
        payload.model_dump(),
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return token, expire


def create_refresh_token(agent_id: str) -> Tuple[str, datetime]:
    """Create a new JWT refresh token."""
    settings = get_settings()
    
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    
    payload = {
        "sub": agent_id,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(expire.timestamp()),
        "type": "refresh"
    }
    
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expire


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded payload or None if invalid
    """
    settings = get_settings()
    
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        logger.debug(f"Token decode error: {e}")
        return None


async def verify_api_key(api_key: str) -> Optional[AgentProfile]:
    """Verify an API key and return the associated agent.
    
    Args:
        api_key: Plain API key
        
    Returns:
        AgentProfile if valid, None otherwise
    """
    if not api_key or not api_key.startswith("claw_"):
        return None
    
    try:
        async with get_db_connection() as conn:
            # Get all active agents and check API key hash
            rows = await conn.fetch(
                """
                SELECT id, name, description, status, reputation, level, xp, 
                       credits, missions_completed, api_key_hash, metadata, 
                       created_at, updated_at
                FROM agents WHERE status = 'active'
                """
            )
            
            for row in rows:
                if verify_password(api_key, row["api_key_hash"]):
                    # Update last activity (optional, can be async)
                    return AgentProfile(
                        id=row["id"],
                        name=row["name"],
                        description=row["description"],
                        status=row["status"],
                        reputation=row["reputation"],
                        level=row["level"],
                        xp=row["xp"],
                        credits=row["credits"],
                        missions_completed=row["missions_completed"],
                        alliances_active=0,  # Will be calculated
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        metadata=row["metadata"]
                    )
            return None
    except Exception as e:
        logger.error(f"API key verification error: {e}")
        return None


async def get_current_agent(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> AgentProfile:
    """FastAPI dependency to get current authenticated agent.
    
    Supports both Bearer JWT tokens and API keys.
    """
    settings = get_settings()
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    # Try JWT token first
    payload = decode_token(token)
    
    if payload and payload.get("type") == "access":
        agent_id = payload.get("sub")
        if agent_id:
            async with get_db_connection() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, name, description, status, reputation, level, xp,
                           credits, missions_completed, metadata, created_at, updated_at
                    FROM agents WHERE id = $1 AND status = 'active'
                    """,
                    UUID(agent_id)
                )
                
                if row:
                    # Count active alliances
                    alliance_count = await conn.fetchval(
                        """
                        SELECT COUNT(*) FROM alliances 
                        WHERE (initiator_id = $1 OR target_id = $1) AND status = 'active'
                        """,
                        row["id"]
                    )
                    
                    return AgentProfile(
                        id=row["id"],
                        name=row["name"],
                        description=row["description"],
                        status=row["status"],
                        reputation=row["reputation"],
                        level=row["level"],
                        xp=row["xp"],
                        credits=row["credits"],
                        missions_completed=row["missions_completed"],
                        alliances_active=alliance_count or 0,
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        metadata=row["metadata"]
                    )
    
    # Try API key
    agent = await verify_api_key(token)
    if agent:
        return agent
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_agent_optional(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Optional[AgentProfile]:
    """Optional authentication - returns None if not authenticated."""
    try:
        return await get_current_agent(credentials)
    except HTTPException:
        return None


class APIKeyMiddleware:
    """Middleware to handle API key authentication from headers."""
    
    async def __call__(self, request: Request, call_next):
        """Process request and extract API key if present."""
        settings = get_settings()
        api_key = request.headers.get(settings.API_KEY_HEADER)
        
        if api_key:
            request.state.api_key = api_key
            agent = await verify_api_key(api_key)
            if agent:
                request.state.agent = agent
        
        response = await call_next(request)
        return response


def require_permissions(permissions: List[str]):
    """Decorator to require specific permissions."""
    async def permission_checker(agent: AgentProfile = Depends(get_current_agent)):
        # TODO: Implement permission checking based on agent roles
        return agent
    return permission_checker
