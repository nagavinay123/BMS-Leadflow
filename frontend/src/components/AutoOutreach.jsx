/**
 * AutoOutreach — optional post-search email dispatch panel
 *
 * Default: OFF (toggle must be enabled by user).
 * Eligible leads = score ≥ threshold + verified email + CH-matched + not already contacted + not suppressed.
 * dry_run=true (default): drafts are saved, no emails sent — safe to preview anytime.
 * dry_run=false: emails are sent and statuses updated (requires confirmation).
 */

import { useState } from 'react'

const API = import.meta.env.VITE_API_URL || ''

const RESULT_COLORS = {
  sent:    { bg: '#064e3b', border: '#10b981', label: '#6ee7b7' },
  dry_run: { bg: '#1e3a5f', border: '#3b82f6', label: '#93c5fd' },
  failed:  { bg: '#4c1d24', border: '#f87171', label: '#fca5a5' },
  skipped: { bg: '#374151', border: '#9ca3af', label: '#d1d5db' },
}

export default function AutoOutreach({ runId, userEmail }) {
  const [enabled,     setEnabled]     = useState(false)
  const [dryRun,      setDryRun]      = useState(true)
  const [confirming,  setConfirming]  = useState(false)
  const [loading,     setLoading]     = useState(false)
  const [result,      setResult]      = useState(null)
  const [error,       setError]       = useState(null)

  function reset() {
    setResult(null)
    setError(null)
    setConfirming(false)
  }

  function handleToggle() {
    if (enabled) { setEnabled(false); reset() }
    else         { setEnabled(true) }
  }

  async function runOutreach() {
    setConfirming(false)
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const r = await fetch(`${API}/api/auto-outreach`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          run_id:     runId || null,
          dry_run:    dryRun,
          user_email: userEmail || null,
        }),
      })
      if (!r.ok) {
        let detail = `HTTP ${r.status}`
        try { const e = await r.json(); detail = e.detail || detail } catch {}
        throw new Error(detail)
      }
      setResult(await r.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  /* ── styles ─────────────────────────────────────────────────── */
  const card = {
    background: '#1e2433',
    border: '1px solid #2d3748',
    borderRadius: 10,
    padding: '16px 20px',
    marginTop: 16,
    maxWidth: '100%',
  }
  const row = { display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }
  const badge = (color, bg) => ({
    display: 'inline-block',
    padding: '2px 10px',
    borderRadius: 12,
    fontSize: 11,
    fontWeight: 700,
    color,
    background: bg,
  })

  /* ── toggle pill ─────────────────────────────────────────────── */
  const toggleBtn = (
    <button
      onClick={handleToggle}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 7,
        padding: '6px 14px', borderRadius: 20, cursor: 'pointer',
        fontSize: 13, fontWeight: 600,
        border: `1px solid ${enabled ? '#10b981' : '#4b5563'}`,
        background: enabled ? 'rgba(16,185,129,0.12)' : 'rgba(75,85,99,0.18)',
        color: enabled ? '#6ee7b7' : '#9ca3af',
        transition: 'all 0.2s',
      }}
    >
      <span style={{
        width: 28, height: 16, borderRadius: 8, position: 'relative',
        background: enabled ? '#10b981' : '#374151',
        display: 'inline-block', transition: 'background 0.2s',
      }}>
        <span style={{
          position: 'absolute', top: 2, left: enabled ? 14 : 2,
          width: 12, height: 12, borderRadius: '50%',
          background: '#fff', transition: 'left 0.2s',
        }} />
      </span>
      Auto Outreach {enabled ? 'ON' : 'OFF'}
    </button>
  )

  if (!enabled) {
    return (
      <div style={{ ...card, display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ color: '#6b7280', fontSize: 13 }}>
          📨 Auto Outreach — automatically email eligible leads from this search
        </span>
        {toggleBtn}
      </div>
    )
  }

  /* ── result panel ─────────────────────────────────────────────── */
  if (result) {
    const isLive = !result.dry_run
    const sentColor   = RESULT_COLORS.sent
    const dryColor    = RESULT_COLORS.dry_run
    const failColor   = RESULT_COLORS.failed

    return (
      <div style={card}>
        <div style={{ ...row, marginBottom: 14 }}>
          {toggleBtn}
          <span style={{ color: '#9ca3af', fontSize: 13 }}>
            {isLive ? '✅ Emails sent' : '🔵 Dry run complete — no emails sent'}
          </span>
          <button onClick={reset}
            style={{ marginLeft: 'auto', background: 'none', border: '1px solid #4b5563',
              color: '#9ca3af', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontSize: 12 }}>
            ↩ Run again
          </button>
        </div>

        {/* Summary cards */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 14 }}>
          {[
            ['Found',    result.found,    '#e5e7eb', '#374151'],
            ['Eligible', result.eligible, '#fde68a', '#78350f'],
            [isLive ? 'Sent' : 'Drafted', isLive ? result.sent : result.skipped,
              isLive ? sentColor.label : dryColor.label,
              isLive ? sentColor.bg    : dryColor.bg],
            ['Failed',   result.failed,  failColor.label, failColor.bg],
          ].map(([label, val, color, bg]) => (
            <div key={label} style={{
              background: bg, border: `1px solid ${color}22`,
              borderRadius: 8, padding: '8px 16px', textAlign: 'center', minWidth: 80,
            }}>
              <div style={{ fontSize: 22, fontWeight: 700, color }}>{val}</div>
              <div style={{ fontSize: 11, color, opacity: 0.8 }}>{label}</div>
            </div>
          ))}
        </div>

        {/* Details table */}
        {result.details && result.details.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ color: '#6b7280', borderBottom: '1px solid #2d3748' }}>
                  <th style={{ textAlign: 'left', padding: '6px 8px' }}>Company</th>
                  <th style={{ textAlign: 'left', padding: '6px 8px' }}>Email</th>
                  <th style={{ textAlign: 'center', padding: '6px 8px' }}>Score</th>
                  <th style={{ textAlign: 'center', padding: '6px 8px' }}>Result</th>
                  {isLive && <th style={{ textAlign: 'left', padding: '6px 8px' }}>Subject</th>}
                  {!isLive && <th style={{ textAlign: 'left', padding: '6px 8px' }}>Note</th>}
                </tr>
              </thead>
              <tbody>
                {result.details.map((d, i) => {
                  const rc = RESULT_COLORS[d.result] || RESULT_COLORS.skipped
                  return (
                    <tr key={d.company_id || i} style={{ borderBottom: '1px solid #1a2030' }}>
                      <td style={{ padding: '6px 8px', color: '#e2e8f0' }}>{d.name}</td>
                      <td style={{ padding: '6px 8px', color: '#94a3b8', fontSize: 11 }}>{d.email}</td>
                      <td style={{ padding: '6px 8px', textAlign: 'center', color: '#fbbf24' }}>{d.score}</td>
                      <td style={{ padding: '6px 8px', textAlign: 'center' }}>
                        <span style={badge(rc.label, rc.bg)}>{d.result}</span>
                      </td>
                      <td style={{ padding: '6px 8px', color: '#64748b', fontSize: 11 }}>
                        {d.subject || d.reason || '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    )
  }

  /* ── confirmation dialog ─────────────────────────────────────── */
  if (confirming) {
    return (
      <div style={card}>
        <div style={{ ...row, marginBottom: 12 }}>
          {toggleBtn}
        </div>
        <div style={{
          background: dryRun ? 'rgba(59,130,246,0.08)' : 'rgba(239,68,68,0.08)',
          border: `1px solid ${dryRun ? '#3b82f6' : '#ef4444'}`,
          borderRadius: 8, padding: '14px 18px', marginBottom: 14,
        }}>
          <p style={{ margin: '0 0 6px', color: '#e2e8f0', fontWeight: 600, fontSize: 14 }}>
            {dryRun
              ? '🔵 Dry Run — no emails will be sent'
              : '⚠️ Live Send — real emails will be sent'}
          </p>
          <p style={{ margin: 0, color: '#94a3b8', fontSize: 13 }}>
            {dryRun
              ? 'This will identify eligible leads and save email drafts only. Safe to run at any time.'
              : 'This will send emails to all eligible leads from this search run. This action cannot be undone.'}
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: '#9ca3af', fontSize: 13 }}>
            <input
              type="checkbox"
              checked={!dryRun}
              onChange={e => setDryRun(!e.target.checked)}
              style={{ accentColor: '#ef4444' }}
            />
            Live send (uncheck for dry run)
          </label>
          <button
            onClick={runOutreach}
            style={{
              padding: '7px 20px', borderRadius: 6, cursor: 'pointer',
              fontWeight: 700, fontSize: 13,
              background: dryRun ? '#1d4ed8' : '#dc2626',
              color: '#fff', border: 'none',
            }}
          >
            {dryRun ? '▶ Run Dry Run' : '🚀 Send Emails'}
          </button>
          <button
            onClick={() => setConfirming(false)}
            style={{
              padding: '7px 16px', borderRadius: 6, cursor: 'pointer',
              fontSize: 13, background: 'none',
              color: '#6b7280', border: '1px solid #374151',
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  /* ── enabled, idle ────────────────────────────────────────────── */
  return (
    <div style={card}>
      <div style={{ ...row, marginBottom: 10 }}>
        {toggleBtn}
        <span style={{ color: '#94a3b8', fontSize: 13 }}>
          Ready to identify eligible leads from this search and send personalised emails.
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', color: '#9ca3af', fontSize: 13 }}>
          <input
            type="checkbox"
            checked={!dryRun}
            onChange={e => setDryRun(!e.target.checked)}
            style={{ accentColor: '#ef4444' }}
          />
          Live send (uncheck = dry run)
        </label>
        <button
          onClick={() => setConfirming(true)}
          disabled={loading}
          style={{
            padding: '7px 20px', borderRadius: 6, cursor: 'pointer',
            fontWeight: 700, fontSize: 13,
            background: loading ? '#374151' : (dryRun ? '#1e3a5f' : '#7f1d1d'),
            color: loading ? '#6b7280' : (dryRun ? '#93c5fd' : '#fca5a5'),
            border: `1px solid ${dryRun ? '#3b82f6' : '#ef4444'}`,
            transition: 'all 0.2s',
          }}
        >
          {loading ? '⏳ Running…' : (dryRun ? '▶ Preview Eligible Leads' : '🚀 Send Emails to Eligible Leads')}
        </button>
      </div>
      {error && (
        <div style={{ marginTop: 10, color: '#fca5a5', fontSize: 13 }}>
          ❌ {error}
        </div>
      )}
    </div>
  )
}
