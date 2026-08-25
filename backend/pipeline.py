"""
BMS LeadFlow — Discovery + Audit Pipeline
Week 5 (updated from Week 4)

Flow:
  1. Google Maps search (type + town → raw businesses)
  2. Companies House matching (incorporated entities only)
  3. Suppression check
  4. Store in Supabase (status = 'discovered')
  5. Website audit: SSL, PageSpeed, mobile, title, meta  ← NEW Week 5
  6. Score each company 0–100                            ← NEW Week 5
  7. Update status to 'enriched'

CLI:
  python pipeline.py --type "plumber" --town "Leeds" --max 50
  python pipeline.py --type "plumber" --town "Leeds" --max 50 --skip-audit
"""

import argparse
import sys
import time
from datetime import datetime, timezone

import os
from dotenv import load_dotenv
load_dotenv()

# Use Apify if token is set, otherwise fall back to Google Maps Places API
if os.getenv("APIFY_API_TOKEN"):
    from apify_scraper import search_businesses, estimate_cost
    print("  [pipeline] Data source: Apify Google Maps scraper")
else:
    from google_maps import search_businesses, estimate_cost
    print("  [pipeline] Data source: Google Maps Places API")
from companies_house   import match_to_companies_house, get_primary_director
from email_finder      import find_email, find_emails_for_domain, hunter_available
from website_checker   import audit_companies
from scoring           import calculate_score
from database import (
    insert_company,
    insert_discovery_run,
    update_discovery_run,
    update_company,
    update_company_score,
    update_company_status,
    save_website_audit,
    is_suppressed,
    get_companies,
    upsert_contact,
)
from email_verify import verify_email, mv_available, should_send
from outreach import OUTREACH_SCORE_THRESHOLD


# ──────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────

