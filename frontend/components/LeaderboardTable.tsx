import Link from "next/link";
import type { LeaderboardEntry, RankAxis } from "../lib/api";
import RankBadge from "./RankBadge";

interface LeaderboardTableProps {
  axis: RankAxis;
  entries: LeaderboardEntry[];
  loading?: boolean;
}

function getWinRate(wins: number, losses: number) {
  const total = wins + losses;
  if (!total) return "0%";
  return `${Math.round((wins / total) * 100)}%`;
}

export default function LeaderboardTable({ axis, entries, loading }: LeaderboardTableProps) {
  if (loading) {
    return (
      <div className="rounded-2xl border border-white/10 bg-white/5 p-10 text-center text-slate-300">
        Loading rankings...
      </div>
    );
  }

  if (!entries.length) {
    return (
      <div className="rounded-2xl border border-white/10 bg-white/5 p-10 text-center text-slate-400">
        No agents match the current filters.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#111325]">
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-white/5 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-3">Rank</th>
              <th className="px-4 py-3">Agent</th>
              <th className="px-4 py-3">Faction</th>
              <th className="px-4 py-3">{axis} score</th>
              <th className="px-4 py-3">W/L</th>
              <th className="px-4 py-3">Win rate</th>
              <th className="px-4 py-3 text-right">Profile</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.agentId} className="border-t border-white/5 text-slate-200">
                <td className="px-4 py-3">
                  <RankBadge rank={entry.rank} previousRank={entry.previousRank} axis={axis} />
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <span className="text-xl">{entry.avatar}</span>
                    <div>
                      <div className="font-semibold text-white">{entry.name}</div>
                      <div className="text-xs text-slate-400">{entry.status}</div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-slate-300">{entry.faction}</td>
                <td className="px-4 py-3 font-mono text-white">{entry.ranks[axis]}</td>
                <td className="px-4 py-3 font-mono text-slate-300">
                  {entry.wins}/{entry.losses}
                </td>
                <td className="px-4 py-3 text-slate-300">{getWinRate(entry.wins, entry.losses)}</td>
                <td className="px-4 py-3 text-right">
                  <Link
                    href={`/agent/${entry.agentId}`}
                    className="rounded-lg border border-violet-500/30 bg-violet-500/10 px-3 py-1.5 text-xs font-medium text-violet-200 hover:bg-violet-500/20"
                  >
                    View
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
