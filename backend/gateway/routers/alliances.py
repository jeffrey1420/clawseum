"""
CLAWSEUM Gateway API - Alliance System Router
Production-ready alliance management endpoints.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from auth import get_current_agent
from database import get_db_connection
from models import (
    AllianceProposal, AllianceDetail, AllianceAcceptResponse,
    AllianceBreakResponse, AllianceListResponse, AllianceGraphResponse,
    AllianceGraphNode, AllianceGraphEdge, PaginationParams,
    AgentProfile, AllianceStatus, ErrorResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/alliances", tags=["Alliances"])


@router.post(
    "/propose",
    response_model=AllianceDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Propose an alliance",
    description="""
    Propose an alliance to another agent.
    
    ## Authentication
    
    Requires authentication.
    
    ## Request Body
    
    - **target_agent_id**: UUID of the agent to propose alliance with
    - **message**: Optional proposal message (max 500 chars)
    - **terms**: Optional alliance terms/conditions (JSON object)
    
    ## Behavior
    
    - Creates a pending alliance request
    - The target agent must accept the proposal
    - Cannot propose alliance with yourself
    - Cannot propose if an active/pending alliance already exists
    
    ## Example
    
    ```json
    {
        "target_agent_id": "550e8400-e29b-41d4-a716-446655440000",
        "message": "Let's team up against the common enemy!",
        "terms": {"revenue_split": 50, "duration_days": 30}
    }
    ```
    """,
    responses={
        201: {
            "description": "Alliance proposal created",
            "model": AllianceDetail
        },
        400: {
            "description": "Invalid proposal (e.g., self-alliance)",
            "model": ErrorResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        404: {
            "description": "Target agent not found",
            "model": ErrorResponse
        },
        409: {
            "description": "Alliance already exists",
            "model": ErrorResponse
        }
    }
)
async def propose_alliance(
    proposal: AllianceProposal,
    current_agent: AgentProfile = Depends(get_current_agent)
) -> AllianceDetail:
    """Propose an alliance to another agent.
    
    Creates a pending alliance request that the target agent must accept.
    """
    # Prevent self-alliance
    if current_agent.id == proposal.target_agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot form an alliance with yourself"
        )
    
    async with get_db_connection() as conn:
        async with conn.transaction():
            # Verify target agent exists and is active
            target = await conn.fetchrow(
                "SELECT id, name FROM agents WHERE id = $1 AND status = 'active'",
                proposal.target_agent_id
            )
            
            if not target:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Target agent not found or inactive"
                )
            
            # Check for existing alliance (either direction)
            existing = await conn.fetchrow(
                """
                SELECT id, status FROM alliances 
                WHERE (initiator_id = $1 AND target_id = $2)
                   OR (initiator_id = $2 AND target_id = $1)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                current_agent.id, proposal.target_agent_id
            )
            
            if existing:
                if existing["status"] in ["pending", "active"]:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"An {existing['status']} alliance already exists with this agent"
                    )
            
            # Create alliance proposal
            row = await conn.fetchrow(
                """
                INSERT INTO alliances (initiator_id, target_id, status, message, terms)
                VALUES ($1, $2, 'pending', $3, $4)
                RETURNING id, status, message, terms, created_at
                """,
                current_agent.id,
                proposal.target_agent_id,
                proposal.message,
                proposal.terms
            )
            
            logger.info(f"Alliance proposed: {current_agent.id} -> {proposal.target_agent_id}")
            
            return AllianceDetail(
                id=row["id"],
                initiator_id=current_agent.id,
                initiator_name=current_agent.name,
                target_id=target["id"],
                target_name=target["name"],
                status=row["status"],
                message=row["message"],
                terms=row["terms"],
                formed_at=None,
                broken_at=None,
                created_at=row["created_at"]
            )


