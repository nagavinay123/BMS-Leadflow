import { useState } from 'react'
import bmsLogo from '../bms-logo.png'

const SUPABASE_URL  = import.meta.env.VITE_SUPABASE_URL
const SUPABASE_KEY  = import.meta.env.VITE_SUPABASE_ANON_KEY

// ── Supabase client (lazy — only created when env vars exist) ──
let _client = null
function getClient() {
  if (_client) return _client
  if (!SUPABASE_URL || !SUPABASE_KEY) return null
  // Dynamic import fallback handled by caller
  const { createClient } = window.__supabase || {}
  if (!createClient) return null
  _client = createClient(SUPABASE_URL, SUPABASE_KEY)
  return _client
}

// ── Styles ────────────────────────────────────────────────────
const S = {
  page: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%)',
    fontFamily: "'Inter', 'Segoe UI', sans-serif",
    padding: 20,
  },
  card: {
    background: '#ffffff',
    borderRadius: 16,
    padding: '48px 44px',
    width: '100%',
    maxWidth: 420,
    boxShadow: '0 25px 60px rgba(0,0,0,0.4)',
  },
  logoWrap: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    marginBottom: 32,
    gap: 12,
  },
  logo: { height: 52, width: 'auto' },
  brandRow: { display: 'flex', alignItems: 'center', gap: 10 },
  brandName: { fontSize: 22, fontWeight: 800, color: '#0f172a', letterSpacing: '-0.3px' },
  brandBadge: {
    fontSize: 11, fontWeight: 700, background: '#1e3a5f', color: '#fff',
    padding: '2px 8px', borderRadius: 20, letterSpacing: '0.5px',
  },
  tagline: { fontSize: 13, color: '#64748b', marginTop: 2 },
  heading: { fontSize: 18, fontWeight: 700, color: '#0f172a', marginBottom: 4 },
  sub:     { fontSize: 13, color: '#64748b', marginBottom: 28 },
  label: {
    display: 'block', fontSize: 12, fontWeight: 600,
    color: '#374151', marginBottom: 6,
  },
  input: {
    width: '100%', padding: '11px 14px', fontSize: 14,
    border: '1.5px solid #d1d5db', borderRadius: 8,
    outline: 'none', boxSizing: 'border-box',
    transition: 'border-color 0.15s',
    color: '#111827', background: '#fff',
  },
  inputFocus: { borderColor: '#1e3a5f' },
  fieldWrap: { marginBottom: 18 },
  forgotRow: { display: 'flex', justifyContent: 'flex-end', marginTop: -10, marginBottom: 18 },
  forgotBtn: {
    background: 'none', border: 'none', cursor: 'pointer',
    fontSize: 12, color: '#1e3a5f', fontWeight: 600, padding: 0,
  },
  btn: {
    width: '100%', padding: '12px', fontSize: 14, fontWeight: 700,
    background: '#1e3a5f', color: '#fff', border: 'none',
    borderRadius: 8, cursor: 'pointer', transition: 'background 0.15s',
    letterSpacing: '0.2px',
  },
  btnDisabled: { background: '#94a3b8', cursor: 'not-allowed' },
  error: {
    background: '#fef2f2', border: '1px solid #fca5a5',
    borderRadius: 8, padding: '10px 14px', fontSize: 13,
    color: '#dc2626', marginBottom: 18,
  },
  success: {
    background: '#f0fdf4', border: '1px solid #86efac',
    borderRadius: 8, padding: '10px 14px', fontSize: 13,
    color: '#166534', marginBottom: 18,
  },
  notice: {
    marginTop: 28, paddingTop: 20, borderTop: '1px solid #f1f5f9',
    textAlign: 'center', fontSize: 12, color: '#94a3b8', lineHeight: 1.5,
  },
  divider: { margin: '0 0 24px', borderTop: '1px solid #f1f5f9' },
}

// ── Config warning screen ─────────────────────────────────────
export function ConfigWarning() {
  return (
    <div style={S.page}>
      <div style={{ ...S.card, textAlign: 'center' }}>
        <div style={S.logoWrap}>
          <img src={bmsLogo} alt="BeMySocial" style={S.logo} />
          <div style={S.brandRow}>
            <span style={S.brandName}>BeMySocial</span>
            <span style={S.brandBadge}>LeadFlow</span>
          </div>
        </div>
        <div style={{ fontSize: 32, marginBottom: 16 }}>⚙️</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: '#0f172a', marginBottom: 10 }}>
          Configuration Required
        </div>
        <div style={{ fontSize: 13, color: '#64748b', lineHeight: 1.7, marginBottom: 24 }}>
          The application cannot start because Supabase environment variables are not configured.
        </div>
        <div style={{
          background: '#fef3c7', border: '1px solid #fde68a',
          borderRadius: 8, padding: '14px 16px', textAlign: 'left',
          fontSize: 12, color: '#78350f', lineHeight: 1.8,
        }}>
          <strong>Add these to <code>frontend/.env</code>:</strong><br />
          <code>VITE_SUPABASE_URL=https://your-project.supabase.co</code><br />
          <code>VITE_SUPABASE_ANON_KEY=eyJ...</code>
        </div>
        <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 16 }}>
          Then restart the dev server: <code>npm run dev</code>
        </div>
      </div>
    </div>
  )
}

