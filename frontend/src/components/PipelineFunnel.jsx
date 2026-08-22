/**
 * PipelineFunnel — shows how many companies survive each pipeline stage
 * Props: stats from GET /api/stats
 */
export default function PipelineFunnel({ stats }) {
  if (!stats || !stats.total) {
    return (
      <div className="card" style={{ textAlign: 'center', color: 'var(--gray-400)', padding: 48 }}>
        Run a search to see the pipeline funnel.
      </div>
    )
  }

  const enriched = (stats.by_status || {})['enriched'] || 0
  const outreach = stats.outreach_ready || 0

  const stages = [
    {
      label:    'Discovered',
      sublabel: 'From Google Maps',
      count:    stats.total,
      color:    'var(--navy)',
      pct:      100,
      icon:     '📍',
    },
    {
      label:    'CH Matched',
      sublabel: 'Incorporated entities',
      count:    stats.ch_matched || 0,
      color:    '#2563eb',
      pct:      pct(stats.ch_matched, stats.total),
      icon:     '🏢',
    },
    {
      label:    'Has Website',
      sublabel: 'Auditable online presence',
      count:    stats.has_website || 0,
      color:    '#7c3aed',
      pct:      pct(stats.has_website, stats.total),
      icon:     '🌐',
    },
    {
      label:    'Enriched',
      sublabel: 'Audited + scored',
      count:    enriched,
      color:    '#0891b2',
      pct:      pct(enriched, stats.total),
      icon:     '✅',
    },
    {
      label:    'Outreach Ready',
      sublabel: 'Score ≥ 60',
      count:    outreach,
      color:    'var(--green)',
      pct:      pct(outreach, stats.total),
      icon:     '🚀',
    },
  ]

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Pipeline Funnel</span>
        <span style={{ fontSize: 12, color: 'var(--gray-400)' }}>
          {outreach} companies ready for outreach
        </span>
      </div>

      <div className="funnel-wrap">
        {stages.map((stage, i) => (
          <div key={i} className="funnel-stage">
            {/* Trapezoid bar */}
            <div
              className="funnel-bar"
              style={{
                width:      `${Math.max(stage.pct, 8)}%`,
                background: stage.color,
              }}
            >
              <span className="funnel-count">{stage.count}</span>
            </div>

            {/* Label */}
            <div className="funnel-label">
              <span className="funnel-icon">{stage.icon}</span>
              <span className="funnel-name">{stage.label}</span>
              <span className="funnel-sub">{stage.sublabel}</span>
              <span className="funnel-pct">{stage.pct}%</span>
            </div>

            {/* Drop arrow between stages */}
            {i < stages.length - 1 && (
              <div className="funnel-arrow">▼</div>
            )}
          </div>
        ))}
      </div>

      {/* Legend row */}
      <div style={{
        padding:        '16px 24px',
        borderTop:      '1px solid var(--gray-200)',
        display:        'flex',
        gap:            32,
        fontSize:       13,
        color:          'var(--gray-500)',
        flexWrap:       'wrap',
      }}>
        <span>🔴 <strong style={{ color: 'var(--navy)' }}>{stats.total}</strong> discovered</span>
        <span>🟡 <strong style={{ color: '#2563eb' }}>{stats.ch_matched || 0}</strong> CH matched ({stats.ch_match_pct || 0}%)</span>
        <span>🟢 <strong style={{ color: 'var(--green)' }}>{outreach}</strong> outreach ready ({stats.outreach_pct || 0}%)</span>
      </div>
    </div>
  )
}

function pct(n, total) {
  if (!total || n == null) return 0
  return Math.round((n / total) * 100)
}
