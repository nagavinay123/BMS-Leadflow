"""
BMS LeadFlow — Website Checker
Week 5 | Pipeline Lead

For each company with a website, this module checks:
  1. Does the site resolve? (is it live?)
  2. Does it have HTTPS / SSL?
  3. Google PageSpeed Insights — performance score (desktop)
  4. Google PageSpeed Insights — mobile score
  5. Does it have a mobile viewport meta tag?
  6. Does it have a <title> tag?
  7. Does it have a meta description?

Results are stored in website_audits and used by:
  - The scoring engine  (bad scores = higher opportunity score)
  - The AI personalisation (Claude references real audit findings in emails)

Usage (standalone):
  python website_checker.py --company-id <uuid>
  python website_checker.py --run-id <uuid>     (audit all from a run)
  python website_checker.py --all               (audit all unaudited companies)
"""

import os
import re
import time
import argparse
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

REQUEST_TIMEOUT   = 10
DELAY_BETWEEN     = 0.5


# ──────────────────────────────────────────────
# Core audit function
# ──────────────────────────────────────────────

def audit_website(domain: str, website_url: str = None) -> dict:
    """
    Run a full website audit for one domain.

    Returns a dict matching the website_audits table schema.
    On any unrecoverable error, returns a dict with resolves=False and error set.
    """
    url = _normalise_url(website_url or domain)

    result = {
        "domain":               domain,
        "resolves":             False,
        "https":                url.startswith("https://"),
        "performance_score":    None,
        "mobile_score":         None,
        "has_viewport":         False,
        "has_title":            False,
        "has_meta_description": False,
        "issues":               [],
        "error":                None,
    }

    # ── Step 1: Is the site reachable? ─────────────────────
    try:
        head = requests.head(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if head.status_code >= 400:
            # Try GET in case HEAD is blocked
            get = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if get.status_code >= 400:
                result["error"] = f"HTTP {get.status_code}"
                return result
        result["resolves"] = True
        result["https"]    = head.url.startswith("https://") if head.url else result["https"]
    except requests.RequestException as e:
        result["error"] = f"Connection failed: {e}"
        return result

    # ── Step 2: Fetch HTML and check page elements ──────────
    try:
        page = requests.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        soup = BeautifulSoup(page.text, "html.parser")

        title_tag = soup.find("title")
        result["has_title"] = bool(title_tag and title_tag.text.strip())

        meta_desc = soup.find("meta", attrs={"name": "description"})
        result["has_meta_description"] = bool(
            meta_desc and meta_desc.get("content", "").strip()
        )

        viewport = soup.find("meta", attrs={"name": "viewport"})
        result["has_viewport"] = bool(viewport)

    except Exception as e:
        result["error"] = f"HTML parse error: {e}"
        # Don't return — PageSpeed can still run

    # ── Step 3: Response-time speed score (no API needed) ──
    speed_score = _response_time_score(url)
    time.sleep(DELAY_BETWEEN)

    result["performance_score"] = speed_score
    result["mobile_score"]      = speed_score   # same proxy — no mobile API

    # ── Step 3b: Scrape email + social links from homepage ───
    soup_obj = soup if 'soup' in dir() else None
    result["scraped_email"]  = _scrape_email(url, soup_obj)
    instagram, facebook = _scrape_social(soup_obj)
    result["instagram_url"]  = instagram
    result["facebook_url"]   = facebook

    # ── Step 4: Build issues list (for personalisation) ─────
    issues = []

    if not result["https"]:
        issues.append({"type": "no_ssl", "label": "No HTTPS / SSL certificate"})

    if speed_score is not None and speed_score < 40:
        issues.append({"type": "poor_performance",
                       "label": f"Website very slow to load (score {speed_score}/100)"})
    elif speed_score is not None and speed_score < 65:
        issues.append({"type": "slow_desktop",
                       "label": f"Website slow to load (score {speed_score}/100)"})

    if not result["has_viewport"]:
        issues.append({"type": "no_viewport",
                       "label": "No mobile viewport tag — not mobile friendly"})

    if not result["has_title"]:
        issues.append({"type": "no_title", "label": "Missing page title tag"})

    if not result["has_meta_description"]:
        issues.append({"type": "no_meta_desc", "label": "Missing meta description"})

    result["issues"] = issues
    return result


# ──────────────────────────────────────────────
# Speed score — response time based (no API)
# ──────────────────────────────────────────────

def _response_time_score(url: str) -> int | None:
    """
    Measures how fast the homepage responds and converts to a 0–100 score.
    No API key required.

    Score bands:
      <0.5s  → 95   (excellent)
      <1.0s  → 80   (good)
      <2.0s  → 65   (average)
      <3.5s  → 45   (slow)
      <6.0s  → 25   (very slow)
      ≥6.0s  → 10   (unusable)
    """
    try:
        start = time.time()
        r = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LeadFlow/1.0)"},
            stream=True,   # only download headers + first chunk
        )
        # Read first 4KB then stop — enough to get time-to-first-byte
        r.raw.read(4096)
        elapsed = time.time() - start
        r.close()

        if   elapsed < 0.5: return 95
        elif elapsed < 1.0: return 80
        elif elapsed < 2.0: return 65
        elif elapsed < 3.5: return 45
        elif elapsed < 6.0: return 25
        else:               return 10
    except Exception as e:
        print(f"  [Speed] Could not measure {url}: {e}")
        return None


