'use client';

import React, { useState, useEffect, useRef } from 'react';

export type EventType = 'betrayal' | 'clutch' | 'diplomacy' | 'elimination' | 'alliance' | 'vote';

export interface FeedEvent {
  id: string;
  type: EventType;
  timestamp: Date;
  prisonerId: string;
  prisonerName: string;
  prisonerAvatar?: string;
  targetId?: string;
  targetName?: string;
  description: string;
  value?: number;
  roomName?: string;
}

interface LiveFeedProps {
  events?: FeedEvent[];
  maxEvents?: number;
  autoScroll?: boolean;
  className?: string;
}

const eventIcons: Record<EventType, string> = {
  betrayal: '🔪',
  clutch: '⚡',
  diplomacy: '🤝',
  elimination: '💀',
  alliance: '🛡️',
  vote: '🗳️',
};

const eventColors: Record<EventType, string> = {
  betrayal: 'text-red-400 bg-red-500/10 border-red-500/30',
  clutch: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
  diplomacy: 'text-blue-400 bg-blue-500/10 border-blue-500/30',
  elimination: 'text-gray-400 bg-gray-500/10 border-gray-500/30',
  alliance: 'text-green-400 bg-green-500/10 border-green-500/30',
  vote: 'text-purple-400 bg-purple-500/10 border-purple-500/30',
};

const eventLabels: Record<EventType, string> = {
  betrayal: 'BETRAYAL',
  clutch: 'CLUTCH',
  diplomacy: 'DIPLOMACY',
  elimination: 'ELIMINATED',
  alliance: 'ALLIANCE',
  vote: 'VOTE',
};

// Mock data generator
export const generateMockEvents = (count: number = 10): FeedEvent[] => {
  const prisoners = [
    { id: 'p1', name: 'Viper', avatar: '🐍' },
    { id: 'p2', name: 'Raven', avatar: '🦅' },
    { id: 'p3', name: 'Wolf', avatar: '🐺' },
    { id: 'p4', name: 'Scorpion', avatar: '🦂' },
    { id: 'p5', name: 'Phantom', avatar: '👻' },
    { id: 'p6', name: 'Reaper', avatar: '💀' },
    { id: 'p7', name: 'Spectre', avatar: '👁️' },
    { id: 'p8', name: 'Shadow', avatar: '🌑' },
  ];

  const rooms = ['The Pit', 'The Arena', 'Cell Block A', 'The Yard', 'Solitary', 'The Commons'];
  
  const descriptions: Record<EventType, string[]> = {
    betrayal: [
      'broke their alliance with',
      'backstabbed their trusted partner',
      'revealed secrets about',
      'sabotaged the plan of',
    ],
    clutch: [
      'won a 1v3 situation',
      'escaped certain death',
      'stole the key from right under',
      'made an impossible shot on',
    ],
    diplomacy: [
      'negotiated peace between rivals',
      'formed a secret pact with',
      'brokered a truce with',
      'convinced the guards to spare',
    ],
    elimination: [
      'was taken out by',
      'fell to the schemes of',
      'couldn\'t escape',
      'met their end at the hands of',
    ],
    alliance: [
      'swore loyalty to',
      'joined forces with',
      'formed an unbreakable bond with',
      'pledged protection to',
    ],
    vote: [
      'voted to eliminate',
      'cast suspicion on',
      'rallied votes against',
      'influenced the room to target',
    ],
  };

  return Array.from({ length: count }, (_, i) => {
    const type = Object.keys(descriptions)[Math.floor(Math.random() * 6)] as EventType;
    const prisoner = prisoners[Math.floor(Math.random() * prisoners.length)];
    const target = prisoners[Math.floor(Math.random() * prisoners.length)];
    const desc = descriptions[type][Math.floor(Math.random() * descriptions[type].length)];
    
    return {
      id: `evt-${Date.now()}-${i}`,
      type,
      timestamp: new Date(Date.now() - i * 30000),
      prisonerId: prisoner.id,
      prisonerName: prisoner.name,
      prisonerAvatar: prisoner.avatar,
      targetId: target.id === prisoner.id ? undefined : target.id,
      targetName: target.id === prisoner.id ? undefined : target.name,
      description: desc,
      value: type === 'betrayal' ? Math.floor(Math.random() * 500) : undefined,
      roomName: rooms[Math.floor(Math.random() * rooms.length)],
    };
  });
};

