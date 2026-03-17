import type { RankAxis } from "../lib/api";

interface RankBadgeProps {
  rank: number;
  previousRank?: number;
  axis: RankAxis;
}

const AXIS_STYLES: Record<RankAxis, string> = {
  power: "bg-red-500/15 text-red-300 border-red-500/30",
  honor: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  chaos: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  influence: "bg-violet-500/15 text-violet-300 border-violet-500/30",
};

export default function RankBadge({ rank, previousRank, axis }: RankBadgeProps) {
  const movement = previousRank ? previousRank - rank : 0;
  const movementLabel = movement > 0 ? `▲${movement}` : movement < 0 ? `▼${Math.abs(movement)}` : "•";
  const movementColor = movement > 0 ? "text-emerald-300" : movement < 0 ? "text-red-300" : "text-slate-400";

  return (
    <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${AXIS_STYLES[axis]}`}>
      <span>#{rank}</span>
      <span className={movementColor}>{movementLabel}</span>
    </div>
  );
}
