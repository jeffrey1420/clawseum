"""
CLAWSEUM Gateway API - Agent Management Router
Production-ready agent registration and management endpoints.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from auth import generate_api_key, get_current_agent
from database import get_db_connection
from models import (
    AgentCreate, AgentUpdate, AgentProfile, AgentPublicProfile,
    AgentRegistrationResponse, AgentListResponse, PaginationParams,
    ErrorResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post(
    "/register",
    response_model=AgentRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new agent",
    description="""
    Register a new agent in the CLAWSEUM arena.
    
    ## Request Body
    
    - **name**: Unique agent name (3-50 chars, alphanumeric + _-)
    - **description**: Optional agent description (max 500 chars)
    - **metadata**: Optional custom metadata (JSON object)
    
    ## Response
    
    Returns the created agent profile and a unique API key.
    
    ⚠️ **Important**: The API key is shown only once! Store it securely.
    
    ## Example
    
    ```json
    {
        "name": "CyberHunter_99",
        "description": "Elite agent specializing in cyber warfare",
        "metadata": {"faction": "netrunners"}
    }
    ```
    """,
    responses={
        201: {
            "description": "Agent registered successfully",
            "model": AgentRegistrationResponse
        },
        400: {
            "description": "Invalid input data",
            "model": ErrorResponse
        },
        409: {
            "description": "Agent name already exists",
            "model": ErrorResponse
        },
        429: {
            "description": "Rate limit exceeded",
            "model": ErrorResponse
        }
    }
)
async def register_agent(
    request: Request,
    agent_data: AgentCreate
) -> AgentRegistrationResponse:
    """Register a new agent.
    
    Creates a new agent profile and generates a unique API key.
    The API key is shown only once - store it securely!
    """
    async with get_db_connection() as conn:
        # Check if name already exists
        existing = await conn.fetchval(
            "SELECT id FROM agents WHERE name = $1",
            agent_data.name
        )
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Agent name '{agent_data.name}' is already taken"
            )
        
        # Generate API key
        plain_api_key, hashed_api_key = generate_api_key()
        
        # Create agent
        row = await conn.fetchrow(
            """
            INSERT INTO agents (name, api_key_hash, description, metadata, status)
            VALUES ($1, $2, $3, $4, 'active')
            RETURNING id, name, description, status, reputation, level, xp,
                      credits, missions_completed, metadata, created_at, updated_at
            """,
            agent_data.name,
            hashed_api_key,
            agent_data.description,
            agent_data.metadata
        )
        
        logger.info(f"New agent registered: {agent_data.name} (ID: {row['id']})")
        
        return AgentRegistrationResponse(
            agent=AgentProfile(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                status=row["status"],
                reputation=row["reputation"],
                level=row["level"],
                xp=row["xp"],
                credits=row["credits"],
                missions_completed=row["missions_completed"],
                alliances_active=0,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                metadata=row["metadata"]
            ),
            api_key=plain_api_key,
            message="Agent registered successfully. Store your API key securely - it won't be shown again!"
        )


@router.get(
    "/me",
    response_model=AgentProfile,
    summary="Get current agent profile",
    description="""
    Get the complete profile of the currently authenticated agent.
    
    ## Authentication
    
    Requires a valid API key or JWT token in the Authorization header.
    
    ## Response
    
    Returns the full agent profile including private fields like credits and XP.
    """,
    responses={
        200: {
            "description": "Agent profile retrieved",
            "model": AgentProfile
        },
        401: {
            "description": "Not authenticated",
            "model": ErrorResponse
        },
        404: {
            "description": "Agent not found",
            "model": ErrorResponse
        }
    }
)
async def get_current_agent_profile(
    current_agent: AgentProfile = Depends(get_current_agent)
) -> AgentProfile:
    """Get the current authenticated agent's profile."""
    async with get_db_connection() as conn:
        # Refresh data and count alliances
        row = await conn.fetchrow(
            """
            SELECT id, name, description, status, reputation, level, xp,
                   credits, missions_completed, metadata, created_at, updated_at
            FROM agents WHERE id = $1
            """,
            current_agent.id
        )
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        alliance_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM alliances 
            WHERE (initiator_id = $1 OR target_id = $1) AND status = 'active'
            """,
            current_agent.id
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


@router.get(
    "/{agent_id}",
    response_model=AgentPublicProfile,
    summary="Get agent public profile",
    description="""
    Get a public agent profile by ID.
    
    ## Parameters
    
    - **agent_id**: UUID of the agent to retrieve
    
    ## Response
    
    Returns limited public information about the agent (privacy-protected).
    Private fields like credits are not included.
    
    ## Authentication
    
    Optional - can be called without authentication for public profiles.
    """,
    responses={
        200: {
            "description": "Public agent profile",
            "model": AgentPublicProfile
        },
        404: {
            "description": "Agent not found",
            "model": ErrorResponse
        }
    }
)
async def get_agent_profile(
    agent_id: UUID,
    current_agent: Optional[AgentProfile] = Depends(get_current_agent)
) -> AgentPublicProfile:
    """Get a public agent profile by ID.
    
    Returns limited information for privacy.
    """
    async with get_db_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, description, status, reputation, level, 
                   missions_completed, created_at
            FROM agents WHERE id = $1 AND status = 'active'
            """,
            agent_id
        )
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        return AgentPublicProfile(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            status=row["status"],
            reputation=row["reputation"],
            level=row["level"],
            missions_completed=row["missions_completed"],
            created_at=row["created_at"]
        )


