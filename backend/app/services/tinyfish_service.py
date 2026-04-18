"""
TinyFish Service Layer
Wraps TinyFish Search API and Agent API for live retail signal scraping.

TinyFish has 4 APIs:
  - Search API  → geo-targeted web search results (structured JSON)
  - Agent API   → browser automation to extract data from real websites
  - Fetch API   → extract content from known URLs
  - Browser API → direct browser control (not used here)

All functions:
  - Return structured Python dicts
  - Timeout gracefully (never block the analysis pipeline)
  - Degrade to empty fallback when TINYFISH_API_KEY is missing or call fails
"""
import asyncio
import json
import os
import time
from typing import Optional
import requests

from app.core.config import get_settings


def _has_tinyfish_key() -> bool:
    settings = get_settings()
    key = settings.tinyfish_api_key
    return bool(key and key != "your_tinyfish_api_key_here" and len(key) > 10)


def _search_sync(query: str, location: str = "US", num_results: int = 10) -> list[dict]:
    """
    Synchronous TinyFish Search API call.
    Returns list of {title, snippet, url, site_name} dicts.
    """
    if not _has_tinyfish_key():
        return []

    settings = get_settings()
    try:
        resp = requests.get(
            "https://api.search.tinyfish.ai",
            headers={"X-API-Key": settings.tinyfish_api_key},
            params={"q": query, "location": location, "num": num_results},
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("results", [])
    except Exception as e:
        print(f"[TinyFish Search] Error: {e}")
    return []


def _agent_sync(url: str, goal: str, timeout: int = 35) -> Optional[dict]:
    """
    Synchronous TinyFish Agent API call (SSE streaming, collected to completion).
    Returns the result_json dict from the COMPLETE event.
    """
    if not _has_tinyfish_key():
        return None

    settings = get_settings()
    try:
        resp = requests.post(
            "https://agent.tinyfish.ai/v1/automation/run-sse",
            headers={
                "X-API-Key": settings.tinyfish_api_key,
                "Content-Type": "application/json",
            },
            json={"url": url, "goal": goal},
            stream=True,
            timeout=timeout,
        )
        start = time.time()
        for line in resp.iter_lines():
            if time.time() - start > timeout:
                break
            if not line:
                continue
            line_str = line.decode("utf-8") if isinstance(line, bytes) else line
            if line_str.startswith("data: "):
                try:
                    event = json.loads(line_str[6:])
                    if event.get("type") == "COMPLETE":
                        result = event.get("result")
                        if isinstance(result, str):
                            return json.loads(result)
                        return result
                except Exception:
                    pass
    except Exception as e:
        print(f"[TinyFish Agent] Error ({url[:50]}): {e}")
    return None


# ── Async wrappers (run synchronous calls in executor) ──────────────────────

async def search_retail_signals(query: str, location: str = "US") -> list[dict]:
    """Async: search for live retail signals."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _search_sync, query, location, 10)


async def scrape_yelp_new_businesses(city_state: str, category: str = "") -> list[dict]:
    """
    Async: scrape Yelp for recently reviewed/opened businesses in the area.
    Returns list of {name, category, rating, review_count, opened_recently}.
    """
    city_slug = city_state.replace(", ", "-").replace(" ", "-").lower()
    cat_param = f"find_desc={category}&" if category else ""
    url = f"https://www.yelp.com/search?{cat_param}find_loc={city_slug}&sortby=date_desc"
    goal = (
        f"Extract the 12 most recently reviewed businesses in {city_state}. "
        f"Return JSON array: "
        f'[{{"name": str, "category": str, "rating": float, "review_count": int, '
        f'"opened_recently": bool}}]. '
        f"Mark opened_recently=true if the business appears new (low review count, recent activity)."
    )
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _agent_sync, url, goal, 40)
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        # may be wrapped in a key
        for v in result.values():
            if isinstance(v, list):
                return v
    return []


async def scrape_loopnet_listings(city_state: str, store_size: str = "large") -> dict:
    """
    Async: scrape Loopnet for available commercial/retail spaces near the city.
    Returns {count: int, listings: [{address, sqft, type, listing_type}]}.
    """
    city_slug = city_state.split(",")[0].strip().replace(" ", "-")
    state = city_state.split(",")[-1].strip()[:2].upper() if "," in city_state else "AZ"
    url = f"https://www.loopnet.com/search/commercial-real-estate/{city_slug}-{state}/for-lease/"
    goal = (
        f"Find up to 8 available retail/commercial spaces for lease in {city_state}. "
        f"Return JSON: "
        f'{{"count": int, "listings": [{{"address": str, "sqft": int, "listing_type": str, '
        f'"available": bool}}]}}'
    )
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _agent_sync, url, goal, 40)
    if isinstance(result, dict):
        return result
    return {"count": 0, "listings": []}


async def search_news_signals(city_state: str, store_category: str = "retail") -> list[dict]:
    """
    Async: search for recent news about retail openings / development approvals in the area.
    Returns list of search result dicts.
    """
    city = city_state.split(",")[0].strip()
    queries = [
        f'new {store_category} store opening "{city}" 2025 2026',
        f'"{city}" retail development approved permit 2025',
        f'"{city}" commercial real estate growth new business',
    ]
    loop = asyncio.get_event_loop()
    results = []
    for q in queries:
        batch = await loop.run_in_executor(None, _search_sync, q, "US", 5)
        results.extend(batch)
    return results[:15]  # cap at 15 unique signals


async def scrape_city_permits(city_state: str) -> dict:
    """
    Async: attempt to scrape city business permit portal for recent commercial permits.
    Returns {permit_count: int, recent_commercial: int}.
    Gracefully falls back if the city portal is inaccessible.
    """
    city = city_state.split(",")[0].strip().lower().replace(" ", "")
    state = city_state.split(",")[-1].strip().lower() if "," in city_state else "az"

    # Known permit portals for common cities
    KNOWN_PORTALS = {
        "phoenix": "https://www.phoenix.gov/pdd/permits/online-permit-center",
        "gilbert": "https://www.gilbertaz.gov/departments/development-services/permits",
        "scottsdale": "https://www.scottsdaleaz.gov/permits",
        "chandler": "https://www.chandleraz.gov/residents/permits-and-licenses",
        "peoria": "https://peoriaaz.gov/421/Permits",
    }

    portal_url = KNOWN_PORTALS.get(city, f"https://www.{city}{state}.gov/permits")
    goal = (
        "Find the number of new commercial or retail building permits filed in the past 90 days. "
        "Return JSON: {\"permit_count\": int, \"recent_commercial\": int, \"source\": str}"
    )
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _agent_sync, portal_url, goal, 30)
    if isinstance(result, dict) and "permit_count" in result:
        return result
    return {"permit_count": 0, "recent_commercial": 0, "source": "unavailable"}
