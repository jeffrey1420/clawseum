'use client';

import React, { useRef } from 'react';

export type CardType = 'betrayal' | 'clutch' | 'diplomacy';

export interface ShareCardData {
  type: CardType;
  playerName: string;
  playerAvatar?: string;
  targetName?: string;
  description: string;
  timestamp: Date;
  gameId: string;
  stats?: {
    points?: number;
    multiplier?: number;
    viewers?: number;
  };
}

interface ShareCardProps {
  data: ShareCardData;
  onDownload?: () => void;
  onShare?: () => void;
  className?: string;
}

const cardConfig: Record<CardType, {
  gradient: string;
  accent: string;
  icon: string;
  title: string;
  subtitle: string;
}> = {
  betrayal: {
    gradient: 'from-red-900/80 via-red-800/60 to-rose-900/80',
    accent: 'text-red-400',
    icon: '🔪',
    title: 'BETRAYAL',
    subtitle: 'Trust is a weapon',
  },
  clutch: {
    gradient: 'from-amber-900/80 via-yellow-800/60 to-orange-900/80',
    accent: 'text-yellow-400',
    icon: '⚡',
    title: 'CLUTCH',
    subtitle: 'Against all odds',
  },
  diplomacy: {
    gradient: 'from-blue-900/80 via-indigo-800/60 to-cyan-900/80',
    accent: 'text-blue-400',
    icon: '🤝',
    title: 'DIPLOMACY',
    subtitle: 'Words win wars',
  },
};

// Sample data for demo purposes
export const sampleCards: ShareCardData[] = [
  {
    type: 'betrayal',
    playerName: 'VIPER',
    playerAvatar: '🐍',
    targetName: 'RAVEN',
    description: 'Backstabbed their alliance partner moments before victory',
    timestamp: new Date(),
    gameId: 'CLW-2024-001',
    stats: { points: 450, multiplier: 3.5, viewers: 1247 },
  },
  {
    type: 'clutch',
    playerName: 'WOLF',
    playerAvatar: '🐺',
    targetName: 'THE PIT',
    description: 'Escaped a 1v4 situation with 3 seconds remaining',
    timestamp: new Date(),
    gameId: 'CLW-2024-001',
    stats: { points: 890, multiplier: 5.0, viewers: 2856 },
  },
  {
    type: 'diplomacy',
    playerName: 'PHANTOM',
    playerAvatar: '👻',
    targetName: 'SCORPION',
    description: 'Negotiated a truce that eliminated three other players',
    timestamp: new Date(),
    gameId: 'CLW-2024-001',
    stats: { points: 320, multiplier: 2.0, viewers: 892 },
  },
];

export default function ShareCard({ data, onDownload, onShare, className = '' }: ShareCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const config = cardConfig[data.type];

  const handleDownload = () => {
    // In a real implementation, this would use html2canvas or similar
    console.log('Downloading card:', data);
    onDownload?.();
  };

  const handleShare = () => {
    const shareText = `${config.icon} ${data.playerName} just pulled off a ${config.title} in CLAWSEUM!\n\n"${data.description}"\n\nWatch live: clawseum.game/watch/${data.gameId}`;
    
    if (navigator.share) {
      navigator.share({
        title: `${data.playerName}'s ${config.title} in CLAWSEUM`,
        text: shareText,
        url: `https://clawseum.game/watch/${data.gameId}`,
      });
    } else {
      navigator.clipboard.writeText(shareText);
      console.log('Copied to clipboard');
    }
    onShare?.();
  };

  return (
    <div className={`group ${className}`}>
      {/* Card Container */}
      <div
        ref={cardRef}
        className={`relative w-full max-w-sm mx-auto overflow-hidden rounded-2xl bg-gradient-to-br ${config.gradient} border border-white/20 shadow-2xl`}
      >
        {/* Background Pattern */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute inset-0" style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.4'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }} /&gt;
        </div>

        {/* Header */}
        <div className="relative p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-3xl">{config.icon}</span>
              <div>
                <h4 className={`text-sm font-bold tracking-wider ${config.accent}`}>{config.title}</h4>
                <p className="text-xs text-white/60">{config.subtitle}</p>
              </div>
            </div>
            <div className="text-right">
              <span className="text-xs text-white/40 font-mono">{data.gameId}</span>
            </div>
          </div>
        </div>

        {/* Main Content */}
        㰶 className="relative px-6 pb-6"㸾
          <div className="glass rounded-xl p-5 border border-white/10">
            {/* Player */}
            <div className="flex items-center gap-4 mb-4">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-white/20 to-white/5 flex items-center justify-center text-4xl border-2 border-white/20 animate-pulse-glow">
                {data.playerAvatar || config.icon}
              </div>
              <div>
                <h3 className="text-2xl font-bold text-white">{data.playerName}</h3>
                {data.targetName && (
                  <p className="text-sm text-white/60">Target: <span className="text-white font-medium">{data.targetName}</span></p>
                )}
              </div>
            </div>

            {/* Description */}
            <div className="bg-black/20 rounded-lg p-4 mb-4">
              <p className="text-sm text-white/90 italic leading-relaxed">
                "{data.description}"
              </p>
            </div>

            {/* Stats */}
            {data.stats && (
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center p-2 bg-black/20 rounded-lg">
                  <p className="text-xs text-white/50">POINTS</p>
                  <p className="text-lg font-bold text-white">{data.stats.points?.toLocaleString()}</p>
                </div>
                <div className="text-center p-2 bg-black/20 rounded-lg">
                  <p className="text-xs text-white/50">MULTIPLIER</p>
                  <p className="text-lg font-bold text-yellow-400">×{data.stats.multiplier}</p>
                </div>
                <div className="text-center p-2 bg-black/20 rounded-lg">
                  <p className="text-xs text-white/50">VIEWERS</p>
                  <p className="text-lg font-bold text-purple-400">{data.stats.viewers?.toLocaleString()}</p>
                </div>
              </div>
            )}
          </div>

          {/* Branding */}
          <div className="mt-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-xs font-bold">
                C
              </div>
              <span className="text-sm font-semibold text-white">CLAWSEUM</span>
            </div>
            <span className="text-xs text-white/40">
              {data.timestamp.toLocaleDateString()}
            </span>
          </div>
        </div>

        {/* Decorative Elements */}
        <div className="absolute -top-20 -right-20 w-40 h-40 bg-white/5 rounded-full blur-3xl" />
        <div className="absolute -bottom-20 -left-20 w-40 h-40 bg-black/20 rounded-full blur-3xl" />
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3 mt-4 justify-center">
        <button
          onClick={handleDownload}
          className="flex items-center gap-2 px-4 py-2 bg-white/10 hover:bg-white/20 rounded-full text-sm font-medium text-white transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          Save
        </button>
        <button
          onClick={handleShare}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 rounded-full text-sm font-medium text-white transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
          </svg>
          Share
        </button>
      </div>
    </div>
  );
}

// Gallery component to showcase all card types
export function ShareCardGallery({ className = '' }: { className?: string }) {
  return (
    <div className={`grid grid-cols-1 md:grid-cols-3 gap-6 ${className}`}>
      {sampleCards.map((card, index) => (
        <ShareCard key={index} data={card} />
      ))}
    </div>
  );
}
