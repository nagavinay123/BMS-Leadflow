import { useState, useEffect } from 'react'

// Status → visual config
const STATUS_CONFIG = {
  READY: {
    icon: '✅',
    badge: { background: '#dcfce7', color: '#166534', border: '1px solid #86efac' },
    label: 'READY',
  },
  NOT_CONFIGURED: {
    icon: '❌',
    badge: { background: '#fee2e2', color: '#dc2626', border: '1px solid #fca5a5' },
    label: 'NOT CONFIGURED',
  },
  BUSINESS_ACTION_REQUIRED: {
    icon: '⚠️',
    badge: { background: '#fef3c7', color: '#92400e', border: '1px solid #fbbf24' },
    label: 'BUSINESS ACTION REQUIRED',
  },
  TECHNICAL_ACTION_REQUIRED: {
    icon: '🔧',
    badge: { background: '#eff6ff', color: '#1d4ed8', border: '1px solid #93c5fd' },
    label: 'TECHNICAL ACTION REQUIRED',
  },
  BLOCKED: {
    icon: '🔒',
    badge: { background: '#fdf2f8', color: '#9d174d', border: '1px solid #f9a8d4' },
    label: 'BLOCKED',
  },
}

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.NOT_CONFIGURED
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: '2px 8px',
      borderRadius: 12, letterSpacing: '0.04em',
      ...cfg.badge,
    }}>
      {cfg.icon} {cfg.label}
    </span>
  )
}

// Colour of the gate row border-left
function gateBorderColor(status) {
  return {
    READY:                    '#16a34a',
    NOT_CONFIGURED:           '#dc2626',
    BUSINESS_ACTION_REQUIRED: '#d97706',
    TECHNICAL_ACTION_REQUIRED:'#2563eb',
    BLOCKED:                  '#9d174d',
  }[status] || '#94a3b8'
}

// Group gates for display
const GATE_GROUPS = [
  {
    title: '🔑 API Keys & Configuration',
    ids: ['pecr_structural', 'millionverifier', 'sending_platform', 'dry_run_disabled', 'anthropic'],
  },
  {
    title: '📋 Legal & Business Requirements',
    ids: ['warmup', 'lia', 'privacy_notice'],
    note: 'These cannot be completed by Claude. A human operator must take the real-world action and then update backend/.env.',
  },
  {
    title: '🌐 DNS Records (sending domain)',
    ids: ['spf', 'dkim', 'dmarc'],
  },
]

