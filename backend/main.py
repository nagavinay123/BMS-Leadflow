"""
BMS LeadFlow — FastAPI Backend
Week 12 (complete)

Endpoints:
  POST /api/search             → run discovery + audit pipeline
  POST /api/audit              → audit companies from a run
  GET  /api/companies          → list companies (with audit data joined)
  GET  /api/runs               → discovery run history
  GET  /api/stats              → pipeline statistics
  GET  /api/audits             → all website audits
  GET  /api/audits/{id}        → single audit

  GET  /api/outreach           → companies in outreach queue (score ≥60)
  POST /api/outreach/{id}/queue          → add company to queue
  POST /api/outreach/{id}/status         → update status (emailed/replied/won/lost)
  GET  /api/outreach/stats               → outreach funnel counts
  POST /api/email-draft/{company_id}     → generate personalised email
  GET  /api/email-draft/{company_id}     → get saved draft
  PATCH /api/email-draft/{draft_id}      → edit draft

  GET  /api/icp                → list ICP profiles
  POST /api/icp                → create ICP profile
  PATCH /api/icp/{id}          → update ICP profile
  DELETE /api/icp/{id}         → delete ICP profile
  POST /api/icp/seed           → seed default profiles

  GET  /api/analytics          → pipeline analytics for charts

  GET  /api/suppression        → suppression list
  POST /api/suppression        → add to suppression list

Start:
  uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from pipeline        import run_discovery
from website_checker import audit_companies
from scoring         import calculate_score
from email_templates import generate_email
from outreach        import (
    get_outreach_queue, queue_company, update_outreach_status, get_outreach_stats,
    save_email_draft, get_email_draft, mark_draft_sent, update_draft,
    get_pipeline_analytics,
)
from icp_profiles    import get_all_profiles, create_profile, update_profile, delete_profile, seed_default_profiles
from database import (
    get_companies,
    get_discovery_runs,
    get_pipeline_stats,
    get_suppression_list,
    add_to_suppression,
    get_all_audits,
    get_website_audit,
    save_website_audit,
    update_company_score,
    update_company_status,
)

app = FastAPI(
    title       = "BMS LeadFlow API",
    description = "Lead generation pipeline for BeMySocial",
    version     = "1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["http://localhost:5173", "http://localhost:3000"],
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)


# ──────────────────────────────────────────────
# Request models
# ──────────────────────────────────────────────

class SearchRequest(BaseModel):
    business_type: str  = Field(..., min_length=2)
    town:          str  = Field(..., min_length=2)
    max_results:   int  = Field(50, ge=1, le=60)
    skip_audit:    bool = Field(False)

class AuditRequest(BaseModel):
    run_id: Optional[str] = None
    limit:  int = Field(50, ge=1, le=200)

class OutreachStatusRequest(BaseModel):
    status: str  # queued | emailed | replied | won | lost | suppressed
    notes:  Optional[str] = None

class EmailDraftRequest(BaseModel):
    sender_name:  str = "James"
    sender_title: str = "Director"

class EmailDraftUpdate(BaseModel):
    subject: str
    body:    str

class ICPProfileRequest(BaseModel):
    name:           str
    description:    Optional[str] = ""
    business_types: Optional[list] = []
    sic_codes:      Optional[list] = []
    min_reviews:    Optional[int]  = 0
    min_rating:     Optional[float] = 0
    active:         Optional[bool] = True

class SuppressionEntry(BaseModel):
    domain:         Optional[str] = None
    company_number: Optional[str] = None
    email:          Optional[str] = None
    reason:         str = "manual"


# ──────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# ──────────────────────────────────────────────
# Discovery + Audit pipeline
# ──────────────────────────────────────────────

@app.post("/api/search")
def search(request: SearchRequest):
    try:
        result = run_discovery(
            business_type = request.business_type.strip(),
            town          = request.town.strip(),
            max_results   = request.max_results,
            skip_audit    = request.skip_audit,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")


@app.post("/api/audit")
def run_audit(request: AuditRequest):
    try:
        companies = get_companies(run_id=request.run_id, limit=request.limit)
        to_audit  = [c for c in companies if c.get("has_website")]
        if not to_audit:
            return {"audited": 0, "message": "No companies with websites found"}

        pairs = audit_companies(to_audit)
        scored = 0
        for company_id, audit in pairs:
            save_website_audit(company_id, audit)
            company = next((c for c in to_audit if c.get("id") == company_id), {})
            score, _ = calculate_score(company, audit)
            update_company_score(company_id, score)
            update_company_status(company_id, "enriched")
            scored += 1

        return {"audited": len(pairs), "scored": scored}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Companies
# ──────────────────────────────────────────────

@app.get("/api/companies")
def list_companies(run_id: Optional[str] = None, status: Optional[str] = None, limit: int = 200):
    try:
        return get_companies(run_id=run_id, status=status, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/runs")
def list_runs(limit: int = 20):
    try:
        return get_discovery_runs(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class DeleteRunsRequest(BaseModel):
    run_ids: list[str]

@app.delete("/api/runs")
def delete_runs(body: DeleteRunsRequest):
    try:
        from database import delete_discovery_runs
        deleted = delete_discovery_runs(body.run_ids)
        return {"deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats")
def pipeline_stats():
    try:
        return get_pipeline_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audits")
def list_audits(run_id: Optional[str] = None):
    try:
        return get_all_audits(run_id=run_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/audits/{company_id}")
def get_audit(company_id: str):
    try:
        audit = get_website_audit(company_id)
        if not audit:
            raise HTTPException(status_code=404, detail="No audit found")
        return audit
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Outreach Queue
# ──────────────────────────────────────────────

@app.get("/api/outreach")
def list_outreach(status: Optional[str] = None, limit: int = 200):
    try:
        return get_outreach_queue(status=status, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/outreach/{company_id}/queue")
def add_to_queue(company_id: str):
    try:
        queue_company(company_id)
        return {"status": "queued", "company_id": company_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/outreach/{company_id}/status")
def set_outreach_status(company_id: str, request: OutreachStatusRequest):
    valid = {"queued", "emailed", "replied", "won", "lost", "suppressed", "none"}
    if request.status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid}")
    try:
        update_outreach_status(company_id, request.status, request.notes)
        return {"status": request.status, "company_id": company_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/outreach/stats")
def outreach_stats():
    try:
        return get_outreach_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Email Drafts
# ──────────────────────────────────────────────

@app.post("/api/email-draft/{company_id}")
def create_email_draft(company_id: str, request: EmailDraftRequest):
    try:
        companies = get_companies(limit=1)
        # Fetch this specific company
        from database import supabase as db
        rows = db.table("companies").select("*, website_audits(*)").eq("id", company_id).limit(1).execute().data
        if not rows:
            raise HTTPException(status_code=404, detail="Company not found")

        from database import _merge_audit
        company = _merge_audit(rows[0])
        draft   = generate_email(company, sender_name=request.sender_name, sender_title=request.sender_title)
        saved   = save_email_draft(company_id, draft["subject"], draft["body"], draft["template_used"])
        return {**draft, "id": saved.get("id"), "company_id": company_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/email-draft/{company_id}")
def fetch_email_draft(company_id: str):
    try:
        draft = get_email_draft(company_id)
        if not draft:
            raise HTTPException(status_code=404, detail="No draft found — generate one first")
        return draft
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/email-draft/{draft_id}")
def edit_email_draft(draft_id: str, request: EmailDraftUpdate):
    try:
        update_draft(draft_id, request.subject, request.body)
        return {"status": "updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/email-draft/{draft_id}/sent")
def mark_sent(draft_id: str):
    try:
        mark_draft_sent(draft_id)
        return {"status": "marked_sent"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# ICP Profiles
# ──────────────────────────────────────────────

@app.get("/api/icp")
def list_icp():
    try:
        return get_all_profiles()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/icp")
def create_icp(request: ICPProfileRequest):
    try:
        return create_profile(request.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/icp/{profile_id}")
def update_icp(profile_id: str, request: ICPProfileRequest):
    try:
        return update_profile(profile_id, request.model_dump(exclude_none=True))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/icp/{profile_id}")
def delete_icp(profile_id: str):
    try:
        delete_profile(profile_id)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/icp/seed")
def seed_icp(force: bool = False):
    try:
        result = seed_default_profiles(force=force)
        return {"status": "seeded", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Analytics
# ──────────────────────────────────────────────

@app.get("/api/analytics")
def analytics():
    try:
        return get_pipeline_analytics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Suppression List
# ──────────────────────────────────────────────

@app.get("/api/suppression")
def list_suppression(limit: int = 200):
    try:
        return get_suppression_list(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/suppression")
def add_suppression(entry: SuppressionEntry):
    if not any([entry.domain, entry.company_number, entry.email]):
        raise HTTPException(status_code=400, detail="Provide at least one of: domain, company_number, email")
    try:
        add_to_suppression(entry.model_dump(exclude_none=True))
        return {"status": "added"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
