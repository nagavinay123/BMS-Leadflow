"""
BMS LeadFlow — ICP Profile Manager

ICP = Ideal Customer Profile
Defines what kind of business BMS targets.

Profiles are stored in Supabase icp_profiles table using the base columns
that have always existed: name, description, business_types, sic_codes,
min_reviews, min_rating, active.

Signal-based matching (e.g. "poor website") is handled in Python code
so it works regardless of whether optional DB columns have been added.
"""

import os
from datetime import date, datetime
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ──────────────────────────────────────────────
# Default ICP profiles
# ONLY uses guaranteed base columns — safe to insert on any schema version
# ──────────────────────────────────────────────
DEFAULT_PROFILES = [
    # ── BMS Live Campaign (sector-agnostic, signal-based) ──────
    # Identified in matching code by the "BMS Live Campaign" prefix.
    # Matches ANY company: CH-matched, active, poor website. No sector filter.
    {
        "name":           "BMS Live Campaign — UK SME Poor Website",
        "description":    "UK incorporated SMEs, trading 2+ years, active at Companies House, "
                          "with a live website that scores poorly on speed or has no SSL. "
                          "The website weakness is exactly what BMS web design and SEO fixes.",
        "business_types": [],
        "sic_codes":      [],
        "min_reviews":    0,
        "min_rating":     0.0,
        "active":         True,
    },

    # ── Estate Agents & Lettings ────────────────────────────────
    {
        "name":           "Estate Agents & Lettings",
        "description":    "UK property agencies — estate agents, letting agents, property management. "
                          "High-competition sector where a strong website and SEO = more listings.",
        "business_types": [
            "estate agent", "letting agent", "lettings", "property", "property management",
            "real estate", "land agent", "surveyor",
        ],
        "sic_codes":      ["68310", "68320", "68100", "68201", "68209"],
        "min_reviews":    5,
        "min_rating":     3.5,
        "active":         True,
    },

    # ── IT Support & Technology ─────────────────────────────────
    {
        "name":           "IT Support & Technology Services",
        "description":    "Local IT support companies, managed service providers, tech consultants. "
                          "Many have outdated websites despite working in tech — easy BMS win.",
        "business_types": [
            "IT support", "IT services", "managed service", "MSP", "tech support",
            "computer repair", "network", "cybersecurity", "software",
        ],
        "sic_codes":      ["62010", "62020", "62030", "62090", "63110", "95110"],
        "min_reviews":    3,
        "min_rating":     3.5,
        "active":         True,
    },

    # ── Local Trades ────────────────────────────────────────────
    {
        "name":           "Local Trades (Plumber / Electrician / Builder)",
        "description":    "Small UK trade businesses with a web presence needing digital upgrade.",
        "business_types": [
            "plumber", "plumbing", "electrician", "electrical", "builder", "building",
            "decorator", "roofer", "roofing", "carpenter", "joiner", "painter",
            "handyman", "gas engineer", "heating engineer",
        ],
        "sic_codes":      ["43210", "43220", "43290", "43310", "43320", "43390"],
        "min_reviews":    5,
        "min_rating":     3.5,
        "active":         True,
    },

    # ── Professional Services ───────────────────────────────────
    {
        "name":           "Professional Services (Accountant / Solicitor)",
        "description":    "Regulated professional firms needing compliant, trust-building websites.",
        "business_types": [
            "accountant", "accounting", "solicitor", "solicitors", "financial advisor",
            "financial adviser", "architect", "tax advisor", "bookkeeper",
        ],
        "sic_codes":      ["69100", "69201", "69202", "70229", "74100", "66220"],
        "min_reviews":    3,
        "min_rating":     3.8,
        "active":         True,
    },

    # ── Health & Beauty ─────────────────────────────────────────
    {
        "name":           "Health & Beauty (Salon / Gym / Dentist)",
        "description":    "Appointment-based businesses benefiting from online booking and social proof.",
        "business_types": [
            "hair salon", "hairdresser", "gym", "dental", "dentist", "beauty salon",
            "beauty therapist", "physio", "physiotherapy", "nail salon", "spa", "barber",
        ],
        "sic_codes":      ["86230", "93110", "96020", "96040", "86210"],
        "min_reviews":    5,
        "min_rating":     4.0,
        "active":         True,
    },
]


# ──────────────────────────────────────────────
# Supabase client
# ──────────────────────────────────────────────
def _get_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    return create_client(url, key)


# ──────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────
def get_all_profiles() -> list:
    supabase = _get_client()
    return supabase.table("icp_profiles").select("*").order("name").execute().data or []


def get_active_profiles() -> list:
    supabase = _get_client()
    return supabase.table("icp_profiles").select("*").eq("active", True).execute().data or []


def create_profile(data: dict) -> dict:
    supabase = _get_client()
    res = supabase.table("icp_profiles").insert(data).execute()
    return res.data[0] if res.data else {}


def update_profile(profile_id: str, data: dict) -> dict:
    supabase = _get_client()
    res = supabase.table("icp_profiles").update(data).eq("id", profile_id).execute()
    return res.data[0] if res.data else {}


def delete_profile(profile_id: str):
    supabase = _get_client()
    supabase.table("icp_profiles").delete().eq("id", profile_id).execute()


