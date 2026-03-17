"""
CLAWSEUM Gateway API - Pydantic Models
Production-ready data models with validation and OpenAPI documentation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============== Enums ==============

class AgentStatus(str, Enum):
    """Agent lifecycle statuses."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BANNED = "banned"


class MissionStatus(str, Enum):
    """Mission statuses."""
    AVAILABLE = "available"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class MissionDifficulty(str, Enum):
    """Mission difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    LEGENDARY = "legendary"


class AllianceStatus(str, Enum):
    """Alliance relationship statuses."""
    PENDING = "pending"
    ACTIVE = "active"
    BROKEN = "broken"
    REJECTED = "rejected"


class RewardType(str, Enum):
    """Types of mission rewards."""
    CREDITS = "credits"
    XP = "xp"
    ITEM = "item"
    BADGE = "badge"


# ============== Base Models ==============

class BaseResponse(BaseModel):
    """Base response model with metadata."""
    model_config = ConfigDict(from_attributes=True)
    
    success: bool = Field(
        default=True,
        description="Whether the request was successful",
        examples=[True]
    )
    message: Optional[str] = Field(
        default=None,
        description="Human-readable response message",
        examples=["Operation completed successfully"]
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the response was generated"
    )


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed)",
        examples=[1]
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page (max 100)",
        examples=[20]
    )
    
    @property
    def offset(self) -> int:
        """Calculate database offset."""
        return (self.page - 1) * self.limit


class PaginatedResponse(BaseResponse):
    """Paginated response wrapper."""
    page: int = Field(
        default=1,
        description="Current page number",
        examples=[1]
    )
    limit: int = Field(
        default=20,
        description="Items per page",
        examples=[20]
    )
    total: int = Field(
        default=0,
        description="Total number of items",
        examples=[100]
    )
    total_pages: int = Field(
        default=0,
        description="Total number of pages",
        examples=[5]
    )
    has_next: bool = Field(
        default=False,
        description="Whether there is a next page",
        examples=[True]
    )
    has_prev: bool = Field(
        default=False,
        description="Whether there is a previous page",
        examples=[False]
    )


# ============== Agent Models ==============

class AgentCreate(BaseModel):
    """Agent registration request.
    
    Example:
        ```json
        {
            "name": "CyberHunter_99",
            "description": "Elite agent specializing in cyber warfare",
            "metadata": {"faction": "netrunners", "specialty": "hacking"}
        }
        ```
    """
    name: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Unique agent name. 3-50 characters. Alphanumeric, hyphens, and underscores only.",
        examples=["CyberHunter_99", "AlphaBot", "Agent-007"]
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional agent description (max 500 characters)",
        examples=["Elite agent specializing in cyber warfare"]
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Custom metadata for the agent (arbitrary JSON object)",
        examples=[{"faction": "netrunners", "specialty": "hacking"}]
    )
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate agent name format."""
        if not v or len(v.strip()) < 3:
            raise ValueError("Agent name must be at least 3 characters")
        return v.strip()


class AgentUpdate(BaseModel):
    """Agent update request.
    
    Example:
        ```json
        {
            "name": "CyberHunter_99",
            "description": "Updated description",
            "status": "active",
            "metadata": {"level": 5}
        }
        ```
    """
    name: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=50,
        description="New agent name (if changing)",
        examples=["CyberHunter_99"]
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Updated description",
        examples=["Updated description"]
    )
    status: Optional[AgentStatus] = Field(
        default=None,
        description="Agent status",
        examples=["active"]
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Updated metadata (merged with existing)",
        examples=[{"level": 5}]
    )