const formatTime = (date: Date): string => {
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const seconds = Math.floor(diff / 1000);
  
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  return `${Math.floor(seconds / 3600)}h ago`;
};

export default function LiveFeed({ 
  events: initialEvents, 
  maxEvents = 50, 
  autoScroll = true,
  className = '' 
}: LiveFeedProps) {
  const [events, setEvents] = useState<FeedEvent[]>(initialEvents || generateMockEvents(15));
  const [isLive, setIsLive] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Simulate real-time updates
  useEffect(() => {
    if (!isLive) return;

    const interval = setInterval(() => {
      setEvents(prev => {
        const newEvent = generateMockEvents(1)[0];
        newEvent.timestamp = new Date();
        newEvent.id = `evt-${Date.now()}`;
        const updated = [newEvent, ...prev].slice(0, maxEvents);
        return updated;
      });
    }, 3500);

    return () => clearInterval(interval);
  }, [isLive, maxEvents]);

  // Auto-scroll to top when new events arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [events, autoScroll]);

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 glass border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className={`w-2 h-2 rounded-full ${isLive ? 'bg-red-500 animate-pulse' : 'bg-gray-500'}`} />
          <h3 className="font-semibold text-white">LIVE FEED</h3>
          <span className="text-xs text-gray-400">{events.length} events</span>
        </div>
        <button
          onClick={() => setIsLive(!isLive)}
          className={`text-xs px-3 py-1 rounded-full transition-colors ${
            isLive 
              ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30' 
              : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
          }`}
        >
          {isLive ? '● LIVE' : '⏸ PAUSED'}
        </button>
      </div>

      {/* Event List */}
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto overflow-x-hidden"
      >
        <div className="p-2 space-y-2">
          {events.map((event, index) => (
            <div
              key={event.id}
              className={`animate-slide-in group relative p-3 rounded-xl border transition-all hover:scale-[1.02] ${eventColors[event.type]}`}
              style={{ animationDelay: `${index * 50}ms` }}
            >
              {/* Event Header */}
              <div className="flex items-start gap-3">
                {/* Avatar */}
                <div className="w-10 h-10 rounded-full bg-black/30 flex items-center justify-center text-lg shrink-0">
                  {event.prisonerAvatar || eventIcons[event.type]}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-white truncate">{event.prisonerName}</span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-black/30 font-medium">
                      {eventLabels[event.type]}
                    </span>
                    <span className="text-xs text-gray-400 ml-auto">{formatTime(event.timestamp)}</span>
                  </div>

                  <p className="text-sm text-gray-300 mt-1">
                    {event.description}
                    {event.targetName && (
                      <span className="font-medium text-white"> {event.targetName}</span>
                    )}
                  </p>

                  {/* Footer Info */}
                  <div className="flex items-center gap-3 mt-2 text-xs">
                    {event.roomName && (
                      <span className="text-gray-500">📍 {event.roomName}</span>
                    )}
                    {event.value && event.value > 0 && (
                      <span className="text-yellow-400 font-medium">+{event.value} pts</span>
                    )}
                  </div>
                </div>

                {/* Type Icon */}
                <div className="text-2xl opacity-50 group-hover:opacity-100 transition-opacity">
                  {eventIcons[event.type]}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer Stats */}
      <div className="px-4 py-3 glass border-t border-white/10">
        <div className="flex items-center justify-between text-xs">
          <div className="flex gap-4">
            <span className="text-red-400">🔪 {events.filter(e => e.type === 'betrayal').length} Betrayals</span>
            <span className="text-yellow-400">⚡ {events.filter(e => e.type === 'clutch').length} Clutches</span>
            <span className="text-blue-400">🤝 {events.filter(e => e.type === 'diplomacy').length} Deals</span>
          </div>
          <span className="text-gray-500">Auto-refresh: 3.5s</span>
        </div>
      </div>
    </div>
  );
}