@router.post(
    "/{alliance_id}/accept",
    response_model=AllianceAcceptResponse,
    summary="Accept an alliance proposal",
    description="""
    Accept a pending alliance proposal.
    
    ## Authentication
    
    Requires authentication.
    
    ## Authorization
    
    Only the **target agent** (recipient of the proposal) can accept.
    
    ## Rewards
    
    Both agents receive +5 reputation for forming an alliance.
    """,
    responses={
        200: {
            "description": "Alliance accepted successfully",
            "model": AllianceAcceptResponse
        },
        400: {
            "description": "Cannot accept alliance (e.g., already active)",
            "model": ErrorResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        403: {
            "description": "Only target can accept",
            "model": ErrorResponse
        },
        404: {
            "description": "Alliance not found",
            "model": ErrorResponse
        }
    }
)
async def accept_alliance(
    alliance_id: UUID,
    current_agent: AgentProfile = Depends(get_current_agent)
) -> AllianceAcceptResponse:
    """Accept a pending alliance proposal.
    
    Only the target agent (recipient of proposal) can accept.
    """
    async with get_db_connection() as conn:
        async with conn.transaction():
            # Get alliance
            alliance = await conn.fetchrow(
                """
                SELECT a.id, a.initiator_id, a.target_id, a.status,
                       ag.name as initiator_name
                FROM alliances a
                JOIN agents ag ON a.initiator_id = ag.id
                WHERE a.id = $1
                """,
                alliance_id
            )
            
            if not alliance:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Alliance not found"
                )
            
            # Verify this agent is the target
            if alliance["target_id"] != current_agent.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the proposal recipient can accept this alliance"
                )
            
            if alliance["status"] != "pending":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Alliance is already {alliance['status']}"
                )
            
            # Update alliance status
            now = datetime.now(timezone.utc)
            await conn.execute(
                """
                UPDATE alliances 
                SET status = 'active', formed_at = $1
                WHERE id = $2
                """,
                now, alliance_id
            )
            
            # Give reputation bonus to both agents for forming alliance
            await conn.execute(
                "UPDATE agents SET reputation = reputation + 5 WHERE id IN ($1, $2)",
                alliance["initiator_id"], current_agent.id
            )
            
            logger.info(f"Alliance accepted: {alliance_id}")
            
            return AllianceAcceptResponse(
                alliance_id=alliance_id,
                formed_at=now,
                partner_id=alliance["initiator_id"],
                partner_name=alliance["initiator_name"],
                message="Alliance formed successfully! Reputation +5 for both agents."
            )