def seed_default_profiles(force: bool = False) -> dict:
    """
    Insert the default ICP profiles.
    force=True  → delete all first, then re-seed.
    force=False → skip if any profiles already exist.
    Returns a dict with counts of seeded / skipped / failed.
    """
    supabase = _get_client()
    existing = supabase.table("icp_profiles").select("id").limit(1).execute().data

    if existing and not force:
        print("ICP profiles already exist — skipping seed (use force=True to reload)")
        return {"skipped": True, "reason": "profiles already exist"}

    if force and existing:
        try:
            supabase.table("icp_profiles").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            print("🗑  Cleared existing ICP profiles")
        except Exception as e:
            print(f"⚠️  Could not clear existing profiles: {e}")

    seeded = 0
    failed = 0
    errors = []

    for profile in DEFAULT_PROFILES:
        try:
            supabase.table("icp_profiles").insert(profile).execute()
            print(f"  ✅ Inserted: {profile['name']}")
            seeded += 1
        except Exception as e:
            print(f"  ❌ Failed to insert '{profile['name']}': {e}")
            errors.append({"profile": profile["name"], "error": str(e)})
            failed += 1

    print(f"✅ Seed complete — {seeded} inserted, {failed} failed")
    return {"seeded": seeded, "failed": failed, "errors": errors}


# ──────────────────────────────────────────────
# Signal matching helpers
# ──────────────────────────────────────────────
def _company_age_years(company: dict) -> float:
    """Return years since incorporation, or 99 if unknown."""
    raw = company.get("incorporation_date")
    if not raw:
        return 99.0
    try:
        if isinstance(raw, str):
            inc = datetime.strptime(raw[:10], "%Y-%m-%d").date()
        else:
            inc = raw
        return (date.today() - inc).days / 365.25
    except Exception:
        return 99.0


def _is_live_campaign_match(company: dict, audit: dict | None) -> bool:
    """
    BMS Live Campaign signal: sector-agnostic.
    Matches if company:
      - has been trading 2+ years (or incorporation unknown), AND
      - has a website with poor speed/mobile (< 70) OR no SSL OR no website
    """
    age = _company_age_years(company)
    if age < 2:
        return False   # too new

    # No website at all = maximum opportunity
    if not company.get("has_website"):
        return True

    if audit:
        perf = audit.get("performance_score")
        mob  = audit.get("mobile_score")
        ssl  = audit.get("https", True)
        if not ssl:
            return True
        if perf is not None and perf < 70:
            return True
        if mob is not None and mob < 70:
            return True

    return False


# ──────────────────────────────────────────────
# Matching — called by scoring.py
# ──────────────────────────────────────────────
def get_matching_profile(
    company: dict,
    profiles: list,
    audit: dict | None = None,
) -> str | None:
    """
    Return the name of the first matching active ICP profile, or None.

    Priority order:
      1. SIC code overlap (most specific)
      2. Business name keyword match
      3. BMS Live Campaign signal match (sector-agnostic, lowest priority)
    """
    business_name = (company.get("name") or "").lower()
    sic_codes     = company.get("sic_codes") or []

    live_campaign_name = None

    for profile in profiles:
        profile_sics = profile.get("sic_codes") or []
        keywords     = [k.lower() for k in (profile.get("business_types") or [])]
        p_name       = profile.get("name", "")

        # Live Campaign profile — signal-based, defer to end
        if p_name.startswith("BMS Live Campaign"):
            if _is_live_campaign_match(company, audit):
                live_campaign_name = p_name
            continue

        # SIC match (highest specificity)
        if profile_sics and any(s in profile_sics for s in sic_codes):
            return p_name

        # Keyword match
        if keywords and any(kw in business_name for kw in keywords):
            return p_name

    # Fall back to Live Campaign if nothing more specific matched
    return live_campaign_name


def icp_bonus_score(
    company: dict,
    profiles: list = None,
    audit: dict | None = None,
) -> int:
    """
    Return bonus ICP-fit points (0–5).
    Called by scoring.py — higher = better ICP match for BMS.
    """
    if profiles is None:
        try:
            profiles = get_active_profiles()
        except Exception:
            return 0

    business_name = (company.get("name") or "").lower()
    sic_codes     = company.get("sic_codes") or []
    rating        = company.get("rating") or 0
    review_count  = company.get("review_count") or 0

    live_campaign_bonus = 0

    for profile in profiles:
        profile_sics = profile.get("sic_codes") or []
        keywords     = [k.lower() for k in (profile.get("business_types") or [])]
        p_name       = profile.get("name", "")

        # Live Campaign — signal-based
        if p_name.startswith("BMS Live Campaign"):
            if _is_live_campaign_match(company, audit):
                live_campaign_bonus = 5
            continue

        # SIC match → full bonus
        if profile_sics and any(s in profile_sics for s in sic_codes):
            return 5

        # Keyword match → check review/rating gate
        if keywords and any(kw in business_name for kw in keywords):
            min_r  = profile.get("min_reviews", 0)
            min_rt = profile.get("min_rating", 0)
            if review_count >= min_r and rating >= min_rt:
                return 5
            return 3  # keyword match but below threshold

    return live_campaign_bonus
