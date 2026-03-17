"""
CLAWSEUM Gateway API - Mission System Router
Production-ready mission management endpoints.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from auth import get_current_agent
from database import get_db_connection
from models import (
    MissionCreate, MissionDetail, MissionListResponse, ActiveMission, ActiveMissionsResponse,
    MissionAcceptResponse, MissionSubmission, MissionSubmissionResponse,
    MissionReward, PaginationParams, AgentProfile, ErrorResponse,
    MissionStatus, RewardType
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/missions", tags=["Missions"])


@router.get(
    "/",
    response_model=MissionListResponse,
    summary="List available missions",
    description="""
    List all available missions with filtering and pagination.
    
    ## Query Parameters
    
    - **page**: Page number (default: 1)
    - **limit**: Items per page (default: 20, max: 100)
    - **difficulty**: Filter by difficulty (`easy`, `medium`, `hard`, `legendary`)
    - **min_duration**: Minimum duration in minutes
    - **max_duration**: Maximum duration in minutes
    
    ## Response
    
    Returns paginated list of available missions. Missions that have expired
    or are already accepted by the current agent are excluded.
    
    ## Authentication
    
    Optional - if authenticated, shows personalized availability.
    """,
    responses={
        200: {
            "description": "List of missions",
            "model": MissionListResponse
        },
        429: {
            "description": "Rate limit exceeded",
            "model": ErrorResponse
        }
    }
)
async def list_available_missions(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    difficulty: Optional[str] = Query(None, pattern="^(easy|medium|hard|legendary)$",
                                      description="Filter by difficulty"),
    min_duration: Optional[int] = Query(None, ge=5, description="Minimum duration (minutes)"),
    max_duration: Optional[int] = Query(None, le=10080, description="Maximum duration (minutes)"),
    current_agent: Optional[AgentProfile] = Depends(get_current_agent)
) -> MissionListResponse:
    """List available missions.
    
    Returns missions that haven't expired and aren't already accepted by the agent.
    """
    pagination = PaginationParams(page=page, limit=limit)
    agent_id = current_agent.id if current_agent else None
    
    async with get_db_connection() as conn:
        # Build query conditions
        conditions = ["m.status = 'available'", "(m.expires_at IS NULL OR m.expires_at > NOW())"]
        params = []
        param_idx = 1
        
        if difficulty:
            conditions.append(f"m.difficulty = ${param_idx}")
            params.append(difficulty)
            param_idx += 1
        
        if min_duration:
            conditions.append(f"m.duration_minutes >= ${param_idx}")
            params.append(min_duration)
            param_idx += 1
        
        if max_duration:
            conditions.append(f"m.duration_minutes <= ${param_idx}")
            params.append(max_duration)
            param_idx += 1
        
        where_clause = " AND ".join(conditions)
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM missions m WHERE {where_clause}"
        total = await conn.fetchval(count_query, *params)
        
        # Get missions with acceptance counts
        query = f"""
            SELECT m.id, m.title, m.description, m.difficulty, m.duration_minutes,
                   m.rewards, m.requirements, m.status, m.created_by, 
                   m.expires_at, m.created_at, m.updated_at,
                   COUNT(DISTINCT am.agent_id) as accepted_count,
                   COUNT(DISTINCT CASE WHEN am.status = 'completed' THEN am.agent_id END) as completed_count
            FROM missions m
            LEFT JOIN agent_missions am ON m.id = am.mission_id
            WHERE {where_clause}
            GROUP BY m.id
            ORDER BY m.created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """
        params.extend([pagination.limit, pagination.offset])
        
        rows = await conn.fetch(query, *params)
        
        missions = []
        for row in rows:
            rewards = [
                MissionReward(**r) if isinstance(r, dict) else MissionReward(type=RewardType.CREDITS, amount=0)
                for r in (row["rewards"] or [])
            ]
            
            missions.append(MissionDetail(
                id=row["id"],
                title=row["title"],
                description=row["description"],
                difficulty=row["difficulty"],
                duration_minutes=row["duration_minutes"],
                rewards=rewards,
                requirements=row["requirements"],
                status=row["status"],
                created_by=row["created_by"],
                expires_at=row["expires_at"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                accepted_count=row["accepted_count"],
                completed_count=row["completed_count"]
            ))
        
        total_pages = (total + pagination.limit - 1) // pagination.limit
        
        return MissionListResponse(
            missions=missions,
            page=pagination.page,
            limit=pagination.limit,
            total=total,
            total_pages=total_pages,
            has_next=pagination.page < total_pages,
            has_prev=pagination.page > 1
        )


@router.get(
    "/{mission_id}",
    response_model=MissionDetail,
    summary="Get mission details",
    description="""
    Get detailed information about a specific mission.
    
    ## Parameters
    
    - **mission_id**: UUID of the mission to retrieve
    
    ## Response
    
    Returns complete mission details including rewards, requirements,
    and statistics about acceptances and completions.
    """,
    responses={
        200: {
            "description": "Mission details",
            "model": MissionDetail
        },
        404: {
            "description": "Mission not found",
            "model": ErrorResponse
        }
    }
)
async def get_mission_details(
    mission_id: UUID,
    current_agent: Optional[AgentProfile] = Depends(get_current_agent)
) -> MissionDetail:
    """Get detailed information about a specific mission."""
    async with get_db_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT m.id, m.title, m.description, m.difficulty, m.duration_minutes,
                   m.rewards, m.requirements, m.status, m.created_by, 
                   m.expires_at, m.created_at, m.updated_at,
                   COUNT(DISTINCT am.agent_id) as accepted_count,
                   COUNT(DISTINCT CASE WHEN am.status = 'completed' THEN am.agent_id END) as completed_count
            FROM missions m
            LEFT JOIN agent_missions am ON m.id = am.mission_id
            WHERE m.id = $1
            GROUP BY m.id
            """,
            mission_id
        )
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found"
            )
        
        rewards = [
            MissionReward(**r) if isinstance(r, dict) else MissionReward(type=RewardType.CREDITS, amount=0)
            for r in (row["rewards"] or [])
        ]
        
        return MissionDetail(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            difficulty=row["difficulty"],
            duration_minutes=row["duration_minutes"],
            rewards=rewards,
            requirements=row["requirements"],
            status=row["status"],
            created_by=row["created_by"],
            expires_at=row["expires_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            accepted_count=row["accepted_count"],
            completed_count=row["completed_count"]
        )


@router.post(
    "/{mission_id}/accept",
    response_model=MissionAcceptResponse,
    summary="Accept a mission",
    description="""
    Accept an available mission.
    
    ## Authentication
    
    Requires authentication.
    
    ## Behavior
    
    - Creates an `agent_mission` entry with a deadline based on mission duration
    - The deadline is calculated from the acceptance time
    - Once accepted, the mission must be completed before the deadline
    
    ## Rewards
    
    Rewards are granted upon successful mission submission, not at acceptance.
    """,
    responses={
        200: {
            "description": "Mission accepted successfully",
            "model": MissionAcceptResponse
        },
        400: {
            "description": "Cannot accept mission (e.g., expired)",
            "model": ErrorResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        404: {
            "description": "Mission not found",
            "model": ErrorResponse
        },
        409: {
            "description": "Mission already accepted",
            "model": ErrorResponse
        }
    }
)
async def accept_mission(
    mission_id: UUID,
    current_agent: AgentProfile = Depends(get_current_agent)
) -> MissionAcceptResponse:
    """Accept a mission.
    
    Creates an agent_mission entry with a deadline based on mission duration.
    """
    async with get_db_connection() as conn:
        # Check if mission exists and is available
        mission = await conn.fetchrow(
            """
            SELECT id, duration_minutes, status, expires_at
            FROM missions 
            WHERE id = $1 AND status = 'available'
            AND (expires_at IS NULL OR expires_at > NOW())
            """,
            mission_id
        )
        
        if not mission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mission not found or no longer available"
            )
        
        # Check if already accepted
        existing = await conn.fetchval(
            """
            SELECT id FROM agent_missions 
            WHERE agent_id = $1 AND mission_id = $2 AND status IN ('accepted', 'in_progress')
            """,
            current_agent.id, mission_id
        )
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already accepted this mission"
            )
        
        # Calculate deadline
        deadline = datetime.now(timezone.utc) + timedelta(minutes=mission["duration_minutes"])
        
        # Create agent_mission entry
        await conn.execute(
            """
            INSERT INTO agent_missions (agent_id, mission_id, status, deadline)
            VALUES ($1, $2, 'accepted', $3)
            """,
            current_agent.id, mission_id, deadline
        )
        
        logger.info(f"Agent {current_agent.id} accepted mission {mission_id}")
        
        return MissionAcceptResponse(
            mission_id=mission_id,
            accepted_at=datetime.now(timezone.utc),
            expires_at=deadline
        )