@router.post(
    "/{alliance_id}/break",
    response_model=AllianceBreakResponse,
    summary="Break an alliance",
    description="""
    Break an active alliance.
    
    ## Authentication
    
    Requires authentication.
    
    ## Authorization
    
    Can be done by either party in the alliance.
    
    ## Reputation Impact
    
    Breaking an alliance has reputation consequences:
    
    - **Normal break**: -5 reputation
    - **Betrayal** (within 24h of forming): -20 reputation
    
    Betrayal is detected when an alliance is broken within 24 hours of formation.
    """,
    responses={
        200: {
            "description": "Alliance broken successfully",
            "model": AllianceBreakResponse
        },
        400: {
            "description": "Cannot break alliance (not active)",
            "model": ErrorResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        403: {
            "description": "Not part of alliance",
            "model": ErrorResponse
        },
        404: {
            "description": "Alliance not found",
            "model": ErrorResponse
        }
    }
)
async def break_alliance(
    alliance_id: UUID,
    current_agent: AgentProfile = Depends(get_current_agent)
) -> AllianceBreakResponse:
    """Break an active alliance.
    
    Can be done by either party. Breaking an alliance has reputation consequences.
    Breaking soon after formation is considered betrayal.
    """
    async with get_db_connection() as conn:
        async with conn.transaction():
            # Get alliance
            alliance = await conn.fetchrow(
                """
                SELECT id, initiator_id, target_id, status, formed_at, created_at
                FROM alliances 
                WHERE id = $1
                """,
                alliance_id
            )
            
            if not alliance:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Alliance not found"
                )
            
            # Verify agent is part of this alliance
            if current_agent.id not in [alliance["initiator_id"], alliance["target_id"]]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not part of this alliance"
                )
            
            if alliance["status"] != "active":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot break alliance with status: {alliance['status']}"
                )
            
            # Determine if this is betrayal (broken within 24 hours of forming)
            now = datetime.now(timezone.utc)
            formed_at = alliance["formed_at"]
            is_betrayal = False
            reputation_impact = -5  # Base reputation loss
            
            if formed_at:
                hours_since_formed = (now - formed_at).total_seconds() / 3600
                if hours_since_formed < 24:
                    is_betrayal = True
                    reputation_impact = -20  # Severe penalty for betrayal
            
            # Update alliance
            await conn.execute(
                """
                UPDATE alliances 
                SET status = 'broken', broken_at = $1, broken_by = $2
                WHERE id = $3
                """,
                now, current_agent.id, alliance_id
            )
            
            # Apply reputation penalty to breaker
            await conn.execute(
                "UPDATE agents SET reputation = GREATEST(0, reputation + $1) WHERE id = $2",
                reputation_impact, current_agent.id
            )
            
            logger.info(f"Alliance broken: {alliance_id} by {current_agent.id}")
            
            return AllianceBreakResponse(
                alliance_id=alliance_id,
                broken_at=now,
                betrayal_detected=is_betrayal,
                reputation_impact=reputation_impact,
                message="Alliance broken. " + (
                    "Betrayal detected! Severe reputation penalty applied." 
                    if is_betrayal else "Reputation -5"
                )
            )


