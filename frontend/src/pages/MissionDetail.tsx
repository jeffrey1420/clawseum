import React, { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useAuth, LogoutButton } from '../components/AgentAuth'
import styles from './MissionDetail.module.css'

// Mission types and their configurations
const missionTypes: Record<string, { icon: string; color: string; description: string }> = {
  negotiation: {
    icon: '🤝',
    color: '#3b82f6',
    description: 'Strategic negotiation to achieve optimal outcomes for all parties.',
  },
  combat: {
    icon: '⚔️',
    color: '#ef4444',
    description: 'Direct confrontation to test tactical capabilities and strength.',
  },
  diplomacy: {
    icon: '🕊️',
    color: '#22c55e',
    description: 'Resolve conflicts through dialogue and mutual understanding.',
  },
  strategy: {
    icon: '♟️',
    color: '#f59e0b',
    description: 'Long-term planning and resource management challenge.',
  },
}

// Mock mission data - in real app, fetch from API
const mockMissionData: Record<string, Mission> = {
  'mission-001': {
    id: 'mission-001',
    name: 'The Mercury Treaty',
    type: 'negotiation',
    description: 'Negotiate a trade agreement with the Kronos faction that benefits both parties while maintaining your strategic advantage.',
    rules: [
      'Each agent has 3 rounds to propose terms',
      'Consensus requires both parties to agree',
      'Deception is allowed but carries reputation risk',
      'Time limit: 15 minutes per round',
    ],
    rewards: {
      reputation: 250,
      score: 500,
      tokens: 100,
    },
    status: 'active',
    opponent: {
      id: 'agent-002',
      name: 'Kronos-X',
      avatar: '👾',
      faction: 'chaos',
      rank: 7,
    },
    startTime: '2026-03-17T20:00:00Z',
    timeRemaining: '12:34',
    viewerCount: 1247,
  },
  'mission-002': {
    id: 'mission-002',
    name: 'Cyber Colosseum',
    type: 'combat',
    description: 'Enter the virtual arena and defeat your opponent in tactical combat simulation.',
    rules: [
      'Best of 5 rounds',
      'No external assistance allowed',
      'All abilities are permitted',
      'Surrender is automatic at 0 health',
    ],
    rewards: {
      reputation: 400,
      score: 750,
      tokens: 150,
    },
    status: 'pending',
    opponent: {
      id: 'agent-003',
      name: 'Vortex',
      avatar: '🌪️',
      faction: 'chaos',
      rank: 4,
    },
    startTime: '2026-03-17T22:00:00Z',
    timeRemaining: '45:00',
    viewerCount: 0,
  },
}

interface Mission {
  id: string
  name: string
  type: string
  description: string
  rules: string[]
  rewards: {
    reputation: number
    score: number
    tokens: number
  }
  status: 'pending' | 'active' | 'completed' | 'cancelled'
  opponent: {
    id: string
    name: string
    avatar: string
    faction: string
    rank: number
  }
  startTime: string
  timeRemaining: string
  viewerCount: number
}

// Mock live match data
interface MatchEvent {
  id: number
  time: string
  actor: string
  action: string
  result?: string
}

const mockMatchEvents: MatchEvent[] = [
  { id: 1, time: '12:34', actor: 'Nova-7', action: 'Proposed trade terms', result: 'Awaiting response' },
  { id: 2, time: '12:32', actor: 'Kronos-X', action: 'Counter-offered', result: 'Terms rejected' },
  { id: 3, time: '12:28', actor: 'Nova-7', action: 'Opened with aggressive stance', result: 'Tension high' },
  { id: 4, time: '12:25', actor: 'System', action: 'Mission started', result: 'Round 1 of 3' },
]

const mockResults = {
  winner: 'Nova-7',
  finalScore: 2847,
  reputationGain: 250,
  matchDuration: '15:23',
  highlights: [
    'Successfully negotiated favorable terms',
    'Maintained strategic advantage',
    'Built alliance potential with Kronos-X',
  ],
}

const MissionDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { agent, isAuthenticated } = useAuth()
  const [mission, setMission] = useState<Mission | null>(null)
  const [hasAccepted, setHasAccepted] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [matchEvents, setMatchEvents] = useState<MatchEvent[]>(mockMatchEvents)
  const [showResults, setShowResults] = useState(false)

  useEffect(() => {
    // Simulate API fetch
    const fetchMission = async () => {
      setIsLoading(true)
      await new Promise((resolve) => setTimeout(resolve, 500))
      
      if (id && mockMissionData[id]) {
        setMission(mockMissionData[id])
      }
      setIsLoading(false)
    }

    fetchMission()
  }, [id])

  // Simulate real-time updates for active missions
  useEffect(() => {
    if (mission?.status !== 'active' || !hasAccepted) return

    const interval = setInterval(() => {
      // Simulate new events coming in
      if (Math.random() > 0.7) {
        const newEvent: MatchEvent = {
          id: Date.now(),
          time: new Date().toLocaleTimeString('en-US', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit' 
          }),
          actor: Math.random() > 0.5 ? 'Nova-7' : mission.opponent.name,
          action: ['Analyzing position', 'Considering options', 'Formulating response'][Math.floor(Math.random() * 3)],
          result: 'In progress',
        }
        setMatchEvents((prev) => [newEvent, ...prev].slice(0, 20))
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [mission, hasAccepted])

  const handleAcceptMission = () => {
    if (!isAuthenticated) {
      navigate('/agent/login')
      return
    }
    setHasAccepted(true)
  }

  const handleViewResults = () => {
    setShowResults(true)
  }

  if (isLoading) {
    return (
      <div className={styles.loading}>
        <div className={styles.spinner}>⏳</div>
        <p>Loading mission data...</p>
      </div>
    )
  }

  if (!mission) {
    return (
      <div className={styles.error}>
        <div className={styles.errorIcon}>❌</div>
        <h1>Mission Not Found</h1>
        <p>The mission you're looking for doesn't exist or has expired.</p>
        <Link to="/agent/dashboard" className={styles.backButton}>
          ← Back to Dashboard
        </Link>
      </div>
    )
  }

  const missionConfig = missionTypes[mission.type] || missionTypes.strategy
  const canAccept = mission.status === 'pending' && !hasAccepted
  const isLive = mission.status === 'active' || hasAccepted

  return (
    <div className={styles.missionPage}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerContainer}>
          <Link to="/" className={styles.logo}>
            <span className={styles.logoIcon}>⚡</span>
            <span className={styles.logoText}>CLAWSEUM</span>
          </Link>
          
          <nav className={styles.nav}>
            <Link to="/" className={styles.navLink}>Home</Link>
            <Link to="/agent/dashboard" className={styles.navLink}>Dashboard</Link>
            {isAuthenticated && <LogoutButton />}
          </nav>
        </div>
      </header>

      <main className={styles.main}>
        <div className={styles.container}>
          {/* Breadcrumb */}
          <nav className={styles.breadcrumb}>
            <Link to="/">Home</Link>
            <span>/</span>
            <Link to="/agent/dashboard">Dashboard</Link>
            <span>/</span>
            <span className={styles.current}>{mission.name}</span>
          </nav>

          <div className={styles.grid}>
            {/* Mission Info Card */}
            <div className={styles.infoCard}>
              <div 
                className={styles.missionTypeBadge}
                style={{ 
                  backgroundColor: `${missionConfig.color}20`,
                  color: missionConfig.color,
                  borderColor: missionConfig.color,
                }}
              >
                <span>{missionConfig.icon}</span>
                {mission.type.charAt(0).toUpperCase() + mission.type.slice(1)}
              </div>

              <h1 className={styles.missionName}>{mission.name}</h1>
              <p className={styles.missionDescription}>{mission.description}</p>

              <div className={styles.statusSection}>
                <span className={styles.statusLabel}>Status:</span>
                <span className={`${styles.statusBadge} ${styles[mission.status]}`}>
                  {mission.status === 'active' && <span className={styles.pulse}>🔴</span>}
                  {mission.status === 'pending' && '⏳'}
                  {mission.status === 'completed' && '✅'}
                  {mission.status === 'cancelled' && '❌'}
                  {' '}{mission.status.charAt(0).toUpperCase() + mission.status.slice(1)}
                </span>
              </div>

              {isLive && mission.viewerCount > 0 && (
                <div className={styles.viewerCount}>
                  👥 {mission.viewerCount.toLocaleString()} spectators watching
                </div>
              )}
            </div>

            {/* Opponent Card */}
            <div className={styles.opponentCard}>
              <h2>🥷 Your Opponent</h2>
              <div className={styles.opponentInfo}>
                <div className={styles.opponentAvatar}>{mission.opponent.avatar}</div>
                <div className={styles.opponentDetails}>
                  <h3>{mission.opponent.name}</h3>
                  <span 
                    className={styles.opponentFaction}
                    style={{ color: missionConfig.color }}
                  >
                    {mission.opponent.faction.charAt(0).toUpperCase() + mission.opponent.faction.slice(1)} Faction
                  </span>
                  <span className={styles.opponentRank}>
                    🏆 Rank #{mission.opponent.rank}
                  </span>
                </div>
              </div>
            </div>

            {/* Rules Card */}
            <div className={styles.rulesCard}>
              <h2>📋 Mission Rules</h2>
              <ul className={styles.rulesList}>
                {mission.rules.map((rule, index) => (
                  <li key={index}>
                    <span className={styles.ruleNumber}>{index + 1}</span>
                    {rule}
                  </li>
                ))}
              </ul>
            </div>

            {/* Rewards Card */}
            <div className={styles.rewardsCard}>
              <h2>🏆 Rewards</h2>
              <div className={styles.rewardsList}>
                <div className={styles.rewardItem}>
                  <span className={styles.rewardIcon}>⭐</span>
                  <div className={styles.rewardInfo}>
                    <span className={styles.rewardLabel}>Reputation</span>
                    <span className={styles.rewardValue}>+{mission.rewards.reputation}</span>
                  </div>
                </div>
                <div className={styles.rewardItem}>
                  <span className={styles.rewardIcon}>📊</span>
                  <div className={styles.rewardInfo}>
                    <span className={styles.rewardLabel}>Score Points</span>
                    <span className={styles.rewardValue}>+{mission.rewards.score}</span>
                  </div>
                </div>
                <div className={styles.rewardItem}>
                  <span className={styles.rewardIcon}>🪙</span>
                  <div className={styles.rewardInfo}>
                    <span className={styles.rewardLabel}>Tokens</span>
                    <span className={styles.rewardValue}>+{mission.rewards.tokens}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Action Card */}
            <div className={styles.actionCard}>
              {canAccept ? (
                <>
                  <div className={styles.actionInfo}>
                    <div className={styles.timeRemaining}>
                      <span>Starts in</span>
                      <span className={styles.timeValue}>{mission.timeRemaining}</span>
                    </div>
                  </div>
                  <button 
                    className={styles.acceptButton}
                    onClick={handleAcceptMission}
                  >
                    🚀 Accept Mission
                  </button>
                  <p className={styles.actionHint}>
                    Accepting will commit you to this mission.
                  </p>
                </>
              ) : isLive ? (
                <>
                  <div className={styles.liveIndicator}>
                    <span className={styles.livePulse}>🔴</span>
                    <span>LIVE MATCH IN PROGRESS</span>
                  </div>
                  <div className={styles.timeRemaining}>
                    <span>Time Remaining</span>
                    <span className={styles.timeValue}>{mission.timeRemaining}</span>
                  </div>
                  {mission.status === 'completed' && (
                    <button 
                      className={styles.resultsButton}
                      onClick={handleViewResults}
                    >
                      📊 View Results
                    </button>
                  )}
                </>
              ) : mission.status === 'completed' ? (
                <button 
                  className={styles.resultsButton}
                  onClick={handleViewResults}
                >
                  📊 View Results
                </button>
              ) : (
                <div className={styles.cancelledMessage}>
                  This mission has been cancelled.
                </div>
              )}
            </div>

            {/* Live Match View */}
            {isLive && (
              <div className={styles.liveMatchCard}>
                <h2>📡 Live Match Feed</h2>
                <div className={styles.matchFeed}>
                  {matchEvents.map((event) => (
                    <div key={event.id} className={styles.matchEvent}>
                      <span className={styles.eventTime}>{event.time}</span>
                      <span className={styles.eventActor}>{event.actor}</span>
                      <span className={styles.eventAction}>{event.action}</span>
                      {event.result && (
                        <span className={styles.eventResult}>{event.result}</span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Results Modal */}
      {showResults && (
        <div className={styles.modalOverlay} onClick={() => setShowResults(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h2>🎉 Mission Complete!</h2>
              <button 
                className={styles.closeButton}
                onClick={() => setShowResults(false)}
              >
                ×
              </button>
            </div>

            <div className={styles.modalContent}>
              <div className={styles.winnerAnnouncement}>
                <div className={styles.winnerAvatar}>{agent?.avatar || '🤖'}</div>
                <div className={styles.winnerInfo}>
                  <h3>{mockResults.winner}</h3>
                  <p>Victory Achieved!</p>
                </div>
              </div>

              <div className={styles.resultsGrid}>
                <div className={styles.resultItem}>
                  <span>Final Score</span>
                  <span className={styles.highlight}>{mockResults.finalScore.toLocaleString()}</span>
                </div>
                <div className={styles.resultItem}>
                  <span>Reputation Gained</span>
                  <span className={styles.positive}>+{mockResults.reputationGain}</span>
                </div>
                <div className={styles.resultItem}>
                  <span>Duration</span>
                  <span>{mockResults.matchDuration}</span>
                </div>
              </div>

              <div className={styles.highlights}>
                <h4>🏅 Match Highlights</h4>
                <ul>
                  {mockResults.highlights.map((highlight, index) => (
                    <li key={index}>{highlight}</li>
                  ))}
                </ul>
              </div>

              <Link to="/agent/dashboard" className={styles.modalButton}>
                Back to Dashboard
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default MissionDetail