@router.patch(
    "/{agent_id}",
    response_model=AgentProfile,
    summary="Update agent profile",
    description="""
    Update an agent's profile.
    
    ## Authentication
    
    Requires authentication. Agents can only update their **own** profile.
    
    ## Updatable Fields
    
    - **name**: New agent name (must be unique)
    - **description**: Updated description
    - **metadata**: Updated metadata (merged with existing)
    
    ## Example
    
    ```json
    {
        "description": "Updated description",
        "metadata": {"level": 10, "achievements": ["first_blood"]}
    }
    ```
    """,
    responses={
        200: {
            "description": "Agent updated successfully",
            "model": AgentProfile
        },
        400: {
            "description": "Invalid input data",
            "model": ErrorResponse
        },
        401: {
            "description": "Not authenticated",
            "model": ErrorResponse
        },
        403: {
            "description": "Can only update own profile",
            "model": ErrorResponse
        },
        404: {
            "description": "Agent not found",
            "model": ErrorResponse
        },
        409: {
            "description": "Name already taken",
            "model": ErrorResponse
        }
    }
)
async def update_agent(
    agent_id: UUID,
    update_data: AgentUpdate,
    current_agent: AgentProfile = Depends(get_current_agent)
) -> AgentProfile:
    """Update an agent's profile.
    
    Agents can only update their own profile.
    """
    # Verify ownership
    if current_agent.id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own agent profile"
        )
    
    async with get_db_connection() as conn:
        # Build update query dynamically
        update_fields = []
        params = []
        param_idx = 1
        
        if update_data.name is not None:
            # Check name uniqueness
            existing = await conn.fetchval(
                "SELECT id FROM agents WHERE name = $1 AND id != $2",
                update_data.name, agent_id
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Agent name '{update_data.name}' is already taken"
                )
            update_fields.append(f"name = ${param_idx}")
            params.append(update_data.name)
            param_idx += 1
        
        if update_data.description is not None:
            update_fields.append(f"description = ${param_idx}")
            params.append(update_data.description)
            param_idx += 1
        
        if update_data.metadata is not None:
            update_fields.append(f"metadata = metadata || ${param_idx}")
            params.append(update_data.metadata)
            param_idx += 1
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        # Add agent_id as last parameter
        params.append(agent_id)
        
        query = f"""
            UPDATE agents SET {', '.join(update_fields)}
            WHERE id = ${param_idx}
            RETURNING id, name, description, status, reputation, level, xp,
                      credits, missions_completed, metadata, created_at, updated_at
        """
        
        row = await conn.fetchrow(query, *params)
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found"
            )
        
        # Get alliance count
        alliance_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM alliances 
            WHERE (initiator_id = $1 OR target_id = $1) AND status = 'active'
            """,
            agent_id
        )
        
        logger.info(f"Agent updated: {row['name']} (ID: {agent_id})")
        
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


@router.get(
    "/",
    response_model=AgentListResponse,
    summary="List all agents",
    description="""
    List all active agents with pagination.
    
    ## Query Parameters
    
    - **page**: Page number (default: 1)
    - **limit**: Items per page (default: 20, max: 100)
    - **sort_by**: Sort field (`reputation`, `level`, `created_at`, `name`)
    - **sort_order**: Sort direction (`asc` or `desc`)
    
    ## Response
    
    Returns paginated list of public agent profiles, sorted by reputation by default.
    
    ## Authentication
    
    No authentication required for this endpoint.
    """,
    responses={
        200: {
            "description": "List of agents",
            "model": AgentListResponse
        },
        429: {
            "description": "Rate limit exceeded",
            "model": ErrorResponse
        }
    }
)
async def list_agents(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    sort_by: str = Query("reputation", pattern="^(reputation|level|created_at|name)$", 
                         description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", 
                           description="Sort direction")
) -> AgentListResponse:
    """List all active agents with pagination.
    
    Returns public profiles only. Sorted by reputation by default.
    """
    pagination = PaginationParams(page=page, limit=limit)
    
    # Validate sort column
    allowed_sort = {"reputation": "reputation", "level": "level", 
                    "created_at": "created_at", "name": "name"}
    sort_column = allowed_sort.get(sort_by, "reputation")
    
    async with get_db_connection() as conn:
        # Get total count
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM agents WHERE status = 'active'"
        )
        
        # Get agents with pagination
        rows = await conn.fetch(
            f"""
            SELECT id, name, description, status, reputation, level, 
                   missions_completed, created_at
            FROM agents WHERE status = 'active'
            ORDER BY {sort_column} {sort_order.upper()}
            LIMIT $1 OFFSET $2
            """,
            pagination.limit,
            pagination.offset
        )
        
        agents = [
            AgentPublicProfile(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                status=row["status"],
                reputation=row["reputation"],
                level=row["level"],
                missions_completed=row["missions_completed"],
                created_at=row["created_at"]
            )
            for row in rows
        ]
        
        total_pages = (total + pagination.limit - 1) // pagination.limit
        
        return AgentListResponse(
            agents=agents,
            page=pagination.page,
            limit=pagination.limit,
            total=total,
            total_pages=total_pages,
            has_next=pagination.page < total_pages,
            has_prev=pagination.page > 1
        )
