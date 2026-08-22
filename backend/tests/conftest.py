"""
Pytest configuration for BMS LeadFlow backend tests.
Sets safe environment variables so tests never call real APIs.
"""

import os
import pytest

# ── Safe defaults for all tests ───────────────────────────────
# These prevent any real API calls during tests.
os.environ.setdefault("SUPABASE_URL",              "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY",      "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test")
os.environ.setdefault("MILLION_VERIFIER_API_KEY",  "")   # Empty → fallback mode
os.environ.setdefault("ANTHROPIC_API_KEY",         "")   # Empty → fallback mode
os.environ.setdefault("HUNTER_API_KEY",            "")
os.environ.setdefault("SMARTLEAD_API_KEY",         "")
os.environ.setdefault("DRY_RUN",                   "true")
os.environ.setdefault("BMS_COMPANY_NUMBER",        "12345678")
os.environ.setdefault("BMS_REGISTERED_ADDRESS",    "1 Test St, London, EC1A 1BB")
os.environ.setdefault("GOOGLE_MAPS_API_KEY",       "")
os.environ.setdefault("APIFY_API_TOKEN",           "")
os.environ.setdefault("COMPANIES_HOUSE_API_KEY",   "test_key")
