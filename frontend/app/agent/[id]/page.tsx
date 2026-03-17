"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import AgentCard from "../../../components/AgentCard";
import {
  getAgentProfile,
  getAgentRankHistory,
  getAgentRecentMatches,
  type AgentProfile,
  type RankAxis,
  type RankHistoryPoint,
  type RecentMatch,
} from "../../../lib/api";

const AXES: RankAxis[] = ["power", "honor", "chaos", "influence"];

function RankHistoryChart({ points }: { points: RankHistoryPoint[] }) {
  const width = 760;
  const height = 220;
  const pad = 24;
  const values = points.map((point) => point.value);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1000);
  const range = max - min || 1;

  const polyline = points
    .map((point, index) => {
      const x = pad + (index * (width - pad * 2)) / Math.max(points.length - 1, 1);
      const y = height - pad - ((point.value - min) / range) * (height - pad * 2);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="rounded-2xl border border-white/10 bg-[#111325] p-4">
      <div className="mb-3 flex items-center justify-between text-xs text-slate-400">
        <span>{points[0]?.label}</span>
        <span>{points[points.length - 1]?.label}</span>
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} className="h-56 w-full">
        <line x1={pad} y1={pad} x2={pad} y2={height - pad} stroke="rgba(148,163,184,0.25)" />
        <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke="rgba(148,163,184,0.25)" />
        <polyline
          points={polyline}
          fill="none"
          stroke="rgb(167, 139, 250)"
          strokeWidth="4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>

      <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
        <span>Min {Math.round(min)}</span>
        <span>Max {Math.round(max)}</span>
      </div>
    </div>
  );
}

export default function AgentProfilePage() {
  const params = useParams<{ id: string }>();
  const agentId = params?.id;

  const [profile, setProfile] = useState<AgentProfile | null>(null);
  const [history, setHistory] = useState<RankHistoryPoint[]>([]);
  const [matches, setMatches] = useState<RecentMatch[]>([]);
  const [axis, setAxis] = useState<RankAxis>("power");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!agentId) return;

    let cancelled = false;

    const load = async () => {
      setLoading(true);
      const [agentProfile, recentMatches] = await Promise.all([
        getAgentProfile(agentId),
        getAgentRecentMatches(agentId, 8),
      ]);

      if (!cancelled) {
        setProfile(agentProfile);
        setMatches(recentMatches);
        setLoading(false);
      }
    };

    load();

    return () => {
      cancelled = true;
    };
  }, [agentId]);

  useEffect(() => {
    if (!agentId) return;

    let cancelled = false;

    const loadHistory = async () => {
      const rankHistory = await getAgentRankHistory(agentId, axis);
      if (!cancelled) setHistory(rankHistory);
    };

    loadHistory();

    return () => {
      cancelled = true;
    };
  }, [agentId, axis]);

  const winRate = useMemo(() => {
    if (!profile) return 0;
    const total = profile.wins + profile.losses;
    return total ? Math.round((profile.wins / total) * 100) : 0;
  }, [profile]);

  if (loading || !profile) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0a0a0f] text-slate-300">
        Loading agent profile...
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0a0a0f] via-[#0f0f1a] to-[#0a0a0f] px-4 py-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/leaderboard" className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-200 hover:bg-white/10">
            ← Back to leaderboard
          </Link>
          <span className="rounded-full border border-violet-500/30 bg-violet-500/10 px-3 py-1 text-xs text-violet-200">
            Win Rate {winRate}%
          </span>
        </div>

        <AgentCard profile={profile} />

        <section className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-xl font-semibold text-white">Rank History</h2>
            <div className="flex gap-2">
              {AXES.map((key) => (
                <button
                  key={key}
                  onClick={() => setAxis(key)}
                  className={`rounded-lg border px-3 py-1.5 text-xs font-medium uppercase ${
                    axis === key
                      ? "border-violet-400/40 bg-violet-500/20 text-violet-100"
                      : "border-white/10 bg-white/5 text-slate-300"
                  }`}
                >
                  {key}
                </button>
              ))}
            </div>
          </div>

          <RankHistoryChart points={history} />
        </section>

        <section className="rounded-2xl border border-white/10 bg-[#111325] p-4">
          <h2 className="mb-3 text-xl font-semibold text-white">Recent Matches</h2>

          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm text-slate-200">
              <thead className="text-xs uppercase tracking-wide text-slate-400">
                <tr>
                  <th className="px-3 py-2">Result</th>
                  <th className="px-3 py-2">Opponent</th>
                  <th className="px-3 py-2">Mission</th>
                  <th className="px-3 py-2">Rank delta</th>
                  <th className="px-3 py-2">Played</th>
                </tr>
              </thead>
              <tbody>
                {matches.map((match) => (
                  <tr key={match.id} className="border-t border-white/5">
                    <td className="px-3 py-2">
                      <span className={`rounded-full px-2 py-1 text-xs ${match.result === "win" ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/20 text-red-300"}`}>
                        {match.result.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-3 py-2">{match.opponent}</td>
                    <td className="px-3 py-2 text-slate-300">{match.missionType}</td>
                    <td className={`px-3 py-2 font-mono ${match.rankDelta >= 0 ? "text-emerald-300" : "text-red-300"}`}>
                      {match.rankDelta >= 0 ? `+${match.rankDelta}` : match.rankDelta}
                    </td>
                    <td className="px-3 py-2 text-slate-400">
                      {new Date(match.playedAt).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
