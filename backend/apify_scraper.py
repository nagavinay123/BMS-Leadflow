"""
BMS LeadFlow — Apify Google Maps Scraper
Alternative to Google Maps Places API — no billing required.

Uses the Apify actor: compass/crawler-google-places
Docs: https://apify.com/compass/crawler-google-places

Setup:
  1. Sign up at https://apify.com (free account)
  2. Go to Settings → Integrations → copy your API token
  3. Add to .env:  APIFY_API_TOKEN=apify_api_xxxxx

Free tier: 5 USD credit/month ≈ ~1,000 Google Maps results
"""

import os
import time
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

ACTOR_ID        = "compass~crawler-google-places"
BASE_URL        = "https://api.apify.com/v2"
POLL_INTERVAL   = 5      # seconds between status checks
MAX_WAIT        = 300    # 5 minutes max wait for Apify run
REQUEST_TIMEOUT = 30     # seconds for each HTTP call


def search_businesses(business_type: str, town: str, max_results: int = 50) -> list:
    """
    Main entry point — mirrors the interface of google_maps.search_businesses().
    Returns a list of dicts with the same field names so pipeline.py needs no changes.
    """
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        raise RuntimeError(
            "APIFY_API_TOKEN not set in .env\n"
            "Sign up at https://apify.com → Settings → Integrations → API token"
        )

    query = f"{business_type} in {town} UK"
    print(f"  [Apify] Searching: '{query}' (max {max_results} results)…")

    run_id = _start_run(token, query, max_results)
    print(f"  [Apify] Run started: {run_id}")

    dataset_id = _wait_for_run(token, run_id)
    print(f"  [Apify] Run complete. Fetching results…")

    raw_items = _fetch_dataset(token, dataset_id, max_results)
    print(f"  [Apify] {len(raw_items)} raw items returned")

    places = [_normalise(item) for item in raw_items if item.get("title")]
    return places


def estimate_cost(result_count: int) -> float:
    """Rough Apify cost estimate in USD (≈ $0.002 per result on free actor)."""
    return round(result_count * 0.002, 4)


# ──────────────────────────────────────────────
# Private helpers
# ──────────────────────────────────────────────

def _start_run(token: str, query: str, max_results: int) -> str:
    """POST to Apify to start a new actor run. Returns the run ID."""
    url = f"{BASE_URL}/acts/{ACTOR_ID}/runs"
    payload = {
        "searchStringsArray": [query],
        "maxCrawledPlacesPerSearch": max_results,
        "language": "en",
        "countryCode": "gb",
        "includeWebResults": False,
    }
    r = requests.post(
        url,
        json    = payload,
        params  = {"token": token},
        timeout = REQUEST_TIMEOUT,
    )
    if r.status_code not in (200, 201):
        _handle_api_error(r)

    data = r.json()
    return data["data"]["id"]


def _wait_for_run(token: str, run_id: str) -> str:
    """Poll until the run finishes. Returns the dataset ID."""
    url     = f"{BASE_URL}/actor-runs/{run_id}"
    waited  = 0
    dot_count = 0

    while waited < MAX_WAIT:
        r = requests.get(url, params={"token": token}, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            _handle_api_error(r)

        data   = r.json()["data"]
        status = data.get("status", "")

        if status == "SUCCEEDED":
            return data["defaultDatasetId"]

        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Apify run {run_id} ended with status: {status}")

        # Still running — print dots so the terminal looks alive
        dot_count += 1
        print(f"  [Apify] Waiting for results{'.' * (dot_count % 4)}  ({waited}s)", end="\r")
        time.sleep(POLL_INTERVAL)
        waited += POLL_INTERVAL

    raise RuntimeError(f"Apify run timed out after {MAX_WAIT}s")


def _fetch_dataset(token: str, dataset_id: str, limit: int) -> list:
    """Fetch items from the completed run's dataset."""
    url = f"{BASE_URL}/datasets/{dataset_id}/items"
    r   = requests.get(
        url,
        params  = {"token": token, "limit": limit, "format": "json"},
        timeout = REQUEST_TIMEOUT,
    )
    if r.status_code != 200:
        _handle_api_error(r)
    return r.json() if isinstance(r.json(), list) else []


def _normalise(item: dict) -> dict:
    """
    Convert Apify's output schema to the same dict shape that
    google_maps.py produced, so pipeline.py works unchanged.

    Apify field reference:
      title, address, phoneUnformatted, website, totalScore,
      reviewsCount, placeId, url, categories, businessStatus,
      location (lat/lng)
    """
    website = item.get("website") or ""
    domain  = _extract_domain(website) if website else None

    # Extract social media links from Apify's socialMedia array
    social      = item.get("socialMedia") or []
    instagram   = next((s["url"] for s in social if s.get("type") == "INSTAGRAM"), None)
    facebook    = next((s["url"] for s in social if s.get("type") == "FACEBOOK"),  None)

    return {
        "name":              item.get("title", ""),
        "formatted_address": item.get("address", ""),
        "phone":             item.get("phoneUnformatted") or item.get("phone", ""),
        "website":           website,
        "domain":            domain,
        "has_website":       bool(website),
        "rating":            item.get("totalScore"),
        "review_count":      item.get("reviewsCount"),
        "place_id":          item.get("placeId", ""),
        "google_maps_url":   item.get("url", ""),
        "types":             item.get("categories", []),
        "business_status":   item.get("businessStatus", "OPERATIONAL"),
        "instagram_url":     instagram,
        "facebook_url":      facebook,
        "source":            "apify",
    }


def _extract_domain(url: str) -> str | None:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return domain[4:] if domain.startswith("www.") else domain
    except Exception:
        return None


def _handle_api_error(response: requests.Response):
    """Raise a helpful error for non-200 Apify responses."""
    try:
        msg = response.json().get("error", {}).get("message", response.text)
    except Exception:
        msg = response.text
    raise RuntimeError(f"Apify API error ({response.status_code}): {msg}")


# ──────────────────────────────────────────────
# CLI — quick test
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser(description="Test Apify scraper")
    parser.add_argument("--type", dest="business_type", default="plumber")
    parser.add_argument("--town", default="Leeds")
    parser.add_argument("--max",  dest="max_results", type=int, default=10)
    args = parser.parse_args()

    results = search_businesses(args.business_type, args.town, args.max_results)
    print(f"\n✅ Got {len(results)} results\n")
    for r in results[:3]:
        print(f"  {r['name']} | {r['formatted_address']} | website: {r.get('website','—')}")
    print("\nFull first result:")
    print(json.dumps(results[0], indent=2, default=str) if results else "No results")
