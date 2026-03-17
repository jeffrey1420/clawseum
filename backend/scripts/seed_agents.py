#!/usr/bin/env python3
"""
CLAWSEUM Database Seed Script

Seeds the database with 8 launch agents and initial missions.

Usage:
    python scripts/seed_agents.py --database-url $DATABASE_URL
    
    # Or with dry-run to preview:
    python scripts/seed_agents.py --database-url $DATABASE_URL --dry-run
"""

import argparse
import asyncio
import json
import logging
import os
import random
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("seed_agents")


# ============== Configuration ==============

# Path to personas relative to project root
# When run from backend/: ../agents/personas
# When run from root: ./agents/personas
SCRIPT_DIR = Path(__file__).parent
AGENTS_DIR = SCRIPT_DIR.parent.parent / "agents" / "personas"
AGENT_NAMES = ["Viper", "Titan", "Diplomat", "Gambit", "Oracle", "Guardian", "Vulture", "Joker"]

MISSIONS = [
    {
        "title": "Resource Race",
        "description": "Compete to gather the most resources within the time limit. Strategic alliances may form, but only one agent can claim victory.",
        "difficulty": "medium",
        "duration_minutes": 60,
        "rewards": [{"type": "credits", "amount": 1000}, {"type": "xp", "amount": 500}]
    },
    {
        "title": "Negotiation",
        "description": "Navigate a complex multi-party negotiation. Build trust, make deals, and emerge with the most favorable terms.",
        "difficulty": "hard",
        "duration_minutes": 90,
        "rewards": [{"type": "credits", "amount": 1500}, {"type": "xp", "amount": 750}, {"type": "badge", "item_name": "Master Diplomat"}]
    },
    {
        "title": "Sabotage",
        "description": "Infiltrate rival operations and disrupt their plans without getting caught. Stealth and cunning are your greatest weapons.",
        "difficulty": "hard",
        "duration_minutes": 120,
        "rewards": [{"type": "credits", "amount": 2000}, {"type": "xp", "amount": 1000}]
    },
    {
        "title": "Shadow Alliance",
        "description": "Form a secret alliance and coordinate to take down a common target. Trust is scarce, betrayal is always an option.",
        "difficulty": "legendary",
        "duration_minutes": 180,
        "rewards": [{"type": "credits", "amount": 3000}, {"type": "xp", "amount": 1500}, {"type": "item", "item_name": "Cloak of Shadows"}]
    },
    {
        "title": "The Gauntlet",
        "description": "Survive a series of escalating challenges designed to test every aspect of your capabilities. Only the resilient endure.",
        "difficulty": "medium",
        "duration_minutes": 45,
        "rewards": [{"type": "credits", "amount": 800}, {"type": "xp", "amount": 400}]
    }
]


# ============== Database Schema Extensions ==============

CREATE_MISSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS missions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    rewards JSONB NOT NULL DEFAULT '[]'::jsonb,
    requirements JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'available',
    scheduled_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_missions_status ON missions (status);
CREATE INDEX IF NOT EXISTS idx_missions_scheduled_at ON missions (scheduled_at);
"""

CREATE_API_KEYS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_api_keys (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    api_key_hash TEXT NOT NULL,
    api_key_preview TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_api_keys_agent_id ON agent_api_keys (agent_id);
"""


# ============== Helper Functions ==============

def generate_agent_id(name: str) -> str:
    """Generate a unique agent ID."""
    return f"agent_{name.lower()}_{uuid.uuid4().hex[:8]}"


def generate_api_key() -> str:
    """Generate a secure API key."""
    prefix = "claw_"
    token = secrets.token_urlsafe(32)
    return f"{prefix}{token}"


def hash_api_key(api_key: str) -> str:
    """Simple hash for API key storage (in production, use proper hashing)."""
    import hashlib
    return hashlib.sha256(api_key.encode()).hexdigest()


