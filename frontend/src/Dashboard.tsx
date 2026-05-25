import React, { useEffect, useMemo, useRef, useState } from 'react'
import Admins from './Admins'
import Audit from './Audit'
import {
  addBlockedDomain,
  addBlockedKeyword,
  addQueueEntry,
  connectBot,
  deleteQueueEntry,
  getBlockedDomains,
  getBlockedKeywords,
  getHealth,
  getQueue,
  getQueueStats,
  logout,
  markQueueCompleted,
  markQueuePlaying,
  removeBlockedDomain,
  removeBlockedKeyword,
  reorderQueue,
  searchQueue,
} from './api'

type TabKey = 'overview' | 'queue' | 'filters' | 'admins' | 'audit' | 'system'

function formatDate(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function Panel({ title, subtitle, children, actions }: { title: string; subtitle?: string; children: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <h3>{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {actions && <div className="panel__actions">{actions}</div>}
      </div>
      {children}
    </section>
  )
}

function StatCard({ label, value, note }: { label: string; value: React.ReactNode; note?: string }) {
  return (
    <article className="stat-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {note && <small>{note}</small>}
    </article>
  )
}

function Pill({ tone = 'neutral', children }: { tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info'; children: React.ReactNode }) {
  return <span className={`pill pill--${tone}`}>{children}</span>
}

export default function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [tab, setTab] = useState<TabKey>('overview')
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const stored = localStorage.getItem('quetie_theme')
    return stored === 'light' ? 'light' : 'dark'
  })
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'live' | 'reconnecting' | 'offline'>('connecting')
  const [snapshot, setSnapshot] = useState<any>(null)
  const [health, setHealth] = useState<any>(null)
  const [stats, setStats] = useState<any>(null)
  const [queue, setQueue] = useState<any[]>([])
  const [queueTotal, setQueueTotal] = useState(0)
  const [queueLoading, setQueueLoading] = useState(false)
  const [queueError, setQueueError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [domains, setDomains] = useState<any[]>([])
  const [keywords, setKeywords] = useState<any[]>([])
  const [filtersLoading, setFiltersLoading] = useState(false)
  const [filtersError, setFiltersError] = useState<string | null>(null)
  const [queueUrl, setQueueUrl] = useState('')
  const [queueSubmitter, setQueueSubmitter] = useState('')
  const [queueNotes, setQueueNotes] = useState('')
  const [domainDraft, setDomainDraft] = useState('')
  const [domainReason, setDomainReason] = useState('')
  const [keywordDraft, setKeywordDraft] = useState('')
  const [keywordReason, setKeywordReason] = useState('')
  const [keywordRegex, setKeywordRegex] = useState(false)
  const [systemError, setSystemError] = useState<string | null>(null)
  const [botActionMessage, setBotActionMessage] = useState<string | null>(null)
  const [botActionLoading, setBotActionLoading] = useState(false)

  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const reconnectDelayRef = useRef(1000)
  const refreshThrottleRef = useRef<number | null>(null)
  const searchTermRef = useRef('')

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('quetie_theme', theme)
  }, [theme])

  const loadQueue = async (query = searchTerm) => {
    setQueueLoading(true)
    setQueueError(null)
    try {
      const data: any = query.trim() ? await searchQueue(query.trim()) : await getQueue(0, 200)
      const entries = data.entries || []
      setQueue(entries)
      setQueueTotal(typeof data.total === 'number' ? data.total : entries.length)
      setSystemError(null)
    } catch (error: any) {
      setQueueError(error.message || 'Failed to load queue')
    } finally {
      setQueueLoading(false)
    }
  }

  const loadFilters = async () => {
    setFiltersLoading(true)
    setFiltersError(null)
    try {
      const [domainData, keywordData] = await Promise.all([getBlockedDomains(), getBlockedKeywords()])
      setDomains(domainData.domains || [])
      setKeywords(keywordData.keywords || [])
      setSystemError(null)
    } catch (error: any) {
      setFiltersError(error.message || 'Failed to load filters')
    } finally {
      setFiltersLoading(false)
    }
  }

  const loadHealth = async () => {
    try {
      setHealth(await getHealth())
      setSystemError(null)
    } catch (error: any) {
      setSystemError(error.message || 'Failed to load health')
    }
  }

  const loadStats = async () => {
    try {
      setStats(await getQueueStats())
      setSystemError(null)
    } catch (error: any) {
      setSystemError(error.message || 'Failed to load stats')
    }
  }

  const refreshAll = async () => {
    await Promise.all([loadQueue(searchTerm), loadFilters(), loadHealth(), loadStats()])
  }

  useEffect(() => {
    void refreshAll()
  }, [])

  useEffect(() => {
    searchTermRef.current = searchTerm
    const timer = window.setTimeout(() => {
      void loadQueue(searchTerm)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [searchTerm])

  useEffect(() => {
    const tick = window.setInterval(() => {
      void loadHealth()
    }, 20000)
    return () => window.clearInterval(tick)
  }, [])

  useEffect(() => {
    let destroyed = false

    const connect = () => {
      if (destroyed) return
      setConnectionStatus(reconnectDelayRef.current > 1000 ? 'reconnecting' : 'connecting')
      try {
        eventSourceRef.current?.close()
        const source = new EventSource('/api/realtime/stream')
        eventSourceRef.current = source

        source.onopen = () => {
          reconnectDelayRef.current = 1000
          setConnectionStatus('live')
        }

        source.onmessage = event => {
          try {
            setSnapshot(JSON.parse(event.data))
          } catch {
            setSnapshot(event.data)
          }

          if (refreshThrottleRef.current) return
          refreshThrottleRef.current = window.setTimeout(() => {
            refreshThrottleRef.current = null
            void Promise.all([loadQueue(searchTermRef.current), loadStats(), loadHealth()])
          }, 250)
        }

        source.onerror = () => {
          setConnectionStatus('offline')
          source.close()
          if (destroyed) return
          if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current)
          reconnectTimerRef.current = window.setTimeout(connect, reconnectDelayRef.current)
          reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 15000)
        }
      } catch {
        setConnectionStatus('offline')
      }
    }

    connect()

    return () => {
      destroyed = true
      eventSourceRef.current?.close()
      if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current)
      if (refreshThrottleRef.current) window.clearTimeout(refreshThrottleRef.current)
    }
  }, [])

  const handleLogout = async () => {
    await logout()
    onLogout()
  }

  const queueItems = useMemo(() => queue || [], [queue])
  const pendingCount = stats?.pending_count ?? queueItems.length

  const handleAddQueue = async (event: React.FormEvent) => {
    event.preventDefault()
    setSystemError(null)
    try {
      await addQueueEntry({ url: queueUrl.trim(), submitter_username: queueSubmitter.trim() || 'streamer', notes: queueNotes.trim() || undefined })
      setQueueUrl('')
      setQueueNotes('')
      await refreshAll()
    } catch (error: any) {
      setSystemError(error.message || 'Failed to add queue item')
    }
  }

  const handlePlay = async (entryId: number) => {
    await markQueuePlaying(entryId)
    await refreshAll()
  }

  const handleComplete = async (entryId: number) => {
    await markQueueCompleted(entryId)
    await refreshAll()
  }

  const handleRemove = async (entryId: number) => {
    const reason = window.prompt('Optional removal reason', '') || ''
    await deleteQueueEntry(entryId, reason)
    await refreshAll()
  }

  const handleMove = async (entryId: number, direction: -1 | 1) => {
    if (searchTerm.trim()) return
    const index = queueItems.findIndex(item => item.id === entryId)
    const nextIndex = index + direction
    if (index < 0 || nextIndex < 0 || nextIndex >= queueItems.length) return
    const nextOrder = queueItems.slice()
    ;[nextOrder[index], nextOrder[nextIndex]] = [nextOrder[nextIndex], nextOrder[index]]
    setQueue(nextOrder)
    await reorderQueue(nextOrder.map(item => item.id))
    await loadQueue(searchTerm)
    await loadStats()
  }

  const handleDomainSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    await addBlockedDomain({ domain: domainDraft.trim(), reason: domainReason.trim() || undefined })
    setDomainDraft('')
    setDomainReason('')
    await loadFilters()
  }

  const handleKeywordSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    await addBlockedKeyword({ keyword: keywordDraft.trim(), reason: keywordReason.trim() || undefined, is_regex: keywordRegex })
    setKeywordDraft('')
    setKeywordReason('')
    setKeywordRegex(false)
    await loadFilters()
  }

  const handleConnectBot = async () => {
    setBotActionLoading(true)
    setBotActionMessage(null)
    setSystemError(null)
    try {
      const result: any = await connectBot()
      setBotActionMessage(result?.message || 'Bot connection request sent.')
      await loadHealth()
    } catch (error: any) {
      setBotActionMessage(error.message || 'Bot connection failed')
    } finally {
      setBotActionLoading(false)
    }
  }

  const botReason = (() => {
    const runtime = health?.runtime || {}
    if (health?.bot) return 'Connected to Twitch chat.'
    if (!runtime.bot_enabled) return 'Bot has not been started in this web process yet.'
    if (runtime.bot_last_error === 'missing_twitch_oauth_token') return 'Twitch OAuth token is missing from the server configuration.'
    if (runtime.bot_last_error === 'failed_to_start') return 'Twitch IRC connection failed. Check the bot username, token, and network access.'
    if (runtime.bot_last_error) return runtime.bot_last_error
    return 'Bot is disconnected.'
  })()

  const topSummary = [
    { label: 'Queue', value: queueTotal, note: 'Searchable live queue' },
    { label: 'Pending', value: pendingCount, note: 'Waiting for playback' },
    { label: 'Realtime', value: connectionStatus, note: 'SSE dashboard stream' },
    { label: 'Health', value: health?.status || 'unknown', note: health?.database ? 'database ready' : 'database issue' },
  ]

  return (
    <div className="dashboard-shell">
      <header className="topbar panel panel--hero">
        <div>
          <span className="eyebrow">miss_brain_glitch_bot · miss_brain_glitch</span>
          <h1>Qutie_MBG Control</h1>
          <p>Streamer-only queue control, filter management, and operational health in one clean console.</p>
        </div>
        <div className="topbar__actions">
          <Pill tone={connectionStatus === 'live' ? 'success' : connectionStatus === 'offline' ? 'danger' : 'warning'}>{connectionStatus}</Pill>
          <button className="button button--ghost" type="button" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </button>
          <button className="button button--ghost" type="button" onClick={() => void refreshAll()}>
            Refresh
          </button>
          <button className="button" type="button" onClick={() => void handleLogout()}>
            Logout
          </button>
        </div>
      </header>

      <section className="metric-grid">
        {topSummary.map(card => (
          <StatCard key={card.label} label={card.label} value={card.value} note={card.note} />
        ))}
      </section>

      <nav className="tabbar panel">
        {[
          ['overview', 'Overview'],
          ['queue', 'Queue'],
          ['filters', 'Filters'],
          ['admins', 'RBAC'],
          ['audit', 'Audit'],
          ['system', 'System'],
        ].map(([key, label]) => (
          <button key={key} className={tab === key ? 'tab tab--active' : 'tab'} onClick={() => setTab(key as TabKey)}>
            {label}
          </button>
        ))}
      </nav>

      {systemError && <div className="notice notice--error">{systemError}</div>}

      {tab === 'overview' && (
        <div className="stack">
          <Panel title="Live snapshot" subtitle="Latest realtime event payload and queue health at a glance" actions={<button className="button button--ghost" onClick={() => void refreshAll()}>Sync now</button>}>
            <div className="overview-grid">
              <div className="overview-card">
                <h4>Playing now</h4>
                <p>{stats?.playing_entry_id ? `Entry #${stats.playing_entry_id}` : 'Nothing currently playing'}</p>
                <small>{stats?.error || 'Queue statistics loaded from backend'}</small>
              </div>
              <div className="overview-card">
                <h4>Database</h4>
                <p>{health?.database ? 'Healthy' : 'Needs attention'}</p>
                <small>{formatDate(health?.runtime?.last_startup_at)}</small>
              </div>
              <div className="overview-card">
                <h4>Bot</h4>
                <div className="panel__actions" style={{ justifyContent: 'space-between' }}>
                  <p>{health?.bot ? 'Connected' : 'Disconnected'}</p>
                  {!health?.bot && (
                    <button className="button button--ghost" type="button" onClick={() => void handleConnectBot()} disabled={botActionLoading}>
                      {botActionLoading ? 'Connecting…' : 'Connect bot'}
                    </button>
                  )}
                </div>
                <small>{botReason}</small>
                {botActionMessage && <small>{botActionMessage}</small>}
                <small>{health?.version || 'v1.0.0'}</small>
              </div>
            </div>
          </Panel>
          <Panel title="Realtime payload" subtitle="SSE stream updates from the backend" actions={<button className="button button--ghost" onClick={() => setSnapshot(null)}>Clear</button>}>
            <pre className="code-block">{snapshot ? JSON.stringify(snapshot, null, 2) : 'Waiting for live events...'}</pre>
          </Panel>
        </div>
      )}

      {tab === 'queue' && (
        <div className="stack">
          <Panel title="Queue controls" subtitle="Search, add, reorder, and mark items as played or completed">
            <form className="inline-form" onSubmit={handleAddQueue}>
              <input className="field field--wide" placeholder="Paste a link to add" value={queueUrl} onChange={e => setQueueUrl(e.target.value)} />
              <input className="field" placeholder="Submitter" value={queueSubmitter} onChange={e => setQueueSubmitter(e.target.value)} />
              <input className="field field--wide" placeholder="Notes" value={queueNotes} onChange={e => setQueueNotes(e.target.value)} />
              <button className="button" type="submit">Add to queue</button>
            </form>

            <div className="queue-toolbar">
              <input className="field field--search" placeholder="Search by URL, title, or submitter" value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
              <button className="button button--ghost" type="button" onClick={() => { setSearchTerm(''); void loadQueue('') }}>Clear</button>
            </div>

            {queueError && <div className="notice notice--error">{queueError}</div>}

            <div className="table-shell">
              <table>
                <thead>
                  <tr>
                    <th>Position</th>
                    <th>Link</th>
                    <th>Submitter</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {queueLoading && queueItems.length === 0 && (
                    <tr><td colSpan={6}><div className="skeleton-row" /></td></tr>
                  )}
                  {!queueLoading && queueItems.length === 0 && (
                    <tr><td colSpan={6}><div className="empty-state">No queue items match the current filter.</div></td></tr>
                  )}
                  {queueItems.map((entry, index) => (
                    <tr key={entry.id}>
                      <td>{index + 1}</td>
                      <td>
                        <div className="queue-link">
                          <strong title={entry.url}>{entry.clip_title || entry.url}</strong>
                          <small>{entry.url}</small>
                        </div>
                      </td>
                      <td>{entry.submitter_username}</td>
                      <td><Pill tone={entry.status === 'playing' ? 'info' : entry.status === 'completed' ? 'success' : entry.status === 'removed' ? 'danger' : 'neutral'}>{entry.status}</Pill></td>
                      <td>{formatDate(entry.created_at)}</td>
                      <td>
                        <div className="row-actions">
                          <button className="button button--ghost" type="button" onClick={() => window.open(entry.url, '_blank', 'noopener,noreferrer')}>Open</button>
                          <button className="button button--ghost" type="button" onClick={() => void handlePlay(entry.id)}>Play</button>
                          <button className="button button--ghost" type="button" onClick={() => void handleComplete(entry.id)}>Done</button>
                          <button className="button button--danger" type="button" onClick={() => void handleRemove(entry.id)}>Remove</button>
                          <button className="button button--ghost" type="button" onClick={() => void handleMove(entry.id, -1)} disabled={!!searchTerm.trim() || index === 0}>↑</button>
                          <button className="button button--ghost" type="button" onClick={() => void handleMove(entry.id, 1)} disabled={!!searchTerm.trim() || index === queueItems.length - 1}>↓</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      )}

      {tab === 'filters' && (
        <div className="grid-2">
          <Panel title="Blocked domains" subtitle="Domains rejected before queue insertion">
            <form className="stack-form" onSubmit={handleDomainSubmit}>
              <input className="field" placeholder="example.com" value={domainDraft} onChange={e => setDomainDraft(e.target.value)} />
              <input className="field" placeholder="Reason" value={domainReason} onChange={e => setDomainReason(e.target.value)} />
              <button className="button" type="submit">Block domain</button>
            </form>
            {filtersLoading && <div className="skeleton-row" />}
            {filtersError && <div className="notice notice--error">{filtersError}</div>}
            <div className="item-list">
              {domains.length === 0 && <div className="empty-state">No blocked domains yet.</div>}
              {domains.map(domain => (
                <div className="item-row" key={domain.id}>
                  <div>
                    <strong>{domain.domain}</strong>
                    <small>{domain.reason || 'No reason supplied'}</small>
                  </div>
                  <button className="button button--danger" type="button" onClick={() => void removeBlockedDomain(domain.domain).then(loadFilters)}>
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </Panel>

          <Panel title="Blocked keywords" subtitle="Keywords and regex patterns filtered by the backend">
            <form className="stack-form" onSubmit={handleKeywordSubmit}>
              <input className="field" placeholder="keyword or regex" value={keywordDraft} onChange={e => setKeywordDraft(e.target.value)} />
              <input className="field" placeholder="Reason" value={keywordReason} onChange={e => setKeywordReason(e.target.value)} />
              <label className="checkbox-row"><input type="checkbox" checked={keywordRegex} onChange={e => setKeywordRegex(e.target.checked)} /> Regex pattern</label>
              <button className="button" type="submit">Block keyword</button>
            </form>
            <div className="item-list">
              {keywords.length === 0 && <div className="empty-state">No blocked keywords yet.</div>}
              {keywords.map(keyword => (
                <div className="item-row" key={keyword.id}>
                  <div>
                    <strong>{keyword.keyword}</strong>
                    <small>{keyword.reason || 'No reason supplied'}{keyword.is_regex ? ' · regex' : ''}</small>
                  </div>
                  <button className="button button--danger" type="button" onClick={() => void removeBlockedKeyword(keyword.keyword).then(loadFilters)}>
                    Remove
                  </button>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}

      {tab === 'admins' && (
        <Admins onChanged={() => void Promise.all([loadHealth(), loadStats()])} />
      )}

      {tab === 'audit' && <Audit />}

      {tab === 'system' && (
        <div className="grid-2">
          <Panel title="Health check" subtitle="Render/UptimeRobot friendly endpoint mirrored in the UI">
            <pre className="code-block">{health ? JSON.stringify(health, null, 2) : 'Loading health...'}</pre>
          </Panel>
          <Panel title="Runtime snapshot" subtitle="Current backend snapshot exposed through SSE and polling">
            <pre className="code-block">{snapshot ? JSON.stringify(snapshot, null, 2) : 'No runtime snapshot yet'}</pre>
          </Panel>
        </div>
      )}
    </div>
  )
}
