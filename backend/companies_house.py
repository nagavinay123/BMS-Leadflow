"""
BMS LeadFlow — Companies House API integration
Owner: Arkana (Week 4)

Matches a Google Maps business to a Companies House record.
Only incorporated entities (Ltd, LLP, PLC) pass through — compliance rule.
Sole traders and partnerships are filtered out (PECR requirement).
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY  = os.getenv("COMPANIES_HOUSE_API_KEY")
BASE_URL = "https://api.company-information.service.gov.uk"

# 600 requests per 5 minutes = 2/sec. We use 0.5s delay → safe.
REQUEST_DELAY = 0.5

# Only these company types are incorporated entities (PECR compliant)
INCORPORATED_TYPES = {
    "ltd",
    "llp",
    "plc",
    "private-limited-guarant-nsc",
    "private-limited-guarant-nsc-limited-exemption",
    "private-unlimited",
    "private-unlimited-nsc",
    "old-public-company",
    "royal-charter",
    "investment-company-with-variable-capital",
}


# ──────────────────────────────────────────────
# Raw API calls
# ──────────────────────────────────────────────

def _search_companies(name: str, items_per_page: int = 5) -> list:
    """
    Search Companies House by name.
    Returns up to items_per_page candidate company records.
    Rate limit: 600 req / 5 min.
    Docs: https://developer-specs.company-information.service.gov.uk/
    """
    if not API_KEY:
        # CH matching is non-fatal — just log and skip
        return []

    params = {"q": name, "items_per_page": items_per_page}
    r = requests.get(
        f"{BASE_URL}/search/companies",
        params=params,
        auth=(API_KEY, ""),
        timeout=10,
    )
    r.raise_for_status()
    time.sleep(REQUEST_DELAY)
    return r.json().get("items", [])


def _get_company(company_number: str) -> dict:
    """Fetch full company profile by company number."""
    r = requests.get(
        f"{BASE_URL}/company/{company_number}",
        auth=(API_KEY, ""),
        timeout=10,
    )
    if r.status_code == 404:
        return {}
    r.raise_for_status()
    time.sleep(REQUEST_DELAY)
    return r.json()


# ──────────────────────────────────────────────
# Public matching function
# ──────────────────────────────────────────────

def match_to_companies_house(business_name: str, town: str) -> dict | None:
    """
    Search Companies House for business_name and return the best match.

    Matching rules (all must pass):
    1. Company status must be 'active'
    2. Company type must be incorporated (Ltd, LLP, PLC) — PECR compliance
    3. Town must appear somewhere in the registered address

    Returns a dict with Companies House data, or None if no suitable match.
    """
    if not API_KEY:
        return None  # CH matching disabled — no API key configured

    try:
        candidates = _search_companies(business_name)
    except requests.RequestException:
        return None

    for candidate in candidates:
        # ── Rule 1: Active only ─────────────────────────────
        if candidate.get("company_status") != "active":
            continue

        # ── Rule 2: Incorporated entities only (PECR) ──────
        company_type = candidate.get("company_type", "").lower()
        if company_type not in INCORPORATED_TYPES:
            continue

        # ── Rule 3: Town appears in address ─────────────────
        address = (candidate.get("address_snippet") or "").lower()
        if town.lower() not in address:
            continue

        # Match found
        return {
            "company_number":     candidate.get("company_number", ""),
            "registered_name":    candidate.get("title", ""),
            "registered_address": candidate.get("address_snippet", ""),
            "incorporation_date": candidate.get("date_of_creation"),
            "company_status":     candidate.get("company_status", ""),
            "company_type":       candidate.get("company_type", ""),
            "sic_codes":          candidate.get("sic_codes", []),
        }

    return None


def is_incorporated(company_type: str) -> bool:
    """Check if a company type is an incorporated entity."""
    return company_type.lower() in INCORPORATED_TYPES


# ──────────────────────────────────────────────
# Officers (directors / owners)
# ──────────────────────────────────────────────

def get_officers(company_number: str) -> list:
    """
    Fetch active officers (directors) for a company from Companies House.

    Returns a list of dicts:
      {first_name, last_name, full_name, role, appointed_on}

    Companies House stores names as "SURNAME, Firstname Middlename" —
    we parse and flip them into a usable format.

    Rate limit: shares the same 600 req/5 min budget as matching.
    """
    if not API_KEY or not company_number:
        return []

    try:
        r = requests.get(
            f"{BASE_URL}/company/{company_number}/officers",
            params={"items_per_page": 10},
            auth=(API_KEY, ""),
            timeout=10,
        )
        time.sleep(REQUEST_DELAY)

        if r.status_code == 404:
            return []
        r.raise_for_status()

        items = r.json().get("items", [])
        officers = []

        for item in items:
            # Skip resigned officers
            if item.get("resigned_on"):
                continue

            raw_name = item.get("name", "")
            first, last = _parse_ch_name(raw_name)

            officers.append({
                "first_name":   first,
                "last_name":    last,
                "full_name":    f"{first} {last}".strip() or raw_name,
                "role":         item.get("officer_role", ""),
                "appointed_on": item.get("appointed_on", ""),
            })

        return officers

    except requests.RequestException:
        return []


def get_primary_director(company_number: str) -> dict | None:
    """
    Returns the first active director (most likely the owner/decision-maker).
    Returns None if no officers found.
    """
    officers = get_officers(company_number)
    # Prefer director role; fall back to first officer
    directors = [o for o in officers if "director" in o.get("role", "").lower()]
    return directors[0] if directors else (officers[0] if officers else None)


def _parse_ch_name(raw: str) -> tuple[str, str]:
    """
    Companies House stores names as: "SMITH, John William"
    Parse into (first_name="John", last_name="Smith")
    """
    raw = raw.strip()
    if "," in raw:
        parts     = raw.split(",", 1)
        last_name  = parts[0].strip().title()
        first_part = parts[1].strip()
        # First word of the remainder is the first name
        first_name = first_part.split()[0].title() if first_part else ""
    else:
        # No comma — just split by space
        words      = raw.split()
        first_name = words[0].title() if words else ""
        last_name  = " ".join(words[1:]).title() if len(words) > 1 else ""

    return first_name, last_name
