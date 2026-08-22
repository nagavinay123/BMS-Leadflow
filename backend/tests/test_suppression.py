"""
Tests for suppression logic.
Mocks Supabase — no real DB calls.
"""

import pytest
import sys, os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_supabase_mock(has_data=True):
    """Create a mock Supabase client that returns or doesn't return suppression data."""
    mock = MagicMock()
    execute_result = MagicMock()
    execute_result.data = [{"id": "suppress-1"}] if has_data else []
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value = execute_result
    return mock


@patch("database.supabase")
def test_is_suppressed_by_email(mock_db):
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"id": "s1"}]
    from database import is_suppressed
    assert is_suppressed(email="test@suppressed.co.uk") is True


@patch("database.supabase")
def test_not_suppressed(mock_db):
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    from database import is_suppressed
    assert is_suppressed(email="clean@company.co.uk") is False


@patch("database.supabase")
def test_is_suppressed_by_domain(mock_db):
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"id": "s1"}]
    from database import is_suppressed
    assert is_suppressed(domain="suppressed.co.uk") is True


@patch("database.supabase")
def test_no_args_returns_false(mock_db):
    from database import is_suppressed
    result = is_suppressed()
    assert result is False
    mock_db.table.assert_not_called()


@patch("database.supabase")
def test_is_suppressed_by_company_number(mock_db):
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"id": "s1"}]
    from database import is_suppressed
    assert is_suppressed(company_number="12345678") is True


# ── Compliance pre-send suppression ─────────────────────────

def test_compliance_blocks_suppressed_email():
    """Suppressed email must fail compliance gate at send time."""
    from compliance import check_pre_send_compliance, ComplianceError

    company  = {"ch_matched": True, "company_status": "active", "score": 75, "domain": "test.co.uk"}
    contact  = {"email": "suppressed@test.co.uk", "email_status": "good"}
    campaign = {"status": "active", "daily_limit": 25}

    with patch("database.supabase") as mock_db:
        # Make is_suppressed return True
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{"id": "s1"}]
        with pytest.raises(ComplianceError) as exc_info:
            check_pre_send_compliance(company, contact, campaign, daily_sent=0, dry_run=True)
        assert "suppression" in str(exc_info.value).lower()


def test_compliance_blocks_unverified_email():
    """Unverified email must fail compliance gate."""
    from compliance import check_pre_send_compliance, ComplianceError

    company  = {"ch_matched": True, "company_status": "active", "score": 75}
    contact  = {"email": "test@company.co.uk", "email_status": "unverified"}
    campaign = {"status": "active", "daily_limit": 25}

    with patch("database.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        with pytest.raises(ComplianceError) as exc_info:
            check_pre_send_compliance(company, contact, campaign, daily_sent=0, dry_run=True)
        assert "unverified" in str(exc_info.value).lower() or "status" in str(exc_info.value).lower()


def test_compliance_blocks_daily_limit_exceeded():
    """Sending beyond daily limit must be blocked."""
    from compliance import check_pre_send_compliance, ComplianceError

    company  = {"ch_matched": True, "company_status": "active", "score": 75}
    contact  = {"email": "test@company.co.uk", "email_status": "good"}
    campaign = {"status": "active", "daily_limit": 25}

    with patch("database.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        with pytest.raises(ComplianceError) as exc_info:
            check_pre_send_compliance(company, contact, campaign, daily_sent=25, dry_run=True)
        assert "limit" in str(exc_info.value).lower()


def test_compliance_passes_clean_record():
    """A clean, verified, active company/contact should pass all gates."""
    from compliance import check_pre_send_compliance

    company  = {"ch_matched": True, "company_status": "active", "score": 75, "domain": "clean.co.uk"}
    contact  = {"email": "john@clean.co.uk", "email_status": "good"}
    campaign = {"status": "active", "daily_limit": 25}

    with patch("database.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        result = check_pre_send_compliance(company, contact, campaign, daily_sent=10, dry_run=True)
        assert result["passed"] is True


def test_compliance_blocks_paused_campaign():
    from compliance import check_pre_send_compliance, ComplianceError
    company  = {"ch_matched": True, "company_status": "active", "score": 75}
    contact  = {"email": "j@co.uk", "email_status": "good"}
    campaign = {"status": "paused", "daily_limit": 25}

    with patch("database.supabase") as mock_db:
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        with pytest.raises(ComplianceError) as exc_info:
            check_pre_send_compliance(company, contact, campaign, daily_sent=0, dry_run=True)
        assert "active" in str(exc_info.value).lower() or "paused" in str(exc_info.value).lower()
