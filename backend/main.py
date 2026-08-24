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

from activity_logger import log_activity
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
from database import supabase as _db
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
    get_campaigns,
    create_campaign,
    update_campaign,
    get_campaign,
    get_campaign_stats,
    add_campaign_member,
    update_campaign_member,
    get_campaign_members,
    get_contacts_for_company,
    record_event,
    get_events,
    get_due_follow_ups,
    cancel_follow_ups_for_member,
    get_budget_this_month,
    log_budget,
    migrate_contacts_from_companies,
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
    max_results:   int  = Field(50, ge=1, le=10000)
    skip_audit:    bool = Field(False)


class BulkSearchItem(BaseModel):
    business_type: str
    town:          str
    max_results:   int = Field(50, ge=1, le=500)

class BulkSearchRequest(BaseModel):
    searches:    list[BulkSearchItem]
    skip_audit:  bool = Field(False)
    icp_id:      Optional[str] = None

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
        log_activity("search", {
            "business_type": request.business_type,
            "town": request.town,
            "max_results": request.max_results,
            "companies_found": len(result.get("companies", [])),
        }, user_email=request.user_email if hasattr(request, "user_email") else None)
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


# ──────────────────────────────────────────────
# Bulk Discovery
# ──────────────────────────────────────────────

@app.post("/api/bulk-search")
def bulk_search(request: BulkSearchRequest):
    """
    Run multiple discovery searches sequentially.
    Deduplication handled by Supabase upsert on google_place_id / company_number / domain.
    """
    results = []
    errors  = []
    total_stored      = 0
    total_outreach    = 0

    for item in request.searches:
        try:
            result = run_discovery(
                business_type = item.business_type.strip(),
                town          = item.town.strip(),
                max_results   = item.max_results,
                skip_audit    = request.skip_audit,
            )
            total_stored   += result.get("stored", 0)
            total_outreach += result.get("outreach_ready", 0)
            results.append({
                "business_type": item.business_type,
                "town":          item.town,
                "stored":        result.get("stored", 0),
                "outreach_ready":result.get("outreach_ready", 0),
                "run_id":        result.get("run_id"),
            })
        except Exception as e:
            errors.append({
                "business_type": item.business_type,
                "town":          item.town,
                "error":         str(e),
            })

    return {
        "total_searches":   len(request.searches),
        "successful":       len(results),
        "failed":           len(errors),
        "total_stored":     total_stored,
        "total_outreach_ready": total_outreach,
        "results":          results,
        "errors":           errors,
    }


# ──────────────────────────────────────────────
# Email Verification (MillionVerifier)
# ──────────────────────────────────────────────

class VerifyEmailRequest(BaseModel):
    email: str

@app.post("/api/verify-email")
def verify_single_email(request: VerifyEmailRequest):
    try:
        from email_verify import verify_email
        return verify_email(request.email)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/verify-email/company/{company_id}")
def verify_company_email(company_id: str):
    try:
        from email_verify import verify_email, should_send
        from database import supabase as db
        from datetime import datetime, timezone
        rows = db.table("companies").select("contact_email").eq("id", company_id).limit(1).execute().data
        if not rows or not rows[0].get("contact_email"):
            raise HTTPException(status_code=404, detail="No contact email for this company")
        email  = rows[0]["contact_email"]
        result = verify_email(email)
        # Update contacts table
        from database import upsert_contact
        upsert_contact({
            "company_id":     company_id,
            "email":          email,
            "email_status":   result["email_status"],
            "email_verified_at": datetime.now(timezone.utc).isoformat() if result["can_send"] else None,
        })
        # Also update companies.email_verified
        db.table("companies").update({
            "email_verified": result["can_send"],
        }).eq("id", company_id).execute()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/migrate-contacts")