export default function CompliancePage() {
  const [readiness,  setReadiness]  = useState(null)
  const [suppression, setSuppression] = useState([])
  const [addForm,    setAddForm]    = useState({ email: '', domain: '', reason: 'manual' })
  const [adding,     setAdding]     = useState(false)
  const [loading,    setLoading]    = useState(true)
  const [probing,    setProbing]    = useState(false)
  const [search,     setSearch]     = useState('')
  const [expanded,   setExpanded]   = useState({})

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true)
    try {
      const [pr, sup] = await Promise.all([
        fetch('/api/production-readiness').then(r => r.json()),
        fetch('/api/suppression').then(r => r.json()),
      ])
      setReadiness(pr)
      setSuppression(Array.isArray(sup) ? sup : [])
    } catch {}
    setLoading(false)
  }

  async function probeAuth() {
    setProbing(true)
    try {
      const pr = await fetch('/api/production-readiness?probe=true').then(r => r.json())
      setReadiness(pr)
    } catch {}
    setProbing(false)
  }

  async function addToSuppression() {
    if (!addForm.email && !addForm.domain) return
    setAdding(true)
    try {
      await fetch('/api/suppression', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(addForm),
      })
      setAddForm({ email: '', domain: '', reason: 'manual' })
      await loadData()
    } catch (e) { alert('Failed: ' + e.message) }
    setAdding(false)
  }

  const checks   = readiness?.checks || {}
  const blockers = readiness?.blockers || []
  const isReady  = readiness?.ready_for_live_sending === true
  const dryRun   = readiness?.dry_run_active !== false

  const filtered = suppression.filter(s =>
    !search || (s.email || '').includes(search) || (s.domain || '').includes(search)
  )

  return (
    <div>

      {/* ── Live Sending Gate banner ── */}
      <div style={{
        borderRadius: 10, padding: '16px 20px', marginBottom: 20,
        background: isReady ? '#dcfce7' : dryRun ? '#f0f9ff' : '#fee2e2',
        border: `2px solid ${isReady ? '#16a34a' : dryRun ? '#0ea5e9' : '#dc2626'}`,
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap',
      }}>
        <div>
          <div style={{ fontWeight: 800, fontSize: 15, color: isReady ? '#14532d' : dryRun ? '#0c4a6e' : '#7f1d1d' }}>
            {isReady
              ? '✅ READY FOR LIVE SENDING'
              : dryRun
                ? '🔒 DRY-RUN MODE — No real emails will be sent'
                : '❌ NOT READY — Live sending is blocked'}
          </div>
          <div style={{ fontSize: 12, marginTop: 4, color: '#374151' }}>
            {readiness?.note || ''}
            {!isReady && blockers.length > 0 && (
              <span style={{ marginLeft: 8, color: '#dc2626', fontWeight: 600 }}>
                {blockers.length} blocker{blockers.length !== 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn" onClick={loadData} style={{ fontSize: 12, padding: '5px 14px' }}>
            🔄 Refresh
          </button>
          <button className="btn" onClick={probeAuth} disabled={probing}
            style={{ fontSize: 12, padding: '5px 14px', background: '#eff6ff', color: '#1d4ed8', border: '1px solid #93c5fd' }}>
            {probing ? 'Probing…' : '🔌 Probe sending platform'}
          </button>
        </div>
      </div>

      {/* ── Blockers summary ── */}
      {blockers.length > 0 && (
        <div style={{
          background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 10,
          padding: '12px 16px', marginBottom: 20,
        }}>
          <div style={{ fontWeight: 700, fontSize: 13, color: '#991b1b', marginBottom: 8 }}>
            🚨 Live sending is blocked until all of the following are resolved:
          </div>
          {blockers.map((b, i) => (
            <div key={i} style={{ fontSize: 12, color: '#7f1d1d', padding: '2px 0' }}>• {b}</div>
          ))}
        </div>
      )}

      {/* ── Gate groups ── */}
      {GATE_GROUPS.map(group => {
        const groupChecks = group.ids
          .map(id => ({ id, ...(checks[id] || {}) }))
          .filter(c => c.status)
        if (!groupChecks.length) return null

        return (
          <div key={group.title} className="card" style={{ marginBottom: 16 }}>
            <div className="card-header">
              <span className="card-title" style={{ fontSize: 13 }}>{group.title}</span>
              <span style={{ fontSize: 12, color: '#64748b' }}>
                {groupChecks.filter(c => c.status === 'READY').length}/{groupChecks.length} ready
              </span>
            </div>

            {group.note && (
              <div style={{
                background: '#fef3c7', borderBottom: '1px solid #fde68a',
                padding: '8px 16px', fontSize: 12, color: '#78350f',
              }}>
                ⚠️ {group.note}
              </div>
            )}

            {groupChecks.map(c => {
              const isExpanded = expanded[c.id]
              return (
                <div key={c.id} style={{
                  borderLeft: `4px solid ${gateBorderColor(c.status)}`,
                  padding: '12px 16px',
                  borderBottom: '1px solid #f1f5f9',
                  cursor: 'pointer',
                }} onClick={() => setExpanded(e => ({ ...e, [c.id]: !e[c.id] }))}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
                      <span style={{ fontSize: 16 }}>{STATUS_CONFIG[c.status]?.icon || '?'}</span>
                      <span style={{ fontSize: 13, fontWeight: 600, color: '#1e293b' }}>{c.label || c.id}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <StatusBadge status={c.status} />
                      <span style={{ fontSize: 12, color: '#94a3b8' }}>{isExpanded ? '▲' : '▼'}</span>
                    </div>
                  </div>

                  {/* Detail row — always visible */}
                  <div style={{ fontSize: 12, color: '#64748b', marginTop: 4, paddingLeft: 28 }}>
                    {c.detail}
                  </div>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div style={{
                      marginTop: 10, paddingLeft: 28,
                      borderTop: '1px dashed #e2e8f0', paddingTop: 10,
                    }}>
                      {c.action_required && (
                        <div style={{
                          background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6,
                          padding: '8px 12px', marginBottom: 8,
                        }}>
                          <div style={{ fontSize: 11, fontWeight: 700, color: '#475569', marginBottom: 3 }}>
                            ACTION REQUIRED
                          </div>
                          <div style={{ fontSize: 12, color: '#1e293b' }}>{c.action_required}</div>
                        </div>
                      )}
                      <div style={{ display: 'flex', gap: 20, fontSize: 11, color: '#64748b' }}>
                        <span><strong>Who must act:</strong> {c.who_must_act || '—'}</span>
                        <span>
                          <strong>Claude can verify:</strong>{' '}
                          {c.can_claude_verify
                            ? '✅ Yes — click Refresh to re-check'
                            : '❌ No — human confirmation required'}
                        </span>
                        {!c.mandatory && (
                          <span style={{ color: '#16a34a' }}>ℹ️ Optional (not a hard blocker)</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )
      })}

      {loading && (
        <div style={{ padding: 20, textAlign: 'center', color: '#94a3b8', fontSize: 13 }}>
          Loading compliance status…
        </div>
      )}

      {/* ── Suppression list ── */}
      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-header">
          <span className="card-title">Suppression List ({suppression.length})</span>
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search email / domain…"
            style={{ padding: '4px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13 }}
          />
        </div>

        <div style={{
          padding: '12px 16px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0',
          display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end',
        }}>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: '#64748b', marginBottom: 3 }}>Email</label>
            <input
              value={addForm.email} onChange={e => setAddForm(f => ({ ...f, email: e.target.value }))}
              placeholder="someone@company.co.uk"
              style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13, width: 220 }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: '#64748b', marginBottom: 3 }}>Domain</label>
            <input
              value={addForm.domain} onChange={e => setAddForm(f => ({ ...f, domain: e.target.value }))}
              placeholder="company.co.uk"
              style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13, width: 160 }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 11, color: '#64748b', marginBottom: 3 }}>Reason</label>
            <select
              value={addForm.reason} onChange={e => setAddForm(f => ({ ...f, reason: e.target.value }))}
              style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13, height: 34 }}
            >
              <option value="manual">Manual</option>
              <option value="unsubscribe">Unsubscribe</option>
              <option value="bounce">Bounce</option>
              <option value="client">BMS Client</option>
              <option value="objection">Objection</option>
            </select>
          </div>
          <button
            className="btn btn-primary" style={{ padding: '6px 16px' }}
            disabled={adding || (!addForm.email && !addForm.domain)}
            onClick={addToSuppression}
          >
            {adding ? 'Adding…' : '+ Suppress'}
          </button>
        </div>

        {loading ? (
          <div style={{ padding: 20, textAlign: 'center', color: '#94a3b8' }}>Loading…</div>
        ) : filtered.length === 0 ? (
          <div style={{ padding: 24, textAlign: 'center', color: '#94a3b8', fontSize: 13 }}>
            {search ? 'No matches found.' : 'Suppression list is empty.'}
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Email</th><th>Domain</th><th>Company #</th><th>Reason</th><th>Added</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(s => (
                  <tr key={s.id}>
                    <td style={{ fontSize: 12 }}>{s.email || '—'}</td>
                    <td style={{ fontSize: 12 }}>{s.domain || '—'}</td>
                    <td style={{ fontSize: 12 }}>{s.company_number || '—'}</td>
                    <td>
                      <span className={`badge badge-${s.reason === 'unsubscribe' ? 'red' : s.reason === 'bounce' ? 'amber' : 'gray'}`}>
                        {s.reason}
                      </span>
                    </td>
                    <td style={{ fontSize: 11, color: '#64748b' }}>
                      {s.added_at ? new Date(s.added_at).toLocaleDateString('en-GB') : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Legal notice ── */}
      <div style={{
        marginTop: 20, background: '#fef3c7', border: '1px solid #fbbf24',
        borderRadius: 10, padding: '16px 20px',
      }}>
        <div style={{ fontWeight: 700, fontSize: 14, color: '#92400e', marginBottom: 8 }}>
          ⚖️ Legal Documents Required Before Live Sending
        </div>
        <p style={{ fontSize: 13, color: '#78350f', margin: '0 0 8px' }}>
          The following must be completed by James / BMS legal team. LeadFlow cannot generate or approve them.
        </p>
        <ul style={{ fontSize: 13, color: '#78350f', margin: 0, paddingLeft: 20 }}>
          <li><strong>Legitimate Interests Assessment (LIA)</strong> — document why BMS has a legitimate interest under PECR / UK GDPR Art. 6(1)(f). Once signed off, set <code>LIA_APPROVED=true</code> in backend/.env.</li>
          <li><strong>Privacy Notice</strong> — must be published at bemysocial.co.uk/privacy. Once live, set <code>PRIVACY_NOTICE_CONFIRMED=true</code> in backend/.env.</li>
          <li><strong>Inbox warmup</strong> — 6–8 weeks at 20 emails/day before any live campaign. Once complete, set <code>EMAIL_WARMUP_COMPLETED=true</code> in backend/.env.</li>
          <li><strong>SPF / DKIM / DMARC</strong> — DNS records must be added to the sending domain. Check status in the DNS section above.</li>
        </ul>
      </div>
    </div>
  )
}
