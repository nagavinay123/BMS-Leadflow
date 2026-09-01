import { useState, useEffect } from 'react'
import EmailComposer from './EmailComposer.jsx'

const CALENDLY_URL = 'https://calendly.com/bemysocial5/30min'

// ── Outreach status config ────────────────────────────────────────────────────
const STATUS_COLOURS = {
  none:           'badge-gray',
  queued:         'badge-navy',
  emailed:        'badge-amber',
  replied:        'badge-green',
  meeting_booked: 'badge-purple',
  phone_call:     'badge-amber',
  won:            'badge-green',
  lost:           'badge-red',
  suppressed:     'badge-red',
}
const STATUS_LABELS = {
  none:           '— Not queued',
  queued:         '📋 Queued',
  emailed:        '📧 Emailed',
  replied:        '💬 Replied',
  meeting_booked: '📅 Meeting Booked',
  phone_call:     '📞 Phone Called',
  won:            '🏆 Won',
  lost:           '✗ Lost',
  suppressed:     '🚫 Suppressed',
}

// ── Phone call status config ──────────────────────────────────────────────────
const CALL_STATUS_CONFIG = {
  pending:        { label: 'Pending',        color: '#64748b', bg: '#f1f5f9', border: '#cbd5e1' },
  completed:      { label: '✓ Completed',    color: '#047857', bg: '#ecfdf5', border: '#6ee7b7' },
  call_back:      { label: '↩ Call Back',    color: '#b45309', bg: '#fffbeb', border: '#fcd34d' },
  meeting_booked: { label: '📅 Meeting',     color: '#7c3aed', bg: '#ede9fe', border: '#c4b5fd' },
}

