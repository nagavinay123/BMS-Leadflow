"""
BMS LeadFlow — Abstract email provider interface
All email sending goes through this abstraction layer.
Concrete implementations: smartlead_provider.py

Environment:
  DRY_RUN=true   → no real emails sent (default for development)
  EMAIL_PROVIDER  → 'smartlead' | 'instantly' | 'smtp' (default: smartlead)
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"


class EmailProvider(ABC):
    """Abstract base class for email sending providers."""

    @abstractmethod
    def send_email(
        self,
        to_email:     str,
        to_name:      Optional[str],
        subject:      str,
        body:         str,
        from_name:    str,
        from_email:   str,
        reply_to:     Optional[str] = None,
        campaign_id:  Optional[str] = None,
        thread_id:    Optional[str] = None,
    ) -> dict:
        """
        Send a single email.
        Returns: {"success": bool, "message_id": str, "error": str|None}
        """

    @abstractmethod
    def cancel_sequence(self, thread_id: str) -> dict:
        """Cancel all pending emails in a sequence/thread."""

    @abstractmethod
    def get_campaign_stats(self, provider_campaign_id: str) -> dict:
        """Fetch aggregate stats from the provider."""

    @abstractmethod
    def process_webhook(self, payload: dict) -> dict:
        """
        Parse a webhook payload from this provider.
        Returns normalised event dict:
          {
            "event_type":        "sent"|"open"|"click"|"reply"|"bounce"|"unsubscribe",
            "email":             str,
            "provider_event_id": str,
            "occurred_at":       str,   # ISO timestamp
            "metadata":          dict,
          }
        """


class DryRunProvider(EmailProvider):
    """
    Safe no-op provider for development and testing.
    Logs every call but does NOT contact any external service.
    Always activated when DRY_RUN=true.
    """

    def send_email(self, to_email, to_name, subject, body, from_name,
                   from_email, reply_to=None, campaign_id=None, thread_id=None):
        logger.info(
            "[DRY RUN] Would send email to %s | subject: %s | from: %s <%s>",
            to_email, subject, from_name, from_email
        )
        print(f"  [DRY RUN] 📧 Would send → {to_email} | '{subject}'")
        return {
            "success":    True,
            "message_id": f"dry-run-{to_email}-{subject[:20].replace(' ','-')}",
            "error":      None,
            "dry_run":    True,
        }

    def cancel_sequence(self, thread_id):
        logger.info("[DRY RUN] Would cancel sequence/thread: %s", thread_id)
        return {"success": True, "dry_run": True}

    def get_campaign_stats(self, provider_campaign_id):
        return {"dry_run": True, "note": "No real stats in dry-run mode"}

    def process_webhook(self, payload):
        return {"dry_run": True, "payload_received": payload}


def get_provider() -> EmailProvider:
    """
    Factory: returns the configured email provider.
    If DRY_RUN=true, always returns DryRunProvider regardless of other settings.
    """
    if DRY_RUN:
        logger.info("Email provider: DryRunProvider (DRY_RUN=true)")
        return DryRunProvider()

    provider_name = os.getenv("EMAIL_PROVIDER", "smartlead").lower()

    if provider_name == "smartlead":
        from smartlead_provider import SmartleadProvider
        return SmartleadProvider()
    elif provider_name == "instantly":
        from instantly_provider import InstantlyProvider
        return InstantlyProvider()
    elif provider_name == "smtp":
        from smtp_provider import SMTPProvider
        return SMTPProvider()
    else:
        logger.warning("Unknown EMAIL_PROVIDER=%s, falling back to DryRunProvider", provider_name)
        return DryRunProvider()