def run_discovery(
    business_type: str,
    town: str,
    max_results: int = 50,
    skip_audit: bool = False,
) -> dict:
    """
    Full discovery + audit pipeline.

    Returns a summary dict with run_id, counts, and the stored companies list.
    """
    _header(f"LeadFlow Pipeline | {business_type} in {town} | max {max_results}")

    run_id = insert_discovery_run({
        "source":        "google_maps+companies_house",
        "query":         {"business_type": business_type, "town": town, "max_results": max_results},
        "results_count": 0,
        "est_cost_usd":  0,
        "ran_at":        datetime.now(timezone.utc).isoformat(),
        "status":        "running",
    })

    stats = {
        "run_id":            run_id,
        "total_from_google": 0,
        "suppressed":        0,
        "no_website":        0,
        "ch_matched":        0,
        "ch_unmatched":      0,
        "audited":           0,
        "stored":            0,
        "outreach_ready":    0,   # score >= OUTREACH_SCORE_THRESHOLD
        "est_cost_usd":      0.0,
        "companies":         [],
    }

    # ── Step 1: Google Maps ─────────────────────────────────
    print("\nStep 1/3  Google Maps search…")
    try:
        places = search_businesses(business_type, town, max_results)
    except Exception as e:
        update_discovery_run(run_id, {"status": "failed", "error": str(e)})
        raise RuntimeError(f"Google Maps search failed: {e}")

    stats["total_from_google"] = len(places)
    print(f"  → {len(places)} businesses found")

    # ── Step 2: CH matching + store ─────────────────────────
    print(f"\nStep 2/3  Companies House matching…")
    # Load active ICP profiles once (used in scoring)
    try:
        from icp_profiles import get_active_profiles
        active_profiles = get_active_profiles()
        print(f"  [ICP] {len(active_profiles)} active profile(s) loaded")
    except Exception:
        active_profiles = []
    stored_companies = []

    for i, place in enumerate(places, 1):
        name   = place.get("name", "Unknown")
        domain = place.get("domain")

        if is_suppressed(domain=domain):
            stats["suppressed"] += 1
            continue

        if not place.get("has_website"):
            stats["no_website"] += 1

        ch = match_to_companies_house(name, town)

        if ch:
            stats["ch_matched"] += 1
            ch_tag = f"CH {ch['company_number']}"
        else:
            stats["ch_unmatched"] += 1
            ch_tag = "no CH"
            print(f"  [{i:02d}/{len(places)}] {name[:40]} … {ch_tag} — skipped (PECR: incorporated only)")
            continue  # Only store Companies House-matched entities

        print(f"  [{i:02d}/{len(places)}] {name[:40]} … {ch_tag}")

        record = {
            "name":               name,
            "domain":             domain,
            "phone":              place.get("phone", ""),
            "website":            place.get("website", ""),
            "has_website":        place.get("has_website", False),
            "rating":             place.get("rating"),
            "review_count":       place.get("review_count"),
            "registered_address": place.get("formatted_address", ""),
            "source":             "google_maps",
            "source_url":         place.get("google_maps_url", ""),
            "google_place_id":    place.get("place_id", ""),
            "discovery_run_id":   run_id,
            "status":             "discovered",
            "ch_matched":         bool(ch),
            "score":              0,
            "instagram_url":      place.get("instagram_url"),
            "facebook_url":       place.get("facebook_url"),
        }

        if ch:
            record.update({
                "company_number":     ch["company_number"],
                "registered_name":    ch["registered_name"],
                "registered_address": ch["registered_address"],
                "incorporation_date": ch.get("incorporation_date"),
                "company_status":     ch["company_status"],
                "company_type":       ch["company_type"],
                "sic_codes":          ch.get("sic_codes", []),
            })

            # ── Officer lookup (director / owner name) ──────
            director = get_primary_director(ch["company_number"])
            if director:
                record["contact_first_name"] = director["first_name"]
                record["contact_last_name"]  = director["last_name"]
                record["contact_full_name"]  = director["full_name"]
                record["contact_role"]       = director["role"]
                print(f"         👤 Director: {director['full_name']}")

            # ── Email finder (Hunter.io) ─────────────────────
            if hunter_available() and domain and director:
                email_result = find_email(
                    domain,
                    director["first_name"],
                    director["last_name"],
                )
                if email_result.get("email"):
                    found_email  = email_result["email"]
                    confidence   = email_result["confidence"]

                    # ── MillionVerifier verification ─────────────
                    if mv_available():
                        mv_result   = verify_email(found_email)
                        email_status = mv_result["email_status"]
                        email_verified = mv_result["can_send"]
                        print(f"         📧 Email: {found_email} → {email_status} (MV)")
                    else:
                        # Hunter confidence >= 80 as fallback (NOT spec-compliant — use MV in prod)
                        email_status   = "unverified"
                        email_verified = False
                        print(f"         📧 Email: {found_email} ({confidence}%) [MV key missing]")

                    record["contact_email"]    = found_email
                    record["email_confidence"] = confidence
                    record["email_verified"]   = email_verified
                    record["_email_status"]    = email_status  # internal, stripped before DB insert

        try:
            # Strip internal-only fields before DB insert
            email_status = record.pop("_email_status", "unverified")

            stored = insert_company(record)
            company_id = stored.get("id")
            record["id"] = company_id
            stored_companies.append(record)
            stats["stored"] += 1

            # ── Write to contacts table ──────────────────────
            if company_id and record.get("contact_email"):
                upsert_contact({
                    "company_id":     company_id,
                    "email":          record["contact_email"],
                    "first_name":     record.get("contact_first_name"),
                    "last_name":      record.get("contact_last_name"),
                    "full_name":      record.get("contact_full_name"),
                    "role":           record.get("contact_role"),
                    "email_status":   email_status,
                    "email_confidence": record.get("email_confidence"),
                    "email_verified_at": datetime.now(timezone.utc).isoformat() if record.get("email_verified") else None,
                    "source":         "companies_house",
                    "is_primary":     True,
                })
        except Exception as e:
            print(f"  ⚠️  Store failed for {name}: {e}")

        time.sleep(0.05)

    stats["companies"] = stored_companies

    # ── Step 3: Website audit + scoring ─────────────────────
    if skip_audit:
        print("\nStep 3/3  Skipping website audit (--skip-audit flag set)")
    else:
        companies_with_sites = [c for c in stored_companies if c.get("has_website")]
        print(f"\nStep 3/3  Website audit ({len(companies_with_sites)} companies with websites)…")

        audit_pairs = audit_companies(companies_with_sites)
        stats["audited"] = len(audit_pairs)

        for company_id, audit in audit_pairs:
            # Find the company record
            company = next((c for c in stored_companies if c.get("id") == company_id), {})

            # ── Pop company-level fields BEFORE saving audit ─
            scraped_email  = audit.pop("scraped_email",  None)
            instagram_url  = audit.pop("instagram_url",  None)
            facebook_url   = audit.pop("facebook_url",   None)

            # Save audit (now clean — no extra columns)
            save_website_audit(company_id, audit)

            social_update = {}
            if instagram_url and not company.get("instagram_url"):
                social_update["instagram_url"] = instagram_url
                company["instagram_url"] = instagram_url
                print(f"         📷 Instagram: {instagram_url}")
            if facebook_url and not company.get("facebook_url"):
                social_update["facebook_url"] = facebook_url
                company["facebook_url"] = facebook_url
                print(f"         👍 Facebook:  {facebook_url}")
            if social_update:
                update_company(company_id, social_update)

            if scraped_email and not company.get("contact_email"):
                update_company(company_id, {
                    "contact_email":    scraped_email,
                    "email_verified":   False,
                    "email_confidence": 50,
                })
                company["contact_email"]    = scraped_email
                company["email_verified"]   = False
                company["email_confidence"] = 50
                print(f"         📧 Scraped email: {scraped_email}")

            # Calculate score (with ICP profiles)
            score, breakdown = calculate_score(company, audit, icp_profiles=active_profiles)
            icp_match = breakdown.get("icp_match")
            update_company_score(company_id, score)
            if icp_match:
                update_company(company_id, {"icp_match": icp_match})
                company["icp_match"] = icp_match
            update_company_status(company_id, "enriched")

            # Patch the in-memory record too (so the return value is accurate)
            company["score"]  = score
            company["status"] = "enriched"

            if score >= OUTREACH_SCORE_THRESHOLD:
                stats["outreach_ready"] += 1

        # Score companies with no website too
        for company in stored_companies:
            if not company.get("has_website") and company.get("id"):
                score, breakdown = calculate_score(company, None, icp_profiles=active_profiles)
                update_company_score(company["id"], score)
                icp_match = breakdown.get("icp_match")
                if icp_match:
                    update_company(company["id"], {"icp_match": icp_match})
                    company["icp_match"] = icp_match
                company["score"] = score

    # ── Finalise run ────────────────────────────────────────
    est = estimate_cost(stats["total_from_google"])
    stats["est_cost_usd"] = est

    update_discovery_run(run_id, {
        "results_count": stats["stored"],
        "est_cost_usd":  est,
        "status":        "complete",
    })

    # Re-fetch from DB so companies include merged audit data
    stats["companies"] = get_companies(run_id=run_id)

    _print_summary(stats)
    return stats


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _header(text: str):
    print(f"\n{'='*55}\n  {text}\n{'='*55}")


