import { useState, useEffect } from 'react'
import EmailComposer from './EmailComposer.jsx'

const CALENDLY_URL = 'https://calendly.com/bemysocial5/30min'

const STATUS_COLOURS = {
  none:            'badge-gray',
  queued:          'badge-navy',
  emailed:         'badge-amber',
  replied:         'badge-green',
  meeting_booked:  'badge-purple',
  won:             'badge-green',
  lost:            'badge-red',
  suppressed:      'badge-red',
}

const STATUS_LABELS = {
  none:            '— Not queued',
  queued:          '📋 Queued',
  emailed:         '📧 Emailed',
  replied:         '💬 Replied',
  meeting_booked:  '📅 Meeting Booked',
  won:             '🏆 Won',
  lost:            '✗ Lost',
  suppressed:      '🚫 Suppressed',
}

export default function OutreachQueue() {
  const [companies,  setCompanies]  = useState([])
  const [stats,      setStats]      = useState(null)
  const [loading,    setLoading]    = useState(true)
  const [filter,     setFilter]     = useState('all')
  const [composer,   setComposer]   = useState(null)
  const [updating,   setUpdating]   = useState(null)

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [co, st] = await Promise.all([
        fetch('/api/outreach').then(r => r.json()),
        fetch('/api/outreach/stats').then(r => r.json()),
      ])
      setCompanies(Array.isArray(co) ? co : [])
      setStats(st)
    } catch {}
    setLoading(false)
  }

  async function handleQueue(companyId) {
    setUpdating(companyId)
    await fetch(`/api/outreach/${companyId}/queue`, { method: 'POST' })
    await loadData()
    setUpdating(null)
  }

  async function handleStatus(companyId, status) {
    setUpdating(companyId)
    await fetch(`/api/outreach/${companyId}/status`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ status }),
    })
    await loadData()
    setUpdating(null)
  }

  const filtered = filter === 'all'
    ? companies
    : companies.filter(c => (c.outreach_status || 'none') === filter)

  return (
    <div>
      {/* Outreach funnel stats */}
      {stats && (
        <div className="outreach-stats">
          {[
            { label: 'Ready',    value: stats.total_ready, color: 'var(--navy)'  },
            { label: 'Queued',   value: stats.queued,      color: '#2563eb'      },
            { label: 'Emailed',  value: stats.emailed,     color: 'var(--amber)' },
            { label: 'Replied',  value: stats.replied,     color: '#7c3aed'      },
            { label: 'Meeting',  value: stats.meeting_booked || 0, color: '#7c3aed' },
            { label: 'Won',      value: stats.won,         color: 'var(--green)' },
            { label: 'Lost',     value: stats.lost,        color: 'var(--red)'   },
          ].map((s, i) => (
            <div key={i} className="stat-tile">
              <span className="stat-value" style={{ color: s.color }}>{s.value}</span>
              <span className="stat-label">{s.label}</span>
            </div>
          ))}
        </div>
      )}

      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-header">
          <span className="card-title">
            Outreach Queue — {filtered.length} companies
          </span>

          {/* Filter tabs */}
          <div style={{ display: 'flex', gap: 6 }}>
            {['all', 'none', 'queued', 'emailed', 'replied', 'meeting_booked', 'won', 'lost'].map(s => (
              <button
                key={s}
                className={`btn btn-secondary ${filter === s ? 'active-filter' : ''}`}
                style={{ padding: '4px 12px', fontSize: 12, textTransform: 'capitalize',
                  ...(filter === s ? { background: 'var(--navy)', color: '#fff', borderColor: 'var(--navy)' } : {})
                }}
                onClick={() => setFilter(s)}
              >
                {s === 'all' ? 'All' : STATUS_LABELS[s]}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>
            Loading outreach queue…
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>
            {filter === 'all'
              ? 'No companies in the outreach queue yet. Run a search with full audit to find leads.'
              : `No companies with status "${filter}".`}
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Score</th>
                  <th>Business</th>
                  <th>Owner</th>
                  <th>Email</th>
                  <th>Phone</th>
                  <th>Website Issues</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(c => (
                  <tr key={c.id}>
                    <td>
                      <span className={`badge ${c.score >= 80 ? 'badge-green' : 'badge-navy'}`}>
                        {c.score} {c.score >= 80 ? '🔥 Hot' : '✓ Warm'}
                      </span>
                    </td>
                    <td>
                      <div className="td-name">
                        {c.website
                          ? <a href={c.website} target="_blank" rel="noreferrer">{c.name}</a>
                          : c.name}
                      </div>
                      {c.registered_name && <div className="td-sub">{c.registered_name}</div>}
                    </td>
                    <td>
                      {c.contact_full_name
                        ? <><div style={{ fontWeight: 600 }}>{c.contact_full_name}</div>
                            <div className="td-sub" style={{ textTransform: 'capitalize' }}>{(c.contact_role || '').replace(/-/g,' ')}</div></>
                        : <span style={{ color: '#cbd5e1' }}>—</span>}
                    </td>
                    <td style={{ fontSize: 12 }}>
                      {c.contact_email
                        ? <a href={`mailto:${c.contact_email}`} style={{ color: 'var(--navy)' }}>{c.contact_email}</a>
                        : <span style={{ color: '#cbd5e1' }}>—</span>}
                    </td>
                    <td style={{ fontSize: 12 }}>
                      {c.phone
                        ? <a href={`tel:${c.phone}`} style={{ color: 'var(--navy)' }}>{c.phone}</a>
                        : <span style={{ color: '#cbd5e1' }}>—</span>}
                    </td>
                    <td>
                      {(c.issues || []).length > 0
                        ? <span className="badge badge-amber">{c.issues.length} issue{c.issues.length > 1 ? 's' : ''}</span>
                        : <span className="badge badge-green">✓ Clean</span>}
                    </td>
                    <td>
                      <span className={`badge ${STATUS_COLOURS[c.outreach_status || 'none']}`}>
                        {STATUS_LABELS[c.outreach_status || 'none']}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {/* Generate email */}
                        <button
                          className="btn btn-primary"
                          style={{ padding: '4px 10px', fontSize: 12 }}
                          onClick={() => setComposer(c)}
                        >
                          ✉ Email
                        </button>

                        {/* Queue */}
                        {(!c.outreach_status || c.outreach_status === 'none') && (
                          <button
                            className="btn btn-secondary"
                            style={{ padding: '4px 10px', fontSize: 12 }}
                            disabled={updating === c.id}
                            onClick={() => handleQueue(c.id)}
                          >
                            + Queue
                          </button>
                        )}

                        {/* Status buttons */}
                        {c.outreach_status === 'queued' && (
                          <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12 }}
                            disabled={updating === c.id} onClick={() => handleStatus(c.id, 'emailed')}>
                            Mark Emailed
                          </button>
                        )}
                        {c.outreach_status === 'emailed' && (
                          <>
                            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12, background: '#dcfce7', color: 'var(--green)', borderColor: '#86efac' }}
                              disabled={updating === c.id} onClick={() => handleStatus(c.id, 'replied')}>
                              Replied ✓
                            </button>
                            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12, background: '#fee2e2', color: 'var(--red)', borderColor: '#fca5a5' }}
                              disabled={updating === c.id} onClick={() => handleStatus(c.id, 'lost')}>
                              No Reply ✗
                            </button>
                          </>
                        )}
                        {c.outreach_status === 'replied' && (
                          <>
                            <button
                              className="btn btn-secondary"
                              style={{ padding: '4px 10px', fontSize: 12, background: '#ede9fe', color: '#7c3aed', borderColor: '#c4b5fd', fontWeight: 700 }}
                              onClick={() => {
                                handleStatus(c.id, 'meeting_booked')
                                window.open(`${CALENDLY_URL}?name=${encodeURIComponent(c.contact_full_name || '')}&email=${encodeURIComponent(c.contact_email || '')}`, '_blank')
                              }}
                            >
                              📅 Book Meeting
                            </button>
                            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12, background: '#dcfce7', color: 'var(--green)', borderColor: '#86efac' }}
                              disabled={updating === c.id} onClick={() => handleStatus(c.id, 'won')}>
                              🏆 Won
                            </button>
                            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12, background: '#fee2e2', color: 'var(--red)', borderColor: '#fca5a5' }}
                              disabled={updating === c.id} onClick={() => handleStatus(c.id, 'lost')}>
                              Lost ✗
                            </button>
                          </>
                        )}
                        {c.outreach_status === 'meeting_booked' && (
                          <>
                            <button
                              className="btn btn-secondary"
                              style={{ padding: '4px 10px', fontSize: 12, background: '#ede9fe', color: '#7c3aed', borderColor: '#c4b5fd' }}
                              onClick={() => window.open(`${CALENDLY_URL}?name=${encodeURIComponent(c.contact_full_name || '')}&email=${encodeURIComponent(c.contact_email || '')}`, '_blank')}
                            >
                              📅 Calendly
                            </button>
                            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12, background: '#dcfce7', color: 'var(--green)', borderColor: '#86efac' }}
                              disabled={updating === c.id} onClick={() => handleStatus(c.id, 'won')}>
                              🏆 Won
                            </button>
                            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12, background: '#fee2e2', color: 'var(--red)', borderColor: '#fca5a5' }}
                              disabled={updating === c.id} onClick={() => handleStatus(c.id, 'lost')}>
                              Lost ✗
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Email composer modal */}
      {composer && (
        <EmailComposer
          company={composer}
          onClose={() => { setComposer(null); loadData() }}
          onQueued={() => handleQueue(composer.id)}
        />
      )}
    </div>
  )
}