def run_contact_migration():
    """One-time migration: copy contact data from companies into contacts table."""
    try:
        migrated = migrate_contacts_from_companies()
        return {"status": "ok", "migrated": migrated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/contacts/{company_id}")
def list_contacts(company_id: str):
    try:
        return get_contacts_for_company(company_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Campaigns
# ──────────────────────────────────────────────

class CampaignRequest(BaseModel):
    name:          str
    description:   Optional[str] = ""
    icp_id:        Optional[str] = None
    sender_name:   str           = "James"
    sender_email:  Optional[str] = None
    reply_to_email:Optional[str] = None
    daily_limit:   int           = Field(25, ge=1, le=100)
    weekly_budget: float         = 0.0
    dry_run:       bool          = True   # Always default to dry run — safety

class CampaignStatusUpdate(BaseModel):
    status: str  # draft | active | paused | completed | cancelled

class AddMembersRequest(BaseModel):
    company_ids:   list[str]
    contact_id:    Optional[str] = None

@app.get("/api/campaigns")
def list_campaigns(status: Optional[str] = None):
    try:
        return get_campaigns(status=status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/campaigns")
def create_new_campaign(request: CampaignRequest):
    try:
        data = request.model_dump()
        return create_campaign(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/campaigns/{campaign_id}")
def get_campaign_detail(campaign_id: str):
    try:
        c = get_campaign(campaign_id)
        if not c:
            raise HTTPException(status_code=404, detail="Campaign not found")
        c["stats"] = get_campaign_stats(campaign_id)
        return c
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/campaigns/{campaign_id}/status")
def update_campaign_status_endpoint(campaign_id: str, request: CampaignStatusUpdate):
    valid = {"draft","active","paused","completed","cancelled"}
    if request.status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid}")
    try:
        update_campaign(campaign_id, {"status": request.status})
        return {"status": request.status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/campaigns/{campaign_id}/members")
def add_campaign_members(campaign_id: str, request: AddMembersRequest):
    try:
        added = 0
        for company_id in request.company_ids:
            add_campaign_member({
                "campaign_id": campaign_id,
                "company_id":  company_id,
                "contact_id":  request.contact_id,
                "status":      "queued",
            })
            added += 1
        return {"added": added}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/campaigns/{campaign_id}/members")
def list_campaign_members_endpoint(campaign_id: str, status: Optional[str] = None):
    try:
        return get_campaign_members(campaign_id, status=status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/campaigns/{campaign_id}/stats")
def campaign_stats_endpoint(campaign_id: str):
    try:
        return get_campaign_stats(campaign_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Events
# ──────────────────────────────────────────────

@app.get("/api/events")
def list_events_endpoint(campaign_id: Optional[str] = None, event_type: Optional[str] = None, limit: int = 200):
    try:
        return get_events(campaign_id=campaign_id, event_type=event_type, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Budget
# ──────────────────────────────────────────────

@app.get("/api/budget")
def budget_summary():
    try:
        return {
            "month_to_date_gbp": get_budget_this_month(),
            "limit_gbp":         100.0,
            "remaining_gbp":     round(100.0 - get_budget_this_month(), 2),
            "detail":            get_monthly_budget_summary_safe(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_monthly_budget_summary_safe():
    try:
        from database import get_monthly_budget_summary
        return get_monthly_budget_summary()
    except Exception:
        return []


# ──────────────────────────────────────────────
# AI Personalisation
# ──────────────────────────────────────────────

class PersonaliseRequest(BaseModel):
    company_id:  str
    draft_id:    Optional[str] = None
    sender_name: str = "James"

@app.post("/api/personalise/{company_id}")
def personalise_email(company_id: str, request: PersonaliseRequest):
    try:
        from claude_personalise import personalise_email as claude_personalise
        from database import supabase as db
        rows = db.table("companies").select("*, website_audits(*)").eq("id", company_id).limit(1).execute().data
        if not rows:
            raise HTTPException(status_code=404, detail="Company not found")
        from database import _merge_audit
        company = _merge_audit(rows[0])
        result  = claude_personalise(company)
        # Persist to email_drafts if draft_id provided
        if request.draft_id and result.get("opening_line"):
            from datetime import datetime, timezone
            db.table("email_drafts").update({
                "ai_opening":      result["opening_line"],
                "ai_model":        result.get("model"),
                "ai_generated_at": datetime.now(timezone.utc).isoformat(),
                "approval_status": "pending",
            }).eq("id", request.draft_id).execute()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Approval Queue
# ──────────────────────────────────────────────

class ApprovalDecision(BaseModel):
    decision:         str   # 'approved' | 'rejected'
    rejection_reason: Optional[str] = None
    approved_by:      str = "James"
    edited_opening:   Optional[str] = None

@app.get("/api/approval-queue")
def get_approval_queue(limit: int = 100):
    """Return email drafts pending AI copy review."""
    try:
        from database import supabase as db
        rows = (
            db.table("email_drafts")
            .select("*, companies(name, domain, contact_full_name, score, icp_match)")
            .eq("approval_status", "pending")
            .not_.is_("ai_opening", "null")
            .order("generated_at", desc=True)
            .limit(limit)
            .execute()
            .data or []
        )
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/approval-queue/{draft_id}")
def decide_draft(draft_id: str, request: ApprovalDecision):
    if request.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")
    try:
        from database import supabase as db
        from datetime import datetime, timezone
        update_data = {
            "approval_status":   request.decision,
            "approved_by":       request.approved_by,
            "approved_at":       datetime.now(timezone.utc).isoformat(),
            "rejection_reason":  request.rejection_reason,
        }
        if request.edited_opening:
            update_data["ai_opening"] = request.edited_opening
        db.table("email_drafts").update(update_data).eq("id", draft_id).execute()
        # Log to decisions_log
        db.table("decisions_log").insert({
            "decision":           f"AI copy {request.decision}: draft {draft_id}",
            "options_considered": f"Original AI opening reviewed",
            "made_by":            request.approved_by,
        }).execute()
        return {"status": request.decision}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Webhook (email events from Smartlead / Instantly)
# ──────────────────────────────────────────────

@app.post("/api/webhook/email")
async def email_webhook(request_body: dict):
    """
    Receive email events from Smartlead / Instantly.
    Processes: sent, open, click, reply, bounce, unsubscribe.
    Idempotent: duplicate provider_event_id is ignored.
    """
    try:
        from campaign_engine import process_webhook_event
        result = process_webhook_event(request_body)
        return {"status": "ok", "processed": result}
    except Exception as e:
        import logging
        logging.error("Webhook processing error: %s | payload: %s", e, request_body)
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────
# Compliance
# ──────────────────────────────────────────────

@app.get("/api/compliance/checklist")
def compliance_checklist():
    """
    Backwards-compatible checklist endpoint.
    Delegates to /api/production-readiness and converts to legacy gate format.
    """
    from production_readiness import check_production_readiness
    pr = check_production_readiness()
    gates = []
    for check_id, c in pr["checks"].items():
        gates.append({
            "id":      check_id,
            "label":   c["label"],
            "ok":      c["status"] == "READY",
            "status":  c["status"],
            "detail":  c["detail"],
            "action":  c["action_required"],
            "who":     c["who_must_act"],
            "mandatory": c.get("mandatory", True),
            "can_claude_verify": c["can_claude_verify"],
        })
    return {
        "ready_for_live_sending": pr["ready_for_live_sending"],
        "dry_run_active":         pr["dry_run_active"],
        "gates":                  gates,
        "blockers":               pr["blockers"],
        "note":                   pr["note"],
    }


@app.get("/api/activity")
def get_activity(limit: int = 50):
    """Return recent activity log entries."""
    try:
        result = _db.table("activity_log") \
            .select("*") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        return result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/activity")
def post_activity(payload: dict):
    """Log a client-side action (e.g. login, status change)."""
    log_activity(
        action=payload.get("action", "unknown"),
        details=payload.get("details", {}),
        user_email=payload.get("user_email"),
    )
    return {"ok": True}


@app.get("/api/production-readiness")
def production_readiness(probe: bool = False):
    """
    Full production readiness check.
    Returns ready_for_live_sending=true ONLY when ALL mandatory gates pass.

    Query param ?probe=true will attempt to authenticate with Smartlead API
    (read-only — no email sent) to verify credentials are valid.
    """
    from production_readiness import check_production_readiness
    return check_production_readiness(probe_sending_platform=probe)


# ──────────────────────────────────────────────
# Follow-ups (manual trigger for testing)
# ──────────────────────────────────────────────

@app.post("/api/process-follow-ups")
def trigger_follow_ups():
    try:
        from campaign_engine import process_due_follow_ups
        result = process_due_follow_ups()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/send/{campaign_member_id}")
def send_email_endpoint(campaign_member_id: str):
    """
    Attempt to send the email for a specific campaign member.
    In DRY_RUN mode, simulates the send without contacting any real email provider.
    """
    try:
        from campaign_engine import send_campaign_email
        result = send_campaign_email(campaign_member_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