def _print_summary(s: dict):
    print(f"\n{'─'*55}")
    print(f"  SUMMARY — Run ID: {s['run_id']}")
    print(f"{'─'*55}")
    print(f"  From Google Maps:    {s['total_from_google']}")
    print(f"  Suppressed:          {s['suppressed']}")
    print(f"  No website:          {s['no_website']}")
    print(f"  CH matched:          {s['ch_matched']}")
    print(f"  Stored to Supabase:  {s['stored']}")
    print(f"  Websites audited:    {s['audited']}")
    print(f"  Outreach ready (≥{OUTREACH_SCORE_THRESHOLD}):{s['outreach_ready']}")
    print(f"  Est. API cost:       ~${s['est_cost_usd']:.4f}")
    print(f"{'─'*55}\n")


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BMS LeadFlow pipeline (Week 5)")
    parser.add_argument("--type",         dest="business_type", required=True)
    parser.add_argument("--town",         required=True)
    parser.add_argument("--max",          dest="max_results", type=int, default=50)
    parser.add_argument("--skip-audit",   action="store_true",
                        help="Skip website checker (faster, for testing)")
    args = parser.parse_args()

    try:
        run_discovery(
            business_type = args.business_type,
            town          = args.town,
            max_results   = args.max_results,
            skip_audit    = args.skip_audit,
        )
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        sys.exit(1)
