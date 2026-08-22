import { useState, useEffect } from 'react'

export default function ApprovalQueue() {
  const [drafts,   setDrafts]   = useState([])
  const [loading,  setLoading]  = useState(true)
  const [deciding, setDeciding] = useState(null)
  const [editText, setEditText] = useState({})

  useEffect(() => { loadQueue() }, [])

  async function loadQueue() {
    setLoading(true)
    try {
      const data = await fetch('/api/approval-queue').then(r => r.json())
      setDrafts(Array.isArray(data) ? data : [])
    } catch {}
    setLoading(false)
  }

  async function decide(draftId, decision, rejectionReason = null) {
    setDeciding(draftId)
    try {
      await fetch(`/api/approval-queue/${draftId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision,
          rejection_reason: rejectionReason,
          approved_by: 'James',
          edited_opening: editText[draftId] || null,
        }),
      })
      await loadQueue()
    } catch (e) {
      alert('Action failed: ' + e.message)
    } finally {
      setDeciding(null)
    }
  }

  async function generateAI(draftId, companyId) {
    setDeciding(draftId)
    try {
      await fetch(`/api/personalise/${companyId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ company_id: companyId, draft_id: draftId }),
      })
      await loadQueue()
    } catch (e) {
      alert('AI generation failed: ' + e.message)
    } finally {
      setDeciding(null)
    }
  }

  return (
    <div>
      <div className="card-header" style={{ marginBottom: 16 }}>
        <span className="card-title">AI Copy Approval Queue</span>
        <span style={{ fontSize: 12, color: '#64748b' }}>
          {drafts.length} draft{drafts.length !== 1 ? 's' : ''} pending review
        </span>
      </div>

      <div style={{
        background: '#fef3c7', border: '1px solid #fbbf24', borderRadius: 8,
        padding: '10px 14px', marginBottom: 20, fontSize: 13, color: '#92400e',
      }}>
        ℹ️ Review AI-generated opening lines before they are sent. Approve, reject, or edit each one.
        Approved lines will be inserted at the top of the email body.
      </div>

      {loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: '#94a3b8' }}>Loading…</div>
      ) : drafts.length === 0 ? (
        <div style={{ padding: 40, textAlign: 'center', color: '#94a3b8' }}>
          No AI copy pending review. Generate personalised emails from the Outreach tab first.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {drafts.map(draft => {
            const company = draft.companies || {}
            return (
              <div key={draft.id} className="card" style={{ padding: 0 }}>
                <div style={{ padding: '14px 20px', borderBottom: '1px solid #f1f5f9' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8 }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: 15 }}>{company.name || 'Unknown'}</div>
                      <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
                        {company.domain && <a href={`https://${company.domain}`} target="_blank" rel="noreferrer" style={{ color: '#1e3764' }}>{company.domain}</a>}
                        {company.score && <span style={{ marginLeft: 8 }}>• Score: <strong>{company.score}</strong></span>}
                        {company.icp_match && <span style={{ marginLeft: 8 }}>• ICP: {company.icp_match}</span>}
                        {company.contact_full_name && <span style={{ marginLeft: 8 }}>• {company.contact_full_name}</span>}
                      </div>
                    </div>
                    <span style={{ fontSize: 11, color: '#94a3b8' }}>
                      {draft.generated_at ? new Date(draft.generated_at).toLocaleString('en-GB') : ''}
                    </span>
                  </div>
                </div>

                <div style={{ padding: '14px 20px' }}>
                  <div style={{ fontSize: 12, color: '#64748b', marginBottom: 6, fontWeight: 600 }}>SUBJECT</div>
                  <div style={{
                    background: '#f8fafc', borderRadius: 6, padding: '8px 12px',
                    fontSize: 13, marginBottom: 12,
                  }}>
                    {draft.subject}
                  </div>

                  <div style={{ fontSize: 12, color: '#64748b', marginBottom: 6, fontWeight: 600 }}>
                    AI OPENING LINE
                    {draft.ai_model && <span style={{ fontWeight: 400, marginLeft: 6 }}>({draft.ai_model})</span>}
                  </div>
                  {draft.ai_opening ? (
                    <textarea
                      value={editText[draft.id] !== undefined ? editText[draft.id] : draft.ai_opening}
                      onChange={e => setEditText(prev => ({ ...prev, [draft.id]: e.target.value }))}
                      style={{
                        width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #d1d5db',
                        fontSize: 13, fontFamily: 'inherit', resize: 'vertical', minHeight: 60,
                        boxSizing: 'border-box',
                      }}
                    />
                  ) : (
                    <div style={{ color: '#94a3b8', fontSize: 13, marginBottom: 12, fontStyle: 'italic' }}>
                      No AI opening generated yet.
                      <button
                        className="btn btn-secondary" style={{ marginLeft: 8, padding: '3px 10px', fontSize: 12 }}
                        disabled={deciding === draft.id}
                        onClick={() => generateAI(draft.id, draft.company_id)}
                      >
                        Generate with Claude
                      </button>
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
                    <button
                      className="btn btn-primary"
                      style={{ padding: '6px 18px', background: '#16a34a', borderColor: '#16a34a' }}
                      disabled={deciding === draft.id || !draft.ai_opening}
                      onClick={() => decide(draft.id, 'approved')}
                    >
                      ✓ Approve
                    </button>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '6px 18px', color: '#dc2626', borderColor: '#fca5a5' }}
                      disabled={deciding === draft.id}
                      onClick={() => {
                        const reason = prompt('Rejection reason (optional):')
                        decide(draft.id, 'rejected', reason)
                      }}
                    >
                      ✗ Reject
                    </button>
                    {editText[draft.id] && editText[draft.id] !== draft.ai_opening && (
                      <button
                        className="btn btn-secondary"
                        style={{ padding: '6px 18px' }}
                        disabled={deciding === draft.id}
                        onClick={() => decide(draft.id, 'approved')}
                      >
                        ✓ Approve (Edited)
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
