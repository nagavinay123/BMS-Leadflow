"""
BMS LeadFlow — Google Maps Places API integration
Owner: Vinay (Week 4)

Searches for UK businesses by type + town.
Returns enriched business records ready for Companies House matching.
"""

import os
import time
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY  = os.getenv("GOOGLE_MAPS_API_KEY")
BASE_URL = "https://maps.googleapis.com/maps/api/place"

# Google requires ≥2s before a next_page_token is valid
PAGE_DELAY_SECONDS   = 2.0
# Keep well under 100 QPS limit for Place Details
DETAIL_DELAY_SECONDS = 0.15


# ──────────────────────────────────────────────
# Raw API calls
# ──────────────────────────────────────────────

def _text_search(query: str, next_page_token: str = None) -> dict:
    """
    Places Text Search API — returns up to 20 results per page.
    Cost: $32 per 1,000 calls.
    Docs: https://developers.google.com/maps/documentation/places/web-service/search-text
    """
    if not API_KEY:
        raise RuntimeError("GOOGLE_MAPS_API_KEY not set in .env")

    params = {"query": query, "region": "gb", "key": API_KEY}
    if next_page_token:
        params["pagetoken"] = next_page_token

    r = requests.get(f"{BASE_URL}/textsearch/json", params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def _place_details(place_id: str) -> dict:
    """
    Place Details API — returns full info for one business.
    Fields: name, address, phone, website, rating, reviews, types, status.
    Cost: $3 per 1,000 calls (contact fields tier).
    Docs: https://developers.google.com/maps/documentation/places/web-service/details
    """
    params = {
        "place_id": place_id,
        "fields": (
            "name,formatted_address,formatted_phone_number,"
            "website,rating,user_ratings_total,"
            "types,business_status,url"
        ),
        "key": API_KEY,
    }
    r = requests.get(f"{BASE_URL}/details/json", params=params, timeout=10)
    r.raise_for_status()
    return r.json()


# ──────────────────────────────────────────────
# Public search function
# ──────────────────────────────────────────────

def search_businesses(business_type: str, town: str, max_results: int = 60) -> list[dict]:
    """
    Search Google Maps for UK businesses matching business_type in town.
    Paginates up to 3 pages (60 results max — Google's hard cap).
    Enriches each result with Place Details (phone, website, etc.).

    Returns a list of dicts, each representing one business.
    """
    query  = f"{business_type} in {town}, UK"
    raw    = _paginate_search(query, max_results)
    return _enrich_batch(raw)


def _paginate_search(query: str, max_results: int) -> list:
    """Run paginated Text Search and return raw place objects."""
    results          = []
    next_page_token  = None

    while len(results) < max_results:
        if next_page_token:
            time.sleep(PAGE_DELAY_SECONDS)

        data   = _text_search(query, next_page_token)
        status = data.get("status")

        if status == "ZERO_RESULTS":
            break
        if status != "OK":
            raise RuntimeError(
                f"Google Maps API error: {status} — {data.get('error_message', 'no detail')}"
            )

        results.extend(data.get("results", []))
        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break

    return results[:max_results]


def _enrich_batch(raw_places: list) -> list[dict]:
    """Fetch Place Details for each raw result and return clean dicts."""
    enriched = []

    for place in raw_places:
        place_id = place.get("place_id", "")
        if not place_id:
            continue

        try:
            data   = _place_details(place_id)
            status = data.get("status")
            if status != "OK":
                continue

            d       = data["result"]
            website = d.get("website", "")
            domain  = _extract_domain(website) if website else None

            enriched.append({
                "name":              d.get("name", ""),
                "formatted_address": d.get("formatted_address", ""),
                "phone":             d.get("formatted_phone_number", ""),
                "website":           website,
                "domain":            domain,
                "rating":            d.get("rating"),
                "review_count":      d.get("user_ratings_total"),
                "types":             d.get("types", []),
                "business_status":   d.get("business_status", ""),
                "google_maps_url":   d.get("url", ""),
                "place_id":          place_id,
                "has_website":       bool(website),
            })
        except requests.RequestException:
            # Skip individual failures — don't abort the whole batch
            continue
        finally:
            time.sleep(DETAIL_DELAY_SECONDS)

    return enriched


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _extract_domain(url: str) -> str:
    """Strip protocol, www., and path from a URL to get the bare domain."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        return domain.replace("www.", "").lower().strip("/")
    except Exception:
        return url


def estimate_cost(result_count: int, pages_used: int = 3) -> float:
    """Estimate USD cost for a search run."""
    text_search_cost = pages_used * 0.032   # $32 per 1,000
    detail_cost      = result_count * 0.003  # $3 per 1,000
    return round(text_search_cost + detail_cost, 4)