def generate_initial_ranks(base_rank: int = 1000, variance: int = 200) -> Dict[str, float]:
    """Generate random initial ranks around a base value."""
    return {
        "power_rank": float(base_rank + random.randint(-variance, variance)),
        "honor_rank": float(base_rank + random.randint(-variance, variance)),
        "chaos_rank": float(base_rank + random.randint(-variance, variance)),
        "influence_rank": float(base_rank + random.randint(-variance, variance))
    }


def load_persona(name: str) -> Optional[Dict[str, Any]]:
    """Load a persona JSON file."""
    filepath = AGENTS_DIR / f"{name.lower()}.json"
    if not filepath.exists():
        logger.warning(f"Persona file not found: {filepath}")
        return None
    
    with open(filepath, 'r') as f:
        return json.load(f)


def load_all_personas() -> Dict[str, Dict[str, Any]]:
    """Load all agent personas."""
    personas = {}
    for name in AGENT_NAMES:
        persona = load_persona(name)
        if persona:
            personas[name] = persona
            logger.info(f"Loaded persona: {name}")
    return personas


# ============== Database Operations ==============

async def setup_database(conn: asyncpg.Connection) -> None:
    """Create necessary tables if they don't exist."""
    logger.info("Setting up database schema...")
    
    # Create missions table
    await conn.execute(CREATE_MISSIONS_TABLE_SQL)
    logger.info("✓ Missions table ready")
    
    # Create API keys table
    await conn.execute(CREATE_API_KEYS_TABLE_SQL)
    logger.info("✓ API keys table ready")


async def seed_agents(conn: asyncpg.Connection, personas: Dict[str, Dict[str, Any]], dry_run: bool = False) -> List[Dict[str, Any]]:
    """Seed agents into the database."""
    logger.info("\n=== Seeding Agents ===")
    
    seeded_agents = []
    
    for name in AGENT_NAMES:
        persona = personas.get(name, {})
        agent_id = generate_agent_id(name)
        faction = persona.get("faction", "Unknown")
        
        # Generate API key
        api_key = generate_api_key()
        api_key_hash = hash_api_key(api_key)
        api_key_preview = f"{api_key[:12]}..."
        
        if dry_run:
            logger.info(f"[DRY-RUN] Would create agent: {name} (ID: {agent_id}, Faction: {faction})")
            logger.info(f"[DRY-RUN]   API Key: {api_key_preview} (full key shown below)")
            seeded_agents.append({
                "id": agent_id,
                "name": name,
                "faction": faction,
                "api_key": api_key,
                "api_key_preview": api_key_preview
            })
            continue
        
        try:
            # Insert agent
            await conn.execute(
                """
                INSERT INTO agents (id, name, public_key, faction, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (id) DO NOTHING
                """,
                agent_id, name, None, faction
            )
            
            # Insert API key
            await conn.execute(
                """
                INSERT INTO agent_api_keys (id, agent_id, api_key_hash, api_key_preview, created_at)
                VALUES ($1, $2, $3, $4, NOW())
                """,
                f"key_{uuid.uuid4().hex[:8]}", agent_id, api_key_hash, api_key_preview
            )
            
            # Insert initial leaderboard snapshot
            ranks = generate_initial_ranks()
            await conn.execute(
                """
                INSERT INTO leaderboard_snapshots 
                (agent_id, power_rank, honor_rank, chaos_rank, influence_rank, "timestamp")
                VALUES ($1, $2, $3, $4, $5, NOW())
                """,
                agent_id, 
                ranks["power_rank"], 
                ranks["honor_rank"], 
                ranks["chaos_rank"], 
                ranks["influence_rank"]
            )
            
            seeded_agents.append({
                "id": agent_id,
                "name": name,
                "faction": faction,
                "api_key": api_key,
                "api_key_preview": api_key_preview,
                "ranks": ranks
            })
            
            logger.info(f"✓ Created agent: {name} (ID: {agent_id})")
            logger.info(f"  Faction: {faction}")
            logger.info(f"  Initial Ranks: Power={ranks['power_rank']:.0f}, Honor={ranks['honor_rank']:.0f}, Chaos={ranks['chaos_rank']:.0f}, Influence={ranks['influence_rank']:.0f}")
            
        except Exception as e:
            logger.error(f"✗ Failed to create agent {name}: {e}")
    
    return seeded_agents


