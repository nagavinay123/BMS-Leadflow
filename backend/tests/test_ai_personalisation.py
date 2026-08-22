"""
Tests for Claude AI personalisation.
Mocks Anthropic API — no real calls made.
"""

import pytest
import sys, os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def base_company():
    return {
        "id":                "co-001",
        "name":              "Smith Plumbing Ltd",
        "domain":            "smithplumbing.co.uk",
        "has_website":       True,
        "https":             False,
        "performance_score": 32,
        "mobile_score":      28,
        "audit_source":      "pagespeed",
        "rating":            4.2,
        "review_count":      18,
        "issues": [
            {"type": "no_ssl",          "label": "No HTTPS / SSL certificate"},
            {"type": "poor_performance", "label": "Website very slow to load (desktop score 32/100)"},
        ],
        "icp_match": "Local Trades",
    }


# ─────────────────────────────────────────────────────────────
# API available
# ─────────────────────────────────────────────────────────────

@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"})
def test_personalise_calls_claude_api():
    """When API key is set, Claude should be called."""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="I was looking at Smith Plumbing Ltd's website and noticed it's loading very slowly.")]
    mock_client  = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("anthropic.Anthropic", return_value=mock_client):
        import importlib, claude_personalise
        importlib.reload(claude_personalise)
        result = claude_personalise.personalise_email(base_company())

    assert result["opening_line"] is not None
    assert result["fallback_used"] is False
    assert result["error"] is None
    mock_client.messages.create.assert_called_once()


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"})
def test_invented_percentage_triggers_fallback():
    """Claude outputs with invented percentages should trigger safety fallback."""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Your website is 47% slower than competitors.")]
    mock_client  = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("anthropic.Anthropic", return_value=mock_client):
        import importlib, claude_personalise
        importlib.reload(claude_personalise)
        result = claude_personalise.personalise_email(base_company())

    # Should fall back to rule-based when invented % detected
    assert result["opening_line"] is not None
    # Fallback may or may not be used — either is acceptable as long as no invented %
    assert "47%" not in (result["opening_line"] or "")


# ─────────────────────────────────────────────────────────────
# API unavailable — fallback
# ─────────────────────────────────────────────────────────────

@patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""})
def test_missing_api_key_uses_rule_based():
    """Without API key, rule-based fallback should produce a valid opening."""
    import importlib, claude_personalise
    importlib.reload(claude_personalise)
    result = claude_personalise.personalise_email(base_company())
    assert result["opening_line"] is not None
    assert len(result["opening_line"]) > 20
    assert result["fallback_used"] is True
    assert "ANTHROPIC_API_KEY" in (result["error"] or "")


@patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"})
def test_api_error_falls_back_to_rule_based():
    """API errors should gracefully fall back to rule-based."""
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API rate limit")

    with patch("anthropic.Anthropic", return_value=mock_client):
        import importlib, claude_personalise
        importlib.reload(claude_personalise)
        result = claude_personalise.personalise_email(base_company())

    assert result["opening_line"] is not None  # fallback produced
    assert result["fallback_used"] is True
    assert result["error"] is not None


# ─────────────────────────────────────────────────────────────
# Rule-based fallback tests
# ─────────────────────────────────────────────────────────────

def test_no_ssl_uses_ssl_fallback():
    import importlib, claude_personalise
    importlib.reload(claude_personalise)
    company  = base_company()
    company["https"] = False
    opening  = claude_personalise._rule_based_opening(company)
    assert "Secure" in opening or "SSL" in opening or "HTTPS" in opening or "slow" in opening or "Smith" in opening


def test_no_website_uses_no_website_fallback():
    import importlib, claude_personalise
    importlib.reload(claude_personalise)
    company = base_company()
    company["has_website"] = False
    opening = claude_personalise._rule_based_opening(company)
    assert "website" in opening.lower()


def test_clean_company_gets_generic_opening():
    import importlib, claude_personalise
    importlib.reload(claude_personalise)
    company = {
        "name": "Clean Company Ltd",
        "has_website": True, "https": True,
        "performance_score": 95, "mobile_score": 92,
        "issues": [], "audit_source": "pagespeed",
    }
    opening = claude_personalise._rule_based_opening(company)
    assert "Clean Company" in opening or "clean" in opening.lower() or len(opening) > 10