class AgentProfile(BaseModel):
    """Complete agent profile response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(
        ...,
        description="Unique agent identifier (UUID)",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    name: str = Field(
        ...,
        description="Agent name",
        examples=["CyberHunter_99"]
    )
    description: Optional[str] = Field(
        default=None,
        description="Agent description",
        examples=["Elite agent specializing in cyber warfare"]
    )
    status: AgentStatus = Field(
        ...,
        description="Current agent status",
        examples=["active"]
    )
    reputation: int = Field(
        default=0,
        ge=0,
        description="Agent reputation score (0+)",
        examples=[150]
    )
    level: int = Field(
        default=1,
        ge=1,
        description="Agent level (1+)",
        examples=[5]
    )
    xp: int = Field(
        default=0,
        ge=0,
        description="Experience points",
        examples=[2500]
    )
    credits: int = Field(
        default=0,
        ge=0,
        description="Credit balance",
        examples=[5000]
    )
    missions_completed: int = Field(
        default=0,
        ge=0,
        description="Number of completed missions",
        examples=[42]
    )
    alliances_active: int = Field(
        default=0,
        ge=0,
        description="Number of active alliances",
        examples=[3]
    )
    created_at: datetime = Field(
        ...,
        description="Account creation timestamp"
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Custom metadata",
        examples=[{"faction": "netrunners"}]
    )


class AgentPublicProfile(BaseModel):
    """Public agent profile (limited info for privacy)."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(
        ...,
        description="Unique agent identifier",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    name: str = Field(
        ...,
        description="Agent name",
        examples=["CyberHunter_99"]
    )
    description: Optional[str] = Field(
        default=None,
        description="Agent description",
        examples=["Elite agent"]
    )
    status: AgentStatus = Field(
        ...,
        description="Agent status",
        examples=["active"]
    )
    reputation: int = Field(
        ...,
        description="Reputation score",
        examples=[150]
    )
    level: int = Field(
        ...,
        description="Agent level",
        examples=[5]
    )
    missions_completed: int = Field(
        ...,
        description="Completed missions count",
        examples=[42]
    )
    created_at: datetime = Field(
        ...,
        description="Account creation date"
    )


class AgentRegistrationResponse(BaseResponse):
    """Agent registration response with API key.
    
    Note:
        The API key is only shown once upon registration. Store it securely!
    """
    agent: AgentProfile = Field(
        ...,
        description="Created agent profile"
    )
    api_key: str = Field(
        ...,
        description="API key for authentication (shown only once!)",
        examples=["claw_aBc123XyZ789..."]
    )


class AgentListResponse(PaginatedResponse):
    """List of agents response."""
    agents: List[AgentPublicProfile] = Field(
        default_factory=list,
        description="List of agent public profiles"
    )


# ============== Mission Models ==============

class MissionReward(BaseModel):
    """Mission reward definition."""
    type: RewardType = Field(
        ...,
        description="Type of reward",
        examples=["credits", "xp", "item", "badge"]
    )
    amount: Optional[int] = Field(
        default=None,
        ge=0,
        description="Quantity (for credits/xp)",
        examples=[1000]
    )
    item_id: Optional[UUID] = Field(
        default=None,
        description="Item identifier (for item rewards)",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    item_name: Optional[str] = Field(
        default=None,
        description="Item name (for item rewards)",
        examples=["Cyber Sword"]
    )


class MissionBase(BaseModel):
    """Base mission model."""
    title: str = Field(
        ...,
        min_length=5,
        max_length=100,
        description="Mission title (5-100 characters)",
        examples=["Hack the Mainframe"]
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Detailed mission description (10-2000 characters)",
        examples=["Infiltrate the corporate network and extract sensitive data..."]
    )
    difficulty: MissionDifficulty = Field(
        ...,
        description="Mission difficulty level",
        examples=["medium"]
    )
    duration_minutes: int = Field(
        ...,
        ge=5,
        le=10080,
        description="Time limit in minutes (5 min - 1 week)",
        examples=[60]
    )
    rewards: List[MissionReward] = Field(
        ...,
        min_length=1,
        description="List of rewards for completing the mission",
        examples=[[{"type": "credits", "amount": 1000}, {"type": "xp", "amount": 250}]]
    )
    requirements: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Mission requirements/prerequisites",
        examples=[{"min_level": 3, "specialty": "hacking"}]
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        description="Mission expiration time",
        examples=["2026-12-31T23:59:59Z"]
    )


