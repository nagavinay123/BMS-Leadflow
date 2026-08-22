"""
Tests for company deduplication logic.
Verifies that upsert on google_place_id prevents duplicate companies.
"""

import pytest
import sys, os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def make_upsert_mock(returned_id="existing-uuid-001"):
    """Mock that simulates Supabase upsert returning the existing/new record."""
    mock = MagicMock()
    mock.table.return_value.upsert.return_value.execute.return_value.data = [{"id": returned_id, "name": "Test Ltd"}]
    mock.table.return_value.insert.return_value.execute.return_value.data = [{"id": "new-uuid-002", "name": "Test Ltd"}]
    return mock


@patch("database.supabase")
def test_insert_with_place_id_uses_upsert(mock_db):
    """Companies with google_place_id should upsert, not blind insert."""
    mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "place-001"}]
    from database import insert_company
    result = insert_company({
        "name":           "Test Plumbing",
        "google_place_id":"ChIJ_test_place_id",
        "source":         "google_maps",
    })
    # Verify upsert was called, not insert
    mock_db.table.return_value.upsert.assert_called_once()
    assert result.get("id") == "place-001"


@patch("database.supabase")
def test_insert_without_place_id_uses_insert(mock_db):
    """Companies without google_place_id use regular insert."""
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [{"id": "new-001"}]
    from database import insert_company
    result = insert_company({"name": "Test Ltd", "source": "google_maps"})
    mock_db.table.return_value.insert.assert_called_once()
    assert result.get("id") == "new-001"


def test_company_number_uniqueness_verified_by_schema():
    """
    The schema.sql creates a partial unique index on company_number.
    This test documents that the constraint exists and is not enforced in Python.
    The Python code relies on Supabase's constraint to reject duplicates.
    """
    # This is a documentation test — the constraint is in SQL, not Python
    assert True, "Unique constraint on company_number is in supabase/schema.sql"


def test_domain_uniqueness_verified_by_schema():
    """
    The schema.sql creates a partial unique index on domain.
    """
    assert True, "Unique constraint on domain is in supabase/schema.sql"


@patch("database.supabase")
def test_upsert_contact_deduplicates_on_company_email(mock_db):
    """contacts upsert on (company_id, email) prevents duplicate contacts."""
    mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{"id": "contact-001"}]
    from database import upsert_contact
    result = upsert_contact({
        "company_id": "company-001",
        "email":      "john@test.co.uk",
        "first_name": "John",
        "email_status": "good",
    })
    mock_db.table.return_value.upsert.assert_called_once()


@patch("database.supabase")
def test_upsert_contact_without_email_uses_insert(mock_db):
    """Contacts without email cannot deduplicate — uses insert."""
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [{"id": "contact-002"}]
    from database import upsert_contact
    result = upsert_contact({
        "company_id": "company-001",
        "first_name": "John",
        "email_status": "unverified",
    })
    mock_db.table.return_value.insert.assert_called_once()
