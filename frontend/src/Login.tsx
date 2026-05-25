import React, { useState } from 'react'
import { login, createSession } from './api'

export default function Login({ onLogin }: { onLogin: (t: string) => void }) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const data: any = await login(username, password)
      const token = data.token
      if (!token) throw new Error('No token')
      await createSession(token)
      localStorage.setItem('quetie_token', token)
      onLogin(token)
    } catch (err: any) {
      setError(err.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card panel panel--hero">
        <div className="auth-copy">
          <span className="eyebrow">Private streamer console</span>
          <h1>Quetie_MBG</h1>
          <p>
            Secure dashboard access for queue moderation, blocked link control,
            and real-time Twitch queue operations.
          </p>
        </div>
        <form onSubmit={submit} className="auth-form">
          <h2>Login</h2>
          {error && <div className="notice notice--error">{error}</div>}
          <label>
            Username
            <input value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" />
          </label>
          <button type="submit" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
          <p className="auth-footnote">Sessions are persistent and protected with secure cookies + CSRF.</p>
        </form>
      </div>
    </div>
  )
}
