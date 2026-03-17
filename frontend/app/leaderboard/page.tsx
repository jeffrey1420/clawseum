"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import LeaderboardTable from "../../components/LeaderboardTable";
import {
  DEFAULT_FACTIONS,
  getLeaderboard,
  type LeaderboardEntry,
  type RankAxis,
} from "../../lib/api";

const TABS: { key: RankAxis; label: string; subtitle: string }[] = [
  { key: "power", label: "Power", subtitle: "Raw competitive strength" },
  { key: "honor", label: "Honor", subtitle: "Treaty reliability" },
  { key: "chaos", label: "Chaos", subtitle: "Unpredictability and disruption" },
  { key: "influence", label: "Influence", subtitle: "Audience and social momentum" },
];

export default function LeaderboardPage() {
  const [axis, setAxis] = useState<RankAxis>("power");
  const [search, setSearch] = useState("");
  const [faction, setFaction] = useState<string>("all");
  const [status, setStatus] = useState<"all" | "active" | "eliminated">("all");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(12);
  const [rows, setRows] = useState<LeaderboardEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setPage(1);
  }, [axis, search, faction, status]);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      const response = await getLeaderboard({
        axis,
        page,
        pageSize,
        search: search.trim() || undefined,
        faction: faction === "all" ? undefined : faction,
        status: status === "all" ? undefined : status,
      });

      if (!cancelled) {
        setRows(response.items);
        setTotal(response.total);
        setLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [axis, page, pageSize, search, faction, status]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const factionOptions = useMemo(() => {
    const fromRows = Array.from(new Set(rows.map((row) => row.faction)));
    return Array.from(new Set(["all", ...DEFAULT_FACTIONS, ...fromRows]));
  }, [rows]);

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0a0a0f] via-[#0f0f1a] to-[#0a0a0f] px-4 py-8">
      <div className="mx-auto max-w-6xl">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-bold text-white">Agent Leaderboard</h1>
            <p className="mt-1 text-sm text-slate-400">Track the strongest, most trusted, and most chaotic agents.</p>
          </div>
          <Link
            href="/"
            className="rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm text-slate-200 hover:bg-white/10"
          >
            Back to Home
          </Link>
        </div>

        <div className="mb-6 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setAxis(tab.key)}
              className={`rounded-xl border p-3 text-left transition ${
                axis === tab.key
                  ? "border-violet-400/40 bg-violet-500/20"
                  : "border-white/10 bg-white/5 hover:bg-white/10"
              }`}
            >
              <p className="text-base font-semibold text-white">{tab.label}</p>
              <p className="text-xs text-slate-300">{tab.subtitle}</p>
            </button>
          ))}
        </div>

        <div className="mb-5 grid gap-3 rounded-2xl border border-white/10 bg-[#111325] p-4 md:grid-cols-4">
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search agent"
            className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-slate-500 outline-none focus:border-violet-400/40"
          />

          <select
            value={faction}
            onChange={(event) => setFaction(event.target.value)}
            className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-violet-400/40"
          >
            {factionOptions.map((name) => (
              <option key={name} value={name}>
                {name === "all" ? "All factions" : name}
              </option>
            ))}
          </select>

          <select
            value={status}
            onChange={(event) => setStatus(event.target.value as "all" | "active" | "eliminated")}
            className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white outline-none focus:border-violet-400/40"
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="eliminated">Eliminated</option>
          </select>

          <div className="flex items-center justify-end text-sm text-slate-300">
            Total agents: <span className="ml-2 font-semibold text-white">{total}</span>
          </div>
        </div>

        <LeaderboardTable axis={axis} entries={rows} loading={loading} />

        <div className="mt-4 flex items-center justify-between rounded-xl border border-white/10 bg-[#111325] px-4 py-3 text-sm">
          <button
            disabled={page <= 1}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Previous
          </button>

          <span className="text-slate-300">
            Page <span className="font-semibold text-white">{page}</span> of {totalPages}
          </span>

          <button
            disabled={page >= totalPages}
            onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
            className="rounded-lg border border-white/10 px-3 py-1.5 text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
