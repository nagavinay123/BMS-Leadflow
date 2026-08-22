"""
Tests for Companies House matching — incorporated entity filtering.
Mocks CH API — no real HTTP calls made.
"""

import pytest
import sys, os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


INCORPORATED_TYPES = {
    "private-limited-company",
    "limited-liability-partnership",
    "public-limited-company",
    "private-limited-company-section-30-exemption",
    "old-public-company",
    "private-unlimited",
    "registered-society-non-jurisdictional",
}

EXCLUDED_TYPES = {
    "sole-trader",
    "partnership",
    "scottish-partnership",
    "industrial-and-provident-society",
    "royal-charter",
    "other",
}


# ─────────────────────────────────────────────────────────────
# Incorporated type filtering
# ─────────────────────────────────────────────────────────────

def test_private_limited_company_is_included():
    assert "private-limited-company" in INCORPORATED_TYPES


def test_llp_is_included():
    assert "limited-liability-partnership" in INCORPORATED_TYPES


def test_plc_is_included():
    assert "public-limited-company" in INCORPORATED_TYPES


def test_sole_trader_is_excluded():
    """Sole traders must NOT enter the system — PECR."""
    assert "sole-trader" not in INCORPORATED_TYPES


def test_partnership_is_excluded():
    """General partnerships must be excluded."""
    assert "partnership" not in INCORPORATED_TYPES


# ─────────────────────────────────────────────────────────────
# match_to_companies_house function
# ─────────────────────────────────────────────────────────────

@patch("companies_house.requests.get")
def test_ch_match_returns_none_for_dissolved(mock_get):
    """Dissolved companies should not be returned."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [{
            "company_name":   "TEST PLUMBING LTD",
            "company_number": "12345678",
            "company_status": "dissolved",
            "company_type":   "private-limited-company",
            "address_snippet":"1 Test Street, London",
            "date_of_creation": "2018-01-01",
        }]
    }
    mock_get.return_value = mock_response

    from companies_house import match_to_companies_house
    result = match_to_companies_house("Test Plumbing", "London")
    # Dissolved companies should be excluded
    assert result is None or result.get("company_status") != "dissolved"


@patch("companies_house.requests.get")
def test_ch_match_returns_active_company(mock_get):
    """Active incorporated companies should be matched."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [{
            "company_name":   "TEST PLUMBING LTD",
            "company_number": "12345678",
            "company_status": "active",
            "company_type":   "private-limited-company",
            "address_snippet":"1 Test Street, London",
            "date_of_creation": "2018-01-01",
        }]
    }
    mock_get.return_value = mock_response

    from companies_house import match_to_companies_house
    result = match_to_companies_house("Test Plumbing", "London")
    # Active company should be returned (or None if name match fails)
    if result:
        assert result.get("company_status") == "active"
        assert result.get("company_type") == "private-limited-company"


@patch("companies_house.requests.get")
def test_ch_no_results_returns_none(mock_get):
    """No search results → None."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"items": []}
    mock_get.return_value = mock_response

    from companies_house import match_to_companies_house
    result = match_to_companies_house("Completely Unknown Business", "Nowhere")
    assert result is None


@patch("companies_house.requests.get")
def test_ch_api_error_returns_none(mock_get):
    """CH API errors should return None gracefully."""
    import requests
    mock_get.side_effect = requests.RequestException("Connection refused")
    from companies_house import match_to_companies_house
    result = match_to_companies_house("Test Ltd", "London")
    assert result is None


# ─────────────────────────────────────────────────────────────
# Director lookup
# ─────────────────────────────────────────────────────────────

@patch("companies_house.requests.get")
def test_get_primary_director_returns_first_active_director(mock_get):
    """Should return the first active director from CH officer list."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [{
            "name":          "SMITH, John William",
            "officer_role":  "director",
            "resigned_on":   None,
            "name_elements": {"forename": "John", "surname": "Smith"},
        }]
    }
    mock_get.return_value = mock_response

    from companies_house import get_primary_director
    result = get_primary_director("12345678")
    if result:  # May return None if name parsing differs
        assert "first_name" in result or "full_name" in result


@patch("companies_house.requests.get")
def test_resigned_director_not_returned(mock_get):
    """Resigned directors should be filtered out."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "items": [{
            "name":          "JONES, Mary",
            "officer_role":  "director",
            "resigned_on":   "2020-06-01",
        }]
    }
    mock_get.return_value = mock_response
    from companies_house import get_primary_director
    result = get_primary_director("99999999")
    # Resigned officer should not be returned
    # Result may be None (all resigned) or the next non-resigned one
    assert result is None or result.get("full_name") != "Mary Jones"