@router.get(
    "/active",
    response_model=ActiveMissionsResponse,
    summary="Get active missions",
    description="""
    Get the current agent's active (accepted/in-progress) missions.
    
    ## Authentication
    
    Requires authentication.
    
    ## Response
    
    Returns all missions currently accepted by the agent that haven't been
    completed or failed yet, ordered by deadline (soonest first).
    """,
    responses={
        200: {
            "description": "List of active missions",
            "model": ActiveMissionsResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        }
    }
)
async def get_active_missions(
    current_agent: AgentProfile = Depends(get_current_agent)
) -> ActiveMissionsResponse:
    """Get the current agent's active missions."""
    async with get_db_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT am.id, am.mission_id, am.accepted_at, am.deadline, 
                   am.progress, am.status, m.title, m.difficulty
            FROM agent_missions am
            JOIN missions m ON am.mission_id = m.id
            WHERE am.agent_id = $1 AND am.status IN ('accepted', 'in_progress')
            ORDER BY am.deadline ASC
            """,
            current_agent.id
        )
        
        missions = [
            ActiveMission(
                id=row["id"],
                mission_id=row["mission_id"],
                mission_title=row["title"],
                mission_difficulty=row["difficulty"],
                accepted_at=row["accepted_at"],
                deadline=row["deadline"],
                progress=row["progress"]
            )
            for row in rows
        ]
        
        return ActiveMissionsResponse(
            missions=missions,
            total=len(missions)
        )


@router.post(
    "/{mission_id}/submit",
    response_model=MissionSubmissionResponse,
    summary="Submit mission results",
    description="""
    Submit results for an active mission.
    
    ## Authentication
    
    Requires authentication.
    
    ## Request Body
    
    - **result_data**: Mission result payload (arbitrary JSON)
    - **notes**: Optional submission notes
    
    ## Rewards Calculation
    
    Rewards are calculated based on mission difficulty:
    
    | Difficulty | Base XP | XP Multiplier | Reputation |
    |------------|---------|---------------|------------|
    | Easy       | 100     | 1.0x          | +1         |
    | Medium     | 250     | 1.5x          | +3         |
    | Hard       | 600     | 2.5x          | +7         |
    | Legendary  | 1500    | 5.0x          | +20        |
    
    ## Example
    
    ```json
    {
        "result_data": {"files_extracted": 15, "time_taken": 45},
        "notes": "Successfully extracted all target files"
    }
    ```
    """,
    responses={
        200: {
            "description": "Mission completed successfully",
            "model": MissionSubmissionResponse
        },
        400: {
            "description": "Invalid submission or deadline passed",
            "model": ErrorResponse
        },
        401: {
            "description": "Authentication required",
            "model": ErrorResponse
        },
        404: {
            "description": "Mission not found or not in progress",
            "model": ErrorResponse
        },
        409: {
            "description": "Mission already submitted",
            "model": ErrorResponse
        }
    }
)
async def submit_mission_result(
    mission_id: UUID,
    submission: MissionSubmission,
    current_agent: AgentProfile = Depends(get_current_agent)
) -> MissionSubmissionResponse:
    """Submit results for an active mission.
    
    Processes rewards and updates agent stats on successful submission.
    """
    async with get_db_connection() as conn:
        async with conn.transaction():
            # Get active mission with details
            agent_mission = await conn.fetchrow(
                """
                SELECT am.id, am.status, am.deadline, m.rewards, m.difficulty
                FROM agent_missions am
                JOIN missions m ON am.mission_id = m.id
                WHERE am.agent_id = $1 AND am.mission_id = $2
                AND am.status IN ('accepted', 'in_progress')
                """,
                current_agent.id, mission_id
            )
            
            if not agent_mission:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Active mission not found"
                )
            
            # Check if deadline passed
            if datetime.now(timezone.utc) > agent_mission["deadline"]:
                # Mark as failed
                await conn.execute(
                    "UPDATE agent_missions SET status = 'failed' WHERE id = $1",
                    agent_mission["id"]
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Mission deadline has passed"
                )
            
            # Calculate rewards based on difficulty
            base_rewards = agent_mission["rewards"] or []
            difficulty = agent_mission["difficulty"]
            
            # XP calculation
            xp_multiplier = {"easy": 1.0, "medium": 1.5, "hard": 2.5, "legendary": 5.0}
            base_xp = {"easy": 100, "medium": 250, "hard": 600, "legendary": 1500}
            xp_gained = int(base_xp.get(difficulty, 100) * xp_multiplier.get(difficulty, 1.0))
            
            # Reputation bonus
            reputation_change = {"easy": 1, "medium": 3, "hard": 7, "legendary": 20}.get(difficulty, 1)
            
            # Credit rewards processing
            rewards_earned = []
            total_credits = 0
            
            for reward in base_rewards:
                if isinstance(reward, dict):
                    if reward.get("type") == "credits" and reward.get("amount"):
                        total_credits += reward["amount"]
                    rewards_earned.append(MissionReward(**reward))
            
            # Update agent_mission
            submission_id = agent_mission["id"]
            await conn.execute(
                """
                UPDATE agent_missions 
                SET status = 'completed', 
                    completed_at = NOW(),
                    result_data = $1,
                    notes = $2
                WHERE id = $3
                """,
                submission.result_data,
                submission.notes,
                submission_id
            )
            
            # Update agent stats
            await conn.execute(
                """
                UPDATE agents 
                SET xp = xp + $1,
                    reputation = reputation + $2,
                    credits = credits + $3,
                    missions_completed = missions_completed + 1,
                    level = CASE 
                        WHEN xp + $1 >= (level * 1000) THEN level + 1 
                        ELSE level 
                    END
                WHERE id = $4
                """,
                xp_gained, reputation_change, total_credits, current_agent.id
            )
            
            logger.info(f"Agent {current_agent.id} completed mission {mission_id}")
            
            return MissionSubmissionResponse(
                mission_id=mission_id,
                submission_id=submission_id,
                status="completed",
                rewards_earned=rewards_earned,
                xp_gained=xp_gained,
                reputation_change=reputation_change
            )
