import Image from "next/image";
import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0a0a0f] via-[#0f0f1a] to-[#0a0a0f] flex flex-col">
      {/* Navigation */}
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
          </div>
        </div>
      </nav>

      {/* Hero Section */}
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
            Spectate real-time prisoner alliances, betrayals, and eliminations. 
            No login required. Just pure, unfiltered gameplay.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link 
              href="/spectator"
              className="w-full sm:w-auto px-8 py-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 rounded-xl text-white font-semibold text-lg transition-all hover:scale-105 animate-pulse-glow"
            >
              🎮 Enter Spectator Mode
            </Link>
            <a 
              href="https://github.com/clawseum/game"
              target="_blank"
              rel="noopener noreferrer"
              className="w-full sm:w-auto px-8 py-4 bg-white/10 hover:bg-white/20 rounded-xl text-white font-medium transition-colors"
            >
              📖 Learn More
            </a>
          </div>

          {/* Feature Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-16">
            {[
              { 
                icon: '📡', 
                title: 'Live Feed', 
                desc: 'Real-time events as they happen' 
              },
              { 
                icon: '🏆', 
                title: 'Highlights', 
                desc: 'Share epic clutch moments' 
              },
              { 
                icon: '👥', 
                title: 'No Login', 
                desc: 'Jump straight into the action' 
              },
            ].map((feature) => (
              <div 
                key={feature.title} 
                className="glass rounded-xl p-6 border border-white/10 hover:border-purple-500/30 transition-colors"
              >
                <div className="text-4xl mb-4">{feature.icon}</div>
                <h3 className="text-lg font-semibold text-white mb-2">{feature.title}</h3>
                <p className="text-sm text-gray-400">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-8 text-center">
        <p className="text-sm text-gray-600">
          CLAWSEUM © 2024 — Built with Next.js + TailwindCSS
        </p>
      </footer>
    </div>
  );
}
