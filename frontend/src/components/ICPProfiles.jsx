import { useState, useEffect } from 'react'

export default function ICPProfiles() {
  const [profiles, setProfiles] = useState([])
  const [loading,  setLoading]  = useState(true)
  const [editing,  setEditing]  = useState(null)
  const [seeding,  setSeeding]  = useState(false)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    const data = await fetch('/api/icp').then(r => r.json()).catch(() => [])
    setProfiles(Array.isArray(data) ? data : [])
    setLoading(false)
  }

  async function seedDefaults(force = false) {
    if (force && !confirm('This will DELETE all existing ICP profiles and reload the defaults. Continue?')) return
    setSeeding(true)
    try {
      const res  = await fetch(`/api/icp/seed?force=${force}`, { method: 'POST' })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        alert('Seed failed: ' + (data.detail || `HTTP ${res.status}`))
      } else if (data.result?.errors?.length > 0) {
        alert('Some profiles failed:\n' + data.result.errors.map(e => `• ${e.profile}: ${e.error}`).join('\n'))
      }
    } catch (e) {
      alert('Seed error: ' + e.message)
    }
    await load()
    setSeeding(false)
  }

  async function toggleActive(profile) {
    await fetch(`/api/icp/${profile.id}`, {
      method:  'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ ...profile, active: !profile.active }),
    })
    await load()
  }

  async function deleteProfile(id) {
    if (!confirm('Delete this ICP profile?')) return
    await fetch(`/api/icp/${id}`, { method: 'DELETE' })
    await load()
  }

  const SIGNALS_HELP = {
    poor_website: 'Website speed/mobile score < 70',
    no_ssl:       'Site has no HTTPS',
    ch_active:    'Active at Companies House',
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--navy)' }}>ICP Profiles</h2>
          <p style={{ fontSize: 13, color: 'var(--gray-400)', marginTop: 4, maxWidth: 600 }}>
            Ideal Customer Profiles define who BMS targets. Companies matching an active profile earn up to{' '}
            <strong>+5 ICP Fit points</strong> and show a <span style={{ color: '#7c3aed' }}>🎯</span> badge in the table.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10, flexShrink: 0 }}>
          {profiles.length > 0 && (
            <button
              className="btn btn-secondary"
              style={{ fontSize: 12 }}
              onClick={() => seedDefaults(true)}
              disabled={seeding}
              title="Delete all profiles and reload the 6 built-in defaults"
            >
              {seeding ? 'Reloading…' : '🔄 Reload Defaults'}
            </button>
          )}
          <button className="btn btn-primary" onClick={() => setEditing({})}>
            + New Profile
          </button>
        </div>
      </div>

      {/* How it works callout */}
      <div style={{
        background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8,
        padding: '12px 16px', marginBottom: 20, fontSize: 13, color: '#1e40af',
      }}>
        <strong>How ICP matching works:</strong> Each discovered company is checked against active profiles in order.
        A match is made by <em>SIC code</em> (Companies House sector), <em>business name keywords</em>, or <em>website signals</em>
        (e.g. the "BMS Live Campaign" profile matches any company with a poor website — sector doesn't matter).
        The matched profile name appears in the 🎯 ICP column.
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--gray-400)' }}>Loading…</div>
      ) : profiles.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 60, color: 'var(--gray-400)' }}>
          No ICP profiles yet.
          <br /><br />
          <button className="btn btn-primary" onClick={() => seedDefaults(false)} disabled={seeding}>
            {seeding ? 'Seeding…' : '🌱 Load Default Profiles'}
          </button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 16 }}>
          {profiles.map(p => {
            const signals = p.signals || []
            const regions = p.regions || []
            const age     = p.min_company_age_years || 0
            return (
              <div key={p.id} className="card" style={{ opacity: p.active ? 1 : 0.55 }}>
                <div className="card-header" style={{ justifyContent: 'space-between' }}>
                  <div>
                    <span className="card-title" style={{ fontSize: 14 }}>{p.name}</span>
                    <span className={`badge ${p.active ? 'badge-green' : 'badge-gray'}`} style={{ marginLeft: 10 }}>
                      {p.active ? '✓ Active' : 'Inactive'}
                    </span>
                  </div>
                </div>
                <div className="card-body" style={{ paddingTop: 10 }}>
                  <p style={{ fontSize: 12, color: 'var(--gray-600)', marginBottom: 10 }}>
                    {p.description || '—'}
                  </p>

                  {/* Keywords */}
                  {p.business_types?.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--gray-400)', textTransform: 'uppercase', marginBottom: 4 }}>
                        Keywords
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {p.business_types.slice(0, 6).map(t => (
                          <span key={t} className="tag" style={{ fontSize: 11 }}>{t}</span>
                        ))}
                        {p.business_types.length > 6 && (
                          <span className="tag" style={{ fontSize: 11, color: 'var(--gray-400)' }}>
                            +{p.business_types.length - 6} more
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Signals */}
                  {signals.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--gray-400)', textTransform: 'uppercase', marginBottom: 4 }}>
                        Signals (sector-agnostic match)
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {signals.map(s => (
                          <span key={s} className="tag" style={{ fontSize: 11, background: '#fef3c7', color: '#92400e', border: '1px solid #fde68a' }}
                            title={SIGNALS_HELP[s] || s}>
                            ⚡ {s.replace(/_/g, ' ')}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Meta row */}
                  <div style={{ fontSize: 11, color: 'var(--gray-400)', marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 12 }}>
                    {age > 0 && <span>📅 {age}+ yrs trading</span>}
                    {(p.min_reviews > 0 || p.min_rating > 0) && (
                      <span>⭐ {p.min_reviews}+ reviews · {p.min_rating}+</span>
                    )}
                    {regions.length > 0 && <span>📍 {regions.join(', ')}</span>}
                    {p.size_band && p.size_band !== 'Any' && <span>🏢 {p.size_band}</span>}
                  </div>

                  <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
                    <button className="btn btn-secondary" style={{ fontSize: 12, padding: '4px 12px' }}
                      onClick={() => toggleActive(p)}>
                      {p.active ? 'Deactivate' : 'Activate'}
                    </button>
                    <button className="btn btn-secondary" style={{ fontSize: 12, padding: '4px 12px' }}
                      onClick={() => setEditing(p)}>
                      Edit
                    </button>
                    <button className="btn btn-secondary"
                      style={{ fontSize: 12, padding: '4px 12px', color: 'var(--red)', borderColor: '#fca5a5', marginLeft: 'auto' }}
                      onClick={() => deleteProfile(p.id)}>
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {editing !== null && (
        <ICPModal
          profile={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load() }}
        />
      )}
    </div>
  )
}

function ICPModal({ profile, onClose, onSaved }) {
  const isNew = !profile.id
  const [form, setForm] = useState({
    name:                  profile.name                  || '',
    description:           profile.description           || '',
    business_types:        (profile.business_types || []).join(', '),
    sic_codes:             (profile.sic_codes      || []).join(', '),
    signals:               (profile.signals        || []).join(', '),
    exclusions:            (profile.exclusions     || []).join(', '),
    regions:               (profile.regions        || []).join(', '),
    size_band:             profile.size_band             || 'SME',
    min_company_age_years: profile.min_company_age_years ?? 0,
    min_reviews:           profile.min_reviews           ?? 0,
    min_rating:            profile.min_rating            ?? 0,
    active:                profile.active                ?? true,
  })
  const [saving, setSaving] = useState(false)

  function csv(str) {
    return str.split(',').map(s => s.trim()).filter(Boolean)
  }

  async function save() {
    setSaving(true)
    const payload = {
      ...form,
      business_types:        csv(form.business_types),
      sic_codes:             csv(form.sic_codes),
      signals:               csv(form.signals),
      exclusions:            csv(form.exclusions),
      regions:               csv(form.regions),
      min_company_age_years: Number(form.min_company_age_years),
      min_reviews:           Number(form.min_reviews),
      min_rating:            Number(form.min_rating),
    }
    const url    = isNew ? '/api/icp' : `/api/icp/${profile.id}`
    const method = isNew ? 'POST' : 'PATCH'
    await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    })
    setSaving(false)
    onSaved()
  }

  const fields = [
    { label: 'Name',                                              key: 'name',                  type: 'text',   hint: '' },
    { label: 'Description',                                       key: 'description',           type: 'text',   hint: '' },
    { label: 'Keywords (comma-separated)',                        key: 'business_types',        type: 'text',   hint: 'e.g. plumber, electrician, builder' },
    { label: 'SIC codes (comma-separated)',                       key: 'sic_codes',             type: 'text',   hint: 'e.g. 43210, 43220' },
    { label: 'Signals — sector-agnostic match (comma-separated)', key: 'signals',               type: 'text',   hint: 'poor_website, no_ssl, ch_active' },
    { label: 'Exclusions (comma-separated)',                      key: 'exclusions',            type: 'text',   hint: 'e.g. franchise, plc, chain' },
    { label: 'Regions (comma-separated, blank = any)',            key: 'regions',               type: 'text',   hint: 'e.g. Yorkshire, London, South West' },
    { label: 'Size band',                                         key: 'size_band',             type: 'text',   hint: 'SME, Micro, Any' },
    { label: 'Min company age (years, 0 = any)',                  key: 'min_company_age_years', type: 'number', hint: '' },
    { label: 'Min Google reviews',                                key: 'min_reviews',           type: 'number', hint: '' },
    { label: 'Min Google rating',                                 key: 'min_rating',            type: 'number', hint: '' },
  ]

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal-box" style={{ maxWidth: 560, maxHeight: '90vh', overflowY: 'auto' }}>
        <div className="modal-header">
          <span className="modal-title">{isNew ? 'New ICP Profile' : 'Edit ICP Profile'}</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {fields.map(f => (
            <div key={f.key} className="form-group">
              <label className="form-label">{f.label}</label>
              <input
                className="form-input"
                type={f.type}
                value={form[f.key]}
                placeholder={f.hint}
                onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
              />
            </div>
          ))}

          <label className="toggle-label">
            <input type="checkbox" checked={form.active}
              onChange={e => setForm(p => ({ ...p, active: e.target.checked }))}
              style={{ accentColor: 'var(--orange)', width: 16, height: 16 }}
            />
            <span><strong>Active</strong> — contributes to ICP scoring and matching</span>
          </label>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={save} disabled={saving || !form.name}>
            {saving ? 'Saving…' : isNew ? 'Create Profile' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  )
}
