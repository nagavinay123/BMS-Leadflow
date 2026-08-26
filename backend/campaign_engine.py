"""
BMS LeadFlow — Campaign Engine
Orchestrates the full campaign workflow:
  1. Pull approved members from campaign
  2. Compliance check
  3. Send (or DRY RUN)
  4. Schedule follow-ups
  5. Process webhook events (reply/bounce/unsub → cancel follow-ups + suppress)

DRY_RUN=true (default) → no real emails sent.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

# Follow-up schedule (business days approximately)
FOLLOW_UP_DELAYS = {
    2: timedelta(days=4),   # Step 2: ~4 days after initial
    3: timedelta(days=11),  # Step 3: ~11 days after initial
}


# ─────────────────────────────────────────────────────────────
# Send a campaign email
# ─────────────────────────────────────────────────────────────

def send_campaign_email(campaign_member_id: str) -> dict:
    """
    Send the email for one campaign member.
    Runs all compliance gates before sending.
    Schedules follow-ups on success.
    """
    from database import (
        supabase as db, update_campaign_member, record_event,
        cancel_follow_ups_for_member, add_campaign_member
    )
    from email_provider import get_provider
    from compliance import check_pre_send_compliance, append_compliant_footer, ComplianceError
    from email_templates import generate_email
    from production_readiness import require_production_ready, ProductionNotReadyError

    # ── Fetch member + company + contact ─────────────────────
    rows = (
        db.table("campaign_members")
        .select("*, campaigns(*), companies(*), contacts(*), email_drafts(*)")
        .eq("id", campaign_member_id)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        return {"success": False, "error": "Campaign member not found"}

    member   = rows[0]
    campaign = member.get("campaigns") or {}
    company  = member.get("companies") or {}
    contact  = member.get("contacts") or {}
    draft    = member.get("email_drafts")

    dry_run = campaign.get("dry_run", True) or DRY_RUN

    # ── Production readiness gate (blocks live sends until all requirements met) ──
    try:
        require_production_ready(dry_run)
    except ProductionNotReadyError as pne:
        logger.error("Production readiness gate FAILED: %s", pne)
        return {"success": False, "error": str(pne), "production_gate_failed": True}

    # ── Count emails sent today from this campaign ─────────────
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    sent_today = (
        db.table("events")
        .select("id", count="exact")
        .eq("campaign_id", campaign.get("id"))
        .eq("event_type", "sent")
        .gte("occurred_at", today_start.isoformat())
        .execute()
        .count or 0
    )

    # ── Build email if no draft ───────────────────────────────
    email_addr = contact.get("email") or company.get("contact_email")
    if not email_addr:
        update_campaign_member(campaign_member_id, {"status": "error", "stopped_reason": "no email"})
        return {"success": False, "error": "No email address for this contact"}

    if not draft:
        draft = generate_email(
            company,
            sender_name  = campaign.get("sender_name", "James"),
            sender_title = "Director",
        )
        # Inject AI opening if available
        if company.get("ai_opening"):
            body = draft["body"].replace("__AI_OPENING__", company["ai_opening"])
            draft["body"] = body

    subject = draft.get("subject", "Grow your business with BeMySocial")
    body    = draft.get("body", "")

    # ── Compliance check ──────────────────────────────────────
    try:
        check_pre_send_compliance(
            company    = company,
            contact    = contact if contact else {"email": email_addr, "email_status": "good"
                                                  if company.get("email_verified") else "unverified"},
            campaign   = campaign,
            daily_sent = sent_today,
            dry_run    = dry_run,
        )
    except ComplianceError as ce:
        logger.warning("Compliance gate failed for member %s: %s", campaign_member_id, ce)
        update_campaign_member(campaign_member_id, {
            "status":        "stopped",
            "stopped_reason": str(ce),
        })
        return {"success": False, "error": str(ce), "compliance_blocked": True}

    # ── Append compliant footer ───────────────────────────────
    body_with_footer = append_compliant_footer(body, email_addr)

    # ── Send ──────────────────────────────────────────────────
    provider = get_provider()
    result   = provider.send_email(
        to_email    = email_addr,
        to_name     = contact.get("full_name") or company.get("contact_full_name"),
        subject     = subject,
        body        = body_with_footer,
        from_name   = campaign.get("sender_name", "James"),
        from_email  = campaign.get("sender_email", "james@bemysocial.co.uk"),
        reply_to    = campaign.get("reply_to_email"),
        campaign_id = campaign.get("id"),
        thread_id   = member.get("provider_thread_id"),
    )

    if result.get("success"):
        now = datetime.now(timezone.utc).isoformat()
        update_campaign_member(campaign_member_id, {
            "status":             "sent",
            "sent_at":            now,
            "sequence_step":      member.get("sequence_step", 1),
            "provider_thread_id": result.get("message_id"),
        })

        # Record sent event
        record_event({
            "campaign_id":        campaign.get("id"),
            "campaign_member_id": campaign_member_id,
            "company_id":         company.get("id"),
            "contact_id":         contact.get("id"),
            "event_type":         "sent",
            "email":              email_addr,
            "subject":            subject,
            "provider_event_id":  result.get("message_id"),
            "metadata":           {"dry_run": dry_run, "step": member.get("sequence_step", 1)},
        })

        # Update campaign metrics
        db.table("campaigns").update({"total_sent": db.table("campaigns")
            .select("total_sent").eq("id", campaign.get("id")).execute().data[0]["total_sent"] + 1
        }).eq("id", campaign.get("id")).execute()

        # ── Schedule follow-ups ───────────────────────────────
        if member.get("sequence_step", 1) == 1:
            _schedule_follow_ups(campaign_member_id, campaign, company, contact)

        return {"success": True, "dry_run": dry_run, "message_id": result.get("message_id")}
    else:
        update_campaign_member(campaign_member_id, {
            "status":         "error",
            "stopped_reason": result.get("error", "Send failed"),
        })
        return {"success": False, "error": result.get("error")}


def _schedule_follow_ups(member_id: str, campaign: dict, company: dict, contact: dict):
    """Schedule follow-up emails (steps 2 and 3) for a campaign member."""
    from database import supabase as db
    now = datetime.now(timezone.utc)
    for step, delay in FOLLOW_UP_DELAYS.items():
        scheduled_at = now + delay
        # Skip weekends
        while scheduled_at.weekday() >= 5:
            scheduled_at += timedelta(days=1)
        db.table("follow_ups").insert({
            "campaign_member_id": member_id,
            "campaign_id":        campaign.get("id"),
            "company_id":         company.get("id"),
            "contact_id":         contact.get("id"),
            "sequence_step":      step,
            "scheduled_at":       scheduled_at.isoformat(),
            "status":             "scheduled",
        }).execute()


# ─────────────────────────────────────────────────────────────
# Process due follow-ups (called by scheduler / cron)
# ─────────────────────────────────────────────────────────────

def process_due_follow_ups() -> dict:
    """
    Find and send all follow-ups that are due now.
    Called by scheduler every 15 minutes.
    """
    from database import get_due_follow_ups, supabase as db
    from email_provider import get_provider
    from compliance import append_compliant_footer, ComplianceError, check_pre_send_compliance
    from email_templates import generate_followup_email
    from production_readiness import require_production_ready, ProductionNotReadyError

    due     = get_due_follow_ups(limit=50)
    sent    = 0
    skipped = 0
    errors  = []

    provider = get_provider()

    for fu in due:
        member  = (fu.get("campaign_members") or {})
        company = (member.get("companies") or {})
        contact = member.get("contacts") or {}
        campaign = {}
        fu_id    = fu.get("id")
        step     = fu.get("sequence_step", 2)

        try:
            # Fetch campaign
            cam_rows = db.table("campaigns").select("*").eq("id", fu.get("campaign_id")).limit(1).execute().data
            if not cam_rows:
                raise ValueError("Campaign not found")
            campaign = cam_rows[0]

            # Skip if member stopped
            if member.get("status") in ("replied","bounced","unsubscribed","stopped"):
                db.table("follow_ups").update({"status": "cancelled", "cancel_reason": member["status"]}).eq("id", fu_id).execute()
                skipped += 1
                continue

            email_addr = contact.get("email") or company.get("contact_email")
            if not email_addr:
                skipped += 1
                continue

            dry_run = campaign.get("dry_run", True) or DRY_RUN

            # ── Production gate (follow-up path) ─────────────
            try:
                require_production_ready(dry_run)
            except ProductionNotReadyError as pne:
                logger.error("Production gate blocked follow-up %s: %s", fu_id, pne)
                db.table("follow_ups").update({
                    "status": "cancelled",
                    "cancel_reason": f"production_gate_failed: {str(pne)[:200]}",
                }).eq("id", fu_id).execute()
                skipped += 1
                continue

            # Compliance (skip time check in dry run)
            today_start = datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
            sent_today  = (
                db.table("events").select("id", count="exact")
                .eq("campaign_id", fu.get("campaign_id"))
                .eq("event_type", "sent")
                .gte("occurred_at", today_start.isoformat())
                .execute().count or 0
            )
            try:
                check_pre_send_compliance(
                    company    = company,
                    contact    = contact if contact else {"email": email_addr, "email_status": "good"},
                    campaign   = campaign,
                    daily_sent = sent_today,
                    dry_run    = dry_run,
                )
            except ComplianceError as ce:
                db.table("follow_ups").update({"status": "cancelled", "cancel_reason": str(ce)}).eq("id", fu_id).execute()
                skipped += 1
                continue

            # Generate follow-up email body
            fu_draft = generate_followup_email(company, step=step,
                                               sender_name=campaign.get("sender_name","James"))
            body = append_compliant_footer(fu_draft["body"], email_addr)

            result = provider.send_email(
                to_email   = email_addr,
                to_name    = contact.get("full_name") or company.get("contact_full_name"),
                subject    = fu_draft["subject"],
                body       = body,
                from_name  = campaign.get("sender_name","James"),
                from_email = campaign.get("sender_email","james@bemysocial.co.uk"),
                campaign_id= campaign.get("id"),
                thread_id  = member.get("provider_thread_id"),
            )

            if result.get("success"):
                now_iso = datetime.now(timezone.utc).isoformat()
                db.table("follow_ups").update({"status":"sent","sent_at":now_iso}).eq("id",fu_id).execute()
                from database import update_campaign_member, record_event
                update_campaign_member(member.get("id"), {"sequence_step": step})
                record_event({
                    "campaign_id":        fu.get("campaign_id"),
                    "campaign_member_id": member.get("id"),
                    "company_id":         company.get("id"),
                    "event_type":         "sent",
                    "email":              email_addr,
                    "subject":            fu_draft["subject"],
                    "provider_event_id":  result.get("message_id"),
                    "metadata":           {"step": step, "dry_run": dry_run},
                })
                sent += 1
            else:
                errors.append({"follow_up_id": fu_id, "error": result.get("error")})

        except Exception as exc:
            logger.error("Follow-up processing error for %s: %s", fu_id, exc)
            errors.append({"follow_up_id": fu_id, "error": str(exc)})

    return {"processed": len(due), "sent": sent, "skipped": skipped, "errors": errors}


# ─────────────────────────────────────────────────────────────
# Process webhook events
# ─────────────────────────────────────────────────────────────

def process_webhook_event(payload: dict) -> dict:
    """
    Process a webhook event from the email provider.
    Normalises → stores → triggers automatic actions.
    """
    from email_provider import get_provider
    from database import record_event, update_campaign_member, cancel_follow_ups_for_member, add_to_suppression, supabase as db

    provider = get_provider()
    event    = provider.process_webhook(payload)

    if event.get("dry_run"):
        return {"note": "dry_run webhook — not processed"}

    event_type        = event.get("event_type")
    email             = event.get("email")
    provider_event_id = event.get("provider_event_id")
    occurred_at       = event.get("occurred_at")

    # Find matching campaign member by email
    member_rows = (
        db.table("campaign_members")
        .select("id, campaign_id, company_id, contact_id")
        .execute()
        .data or []
    )
    # Match by contact email
    member = None
    if email:
        cont_rows = db.table("contacts").select("id,company_id").eq("email", email).limit(1).execute().data
        if cont_rows:
            for m in member_rows:
                if m.get("company_id") == cont_rows[0].get("company_id"):
                    member = m
                    break

    # Store event (idempotent)
    record_event({
        "campaign_id":        (member or {}).get("campaign_id"),
        "campaign_member_id": (member or {}).get("id"),
        "company_id":         (member or {}).get("company_id"),
        "event_type":         event_type,
        "email":              email,
        "provider_event_id":  provider_event_id,
        "occurred_at":        occurred_at,
        "metadata":           event.get("metadata", {}),
    })

    # ── Automatic actions ─────────────────────────────────────
    if member:
        member_id = member["id"]
        now_iso   = datetime.now(timezone.utc).isoformat()

        if event_type == "reply":
            update_campaign_member(member_id, {"status": "replied", "replied_at": now_iso})
            cancel_follow_ups_for_member(member_id, "reply")
            logger.info("Reply from %s — follow-ups cancelled", email)

        elif event_type == "bounce":
            update_campaign_member(member_id, {"status": "bounced", "bounced_at": now_iso})
            cancel_follow_ups_for_member(member_id, "bounce")
            if email:
                add_to_suppression({"email": email, "reason": "bounce"})
            logger.info("Bounce from %s — suppressed", email)
            # ── Bounce rate auto-pause (4% threshold) ─────────
            campaign_id = member.get("campaign_id")
            if campaign_id:
                events_data = db.table("events").select("event_type") \
                    .eq("campaign_id", campaign_id) \
                    .in_("event_type", ["sent", "bounce"]).execute().data or []
                total_sent   = sum(1 for e in events_data if e["event_type"] == "sent")
                total_bounce = sum(1 for e in events_data if e["event_type"] == "bounce")
                if total_sent > 0 and (total_bounce / total_sent) >= 0.04:
                    db.table("campaigns").update({
                        "status": "paused",
                        "pause_reason": f"Auto-paused: bounce rate {total_bounce}/{total_sent} ({100*total_bounce//total_sent}%) ≥ 4%",
                    }).eq("id", campaign_id).execute()
                    logger.warning(
                        "Campaign %s auto-paused: bounce rate %d/%d (%.1f%%)",
                        campaign_id, total_bounce, total_sent, 100*total_bounce/total_sent
                    )

        elif event_type == "unsubscribe":
            update_campaign_member(member_id, {"status": "unsubscribed", "unsubscribed_at": now_iso})
            cancel_follow_ups_for_member(member_id, "unsubscribe")
            if email:
                add_to_suppression({"email": email, "reason": "unsubscribe"})
            # Also suppress domain? Only if individual unsubscribe
            logger.info("Unsubscribe from %s — suppressed", email)

    return {"event_type": event_type, "processed": True, "member_found": member is not None}


# ─────────────────────────────────────────────────────────────
# Campaign runner (add qualified companies to a campaign)
# ─────────────────────────────────────────────────────────────

def populate_campaign(campaign_id: str, icp_id: str = None, limit: int = 500) -> dict:
    """
    Add all outreach-ready companies (score ≥ threshold, email verified, not suppressed)
    to a campaign as members. Associates the primary verified contact.
    """
    from database import supabase as db, add_campaign_member, is_suppressed
    from outreach import OUTREACH_SCORE_THRESHOLD

    # Query: companies with score >= threshold AND email_verified = True
    q = db.table("companies").select("id, contact_email, score, icp_id, domain, company_number") \
        .gte("score", OUTREACH_SCORE_THRESHOLD) \
        .eq("email_verified", True)
    if icp_id:
        q = q.eq("icp_id", icp_id)
    companies = q.limit(limit).execute().data or []

    added   = 0
    skipped = 0
    for co in companies:
        # Suppression check
        if is_suppressed(email=co.get("contact_email"), domain=co.get("domain"),
                         company_number=co.get("company_number")):
            skipped += 1
            continue
        # Find primary contact
        cont = db.table("contacts").select("id").eq("company_id", co["id"]) \
               .eq("is_primary", True).limit(1).execute().data
        contact_id = cont[0]["id"] if cont else None
        add_campaign_member({
            "campaign_id": campaign_id,
            "company_id":  co["id"],
            "contact_id":  contact_id,
            "status":      "queued",
        })
        added += 1

    return {"added": added, "skipped": skipped, "total_candidates": len(companies)}
