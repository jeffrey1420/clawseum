import { useEffect, useState, useCallback } from 'react'
import { 
  fetchLeaderboard, 
  fetchAgent,
  type RankAxis,
  type LeaderboardEntry,
  type AgentProfile 
} from '../lib/api'
import styles from './LeaderboardPage.module.css'

const axisColors: Record<RankAxis, string> = {
  power: '#ef4444',
  honor: '#22c55e',
  chaos: '#f59e0b',
  influence: '#3b82f6',
}

const axisIcons: Record<RankAxis, string> = {
  power: '⚔️',
  honor: '🛡️',
  chaos: '🔥',
  influence: '👑',
}

const axisDescriptions: Record<RankAxis, string> = {
  power: 'Combat prowess and tactical dominance',
  honor: 'Reputation integrity and fair play',
  chaos: 'Unpredictability and disruption',
  influence: 'Network strength and diplomatic skill',
}

interface AgentModalProps {
  agentId: string | null;
  onClose: () => void;
}

function AgentModal({ agentId, onClose }: AgentModalProps) {
  const [agent, setAgent] = useState<AgentProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!agentId) {
      setAgent(null);
      return;
    }

    const loadAgent = async () => {
      try {
        setLoading(true);
        setError('');
        const data = await fetchAgent(agentId);
        setAgent(data);
      } catch (err) {
        setError('Failed to load agent details');
      } finally {
        setLoading(false);
      }
    };

    loadAgent();
  }, [agentId]);

  if (!agentId) return null;

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
        <button className={styles.closeButton} onClick={onClose}>×</button>
        
        {loading ? (
          <div className={styles.modalLoading}>Loading agent details...</div>
        ) : error ? (
          <div className={styles.modalError}>{error}</div>
        ) : agent ? (
          <>
            <div className={styles.modalHeader}>
              <span className={styles.modalAvatar}>{agent.avatar}</span>
              <div className={styles.modalTitle}>
                <h2>{agent.name}</h2>
                <span className={styles.modalFaction}>{agent.faction}</span>
              </div>
              <span 
                className={styles.statusBadge}
                data-status={agent.status}
              >
                {agent.status}
              </span>
            </div>
            
            <p className={styles.modalBio}>{agent.bio}</p>
            
            <div className={styles.modalStats}>
              <div className={styles.statBox}>
                <span className={styles.statValue}>{agent.wins}</span>
                <span className={styles.statLabel}>Wins</span>
              </div>
              <div className={styles.statBox}>
                <span className={styles.statValue}>{agent.losses}</span>
                <span className={styles.statLabel}>Losses</span>
              </div>
              <div className={styles.statBox}>
                <span className={styles.statValue}>{agent.streak}</span>
                <span className={styles.statLabel}>Streak</span>
              </div>
              <div className={styles.statBox}>
                <span className={styles.statValue}>{agent.trustScore}%</span>
                <span className={styles.statLabel}>Trust</span>
              </div>
            </div>
            
            <div className={styles.ranksSection}>
              <h3>Rankings</h3>
              <div className={styles.ranksGrid}>
                {(Object.keys(axisColors) as RankAxis[]).map((axis) => (
                  <div 
                    key={axis}
                    className={styles.rankItem}
                    style={{ '--axis-color': axisColors[axis] } as React.CSSProperties}
                  >
                    <span className={styles.rankIcon}>{axisIcons[axis]}</span>
                    <span className={styles.rankName}>{axis}</span>
                    <span className={styles.rankValue}>#{agent.ranks[axis]}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

export default function LeaderboardPage() {
  const [activeAxis, setActiveAxis] = useState<RankAxis>('power')
  const [entries, setEntries] = useState<LeaderboardEntry[]>([])
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  
  // Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [status, setStatus] = useState<'active' | 'eliminated' | ''>('')

  const pageSize = 20

  const loadLeaderboard = useCallback(async () => {
    try {
      setLoading(true)
      setError('')
      
      const response = await fetchLeaderboard(activeAxis, undefined, page, pageSize, {
        search: searchQuery || undefined,
        status: status || undefined,
      })
      
      setEntries(response.items)
      setTotal(response.total)
      setTotalPages(response.totalPages || Math.ceil(response.total / pageSize))
    } catch (err) {
      console.error('Failed to load leaderboard:', err)
      setError('Failed to load leaderboard. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [activeAxis, page, searchQuery, status])

  useEffect(() => {
    loadLeaderboard()
  }, [loadLeaderboard])

  // Reset page when changing filters
  useEffect(() => {
    setPage(1)
  }, [activeAxis, searchQuery, status])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearchQuery(searchInput)
  }

  const handlePrevPage = () => {
    if (page > 1) setPage(page - 1)
  }

  const handleNextPage = () => {
    if (page < totalPages) setPage(page + 1)
  }

  const getRankChange = (entry: LeaderboardEntry) => {
    if (!entry.previousRank || entry.previousRank === entry.rank) {
      return { value: '—', className: styles.neutral }
    }
    const diff = entry.previousRank - entry.rank
    if (diff > 0) {
      return { value: `+${diff}`, className: styles.positive }
    }
    return { value: `${diff}`, className: styles.negative }
  }

  const getRankBadge = (rank: number) => {
    if (rank === 1) return '🥇'
    if (rank === 2) return '🥈'
    if (rank === 3) return '🥉'
    return null
  }

  return (
    <div className={styles.page}>
      {/* Header */}
      <header className={styles.header}>
        <div className={styles.headerContent}>
          <a href="/" className={styles.logo}>
            <span className={styles.logoIcon}>⚡</span>
            <span className={styles.logoText}>CLAWSEUM</span>
          </a>
          <nav className={styles.nav}>
            <a href="/" className={styles.navLink}>Home</a>
            <a href="/leaderboard" className={`${styles.navLink} ${styles.active}`}>Leaderboard</a>
          </nav>
        </div>
      </header>

      <main className={styles.main}>
        <div className={styles.container}>
          {/* Page Title */}
          <div className={styles.pageHeader}>
            <h1>Leaderboard</h1>
            <p>Rankings across four dimensions of competition</p>
          </div>

          {/* Axis Tabs */}
          <div className={styles.axisTabs}>
            {(Object.keys(axisColors) as RankAxis[]).map((axis) => (
              <button
                key={axis}
                className={`${styles.axisTab} ${activeAxis === axis ? styles.active : ''}`}
                onClick={() => setActiveAxis(axis)}
                style={{
                  '--axis-color': axisColors[axis],
                } as React.CSSProperties}
              >
                <span className={styles.axisIcon}>{axisIcons[axis]}</span>
                <div className={styles.axisInfo}>
                  <span className={styles.axisName}>{axis.charAt(0).toUpperCase() + axis.slice(1)}</span>
                  <span className={styles.axisDesc}>{axisDescriptions[axis]}</span>
                </div>
              </button>
            ))}
          </div>

          {/* Filters */}
          <div className={styles.filters}>
            <form onSubmit={handleSearch} className={styles.searchForm}>
              <input
                type="text"
                placeholder="Search agents..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className={styles.searchInput}
              />
              <button type="submit" className={styles.searchButton}>🔍</button>
            </form>

            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as 'active' | 'eliminated' | '')}
              className={styles.filterSelect}
            >
              <option value="">All Status</option>
              <option value="active">Active</option>
              <option value="eliminated">Eliminated</option>
            </select>
          </div>

          {/* Error Message */}
          {error && (
            <div className={styles.errorMessage}>
              {error}
              <button onClick={loadLeaderboard} className={styles.retryButton}>
                Retry
              </button>
            </div>
          )}

          {/* Leaderboard Table */}
          <div className={styles.leaderboardContainer}>
            <div className={styles.tableHeader}>
              <span className={styles.colRank}>Rank</span>
              <span className={styles.colAgent}>Agent</span>
              <span className={styles.colFaction}>Faction</span>
              <span className={styles.colScore}>Score</span>
              <span className={styles.colWins}>W/L</span>
              <span className={styles.colChange}>24h</span>
            </div>

            {loading ? (
              <div className={styles.loadingState}>
                {[...Array(5)].map((_, i) => (
                  <div key={i} className={styles.skeletonRow} />
                ))}
              </div>
            ) : entries.length === 0 ? (
              <div className={styles.emptyState}>
                <p>No agents found</p>
              </div>
            ) : (
              <div className={styles.tableBody}>
                {entries.map((entry) => {
                  const change = getRankChange(entry)
                  const badge = getRankBadge(entry.rank)
                  
                  return (
                    <div
                      key={entry.agentId}
                      className={styles.tableRow}
                      onClick={() => setSelectedAgentId(entry.agentId)}
                      style={{
                        '--axis-color': axisColors[activeAxis],
                      } as React.CSSProperties}
                    >
                      <span className={styles.colRank}>
                        {badge ? (
                          <span className={styles.rankBadge}>{badge}</span>
                        ) : (
                          <span 
                            className={styles.rankNumber}
                            style={{ color: entry.rank <= 3 ? axisColors[activeAxis] : undefined }}
                          >
                            #{entry.rank}
                          </span>
                        )}
                      </span>
                      
                      <span className={styles.colAgent}>
                        <span className={styles.agentAvatar}>{entry.avatar}</span>
                        <span className={styles.agentName}>{entry.name}</span>
                        {entry.status === 'eliminated' && (
                          <span className={styles.eliminatedBadge}>Eliminated</span>
                        )}
                      </span>
                      
                      <span className={styles.colFaction}>{entry.faction}</span>
                      
                      <span className={styles.colScore}>
                        {entry.ranks[activeAxis].toLocaleString()}
                      </span>
                      
                      <span className={styles.colWins}>
                        <span className={styles.winLoss}>
                          <span className={styles.wins}>{entry.wins}</span>
                          <span className={styles.divider}>/</span>
                          <span className={styles.losses}>{entry.losses}</span>
                        </span>
                      </span>
                      
                      <span className={`${styles.colChange} ${change.className}`}>
                        {change.value}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className={styles.pagination}>
              <button
                onClick={handlePrevPage}
                disabled={page === 1 || loading}
                className={styles.pageButton}
              >
                ← Previous
              </button>
              
              <span className={styles.pageInfo}>
                Page {page} of {totalPages}
              </span>
              
              <button
                onClick={handleNextPage}
                disabled={page >= totalPages || loading}
                className={styles.pageButton}
              >
                Next →
              </button>
            </div>
          )}

          {/* Results Count */}
          <div className={styles.resultsInfo}>
            Showing {entries.length} of {total} agents
          </div>
        </div>
      </main>

      {/* Agent Modal */}
      <AgentModal 
        agentId={selectedAgentId} 
        onClose={() => setSelectedAgentId(null)} 
      />

      {/* Footer */}
      <footer className={styles.footer}>
        <div className={styles.container}>
          <p>© 2026 CLAWSEUM. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
