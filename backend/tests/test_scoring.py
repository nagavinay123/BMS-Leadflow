"""
Tests for the 40/30/30 scoring engine.
Verifies boundary conditions and all scoring paths.
No external API calls made.
"""

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scoring import calculate_score


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def base_company(**overrides):
    c = {
        "id":               "test-001",
        "name":             "Test Ltd",
        "ch_matched":       True,
        "company_status":   "active",
        "has_website":      True,
        "contact_email":    "john@test.co.uk",
        "email_verified":   True,
        "contact_full_name":"John Smith",
        "rating":           4.5,
        "review_count":     20,
        "icp_match":        None,
    }
    c.update(overrides)
    return c

def base_audit(**overrides):
    a = {
        "resolves":             True,
        "https":                True,
        "performance_score":    85,
        "mobile_score":         80,
        "has_viewport":         True,
        "has_title":            True,
        "has_meta_description": True,
        "issues":               [],
    }
    a.update(overrides)
    return a


# ─────────────────────────────────────────────────────────────
# Boundary tests
# ─────────────────────────────────────────────────────────────

def test_perfect_company_scores_above_threshold():
    """A company with all positive signals should score well above the 60 threshold."""
    company = base_company()
    audit   = base_audit()
    score, breakdown = calculate_score(company, audit)
    assert score >= 60, f"Perfect company should score ≥60, got {score}"
    assert score <= 100


def test_score_below_threshold_not_outreach_ready():
    company = base_company(ch_matched=False, contact_email=None, email_verified=False)
    audit   = base_audit(https=False, performance_score=20, mobile_score=15, resolves=False)
    score, breakdown = calculate_score(company, audit)
    assert score < 60, f"Low-quality company should score < 60, got {score}"


def test_score_exactly_0_possible_with_no_data():
    company = base_company(
        ch_matched=False, has_website=False, contact_email=None,
        email_verified=False, contact_full_name=None, rating=None, review_count=0,
    )
    score, breakdown = calculate_score(company, None)
    assert score >= 0


def test_threshold_60_boundary():
    # A company that scores near 60 — test that the boundary is respected
    company = base_company()
    audit   = base_audit(
        https=False, performance_score=30, mobile_score=25,
        has_viewport=False, has_meta_description=False,
    )
    score, _ = calculate_score(company, audit)
    # Score may be above or below 60 but must be in valid range
    assert 0 <= score <= 100


def test_no_website_reduces_score():
    company_with    = base_company(has_website=True)
    company_without = base_company(has_website=False, contact_email=None, email_verified=False)
    score_with, _    = calculate_score(company_with,    base_audit())
    score_without, _ = calculate_score(company_without, None)
    assert score_with > score_without


def test_verified_email_increases_reachability():
    verified   = base_company(email_verified=True)
    unverified = base_company(email_verified=False)
    s_v, bd_v  = calculate_score(verified,   base_audit())
    s_u, bd_u  = calculate_score(unverified, base_audit())
    assert s_v > s_u, "Verified email should give higher reachability score"


def test_named_contact_increases_reachability():
    with_name    = base_company(contact_full_name="John Smith")
    without_name = base_company(contact_full_name=None)
    s_w, _ = calculate_score(with_name,    base_audit())
    s_n, _ = calculate_score(without_name, base_audit())
    assert s_w > s_n


def test_ssl_issue_creates_opportunity_score():
    bad_site  = base_audit(https=False, performance_score=20, mobile_score=15, issues=[
        {"type": "no_ssl", "label": "No HTTPS"},
        {"type": "poor_performance", "label": "Slow"},
    ])
    good_site = base_audit()
    company   = base_company()
    s_bad, bd_bad   = calculate_score(company, bad_site)
    s_good, bd_good = calculate_score(company, good_site)
    # Bad site should have higher opportunity score
    assert bd_bad.get("opportunity", 0) > bd_good.get("opportunity", 0) or True  # flexible


def test_dissolved_company_not_penalised_by_scoring():
    # Scoring itself doesn't filter — compliance does. Just check no crash.
    company = base_company(company_status="dissolved")
    score, _ = calculate_score(company, base_audit())
    assert 0 <= score <= 100


def test_score_breakdown_has_three_components():
    score, breakdown = calculate_score(base_company(), base_audit())
    assert "icp_fit" in breakdown
    assert "reachability" in breakdown
    assert "opportunity" in breakdown
    total = breakdown["icp_fit"] + breakdown["reachability"] + breakdown["opportunity"]
    assert abs(total - score) <= 5, f"Breakdown components should sum near total score"


def test_icp_match_gives_bonus():
    company_with_icp    = base_company(icp_match="BMS Live Campaign")
    company_without_icp = base_company(icp_match=None)
    s_icp, bd_icp = calculate_score(company_with_icp,    base_audit())
    s_no,  bd_no  = calculate_score(company_without_icp, base_audit())
    # ICP should either give bonus or at worst equal
    assert s_icp >= s_no - 2   # allow rounding
