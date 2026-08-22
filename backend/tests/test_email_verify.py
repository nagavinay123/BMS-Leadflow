"""
Tests for MillionVerifier email verification.
All API calls are mocked — no real HTTP requests made.
"""

import pytest
import sys, os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def make_mv_response(result, quality=90, role=False, free=False):
    m = MagicMock()
    m.json.return_value = {"result": result, "quality": quality, "role": role, "free": free}
    m.raise_for_status.return_value = None
    return m


# ─────────────────────────────────────────────────────────────
# Status mapping tests
# ─────────────────────────────────────────────────────────────

@patch.dict(os.environ, {"MILLION_VERIFIER_API_KEY": "test_key"})
@patch("requests.get")
def test_ok_maps_to_good(mock_get):
    mock_get.return_value = make_mv_response("ok")
    from email_verify import verify_email
    result = verify_email("test@example.co.uk")
    assert result["email_status"] == "good"
    assert result["can_send"] is True
    assert result["error"] is None


@patch.dict(os.environ, {"MILLION_VERIFIER_API_KEY": "test_key"})
@patch("requests.get")
def test_catch_all_maps_to_catch_all(mock_get):
    mock_get.return_value = make_mv_response("catch_all")
    from email_verify import verify_email
    result = verify_email("sales@company.co.uk")
    assert result["email_status"] == "catch_all"
    assert result["can_send"] is True


@patch.dict(os.environ, {"MILLION_VERIFIER_API_KEY": "test_key"})
@patch("requests.get")
def test_invalid_maps_to_bad(mock_get):
    mock_get.return_value = make_mv_response("invalid")
    from email_verify import verify_email
    result = verify_email("notreal@fake.xyz")
    assert result["email_status"] == "bad"
    assert result["can_send"] is False


@patch.dict(os.environ, {"MILLION_VERIFIER_API_KEY": "test_key"})
@patch("requests.get")
def test_disposable_maps_to_bad(mock_get):
    mock_get.return_value = make_mv_response("disposable")
    from email_verify import verify_email
    result = verify_email("temp@guerrillamail.com")
    assert result["email_status"] == "bad"
    assert result["can_send"] is False


@patch.dict(os.environ, {"MILLION_VERIFIER_API_KEY": "test_key"})
@patch("requests.get")
def test_spamtrap_maps_to_bad(mock_get):
    mock_get.return_value = make_mv_response("spamtrap")
    from email_verify import verify_email
    result = verify_email("spam@trap.com")
    assert result["email_status"] == "bad"
    assert result["can_send"] is False


@patch.dict(os.environ, {"MILLION_VERIFIER_API_KEY": "test_key"})
@patch("requests.get")
def test_unknown_maps_to_unverified(mock_get):
    mock_get.return_value = make_mv_response("unknown")
    from email_verify import verify_email
    result = verify_email("maybe@somewhere.co.uk")
    assert result["email_status"] == "unverified"
    assert result["can_send"] is False


# ─────────────────────────────────────────────────────────────
# API key missing
# ─────────────────────────────────────────────────────────────

@patch.dict(os.environ, {"MILLION_VERIFIER_API_KEY": ""})
def test_missing_api_key_returns_unverified():
    # Must reimport to pick up patched env
    import importlib, email_verify
    importlib.reload(email_verify)
    result = email_verify.verify_email("test@example.co.uk")
    assert result["email_status"] == "unverified"
    assert result["error"] is not None
    assert "MILLION_VERIFIER_API_KEY" in result["error"]


# ─────────────────────────────────────────────────────────────
# API errors
# ─────────────────────────────────────────────────────────────

@patch.dict(os.environ, {"MILLION_VERIFIER_API_KEY": "test_key"})
@patch("requests.get")
def test_api_timeout_returns_error(mock_get):
    import requests as req
    import importlib, email_verify
    importlib.reload(email_verify)
    mock_get.side_effect = req.Timeout("Timeout")
    result = email_verify.verify_email("test@example.co.uk")
    assert result["email_status"] == "unverified"
    assert result["error"] is not None
    assert "timeout" in result["error"].lower() or "Timeout" in result["error"]


@patch.dict(os.environ, {"MILLION_VERIFIER_API_KEY": "test_key"})
@patch("requests.get")
def test_api_error_returns_error(mock_get):
    mock_get.side_effect = Exception("Connection error")
    from email_verify import verify_email
    result = verify_email("test@example.co.uk")
    assert result["email_status"] == "unverified"
    assert result["error"] is not None


# ─────────────────────────────────────────────────────────────
# should_send gate
# ─────────────────────────────────────────────────────────────

def test_should_send_good():
    from email_verify import should_send
    assert should_send("good") is True

def test_should_send_catch_all():
    from email_verify import should_send
    assert should_send("catch_all") is True

def test_should_not_send_unverified():
    from email_verify import should_send
    assert should_send("unverified") is False

def test_should_not_send_bad():
    from email_verify import should_send
    assert should_send("bad") is False

def test_should_not_send_risky():
    from email_verify import should_send
    assert should_send("risky") is False


# ─────────────────────────────────────────────────────────────
# Batch verify
# ─────────────────────────────────────────────────────────────

@patch.dict(os.environ, {"MILLION_VERIFIER_API_KEY": "test_key"})
@patch("requests.get")
def test_batch_verify_returns_list(mock_get):
    import importlib, email_verify
    importlib.reload(email_verify)
    mock_get.return_value = make_mv_response("ok")
    results = email_verify.verify_batch(["a@test.co.uk", "b@test.co.uk", "c@test.co.uk"], delay_ms=0)
    assert len(results) == 3
    assert all(r["email_status"] == "good" for r in results)


@patch.dict(os.environ, {"MILLION_VERIFIER_API_KEY": "test_key"})
@patch("requests.get")
def test_empty_email_returns_error(mock_get):
    from email_verify import verify_email
    result = verify_email("")
    assert result["error"] is not None
    mock_get.assert_not_called()
