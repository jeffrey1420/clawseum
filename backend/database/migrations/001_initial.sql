-- 001_initial.sql
-- Initial database objects for CLAWSEUM backend services.

BEGIN;

CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    public_key TEXT,
    faction TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS match_participants (
    match_id TEXT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    score NUMERIC(12, 3) NOT NULL DEFAULT 0,
    rank_delta JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (match_id, agent_id)
);

CREATE INDEX IF NOT EXISTS idx_match_participants_agent_id
    ON match_participants (agent_id);

CREATE TABLE IF NOT EXISTS leaderboard_snapshots (
    agent_id TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    power_rank NUMERIC(12, 3) NOT NULL,
    honor_rank NUMERIC(12, 3) NOT NULL,
    chaos_rank NUMERIC(12, 3) NOT NULL,
    influence_rank NUMERIC(12, 3) NOT NULL,
    "timestamp" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (agent_id, "timestamp")
);

CREATE INDEX IF NOT EXISTS idx_leaderboard_snapshots_timestamp
    ON leaderboard_snapshots ("timestamp" DESC);

CREATE TABLE IF NOT EXISTS alliances (
    agent_a TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    agent_b TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    formed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    broken_at TIMESTAMPTZ,
    PRIMARY KEY (agent_a, agent_b, formed_at),
    CONSTRAINT chk_alliances_distinct_agents CHECK (agent_a <> agent_b)
);

CREATE INDEX IF NOT EXISTS idx_alliances_status
    ON alliances (status);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_created_at
    ON events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_events_type_created_at
    ON events (type, created_at DESC);

COMMIT;