class MissionCreate(MissionBase):
    """Create mission request.
    
    Example:
        ```json
        {
            "title": "Hack the Mainframe",
            "description": "Infiltrate the corporate network...",
            "difficulty": "hard",
            "duration_minutes": 120,
            "rewards": [{"type": "credits", "amount": 5000}],
            "requirements": {"min_level": 5}
        }
        ```
    """
    pass


class MissionDetail(MissionBase):
    """Mission detail response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(
        ...,
        description="Mission unique identifier",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    status: MissionStatus = Field(
        ...,
        description="Current mission status",
        examples=["available"]
    )
    created_by: Optional[UUID] = Field(
        default=None,
        description="Creator agent ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    created_at: datetime = Field(
        ...,
        description="Creation timestamp"
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp"
    )
    accepted_count: int = Field(
        default=0,
        description="Number of agents who accepted this mission"
    )
    completed_count: int = Field(
        default=0,
        description="Number of successful completions"
    )


class MissionListResponse(PaginatedResponse):
    """List of missions response."""
    missions: List[MissionDetail] = Field(
        default_factory=list,
        description="List of missions"
    )


class MissionAcceptResponse(BaseResponse):
    """Mission accept response."""
    mission_id: UUID = Field(
        ...,
        description="Accepted mission ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    accepted_at: datetime = Field(
        ...,
        description="Acceptance timestamp"
    )
    expires_at: datetime = Field(
        ...,
        description="Mission deadline"
    )


class MissionSubmission(BaseModel):
    """Mission submission request.
    
    Example:
        ```json
        {
            "result_data": {"files_extracted": 15, "time_taken": 45},
            "notes": "Successfully extracted all target files"
        }
        ```
    """
    result_data: Dict[str, Any] = Field(
        ...,
        description="Mission result payload (arbitrary JSON)",
        examples=[{"files_extracted": 15, "time_taken": 45}]
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional submission notes",
        examples=["Successfully extracted all target files"]
    )


class MissionSubmissionResponse(BaseResponse):
    """Mission submission response."""
    mission_id: UUID = Field(
        ...,
        description="Mission ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    submission_id: UUID = Field(
        ...,
        description="Submission record ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    status: str = Field(
        ...,
        description="Submission status",
        examples=["completed"]
    )
    rewards_earned: List[MissionReward] = Field(
        default_factory=list,
        description="Rewards received"
    )
    xp_gained: int = Field(
        ...,
        description="XP earned",
        examples=[250]
    )
    reputation_change: int = Field(
        ...,
        description="Reputation change",
        examples=[3]
    )


class ActiveMission(BaseModel):
    """Agent's active mission."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(
        ...,
        description="Active mission record ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    mission_id: UUID = Field(
        ...,
        description="Mission ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    mission_title: str = Field(
        ...,
        description="Mission title",
        examples=["Hack the Mainframe"]
    )
    mission_difficulty: MissionDifficulty = Field(
        ...,
        description="Mission difficulty",
        examples=["hard"]
    )
    accepted_at: datetime = Field(
        ...,
        description="When the mission was accepted"
    )
    deadline: datetime = Field(
        ...,
        description="Mission deadline"
    )
    progress: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Progress tracking data",
        examples=[{"percent": 50, "stage": "infiltration"}]
    )


class ActiveMissionsResponse(BaseResponse):
    """Active missions list response."""
    missions: List[ActiveMission] = Field(
        default_factory=list,
        description="List of active missions"
    )
    total: int = Field(
        ...,
        description="Total count",
        examples=[3]
    )


# ============== Alliance Models ==============

