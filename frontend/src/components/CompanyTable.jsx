import { useState, useMemo } from 'react'

// ── CSV export ─────────────────────────────────
function exportCSV(companies) {
  const FIELDS = [
    'score', 'name', 'registered_name', 'company_number', 'company_type',
    'registered_address', 'website', 'phone', 'has_website', 'ch_matched',
    'contact_first_name', 'contact_last_name', 'contact_email', 'contact_role',
    'performance_score', 'mobile_score', 'https', 'rating', 'review_count',
    'instagram_url', 'facebook_url', 'company_status', 'incorporation_date', 'status',
  ]
  const header = FIELDS.join(',')
  const rows = companies.map(c =>
    FIELDS.map(f => {
      const v = c[f]
      if (v == null) return ''
      if (typeof v === 'boolean') return v ? 'TRUE' : 'FALSE'
      const s = String(v)
      return s.includes(',') || s.includes('"') || s.includes('\n')
        ? `"${s.replace(/"/g, '""')}"` : s
    }).join(',')
  )
  const csv  = [header, ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = `leadflow_${new Date().toISOString().slice(0,10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

const COLUMNS = [
  { key: '#',                  label: 'S NO',         sortable: false },
  { key: 'score',              label: 'Score',        sortable: true  },
  { key: 'icp_match',          label: 'ICP',          sortable: false },
  { key: 'name',               label: 'Business',     sortable: true  },
  { key: 'contact_first_name', label: 'First Name',   sortable: true  },
  { key: 'contact_last_name',  label: 'Last Name',    sortable: true  },
  { key: 'contact_role',       label: 'Job Title',    sortable: true  },
  { key: 'contact_email',      label: 'Email',        sortable: true  },
  { key: 'phone',              label: 'Phone',        sortable: false },
  { key: 'registered_name',    label: 'Reg. Name',    sortable: true  },
  { key: 'company_type',       label: 'Type',         sortable: false },
  { key: 'registered_address', label: 'Address',      sortable: false },
  { key: 'has_website',        label: 'Website',      sortable: true  },
  { key: 'ch_matched',         label: 'Companies House Matching', sortable: true  },
  { key: 'performance_score',  label: 'Speed',        sortable: true  },
  { key: 'https',              label: 'SSL',          sortable: true  },
  { key: 'rating',             label: 'Rating',       sortable: true  },
  { key: 'instagram_url',      label: 'Social',       sortable: false },
]

// ── Filter bar ─────────────────────────────────
const DEFAULT_FILTERS = {
  phone:     'all',
  email:     'all',
  chMatch:   'all',
  instagram: 'all',
  rating:    'all',
  sortBy:    'score_desc',
}

function FilterBar({ filters, onChange }) {
  const dropdowns = [
    {
      key: 'phone', label: 'Phone',
      options: [
        { value: 'all',  label: 'All' },
        { value: 'has',  label: '✓ Has Phone' },
        { value: 'none', label: '✗ No Phone'  },
      ],
    },
    {
      key: 'email', label: 'Email',
      options: [
        { value: 'all',  label: 'All' },
        { value: 'has',  label: '✓ Has Email' },
        { value: 'none', label: '✗ No Email'  },
      ],
    },
    {
      key: 'chMatch', label: 'Companies House',
      options: [
        { value: 'all',       label: 'All'           },
        { value: 'matched',   label: '✓ Matched'     },
        { value: 'unmatched', label: '~ Unmatched'   },
      ],
    },
    {
      key: 'instagram', label: 'Instagram',
      options: [
        { value: 'all',  label: 'All'               },
        { value: 'has',  label: '✓ Has Instagram'   },
        { value: 'none', label: '✗ No Instagram'    },
      ],
    },
    {
      key: 'rating', label: 'Min Rating',
      options: [
        { value: 'all', label: 'All'      },
        { value: '4.5', label: '4.5+ ⭐' },
        { value: '4.0', label: '4.0+ ⭐' },
        { value: '3.5', label: '3.5+ ⭐' },
      ],
    },
  ]

  const sortOptions = [
    { value: 'score_desc',   label: 'Score: High → Low'   },
    { value: 'score_asc',    label: 'Score: Low → High'   },
    { value: 'rating_desc',  label: 'Rating: High → Low'  },
    { value: 'rating_asc',   label: 'Rating: Low → High'  },
    { value: 'reviews_desc', label: 'Reviews: Most first' },
    { value: 'name_asc',     label: 'Name: A → Z'         },
  ]

  const hasActiveFilter = Object.entries(filters).some(
    ([k, v]) => k !== 'sortBy' && v !== 'all'
  )

  return (
    <div style={{
      padding: '10px 20px',
      borderBottom: '1px solid var(--gray-200)',
      background: 'var(--gray-50)',
      display: 'flex',
      flexWrap: 'wrap',
      gap: 10,
      alignItems: 'center',
    }}>
      {dropdowns.map(d => (
        <div key={d.key} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span style={{
            fontSize: 10, fontWeight: 700, color: 'var(--gray-400)',
            textTransform: 'uppercase', letterSpacing: '.5px', whiteSpace: 'nowrap',
          }}>
            {d.label}:
          </span>
          <select
            style={{
              padding: '4px 8px', fontSize: 12, border: '1px solid var(--gray-200)',
              borderRadius: 6, background: filters[d.key] !== 'all' ? '#eff6ff' : 'white',
              color: filters[d.key] !== 'all' ? '#1d4ed8' : 'var(--gray-900)',
              fontWeight: filters[d.key] !== 'all' ? 700 : 400,
              cursor: 'pointer', outline: 'none',
            }}
            value={filters[d.key]}
            onChange={e => onChange({ ...filters, [d.key]: e.target.value })}
          >
            {d.options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      ))}

      {/* Divider */}
      <div style={{ width: 1, height: 24, background: 'var(--gray-200)', margin: '0 4px' }} />

      {/* Sort by */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        <span style={{
          fontSize: 10, fontWeight: 700, color: 'var(--gray-400)',
          textTransform: 'uppercase', letterSpacing: '.5px', whiteSpace: 'nowrap',
        }}>
          Sort By:
        </span>
        <select
          style={{
            padding: '4px 8px', fontSize: 12, border: '1px solid var(--gray-200)',
            borderRadius: 6, background: 'white', color: 'var(--gray-900)',
            cursor: 'pointer', outline: 'none',
          }}
          value={filters.sortBy}
          onChange={e => onChange({ ...filters, sortBy: e.target.value })}
        >
          {sortOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      {/* Clear button */}
      {hasActiveFilter && (
        <button
          onClick={() => onChange({ ...DEFAULT_FILTERS, sortBy: filters.sortBy })}
          style={{
            marginLeft: 4, padding: '4px 10px', fontSize: 11, fontWeight: 600,
            background: '#fee2e2', color: 'var(--red)', border: '1px solid #fca5a5',
            borderRadius: 6, cursor: 'pointer',
          }}
        >
          ✕ Clear filters
        </button>
      )}

      {/* Active count badge */}
      {hasActiveFilter && (
        <span style={{
          fontSize: 11, color: '#1d4ed8', fontWeight: 700,
          background: '#eff6ff', padding: '2px 8px', borderRadius: 999,
        }}>
          {Object.entries(filters).filter(([k, v]) => k !== 'sortBy' && v !== 'all').length} active
        </span>
      )}
    </div>
  )
}

// ── Main component ─────────────────────────────
export default function CompanyTable({ companies }) {
  const [filter,    setFilter]    = useState('')
  const [page,      setPage]      = useState(1)
  const [expanded,  setExpanded]  = useState(null)
  const [adv,       setAdv]       = useState(DEFAULT_FILTERS)
  const PER_PAGE = 25

  function handleAdvChange(next) { setAdv(next); setPage(1) }
  function handleTextChange(e)   { setFilter(e.target.value); setPage(1) }

  const filtered = useMemo(() => {
    const q = filter.toLowerCase()

    return companies
      .filter(c => {
        // Text search
        if (q && !(
          (c.name              || '').toLowerCase().includes(q) ||
          (c.registered_name   || '').toLowerCase().includes(q) ||
          (c.company_number    || '').toLowerCase().includes(q) ||
          (c.registered_address|| '').toLowerCase().includes(q)
        )) return false

        // Phone
        if (adv.phone === 'has'  && !c.phone)         return false
        if (adv.phone === 'none' &&  c.phone)         return false

        // Email
        if (adv.email === 'has'  && !c.contact_email) return false
        if (adv.email === 'none' &&  c.contact_email) return false

        // CH Match
        if (adv.chMatch === 'matched'   && !c.ch_matched) return false
        if (adv.chMatch === 'unmatched' &&  c.ch_matched) return false

        // Instagram
        if (adv.instagram === 'has'  && !c.instagram_url) return false
        if (adv.instagram === 'none' &&  c.instagram_url) return false

        // Min rating
        if (adv.rating !== 'all' && (c.rating || 0) < parseFloat(adv.rating)) return false

        return true
      })
      .sort((a, b) => {
        switch (adv.sortBy) {
          case 'score_asc':    return (a.score      || 0) - (b.score      || 0)
          case 'rating_desc':  return (b.rating     || 0) - (a.rating     || 0)
          case 'rating_asc':   return (a.rating     || 0) - (b.rating     || 0)
          case 'reviews_desc': return (b.review_count|| 0) - (a.review_count|| 0)
          case 'name_asc':     return (a.name||'').localeCompare(b.name||'')
          default:             return (b.score      || 0) - (a.score      || 0)
        }
      })
  }, [companies, filter, adv])

  const totalPages = Math.ceil(filtered.length / PER_PAGE)
  const pageData   = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE)

  const outreachReady = companies.filter(c => (c.score || 0) >= 60).length
  const enriched      = companies.filter(c => c.status === 'enriched').length
  const withInsta     = companies.filter(c => c.instagram_url).length

  return (
    <div className="card">
      {/* Header */}
      <div className="card-header">
        <div>
          <span className="card-title">
            Companies ({filtered.length} of {companies.length})
          </span>
          <span style={{ marginLeft: 16, fontSize: 12, color: 'var(--gray-400)' }}>
            {enriched} audited ·{' '}
            <strong style={{ color: 'var(--green)' }}>{outreachReady} outreach ready</strong>
            {withInsta > 0 && (
              <> · <strong style={{ color: '#c026d3' }}>📷 {withInsta} on Instagram</strong></>
            )}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <input
            className="form-input"
            style={{ width: 220, padding: '6px 10px' }}
            placeholder="Filter by name, number, address…"
            value={filter}
            onChange={handleTextChange}
          />
          <button
            className="btn btn-secondary"
            style={{ whiteSpace: 'nowrap', padding: '6px 14px', fontSize: 13 }}
            onClick={() => exportCSV(filtered)}
            disabled={filtered.length === 0}
            title="Export filtered results to CSV"
          >
            ⬇ Export CSV
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <FilterBar filters={adv} onChange={handleAdvChange} />

      {/* Table */}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {COLUMNS.map(col => (
                <th key={col.key} style={{ cursor: 'default', padding: '14px 22px' }}>
                  {col.label}
                </th>
              ))}
              <th style={{ padding: '14px 22px' }}>Issues</th>
            </tr>
          </thead>
          <tbody>
            {pageData.map((c, i) => (
              <>
                <tr
                  key={c.id || i}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setExpanded(expanded === c.id ? null : c.id)}
                >
                  {/* S NO */}
                  <td style={{ color: 'var(--gray-400)', fontSize: 12, fontWeight: 600, textAlign: 'center', minWidth: 36, padding: '14px 22px' }}>
                    {(page - 1) * PER_PAGE + i + 1}
                  </td>

                  {/* Score */}
                  <td><ScoreBadge score={c.score} /></td>

                  {/* ICP match */}
                  <td>
                    {c.icp_match
                      ? <span style={{
                          display: 'inline-block',
                          background: '#ede9fe', color: '#6d28d9',
                          fontSize: 10, fontWeight: 700,
                          padding: '2px 7px', borderRadius: 999,
                          whiteSpace: 'nowrap',
                        }}>
                          🎯 {c.icp_match.split('(')[0].trim()}
                        </span>
                      : <Dash />
                    }
                  </td>

                  {/* Business name */}
                  <td>
                    <div className="td-name">
                      {c.website
                        ? <a href={c.website} target="_blank" rel="noreferrer"
                            onClick={e => e.stopPropagation()}>{c.name}</a>
                        : c.name
                      }
                    </div>
                  </td>

                  {/* First Name */}
                  <td>
                    {c.contact_first_name
                      ? <div style={{ fontWeight: 600 }}>{c.contact_first_name}</div>
                      : <Dash />
                    }
                  </td>

                  {/* Last Name */}
                  <td>
                    {c.contact_last_name
                      ? <>
                          <div style={{ fontWeight: 600 }}>{c.contact_last_name}</div>
                        </>
                      : <Dash />
                    }
                  </td>

                  {/* Job Title */}
                  <td style={{ fontSize: 12, textTransform: 'capitalize' }}>
                    {c.contact_role
                      ? c.contact_role.replace(/-/g, ' ')
                      : <Dash />
                    }
                  </td>

                  {/* Email */}
                  <td>
                    {c.contact_email
                      ? <>
                          <a
                            href={`mailto:${c.contact_email}`}
                            style={{ color: 'var(--navy)', fontSize: 12 }}
                            onClick={e => e.stopPropagation()}
                          >
                            {c.contact_email}
                          </a>
                          {c.email_verified
                            ? <span className="badge badge-green" style={{ marginLeft: 4, fontSize: 10 }}>✓</span>
                            : c.email_confidence > 0
                              ? <span className="badge badge-amber" style={{ marginLeft: 4, fontSize: 10 }}>{c.email_confidence}%</span>
                              : null
                          }
                        </>
                      : <Dash />
                    }
                  </td>

                  {/* Phone */}
                  <td>
                    {c.phone
                      ? <a href={`tel:${c.phone}`} style={{ color: 'var(--navy)', fontSize: 12 }}
                           onClick={e => e.stopPropagation()}>{c.phone}</a>
                      : <Dash />
                    }
                  </td>

                  {/* Registered name */}
                  <td>{c.registered_name || <Dash />}</td>

                  {/* Type */}
                  <td>{c.company_type ? <span className="tag">{c.company_type}</span> : <Dash />}</td>

                  {/* Address */}
                  <td style={{ maxWidth: 180 }}>
                    <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 180 }}>
                      {c.registered_address || '—'}
                    </div>
                  </td>

                  {/* Website */}
                  <td>
                    {c.has_website
                      ? <span className="badge badge-green">✓ Yes</span>
                      : <span className="badge badge-red">✗ None</span>
                    }
                  </td>

                  {/* CH match */}
                  <td>
                    {c.ch_matched
                      ? <span className="badge badge-green">✓ Matched</span>
                      : <span className="badge badge-gray">~ Unmatched</span>
                    }
                  </td>

                  {/* PageSpeed */}
                  <td><SpeedBadge score={c.performance_score} /></td>

                  {/* SSL */}
                  <td>
                    {c.https === true  && <span className="badge badge-green">✓ SSL</span>}
                    {c.https === false && <span className="badge badge-red">✗ No SSL</span>}
                    {c.https == null   && <Dash />}
                  </td>

                  {/* Rating */}
                  <td>
                    {c.rating != null
                      ? `⭐ ${c.rating} (${c.review_count || 0})`
                      : <Dash />
                    }
                  </td>

                  {/* Social media */}
                  <td>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {c.instagram_url
                        ? <a
                            href={c.instagram_url}
                            target="_blank" rel="noreferrer"
                            onClick={e => e.stopPropagation()}
                            title="Instagram"
                            style={{
                              display: 'inline-flex', alignItems: 'center', gap: 3,
                              fontSize: 11, fontWeight: 600,
                              background: 'linear-gradient(135deg,#f093fb,#f5576c)',
                              color: 'white', padding: '2px 7px', borderRadius: 999,
                              textDecoration: 'none',
                            }}
                          >
                            📷 IG
                          </a>
                        : null
                      }
                      {c.facebook_url
                        ? <a
                            href={c.facebook_url}
                            target="_blank" rel="noreferrer"
                            onClick={e => e.stopPropagation()}
                            title="Facebook"
                            style={{
                              display: 'inline-flex', alignItems: 'center', gap: 3,
                              fontSize: 11, fontWeight: 600,
                              background: '#1877f2', color: 'white',
                              padding: '2px 7px', borderRadius: 999,
                              textDecoration: 'none',
                            }}
                          >
                            FB
                          </a>
                        : null
                      }
                      {!c.instagram_url && !c.facebook_url && <Dash />}
                    </div>
                  </td>

                  {/* Issues */}
                  <td>
                    {c.issues && c.issues.length > 0
                      ? <span className="badge badge-amber" style={{ cursor: 'pointer' }}>
                          {c.issues.length} issue{c.issues.length > 1 ? 's' : ''} ▾
                        </span>
                      : c.status === 'enriched'
                        ? <span className="badge badge-green">✓ Clean</span>
                        : <Dash />
                    }
                  </td>
                </tr>

                {/* Expanded issues row */}
                {expanded === c.id && c.issues && c.issues.length > 0 && (
                  <tr key={`${c.id}-issues`} style={{ background: '#fefce8' }}>
                    <td colSpan={18} style={{ padding: '12px 20px' }}>
                      <strong style={{ fontSize: 12, color: 'var(--amber)' }}>
                        ⚠️ Website issues found — BMS can fix these:
                      </strong>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
                        {c.issues.map((issue, idx) => (
                          <span key={idx} style={{
                            background: '#fef3c7', color: '#92400e',
                            border: '1px solid #fcd34d',
                            borderRadius: 6, padding: '3px 10px', fontSize: 12
                          }}>
                            {issue.label || issue.type}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}

            {filtered.length === 0 && (
              <tr>
                <td colSpan={18} style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--gray-400)' }}>
                  No companies match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{
          padding: '12px 20px', borderTop: '1px solid var(--gray-200)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 13
        }}>
          <span style={{ color: 'var(--gray-400)' }}>
            Page {page} of {totalPages} · {filtered.length} results
          </span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-secondary" onClick={() => setPage(p => p - 1)} disabled={page === 1}
              style={{ padding: '5px 14px', fontSize: 13 }}>← Prev</button>
            <button className="btn btn-secondary" onClick={() => setPage(p => p + 1)} disabled={page === totalPages}
              style={{ padding: '5px 14px', fontSize: 13 }}>Next →</button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Sub-components ────────────────────────────

function ScoreBadge({ score }) {
  if (score == null) return <Dash />
  const cls = score >= 60 ? 'badge-green' : score >= 40 ? 'badge-amber' : 'badge-gray'
  const label = score >= 80 ? 'Hot' : score >= 60 ? 'Warm' : score >= 40 ? 'Cool' : 'Cold'
  return (
    <span className={`badge ${cls}`} style={{ minWidth: 54, justifyContent: 'center' }}>
      {score} · {label}
    </span>
  )
}

function SpeedBadge({ score }) {
  if (score == null) return <Dash />
  const cls = score >= 90 ? 'badge-green' : score >= 50 ? 'badge-amber' : 'badge-red'
  return <span className={`badge ${cls}`}>{score}</span>
}

function Dash() {
  return <span style={{ color: '#cbd5e1' }}>—</span>
}
