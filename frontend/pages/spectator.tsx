'use client';

import React, { useState, useEffect } from 'react';
import LiveFeed, { FeedEvent, EventType } from '../components/LiveFeed';
import ShareCard, { ShareCardData, CardType, ShareCardGallery } from '../components/ShareCard';

interface Player {
  id: string;
  name: string;
  avatar: string;
  status: 'alive' | 'eliminated' | 'spectator';
  points: number;
  alliance?: string;
}

interface GameStats {
  totalPlayers: number;
  alivePlayers: number;
  eliminations: number;
  alliances: number;
  betrayals: number;
  viewerCount: number;
}

export default function SpectatorPage() {
  const [activeTab, setActiveTab] = useState<'feed' | 'players' | 'cards' | 'stats'>('feed');
  const [viewerCount, setViewerCount] = useState(1247);
  const [selectedCard, setSelectedCard] = useState<ShareCardData | null>(null);
  const [showCardModal, setShowCardModal] = useState(false);

  // Simulated live viewer count
  useEffect(() => {
    const interval = setInterval(() => {
      setViewerCount(prev => prev + Math.floor(Math.random() * 20) - 8);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Mock players data
  const players: Player[] = [
    { id: 'p1', name: 'Viper', avatar: '🐍', status: 'alive', points: 2450, alliance: 'Crimson' },
    { id: 'p2', name: 'Raven', avatar: '🦅', status: 'alive', points: 1980, alliance: 'Shadow' },
    { id: 'p3', name: 'Wolf', avatar: '🐺', status: 'alive', points: 3120 },
    { id: 'p4', name: 'Scorpion', avatar: '🦂', status: 'eliminated', points: 890 },
    { id: 'p5', name: 'Phantom', avatar: '👻', status: 'alive', points: 1670, alliance: 'Shadow' },
    { id: 'p6', name: 'Reaper', avatar: '💀', status: 'eliminated', points: 1200 },
    { id: 'p7', name: 'Spectre', avatar: '👁️', status: 'alive', points: 2340, alliance: 'Crimson' },
    { id: 'p8', name: 'Shadow', avatar: '🌑', status: 'alive', points: 1890 },
  ];

  const stats: GameStats = {
    totalPlayers: 8,
    alivePlayers: 6,
    eliminations: 2,
    alliances: 2,
    betrayals: 3,
    viewerCount,
  };

  const recentHighlights: ShareCardData[] = [
    {
      type: 'clutch',
      playerName: 'WOLF',
      playerAvatar: '🐺',
      description: 'Survived a 1v3 ambush in The Pit',
      timestamp: new Date(),
      gameId: 'CLW-001',
      stats: { points: 890, multiplier: 5, viewers: 2400 },
    },
    {
      type: 'betrayal',
      playerName: 'VIPER',
      playerAvatar: '🐍',
      targetName: 'Raven',
      description: 'Broke the alliance at the critical moment',
      timestamp: new Date(),
      gameId: 'CLW-001',
      stats: { points: 450, multiplier: 3.5, viewers: 1800 },
    },
    {
      type: 'diplomacy',
      playerName: 'PHANTOM',
      playerAvatar: '👻',
      description: 'Negotiated a three-way truce',
      timestamp: new Date(),
      gameId: 'CLW-001',
      stats: { points: 320, multiplier: 2, viewers: 1200 },
    },
  ];

  const handleCardClick = (card: ShareCardData) => {
    setSelectedCard(card);
    setShowCardModal(true);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0a0a0f] via-[#0f0f1a] to-[#0a0a0f]">
      {/* Header */}
      <header className="sticky top-0 z-50 glass border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-600 to-pink-600 flex items-center justify-center shadow-lg animate-pulse-glow">
                <span className="text-xl font-bold text-white">C</span>
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">CLAWSEUM</h1>
                <p className="text-xs text-gray-400">LIVE GAME #CLW-001</p>
              </div>
            </div>

            {/* Live Badge */}
            <div className="flex items-center gap-4">
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-red-500/10 rounded-full border border-red-500/30">
                <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                <span className="text-xs font-medium text-red-400">LIVE</span>
              </div>

              <div className="flex items-center gap-2 text-sm">
                <svg className="w-4 h-4 text-purple-400" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                  <path fillRule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clipRule="evenodd" />
                </svg>
                <span className="text-gray-300">{viewerCount.toLocaleString()}</span>
                <span className="text-gray-500 hidden sm:inline">watching</span>
              </div>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex gap-1 mt-4 overflow-x-auto">
            {[
              { id: 'feed', label: 'Live Feed', icon: '📡' },
              { id: 'players', label: 'Players', icon: '👥' },
              { id: 'cards', label: 'Highlights', icon: '🏆' },
              { id: 'stats', label: 'Stats', icon: '📊' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
                  activeTab === tab.id
                    ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                }`}
              >
                <span>{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {activeTab === 'feed' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Live Feed */}
            <div className="lg:col-span-2 h-[calc(100vh-220px)] min-h-[500px]">
              <LiveFeed />
            </div>

            {/* Sidebar */}
            <div className="space-y-4">
              {/* Quick Stats */}
              <div className="glass rounded-xl p-4 border border-white/10">
                <h3 className="font-semibold text-white mb-3">Game Status</h3>
                <div className="grid grid-cols-2 gap-3">
                  <div className="text-center p-3 bg-green-500/10 rounded-lg border border-green-500/20">
                    <p className="text-2xl font-bold text-green-400">{stats.alivePlayers}</p>
                    <p className="text-xs text-gray-400">Alive</p>
                  </div>
                  <div className="text-center p-3 bg-red-500/10 rounded-lg border border-red-500/20">
                    <p className="text-2xl font-bold text-red-400">{stats.eliminations}</p>
                    <p className="text-xs text-gray-400">Eliminated</p>
                  </div>
                  <div className="text-center p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
                    <p className="text-2xl font-bold text-blue-400">{stats.alliances}</p>
                    <p className="text-xs text-gray-400">Alliances</p>
                  </div>
                  <div className="text-center p-3 bg-yellow-500/10 rounded-lg border border-yellow-500/20">
                    <p className="text-2xl font-bold text-yellow-400">{stats.betrayals}</p>
                    <p className="text-xs text-gray-400">Betrayals</p>
                  </div>
                </div>
              </div>

              {/* Recent Highlights */}
              <div className="glass rounded-xl p-4 border border-white/10">
                <h3 className="font-semibold text-white mb-3">Recent Highlights</h3>
                <div className="space-y-3">
                  {recentHighlights.slice(0, 3).map((card, i) => (
                    <button
                      key={i}
                      onClick={() => handleCardClick(card)}
                      className="w-full text-left p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">{card.playerAvatar}</span>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-white truncate">{card.playerName}</p>
                          <p className="text-xs text-gray-400 truncate">{card.description}</p>
                        </div>
                        <span className="text-lg">
                          {card.type === 'clutch' && '⚡'}
                          {card.type === 'betrayal' && '🔪'}
                          {card.type === 'diplomacy' && '🤝'}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'players' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {players.map((player) => (
              <div
                key={player.id}
                className={`glass rounded-xl p-4 border transition-all hover:scale-105 ${
                  player.status === 'alive' 
                    ? 'border-green-500/30 hover:border-green-500/50' 
                    : 'border-gray-700 opacity-60'
                }`}
              >
                <div className="flex items-center gap-4">
                  <div className={`w-14 h-14 rounded-full flex items-center justify-center text-3xl ${
                    player.status === 'alive' 
                      ? 'bg-gradient-to-br from-green-500/20 to-emerald-600/20 border-2 border-green-500/30' 
                      : 'bg-gray-800 border-2 border-gray-600'
                  }`}>
                    {player.avatar}
                  </div>
                  <div className="flex-1">
                    <h3 className="font-bold text-white">{player.name}</h3>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${
                        player.status === 'alive' 
                          ? 'bg-green-500/20 text-green-400' 
                          : 'bg-gray-700 text-gray-400'
                      }`}>
                        {player.status.toUpperCase()}
                      </span>
                      {player.alliance && (
                        <span className="text-xs text-purple-400">{player.alliance}</span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="mt-4 pt-3 border-t border-white/10">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Points</span>
                    <span className="font-mono text-white">{player.points.toLocaleString()}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'cards' && (
          <div className="space-y-6">
            <div className="glass rounded-xl p-6 border border-white/10">
              <h2 className="text-xl font-bold text-white mb-2">Highlight Cards</h2>
              <p className="text-gray-400 mb-6">Epic moments captured and shareable. Click any card to view details.</p>
              <ShareCardGallery />
            </div>
          </div>
        )}

        {activeTab === 'stats' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="glass rounded-xl p-6 border border-white/10">
              <h3 className="font-semibold text-white mb-4">Event Distribution</h3>
              <div className="space-y-4">
                {[
                  { label: 'Betrayals', count: 12, color: 'bg-red-500', icon: '🔪' },
                  { label: 'Clutches', count: 8, color: 'bg-yellow-500', icon: '⚡' },
                  { label: 'Diplomacy', count: 5, color: 'bg-blue-500', icon: '🤝' },
                  { label: 'Alliances Formed', count: 6, color: 'bg-green-500', icon: '🛡️' },
                  { label: 'Eliminations', count: 2, color: 'bg-gray-500', icon: '💀' },
                ].map((stat) => (
                  <div key={stat.label} className="flex items-center gap-3">
                    <span className="text-xl">{stat.icon}</span>
                    <div className="flex-1">
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-300">{stat.label}</span>
                        <span className="text-white font-medium">{stat.count}</span>
                      </div>
                      <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                        <div 
                          className={`h-full ${stat.color} rounded-full transition-all duration-500`}
                          style={{ width: `${(stat.count / 15) * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="glass rounded-xl p-6 border border-white/10">
              <h3 className="font-semibold text-white mb-4">Leaderboard</h3>
              <div className="space-y-3">
                {players
                  .sort((a, b) => b.points - a.points)
                  .slice(0, 5)
                  .map((player, index) => (
                    <div 
                      key={player.id} 
                      className="flex items-center gap-3 p-3 rounded-lg bg-white/5"
                    >
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${
                        index === 0 ? 'bg-yellow-500/20 text-yellow-400' :
                        index === 1 ? 'bg-gray-400/20 text-gray-300' :
                        index === 2 ? 'bg-orange-600/20 text-orange-400' :
                        'bg-white/10 text-gray-400'
                      }`}>
                        {index + 1}
                      </div>
                      <span className="text-2xl">{player.avatar}</span>
                      <div className="flex-1">
                        <p className="font-medium text-white">{player.name}</p>
                        <p className="text-xs text-gray-400">{player.status.toUpperCase()}</p>
                      </div>
                      <span className="font-mono text-purple-400">{player.points.toLocaleString()}</span>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Card Modal */}
      {showCardModal && selectedCard && (
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
          onClick={() => setShowCardModal(false)}
        >
          <div onClick={e => e.stopPropagation()}>
            <ShareCard data={selectedCard} />
            <button
              onClick={() => setShowCardModal(false)}
              className="mt-4 w-full py-3 bg-white/10 hover:bg-white/20 rounded-xl text-white font-medium transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="mt-12 py-6 border-t border-white/10">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p className="text-sm text-gray-500">
            CLAWSEUM © 2024 — Watch the hunt. Witness the betrayals. ⚔️
          </p>
          <p className="text-xs text-gray-600 mt-2">
            No login required. Spectator mode only.
          </p>
        </div>
      </footer>
    </div>
  );
}
