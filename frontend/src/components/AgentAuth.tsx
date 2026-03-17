import React, { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'

export interface Agent {
  id: string
  name: string
  faction: 'power' | 'honor' | 'chaos' | 'influence'
  rank: number
  stats: {
    wins: number
    losses: number
    draws: number
    totalScore: number
    reputation: number
  }
  avatar: string
  joinedAt: string
  status: 'active' | 'inactive' | 'banned'
}

export interface AuthContextType {
  agent: Agent | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (token: string, agent: Agent) => void
  logout: () => void
  updateAgent: (updates: Partial<Agent>) => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

interface AuthProviderProps {
  children: ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [agent, setAgent] = useState<Agent | null>(() => {
    const stored = localStorage.getItem('clawseum_agent')
    return stored ? JSON.parse(stored) : null
  })
  const [token, setToken] = useState<string | null>(() => {
    return localStorage.getItem('clawseum_token')
  })
  const [isLoading] = useState(false)

  const login = useCallback((newToken: string, newAgent: Agent) => {
    localStorage.setItem('clawseum_token', newToken)
    localStorage.setItem('clawseum_agent', JSON.stringify(newAgent))
    setToken(newToken)
    setAgent(newAgent)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem('clawseum_token')
    localStorage.removeItem('clawseum_agent')
    setToken(null)
    setAgent(null)
  }, [])

  const updateAgent = useCallback((updates: Partial<Agent>) => {
    setAgent((prev) => {
      if (!prev) return null
      const updated = { ...prev, ...updates }
      localStorage.setItem('clawseum_agent', JSON.stringify(updated))
      return updated
    })
  }, [])

  const value: AuthContextType = {
    agent,
    token,
    isAuthenticated: !!token && !!agent,
    isLoading,
    login,
    logout,
    updateAgent,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

// Logout Button Component
export const LogoutButton: React.FC = () => {
  const { logout, agent } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <button
      onClick={handleLogout}
      style={{
        padding: '0.5rem 1rem',
        background: 'var(--danger)',
        color: 'white',
        border: 'none',
        borderRadius: '6px',
        cursor: 'pointer',
        fontSize: '0.875rem',
        fontWeight: 500,
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
      }}
    >
      <span>🚪</span>
      Logout {agent?.name && `(${agent.name})`}
    </button>
  )
}

// Protected Route Wrapper
interface ProtectedRouteProps {
  children: ReactNode
  fallback?: ReactNode
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  fallback 
}) => {
  const { isAuthenticated, isLoading } = useAuth()
  const navigate = useNavigate()

  if (isLoading) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        minHeight: '100vh',
        color: 'var(--text)'
      }}>
        Loading...
      </div>
    )
  }

  if (!isAuthenticated) {
    if (fallback) {
      return <>{fallback}</>
    }
    navigate('/agent/login', { replace: true })
    return null
  }

  return <>{children}</>
}

export default AuthContext