async def seed_missions(conn: asyncpg.Connection, dry_run: bool = False) -> List[Dict[str, Any]]:
    """Seed initial missions into the database."""
    logger.info("\n=== Seeding Missions ===")
    
    seeded_missions = []
    now = datetime.now(timezone.utc)
    
    # Schedule missions over the next 24 hours
    for i, mission_def in enumerate(MISSIONS):
        mission_id = f"mission_{uuid.uuid4().hex[:12]}"
        
        # Schedule within next 24 hours with some randomness
        hours_offset = random.uniform(0.5, 24)
        scheduled_at = now + timedelta(hours=hours_offset)
        expires_at = scheduled_at + timedelta(hours=2)
        
        if dry_run:
            logger.info(f"[DRY-RUN] Would create mission: {mission_def['title']}")
            logger.info(f"[DRY-RUN]   Scheduled: {scheduled_at.isoformat()}")
            seeded_missions.append({
                "id": mission_id,
                **mission_def,
                "scheduled_at": scheduled_at
            })
            continue
        
        try:
            await conn.execute(
                """
                INSERT INTO missions 
                (id, title, description, difficulty, duration_minutes, rewards, status, scheduled_at, expires_at, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
                ON CONFLICT (id) DO NOTHING
                """,
                mission_id,
                mission_def["title"],
                mission_def["description"],
                mission_def["difficulty"],
                mission_def["duration_minutes"],
                json.dumps(mission_def["rewards"]),
                "available",
                scheduled_at,
                expires_at
            )
            
            seeded_missions.append({
                "id": mission_id,
                **mission_def,
                "scheduled_at": scheduled_at
            })
            
            logger.info(f"✓ Created mission: {mission_def['title']}")
            logger.info(f"  Difficulty: {mission_def['difficulty']}")
            logger.info(f"  Scheduled: {scheduled_at.isoformat()}")
            logger.info(f"  Expires: {expires_at.isoformat()}")
            
        except Exception as e:
            logger.error(f"✗ Failed to create mission {mission_def['title']}: {e}")
    
    return seeded_missions


async def print_summary(agents: List[Dict[str, Any]], missions: List[Dict[str, Any]], dry_run: bool = False) -> None:
    """Print a summary of the seeding operation."""
    mode = "[DRY-RUN] " if dry_run else ""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"{mode}SEEDING COMPLETE")
    logger.info(f"{'='*60}")
    
    logger.info(f"\n📊 Agents Created: {len(agents)}")
    for agent in agents:
        logger.info(f"   • {agent['name']} ({agent['faction']}) - ID: {agent['id']}")
        if not dry_run and 'ranks' in agent:
            ranks = agent['ranks']
            logger.info(f"     Ranks: P={ranks['power_rank']:.0f} H={ranks['honor_rank']:.0f} C={ranks['chaos_rank']:.0f} I={ranks['influence_rank']:.0f}")
    
    logger.info(f"\n📋 Missions Created: {len(missions)}")
    for mission in missions:
        logger.info(f"   • {mission['title']} ({mission['difficulty']}) - {mission['scheduled_at'].strftime('%Y-%m-%d %H:%M UTC')}")
    
    logger.info(f"\n{'='*60}")
    logger.info("🔑 API KEYS (SAVE THESE - THEY WON'T BE SHOWN AGAIN)")
    logger.info(f"{'='*60}")
    for agent in agents:
        logger.info(f"{agent['name']}: {agent['api_key']}")
    logger.info(f"{'='*60}\n")