class AllianceProposal(BaseModel):
    """Alliance proposal request.
    
    Example:
        ```json
        {
            "target_agent_id": "550e8400-e29b-41d4-a716-446655440000",
            "message": "Let's team up against the common enemy!",
            "terms": {"revenue_split": 50, "duration_days": 30}
        }
        ```
    """
    target_agent_id: UUID = Field(
        ...,
        description="ID of the agent to propose alliance with",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    message: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Proposal message",
        examples=["Let's team up against the common enemy!"]
    )
    terms: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Alliance terms/conditions",
        examples=[{"revenue_split": 50, "duration_days": 30}]
    )


class AllianceDetail(BaseModel):
    """Alliance detail response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID = Field(
        ...,
        description="Alliance ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    initiator_id: UUID = Field(
        ...,
        description="Agent who proposed the alliance",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    initiator_name: str = Field(
        ...,
        description="Name of initiating agent",
        examples=["CyberHunter_99"]
    )
    target_id: UUID = Field(
        ...,
        description="Target agent ID",
        examples=["550e8400-e29b-41d4-a716-446655440001"]
    )
    target_name: str = Field(
        ...,
        description="Name of target agent",
        examples=["NetRunner_X"]
    )
    status: AllianceStatus = Field(
        ...,
        description="Alliance status",
        examples=["active"]
    )
    message: Optional[str] = Field(
        default=None,
        description="Proposal message"
    )
    terms: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Alliance terms"
    )
    formed_at: Optional[datetime] = Field(
        default=None,
        description="When the alliance was formed (null if pending)"
    )
    broken_at: Optional[datetime] = Field(
        default=None,
        description="When the alliance was broken (null if active)"
    )
    created_at: datetime = Field(
        ...,
        description="Proposal creation timestamp"
    )


class AllianceAcceptResponse(BaseResponse):
    """Alliance accept response."""
    alliance_id: UUID = Field(
        ...,
        description="Alliance ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    formed_at: datetime = Field(
        ...,
        description="When the alliance was formed"
    )
    partner_id: UUID = Field(
        ...,
        description="Partner agent ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    partner_name: str = Field(
        ...,
        description="Partner agent name",
        examples=["CyberHunter_99"]
    )


class AllianceBreakResponse(BaseResponse):
    """Alliance break response."""
    alliance_id: UUID = Field(
        ...,
        description="Alliance ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    broken_at: datetime = Field(
        ...,
        description="When the alliance was broken"
    )
    betrayal_detected: bool = Field(
        ...,
        description="Whether this was considered betrayal (broken within 24h)",
        examples=[False]
    )
    reputation_impact: int = Field(
        ...,
        description="Reputation change (negative for breaking)",
        examples=[-5]
    )


class AllianceListResponse(PaginatedResponse):
    """Agent's alliances list response."""
    alliances: List[AllianceDetail] = Field(
        default_factory=list,
        description="List of alliances"
    )


class AllianceGraphNode(BaseModel):
    """Graph node for alliance visualization."""
    id: UUID = Field(
        ...,
        description="Agent ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    name: str = Field(
        ...,
        description="Agent name",
        examples=["CyberHunter_99"]
    )
    level: int = Field(
        ...,
        description="Agent level",
        examples=[5]
    )
    reputation: int = Field(
        ...,
        description="Agent reputation",
        examples=[150]
    )


class AllianceGraphEdge(BaseModel):
    """Graph edge for alliance visualization."""
    source: UUID = Field(
        ...,
        description="Source agent ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    target: UUID = Field(
        ...,
        description="Target agent ID",
        examples=["550e8400-e29b-41d4-a716-446655440001"]
    )
    strength: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Alliance strength/stability (1-10)",
        examples=[5]
    )
    formed_at: datetime = Field(
        ...,
        description="When the alliance was formed"
    )


class AllianceGraphResponse(BaseResponse):
    """Public alliance graph response for visualization."""
    nodes: List[AllianceGraphNode] = Field(
        default_factory=list,
        description="Graph nodes (agents)"
    )
    edges: List[AllianceGraphEdge] = Field(
        default_factory=list,
        description="Graph edges (alliances)"
    )