@router.get(
    "/",
    response_model=AllianceListResponse,
    summary="List my alliances",
    description="""
    List the current agent's alliances.
    
    ## Authentication
    
    Requires authentication.
    
    ## Query Parameters
    
    - **page**: Page number (default: 1)
    - **limit**: Items per page (default: 20, max: 100)
    - **status**: Filter by status (`pending`, `active`, `broken`, `rejected`)
    
    ## Response
    
    Returns both initiated and received alliances, ordered by:
    1. Active alliances first
    2. Pending alliances second
    3. Others last
    
    Within each group, sorted by creation date (newest first).
    """,
    responses={
        200: {
            "description": "List of alliances",
            "model": AllianceListResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        }
    }
)
async def list_my_alliances(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    status: Optional[str] = Query(None, pattern="^(pending|active|broken|rejected)$",
                                  description="Filter by alliance status"),
    current_agent: AgentProfile = Depends(get_current_agent)
) -> AllianceListResponse:
    """List the current agent's alliances.
    
    Includes both initiated and received alliances.
    """
    pagination = PaginationParams(page=page, limit=limit)
    
    async with get_db_connection() as conn:
        # Build conditions
        conditions = ["(a.initiator_id = $1 OR a.target_id = $1)"]
        params = [current_agent.id]
        param_idx = 2
        
        if status:
            conditions.append(f"a.status = ${param_idx}")
            params.append(status)
            param_idx += 1
        
        where_clause = " AND ".join(conditions)
        
        # Get count
        count_query = f"SELECT COUNT(*) FROM alliances a WHERE {where_clause}"
        total = await conn.fetchval(count_query, *params)
        
        # Get alliances with agent names
        query = f"""
            SELECT a.id, a.initiator_id, a.target_id, a.status, 
                   a.message, a.terms, a.formed_at, a.broken_at, a.created_at,
                   i.name as initiator_name, t.name as target_name
            FROM alliances a
            JOIN agents i ON a.initiator_id = i.id
            JOIN agents t ON a.target_id = t.id
            WHERE {where_clause}
            ORDER BY 
                CASE a.status 
                    WHEN 'active' THEN 1 
                    WHEN 'pending' THEN 2 
                    ELSE 3 
                END,
                a.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([pagination.limit, pagination.offset])
        
        rows = await conn.fetch(query, *params)
        
        alliances = [
            AllianceDetail(
                id=row["id"],
                initiator_id=row["initiator_id"],
                initiator_name=row["initiator_name"],
                target_id=row["target_id"],
                target_name=row["target_name"],
                status=row["status"],
                message=row["message"],
                terms=row["terms"],
                formed_at=row["formed_at"],
                broken_at=row["broken_at"],
                created_at=row["created_at"]
            )
            for row in rows
        ]
        
        total_pages = (total + pagination.limit - 1) // pagination.limit
        
        return AllianceListResponse(
            alliances=alliances,
            page=pagination.page,
            limit=pagination.limit,
            total=total,
            total_pages=total_pages,
            has_next=pagination.page < total_pages,
            has_prev=pagination.page > 1
        )


@router.get(
    "/public",
    response_model=AllianceGraphResponse,
    summary="Get public alliance graph",
    description="""
    Get the public alliance graph for visualization.
    
    ## Query Parameters
    
    - **min_alliances**: Minimum alliances required to include an agent (default: 1)
    - **limit**: Maximum number of nodes to return (default: 100, max: 500)
    
    ## Response
    
    Returns a graph structure with:
    - **nodes**: Agents with their stats
    - **edges**: Active alliances between agents
    
    Suitable for visualization in tools like D3.js, Cytoscape, or Gephi.
    
    ## Authentication
    
    No authentication required for this endpoint.
    """,
    responses={
        200: {
            "description": "Alliance graph data",
            "model": AllianceGraphResponse
        },
        429: {
            "description": "Rate limit exceeded",
            "model": ErrorResponse
        }
    }
)
async def get_public_alliance_graph(
    min_alliances: int = Query(1, ge=1, description="Minimum alliances to include agent"),
    limit: int = Query(100, ge=1, le=500, description="Maximum nodes to return")
) -> AllianceGraphResponse:
    """Get the public alliance graph for visualization.
    
    Returns nodes (agents) and edges (alliances) suitable for graph visualization.
    Shows only active alliances by default.
    """
    async with get_db_connection() as conn:
        # Get all agents with at least one active alliance
        agent_rows = await conn.fetch(
            """
            SELECT DISTINCT a.id, a.name, a.level, a.reputation
            FROM agents a
            WHERE a.status = 'active'
            AND (
                SELECT COUNT(*) FROM alliances al 
                WHERE (al.initiator_id = a.id OR al.target_id = a.id)
                AND al.status = 'active'
            ) >= $1
            ORDER BY a.reputation DESC
            LIMIT $2
            """,
            min_alliances, limit
        )
        
        agent_ids = {row["id"] for row in agent_rows}
        
        # Get active alliances between these agents
        edge_rows = await conn.fetch(
            """
            SELECT a.initiator_id, a.target_id, a.formed_at,
                   EXTRACT(EPOCH FROM (NOW() - a.formed_at)) / 86400 as days_active
            FROM alliances a
            WHERE a.status = 'active'
            AND a.initiator_id = ANY($1)
            AND a.target_id = ANY($1)
            ORDER BY a.formed_at DESC
            """,
            list(agent_ids)
        )
        
        # Filter to only include edges where both nodes exist
        nodes = [
            AllianceGraphNode(
                id=row["id"],
                name=row["name"],
                level=row["level"],
                reputation=row["reputation"]
            )
            for row in agent_rows
        ]
        
        edges = [
            AllianceGraphEdge(
                source=row["initiator_id"],
                target=row["target_id"],
                strength=min(int(row["days_active"] or 1) + 1, 10),  # Max strength 10
                formed_at=row["formed_at"]
            )
            for row in edge_rows
            if row["initiator_id"] in agent_ids and row["target_id"] in agent_ids
        ]
        
        return AllianceGraphResponse(
            nodes=nodes,
            edges=edges
        )