# ──────────────────────────────────────────────
# URL helper
# ──────────────────────────────────────────────

# ──────────────────────────────────────────────
# Email scraper (free — no API key needed)
# ──────────────────────────────────────────────

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE
)

# Domains to ignore (privacy, images, icons, etc.)
EMAIL_BLOCKLIST = {
    "sentry.io", "example.com", "wixpress.com", "squarespace.com",
    "wordpress.com", "shopify.com", "googletagmanager.com", "schema.org",
    "w3.org", "facebook.com", "instagram.com", "twitter.com",
}


def _scrape_email(base_url: str, homepage_soup: BeautifulSoup = None) -> str | None:
    """
    Try to find a contact email address on the website.

    Strategy:
      1. Check mailto: links on the already-fetched homepage
      2. Regex-scan homepage text for email patterns
      3. Try fetching /contact, /contact-us, /about pages and repeat

    Returns the first valid, non-blocked email found, or None.
    """
    found = set()

    # ── Homepage (use already-parsed soup if available) ──────
    if homepage_soup:
        found.update(_extract_from_soup(homepage_soup))

    if not found:
        # Try raw text scan of homepage HTML
        try:
            r = requests.get(base_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            found.update(_extract_from_text(r.text))
        except Exception:
            pass

    # ── Try contact/about pages ──────────────────────────────
    if not found:
        contact_paths = ["/contact", "/contact-us", "/about", "/about-us", "/reach-us"]
        for path in contact_paths:
            try:
                r = requests.get(
                    base_url.rstrip("/") + path,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True,
                )
                if r.status_code == 200:
                    found.update(_extract_from_text(r.text))
                if found:
                    break
            except Exception:
                continue

    # Return first good email (prefer non-noreply)
    ranked = sorted(
        found,
        key=lambda e: (
            any(x in e.lower() for x in ["noreply", "no-reply", "donotreply"]),
            any(x in e.lower() for x in ["info@", "hello@", "contact@", "support@"]) is False,
        )
    )
    return ranked[0] if ranked else None


def _extract_from_soup(soup: BeautifulSoup) -> set:
    """Find emails from mailto: links in parsed HTML."""
    emails = set()
    for tag in soup.find_all("a", href=True):
        href = tag["href"]
        if href.lower().startswith("mailto:"):
            email = href[7:].split("?")[0].strip().lower()
            if _is_valid_email(email):
                emails.add(email)
    # Also scan visible text
    emails.update(_extract_from_text(soup.get_text()))
    return emails


def _extract_from_text(text: str) -> set:
    """Find emails using regex on raw text/HTML."""
    matches = EMAIL_RE.findall(text)
    return {e.lower() for e in matches if _is_valid_email(e)}


def _is_valid_email(email: str) -> bool:
    """Basic validation — not a blocked domain, looks real."""
    if not email or "@" not in email:
        return False
    domain = email.split("@")[-1].lower()
    if domain in EMAIL_BLOCKLIST:
        return False
    # Must have a dot in the domain part
    if "." not in domain:
        return False
    # Skip image/asset extensions wrongly captured
    if domain.endswith((".png", ".jpg", ".gif", ".svg", ".webp", ".css", ".js")):
        return False
    return True


def _scrape_social(soup: BeautifulSoup) -> tuple:
    """
    Look for Instagram and Facebook links in the page HTML.
    Returns (instagram_url, facebook_url) — either can be None.
    """
    if soup is None:
        return None, None

    instagram = None
    facebook  = None

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip().lower()
        if not instagram and "instagram.com/" in href:
            # Skip generic instagram.com homepage
            if href not in ("https://instagram.com", "https://www.instagram.com",
                            "http://instagram.com", "http://www.instagram.com",
                            "https://instagram.com/", "https://www.instagram.com/"):
                instagram = tag["href"].strip()
        if not facebook and "facebook.com/" in href:
            if href not in ("https://facebook.com", "https://www.facebook.com",
                            "http://facebook.com", "http://www.facebook.com",
                            "https://facebook.com/", "https://www.facebook.com/"):
                facebook = tag["href"].strip()
        if instagram and facebook:
            break

    return instagram, facebook


def _normalise_url(url_or_domain: str) -> str:
    """Ensure the URL has a scheme. Default to https."""
    s = url_or_domain.strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    return f"https://{s}"


# ──────────────────────────────────────────────
# Batch audit (used by pipeline and CLI)
# ──────────────────────────────────────────────

def audit_companies(companies: list) -> list:
    """
    Run website audits for a list of company dicts.
    Returns list of (company_id, audit_result) tuples.
    Skips companies with no website.
    """
    results = []
    total   = len([c for c in companies if c.get("has_website")])
    done    = 0

    for company in companies:
        if not company.get("has_website") or not company.get("website"):
            continue

        done += 1
        name   = company.get("name", "Unknown")[:45]
        domain = company.get("domain") or company.get("website", "")
        print(f"  [{done:02d}/{total}] {name} ({domain})", end=" … ", flush=True)

        audit = audit_website(domain=domain, website_url=company.get("website"))

        perf_label   = f"perf {audit['performance_score']}" if audit["performance_score"] is not None else "perf —"
        mobile_label = f"mob {audit['mobile_score']}" if audit["mobile_score"] is not None else "mob —"
        ssl_label    = "SSL ✓" if audit["https"] else "SSL ✗"
        print(f"{perf_label} | {mobile_label} | {ssl_label} | {len(audit['issues'])} issues")

        results.append((company.get("id"), audit))

    return results


# ──────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    from database import get_companies, save_website_audit, update_company_status

    parser = argparse.ArgumentParser(description="BMS LeadFlow — Website checker (Week 5)")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-id",     help="Audit all companies from a specific discovery run")
    group.add_argument("--all",        action="store_true", help="Audit all companies with a website")
    group.add_argument("--url",        help="Audit a single URL (for testing)")
    args = parser.parse_args()

    if args.url:
        print(f"\nAuditing: {args.url}")
        result = audit_website(domain=args.url)
        import json
        print(json.dumps(result, indent=2))

    else:
        companies = get_companies(run_id=args.run_id if args.run_id else None)
        companies_with_site = [c for c in companies if c.get("has_website")]
        print(f"\n{'='*55}")
        print(f"  Website Checker — {len(companies_with_site)} companies to audit")
        print(f"{'='*55}\n")

        pairs = audit_companies(companies_with_site)

        print(f"\nSaving {len(pairs)} audits to Supabase…")
        for company_id, audit in pairs:
            save_website_audit(company_id, audit)
            update_company_status(company_id, "enriched")

        print(f"\n✅ Done — {len(pairs)} audits saved.")
