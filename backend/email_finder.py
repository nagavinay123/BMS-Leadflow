"""
BMS LeadFlow — Email Finder (Hunter.io)
Week 7: Reachability enrichment

Finds the professional email address for a company contact
using domain + first/last name via Hunter.io API.

Setup:
  1. Sign up at https://hunter.io (free — 25 searches/month)
  2. Dashboard → API → copy your API key
  3. Add to .env: HUNTER_API_KEY=your-key-here

Docs: https://hunter.io/api-documentation
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL      = "https://api.hunter.io/v2"
REQUEST_DELAY = 1.0   # be polite to Hunter.io free tier


def find_email(domain: str, first_name: str, last_name: str) -> dict:
    """
    Find and verify a professional email for a named person at a domain.

    Returns:
      {
        "email":      "john@example.com" or None,
        "confidence": 0–100 (Hunter.io confidence score),
        "verified":   True/False,
        "source":     "hunter.io"
      }
    """
    api_key = os.getenv("HUNTER_API_KEY")
    if not api_key:
        return _empty_result("HUNTER_API_KEY not configured")

    if not domain or not first_name:
        return _empty_result("domain or first_name missing")

    try:
        result = _email_finder(api_key, domain, first_name, last_name)
        time.sleep(REQUEST_DELAY)
        return result
    except Exception as e:
        return _empty_result(str(e))


def find_emails_for_domain(domain: str, limit: int = 5) -> list:
    """
    Find all known email addresses for a domain (domain search).
    Useful when we don't have a specific name.

    Returns a list of email dicts.
    """
    api_key = os.getenv("HUNTER_API_KEY")
    if not api_key or not domain:
        return []

    try:
        r = requests.get(
            f"{BASE_URL}/domain-search",
            params={
                "domain":   domain,
                "limit":    limit,
                "api_key":  api_key,
            },
            timeout=10,
        )
        time.sleep(REQUEST_DELAY)

        if r.status_code == 401:
            raise RuntimeError("Hunter.io API key invalid")
        if r.status_code == 429:
            raise RuntimeError("Hunter.io rate limit reached — upgrade plan or wait")
        r.raise_for_status()

        data    = r.json().get("data", {})
        emails  = data.get("emails", [])
        pattern = data.get("pattern")          # e.g. "{first}.{last}"

        return [
            {
                "email":      e.get("value"),
                "first_name": e.get("first_name", ""),
                "last_name":  e.get("last_name", ""),
                "confidence": e.get("confidence", 0),
                "type":       e.get("type", ""),   # "personal" or "generic"
                "pattern":    pattern,
                "source":     "hunter.io",
            }
            for e in emails
        ]

    except Exception:
        return []


def verify_email(email: str) -> dict:
    """
    Verify whether a specific email address is deliverable.
    Uses Hunter.io email-verifier endpoint.

    Returns:
      { "email": ..., "result": "deliverable"|"risky"|"undeliverable", "score": 0-100 }
    """
    api_key = os.getenv("HUNTER_API_KEY")
    if not api_key or not email:
        return {"email": email, "result": "unknown", "score": 0}

    try:
        r = requests.get(
            f"{BASE_URL}/email-verifier",
            params={"email": email, "api_key": api_key},
            timeout=15,
        )
        time.sleep(REQUEST_DELAY)
        r.raise_for_status()

        data = r.json().get("data", {})
        return {
            "email":  email,
            "result": data.get("result", "unknown"),
            "score":  data.get("score", 0),
        }
    except Exception:
        return {"email": email, "result": "unknown", "score": 0}


# ──────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────

def _email_finder(api_key: str, domain: str, first: str, last: str) -> dict:
    """Call Hunter.io /email-finder for a specific person."""
    params = {
        "domain":      domain,
        "first_name":  first,
        "last_name":   last,
        "api_key":     api_key,
    }
    r = requests.get(f"{BASE_URL}/email-finder", params=params, timeout=10)

    if r.status_code == 401:
        raise RuntimeError("Hunter.io API key invalid")
    if r.status_code == 429:
        raise RuntimeError("Hunter.io monthly limit reached")
    if r.status_code == 404 or r.status_code == 400:
        return _empty_result("no email found")

    r.raise_for_status()
    data = r.json().get("data", {})

    email      = data.get("email")
    confidence = data.get("score", 0)
    verified   = confidence >= 70   # Hunter.io: 70+ = confident

    return {
        "email":      email,
        "confidence": confidence,
        "verified":   verified,
        "source":     "hunter.io",
        "error":      None,
    }


def _empty_result(reason: str = "") -> dict:
    return {
        "email":      None,
        "confidence": 0,
        "verified":   False,
        "source":     "hunter.io",
        "error":      reason,
    }


def hunter_available() -> bool:
    """Return True if Hunter.io is configured."""
    return bool(os.getenv("HUNTER_API_KEY"))


# ──────────────────────────────────────────────
# CLI test
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser(description="Test Hunter.io email finder")
    parser.add_argument("--domain",  required=True,  help="e.g. example.com")
    parser.add_argument("--first",   default="",     help="First name")
    parser.add_argument("--last",    default="",     help="Last name")
    parser.add_argument("--search",  action="store_true", help="Domain search (all emails)")
    args = parser.parse_args()

    if args.search:
        results = find_emails_for_domain(args.domain)
        print(f"\n✅ Found {len(results)} emails for {args.domain}")
        for e in results:
            print(f"  {e['email']} ({e['confidence']}% confidence) — {e['first_name']} {e['last_name']}")
    else:
        result = find_email(args.domain, args.first, args.last)
        print(f"\n✅ Result: {json.dumps(result, indent=2)}")
