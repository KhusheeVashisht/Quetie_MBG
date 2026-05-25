import React, { useEffect, useState } from 'react'
import { getAuditLogs } from './api'

export default function Audit() {
  const [logs, setLogs] = useState<any[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const data: any = await getAuditLogs()
      setLogs(data.logs || [])
    } catch (err: any) {
      setError(err.message || 'Failed to load audit logs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <h3>Audit trail</h3>
          <p>Recent admin actions and backend security events.</p>
        </div>
        <div className="panel__actions">
          <button className="button button--ghost" type="button" onClick={() => void refresh()}>
            Refresh
          </button>
        </div>
      </div>

      {error && <div className="notice notice--error">{error}</div>}
      {loading && <div className="skeleton-row" />}

      <div className="audit-list">
        {logs.length === 0 && !loading && <div className="empty-state">No audit events yet.</div>}
        {logs.map(log => (
          <article className="audit-row" key={log.id}>
            <div>
              <strong>{log.action}</strong>
              <p>{log.details || 'No details available'}</p>
            </div>
            <div className="audit-meta">
              <span>{log.actor || 'system'}</span>
              <span>{log.target || '—'}</span>
              <span>{log.created_at ? new Date(log.created_at).toLocaleString() : '—'}</span>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
