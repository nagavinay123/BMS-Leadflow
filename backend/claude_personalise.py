"""
BMS LeadFlow — Claude AI Email Personalisation
Generates ONE personalised opening line per company, using real audit data.

Rules (spec):
  - UK English only
  - No invented facts, no unsupported claims, no fabricated metrics
  - Based ONLY on data from the website audit + ICP context
  - Concise and professional — 1–2 sentences max
  - Do NOT write the whole email — only the opening line

Environment:
  ANTHROPIC_API_KEY  — get from https://console.anthropic.com

Model: claude-haiku-4-5-20251001 (fast + cheap for single-line generation)
"""

import os
import logging
from typing import Optional
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL             = "claude-haiku-4-5-20251001"
MAX_TOKENS        = 120


def _api_available() -> bool:
    return bool(ANTHROPIC_API_KEY)


def personalise_email(company: dict) -> dict:
    """
    Generate a personalised opening line for a cold email to this company.

    Args:
        company: merged company + audit dict (from get_companies / _merge_audit)

    Returns:
        {
          "opening_line":  str | None,
          "model":         str,
          "generated_at":  str,
          "error":         str | None,
          "fallback_used": bool,
        }
    """
    base = {
        "opening_line": None,
        "model":        MODEL,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "error":        None,
        "fallback_used": False,
    }

    if not _api_available():
        base["error"]        = "ANTHROPIC_API_KEY not set — using rule-based fallback"
        base["opening_line"] = _rule_based_opening(company)
        base["fallback_used"] = True
        return base

    # ── Build the prompt ──────────────────────────────────────
    prompt = _build_prompt(company)

    try:
        import anthropic
        client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message  = client.messages.create(
            model      = MODEL,
            max_tokens = MAX_TOKENS,
            messages   = [{"role": "user", "content": prompt}],
        )
        opening_line = message.content[0].text.strip()

        # Safety: ensure no invented data (basic check)
        opening_line = _safety_check(opening_line, company)

        base["opening_line"] = opening_line
        return base

    except Exception as exc:
        logger.error("Claude personalise error: %s", exc)
        base["error"]         = str(exc)
        base["opening_line"]  = _rule_based_opening(company)
        base["fallback_used"] = True
        return base


def _build_prompt(company: dict) -> str:
    """Build the Claude prompt from real audit data only."""
    biz_name   = company.get("name", "the business")
    issues     = company.get("issues") or []
    perf       = company.get("performance_score")
    mobile     = company.get("mobile_score")
    has_ssl    = company.get("https")
    has_web    = company.get("has_website")
    rating     = company.get("rating")
    reviews    = company.get("review_count")
    icp_match  = company.get("icp_match", "")
    audit_src  = company.get("audit_source", "response_time")

    facts = []
    if not has_web:
        facts.append("they do not have a website")
    if not has_ssl:
        facts.append("their website lacks HTTPS (shows as 'Not Secure' in browsers)")
    if perf is not None and perf < 60 and audit_src == "pagespeed":
        facts.append(f"their desktop performance score is {perf}/100 (from Google PageSpeed)")
    if mobile is not None and mobile < 60 and audit_src == "pagespeed":
        facts.append(f"their mobile performance score is {mobile}/100")
    for issue in issues:
        label = issue.get("label", "")
        if label and "response_time" not in label.lower():
            facts.append(label.lower())
    if rating and reviews:
        facts.append(f"they have {reviews} Google reviews rated {rating}/5")

    facts_text = "; ".join(facts) if facts else "their website has room for improvement"

    return f"""You are writing the opening line of a professional cold email from BeMySocial (a UK digital marketing agency) to {biz_name}.

Verified facts about this business (from our website audit):
{facts_text}

Write EXACTLY ONE opening sentence (1–2 sentences maximum) that:
- Is specific to this company using ONLY the facts above
- Is in professional UK English
- Does NOT invent any data not listed above
- Does NOT make promises or guarantees
- Opens naturally as the first sentence of an email (not "Dear..." just the opening observation)
- Is conversational, not salesy

Output only the opening line. Nothing else."""


def _rule_based_opening(company: dict) -> str:
    """Fallback opening line when Claude API is unavailable."""
    biz_name = company.get("name", "your business")
    issues   = company.get("issues") or []
    has_ssl  = company.get("https")
    perf     = company.get("performance_score")

    if not company.get("has_website"):
        return f"I came across {biz_name} and noticed you don't currently have a website — something we can help with."
    if not has_ssl:
        return f"I was looking at {biz_name}'s website and noticed it's flagged as 'Not Secure' by browsers, which can put off potential customers before they've even read a word."
    if perf is not None and perf < 50:
        return f"I was reviewing {biz_name}'s website and noticed it's loading slowly, which can affect your Google ranking and reduce enquiries."
    if issues:
        return f"I came across {biz_name}'s website and spotted a few things that might be holding back your online visibility."
    return f"I came across {biz_name} while researching businesses in your area and wanted to reach out."


def _safety_check(text: str, company: dict) -> str:
    """
    Basic safety check: ensure Claude hasn't invented specific numbers
    not present in the audit data. If suspicious, fall back to rule-based.
    """
    import re
    # Check for invented percentages or stats not in our data
    invented_numbers = re.findall(r'\b\d{2,3}%', text)
    if invented_numbers:
        logger.warning("Claude output contained invented percentages: %s — using fallback", invented_numbers)
        return _rule_based_opening(company)
    return text
