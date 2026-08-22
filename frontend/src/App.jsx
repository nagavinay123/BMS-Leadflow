import { useState, useEffect, useCallback, useRef } from 'react'
import SearchForm     from './components/SearchForm.jsx'
import StatsBar       from './components/StatsBar.jsx'
import CompanyTable   from './components/CompanyTable.jsx'
import RunsHistory    from './components/RunsHistory.jsx'
import PipelineFunnel from './components/PipelineFunnel.jsx'
import OutreachQueue  from './components/OutreachQueue.jsx'
import Analytics      from './components/Analytics.jsx'
import ICPProfiles    from './components/ICPProfiles.jsx'
import bmsLogo from './bms-logo.png'

const LOADING_MESSAGES = [
  { icon: '📍', text: 'Searching Google Maps for businesses…'           },
  { icon: '🔍', text: 'Fetching place details for each result…'         },
  { icon: '🏢', text: 'Matching to Companies House register…'           },
  { icon: '⚖️',  text: 'Checking PECR — incorporated entities only…'   },
  { icon: '👤', text: 'Looking up company directors…'                   },
  { icon: '💾', text: 'Storing verified companies in database…'          },
  { icon: '🌐', text: 'Checking websites — SSL, title, meta tags…'      },
  { icon: '📧', text: 'Scraping contact emails from websites…'           },
  { icon: '⚡', text: 'Running Google PageSpeed audit (desktop)…'        },
  { icon: '📱', text: 'Running Google PageSpeed audit (mobile)…'        },
  { icon: '🏆', text: 'Scoring companies 0–100…'                        },
  { icon: '✅', text: 'Almost done — ranking by score…'                  },
]

const TABS = [
  { id: 'search',   label: '🔍 Search'    },
  { id: 'funnel',   label: '📊 Funnel'    },
  { id: 'outreach', label: '📧 Outreach'  },
  { id: 'analytics',label: '📈 Analytics' },
  { id: 'icp',      label: '🎯 ICP'       },
  { id: 'runs',     label: '📋 History'   },
]

export default function App() {
  const [companies,  setCompanies]  = useState([])
  const [stats,      setStats]      = useState(null)
  const [runs,       setRuns]       = useState([])
  const [loading,    setLoading]    = useState(false)
  const [error,      setError]      = useState(null)
  const [lastRun,    setLastRun]    = useState(null)
  const [tab,        setTab]        = useState('search')
  const [apiOk,      setApiOk]      = useState(null)
  const [msgIdx,     setMsgIdx]     = useState(0)
  const msgTimer = useRef(null)

  useEffect(() => {
    fetch('/health')
      .then(r => r.ok ? setApiOk(true) : setApiOk(false))
      .catch(() => setApiOk(false))
  }, [])

  useEffect(() => {
    if (apiOk) { refreshStats(); refreshRuns(); fetchCompanies() }
  }, [apiOk])

  useEffect(() => {
    if (loading) {
      setMsgIdx(0)
      msgTimer.current = setInterval(() => setMsgIdx(i => (i + 1) % LOADING_MESSAGES.length), 4000)
    } else {
      clearInterval(msgTimer.current)
    }
    return () => clearInterval(msgTimer.current)
  }, [loading])

  const refreshStats = useCallback(() =>
    fetch('/api/stats').then(r => r.json()).then(setStats).catch(() => {}), [])

  const refreshRuns = useCallback(() =>
    fetch('/api/runs').then(r => r.json()).then(setRuns).catch(() => {}), [])

  const fetchCompanies = useCallback((runId = null) => {
    const url = runId ? `/api/companies?run_id=${runId}&limit=200` : '/api/companies?limit=200'
    return fetch(url).then(r => r.json()).then(d => setCompanies(Array.isArray(d) ? d : [])).catch(() => {})
  }, [])

  async function handleSearch({ businessType, town, maxResults, skipAudit }) {
    setLoading(true); setError(null); setCompanies([]); setLastRun(null)
    try {
      const r = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ business_type: businessType, town, max_results: maxResults, skip_audit: skipAudit }),
      })
      if (!r.ok) {
        let detail = `HTTP ${r.status}`
        try { const e = await r.json(); detail = e.detail || detail } catch {}
        throw new Error(detail)
      }
      const result = await r.json()
      setLastRun(result)
      setCompanies(result.companies || [])
      refreshStats(); refreshRuns()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  function handleViewRun(runId) { fetchCompanies(runId); setTab('search') }

  const msg = LOADING_MESSAGES[msgIdx]

  return (
    <div className="app">
      <header>
        <div className="header-inner">
          <div className="logo" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <img src={bmsLogo} alt="BeMySocial Logo" style={{ height: 32, width: 'auto' }} />
            <span className="logo-name">LeadFlow</span>
            <span className="logo-badge">v1.0</span>
          </div>
          <nav>
            {TABS.map(t => (
              <button key={t.id} className={tab === t.id ? 'active' : ''} onClick={() => setTab(t.id)}>
                {t.label}
                {t.id === 'runs' && runs.length > 0 && ` (${runs.length})`}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main>
        {apiOk === false && (
          <div className="error-banner">
            ⚠️ Cannot reach backend at localhost:8000. Run:&nbsp;
            <code>uvicorn main:app --reload --port 8000</code>
          </div>
        )}

        {/* ── Search ── */}
        {tab === 'search' && (
          <>
            <div className="section-gap">
              <SearchForm onSearch={handleSearch} loading={loading} />
            </div>
            {error && <div className="error-banner">❌ {error}</div>}

            {loading && (
              <div className="loading-overlay">
                <div className="big-spinner" />
                <p className="loading-title">Running discovery pipeline…</p>
                <div className="loading-msg">
                  <span className="loading-icon">{msg.icon}</span>
                  <span>{msg.text}</span>
                </div>
                <p className="loading-hint">
                  Full pipeline takes 2–5 min for 50 companies.
                  <br />Tick Fast mode to skip website audit (~30s).
                </p>
              </div>
            )}

            {!loading && stats && (
              <div className="section-gap">
                <StatsBar stats={stats} lastRun={lastRun} />
              </div>
            )}

            {!loading && companies.length > 0 && <CompanyTable companies={companies} />}

            {!loading && companies.length === 0 && !error && (
              <div className="empty-state">
                Enter a business type and town above to discover leads.
              </div>
            )}
          </>
        )}

        {/* ── Funnel ── */}
        {tab === 'funnel' && (
          <div className="section-gap"><PipelineFunnel stats={stats} /></div>
        )}

        {/* ── Outreach ── */}
        {tab === 'outreach' && <OutreachQueue />}

        {/* ── Analytics ── */}
        {tab === 'analytics' && <Analytics />}

        {/* ── ICP ── */}
        {tab === 'icp' && <ICPProfiles />}

        {/* ── History ── */}
        {tab === 'runs' && <RunsHistory runs={runs} onViewRun={handleViewRun} onDeleted={refreshRuns} />}
      </main>
    </div>
  )
}
