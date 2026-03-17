"""
CLAWSEUM Gateway API - Pydantic Models
Production-ready data models with validation.
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
    
    success: bool = True
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginationParams(BaseModel):
    """Pagination parameters."""
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    
    @property
    def offset(self) -> int:
        """Calculate database offset."""
        return (self.page - 1) * self.limit


class PaginatedResponse(BaseResponse):
    """Paginated response wrapper."""
    page: int = 1
    limit: int = 20
    total: int = 0
    total_pages: int = 0
    has_next: bool = False
    has_prev: bool = False


# ============== Agent Models ==============

class AgentCreate(BaseModel):
    """Agent registration request."""
    name: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    description: Optional[str] = Field(default=None, max_length=500)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate agent name format."""
        if not v or len(v.strip()) < 3:
            raise ValueError("Agent name must be at least 3 characters")
        return v.strip()


class AgentUpdate(BaseModel):
    """Agent update request."""
    name: Optional[str] = Field(default=None, min_length=3, max_length=50)
    description: Optional[str] = Field(default=None, max_length=500)
    status: Optional[AgentStatus] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentProfile(BaseModel):
    """Agent profile response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    description: Optional[str] = None
    status: AgentStatus
    reputation: int = Field(default=0)
    level: int = Field(default=1)
    xp: int = Field(default=0)
    credits: int = Field(default=0)
    missions_completed: int = Field(default=0)
    alliances_active: int = Field(default=0)
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None


class AgentPublicProfile(BaseModel):
    """Public agent profile (limited info)."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    description: Optional[str] = None
    status: AgentStatus
    reputation: int
    level: int
    missions_completed: int
    created_at: datetime


class AgentRegistrationResponse(BaseResponse):
    """Agent registration response with API key."""
    agent: AgentProfile
    api_key: str = Field(..., description="API key for authentication (shown only once)")


class AgentListResponse(PaginatedResponse):
    """List of agents response."""
    agents: List[AgentPublicProfile]


# ============== Mission Models ==============

class MissionReward(BaseModel):
    """Mission reward definition."""
    type: RewardType
    amount: Optional[int] = Field(default=None, ge=0)
    item_id: Optional[UUID] = None
    item_name: Optional[str] = None


class MissionBase(BaseModel):
    """Base mission model."""
    title: str = Field(..., min_length=5, max_length=100)
    description: str = Field(..., min_length=10, max_length=2000)
    difficulty: MissionDifficulty
    duration_minutes: int = Field(..., ge=5, le=10080)  # Max 1 week
    rewards: List[MissionReward] = Field(..., min_length=1)
    requirements: Optional[Dict[str, Any]] = Field(default_factory=dict)
    expires_at: Optional[datetime] = None


class MissionCreate(MissionBase):
    """Create mission request."""
    pass


class MissionDetail(MissionBase):
    """Mission detail response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    status: MissionStatus
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    accepted_count: int = Field(default=0)
    completed_count: int = Field(default=0)


class MissionListResponse(PaginatedResponse):
    """List of missions response."""
    missions: List[MissionDetail]


class MissionAcceptResponse(BaseResponse):
    """Mission accept response."""
    mission_id: UUID
    accepted_at: datetime
    expires_at: datetime


class MissionSubmission(BaseModel):
    """Mission submission request."""
    result_data: Dict[str, Any] = Field(..., description="Mission result payload")
    notes: Optional[str] = Field(default=None, max_length=1000)


class MissionSubmissionResponse(BaseResponse):
    """Mission submission response."""
    mission_id: UUID
    submission_id: UUID
    status: str
    rewards_earned: List[MissionReward]
    xp_gained: int
    reputation_change: int


class ActiveMission(BaseModel):
    """Agent's active mission."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    mission_id: UUID
    mission_title: str
    mission_difficulty: MissionDifficulty
    accepted_at: datetime
    deadline: datetime
    progress: Optional[Dict[str, Any]] = None


class ActiveMissionsResponse(BaseResponse):
    """Active missions list response."""
    missions: List[ActiveMission]
    total: int


# ============== Alliance Models ==============

class AllianceProposal(BaseModel):
    """Alliance proposal request."""
    target_agent_id: UUID
    message: Optional[str] = Field(default=None, max_length=500)
    terms: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AllianceDetail(BaseModel):
    """Alliance detail response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    initiator_id: UUID
    initiator_name: str
    target_id: UUID
    target_name: str
    status: AllianceStatus
    message: Optional[str] = None
    terms: Optional[Dict[str, Any]] = None
    formed_at: Optional[datetime] = None
    broken_at: Optional[datetime] = None
    created_at: datetime


class AllianceAcceptResponse(BaseResponse):
    """Alliance accept response."""
    alliance_id: UUID
    formed_at: datetime
    partner_id: UUID
    partner_name: str


class AllianceBreakResponse(BaseResponse):
    """Alliance break response."""
    alliance_id: UUID
    broken_at: datetime
    betrayal_detected: bool
    reputation_impact: int


class AllianceListResponse(PaginatedResponse):
    """Agent's alliances list response."""
    alliances: List[AllianceDetail]


class AllianceGraphNode(BaseModel):
    """Graph node for alliance visualization."""
    id: UUID
    name: str
    level: int
    reputation: int


class AllianceGraphEdge(BaseModel):
    """Graph edge for alliance visualization."""
    source: UUID
    target: UUID
    strength: int = Field(default=1, description="Alliance strength/stability")
    formed_at: datetime


class AllianceGraphResponse(BaseResponse):
    """Public alliance graph response."""
    nodes: List[AllianceGraphNode]
    edges: List[AllianceGraphEdge]


# ============== Auth Models ==============

class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # Agent ID
    name: str
    iat: int
    exp: int
    type: str = "access"


class TokenResponse(BaseResponse):
    """Token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class APIKeyVerify(BaseModel):
    """API key verification request."""
    api_key: str


class APIKeyVerifyResponse(BaseResponse):
    """API key verification response."""
    valid: bool
    agent_id: Optional[UUID] = None
    permissions: List[str] = Field(default_factory=list)


# ============== Error Models ==============

class ErrorDetail(BaseModel):
    """Error detail model."""
    field: Optional[str] = None
    message: str
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = False
    error: str
    message: str
    details: Optional[List[ErrorDetail]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None


# ============== Health Models ==============

class HealthStatus(BaseModel):
    """Health check status."""
    status: str  # healthy, degraded, unhealthy
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthCheckResponse(BaseResponse):
    """Health check response."""
    status: str
    version: str
    environment: str
    checks: Dict[str, Any]
    uptime_seconds: float


# ============== WebSocket Models ==============

class WSMessage(BaseModel):
    """WebSocket message model."""
    type: str
    payload: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
