"""
BMS LeadFlow — Outreach Queue Manager
Week 8

Manages the outreach pipeline:
  queued → emailed → replied → won / lost

Also handles saving and retrieving email drafts.
"""

import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


def _get_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    return create_client(url, key)


# ──────────────────────────────────────────────
# Outreach Queue
# ──────────────────────────────────────────────

def get_outreach_queue(status: str = None, limit: int = 200) -> list:
    """
    Return companies in the outreach queue.
    Optionally filter by status: queued | emailed | replied | won | lost
    """
    supabase = _get_client()
    query = supabase.table("companies").select("*, website_audits(*)").gte("score", 50)

    if status:
        query = query.eq("outreach_status", status)
    else:
        # Default: all that are ready (scored ≥60, not suppressed/lost)
        query = query.neq("outreach_status", "suppressed")

    rows = query.order("score", desc=True).limit(limit).execute().data or []
    return [_merge_audit(r) for r in rows]


def queue_company(company_id: str) -> dict:
    """Move a company into the outreach queue."""
    supabase = _get_client()
    return supabase.table("companies").update({
        "outreach_status":    "queued",
        "outreach_queued_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", company_id).execute().data or {}


def update_outreach_status(company_id: str, status: str, notes: str = None) -> dict:
    """
    Update the outreach status for a company.
    Valid statuses: queued | emailed | replied | won | lost | suppressed
    """
    supabase = _get_client()
    data = {"outreach_status": status}
    if status == "emailed":
        data["outreach_emailed_at"] = datetime.now(timezone.utc).isoformat()
    if notes:
        data["outreach_notes"] = notes
    return supabase.table("companies").update(data).eq("id", company_id).execute().data or {}


def get_outreach_stats() -> dict:
    """Count companies at each outreach stage."""
    supabase = _get_client()
    rows = (
        supabase.table("companies")
        .select("outreach_status, score")
        .gte("score", 50)
        .execute()
        .data or []
    )
    counts = {}
    for r in rows:
        s = r.get("outreach_status") or "none"
        counts[s] = counts.get(s, 0) + 1

    return {
        "queued":     counts.get("queued", 0),
        "emailed":    counts.get("emailed", 0),
        "replied":    counts.get("replied", 0),
        "won":        counts.get("won", 0),
        "lost":       counts.get("lost", 0),
        "none":       counts.get("none", 0),
        "total_ready": sum(counts.values()),
    }


# ──────────────────────────────────────────────
# Email Drafts
# ──────────────────────────────────────────────

def save_email_draft(company_id: str, subject: str, body: str, template_used: str = "default") -> dict:
    supabase = _get_client()
    # Delete old draft for this company first
    supabase.table("email_drafts").delete().eq("company_id", company_id).execute()
    res = supabase.table("email_drafts").insert({
        "company_id":    company_id,
        "subject":       subject,
        "body":          body,
        "template_used": template_used,
    }).execute()
    return res.data[0] if res.data else {}


def get_email_draft(company_id: str) -> dict | None:
    supabase = _get_client()
    res = (
        supabase.table("email_drafts")
        .select("*")
        .eq("company_id", company_id)
        .order("generated_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def mark_draft_sent(draft_id: str):
    supabase = _get_client()
    supabase.table("email_drafts").update({
        "sent":    True,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", draft_id).execute()


def update_draft(draft_id: str, subject: str, body: str):
    supabase = _get_client()
    supabase.table("email_drafts").update({
        "subject": subject,
        "body":    body,
        "edited":  True,
    }).eq("id", draft_id).execute()


# ──────────────────────────────────────────────
# Analytics
# ──────────────────────────────────────────────

def get_pipeline_analytics() -> dict:
    """Returns data for the analytics charts."""
    supabase = _get_client()

    # Runs over time
    runs = (
        supabase.table("discovery_runs")
        .select("ran_at, results_count, query, status, est_cost_usd")
        .order("ran_at", desc=False)
        .limit(30)
        .execute()
        .data or []
    )

    # Score distribution
    scores = (
        supabase.table("companies")
        .select("score, status, ch_matched, has_website")
        .execute()
        .data or []
    )

    score_bands = {"Cold (0-39)": 0, "Cool (40-59)": 0, "Warm (60-79)": 0, "Hot (80+)": 0}
    for r in scores:
        s = r.get("score") or 0
        if s >= 80:     score_bands["Hot (80+)"] += 1
        elif s >= 60:   score_bands["Warm (60-79)"] += 1
        elif s >= 40:   score_bands["Cool (40-59)"] += 1
        else:           score_bands["Cold (0-39)"] += 1

    outreach = get_outreach_stats()

    return {
        "runs":         runs,
        "score_bands":  score_bands,
        "outreach":     outreach,
        "totals": {
            "companies":    len(scores),
            "ch_matched":   sum(1 for r in scores if r.get("ch_matched")),
            "has_website":  sum(1 for r in scores if r.get("has_website")),
            "outreach_ready": sum(1 for r in scores if (r.get("score") or 0) >= 50),
        }
    }


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _merge_audit(company: dict) -> dict:
    audits = company.pop("website_audits", None) or []
    if audits:
        a = audits[0]
        company.update({
            "performance_score":    a.get("performance_score"),
            "mobile_score":         a.get("mobile_score"),
            "https":                a.get("https"),
            "issues":               a.get("issues", []),
            "resolves":             a.get("resolves"),
        })
    return company
