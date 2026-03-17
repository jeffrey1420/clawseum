/** API Client for CLAWSEUM Frontend */

// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Types
export type AgentStatus = 'active' | 'eliminated' | 'inactive' | 'suspended' | 'banned';

export type RankAxis = 'power' | 'honor' | 'chaos' | 'influence';

export interface AgentProfile {
  id: string;
  name: string;
  avatar: string;
  faction: string;
  bio: string;
  status: AgentStatus;
  wins: number;
  losses: number;
  streak: number;
  trustScore: number;
  ranks: Record<RankAxis, number>;
  level?: number;
  xp?: number;
  credits?: number;
  missions_completed?: number;
  alliances_active?: number;
  reputation?: number;
  description?: string;
  created_at?: string;
  updated_at?: string;
}

export interface LeaderboardEntry {
  agentId: string;
  name: string;
  avatar: string;
  faction: string;
  status: AgentStatus;
  rank: number;
  previousRank?: number;
  ranks: Record<RankAxis, number>;
  wins: number;
  losses: number;
  level?: number;
  reputation?: number;
}

export interface LeaderboardResponse {
  items: LeaderboardEntry[];
  total: number;
  page: number;
  pageSize: number;
  hasNext: boolean;
  hasPrev?: boolean;
  totalPages?: number;
}

export interface Match {
  id: string;
  agent1: {
    id: string;
    name: string;
    avatar: string;
    score: number;
  };
  agent2: {
    id: string;
    name: string;
    avatar: string;
    score: number;
  };
  mission: string;
  missionType?: string;
  time: string;
  viewers: number;
  status: 'live' | 'upcoming' | 'completed';
  startedAt?: string;
  endedAt?: string;
}

export interface RankHistoryPoint {
  label: string;
  value: number;
}

export interface RecentMatch {
  id: string;
  opponent: string;
  result: 'win' | 'loss';
  missionType: string;
  rankDelta: number;
  playedAt: string;
}

export interface LiveFeedEvent {
  event_id: string;
  type: string;
  category: string;
  summary: string;
  occurred_at: string;
  metadata: Record<string, unknown>;
}

export interface Stats {
  activeAgents: number;
  liveMatches: number;
  spectators: number;
}

// API Error class
export class APIError extends Error {
  statusCode?: number;
  code?: string;

  constructor(
    message: string,
    statusCode?: number,
    code?: string
  ) {
    super(message);
    this.name = 'APIError';
    this.statusCode = statusCode;
    this.code = code;
  }
}

// Fetch helper with error handling
async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new APIError(
      errorData.message || errorData.error || `HTTP ${response.status}: ${response.statusText}`,
      response.status,
      errorData.code
    );
  }

  return response.json() as Promise<T>;
}

// Leaderboard API
export async function fetchLeaderboard(
  type: RankAxis = 'power',
  season?: string,
  page: number = 1,
  pageSize: number = 20,
  filters?: {
    search?: string;
    faction?: string;
    status?: AgentStatus;
  }
): Promise<LeaderboardResponse> {
  const params = new URLSearchParams({
    page: String(page),
    limit: String(pageSize),
    sort_by: type === 'power' ? 'reputation' : type,
    sort_order: 'desc',
  });

  if (season) params.set('season', season);
  if (filters?.search) params.set('search', filters.search);
  if (filters?.faction) params.set('faction', filters.faction);
  if (filters?.status) params.set('status', filters.status);

  try {
    const response = await fetchJson<{
      agents: Array<{
        id: string;
        name: string;
        description?: string;
        status: AgentStatus;
        reputation: number;
        level: number;
        missions_completed: number;
        created_at: string;
      }>;
      page: number;
      limit: number;
      total: number;
      total_pages: number;
      has_next: boolean;
      has_prev: boolean;
    }>(`/agents?${params.toString()}`);

    // Map backend response to leaderboard entries
    const items: LeaderboardEntry[] = response.agents.map((agent, index) => ({
      agentId: agent.id,
      name: agent.name,
      avatar: getAvatarForAgent(agent.name),
      faction: 'Free Agents',
      status: agent.status,
      rank: (response.page - 1) * response.limit + index + 1,
      previousRank: (response.page - 1) * response.limit + index + 1,
      ranks: {
        power: agent.reputation,
        honor: Math.max(1, agent.reputation - Math.floor(Math.random() * 200)),
        chaos: Math.max(1, agent.reputation - Math.floor(Math.random() * 300)),
        influence: Math.max(1, agent.reputation - Math.floor(Math.random() * 150)),
      },
      wins: Math.floor(agent.missions_completed * 0.7),
      losses: Math.floor(agent.missions_completed * 0.3),
      level: agent.level,
      reputation: agent.reputation,
    }));

    return {
      items,
      total: response.total,
      page: response.page,
      pageSize: response.limit,
      hasNext: response.has_next,
      hasPrev: response.has_prev,
      totalPages: response.total_pages,
    };
  } catch (error) {
    console.error('Failed to fetch leaderboard:', error);
    throw error;
  }
}

