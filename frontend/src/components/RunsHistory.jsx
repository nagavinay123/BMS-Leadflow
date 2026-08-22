import { useState } from 'react'

export default function RunsHistory({ runs, onViewRun, onDeleted }) {
  const [selected, setSelected] = useState(new Set())
  const [deleting, setDeleting] = useState(false)

  if (!runs || runs.length === 0) {
    return (
      <div className="card">
        <div className="card-header">
          <span className="card-title">Discovery Runs</span>
        </div>
        <div className="empty-state">No runs yet. Run a search to see history here.</div>
      </div>
    )
  }

  function toggleAll() {
    if (selected.size === runs.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(runs.map(r => r.id)))
    }
  }

  function toggleOne(id) {
    const next = new Set(selected)
    next.has(id) ? next.delete(id) : next.add(id)
    setSelected(next)
  }

  async function deleteSelected() {
    if (selected.size === 0) return
    if (!confirm(`Delete ${selected.size} run${selected.size > 1 ? 's' : ''}? This cannot be undone.`)) return
    setDeleting(true)
    try {
      const res = await fetch('/api/runs', {
        method:  'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ run_ids: [...selected] }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
      }
      setSelected(new Set())
      onDeleted?.()
    } catch (e) {
      alert('Delete failed: ' + e.message)
    } finally {
      setDeleting(false)
    }
  }

  const allChecked = selected.size === runs.length
  const someChecked = selected.size > 0 && selected.size < runs.length

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <span className="card-title">Discovery Runs ({runs.length})</span>
          <span style={{ marginLeft: 12, fontSize: 12, color: 'var(--gray-400)' }}>
            Select runs to delete
          </span>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          {selected.size > 0 && (
            <span style={{ fontSize: 12, color: 'var(--gray-600)', fontWeight: 600 }}>
              {selected.size} selected
            </span>
          )}
          <button
            className="btn btn-secondary"
            style={{
              padding: '6px 14px', fontSize: 13,
              color: selected.size > 0 ? 'var(--red)' : 'var(--gray-400)',
              borderColor: selected.size > 0 ? '#fca5a5' : undefined,
              opacity: selected.size === 0 ? 0.4 : 1,
            }}
            disabled={selected.size === 0 || deleting}
            onClick={deleteSelected}
          >
            {deleting ? 'Deleting…' : `🗑 Delete${selected.size > 0 ? ` (${selected.size})` : ''}`}
          </button>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th style={{ width: 40, textAlign: 'center' }}>
                <input
                  type="checkbox"
                  checked={allChecked}
                  ref={el => { if (el) el.indeterminate = someChecked }}
                  onChange={toggleAll}
                  style={{ cursor: 'pointer', width: 15, height: 15 }}
                />
              </th>
              <th>Run ID</th>
              <th>Business Type</th>
              <th>Town</th>
              <th>Results</th>
              <th>Est. Cost</th>
              <th>Status</th>
              <th>Date / Time</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {runs.map(run => {
              const q      = run.query || {}
              const ranAt  = run.ran_at ? new Date(run.ran_at).toLocaleString('en-GB') : '—'
              const status = run.status || 'unknown'
              const isSelected = selected.has(run.id)

              return (
                <tr
                  key={run.id}
                  style={{ background: isSelected ? '#eff6ff' : undefined }}
                >
                  <td style={{ textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleOne(run.id)}
                      style={{ cursor: 'pointer', width: 15, height: 15 }}
                    />
                  </td>
                  <td><span className="td-mono">{run.id?.slice(0, 8)}…</span></td>
                  <td><strong>{q.business_type || '—'}</strong></td>
                  <td>{q.town || '—'}</td>
                  <td><strong>{run.results_count ?? 0}</strong></td>
                  <td>${run.est_cost_usd?.toFixed(4) ?? '0.0000'}</td>
                  <td>
                    <span className={`badge ${
                      status === 'complete' ? 'badge-green' :
                      status === 'running'  ? 'badge-amber' : 'badge-red'
                    }`}>
                      {status}
                    </span>
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--gray-400)' }}>{ranAt}</td>
                  <td>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '4px 12px', fontSize: 12 }}
                      onClick={() => onViewRun(run.id)}
                    >
                      View →
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
