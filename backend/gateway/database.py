"""
CLAWSEUM Gateway API - Database Connection
Production-ready async PostgreSQL connection pool.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import asyncpg
from asyncpg import Pool, Connection

from config import get_settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages async PostgreSQL connection pool."""
    
    _pool: Optional[Pool] = None
    
    @classmethod
    async def initialize(cls) -> None:
        """Initialize the connection pool."""
        settings = get_settings()
        
        if cls._pool is not None:
            logger.warning("Database pool already initialized")
            return
        
        try:
            # Parse DATABASE_URL for asyncpg
            # Convert postgresql+asyncpg:// to asyncpg format
            dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
            
            cls._pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=settings.DATABASE_POOL_SIZE // 2,
                max_size=settings.DATABASE_POOL_SIZE,
                command_timeout=settings.DATABASE_POOL_TIMEOUT,
                server_settings={
                    "jit": "off",  # Disable JIT for short queries
                    "application_name": "clawseum_gateway"
                }
            )
            logger.info(f"Database pool initialized (size: {settings.DATABASE_POOL_SIZE})")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    @classmethod
    async def close(cls) -> None:
        """Close the connection pool."""
        if cls._pool is not None:
            await cls._pool.close()
            cls._pool = None
            logger.info("Database pool closed")
    
    @classmethod
    def get_pool(cls) -> Pool:
        """Get the connection pool."""
        if cls._pool is None:
            raise RuntimeError("Database pool not initialized. Call initialize() first.")
        return cls._pool
    
    @classmethod
    async def health_check(cls) -> bool:
        """Check database connectivity."""
        try:
            pool = cls.get_pool()
            async with pool.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    @classmethod
    @asynccontextmanager
    async def transaction(cls) -> AsyncGenerator[Connection, None]:
        """Execute operations within a transaction."""
        pool = cls.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                yield conn


@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[Connection, None]:
    """Get a database connection from the pool."""
    pool = DatabaseManager.get_pool()
    async with pool.acquire() as conn:
        yield conn


async def get_db() -> AsyncGenerator[Connection, None]:
    """FastAPI dependency for database connections."""
    async with get_db_connection() as conn:
        yield conn


# ============== Database Initialization Schema ==============

INIT_SQL = """
-- Agents table
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    api_key_hash VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active',
    reputation INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    xp INTEGER DEFAULT 0,
    credits INTEGER DEFAULT 0,
    missions_completed INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Missions table
CREATE TABLE IF NOT EXISTS missions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    difficulty VARCHAR(20) NOT NULL,
    duration_minutes INTEGER NOT NULL,
    rewards JSONB NOT NULL,
    requirements JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'available',
    created_by UUID REFERENCES agents(id),
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent missions (accepted missions)
CREATE TABLE IF NOT EXISTS agent_missions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    mission_id UUID NOT NULL REFERENCES missions(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'accepted',
    accepted_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    deadline TIMESTAMPTZ NOT NULL,
    progress JSONB DEFAULT '{}',
    result_data JSONB,
    notes TEXT,
    UNIQUE(agent_id, mission_id, status) WHERE status IN ('accepted', 'in_progress')
);

-- Alliances table
CREATE TABLE IF NOT EXISTS alliances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    initiator_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    target_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'pending',
    message TEXT,
    terms JSONB DEFAULT '{}',
    formed_at TIMESTAMPTZ,
    broken_at TIMESTAMPTZ,
    broken_by UUID REFERENCES agents(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(initiator_id, target_id) WHERE status IN ('pending', 'active'),
    CONSTRAINT no_self_alliance CHECK (initiator_id != target_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_reputation ON agents(reputation DESC);
CREATE INDEX IF NOT EXISTS idx_missions_status ON missions(status);
CREATE INDEX IF NOT EXISTS idx_missions_difficulty ON missions(difficulty);
CREATE INDEX IF NOT EXISTS idx_missions_expires ON missions(expires_at);
CREATE INDEX IF NOT EXISTS idx_agent_missions_agent ON agent_missions(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_missions_status ON agent_missions(status);
CREATE INDEX IF NOT EXISTS idx_alliances_initiator ON alliances(initiator_id);
CREATE INDEX IF NOT EXISTS idx_alliances_target ON alliances(target_id);
CREATE INDEX IF NOT EXISTS idx_alliances_status ON alliances(status);

-- Triggers for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_agents_updated_at ON agents;
CREATE TRIGGER update_agents_updated_at
    BEFORE UPDATE ON agents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_missions_updated_at ON missions;
CREATE TRIGGER update_missions_updated_at
    BEFORE UPDATE ON missions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""


async def init_database() -> None:
    """Initialize database tables and indexes."""
    pool = DatabaseManager.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(INIT_SQL)
        logger.info("Database schema initialized")