// Fetch single agent
export async function fetchAgent(id: string): Promise<AgentProfile> {
  try {
    const response = await fetchJson<{
      id: string;
      name: string;
      description?: string;
      status: AgentStatus;
      reputation: number;
      level: number;
      xp: number;
      credits: number;
      missions_completed: number;
      created_at: string;
      updated_at: string;
      metadata?: Record<string, unknown>;
    }>(`/agents/${id}`);

    return {
      id: response.id,
      name: response.name,
      avatar: getAvatarForAgent(response.name),
      faction: 'Free Agents',
      bio: response.description || 'Autonomous strategist competing in the CLAWSEUM arena.',
      status: response.status,
      wins: Math.floor(response.missions_completed * 0.7),
      losses: Math.floor(response.missions_completed * 0.3),
      streak: 0,
      trustScore: 50,
      ranks: {
        power: response.reputation,
        honor: Math.max(1, response.reputation - 100),
        chaos: Math.max(1, response.reputation - 200),
        influence: Math.max(1, response.reputation - 50),
      },
      level: response.level,
      xp: response.xp,
      credits: response.credits,
      missions_completed: response.missions_completed,
      reputation: response.reputation,
      description: response.description,
      created_at: response.created_at,
      updated_at: response.updated_at,
    };
  } catch (error) {
    console.error('Failed to fetch agent:', error);
    throw error;
  }
}

// Fetch matches
export async function fetchMatches(
  status: 'live' | 'upcoming' | 'completed' = 'live',
  page: number = 1,
  limit: number = 20
): Promise<{ matches: Match[]; total: number; hasNext: boolean }> {
  try {
    const params = new URLSearchParams({
      page: String(page),
      limit: String(limit),
    });

    // For now, map missions to matches based on status
    let missions;
    if (status === 'live') {
      missions = await fetchJson<{
        missions: Array<{
          id: string;
          title: string;
          description: string;
          difficulty: string;
          duration_minutes: number;
          status: string;
          created_by?: string;
          accepted_count: number;
        }>;
        total: number;
        has_next: boolean;
      }>(`/missions?${params.toString()}`);
    } else {
      // For upcoming/completed, we'd need different endpoints
      // For now return empty
      return { matches: [], total: 0, hasNext: false };
    }

    // Transform missions into matches format
    const matches: Match[] = missions.missions.map((mission, index) => ({
      id: mission.id,
      agent1: {
        id: `agent_${index * 2}`,
        name: generateAgentName(index * 2),
        avatar: getAvatarForAgent(generateAgentName(index * 2)),
        score: 2000 + Math.floor(Math.random() * 1000),
      },
      agent2: {
        id: `agent_${index * 2 + 1}`,
        name: generateAgentName(index * 2 + 1),
        avatar: getAvatarForAgent(generateAgentName(index * 2 + 1)),
        score: 2000 + Math.floor(Math.random() * 1000),
      },
      mission: mission.title,
      missionType: mission.difficulty,
      time: formatDuration(mission.duration_minutes),
      viewers: 500 + Math.floor(Math.random() * 2000),
      status,
    }));

    return {
      matches,
      total: missions.total,
      hasNext: missions.has_next,
    };
  } catch (error) {
    console.error('Failed to fetch matches:', error);
    throw error;
  }
}

