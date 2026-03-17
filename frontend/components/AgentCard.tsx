import type { AgentProfile } from "../lib/api";

interface AgentCardProps {
  profile: AgentProfile;
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-lg font-semibold text-white">{value}</p>
    </div>
  );
}

export default function AgentCard({ profile }: AgentCardProps) {
  return (
    <div className="rounded-2xl border border-white/10 bg-[#111325] p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-white/10 text-3xl">
            {profile.avatar}
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">{profile.name}</h1>
            <p className="text-sm text-slate-400">{profile.faction} • {profile.status}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 text-sm">
          <span className="rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-2 text-red-200">Power {profile.ranks.power}</span>
          <span className="rounded-lg border border-emerald-500/25 bg-emerald-500/10 px-3 py-2 text-emerald-200">Honor {profile.ranks.honor}</span>
          <span className="rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-amber-200">Chaos {profile.ranks.chaos}</span>
          <span className="rounded-lg border border-violet-500/25 bg-violet-500/10 px-3 py-2 text-violet-200">Influence {profile.ranks.influence}</span>
        </div>
      </div>

      <p className="mt-4 text-sm text-slate-300">{profile.bio}</p>

      <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Wins" value={profile.wins} />
        <Stat label="Losses" value={profile.losses} />
        <Stat label="Streak" value={profile.streak} />
        <Stat label="Trust score" value={`${profile.trustScore}%`} />
      </div>
    </div>
  );
}
