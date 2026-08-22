import { useState } from 'react'

const BUSINESS_TYPES = [
  'plumber', 'electrician', 'accountant', 'solicitor', 'estate agent',
  'restaurant', 'dental practice', 'gym', 'hair salon', 'builder',
  'IT support', 'marketing agency', 'recruitment agency', 'architect',
]

const UK_TOWNS = [
  'London', 'Manchester', 'Birmingham', 'Leeds', 'Liverpool',
  'Sheffield', 'Bristol', 'Newcastle', 'Nottingham', 'Leicester',
  'Southampton', 'Portsmouth', 'Cardiff', 'Edinburgh', 'Glasgow',
]

export default function SearchForm({ onSearch, loading }) {
  const [businessType, setBusinessType] = useState('')
  const [town,         setTown]         = useState('')
  const [maxResults,   setMaxResults]   = useState(50)
  const [skipAudit,    setSkipAudit]    = useState(false)

  function handleSubmit(e) {
    e.preventDefault()
    if (!businessType.trim() || !town.trim()) return
    onSearch({ businessType: businessType.trim(), town: town.trim(), maxResults, skipAudit })
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Discovery Search</span>
        <span style={{ fontSize: 12, color: 'var(--gray-400)' }}>
          Google Maps + Companies House + Website Audit
        </span>
      </div>
      <div className="card-body">
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto auto', gap: 16, alignItems: 'end' }}>

            {/* Business type */}
            <div className="form-group">
              <label className="form-label">Business type</label>
              <input
                list="types-list"
                className="form-input"
                placeholder="e.g. plumber"
                value={businessType}
                onChange={e => setBusinessType(e.target.value)}
                disabled={loading}
                required
              />
              <datalist id="types-list">
                {BUSINESS_TYPES.map(t => <option key={t} value={t} />)}
              </datalist>
            </div>

            {/* Town */}
            <div className="form-group">
              <label className="form-label">Town / City</label>
              <input
                list="towns-list"
                className="form-input"
                placeholder="e.g. Leeds"
                value={town}
                onChange={e => setTown(e.target.value)}
                disabled={loading}
                required
              />
              <datalist id="towns-list">
                {UK_TOWNS.map(t => <option key={t} value={t} />)}
              </datalist>
            </div>

            {/* Max results */}
            <div className="form-group" style={{ minWidth: 120 }}>
              <label className="form-label">Max Results</label>
              <input
                type="number"
                className="form-input"
                min={0}
                max={10000}
                value={maxResults}
                onChange={e => {
                  const v = parseInt(e.target.value, 10)
                  if (!isNaN(v) && v >= 0) setMaxResults(Math.min(v, 10000))
                }}
                disabled={loading}
                style={{ width: '100%' }}
              />
              <span className="form-hint">0 – 10,000 results</span>
            </div>

            {/* Submit */}
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || !businessType || !town}
              style={{ height: 40 }}
            >
              {loading
                ? <><span className="spinner" /> Running…</>
                : '🔍 Find Leads'
              }
            </button>

          </div>

          {/* Fast mode toggle */}
          <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
            <label className="toggle-label">
              <input
                type="checkbox"
                checked={skipAudit}
                onChange={e => setSkipAudit(e.target.checked)}
                disabled={loading}
                style={{ accentColor: 'var(--orange)', width: 16, height: 16, cursor: 'pointer' }}
              />
              <span>
                <strong>Fast mode</strong> — skip website audit
                <span style={{ color: 'var(--gray-400)', marginLeft: 6, fontWeight: 400 }}>
                  (discovery only, ~30s instead of 5 min)
                </span>
              </span>
            </label>
          </div>
        </form>
      </div>
    </div>
  )
}
