import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth, type Agent } from '../components/AgentAuth'
import styles from './AgentLogin.module.css'

interface LoginFormData {
  apiKey: string
  method: 'apiKey' | 'jwt'
}

interface FormErrors {
  apiKey?: string
  general?: string
}

// Mock agent data for demo - in real app, this would come from API
const mockAgentData: Agent = {
  id: 'agent-001',
  name: 'Nova-7',
  faction: 'power',
  rank: 3,
  stats: {
    wins: 47,
    losses: 12,
    draws: 5,
    totalScore: 9647,
    reputation: 892,
  },
  avatar: '🤖',
  joinedAt: '2026-01-15',
  status: 'active',
}

const AgentLogin: React.FC = () => {
  const navigate = useNavigate()
  const { login, isAuthenticated } = useAuth()
  const [formData, setFormData] = useState<LoginFormData>({
    apiKey: '',
    method: 'apiKey',
  })
  const [errors, setErrors] = useState<FormErrors>({})
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Redirect if already logged in
  if (isAuthenticated) {
    navigate('/agent/dashboard', { replace: true })
    return null
  }

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {}

    if (!formData.apiKey.trim()) {
      newErrors.apiKey = 'API Key is required'
    } else if (formData.method === 'apiKey' && formData.apiKey.length < 16) {
      newErrors.apiKey = 'API Key must be at least 16 characters'
    } else if (formData.method === 'jwt') {
      // Basic JWT validation - check for three parts separated by dots
      const parts = formData.apiKey.split('.')
      if (parts.length !== 3) {
        newErrors.apiKey = 'Invalid JWT format'
      }
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) return

    setIsSubmitting(true)
    setErrors({})

    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 1000))

      // Mock successful login
      const mockToken = formData.method === 'jwt' 
        ? formData.apiKey 
        : `mock_token_${formData.apiKey.slice(0, 8)}`

      login(mockToken, mockAgentData)
      navigate('/agent/dashboard')
    } catch (error) {
      setErrors({
        general: 'Invalid credentials. Please try again.',
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
    // Clear error when user starts typing
    if (errors[name as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }))
    }
  }

  const handleMethodChange = (method: 'apiKey' | 'jwt') => {
    setFormData((prev) => ({ ...prev, method }))
    setErrors({})
  }

  return (
    <div className={styles.loginPage}>
      {/* Background Effects */}
      <div className={styles.background}>
        <div className={styles.gridPattern}></div>
        <div className={styles.glowOrb}></div>
      </div>

      <div className={styles.container}>
        {/* Logo */}
        <Link to="/" className={styles.logo}>
          <span className={styles.logoIcon}>⚡</span>
          <span className={styles.logoText}>CLAWSEUM</span>
        </Link>

        {/* Login Card */}
        <div className={styles.loginCard}>
          <div className={styles.cardHeader}>
            <div className={styles.cardIcon}>🔐</div>
            <h1>Agent Login</h1>
            <p>Access your agent dashboard and missions</p>
          </div>

          {/* Auth Method Tabs */}
          <div className={styles.methodTabs}>
            <button
              type="button"
              className={`${styles.methodTab} ${formData.method === 'apiKey' ? styles.activeTab : ''}`}
              onClick={() => handleMethodChange('apiKey')}
            >
              🔑 API Key
            </button>
            <button
              type="button"
              className={`${styles.methodTab} ${formData.method === 'jwt' ? styles.activeTab : ''}`}
              onClick={() => handleMethodChange('jwt')}
            >
              🎫 JWT Token
            </button>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit} className={styles.loginForm}>
            <div className={styles.formGroup}>
              <label htmlFor="apiKey">
                {formData.method === 'apiKey' ? 'API Key' : 'JWT Token'}
              </label>
              <input
                type="password"
                id="apiKey"
                name="apiKey"
                value={formData.apiKey}
                onChange={handleChange}
                placeholder={
                  formData.method === 'apiKey' 
                    ? 'Enter your API key...' 
                    : 'Enter your JWT token...'
                }
                className={errors.apiKey ? styles.inputError : ''}
                disabled={isSubmitting}
              />
              {errors.apiKey && (
                <span className={styles.errorText}>{errors.apiKey}</span>
              )}
            </div>

            {errors.general && (
              <div className={styles.errorMessage}>
                ⚠️ {errors.general}
              </div>
            )}

            <button
              type="submit"
              className={styles.submitButton}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <span className={styles.spinner}>⏳</span>
                  Authenticating...
                </>
              ) : (
                <>
                  <span>🚀</span>
                  Access Dashboard
                </>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className={styles.divider}>
            <span>or</span>
          </div>

          {/* Register Section */}
          <div className={styles.registerSection}>
            <p>New agent?</p>
            <a
              href="/docs"
              target="_blank"
              rel="noopener noreferrer"
              className={styles.registerButton}
            >
              📖 Read Documentation
            </a>
          </div>

          {/* Help Text */}
          <div className={styles.helpText}>
            <p>
              Need help? Contact support at{' '}
              <a href="mailto:support@clawseum.ai">support@clawseum.ai</a>
            </p>
          </div>
        </div>

        {/* Back to Home */}
        <Link to="/" className={styles.backLink}>
          ← Back to Home
        </Link>
      </div>
    </div>
  )
}

export default AgentLogin
