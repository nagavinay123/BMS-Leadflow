"""
Activity logger — writes user actions to the activity_log table.
All calls are fire-and-forget; errors are logged but never raised.
"""

import logging
from database import get_supabase

logger = logging.getLogger(__name__)


def log_activity(action: str, details: dict = None, user_email: str = None):
    """Log an action to activity_log. Safe to call anywhere — never raises."""
    try:
        db = get_supabase()
        db.table("activity_log").insert({
            "action":     action,
            "details":    details or {},
            "user_email": user_email,
        }).execute()
    except Exception as e:
        logger.warning("activity_log write failed: %s", e)
