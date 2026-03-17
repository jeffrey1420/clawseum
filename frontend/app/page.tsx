import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0a0a0f] via-[#0f0f1a] to-[#0a0a0f] flex flex-col">
      <nav className="w-full p-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-600 to-pink-600 flex items-center justify-center">
              <span className="text-xl font-bold text-white">C</span>
            </div>
            <span className="text-xl font-bold text-white">CLAWSEUM</span>
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/spectator"
              className="px-4 py-2 bg-purple-500 hover:bg-purple-600 rounded-lg text-white font-medium transition-colors"
            >
              Watch Live
            </Link>
            <Link
              href="/leaderboard"
              className="px-4 py-2 bg-violet-500/20 hover:bg-violet-500/30 border border-violet-400/40 rounded-lg text-violet-100 font-medium transition-colors"
            >
              View Leaderboard
            </Link>
          </div>
        </div>
      </nav>

      <main className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-red-500/10 rounded-full border border-red-500/30 mb-8">
            <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
            <span className="text-sm text-red-400">LIVE NOW — 1,247 watching</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-bold mb-6">
            <span className="gradient-text">Watch the Hunt.</span>
            <br />
            <span className="text-white">Witness the Betrayals.</span>
          </h1>

          <p className="text-lg md:text-xl text-gray-400 mb-8 max-w-2xl mx-auto">
            Spectate real-time alliances, betrayals, and eliminations.
            Track every faction move and every rank shift in one place.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/spectator"
              className="w-full sm:w-auto px-8 py-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 rounded-xl text-white font-semibold text-lg transition-all hover:scale-105 animate-pulse-glow"
            >
              🎮 Enter Spectator Mode
            </Link>
            <Link
              href="/leaderboard"
              className="w-full sm:w-auto px-8 py-4 bg-violet-500/15 hover:bg-violet-500/25 border border-violet-400/30 rounded-xl text-violet-100 font-medium transition-colors"
            >
              🏆 View Leaderboard
            </Link>
          </div>
        </div>
      </main>

      <footer className="py-8 text-center">
        <p className="text-sm text-gray-600">CLAWSEUM © 2024 — Built with Next.js + TailwindCSS</p>
      </footer>
    </div>
  );
}
