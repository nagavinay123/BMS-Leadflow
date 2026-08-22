"""
BMS LeadFlow — Compliance engine
PECR / UK GDPR compliance gates checked before every send.

Every gate must pass before an email is sent.
If any gate fails, the send is blocked and the reason is logged.

IMPORTANT: LIA and Privacy Notice are business/legal documents that must be
supplied by James / BMS legal team. This module checks for their existence
but does NOT generate or approve them automatically.
"""

import os
import logging
from typing import Optional
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# UK sending time gate (Mon–Fri 09:00–17:00 UK time)
# ─────────────────────────────────────────────────────────────

def is_within_uk_sending_hours() -> tuple[bool, str]:
    """
    Returns (allowed: bool, reason: str).
    Sending only allowed Mon–Fri 09:00–17:00 UK time (GMT/BST).
    """
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        # Python < 3.9 fallback
        try:
            from backports.zoneinfo import ZoneInfo
        except ImportError:
            # Can't check timezone — allow but warn
            logger.warning("zoneinfo not available — sending time check skipped")
            return True, "timezone check unavailable"

    uk_tz = ZoneInfo("Europe/London")
    now_uk = datetime.now(tz=uk_tz)

    if now_uk.weekday() >= 5:  # Saturday=5, Sunday=6
        return False, f"Weekend sending blocked (UK time: {now_uk.strftime('%A %H:%M')})"

    hour = now_uk.hour
    if hour < 9 or hour >= 17:
        return False, f"Outside sending hours 09:00–17:00 UK (current: {now_uk.strftime('%H:%M')})"

    return True, "ok"


# ─────────────────────────────────────────────────────────────
# Pre-send compliance gate
# ─────────────────────────────────────────────────────────────

class ComplianceError(Exception):
    """Raised when a compliance gate fails — blocks the send."""


def check_pre_send_compliance(
    company:        dict,
    contact:        dict,
    campaign:       dict,
    daily_sent:     int,
    dry_run:        bool = True,
) -> dict:
    """
    Run all compliance gates before sending an email.

    Args:
        company:    companies row dict
        contact:    contacts row dict
        campaign:   campaigns row dict
        daily_sent: number of emails already sent today from this inbox
        dry_run:    if True, time/hour checks are skipped (safe for testing)

    Returns:
        {"passed": True, "checks": [...]}

    Raises:
        ComplianceError with reason if any gate fails.
    """
    from database import is_suppressed

    checks  = []
    email   = contact.get("email") or company.get("contact_email")

    def gate(name: str, passed: bool, reason: str = ""):
        checks.append({"gate": name, "passed": passed, "reason": reason})
        if not passed:
            raise ComplianceError(f"[{name}] {reason}")

    # 1. Company eligible (active, incorporated, not dissolved)
    gate(
        "company_eligible",
        company.get("ch_matched", False) and company.get("company_status", "") == "active",
        "Company is not an active incorporated entity — PECR requires ltd/llp/plc only",
    )

    # 2. Contact exists
    gate("contact_exists", bool(email), "No contact email address")

    # 3. Email verified (must be good or catch_all per MillionVerifier)
    email_status = contact.get("email_status", "unverified")
    gate(
        "email_verified",
        email_status in ("good", "catch_all"),
        f"Email status '{email_status}' — only good/catch_all permitted",
    )

    # 4. Suppression check (checked AGAIN at send time, not just at discovery)
    gate(
        "not_suppressed",
        not is_suppressed(
            email          = email,
            domain         = company.get("domain"),
            company_number = company.get("company_number"),
        ),
        f"Email/domain/company is on the suppression list",
    )

    # 5. Campaign is active
    gate(
        "campaign_active",
        campaign.get("status") == "active",
        f"Campaign status is '{campaign.get('status')}' — must be 'active'",
    )

    # 6. Daily sending limit
    daily_limit = campaign.get("daily_limit", 25)
    gate(
        "daily_limit",
        daily_sent < daily_limit,
        f"Daily limit reached: {daily_sent}/{daily_limit} emails sent today",
    )

    # 7. Sending time (skip in dry-run)
    if not dry_run:
        time_ok, time_reason = is_within_uk_sending_hours()
        gate("sending_time", time_ok, time_reason)

    # 8. Score threshold
    gate(
        "score_threshold",
        (company.get("score", 0) or 0) >= 60,
        f"Score {company.get('score', 0)} is below threshold of 60",
    )

    return {"passed": True, "checks": checks}


# ─────────────────────────────────────────────────────────────
# Email footer builder (PECR-compliant)
# ─────────────────────────────────────────────────────────────

BMS_COMPANY_NAME    = "BeMySocial Ltd"
BMS_COMPANY_NUMBER  = os.getenv("BMS_COMPANY_NUMBER",  "")
BMS_REGISTERED_ADDR = os.getenv("BMS_REGISTERED_ADDRESS", "")
BMS_WEBSITE         = "https://bemysocial.co.uk"
UNSUBSCRIBE_URL     = os.getenv("UNSUBSCRIBE_URL", f"{BMS_WEBSITE}/unsubscribe")


def build_email_footer(recipient_email: str, reason_for_contact: str = "") -> str:
    """
    Build a PECR-compliant email footer.
    Must include: company name, registered address, company number,
                  reason for contact, unsubscribe link.
    """
    reason = reason_for_contact or (
        "We are contacting you as we believe your business may benefit from our "
        "social media and digital marketing services. We identified your details "
        "from public sources under Legitimate Interests (PECR / UK GDPR)."
    )
    footer_parts = [
        "---",
        reason,
        "",
        f"To stop receiving emails, reply with 'Unsubscribe' or click: {UNSUBSCRIBE_URL}?email={recipient_email}",
        "",
        f"{BMS_COMPANY_NAME}",
    ]
    if BMS_REGISTERED_ADDR:
        footer_parts.append(BMS_REGISTERED_ADDR)
    if BMS_COMPANY_NUMBER:
        footer_parts.append(f"Company No. {BMS_COMPANY_NUMBER}")
    footer_parts.append(BMS_WEBSITE)
    return "\n".join(footer_parts)


def append_compliant_footer(body: str, recipient_email: str) -> str:
    """Append the compliance footer to an email body (strips any existing footer first)."""
    # Remove old footer if present
    if "\n---\n" in body:
        body = body[:body.index("\n---\n")]
    return body.rstrip() + "\n\n" + build_email_footer(recipient_email)
