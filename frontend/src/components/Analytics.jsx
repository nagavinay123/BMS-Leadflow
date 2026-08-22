import { useState, useEffect } from 'react'

export default function Analytics() {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/analytics')
      .then(r => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div style={{ textAlign: 'center', padding: 60, color: 'var(--gray-400)' }}>
      Loading analytics…
    </div>
  )

  if (!data) return (
    <div style={{ textAlign: 'center', padding: 60, color: 'var(--gray-400)' }}>
      No analytics data yet. Run a search first.
    </div>
  )

  const { score_bands, totals, outreach, runs } = data

  const maxBand  = Math.max(...Object.values(score_bands), 1)
  const maxRun   = Math.max(...(runs || []).map(r => r.results_count || 0), 1)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* KPI row */}
      <div className="stats-bar">
        {[
          { label: 'Total Companies',   value: totals.companies,       color: 'var(--navy)'  },
          { label: 'CH Matched',        value: totals.ch_matched,      color: '#2563eb'      },
          { label: 'Have Website',      value: totals.has_website,     color: '#7c3aed'      },
          { label: 'Outreach Ready',    value: totals.outreach_ready,  color: 'var(--green)' },
          { label: 'Won',               value: outreach?.won || 0,     color: 'var(--green)' },
        ].map((k, i) => (
          <div key={i} className="stat-tile">
            <span className="stat-value" style={{ color: k.color }}>{k.value}</span>
            <span className="stat-label">{k.label}</span>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>

        {/* Score distribution */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Score Distribution</span>
          </div>
          <div style={{ padding: 20 }}>
            {Object.entries(score_bands).map(([label, count]) => {
              const colours = {
                'Cold (0-39)':   { bar: '#94a3b8', text: 'var(--gray-600)' },
                'Cool (40-59)':  { bar: 'var(--amber)', text: 'var(--amber)' },
                'Warm (60-79)':  { bar: 'var(--green)', text: 'var(--green)' },
                'Hot (80+)':     { bar: 'var(--orange)', text: 'var(--orange)' },
              }
              const c   = colours[label] || { bar: 'var(--navy)', text: 'var(--navy)' }
              const pct = Math.round((count / Math.max(totals.companies, 1)) * 100)
              return (
                <div key={label} style={{ marginBottom: 14 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 13 }}>
                    <span style={{ fontWeight: 600, color: c.text }}>{label}</span>
                    <span style={{ color: 'var(--gray-400)' }}>{count} ({pct}%)</span>
                  </div>
                  <div style={{ background: 'var(--gray-100)', borderRadius: 6, height: 12, overflow: 'hidden' }}>
                    <div style={{
                      height: '100%', borderRadius: 6,
                      width: `${(count / maxBand) * 100}%`,
                      background: c.bar,
                      transition: 'width .5s ease',
                    }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Outreach funnel */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Outreach Funnel</span>
          </div>
          <div style={{ padding: 20 }}>
            {outreach && [
              { label: 'Outreach Ready (≥60)', value: totals.outreach_ready, color: 'var(--navy)'  },
              { label: 'Queued',               value: outreach.queued,       color: '#2563eb'      },
              { label: 'Emailed',              value: outreach.emailed,      color: 'var(--amber)' },
              { label: 'Replied',              value: outreach.replied,      color: '#7c3aed'      },
              { label: 'Won 🏆',               value: outreach.won,          color: 'var(--green)' },
              { label: 'Lost',                 value: outreach.lost,         color: 'var(--red)'   },
            ].map((row, i) => (
              <div key={i} style={{ marginBottom: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 13 }}>
                  <span style={{ fontWeight: 600, color: row.color }}>{row.label}</span>
                  <span style={{ color: 'var(--gray-400)' }}>{row.value}</span>
                </div>
                <div style={{ background: 'var(--gray-100)', borderRadius: 6, height: 12, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%', borderRadius: 6,
                    width: `${(row.value / Math.max(totals.outreach_ready, 1)) * 100}%`,
                    background: row.color,
                    transition: 'width .5s ease',
                  }} />
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* Discovery runs history chart */}
      {runs && runs.length > 0 && (
        <div className="card">
          <div className="card-header">
            <span className="card-title">Discovery Runs</span>
            <span style={{ fontSize: 12, color: 'var(--gray-400)' }}>
              {runs.length} runs · total ${runs.reduce((s, r) => s + (r.est_cost_usd || 0), 0).toFixed(4)} API cost
            </span>
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ minWidth: 600 }}>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Query</th>
                  <th>Results</th>
                  <th>Cost</th>
                  <th>Status</th>
                  <th>Volume</th>
                </tr>
              </thead>
              <tbody>
                {[...runs].reverse().map((run, i) => {
                  const q    = run.query || {}
                  const date = run.ran_at ? new Date(run.ran_at).toLocaleDateString('en-GB') : '—'
                  const pct  = Math.round(((run.results_count || 0) / maxRun) * 100)
                  return (
                    <tr key={i}>
                      <td style={{ fontSize: 12, color: 'var(--gray-400)' }}>{date}</td>
                      <td>
                        <span style={{ fontWeight: 600 }}>{q.business_type || '—'}</span>
                        {q.town && <span style={{ color: 'var(--gray-400)', marginLeft: 6 }}>in {q.town}</span>}
                      </td>
                      <td><strong>{run.results_count || 0}</strong></td>
                      <td style={{ fontSize: 12, color: 'var(--gray-400)' }}>
                        ${(run.est_cost_usd || 0).toFixed(4)}
                      </td>
                      <td>
                        <span className={`badge ${run.status === 'complete' ? 'badge-green' : run.status === 'failed' ? 'badge-red' : 'badge-amber'}`}>
                          {run.status}
                        </span>
                      </td>
                      <td style={{ width: 120 }}>
                        <div style={{ background: 'var(--gray-100)', borderRadius: 4, height: 8 }}>
                          <div style={{ height: '100%', borderRadius: 4, width: `${pct}%`, background: 'var(--navy)' }} />
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
