"""
BMS LeadFlow — Scoring Engine
Week 5

Scores each company 0–100 using three categories from the spec:

  ICP Fit      (max 40 pts)  — how well the company matches the target profile
  Reachability (max 30 pts)  — verified email + named contact (Week 7)
  Opportunity  (max 30 pts)  — how many website problems BMS can fix

Outreach threshold: score >= 60 → company enters the outreach queue.

Week 5 implements ICP Fit (partial) and Opportunity (full).
Reachability scoring (30 pts) is added in Week 7 when verified emails arrive.
"""


def calculate_score(company: dict, audit: dict | None = None, icp_profiles: list = None) -> tuple[int, dict]:
    """
    Calculate the total score for a company.

    Args:
        company: company row from Supabase
        audit:   website_audit row (or None if not yet audited)

    Returns:
        (total_score, breakdown_dict)
    """
    breakdown = {
        "icp_fit":      0,
        "reachability": 0,
        "opportunity":  0,
        "total":        0,
        "threshold_met": False,
    }

    breakdown["icp_fit"]      = _icp_fit_score(company)
    breakdown["reachability"] = _reachability_score(company)
    breakdown["opportunity"]  = _opportunity_score(audit)

    # ICP profile bonus (+5 pts if company matches an active profile)
    icp_matched_name = None
    if icp_profiles:
        from icp_profiles import icp_bonus_score, get_matching_profile
        bonus = icp_bonus_score(company, icp_profiles, audit=audit)
        icp_matched_name = get_matching_profile(company, icp_profiles, audit=audit)
        breakdown["icp_fit"] = min(breakdown["icp_fit"] + bonus, 40)

    breakdown["icp_match"] = icp_matched_name

    total = min(
        breakdown["icp_fit"] + breakdown["reachability"] + breakdown["opportunity"],
        100
    )
    breakdown["total"]         = total
    breakdown["threshold_met"] = total >= 60

    return total, breakdown


# ──────────────────────────────────────────────
# ICP Fit (max 40 pts)
# Full scoring uses SIC codes + region matching (Week 6 with ICP profiles)
# Week 5: score based on what we know from discovery
# ──────────────────────────────────────────────

def _icp_fit_score(company: dict) -> int:
    score = 0

    # Confirmed incorporated entity (Ltd/LLP/PLC) — PECR compliant  (15 pts)
    if company.get("ch_matched"):
        score += 15

    # Company is actively trading (10 pts)
    if company.get("company_status") == "active":
        score += 10

    # Has a website — has digital presence we can improve (5 pts)
    if company.get("has_website"):
        score += 5

    # Has Google reviews — actively trading, real business (5 pts)
    review_count = company.get("review_count") or 0
    if review_count >= 10:
        score += 5
    elif review_count >= 1:
        score += 2

    # Remaining 5 pts come from SIC sector matching (Week 6 with ICP profiles)

    return min(score, 40)


# ──────────────────────────────────────────────
# Reachability (max 30 pts)
# Added in Week 7 when verified emails + named contacts arrive
# ──────────────────────────────────────────────

def _reachability_score(company: dict) -> int:
    score = 0

    # Verified email address found (20 pts) — Week 7
    if company.get("email_verified"):
        score += 20

    # Named decision-maker found (10 pts)
    if company.get("contact_full_name") or company.get("contact_first_name"):
        score += 10

    return min(score, 30)


# ──────────────────────────────────────────────
# Opportunity (max 30 pts)
# Score HIGHER when the website has problems BMS can fix.
# This is the key insight: a broken website = a warm lead for web design + SEO.
# ──────────────────────────────────────────────

def _opportunity_score(audit: dict | None) -> int:
    if not audit:
        return 0     # can't score without an audit

    if not audit.get("resolves"):
        return 5     # site is completely down — extreme opportunity

    score = 0

    # Desktop performance (max 12 pts)
    perf = audit.get("performance_score")
    if perf is not None:
        if perf < 30:    score += 12   # very poor — urgent fix needed
        elif perf < 50:  score += 10
        elif perf < 70:  score += 7
        elif perf < 90:  score += 4
        # 90+ is fine — no opportunity there

    # Mobile performance (max 10 pts)
    mob = audit.get("mobile_score")
    if mob is not None:
        if mob < 30:     score += 10
        elif mob < 50:   score += 8
        elif mob < 70:   score += 5
        elif mob < 90:   score += 2

    # No SSL (5 pts) — easy fix, clear value
    if not audit.get("https"):
        score += 5

    # Not mobile friendly (3 pts)
    if not audit.get("has_viewport"):
        score += 3

    # Missing SEO basics (up to 5 pts total)
    if not audit.get("has_title"):
        score += 3
    if not audit.get("has_meta_description"):
        score += 2

    return min(score, 30)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def score_label(score: int) -> str:
    """Human-readable label for a score."""
    if score >= 80: return "Hot"
    if score >= 60: return "Warm"
    if score >= 40: return "Cool"
    return "Cold"


def is_outreach_ready(score: int) -> bool:
    """Returns True if the company meets the outreach threshold (>=60)."""
    return score >= 60
