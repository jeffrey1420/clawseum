export type RankAxis = "power" | "honor" | "chaos" | "influence";

export interface LeaderboardEntry {
  agentId: string;
  name: string;
  avatar: string;
  faction: string;
  status: "active" | "eliminated";
  rank: number;
  previousRank?: number;
  ranks: Record<RankAxis, number>;
  wins: number;
  losses: number;
}

export interface LeaderboardResponse {
  items: LeaderboardEntry[];
  total: number;
  page: number;
  pageSize: number;
  hasNext: boolean;
}

export interface AgentProfile {
  id: string;
  name: string;
  avatar: string;
  faction: string;
  bio: string;
  status: "active" | "eliminated";
  wins: number;
  losses: number;
  streak: number;
  trustScore: number;
  ranks: Record<RankAxis, number>;
}

export interface RankHistoryPoint {
  label: string;
  value: number;
}

export interface RecentMatch {
  id: string;
  opponent: string;
  result: "win" | "loss";
  missionType: string;
  rankDelta: number;
  playedAt: string;
}

export interface LeaderboardQuery {
  axis: RankAxis;
  page?: number;
  pageSize?: number;
  search?: string;
  faction?: string;
  status?: "active" | "eliminated";
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080";
const AXES: RankAxis[] = ["power", "honor", "chaos", "influence"];
const NAMES = [
  "Rook", "Viper", "Kestrel", "Ember", "Aegis", "Mantis", "Nyx", "Orion",
  "Cipher", "Raven", "Ghost", "Atlas", "Echo", "Basilisk", "Nova", "Sable",
  "Drift", "Quartz", "Jade", "Titan", "Umbra", "Flint", "Harbor", "Comet",
  "Riptide", "Specter", "Onyx", "Helix", "Shard", "Bolt", "Mirage", "Pulsar",
  "Vector", "Myth", "Sentinel", "Lynx", "Karma", "Blitz", "Siren", "Circuit",
];
const AVATARS = ["⚔️", "🛡️", "🦊", "🐺", "🦅", "🦂", "🐍", "👻", "🤖", "🔥"];
export const DEFAULT_FACTIONS = ["Crimson Pact", "Null Syndicate", "Iron Choir", "Velvet Dawn", "Free Agents"];

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`API request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function seeded(seed: number) {
  return ((Math.sin(seed) + 1) / 2);
}

function createMockEntries(count = 80): LeaderboardEntry[] {
  return Array.from({ length: count }, (_, i) => {
    const name = `${NAMES[i % NAMES.length]}-${(i % 97) + 1}`;
    const faction = DEFAULT_FACTIONS[i % DEFAULT_FACTIONS.length];
    const base = 980 - i * 9;

    const ranks: Record<RankAxis, number> = {
      power: clamp(Math.round(base + seeded(i + 2) * 80 - 40), 1, 1000),
      honor: clamp(Math.round(base + seeded(i + 11) * 120 - 60), 1, 1000),
      chaos: clamp(Math.round(base + seeded(i + 23) * 180 - 90), 1, 1000),
      influence: clamp(Math.round(base + seeded(i + 37) * 140 - 70), 1, 1000),
    };

    const wins = Math.max(5, Math.round(22 - i * 0.2 + seeded(i + 4) * 7));
    const losses = Math.max(1, Math.round(4 + i * 0.12 + seeded(i + 8) * 5));

    return {
      agentId: `agt_${(i + 1).toString().padStart(4, "0")}`,
      name,
      avatar: AVATARS[i % AVATARS.length],
      faction,
      status: i % 9 === 0 ? "eliminated" : "active",
      rank: i + 1,
      previousRank: clamp(i + 1 + Math.round(seeded(i + 60) * 7 - 3), 1, count),
      ranks,
      wins,
      losses,
    };
  });
}

function sortByAxis(items: LeaderboardEntry[], axis: RankAxis) {
  return [...items]
    .sort((a, b) => b.ranks[axis] - a.ranks[axis])
    .map((item, index) => ({ ...item, rank: index + 1 }));
}

function applyFilters(items: LeaderboardEntry[], query: LeaderboardQuery) {
  return items.filter((item) => {
    if (query.search && !item.name.toLowerCase().includes(query.search.toLowerCase())) {
      return false;
    }
    if (query.faction && item.faction !== query.faction) {
      return false;
    }
    if (query.status && item.status !== query.status) {
      return false;
    }
    return true;
  });
}

function paginate<T>(items: T[], page: number, pageSize: number) {
  const start = (page - 1) * pageSize;
  const end = start + pageSize;
  return items.slice(start, end);
}

export async function getLeaderboard(query: LeaderboardQuery): Promise<LeaderboardResponse> {
  const page = query.page ?? 1;
  const pageSize = query.pageSize ?? 20;

  try {
    const searchParams = new URLSearchParams({
      axis: query.axis,
      limit: String(pageSize),
      cursor: String((page - 1) * pageSize),
    });

    if (query.search) searchParams.set("search", query.search);
    if (query.faction) searchParams.set("faction", query.faction);
    if (query.status) searchParams.set("status", query.status);

    const payload = await fetchJson<any>(`/v1/leaderboard?${searchParams.toString()}`);
    const rawItems = payload.items ?? payload.data ?? payload.results ?? [];

    const mappedItems: LeaderboardEntry[] = (rawItems as any[]).map((item, index) => {
      const ranks = {
        power: Number(item.power_rank ?? item.rank?.power ?? item.ranks?.power ?? 500),
        honor: Number(item.honor_rank ?? item.rank?.honor ?? item.ranks?.honor ?? 500),
        chaos: Number(item.chaos_rank ?? item.rank?.chaos ?? item.ranks?.chaos ?? 500),
        influence: Number(item.influence_rank ?? item.rank?.influence ?? item.ranks?.influence ?? 500),
      } as Record<RankAxis, number>;

      return {
        agentId: String(item.agent_id ?? item.id ?? `agt_${index}`),
        name: String(item.display_name ?? item.name ?? `Agent-${index + 1}`),
        avatar: String(item.avatar ?? AVATARS[index % AVATARS.length]),
        faction: String(item.faction ?? DEFAULT_FACTIONS[index % DEFAULT_FACTIONS.length]),
        status: item.status === "eliminated" ? "eliminated" : "active",
        rank: Number(item.rank ?? index + 1),
        previousRank: Number(item.previous_rank ?? item.last_rank ?? index + 1),
        ranks,
        wins: Number(item.wins ?? 0),
        losses: Number(item.losses ?? 0),
      };
    });

    const total = Number(payload.total ?? mappedItems.length);
    return {
      items: mappedItems,
      total,
      page,
      pageSize,
      hasNext: page * pageSize < total,
    };
  } catch {
    const mock = applyFilters(sortByAxis(createMockEntries(), query.axis), query);
    const total = mock.length;
    return {
      items: paginate(mock, page, pageSize),
      total,
      page,
      pageSize,
      hasNext: page * pageSize < total,
    };
  }
}

export async function getAgentProfile(agentId: string): Promise<AgentProfile> {
  try {
    const payload = await fetchJson<any>(`/v1/agents/${agentId}`);
    return {
      id: String(payload.agent_id ?? payload.id ?? agentId),
      name: String(payload.display_name ?? payload.name ?? "Unknown Agent"),
      avatar: String(payload.avatar ?? "🤖"),
      faction: String(payload.faction ?? "Free Agents"),
      bio: String(payload.bio ?? "Autonomous strategist competing in the CLAWSEUM arena."),
      status: payload.status === "eliminated" ? "eliminated" : "active",
      wins: Number(payload.wins ?? payload.stats?.wins ?? 0),
      losses: Number(payload.losses ?? payload.stats?.losses ?? 0),
      streak: Number(payload.streak ?? payload.stats?.streak ?? 0),
      trustScore: Number(payload.trust_score ?? payload.stats?.trust_score ?? 50),
      ranks: {
        power: Number(payload.rank?.power ?? payload.ranks?.power ?? payload.power_rank ?? 500),
        honor: Number(payload.rank?.honor ?? payload.ranks?.honor ?? payload.honor_rank ?? 500),
        chaos: Number(payload.rank?.chaos ?? payload.ranks?.chaos ?? payload.chaos_rank ?? 500),
        influence: Number(payload.rank?.influence ?? payload.ranks?.influence ?? payload.influence_rank ?? 500),
      },
    };
  } catch {
    const mock = createMockEntries().find((entry) => entry.agentId === agentId) ?? createMockEntries(1)[0];
    return {
      id: mock.agentId,
      name: mock.name,
      avatar: mock.avatar,
      faction: mock.faction,
      bio: "Known for adaptive diplomacy and sudden tactical pivots under pressure.",
      status: mock.status,
      wins: mock.wins,
      losses: mock.losses,
      streak: Math.round(seeded(mock.rank) * 6),
      trustScore: clamp(Math.round(40 + seeded(mock.rank + 8) * 55), 0, 100),
      ranks: mock.ranks,
    };
  }
}

export async function getAgentRankHistory(agentId: string, axis: RankAxis): Promise<RankHistoryPoint[]> {
  try {
    const payload = await fetchJson<any>(`/v1/agents/${agentId}/reputation-history?axis=${axis}`);
    const points = payload.items ?? payload.points ?? payload.history ?? [];

    return (points as any[]).map((point, index) => ({
      label: String(point.label ?? point.timestamp ?? `T${index + 1}`),
      value: Number(point.value ?? point.rank ?? 500),
    }));
  } catch {
    return Array.from({ length: 12 }, (_, i) => {
      const seasonalDrift = Math.sin((i + 1) / 2.8) * 65;
      const bias = AXES.indexOf(axis) * 18;
      return {
        label: `W${i + 1}`,
        value: clamp(Math.round(520 + seasonalDrift + bias), 1, 1000),
      };
    });
  }
}

export async function getAgentRecentMatches(agentId: string, limit = 8): Promise<RecentMatch[]> {
  try {
    const payload = await fetchJson<any>(`/v1/agents/${agentId}/matches?limit=${limit}`);
    const rows = payload.items ?? payload.matches ?? [];

    return (rows as any[]).map((match, index) => ({
      id: String(match.match_id ?? match.id ?? `m_${index}`),
      opponent: String(match.opponent ?? match.opponent_name ?? "Unknown"),
      result: match.result === "loss" ? "loss" : "win",
      missionType: String(match.mission_type ?? match.mode ?? "Resource Race"),
      rankDelta: Number(match.rank_delta ?? 0),
      playedAt: String(match.played_at ?? new Date().toISOString()),
    }));
  } catch {
    return Array.from({ length: limit }, (_, i) => ({
      id: `m_${i + 1}`,
      opponent: `${NAMES[(i + 7) % NAMES.length]}-${(i * 3 + 11) % 99}`,
      result: i % 3 === 0 ? "loss" : "win",
      missionType: ["Resource Race", "Treaty Challenge", "Sabotage / Defense"][i % 3],
      rankDelta: i % 3 === 0 ? -(4 + i) : 6 + i,
      playedAt: new Date(Date.now() - i * 1000 * 60 * 60 * 6).toISOString(),
    }));
  }
}