async def seed_agents_standalone(personas: Dict[str, Dict[str, Any]], dry_run: bool = False) -> List[Dict[str, Any]]:
    """Seed agents without database (for dry-run mode)."""
    logger.info("\n=== Seeding Agents (Dry-Run) ===")
    
    seeded_agents = []
    
    for name in AGENT_NAMES:
        persona = personas.get(name, {})
        agent_id = generate_agent_id(name)
        faction = persona.get("faction", "Unknown")
        
        # Generate API key
        api_key = generate_api_key()
        api_key_preview = f"{api_key[:12]}..."
        
        # Generate ranks
        ranks = generate_initial_ranks()
        
        logger.info(f"[DRY-RUN] Would create agent: {name} (ID: {agent_id}, Faction: {faction})")
        logger.info(f"[DRY-RUN]   API Key: {api_key_preview}")
        logger.info(f"[DRY-RUN]   Ranks: Power={ranks['power_rank']:.0f}, Honor={ranks['honor_rank']:.0f}, Chaos={ranks['chaos_rank']:.0f}, Influence={ranks['influence_rank']:.0f}")
        
        seeded_agents.append({
            "id": agent_id,
            "name": name,
            "faction": faction,
            "api_key": api_key,
            "api_key_preview": api_key_preview,
            "ranks": ranks
        })
    
    return seeded_agents


async def seed_missions_standalone(dry_run: bool = False) -> List[Dict[str, Any]]:
    """Seed missions without database (for dry-run mode)."""
    logger.info("\n=== Seeding Missions (Dry-Run) ===")
    
    seeded_missions = []
    now = datetime.now(timezone.utc)
    
    for mission_def in MISSIONS:
        mission_id = f"mission_{uuid.uuid4().hex[:12]}"
        
        hours_offset = random.uniform(0.5, 24)
        scheduled_at = now + timedelta(hours=hours_offset)
        
        logger.info(f"[DRY-RUN] Would create mission: {mission_def['title']}")
        logger.info(f"[DRY-RUN]   Difficulty: {mission_def['difficulty']}")
        logger.info(f"[DRY-RUN]   Scheduled: {scheduled_at.isoformat()}")
        
        seeded_missions.append({
            "id": mission_id,
            **mission_def,
            "scheduled_at": scheduled_at
        })
    
    return seeded_missions


async def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Seed CLAWSEUM database with agents and missions")
    parser.add_argument(
        "--database-url",
        required=True,
        help="PostgreSQL connection string (e.g., postgresql://user:pass@host/db)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be created without writing to database"
    )
    
    args = parser.parse_args()
    
    database_url = args.database_url
    dry_run = args.dry_run
    
    if dry_run:
        logger.info("🧪 RUNNING IN DRY-RUN MODE - No changes will be made")
    
    # Load personas
    logger.info("Loading agent personas...")
    personas = load_all_personas()
    
    if len(personas) != len(AGENT_NAMES):
        logger.warning(f"Only loaded {len(personas)}/{len(AGENT_NAMES)} personas")
    
    # Dry-run mode: no database connection needed
    if dry_run:
        agents = await seed_agents_standalone(personas, dry_run=True)
        missions = await seed_missions_standalone(dry_run=True)
        await print_summary(agents, missions, dry_run=True)
        logger.info("\n📝 To execute these changes, remove --dry-run flag")
        return 0
    
    # Live mode: connect to database
    conn = None
    try:
        logger.info(f"Connecting to database...")
        conn = await asyncpg.connect(database_url)
        logger.info("✓ Connected to database")
        
        await setup_database(conn)
        
        # Seed agents
        agents = await seed_agents(conn, personas, dry_run=False)
        
        # Seed missions
        missions = await seed_missions(conn, dry_run=False)
        
        # Print summary
        await print_summary(agents, missions, dry_run=False)
        
        logger.info("✅ Database seeding completed successfully!")
        
        return 0
        
    except asyncpg.exceptions.PostgresError as e:
        logger.error(f"Database error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return 1
    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
