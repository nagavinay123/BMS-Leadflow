import { useState, useEffect } from 'react'

const ACTION_ICONS = {
  search:         '🔍',
  login:          '🔐',
  logout:         '🚪',
  status_change:  '🔄',
  email_sent:     '📧',
  meeting_booked: '📅',
  approved:       '✅',
  rejected:       '❌',
  default:        '📋',
}

function timeAgo(isoString) {
  const diff = Date.now() - new Date(isoString).getTime()
  const mins  = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days  = Math.floor(diff / 86400000)
  if (mins  < 1)   return 'just now'
  if (mins  < 60)  return `${mins}m ago`
  if (hours < 24)  return `${hours}h ago`
  return `${days}d ago`
}

function formatDetails(details) {
  if (!details || Object.keys(details).length === 0) return null
  return Object.entries(details)
    .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
    .join(' · ')
}

export default function ActivityLog({ userEmail }) {
  const [logs,    setLogs]    = useState([])
  const [loading, setLoading] = useState(true)
  const [filter,  setFilter]  = useState('all')

  useEffect(() => {
    loadLogs()
  }, [])

  async function loadLogs() {
    setLoading(true)
    try {
      const EXCLUDED = ['viewed_activity_log']
      const data = await fetch('/api/activity?limit=200').then(r => r.json())
      setLogs(Array.isArray(data) ? data.filter(l => !EXCLUDED.includes(l.action)) : [])
    } catch {}
    setLoading(false)
  }

  const actions = ['all', ...new Set(logs.map(l => l.action))]
  const filtered = filter === 'all' ? logs : logs.filter(l => l.action === filter)

  return (
    <div>
      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-header">
          <span className="card-title">Activity Log — {filtered.length} entries</span>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {actions.map(a => (
              <button
                key={a}
                className="btn btn-secondary"
                style={{
                  padding: '4px 12px', fontSize: 12, textTransform: 'capitalize',
                  ...(filter === a ? { background: 'var(--navy)', color: '#fff', borderColor: 'var(--navy)' } : {})
                }}
                onClick={() => setFilter(a)}
              >
                {a === 'all' ? 'All' : a.replace(/_/g, ' ')}
              </button>
            ))}
            <button className="btn btn-secondary" style={{ padding: '4px 12px', fontSize: 12 }} onClick={loadLogs}>
              ↻ Refresh
            </button>
          </div>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading…</div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>
            No activity yet. Actions like searches, status changes, and logins will appear here.
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>When</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(log => {
                  const isLogin  = log.action === 'login'
                  const isLogout = log.action === 'logout'
                  const rowBg = isLogin  ? '#f0fdf4'
                              : isLogout ? '#fef2f2'
                              : 'transparent'
                  return (
                    <tr key={log.id} style={{ background: rowBg }}>
                      <td style={{ fontSize: 12, color: '#64748b', whiteSpace: 'nowrap' }}>
                        {timeAgo(log.created_at)}
                        <div style={{ fontSize: 11, color: '#94a3b8' }}>
                          {new Date(log.created_at).toLocaleString('en-GB')}
                        </div>
                      </td>
                      <td style={{ fontSize: 12 }}>
                        {log.user_email
                          ? <span style={{ background: '#f1f5f9', padding: '2px 8px', borderRadius: 12, fontSize: 11 }}>{log.user_email}</span>
                          : <span style={{ color: '#cbd5e1' }}>—</span>}
                      </td>
                      <td>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: isLogin || isLogout ? 700 : 600 }}>
                          {ACTION_ICONS[log.action] || ACTION_ICONS.default}
                          {log.action.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td style={{ fontSize: 12, color: '#64748b' }}>
                        {formatDetails(log.details) || '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
