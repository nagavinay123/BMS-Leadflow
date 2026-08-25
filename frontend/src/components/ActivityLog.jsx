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

function dayLabel(dateStr) {
  const d     = new Date(dateStr)
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(today.getDate() - 1)
  if (d.toDateString() === today.toDateString())     return 'Today'
  if (d.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function timeStr(isoString) {
  return new Date(isoString).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

function calDay(isoString) {
  return new Date(isoString).toDateString()
}

function groupLogs(logs) {
  const map = {}
  for (const log of logs) {
    const key = `${calDay(log.created_at)}||${log.user_email || ''}||${log.action}`
    if (!map[key]) {
      map[key] = {
        key,
        day:        calDay(log.created_at),
        dayLabel:   dayLabel(log.created_at),
        user_email: log.user_email,
        action:     log.action,
        count:      0,
        latest:     log.created_at,
        items:      [],
      }
    }
    map[key].count++
    map[key].items.push(log)
    if (log.created_at > map[key].latest) map[key].latest = log.created_at
  }
  // Sort by latest desc
  return Object.values(map).sort((a, b) => b.latest.localeCompare(a.latest))
}

function formatDetails(details) {
  if (!details || Object.keys(details).length === 0) return null
  return Object.entries(details)
    .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
    .join(' · ')
}

export default function ActivityLog({ userEmail }) {
  const [logs,     setLogs]     = useState([])
  const [loading,  setLoading]  = useState(true)
  const [filter,   setFilter]   = useState('all')
  const [expanded, setExpanded] = useState({})

  useEffect(() => { loadLogs() }, [])

  async function loadLogs() {
    setLoading(true)
    try {
      const EXCLUDED = ['viewed_activity_log']
      const data = await fetch('/api/activity?limit=500').then(r => r.json())
      setLogs(Array.isArray(data) ? data.filter(l => !EXCLUDED.includes(l.action)) : [])
    } catch {}
    setLoading(false)
  }

  function toggleExpand(key) {
    setExpanded(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const filtered = filter === 'all' ? logs : logs.filter(l => l.action === filter)
  const grouped  = groupLogs(filtered)
  const actions  = ['all', ...new Set(logs.map(l => l.action))]

  return (
    <div>
      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-header">
          <span className="card-title">Activity Log — {grouped.length} grouped entries</span>
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
        ) : grouped.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>
            No activity yet. Actions like searches, status changes, and logins will appear here.
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Day</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Count</th>
                  <th>Last seen</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {grouped.map(g => {
                  const isLogin  = g.action === 'login'
                  const isLogout = g.action === 'logout'
                  const rowBg    = isLogin ? '#f0fdf4' : isLogout ? '#fef2f2' : 'transparent'
                  const isOpen   = expanded[g.key]

                  return (
                    <>
                      <tr key={g.key} style={{ background: rowBg }}>
                        <td style={{ fontWeight: 600, fontSize: 13, whiteSpace: 'nowrap' }}>
                          {g.dayLabel}
                        </td>
                        <td style={{ fontSize: 12 }}>
                          {g.user_email
                            ? <span style={{ background: '#f1f5f9', padding: '2px 8px', borderRadius: 12, fontSize: 11 }}>{g.user_email}</span>
                            : <span style={{ color: '#cbd5e1' }}>—</span>}
                        </td>
                        <td>
                          <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13,
                            fontWeight: isLogin || isLogout ? 700 : 600 }}>
                            {ACTION_ICONS[g.action] || ACTION_ICONS.default}
                            {g.action.replace(/_/g, ' ')}
                          </span>
                        </td>
                        <td>
                          <span style={{
                            background: '#e0e7ff', color: '#3730a3',
                            padding: '2px 10px', borderRadius: 12, fontSize: 12, fontWeight: 700
                          }}>
                            {g.count} {g.count === 1 ? 'time' : 'times'}
                          </span>
                        </td>
                        <td style={{ fontSize: 12, color: '#64748b' }}>
                          {timeStr(g.latest)}
                        </td>
                        <td>
                          {g.count > 1 && (
                            <button
                              className="btn btn-secondary"
                              style={{ padding: '2px 10px', fontSize: 11 }}
                              onClick={() => toggleExpand(g.key)}
                            >
                              {isOpen ? '▲ Hide' : '▼ Show all'}
                            </button>
                          )}
                        </td>
                      </tr>

                      {/* Expanded individual events */}
                      {isOpen && g.items
                        .slice().sort((a, b) => b.created_at.localeCompare(a.created_at))
                        .map(log => (
                          <tr key={log.id} style={{ background: isLogin ? '#f7fef9' : isLogout ? '#fff7f7' : '#f8fafc' }}>
                            <td style={{ fontSize: 11, color: '#94a3b8', paddingLeft: 24 }}>
                              ↳ {new Date(log.created_at).toLocaleString('en-GB')}
                            </td>
                            <td style={{ fontSize: 11, color: '#94a3b8' }}>{log.user_email || '—'}</td>
                            <td style={{ fontSize: 11, color: '#64748b' }}>
                              {ACTION_ICONS[log.action] || ACTION_ICONS.default} {log.action.replace(/_/g, ' ')}
                            </td>
                            <td colSpan={3} style={{ fontSize: 11, color: '#94a3b8' }}>
                              {formatDetails(log.details) || '—'}
                            </td>
                          </tr>
                        ))
                      }
                    </>
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
