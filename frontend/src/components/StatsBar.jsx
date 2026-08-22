export default function StatsBar({ stats, lastRun }) {
  const discovered = stats?.total || 0
  const chMatched  = stats?.ch_matched || 0
  const hasWebsite = stats?.has_website || 0
  const outreach   = stats?.outreach_ready || 0
  const chPct      = stats?.ch_match_pct || 0
  const webPct     = stats?.website_pct || 0
  const outPct     = stats?.outreach_pct || 0

  return (
    <div>
      {lastRun && (
        <div className="run-banner">
          <span>
            ✅ Run complete — <strong>{lastRun.total_from_google}</strong> found ·{' '}
            <strong>{lastRun.ch_matched}</strong> CH matched ·{' '}
            <strong>{lastRun.stored}</strong> stored ·{' '}
            est. cost <strong>${(lastRun.est_cost_usd || 0).toFixed(4)}</strong>
          </span>
          <span style={{ opacity: 0.7, fontSize: 11 }}>
            Run {(lastRun.run_id || '').slice(0, 8)}
          </span>
        </div>
      )}

      <div className="stats-bar">
        <StatCard value={discovered}              label="Total Discovered" />
        <StatCard value={chMatched}   sub={`${chPct}% of total`}  label="CH Matched"      color="var(--navy)" />
        <StatCard value={hasWebsite}  sub={`${webPct}% of total`} label="Have Website"    color="#7c3aed" />
        <StatCard value={discovered - hasWebsite} label="No Website"      sub="no audit" color="var(--amber)" />
        <StatCard value={outreach}    sub={`${outPct}% · score ≥ 60`} label="Outreach Ready" color="var(--green)" />
      </div>
    </div>
  )
}

function StatCard({ value, label, sub, color }) {
  return (
    <div className="stat-card">
      <div className="stat-value" style={color ? { color } : {}}>
        {value ?? '—'}
      </div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}
