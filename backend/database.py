"""
BMS LeadFlow — Supabase database layer
Week 6 update: companies now joined with website_audits automatically
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


def _get_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env\n"
            "Find them: Supabase dashboard → Project Settings → API"
        )
    return create_client(url, key)


supabase: Client = _get_client()


# ──────────────────────────────────────────────
# Companies
# ──────────────────────────────────────────────

def insert_company(data: dict) -> dict:
    if data.get("google_place_id"):
        res = (
            supabase.table("companies")
            .upsert(data, on_conflict="google_place_id")
            .execute()
        )
    else:
        res = supabase.table("companies").insert(data).execute()
    return res.data[0] if res.data else {}


def update_company(company_id: str, data: dict):
    supabase.table("companies").update(data).eq("id", company_id).execute()


def update_company_status(company_id: str, status: str):
    supabase.table("companies").update({"status": status}).eq("id", company_id).execute()


def update_company_score(company_id: str, score: int):
    supabase.table("companies").update({"score": score}).eq("id", company_id).execute()


def get_companies(run_id: str = None, status: str = None, limit: int = 200) -> list:
    """
    Fetch companies with their website_audits merged in.
    Supabase relational select: *, website_audits(*) returns the audit as a nested list.
    We flatten it so every company dict has audit fields at the top level.
    """
    query = supabase.table("companies").select("*, website_audits(*)")
    if run_id:
        query = query.eq("discovery_run_id", run_id)
    if status:
        query = query.eq("status", status)
    query = query.order("score", desc=True).limit(limit)

    rows = query.execute().data or []
    return [_merge_audit(row) for row in rows]


def _merge_audit(company: dict) -> dict:
    """
    Flatten the website_audits nested list into the company dict.
    Supabase returns it as: company["website_audits"] = [{...}] or []
    """
    audits = company.pop("website_audits", None) or []
    if audits:
        audit = audits[0]
        company.update({
            "performance_score":    audit.get("performance_score"),
            "mobile_score":         audit.get("mobile_score"),
            "https":                audit.get("https"),
            "has_viewport":         audit.get("has_viewport"),
            "has_title":            audit.get("has_title"),
            "has_meta_description": audit.get("has_meta_description"),
            "issues":               audit.get("issues", []),
            "resolves":             audit.get("resolves"),
            "audit_error":          audit.get("error"),
            "audited_at":           audit.get("audited_at"),
        })
    return company


def get_pipeline_stats() -> dict:
    rows = (
        supabase.table("companies")
        .select("status, ch_matched, has_website, score")
        .execute()
        .data or []
    )
    total           = len(rows)
    by_status       = {}
    ch_matched      = 0
    has_website     = 0
    outreach_ready  = 0

    for r in rows:
        s = r.get("status", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        if r.get("ch_matched"):            ch_matched += 1
        if r.get("has_website"):           has_website += 1
        if (r.get("score") or 0) >= 60:   outreach_ready += 1

    return {
        "total":          total,
        "by_status":      by_status,
        "ch_matched":     ch_matched,
        "has_website":    has_website,
        "outreach_ready": outreach_ready,
        "ch_match_pct":   round(ch_matched  / total * 100) if total else 0,
        "website_pct":    round(has_website / total * 100) if total else 0,
        "outreach_pct":   round(outreach_ready / total * 100) if total else 0,
    }


# ──────────────────────────────────────────────
# Website Audits
# ──────────────────────────────────────────────

def save_website_audit(company_id: str, audit: dict) -> dict:
    supabase.table("website_audits").delete().eq("company_id", company_id).execute()
    record = {**audit, "company_id": company_id}
    res = supabase.table("website_audits").insert(record).execute()
    return res.data[0] if res.data else {}


def get_website_audit(company_id: str) -> dict | None:
    res = (
        supabase.table("website_audits")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def get_all_audits(run_id: str = None) -> list:
    if run_id:
        companies = (
            supabase.table("companies")
            .select("id")
            .eq("discovery_run_id", run_id)
            .execute()
            .data or []
        )
        ids = [c["id"] for c in companies]
        if not ids:
            return []
        return supabase.table("website_audits").select("*").in_("company_id", ids).execute().data or []
    return supabase.table("website_audits").select("*").execute().data or []


# ──────────────────────────────────────────────
# Discovery Runs
# ──────────────────────────────────────────────

def insert_discovery_run(data: dict) -> str:
    res = supabase.table("discovery_runs").insert(data).execute()
    return res.data[0]["id"] if res.data else None


def update_discovery_run(run_id: str, data: dict):
    supabase.table("discovery_runs").update(data).eq("id", run_id).execute()


def delete_discovery_runs(run_ids: list) -> int:
    if not run_ids:
        return 0
    # Nullify FK on companies first so the delete isn't blocked
    supabase.table("companies").update({"discovery_run_id": None}).in_("discovery_run_id", run_ids).execute()
    supabase.table("discovery_runs").delete().in_("id", run_ids).execute()
    return len(run_ids)


def get_discovery_runs(limit: int = 20) -> list:
    return (
        supabase.table("discovery_runs")
        .select("*")
        .order("ran_at", desc=True)
        .limit(limit)
        .execute()
        .data or []
    )


# ──────────────────────────────────────────────
# Suppression List
# ──────────────────────────────────────────────

def is_suppressed(company_number: str = None, domain: str = None, email: str = None) -> bool:
    if company_number:
        if supabase.table("suppression_list").select("id").eq("company_number", company_number).execute().data:
            return True
    if domain:
        if supabase.table("suppression_list").select("id").eq("domain", domain).execute().data:
            return True
    if email:
        if supabase.table("suppression_list").select("id").eq("email", email).execute().data:
            return True
    return False


def add_to_suppression(data: dict):
    supabase.table("suppression_list").insert(data).execute()


def get_suppression_list(limit: int = 500) -> list:
    return (
        supabase.table("suppression_list")
        .select("*")
        .order("added_at", desc=True)
        .limit(limit)
        .execute()
        .data or []
    )


# ──────────────────────────────────────────────
# Contacts
# ──────────────────────────────────────────────

def upsert_contact(data: dict) -> dict:
    """
    Insert or update a contact. Uses (company_id, email) as upsert key.
    Falls back to insert if email is missing.
    """
    if data.get("email") and data.get("company_id"):
        res = (
            supabase.table("contacts")
            .upsert(data, on_conflict="company_id,email")
            .execute()
        )
    else:
        res = supabase.table("contacts").insert(data).execute()
    return res.data[0] if res.data else {}


def get_contacts_for_company(company_id: str) -> list:
    return (
        supabase.table("contacts")
        .select("*")
        .eq("company_id", company_id)
        .order("is_primary", desc=True)
        .execute()
        .data or []
    )


def update_contact_verification(contact_id: str, email_status: str, verified_at=None):
    from datetime import datetime, timezone
    supabase.table("contacts").update({
        "email_status":      email_status,
        "email_verified_at": verified_at or datetime.now(timezone.utc).isoformat(),
    }).eq("id", contact_id).execute()


def migrate_contacts_from_companies():
    """
    One-time migration: move contact data from companies.contact_* columns
    into the contacts table.  Safe to run multiple times.
    """
    rows = (
        supabase.table("companies")
        .select("id, contact_email, contact_first_name, contact_last_name,"
                " contact_full_name, contact_role, email_verified, email_confidence")
        .not_.is_("contact_email", "null")
        .execute()
        .data or []
    )
    migrated = 0
    for row in rows:
        contact = {
            "company_id":     row["id"],
            "email":          row["contact_email"],
            "first_name":     row.get("contact_first_name"),
            "last_name":      row.get("contact_last_name"),
            "full_name":      row.get("contact_full_name"),
            "role":           row.get("contact_role"),
            "email_status":   "good" if row.get("email_verified") else "unverified",
            "email_confidence": row.get("email_confidence"),
            "source":         "companies_house",
            "is_primary":     True,
        }
        upsert_contact(contact)
        migrated += 1
    return migrated


# ──────────────────────────────────────────────
# Campaigns
# ──────────────────────────────────────────────

def get_campaigns(status: str = None, limit: int = 50) -> list:
    q = supabase.table("campaigns").select("*")
    if status:
        q = q.eq("status", status)
    return q.order("created_at", desc=True).limit(limit).execute().data or []


def create_campaign(data: dict) -> dict:
    res = supabase.table("campaigns").insert(data).execute()
    return res.data[0] if res.data else {}


def update_campaign(campaign_id: str, data: dict):
    supabase.table("campaigns").update(data).eq("id", campaign_id).execute()


def get_campaign(campaign_id: str) -> dict:
    res = supabase.table("campaigns").select("*").eq("id", campaign_id).limit(1).execute()
    return res.data[0] if res.data else {}


def get_campaign_stats(campaign_id: str) -> dict:
    from supabase import PostgrestAPIError
    try:
        res = supabase.rpc("v_campaign_stats_fn", {}).eq("id", campaign_id).execute()
        return res.data[0] if res.data else {}
    except Exception:
        # Fallback: manual count
        members = supabase.table("campaign_members").select("status").eq("campaign_id", campaign_id).execute().data or []
        events  = supabase.table("events").select("event_type").eq("campaign_id", campaign_id).execute().data or []
        def count(lst, key, val): return sum(1 for x in lst if x.get(key) == val)
        return {
            "member_count":     len(members),
            "sent":             count(members, "status", "sent"),
            "opens":            count(events,  "event_type", "open"),
            "clicks":           count(events,  "event_type", "click"),
            "replies":          count(events,  "event_type", "reply"),
            "bounces":          count(events,  "event_type", "bounce"),
            "unsubscribes":     count(events,  "event_type", "unsubscribe"),
        }


# ──────────────────────────────────────────────
# Campaign Members
# ──────────────────────────────────────────────

def add_campaign_member(data: dict) -> dict:
    res = supabase.table("campaign_members").upsert(
        data, on_conflict="campaign_id,company_id"
    ).execute()
    return res.data[0] if res.data else {}


def update_campaign_member(member_id: str, data: dict):
    supabase.table("campaign_members").update(data).eq("id", member_id).execute()


def get_campaign_members(campaign_id: str, status: str = None, limit: int = 500) -> list:
    q = supabase.table("campaign_members").select("*, companies(*), contacts(*)").eq("campaign_id", campaign_id)
    if status:
        q = q.eq("status", status)
    return q.order("queued_at").limit(limit).execute().data or []


def get_due_follow_ups(limit: int = 100) -> list:
    """Return follow-ups that are due now and not yet cancelled/sent."""
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()
    return (
        supabase.table("follow_ups")
        .select("*, campaign_members(*, companies(*, contacts(*)))")
        .eq("status", "scheduled")
        .lte("scheduled_at", now_iso)
        .limit(limit)
        .execute()
        .data or []
    )


def cancel_follow_ups_for_member(member_id: str, reason: str):
    from datetime import datetime, timezone
    supabase.table("follow_ups").update({
        "status":       "cancelled",
        "cancelled_at": datetime.now(timezone.utc).isoformat(),
        "cancel_reason": reason,
    }).eq("campaign_member_id", member_id).eq("status", "scheduled").execute()


# ──────────────────────────────────────────────
# Events
# ──────────────────────────────────────────────

def record_event(data: dict) -> dict:
    """Insert an event. Skips if provider_event_id already seen (idempotent)."""
    if data.get("provider_event_id"):
        existing = (
            supabase.table("events")
            .select("id")
            .eq("provider_event_id", data["provider_event_id"])
            .execute()
            .data
        )
        if existing:
            return existing[0]
    res = supabase.table("events").insert(data).execute()
    return res.data[0] if res.data else {}


def get_events(campaign_id: str = None, event_type: str = None, limit: int = 500) -> list:
    q = supabase.table("events").select("*")
    if campaign_id:
        q = q.eq("campaign_id", campaign_id)
    if event_type:
        q = q.eq("event_type", event_type)
    return q.order("occurred_at", desc=True).limit(limit).execute().data or []


# ──────────────────────────────────────────────
# Budget Log
# ──────────────────────────────────────────────

def log_budget(provider: str, amount: float, description: str = "",
               campaign_id: str = None, currency: str = "GBP"):
    supabase.table("budget_log").insert({
        "provider":    provider,
        "amount":      amount,
        "currency":    currency,
        "description": description,
        "campaign_id": campaign_id,
    }).execute()


def get_monthly_budget_summary() -> list:
    try:
        return supabase.table("v_monthly_budget").select("*").execute().data or []
    except Exception:
        return []


def get_budget_this_month() -> float:
    from datetime import datetime, timezone
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rows = (
        supabase.table("budget_log")
        .select("amount")
        .gte("occurred_at", month_start.isoformat())
        .execute()
        .data or []
    )
    return round(sum(r["amount"] for r in rows), 2)
