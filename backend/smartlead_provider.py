"""
BMS LeadFlow — Smartlead email provider
Docs: https://api.smartlead.ai/reference

Environment variables required (never commit to Git):
  SMARTLEAD_API_KEY     — get from Smartlead dashboard → Settings → API
  SMARTLEAD_SENDER_ID   — sender account ID in Smartlead (optional; used for scheduling)

Install: no extra library needed — uses requests.
"""

import os
import logging
from typing import Optional
from datetime import datetime, timezone

import requests
from email_provider import EmailProvider

load_dotenv_imported = False
try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv_imported = True
except ImportError:
    pass

logger = logging.getLogger(__name__)

SMARTLEAD_BASE  = "https://server.smartlead.ai/api/v1"
SMARTLEAD_KEY   = os.getenv("SMARTLEAD_API_KEY", "")
REQUEST_TIMEOUT = 30


class SmartleadProvider(EmailProvider):
    """Smartlead cold email API integration."""

    def __init__(self):
        if not SMARTLEAD_KEY:
            raise RuntimeError(
                "SMARTLEAD_API_KEY not set. "
                "Get your key at https://app.smartlead.ai → Settings → API Keys\n"
                "Then add to your .env file: SMARTLEAD_API_KEY=sl-..."
            )
        self.key = SMARTLEAD_KEY

    def _get(self, path: str, params: dict = None) -> dict:
        r = requests.get(
            f"{SMARTLEAD_BASE}/{path}",
            params={**(params or {}), "api_key": self.key},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, data: dict) -> dict:
        r = requests.post(
            f"{SMARTLEAD_BASE}/{path}",
            params={"api_key": self.key},
            json=data,
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

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
        Add a lead to a Smartlead campaign (or create a one-off send).
        Smartlead's model is campaign-based; each send is a campaign member.
        """
        try:
            # Add lead to campaign
            payload = {
                "lead_list": [{
                    "first_name":  (to_name or "").split()[0] if to_name else "",
                    "last_name":   " ".join((to_name or "").split()[1:]) if to_name else "",
                    "email":       to_email,
                    "custom_fields": {},
                }],
                "settings": {
                    "ignore_global_block_list": False,
                    "ignore_unsubscribe_list":  False,
                    "ignore_community_bounce_list": False,
                },
            }
            if campaign_id:
                result = self._post(f"campaigns/{campaign_id}/leads", payload)
            else:
                logger.warning("SmartleadProvider.send_email called without campaign_id")
                return {"success": False, "error": "No campaign_id provided", "message_id": None}

            return {
                "success":    True,
                "message_id": str(result.get("id", "")),
                "error":      None,
                "dry_run":    False,
            }
        except Exception as exc:
            logger.error("Smartlead send_email error: %s", exc)
            return {"success": False, "message_id": None, "error": str(exc)}

    def cancel_sequence(self, thread_id: str) -> dict:
        """Remove a lead from all campaign sequences (mark as stopped)."""
        try:
            result = self._post(f"leads/{thread_id}/stop", {})
            return {"success": True, "result": result}
        except Exception as exc:
            logger.error("Smartlead cancel_sequence error for %s: %s", thread_id, exc)
            return {"success": False, "error": str(exc)}

    def get_campaign_stats(self, provider_campaign_id: str) -> dict:
        try:
            return self._get(f"campaigns/{provider_campaign_id}/analytics")
        except Exception as exc:
            logger.error("Smartlead get_campaign_stats error: %s", exc)
            return {"error": str(exc)}

    def process_webhook(self, payload: dict) -> dict:
        """
        Normalise a Smartlead webhook event.
        Smartlead sends: event_type, email, lead_id, campaign_id, message_id, timestamp.
        """
        # Smartlead event_type mapping
        event_map = {
            "EMAIL_SENT":           "sent",
            "EMAIL_OPEN":           "open",
            "EMAIL_LINK_CLICK":     "click",
            "EMAIL_REPLY":          "reply",
            "EMAIL_BOUNCE":         "bounce",
            "LEAD_UNSUBSCRIBED":    "unsubscribe",
        }
        raw_type = payload.get("event_type", "")
        event_type = event_map.get(raw_type, raw_type.lower())

        return {
            "event_type":        event_type,
            "email":             payload.get("email"),
            "provider_event_id": str(payload.get("message_id") or payload.get("id") or ""),
            "occurred_at":       payload.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            "metadata":          payload,
        }
