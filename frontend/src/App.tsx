import React, { useEffect, useState } from 'react'
import Login from './Login'
import Dashboard from './Dashboard'
import { getMe, getToken, setTokenFromStorage } from './api'

export default function App() {
  const [token, setToken] = useState<string | null>(getToken())
  const [bootstrapped, setBootstrapped] = useState(false)

  useEffect(() => {
    const bootstrap = async () => {
      setTokenFromStorage()
      const storedToken = getToken()
      if (!storedToken) {
        setToken(null)
        setBootstrapped(true)
        return
      }

      try {
        await getMe()
        setToken(storedToken)
      } catch {
        try { localStorage.removeItem('quetie_token') } catch (e) {}
        setToken(null)
      } finally {
        setBootstrapped(true)
      }
    }

    bootstrap()
  }, [])

  const handleLogin = (t: string) => {
    localStorage.setItem('quetie_token', t)
    setToken(t)
  }

  const handleLogout = () => {
    localStorage.removeItem('quetie_token')
    setToken(null)
  }

  if (!bootstrapped) {
    return (
      <div className="app-loading-shell">
        <div className="panel panel--hero panel--loading">
          <div className="skeleton skeleton--title" />
          <div className="skeleton skeleton--line" />
          <div className="skeleton skeleton--line short" />
        </div>
      </div>
    )
  }

  return (
    <div className="app-root">
      {token ? (
        <Dashboard onLogout={handleLogout} />
      ) : (
        <Login onLogin={handleLogin} />
      )}
    </div>
  )
}