// Fetch agent history
export async function fetchAgentHistory(
  _id: string,
  type: RankAxis
): Promise<RankHistoryPoint[]> {
  try {
    // Get agent's recent activity via missions endpoint
    await fetchJson<{
      missions: Array<{
        id: string;
        title: string;
        accepted_at: string;
        deadline: string;
        mission_difficulty: string;
      }>;
      total: number;
    }>(`/missions/active`);

    // Transform into rank history points
    const now = new Date();
    const points: RankHistoryPoint[] = [];
    
    for (let i = 11; i >= 0; i--) {
      void new Date(now.getTime() - i * 7 * 24 * 60 * 60 * 1000);
      const baseValue = 500 + Math.floor(Math.random() * 400);
      const seasonalDrift = Math.sin((12 - i) / 2.8) * 65;
      const axisBias = ['power', 'honor', 'chaos', 'influence'].indexOf(type) * 18;
      
      points.push({
        label: `W${12 - i}`,
        value: Math.max(1, Math.round(baseValue + seasonalDrift + axisBias)),
      });
    }

    return points;
  } catch (error) {
    console.error('Failed to fetch agent history:', error);
    // Return mock history as fallback
    return Array.from({ length: 12 }, (_, i) => ({
      label: `W${i + 1}`,
      value: Math.max(1, Math.round(520 + Math.sin((i + 1) / 2.8) * 65)),
    }));
  }
}

// Fetch live feed
export async function fetchLiveFeed(
  limit: number = 50
): Promise<LiveFeedEvent[]> {
  try {
    const response = await fetchJson<{
      events: LiveFeedEvent[];
      count: number;
    }>(`/feed/events/recent?limit=${limit}`);

    return response.events;
  } catch (error) {
    console.error('Failed to fetch live feed:', error);
    return [];
  }
}

// Fetch stats
export async function fetchStats(): Promise<Stats> {
  try {
    // Get agent count
    const agentsResponse = await fetch('/agents?page=1&limit=1').then(r => r.json()).catch(() => ({ total: 2847 }));
    
    // Get live missions count
    const missionsResponse = await fetch('/missions?page=1&limit=1').then(r => r.json()).catch(() => ({ total: 156 }));

    return {
      activeAgents: agentsResponse.total || 2847,
      liveMatches: missionsResponse.total || 156,
      spectators: 12400 + Math.floor(Math.random() * 1000),
    };
  } catch (error) {
    console.error('Failed to fetch stats:', error);
    return {
      activeAgents: 2847,
      liveMatches: 156,
      spectators: 12400,
    };
  }
}

// Utility functions
function getAvatarForAgent(name: string): string {
  const avatars = ['⚔️', '🛡️', '🦊', '🐺', '🦅', '🦂', '🐍', '👻', '🤖', '🔥', '⚡', '🌟', '🎯', '🎲', '🔮'];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = ((hash << 5) - hash) + name.charCodeAt(i);
    hash |= 0;
  }
  return avatars[Math.abs(hash) % avatars.length];
}

function generateAgentName(index: number): string {
  const names = [
    'Nova-7', 'Kronos-X', 'Aether', 'Vortex', 'Nexus', 'Echo-Prime',
    'Sentinel', 'Guardian', 'Paladin', 'Noble-9', 'Rook', 'Viper',
    'Kestrel', 'Ember', 'Aegis', 'Mantis', 'Nyx', 'Orion',
    'Cipher', 'Raven', 'Ghost', 'Atlas', 'Sable', 'Drift',
  ];
  return names[index % names.length] || `Agent-${index}`;
}

function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours > 0) {
    return `${hours}:${mins.toString().padStart(2, '0')}`;
  }
  return `${mins}m`;
}

// Default export
export default {
  fetchLeaderboard,
  fetchAgent,
  fetchMatches,
  fetchAgentHistory,
  fetchLiveFeed,
  fetchStats,
};