export default function OutreachQueue() {
  const [companies,   setCompanies]   = useState([])
  const [stats,       setStats]       = useState(null)
  const [loading,     setLoading]     = useState(true)
  const [filter,      setFilter]      = useState('all')
  const [composer,    setComposer]    = useState(null)
  const [updating,    setUpdating]    = useState(null)
  const [viewMode,    setViewMode]    = useState('outreach') // 'outreach' | 'phone'

  // Outreach notes (imp_notes)
  const [notes,       setNotes]       = useState({})
  const [savingNote,  setSavingNote]  = useState(null)

  // Phone call notes & status
  const [callNotes,   setCallNotes]   = useState({})
  const [callStatus,  setCallStatus]  = useState({})
  const [savingCall,  setSavingCall]  = useState(null)
  const [callFilter,  setCallFilter]  = useState('all')

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [co, st] = await Promise.all([
        fetch('/api/outreach').then(r => r.json()),
        fetch('/api/outreach/stats').then(r => r.json()),
      ])
      const arr = Array.isArray(co) ? co : []
      setCompanies(arr)
      const n = {}, cs = {}, cn = {}
      arr.forEach(c => {
        if (c.imp_notes)        n[c.id]  = c.imp_notes
        if (c.phone_call_status) cs[c.id] = c.phone_call_status
        if (c.phone_call_notes)  cn[c.id] = c.phone_call_notes
      })
      setNotes(prev => ({ ...n, ...prev }))
      setCallStatus(prev => ({ ...cs, ...prev }))
      setCallNotes(prev => ({ ...cn, ...prev }))
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
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    })
    await loadData()
    setUpdating(null)
  }

  async function saveNote(companyId) {
    setSavingNote(companyId)
    await fetch(`/api/outreach/${companyId}/notes`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ imp_notes: notes[companyId] || '' }),
    }).catch(() => {})
    setSavingNote(null)
  }

  async function saveCallData(companyId, patch = {}) {
    setSavingCall(companyId)
    await fetch(`/api/outreach/${companyId}/phone`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }).catch(() => {})
    setSavingCall(null)
  }

  async function setCallStatusAndSave(companyId, status) {
    setCallStatus(prev => ({ ...prev, [companyId]: status }))
    await saveCallData(companyId, { phone_call_status: status })
  }

  // ── Filtered lists ────────────────────────────────────────────────────────
  const filtered = filter === 'all'
    ? companies
    : companies.filter(c => (c.outreach_status || 'none') === filter)

  const callFiltered = callFilter === 'all'
    ? companies
    : companies.filter(c => {
        const s = callStatus[c.id] || 'pending'
        return s === callFilter
      })

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div>
      {/* Funnel stats */}
      {stats && (
        <div className="outreach-stats">
          {[
            { label: 'Ready',   value: stats.total_ready,        color: 'var(--navy)'  },
            { label: 'Queued',  value: stats.queued,             color: '#2563eb'      },
            { label: 'Emailed', value: stats.emailed,            color: 'var(--amber)' },
            { label: 'Replied', value: stats.replied,            color: '#7c3aed'      },
            { label: 'Meeting', value: stats.meeting_booked || 0, color: '#7c3aed'    },
            { label: 'Won',     value: stats.won,                color: 'var(--green)' },
            { label: 'Lost',    value: stats.lost,               color: 'var(--red)'   },
          ].map((s, i) => (
            <div key={i} className="stat-tile">
              <span className="stat-value" style={{ color: s.color }}>{s.value}</span>
              <span className="stat-label">{s.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* View mode toggle */}
      <div style={{ display: 'flex', gap: 8, marginTop: 20, marginBottom: 4 }}>
        <button
          onClick={() => setViewMode('outreach')}
          style={{
            padding: '8px 20px', borderRadius: 8, fontSize: 14, fontWeight: 600,
            cursor: 'pointer', border: '2px solid',
            background: viewMode === 'outreach' ? 'var(--navy)' : '#fff',
            color: viewMode === 'outreach' ? '#fff' : 'var(--navy)',
            borderColor: 'var(--navy)',
          }}
        >
          📧 Outreach Queue
        </button>
        <button
          onClick={() => setViewMode('phone')}
          style={{
            padding: '8px 20px', borderRadius: 8, fontSize: 14, fontWeight: 600,
            cursor: 'pointer', border: '2px solid',
            background: viewMode === 'phone' ? '#047857' : '#fff',
            color: viewMode === 'phone' ? '#fff' : '#047857',
            borderColor: '#047857',
          }}
        >
          📞 Phone Calls
        </button>
      </div>

      {/* ── OUTREACH VIEW ─────────────────────────────────────────────────── */}
      {viewMode === 'outreach' && (
        <div className="card">
          <div className="card-header">
            <span className="card-title">Outreach Queue — {filtered.length} companies</span>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {['all','none','queued','emailed','replied','meeting_booked','won','lost'].map(s => (
                <button
                  key={s}
                  className="btn btn-secondary"
                  style={{
                    padding: '4px 12px', fontSize: 12, textTransform: 'capitalize',
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
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading…</div>
          ) : filtered.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>
              {filter === 'all' ? 'No companies yet. Run a search to find leads.' : `No companies with status "${filter}".`}
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Score</th>
                    <th>Business</th>
                    <th>Owner</th>
                    <th>Job Title</th>
                    <th>Email</th>
                    <th>Phone</th>
                    <th>Issues</th>
                    <th>IMP Notes</th>
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
                          {c.website ? <a href={c.website} target="_blank" rel="noreferrer">{c.name}</a> : c.name}
                        </div>
                        {c.registered_name && <div className="td-sub">{c.registered_name}</div>}
                      </td>
                      <td>
                        {c.contact_full_name
                          ? <div style={{ fontWeight: 600 }}>{c.contact_full_name}</div>
                          : <span style={{ color: '#cbd5e1' }}>—</span>}
                      </td>
                      <td style={{ fontSize: 12, textTransform: 'capitalize', color: '#475569' }}>
                        {c.contact_role ? (c.contact_role).replace(/-/g,' ') : <span style={{ color: '#cbd5e1' }}>—</span>}
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
                      <td style={{ minWidth: 150 }}>
                        <textarea
                          rows={2}
                          placeholder="Add note…"
                          value={notes[c.id] || ''}
                          onChange={e => setNotes(prev => ({ ...prev, [c.id]: e.target.value }))}
                          onBlur={() => saveNote(c.id)}
                          style={{
                            width: '100%', fontSize: 12, padding: '4px 6px',
                            border: '1px solid #e2e8f0', borderRadius: 6,
                            resize: 'vertical', fontFamily: 'inherit',
                            background: notes[c.id] ? '#fffbeb' : '#f8fafc',
                            color: '#0f172a', outline: 'none', boxSizing: 'border-box',
                          }}
                        />
                        {savingNote === c.id && <span style={{ fontSize: 10, color: '#94a3b8' }}>saving…</span>}
                      </td>
                      <td>
                        <span className={`badge ${STATUS_COLOURS[c.outreach_status || 'none']}`}>
                          {STATUS_LABELS[c.outreach_status || 'none']}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          <button className="btn btn-primary" style={{ padding: '4px 10px', fontSize: 12 }}
                            onClick={() => setComposer(c)}>✉ Email</button>

                          {(!c.outreach_status || c.outreach_status === 'none') && (
                            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12 }}
                              disabled={updating === c.id} onClick={() => handleQueue(c.id)}>+ Queue</button>
                          )}
                          {c.outreach_status === 'queued' && (
                            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12 }}
                              disabled={updating === c.id} onClick={() => handleStatus(c.id, 'emailed')}>Mark Emailed</button>
                          )}
                          {c.outreach_status === 'emailed' && (<>
                            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12, background: '#dcfce7', color: 'var(--green)', borderColor: '#86efac' }}
                              disabled={updating === c.id} onClick={() => handleStatus(c.id, 'replied')}>Replied ✓</button>
                            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12, background: '#fee2e2', color: 'var(--red)', borderColor: '#fca5a5' }}
                              disabled={updating === c.id} onClick={() => handleStatus(c.id, 'lost')}>No Reply ✗</button>
                          </>)}
                          {c.outreach_status === 'replied' && (<>
                            <button className="btn btn-secondary"
                              style={{ padding: '4px 10px', fontSize: 12, background: '#ede9fe', color: '#7c3aed', borderColor: '#c4b5fd', fontWeight: 700 }}
                              onClick={() => { handleStatus(c.id, 'meeting_booked'); window.open(`${CALENDLY_URL}?name=${encodeURIComponent(c.contact_full_name||'')}&email=${encodeURIComponent(c.contact_email||'')}`, '_blank') }}>
                              📅 Book Meeting
                            </button>
                            <button className="btn btn-secondary"
                              style={{ padding: '4px 10px', fontSize: 12, background: '#ecfdf5', color: '#047857', borderColor: '#6ee7b7' }}
                              disabled={updating === c.id}
                              onClick={() => { handleStatus(c.id, 'phone_call'); if (c.phone) window.open(`tel:${c.phone}`) }}>
                              📞 Phone Call
                            </button>
                            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12, background: '#dcfce7', color: 'var(--green)', borderColor: '#86efac' }}
                              disabled={updating === c.id} onClick={() => handleStatus(c.id, 'won')}>🏆 Won</button>
                            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12, background: '#fee2e2', color: 'var(--red)', borderColor: '#fca5a5' }}
                              disabled={updating === c.id} onClick={() => handleStatus(c.id, 'lost')}>Lost ✗</button>
                          </>)}
                          {c.outreach_status === 'meeting_booked' && (<>
                            <button className="btn btn-secondary"
                              style={{ padding: '4px 10px', fontSize: 12, background: '#ede9fe', color: '#7c3aed', borderColor: '#c4b5fd' }}
                              onClick={() => window.open(`${CALENDLY_URL}?name=${encodeURIComponent(c.contact_full_name||'')}&email=${encodeURIComponent(c.contact_email||'')}`, '_blank')}>
                              📅 Calendly
                            </button>
                            <button className="btn btn-secondary"
                              style={{ padding: '4px 10px', fontSize: 12, background: '#ecfdf5', color: '#047857', borderColor: '#6ee7b7' }}
                              onClick={() => { if (c.phone) window.open(`tel:${c.phone}`) }}>
                              📞 Phone Call
                            </button>
                            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12, background: '#dcfce7', color: 'var(--green)', borderColor: '#86efac' }}
                              disabled={updating === c.id} onClick={() => handleStatus(c.id, 'won')}>🏆 Won</button>
                            <button className="btn btn-secondary" style={{ padding: '4px 10px', fontSize: 12, background: '#fee2e2', color: 'var(--red)', borderColor: '#fca5a5' }}
                              disabled={updating === c.id} onClick={() => handleStatus(c.id, 'lost')}>Lost ✗</button>
                          </>)}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── PHONE CALLS VIEW ─────────────────────────────────────────────── */}
      {viewMode === 'phone' && (
        <div className="card">
          <div className="card-header">
            <span className="card-title">📞 Phone Calls — {callFiltered.length} companies</span>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {[
                { key: 'all',           label: 'All' },
                { key: 'pending',       label: '🕐 Pending' },
                { key: 'completed',     label: '✓ Completed' },
                { key: 'call_back',     label: '↩ Call Back' },
                { key: 'meeting_booked',label: '📅 Meeting Booked' },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  className="btn btn-secondary"
                  style={{
                    padding: '4px 14px', fontSize: 12,
                    ...(callFilter === key ? { background: '#047857', color: '#fff', borderColor: '#047857' } : {})
                  }}
                  onClick={() => setCallFilter(key)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>Loading…</div>
          ) : callFiltered.length === 0 ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--gray-400)' }}>No companies found.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Business</th>
                    <th>Owner</th>
                    <th>Job Title</th>
                    <th>Phone</th>
                    <th>Call Status</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {callFiltered.map(c => {
                    const cs = callStatus[c.id] || 'pending'
                    const cfg = CALL_STATUS_CONFIG[cs] || CALL_STATUS_CONFIG.pending
                    return (
                      <tr key={c.id}>
                        <td>
                          <div className="td-name">
                            {c.website ? <a href={c.website} target="_blank" rel="noreferrer">{c.name}</a> : c.name}
                          </div>
                          {c.registered_name && <div className="td-sub">{c.registered_name}</div>}
                        </td>
                        <td>
                          {c.contact_full_name
                            ? <div style={{ fontWeight: 600 }}>{c.contact_full_name}</div>
                            : <span style={{ color: '#cbd5e1' }}>—</span>}
                        </td>
                        <td style={{ fontSize: 12, textTransform: 'capitalize', color: '#475569' }}>
                          {c.contact_role ? (c.contact_role).replace(/-/g,' ') : <span style={{ color: '#cbd5e1' }}>—</span>}
                        </td>
                        <td style={{ fontSize: 13, fontWeight: 600 }}>
                          {c.phone
                            ? <a href={`tel:${c.phone}`} style={{ color: '#047857' }}>{c.phone}</a>
                            : <span style={{ color: '#cbd5e1' }}>—</span>}
                        </td>
                        <td style={{ minWidth: 200 }}>
                          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                            {Object.entries(CALL_STATUS_CONFIG).map(([key, conf]) => (
                              <button
                                key={key}
                                onClick={() => setCallStatusAndSave(c.id, key)}
                                style={{
                                  padding: '3px 10px', fontSize: 11, borderRadius: 6,
                                  border: `1px solid ${cs === key ? conf.border : '#e2e8f0'}`,
                                  background: cs === key ? conf.bg : '#f8fafc',
                                  color: cs === key ? conf.color : '#94a3b8',
                                  fontWeight: cs === key ? 700 : 400,
                                  cursor: 'pointer',
                                }}
                              >
                                {conf.label}
                              </button>
                            ))}
                          </div>
                        </td>
                        <td style={{ minWidth: 220 }}>
                          <textarea
                            rows={2}
                            placeholder="Write what was discussed with the client…"
                            value={callNotes[c.id] || ''}
                            onChange={e => setCallNotes(prev => ({ ...prev, [c.id]: e.target.value }))}
                            onBlur={() => saveCallData(c.id, { phone_call_notes: callNotes[c.id] || '' })}
                            style={{
                              width: '100%', fontSize: 12, padding: '5px 8px',
                              border: '1px solid #e2e8f0', borderRadius: 6,
                              resize: 'vertical', fontFamily: 'inherit',
                              background: callNotes[c.id] ? '#fffbeb' : '#f8fafc',
                              color: '#0f172a', outline: 'none', boxSizing: 'border-box',
                            }}
                          />
                          {savingCall === c.id && <span style={{ fontSize: 10, color: '#94a3b8' }}>saving…</span>}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

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