// ── Main login page ───────────────────────────────────────────
export default function LoginPage({ supabase, onLogin }) {
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState('')
  const [message,  setMessage]  = useState('')
  const [mode,     setMode]     = useState('login')   // 'login' | 'forgot'
  const [focused,  setFocused]  = useState('')

  async function handleLogin(e) {
    e.preventDefault()
    if (!email || !password) { setError('Please enter your email and password.'); return }
    setLoading(true); setError(''); setMessage('')
    try {
      const { data, error: err } = await supabase.auth.signInWithPassword({ email, password })
      if (err) {
        if (err.message?.includes('Invalid login')) {
          setError('Invalid email or password. Please try again.')
        } else if (err.message?.includes('Email not confirmed')) {
          setError('Please confirm your email address before signing in.')
        } else {
          setError(err.message || 'Sign in failed. Please try again.')
        }
      } else if (data?.session) {
        onLogin(data.session)
      }
    } catch {
      setError('Unable to connect. Please check your internet connection.')
    }
    setLoading(false)
  }

  async function handleForgot(e) {
    e.preventDefault()
    if (!email) { setError('Please enter your email address.'); return }
    setLoading(true); setError(''); setMessage('')
    try {
      const { error: err } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/reset-password`,
      })
      if (err) {
        setError(err.message || 'Could not send reset email.')
      } else {
        setMessage('Password reset email sent. Check your inbox.')
      }
    } catch {
      setError('Unable to send reset email. Please try again.')
    }
    setLoading(false)
  }

  return (
    <div style={S.page}>
      <div style={S.card}>

        {/* Logo */}
        <div style={S.logoWrap}>
          <img src={bmsLogo} alt="BeMySocial" style={S.logo} />
          <div style={S.brandRow}>
            <span style={S.brandName}>BeMySocial</span>
            <span style={S.brandBadge}>LeadFlow</span>
          </div>
          <div style={S.tagline}>Lead generation & outreach platform</div>
        </div>

        <hr style={S.divider} />

        {/* Heading */}
        {mode === 'login' ? (
          <>
            <div style={S.heading}>Sign in to your account</div>
            <div style={S.sub}>Enter your BeMySocial credentials below</div>
          </>
        ) : (
          <>
            <div style={S.heading}>Reset your password</div>
            <div style={S.sub}>Enter your email to receive a reset link</div>
          </>
        )}

        {/* Error / success */}
        {error   && <div style={S.error}>⚠️ {error}</div>}
        {message && <div style={S.success}>✅ {message}</div>}

        {/* Form */}
        <form onSubmit={mode === 'login' ? handleLogin : handleForgot} noValidate>
          <div style={S.fieldWrap}>
            <label style={S.label}>Email address</label>
            <input
              type="email"
              value={email}
              onChange={e => { setEmail(e.target.value); setError('') }}
              onFocus={() => setFocused('email')}
              onBlur={() => setFocused('')}
              placeholder="user@bemysocial.co.uk"
              autoComplete="email"
              disabled={loading}
              style={{ ...S.input, ...(focused === 'email' ? S.inputFocus : {}) }}
            />
          </div>

          {mode === 'login' && (
            <div style={S.fieldWrap}>
              <label style={S.label}>Password</label>
              <input
                type="password"
                value={password}
                onChange={e => { setPassword(e.target.value); setError('') }}
                onFocus={() => setFocused('password')}
                onBlur={() => setFocused('')}
                placeholder="••••••••"
                autoComplete="current-password"
                disabled={loading}
                style={{ ...S.input, ...(focused === 'password' ? S.inputFocus : {}) }}
              />
            </div>
          )}

          {mode === 'login' && (
            <div style={S.forgotRow}>
              <button
                type="button"
                style={S.forgotBtn}
                onClick={() => { setMode('forgot'); setError(''); setMessage('') }}
              >
                Forgot password?
              </button>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{ ...S.btn, ...(loading ? S.btnDisabled : {}) }}
          >
            {loading
              ? (mode === 'login' ? 'Signing in…' : 'Sending…')
              : (mode === 'login' ? 'Sign in' : 'Send reset link')}
          </button>
        </form>

        {mode === 'forgot' && (
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <button
              type="button"
              style={{ ...S.forgotBtn, fontSize: 13 }}
              onClick={() => { setMode('login'); setError(''); setMessage('') }}
            >
              ← Back to sign in
            </button>
          </div>
        )}

        {/* Restricted access notice */}
        <div style={S.notice}>
          🔒 Access restricted to authorised BeMySocial team members.<br />
          No public sign-up. Contact your administrator for access.
        </div>
      </div>
    </div>
  )
}
