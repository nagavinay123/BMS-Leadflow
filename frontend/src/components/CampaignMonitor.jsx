import { useState, useEffect } from 'react'

const STATUS_COLORS = {
  draft:     '#94a3b8',
  active:    '#16a34a',
  paused:    '#d97706',
  completed: '#2563eb',
  cancelled: '#dc2626',
}

function StatTile({ label, value, color, sub }) {
  return (
    <div style={{
      background: '#fff', borderRadius: 10, padding: '16px 20px',
      boxShadow: '0 1px 4px rgba(0,0,0,0.06)', minWidth: 100, flex: 1,
    }}>
      <div style={{ fontSize: 26, fontWeight: 800, color: color || '#1e3764' }}>{value ?? '—'}</div>
      <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>{label}</div>
      {sub && <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 1 }}>{sub}</div>}
    </div>
  )
}

function pct(num, den) {
  if (!den || !num) return '0%'
  return `${Math.round((num / den) * 100)}%`
}

export default function CampaignMonitor() {
  const [campaigns, setCampaigns]   = useState([])
  const [selected,  setSelected]    = useState(null)
  const [stats,     setStats]       = useState(null)
  const [events,    setEvents]      = useState([])
  const [loading,   setLoading]     = useState(true)
  const [creating,  setCreating]    = useState(false)
  const [budget,    setBudget]      = useState(null)

  // New campaign form
  const [form, setForm] = useState({
    name: '', sender_name: 'James', sender_email: '',
    daily_limit: 25, weekly_budget: 0, dry_run: true,
  })

  useEffect(() => { loadCampaigns(); loadBudget() }, [])
  useEffect(() => { if (selected) loadCampaignDetail(selected) }, [selected])

  async function loadCampaigns() {
    setLoading(true)
    try {
      const data = await fetch('/api/campaigns').then(r => r.json())
      setCampaigns(Array.isArray(data) ? data : [])
      if (data?.length && !selected) setSelected(data[0].id)
    } catch {}
    setLoading(false)
  }

  async function loadCampaignDetail(id) {
    try {
      const [detail, evts] = await Promise.all([
        fetch(`/api/campaigns/${id}`).then(r => r.json()),
        fetch(`/api/events?campaign_id=${id}&limit=50`).then(r => r.json()),
      ])
      setStats(detail?.stats || detail)
      setEvents(Array.isArray(evts) ? evts : [])
    } catch {}
  }

  async function loadBudget() {
    try {
      const b = await fetch('/api/budget').then(r => r.json())
      setBudget(b)
    } catch {}
  }

  async function createCampaign() {
    try {
      await fetch('/api/campaigns', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      setCreating(false)
      await loadCampaigns()
    } catch (e) { alert('Failed to create campaign: ' + e.message) }
  }

  async function updateStatus(id, status) {
    await fetch(`/api/campaigns/${id}/status`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    })
    await loadCampaigns()
    if (selected === id) await loadCampaignDetail(id)
  }

  async function triggerFollowUps() {
    const r = await fetch('/api/process-follow-ups', { method: 'POST' }).then(r => r.json())
    alert(`Processed: ${r.processed} follow-ups | Sent: ${r.sent} | Skipped: ${r.skipped}`)
  }

  const cam = campaigns.find(c => c.id === selected)

  return (
    <div>
      {/* Budget banner */}
      {budget && (
        <div style={{
          background: budget.month_to_date_gbp > 80 ? '#fee2e2' : '#f0fdf4',
          border: `1px solid ${budget.month_to_date_gbp > 80 ? '#fca5a5' : '#86efac'}`,
          borderRadius: 10, padding: '12px 20px', marginBottom: 20,
          display: 'flex', gap: 24, alignItems: 'center', flexWrap: 'wrap',
        }}>
          <span style={{ fontWeight: 700, fontSize: 14 }}>
            💷 Monthly Budget: £{budget.month_to_date_gbp?.toFixed(2)} / £100.00
          </span>
          <div style={{
            flex: 1, minWidth: 200, background: '#e2e8f0', borderRadius: 4, height: 8,
          }}>
            <div style={{
              width: `${Math.min(100, (budget.month_to_date_gbp / 100) * 100)}%`,
              height: 8, borderRadius: 4,
              background: budget.month_to_date_gbp > 80 ? '#dc2626' : '#16a34a',
            }} />
          </div>
          <span style={{ fontSize: 13, color: '#64748b' }}>
            £{budget.remaining_gbp?.toFixed(2)} remaining
          </span>
        </div>
      )}

      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        {/* Left: campaign list */}
        <div style={{ width: 240, minWidth: 200 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>Campaigns</h3>
            <button
              className="btn btn-primary"
              style={{ padding: '4px 10px', fontSize: 12 }}
              onClick={() => setCreating(c => !c)}
            >
              + New
            </button>
          </div>

          {creating && (
            <div style={{
              background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10,
              padding: 16, marginBottom: 12,
            }}>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>New Campaign</div>
              {[
                ['name', 'Campaign Name', 'text'],
                ['sender_name', 'Sender Name', 'text'],
                ['sender_email', 'Sender Email', 'email'],
                ['daily_limit', 'Daily Limit', 'number'],
              ].map(([k, label, type]) => (
                <div key={k} style={{ marginBottom: 8 }}>
                  <label style={{ fontSize: 11, color: '#64748b' }}>{label}</label>
                  <input
                    type={type} value={form[k]} onChange={e => setForm(f => ({ ...f, [k]: e.target.value }))}
                    style={{ width: '100%', padding: '6px 8px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: 13, boxSizing: 'border-box' }}
                  />
                </div>
              ))}
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, marginBottom: 12 }}>
                <input type="checkbox" checked={form.dry_run} onChange={e => setForm(f => ({ ...f, dry_run: e.target.checked }))} />
                Dry Run (safe — no real emails)
              </label>
              <div style={{ display: 'flex', gap: 6 }}>
                <button className="btn btn-primary" style={{ flex: 1, padding: '6px' }} onClick={createCampaign}>Create</button>
                <button className="btn btn-secondary" style={{ padding: '6px 10px' }} onClick={() => setCreating(false)}>Cancel</button>
              </div>
            </div>
          )}

          {loading ? (
            <div style={{ color: '#94a3b8', fontSize: 13, padding: 8 }}>Loading…</div>
          ) : campaigns.length === 0 ? (
            <div style={{ color: '#94a3b8', fontSize: 13, padding: 8 }}>No campaigns yet.</div>
          ) : (
            campaigns.map(c => (
              <div
                key={c.id}
                onClick={() => setSelected(c.id)}
                style={{
                  padding: '10px 14px', borderRadius: 8, cursor: 'pointer', marginBottom: 6,
                  background: selected === c.id ? '#1e3764' : '#fff',
                  color:      selected === c.id ? '#fff' : '#1e293b',
                  border:     selected === c.id ? '1px solid #1e3764' : '1px solid #e2e8f0',
                }}
              >
                <div style={{ fontSize: 13, fontWeight: 600 }}>{c.name}</div>
                <div style={{ fontSize: 11, marginTop: 2, opacity: 0.75, display: 'flex', gap: 6 }}>
                  <span style={{ color: STATUS_COLORS[c.status], fontWeight: 700 }}>{c.status}</span>
                  {c.dry_run && <span style={{ color: '#d97706' }}>• DRY RUN</span>}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Right: campaign detail */}
        <div style={{ flex: 1, minWidth: 300 }}>
          {!cam ? (
            <div style={{ color: '#94a3b8', padding: 20 }}>Select a campaign</div>
          ) : (
            <>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
                <div>
                  <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800 }}>{cam.name}</h2>
                  <div style={{ display: 'flex', gap: 8, marginTop: 4, flexWrap: 'wrap' }}>
                    <span style={{
                      background: STATUS_COLORS[cam.status] + '22',
                      color: STATUS_COLORS[cam.status], padding: '2px 10px',
                      borderRadius: 20, fontSize: 12, fontWeight: 700,
                    }}>{cam.status}</span>
                    {cam.dry_run && (
                      <span style={{ background: '#fef3c7', color: '#d97706', padding: '2px 10px', borderRadius: 20, fontSize: 12, fontWeight: 700 }}>
                        🏖️ DRY RUN
                      </span>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {cam.status === 'draft' && (
                    <button className="btn btn-primary" style={{ padding: '6px 14px' }}
                      onClick={() => updateStatus(cam.id, 'active')}>▶ Activate</button>
                  )}
                  {cam.status === 'active' && (
                    <button className="btn btn-secondary" style={{ padding: '6px 14px' }}
                      onClick={() => updateStatus(cam.id, 'paused')}>⏸ Pause</button>
                  )}
                  {cam.status === 'paused' && (
                    <button className="btn btn-primary" style={{ padding: '6px 14px' }}
                      onClick={() => updateStatus(cam.id, 'active')}>▶ Resume</button>
                  )}
                  <button className="btn btn-secondary" style={{ padding: '6px 14px', fontSize: 12 }}
                    onClick={triggerFollowUps}>⏰ Process Follow-ups</button>
                </div>
              </div>

              {/* Stats */}
              {stats && (
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
                  <StatTile label="Members"     value={stats.member_count} color="#1e3764" />
                  <StatTile label="Sent"        value={stats.sent}         color="#2563eb" />
                  <StatTile label="Opens"       value={stats.opens}        color="#7c3aed"
                    sub={pct(stats.opens, stats.sent)} />
                  <StatTile label="Clicks"      value={stats.clicks}       color="#0891b2"
                    sub={pct(stats.clicks, stats.sent)} />
                  <StatTile label="Replies"     value={stats.replies}      color="#16a34a"
                    sub={pct(stats.replies, stats.sent)} />
                  <StatTile label="Bounces"     value={stats.bounces}      color="#dc2626"
                    sub={pct(stats.bounces, stats.sent)} />
                  <StatTile label="Unsubscribed" value={stats.unsubscribes} color="#b45309"
                    sub={pct(stats.unsubscribes, stats.sent)} />
                </div>
              )}

              {/* Campaign meta */}
              <div className="card" style={{ marginBottom: 20 }}>
                <div className="card-header">
                  <span className="card-title">Configuration</span>
                </div>
                <div style={{ padding: '12px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  {[
                    ['Sender', cam.sender_name],
                    ['Sender Email', cam.sender_email || '—'],
                    ['Daily Limit', `${cam.daily_limit} emails/day`],
                    ['Weekly Budget', cam.weekly_budget ? `£${cam.weekly_budget}` : '—'],
                    ['Created', cam.created_at ? new Date(cam.created_at).toLocaleDateString('en-GB') : '—'],
                  ].map(([k, v]) => (
                    <div key={k}>
                      <div style={{ fontSize: 11, color: '#94a3b8' }}>{k}</div>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>{v}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Recent events */}
              <div className="card">
                <div className="card-header">
                  <span className="card-title">Recent Events ({events.length})</span>
                </div>
                {events.length === 0 ? (
                  <div style={{ padding: 20, textAlign: 'center', color: '#94a3b8', fontSize: 13 }}>
                    No events yet. {cam.dry_run ? 'DRY RUN mode — events simulated only.' : 'Events will appear as emails are sent.'}
                  </div>
                ) : (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Event</th><th>Email</th><th>Subject</th><th>When</th>
                        </tr>
                      </thead>
                      <tbody>
                        {events.slice(0, 20).map(e => (
                          <tr key={e.id}>
                            <td>
                              <span className={`badge badge-${
                                {sent:'navy',open:'green',click:'navy',reply:'green',bounce:'red',unsubscribe:'amber'}[e.event_type]||'gray'
                              }`}>
                                {e.event_type}
                              </span>
                            </td>
                            <td style={{ fontSize: 12 }}>{e.email || '—'}</td>
                            <td style={{ fontSize: 12, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {e.subject || '—'}
                            </td>
                            <td style={{ fontSize: 11, color: '#64748b' }}>
                              {e.occurred_at ? new Date(e.occurred_at).toLocaleString('en-GB') : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