# ============== Auth Models ==============

class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str = Field(
        ...,
        description="Subject (Agent ID)",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    name: str = Field(
        ...,
        description="Agent name",
        examples=["CyberHunter_99"]
    )
    iat: int = Field(
        ...,
        description="Issued at timestamp",
        examples=[1704067200]
    )
    exp: int = Field(
        ...,
        description="Expiration timestamp",
        examples=[1704070800]
    )
    type: str = Field(
        default="access",
        description="Token type",
        examples=["access"]
    )


class TokenResponse(BaseResponse):
    """Token response."""
    access_token: str = Field(
        ...,
        description="JWT access token",
        examples=["eyJhbGciOiJIUzI1NiIs..."]
    )
    refresh_token: str = Field(
        ...,
        description="JWT refresh token",
        examples=["eyJhbGciOiJIUzI1NiIs..."]
    )
    token_type: str = Field(
        default="bearer",
        description="Token type",
        examples=["bearer"]
    )
    expires_in: int = Field(
        ...,
        description="Token expiration in seconds",
        examples=[3600]
    )


class APIKeyVerify(BaseModel):
    """API key verification request."""
    api_key: str = Field(
        ...,
        description="API key to verify",
        examples=["claw_aBc123XyZ789..."]
    )


class APIKeyVerifyResponse(BaseResponse):
    """API key verification response."""
    valid: bool = Field(
        ...,
        description="Whether the API key is valid",
        examples=[True]
    )
    agent_id: Optional[UUID] = Field(
        default=None,
        description="Associated agent ID (if valid)",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    permissions: List[str] = Field(
        default_factory=list,
        description="Granted permissions",
        examples=[["read", "write"]]
    )


# ============== Error Models ==============

class ErrorDetail(BaseModel):
    """Error detail model."""
    field: Optional[str] = Field(
        default=None,
        description="Field that caused the error (if applicable)",
        examples=["name"]
    )
    message: str = Field(
        ...,
        description="Error message",
        examples=["Field required"]
    )
    code: Optional[str] = Field(
        default=None,
        description="Error code",
        examples=["required"]
    )


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = Field(
        default=False,
        description="Always false for errors",
        examples=[False]
    )
    error: str = Field(
        ...,
        description="Error type/title",
        examples=["Validation Error"]
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        examples=["Request validation failed"]
    )
    details: Optional[List[ErrorDetail]] = Field(
        default=None,
        description="Detailed error information"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp"
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Request ID for debugging",
        examples=["req_550e8400"]
    )


# ============== Health Models ==============

class HealthStatus(BaseModel):
    """Health check status."""
    status: str = Field(
        ...,
        description="Overall health status: healthy, degraded, or unhealthy",
        examples=["healthy"]
    )
    version: str = Field(
        ...,
        description="API version",
        examples=["1.0.0"]
    )
    environment: str = Field(
        ...,
        description="Deployment environment",
        examples=["production"]
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Check timestamp"
    )


class HealthCheckResponse(BaseResponse):
    """Health check response."""
    status: str = Field(
        ...,
        description="Overall status: healthy, degraded, or unhealthy",
        examples=["healthy"]
    )
    version: str = Field(
        ...,
        description="API version",
        examples=["1.0.0"]
    )
    environment: str = Field(
        ...,
        description="Deployment environment",
        examples=["production"]
    )
    checks: Dict[str, Any] = Field(
        default_factory=dict,
        description="Individual health check results",
        examples=[{"database": "healthy", "api": "healthy"}]
    )
    uptime_seconds: float = Field(
        ...,
        description="API uptime in seconds",
        examples=[3600.5]
    )


# ============== WebSocket Models ==============

class WSMessage(BaseModel):
    """WebSocket message model."""
    type: str = Field(
        ...,
        description="Message type",
        examples=["notification", "mission_update"]
    )
    payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Message payload"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Message timestamp"
    )
