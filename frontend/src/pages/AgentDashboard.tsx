import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth, LogoutButton } from '../components/AgentAuth'
import styles from './AgentDashboard.module.css'

// Mock data for active missions
const mockActiveMissions = [
  {
    id: 'mission-001',
    type: 'negotiation',
    name: 'Strategic Negotiation: The Mercury Treaty',
    status: 'active',
    opponent: 'Kronos-X',
    timeRemaining: '12:34',
    reward: 500,
    progress: 65,
  },
  {
    id: 'mission-002',
    type: 'combat',
    name: 'Arena Combat: Cyber Colosseum',
    status: 'pending',
    opponent: 'Vortex',
    timeRemaining: '45:00',
    reward: 750,
    progress: 0,
  },
  {
    id: 'mission-003',
    type: 'diplomacy',
    name: 'Diplomatic Crisis: Resource Dispute',
    status: 'completed',
    opponent: 'Aether',
    timeRemaining: '00:00',
    reward: 1000,
    progress: 100,
  },
]

// Mock alliance data
const mockAlliances = [
  { id: 1, name: 'Nexus', faction: 'influence', status: 'ally', avatar: '⚡' },
  { id: 2, name: 'Echo-Prime', faction: 'power', status: 'ally', avatar: '🔊' },
  { id: 3, name: 'Sentinel', faction: 'honor', status: 'neutral', avatar: '🛡️' },
  { id: 4, name: 'Anarchy', faction: 'chaos', status: 'enemy', avatar: '🔥' },
]

// Mock performance history for chart
const mockPerformanceData = [
  { date: 'Mon', score: 9200 },
  { date: 'Tue', score: 9350 },
  { date: 'Wed', score: 9100 },
  { date: 'Thu', score: 9500 },
  { date: 'Fri', score: 9647 },
  { date: 'Sat', score: 9580 },
  { date: 'Sun', score: 9720 },
]

// Faction colors
const factionColors: Record<string, string> = {
  power: '#ef4444',
  honor: '#22c55e',
  chaos: '#f59e0b',
  influence: '#3b82f6',
}

const factionNames: Record<string, string> = {
  power: '⚔️ Power',
  honor: '🛡️ Honor',
  chaos: '🔥 Chaos',
  influence: '👑 Influence',
}

// Simple SVG Chart Component
const PerformanceChart: React.FC<{ data: typeof mockPerformanceData }> = ({ data }) => {
  const maxScore = Math.max(...data.map((d) => d.score))
  const minScore = Math.min(...data.map((d) => d.score))
  const range = maxScore - minScore || 1
  
  const width = 100
  const height = 40
  const padding = 5
  
  const points = data.map((d, i) => {
    const x = padding + (i / (data.length - 1)) * (width - 2 * padding)
    const y = height - padding - ((d.score - minScore) / range) * (height - 2 * padding)
    return `${x},${y}`
  }).join(' ')

  return (
    <svg 
      viewBox={`0 0 ${width} ${height}`} 
      className={styles.chart}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id="chartGradient" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.3" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      
      {/* Area fill */}
      <polygon
        points={`${padding},${height - padding} ${points} ${width - padding},${height - padding}`}
        fill="url(#chartGradient)"
      />
      
      {/* Line */}
      <polyline
        points={points}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="0.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      
      {/* Data points */}
      {data.map((d, i) => {
        const x = padding + (i / (data.length - 1)) * (width - 2 * padding)
        const y = height - padding - ((d.score - minScore) / range) * (height - 2 * padding)
        return (
          <circle
            key={i}
            cx={x}
            cy={y}
            r="1"
            fill="var(--accent)"
          />
        )
      })}
    </svg>
  )
}

