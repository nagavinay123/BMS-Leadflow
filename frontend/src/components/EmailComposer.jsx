import { useState, useEffect } from 'react'

export default function EmailComposer({ company, onClose, onQueued }) {
  const [subject,   setSubject]   = useState('')
  const [body,      setBody]      = useState('')
  const [loading,   setLoading]   = useState(true)
  const [saving,    setSaving]    = useState(false)
  const [copied,    setCopied]    = useState(false)
  const [draftId,   setDraftId]   = useState(null)
  const [sender,    setSender]    = useState('James')
  const [generated, setGenerated] = useState(false)

  useEffect(() => {
    // Try to load existing draft first
    fetch(`/api/email-draft/${company.id}`)
      .then(r => r.ok ? r.json() : null)
      .then(draft => {
        if (draft) {
          setSubject(draft.subject)
          setBody(draft.body)
          setDraftId(draft.id)
          setGenerated(true)
        }
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [company.id])

  async function generateDraft() {
    setLoading(true)
    try {
      const r = await fetch(`/api/email-draft/${company.id}`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ sender_name: sender }),
      })
      if (!r.ok) throw new Error('Generate failed')
      const data = await r.json()
      setSubject(data.subject)
      setBody(data.body)
      setDraftId(data.id)
      setGenerated(true)
    } catch (e) {
      alert('Could not generate email: ' + e.message)
    }
    setLoading(false)
  }

  async function saveDraft() {
    if (!draftId) return
    setSaving(true)
    await fetch(`/api/email-draft/${draftId}`, {
      method:  'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ subject, body }),
    })
    setSaving(false)
  }

  function copyToClipboard() {
    const text = `Subject: ${subject}\n\n${body}`
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  function openInMailClient() {
    const email = company.contact_email || ''
    const mailto = `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
    window.open(mailto, '_blank')
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal-box">
        {/* Header */}
        <div className="modal-header">
          <div>
            <div className="modal-title">✉ Email Draft</div>
            <div className="modal-subtitle">
              {company.name}
              {company.contact_full_name && ` · ${company.contact_full_name}`}
              {company.contact_email && (
                <span style={{ marginLeft: 8, color: 'var(--navy)', fontWeight: 600 }}>
                  &lt;{company.contact_email}&gt;
                </span>
              )}
            </div>
          </div>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        {/* Sender name picker */}
        {!generated && (
          <div style={{ padding: '12px 20px', background: 'var(--gray-50)', borderBottom: '1px solid var(--gray-200)', display: 'flex', alignItems: 'center', gap: 12 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--gray-600)' }}>SENDER NAME</label>
            <input
              className="form-input"
              style={{ width: 160 }}
              value={sender}
              onChange={e => setSender(e.target.value)}
            />
            <button className="btn btn-primary" onClick={generateDraft} disabled={loading}>
              {loading ? 'Generating…' : '✨ Generate Email'}
            </button>
          </div>
        )}

        {/* Email editor */}
        {generated && !loading && (
          <div style={{ padding: 20, flex: 1, overflow: 'auto' }}>
            {/* Subject */}
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label className="form-label">Subject</label>
              <input
                className="form-input"
                value={subject}
                onChange={e => setSubject(e.target.value)}
                style={{ fontSize: 14, fontWeight: 600 }}
              />
            </div>

            {/* Body */}
            <div className="form-group">
              <label className="form-label">Email body</label>
              <textarea
                value={body}
                onChange={e => setBody(e.target.value)}
                rows={22}
                style={{
                  width: '100%', padding: '10px 12px',
                  border: '1px solid var(--gray-200)', borderRadius: 8,
                  fontSize: 13, lineHeight: 1.7, fontFamily: 'inherit',
                  resize: 'vertical', outline: 'none',
                }}
              />
            </div>

            {/* Audit summary chips */}
            {(company.issues || []).length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--gray-400)', marginBottom: 6, textTransform: 'uppercase' }}>
                  Issues referenced in email
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {company.issues.map((issue, i) => (
                    <span key={i} style={{
                      background: 'var(--amber-bg)', color: 'var(--amber)',
                      fontSize: 11, padding: '2px 8px', borderRadius: 6,
                      border: '1px solid #fcd34d',
                    }}>
                      {issue.label || issue.type}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {loading && !generated && (
          <div style={{ padding: 60, textAlign: 'center', color: 'var(--gray-400)' }}>
            <div className="big-spinner" style={{ margin: '0 auto 16px' }} />
            Generating personalised email…
          </div>
        )}

        {/* Footer actions */}
        {generated && (
          <div className="modal-footer">
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-secondary" onClick={generateDraft} disabled={loading} style={{ fontSize: 13 }}>
                ↺ Regenerate
              </button>
              <button className="btn btn-secondary" onClick={saveDraft} disabled={saving} style={{ fontSize: 13 }}>
                {saving ? 'Saving…' : '💾 Save'}
              </button>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="btn btn-secondary"
                onClick={copyToClipboard}
                style={{ fontSize: 13 }}
              >
                {copied ? '✓ Copied!' : '📋 Copy'}
              </button>
              {company.contact_email && (
                <button
                  className="btn btn-primary"
                  onClick={openInMailClient}
                  style={{ fontSize: 13 }}
                >
                  📧 Open in Mail
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
