"""
BMS LeadFlow — MillionVerifier email verification
Spec: only 'good' and 'catch_all' emails enter the outreach queue.
API docs: https://app.millionverifier.com/api/

Environment variable required:
  MILLION_VERIFIER_API_KEY  — get at https://app.millionverifier.com
"""

import os
import time
import logging
from typing import Optional
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

MILLION_VERIFIER_API_KEY = os.getenv("MILLION_VERIFIER_API_KEY", "")
MV_BASE_URL = "https://api.millionverifier.com/api/v3/"
MV_TIMEOUT  = 30  # seconds

# ─────────────────────────────────────────────────────────────
# Status mapping  (MillionVerifier result → our email_status)
# ─────────────────────────────────────────────────────────────
_STATUS_MAP = {
    "ok":          "good",
    "catch_all":   "catch_all",
    "unknown":     "unverified",
    "invalid":     "bad",
    "disposable":  "bad",
    "spamtrap":    "bad",
    "role":        "risky",     # role-based address e.g. info@, sales@
    "mailbox_full":"risky",
}

SENDABLE_STATUSES = {"good", "catch_all"}


def _api_available() -> bool:
    return bool(MILLION_VERIFIER_API_KEY)


def verify_email(email: str) -> dict:
    """
    Verify a single email address via MillionVerifier.

    Returns:
        {
          "email":        str,
          "email_status": "good" | "catch_all" | "unverified" | "bad" | "risky",
          "raw_result":   str,     # MillionVerifier's raw result string
          "quality":      int,     # 1-100 quality score (if provided)
          "is_role":      bool,
          "is_free":      bool,    # free email provider (gmail, hotmail etc)
          "can_send":     bool,    # True only for good / catch_all
          "error":        str | None,
        }
    """
    base = {
        "email":        email,
        "email_status": "unverified",
        "raw_result":   None,
        "quality":      0,
        "is_role":      False,
        "is_free":      False,
        "can_send":     False,
        "error":        None,
    }

    if not email:
        base["error"] = "No email provided"
        return base

    if not _api_available():
        base["error"] = (
            "MILLION_VERIFIER_API_KEY not set. "
            "Get your key at https://app.millionverifier.com"
        )
        logger.warning("MillionVerifier key missing — email unverified: %s", email)
        return base

    try:
        resp = requests.get(
            MV_BASE_URL,
            params={"api": MILLION_VERIFIER_API_KEY, "email": email},
            timeout=MV_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.Timeout:
        base["error"] = "MillionVerifier API timeout"
        logger.error("MillionVerifier timeout for %s", email)
        return base
    except Exception as exc:
        base["error"] = f"MillionVerifier API error: {exc}"
        logger.error("MillionVerifier error for %s: %s", email, exc)
        return base

    # MillionVerifier response fields
    raw_result   = data.get("result", "unknown")
    quality      = data.get("quality", 0) or 0
    is_role      = bool(data.get("role", False))
    is_free      = bool(data.get("free", False))

    email_status = _STATUS_MAP.get(raw_result, "unverified")

    return {
        "email":        email,
        "email_status": email_status,
        "raw_result":   raw_result,
        "quality":      quality,
        "is_role":      is_role,
        "is_free":      is_free,
        "can_send":     email_status in SENDABLE_STATUSES,
        "error":        None,
    }


def verify_batch(emails: list, delay_ms: int = 300) -> list:
    """
    Verify a list of emails sequentially with a configurable delay.

    Returns:
        List of verify_email() result dicts.
    """
    results = []
    for email in emails:
        result = verify_email(email)
        results.append(result)
        if delay_ms > 0:
            time.sleep(delay_ms / 1000)
    return results


def should_send(email_status: str) -> bool:
    """
    Returns True only if the email status permits sending.
    Only 'good' and 'catch_all' pass the gate.
    """
    return email_status in SENDABLE_STATUSES


def mv_available() -> bool:
    """Returns True if MillionVerifier API key is configured."""
    return _api_available()