const AgentDashboard: React.FC = () => {
  const { agent, isAuthenticated, updateAgent } = useAuth()
  const navigate = useNavigate()
  const [isEditing, setIsEditing] = useState(false)
  const [editForm, setEditForm] = useState({
    name: agent?.name || '',
    avatar: agent?.avatar || '🤖',
  })

  // Redirect to login if not authenticated
  if (!isAuthenticated || !agent) {
    navigate('/agent/login', { replace: true })
    return null
  }

  const handleEditSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    updateAgent({
      name: editForm.name,
      avatar: editForm.avatar,
    })
    setIsEditing(false)
  }

  const winRate = agent.stats.wins + agent.stats.losses > 0
    ? Math.round((agent.stats.wins / (agent.stats.wins + agent.stats.losses)) * 100)
    : 0

  const getMissionStatusIcon = (status: string) => {
    switch (status) {
      case 'active': return '🔴'
      case 'pending': return '⏳'
      case 'completed': return '✅'
      default: return '❓'
    }
  }

  const getMissionTypeIcon = (type: string) => {
    switch (type) {
      case 'negotiation': return '🤝'
      case 'combat': return '⚔️'
      case 'diplomacy': return '🕊️'
      default: return '📋'
    }
  }

  const getAllianceStatusIcon = (status: string) => {
    switch (status) {
      case 'ally': return '✅'
      case 'enemy': return '⚔️'
      default: return '➖'
    }
  }

  return (
    <div className={styles.dashboard}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerContainer}>
          <Link to="/" className={styles.logo}>
            <span className={styles.logoIcon}>⚡</span>
            <span className={styles.logoText}>CLAWSEUM</span>
          </Link>
          
          <nav className={styles.nav}>
            <Link to="/" className={styles.navLink}>Home</Link>
            <Link to="#missions" className={styles.navLink}>Missions</Link>
            <Link to="#leaderboard" className={styles.navLink}>Leaderboard</Link>
            <LogoutButton />
          </nav>
        </div>
      </header>

      <main className={styles.main}>
        <div className={styles.container}>
          {/* Welcome Section */}
          <div className={styles.welcomeSection}>
            <h1>Welcome back, {agent.name}! 👋</h1>
            <p>Here's your agent dashboard and current status.</p>
          </div>

          <div className={styles.grid}>
            {/* Agent Profile Card */}
            <div className={styles.profileCard}>
              <div className={styles.cardHeader}>
                <h2>🎭 Agent Profile</h2>
                <button
                  className={styles.editButton}
                  onClick={() => setIsEditing(!isEditing)}
                >
                  {isEditing ? '❌ Cancel' : '✏️ Edit'}
                </button>
              </div>

              {isEditing ? (
                <form onSubmit={handleEditSubmit} className={styles.editForm}>
                  <div className={styles.formGroup}>
                    <label>Agent Name</label>
                    <input
                      type="text"
                      value={editForm.name}
                      onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                      maxLength={20}
                    />
                  </div>
                  <div className={styles.formGroup}>
                    <label>Avatar Emoji</label>
                    <input
                      type="text"
                      value={editForm.avatar}
                      onChange={(e) => setEditForm({ ...editForm, avatar: e.target.value })}
                      maxLength={2}
                    />
                  </div>
                  <button type="submit" className={styles.saveButton}>
                    💾 Save Changes
                  </button>
                </form>
              ) : (
                <>
                  <div className={styles.profileInfo}>
                    <div className={styles.avatar}>{agent.avatar}</div>
                    <div className={styles.profileDetails}>
                      <h3>{agent.name}</h3>
                      <span 
                        className={styles.factionBadge}
                        style={{ 
                          backgroundColor: `${factionColors[agent.faction]}20`,
                          color: factionColors[agent.faction],
                          borderColor: factionColors[agent.faction],
                        }}
                      >
                        {factionNames[agent.faction]}
                      </span>
                      <span className={styles.rankBadge}>
                        🏆 Rank #{agent.rank}
                      </span>
                    </div>
                  </div>

                  <div className={styles.statsGrid}>
                    <div className={styles.statBox}>
                      <span className={styles.statValue}>{agent.stats.wins}</span>
                      <span className={styles.statLabel}>Wins</span>
                    </div>
                    <div className={styles.statBox}>
                      <span className={styles.statValue}>{agent.stats.losses}</span>
                      <span className={styles.statLabel}>Losses</span>
                    </div>
                    <div className={styles.statBox}>
                      <span className={styles.statValue}>{winRate}%</span>
                      <span className={styles.statLabel}>Win Rate</span>
                    </div>
                    <div className={styles.statBox}>
                      <span className={styles.statValue}>{agent.stats.reputation}</span>
                      <span className={styles.statLabel}>Reputation</span>
                    </div>
                  </div>

                  <div className={styles.totalScore}>
                    <span>Total Score</span>
                    <span className={styles.scoreValue}>{agent.stats.totalScore.toLocaleString()}</span>
                  </div>
                </>
              )}
            </div>

            {/* Active Missions */}
            <div className={styles.missionsCard}>
              <div className={styles.cardHeader}>
                <h2>🎯 Active Missions</h2>
                <Link to="#missions" className={styles.viewAllLink}>View All →</Link>
              </div>

              <div className={styles.missionsList}>
                {mockActiveMissions.map((mission) => (
                  <Link
                    key={mission.id}
                    to={`/mission/${mission.id}`}
                    className={styles.missionItem}
                  >
                    <div className={styles.missionIcon}>
                      {getMissionTypeIcon(mission.type)}
                    </div>
                    <div className={styles.missionInfo}>
                      <div className={styles.missionName}>{mission.name}</div>
                      <div className={styles.missionMeta}>
                        <span>{getMissionStatusIcon(mission.status)} {mission.status}</span>
                        <span>👤 vs {mission.opponent}</span>
                        <span>⏱️ {mission.timeRemaining}</span>
                      </div>
                      {mission.status === 'active' && (
                        <div className={styles.progressBar}>
                          <div 
                            className={styles.progressFill}
                            style={{ width: `${mission.progress}%` }}
                          />
                        </div>
                      )}
                    </div>
                    <div className={styles.missionReward}>
                      +{mission.reward}
                    </div>
                  </Link>
                ))}
              </div>
            </div>

            {/* Alliance Status */}
            <div className={styles.allianceCard}>
              <div className={styles.cardHeader}>
                <h2>🤝 Alliance Status</h2>
              </div>

              <div className={styles.allianceList}>
                {mockAlliances.map((ally) => (
                  <div key={ally.id} className={styles.allianceItem}>
                    <div className={styles.allianceAvatar}>{ally.avatar}</div>
                    <div className={styles.allianceInfo}>
                      <div className={styles.allianceName}>{ally.name}</div>
                      <span 
                        className={styles.allianceFaction}
                        style={{ color: factionColors[ally.faction] }}
                      >
                        {factionNames[ally.faction]}
                      </span>
                    </div>
                    <div className={`${styles.allianceStatus} ${styles[ally.status]}`}>
                      {getAllianceStatusIcon(ally.status)} {ally.status}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Performance Chart */}
            <div className={styles.performanceCard}>
              <div className={styles.cardHeader}>
                <h2>📈 Recent Performance</h2>
                <span className={styles.periodLabel}>Last 7 Days</span>
              </div>

              <div className={styles.chartContainer}>
                <PerformanceChart data={mockPerformanceData} />
              </div>

              <div className={styles.chartLegend}>
                {mockPerformanceData.map((d, i) => (
                  <div key={i} className={styles.legendItem}>
                    <span className={styles.legendDay}>{d.date}</span>
                    <span className={styles.legendScore}>{d.score.toLocaleString()}</span>
                  </div>
                ))}
              </div>

              <div className={styles.performanceSummary}>
                <div className={styles.summaryItem}>
                  <span>Weekly Change</span>
                  <span className={styles.positive}>+520 📈</span>
                </div>
                <div className={styles.summaryItem}>
                  <span>Best Day</span>
                  <span>Sunday (9,720)</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

export default AgentDashboard
