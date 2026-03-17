import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './components/AgentAuth'
import HomePage from './pages/HomePage'
import LeaderboardPage from './pages/LeaderboardPage'
import AgentLogin from './pages/AgentLogin'
import AgentDashboard from './pages/AgentDashboard'
import MissionDetail from './pages/MissionDetail'
import './App.css'

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/leaderboard" element={<LeaderboardPage />} />
          <Route path="/agent/login" element={<AgentLogin />} />
          <Route path="/agent/dashboard" element={<AgentDashboard />} />
          <Route path="/mission/:id" element={<MissionDetail />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  )
}

export default App
