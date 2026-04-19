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
import time
from datetime import datetime
from typing import Optional
import requests

from app.core.config import get_settings

# Always use the actual current year so search queries are not stale
_CURRENT_YEAR = datetime.now().year
_PREV_YEAR    = _CURRENT_YEAR - 1

# TinyFish Search API only accepts ISO 2-letter country codes for `location`.
# City/state strings return 0 results — geo-targeting must be done via query text.
_SEARCH_COUNTRY = "US"

# Per-agent browser automation budget (seconds). Lower = faster /api/analyze;
# TinyFish may return partial/empty JSON under tight budgets — hotspot scores still usable.
def _agent_timeout() -> int:
    try:
        t = int(get_settings().tinyfish_agent_timeout_seconds)
        return max(10, min(t, 120))
    except Exception:
        return 22


def _search_http_timeout() -> int:
    try:
        t = int(get_settings().tinyfish_search_http_timeout_seconds)
        return max(5, min(t, 60))
    except Exception:
        return 12


def _has_tinyfish_key() -> bool:
    settings = get_settings()
    key = settings.tinyfish_api_key
    return bool(key and key != "your_tinyfish_api_key_here" and len(key) > 10)


def _search_sync(query: str, num_results: int = 10) -> list[dict]:
    """
    Synchronous TinyFish Search API call.

    Important notes discovered from live testing:
      - `location` ONLY accepts 2-letter ISO country codes (e.g. "US").
        Passing a city name or state code returns 0 results.
        → Geo-targeting must be embedded directly in the query string.
      - `num` parameter is NOT supported; result count is fixed at 10 per call.
      - Rate limit: ~5–10 req/min sustained (no hard throttling observed in tests).
    """
    if not _has_tinyfish_key():
        return []

    settings = get_settings()
    try:
        resp = requests.get(
            "https://api.search.tinyfish.ai",
            headers={"X-API-Key": settings.tinyfish_api_key},
            params={"query": query, "location": _SEARCH_COUNTRY},
            timeout=_search_http_timeout(),
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            return results[:num_results]
        else:
            print(f"[TinyFish Search] HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[TinyFish Search] Error: {e}")
    return []


def _agent_sync(url: str, goal: str, timeout: Optional[int] = None) -> Optional[dict]:
    """
    Synchronous TinyFish Agent API call (SSE streaming, collected to completion).

    Per-call wall time is capped by Settings.tinyfish_agent_timeout_seconds (default ~22s)
    so /api/analyze stays responsive; incomplete runs return empty/partial JSON.
    """
    if not _has_tinyfish_key():
        return None

    if timeout is None:
        timeout = _agent_timeout()

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
            timeout=timeout + 5,   # socket timeout slightly longer than SSE deadline
        )
        start = time.time()
        for line in resp.iter_lines():
            if time.time() - start > timeout:
                print(f"[TinyFish Agent] Timed out after {timeout}s ({url[:60]})")
                break
            if not line:
                continue
            line_str = line.decode("utf-8") if isinstance(line, bytes) else line
            if line_str.startswith("data: "):
                try:
                    event = json.loads(line_str[6:])
                    etype = event.get("type", "")
                    if etype == "COMPLETE":
                        result = event.get("result")
                        if isinstance(result, str):
                            try:
                                return json.loads(result)
                            except json.JSONDecodeError:
                                pass
                        return result
                    elif etype == "ERROR":
                        print(f"[TinyFish Agent] ERROR event: {event.get('message','')[:120]}")
                        return None
                except Exception:
                    pass
    except Exception as e:
        print(f"[TinyFish Agent] Error ({url[:50]}): {e}")
    return None


# ── Async wrappers (run synchronous calls in executor) ──────────────────────

async def search_retail_signals(query: str) -> list[dict]:
    """Async: search for live retail signals."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _search_sync, query, 10)


async def scrape_yelp_new_businesses(city_state: str, category: str = "") -> list[dict]:
    """
    Scrape Yelp for recently opened businesses — demand validation signal.
    """
    city_slug = city_state.replace(", ", "-").replace(" ", "-").lower()
    cat_param = f"find_desc={category}&" if category else ""
    url = f"https://www.yelp.com/search?{cat_param}find_loc={city_slug}&sortby=date_desc"

    goal = (
        f"You are a retail site selection analyst. On this Yelp page for {city_state}, find the "
        f"12 most recently active or newly opened businesses. "
        f"For each business, determine: (1) Did it open in the past 6 months? "
        f"(2) Is it a {category or 'retail'} establishment or related category? "
        f"(3) Does it have strong early reviews (4.0+) suggesting genuine consumer demand? "
        f"Return a JSON array of objects: "
        f'[{{"name": str, "category": str, "rating": float, "review_count": int, '
        f'"opened_recently": bool, "is_new_opening": bool, "demand_signal": "high"|"medium"|"low"}}]. '
        f"Be precise — only mark opened_recently=true if the business clearly opened in the past 6 months "
        f"based on review dates or listing metadata."
    )

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _agent_sync, url, goal, None)
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        for v in result.values():
            if isinstance(v, list):
                return v
    return []


async def scrape_loopnet_listings(city_state: str, store_size: str = "large") -> dict:
    """
    Scrape Loopnet for available commercial real estate — development readiness signal.
    """
    city_slug = city_state.split(",")[0].strip().replace(" ", "-")
    # Bug fixed: was defaulting to "AZ" — now derive state from city_state correctly
    state = city_state.split(",")[-1].strip()[:2].upper() if "," in city_state else "MN"
    url = f"https://www.loopnet.com/search/commercial-real-estate/{city_slug}-{state}/for-lease/"

    goal = (
        f"You are a commercial real estate analyst. On this Loopnet search page for {city_state}, "
        f"count and describe the available retail/commercial spaces for lease. "
        f"Focus on: (1) How many spaces are available total? "
        f"(2) What size categories are available (small <5K sqft, medium 5-25K sqft, large 25-80K sqft, big-box 80K+)? "
        f"(3) Are there any newly listed spaces from the past 90 days? "
        f"(4) Any anchor-ready spaces (large footprint that could support a big-box retailer)? "
        f"Return JSON: "
        f'{{"count": int, "anchor_ready_count": int, "new_listings_90_days": int, '
        f'"size_breakdown": {{"small": int, "medium": int, "large": int, "big_box": int}}, '
        f'"listings": [{{"address": str, "sqft": int, "listing_type": "new"|"existing", '
        f'"available": bool, "notes": str}}]}}'
    )

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _agent_sync, url, goal, None)
    if isinstance(result, dict):
        return result
    return {"count": 0, "anchor_ready_count": 0, "new_listings_90_days": 0, "listings": []}


async def search_news_signals(city_state: str, store_category: str = "retail") -> list[dict]:
    """
    Search for news signals on two tracks:
    (A) Hype/trending area signals — is this neighborhood becoming a retail destination?
    (B) New store opening announcements — what specific stores just opened or are coming?

    Key fixes:
      1. Year is now dynamic (_CURRENT_YEAR) — was hardcoded to 2025.
      2. City name is embedded in the query (not the broken `location` city param).
      3. Queries cover both current and previous year to catch late-year announcements.
    """
    city = city_state.split(",")[0].strip()
    loop = asyncio.get_event_loop()
    results = []

    # Single merged query keeps /api/analyze latency predictable (was 3× search round-trips).
    queries = [
        f'{city} ("grand opening" OR "now open" OR "coming soon") {store_category} '
        f'{_CURRENT_YEAR} OR {_PREV_YEAR}',
    ]

    for q in queries:
        batch = await loop.run_in_executor(None, _search_sync, q, 10)
        results.extend(batch)

    return results[:12]


async def scrape_city_permits(city_state: str) -> dict:
    """
    Scrape city building permit portal for recent commercial construction activity.
    """
    city = city_state.split(",")[0].strip().lower().replace(" ", "")
    state = city_state.split(",")[-1].strip().lower() if "," in city_state else "mn"

    KNOWN_PORTALS = {
        # Minneapolis Metro
        "minneapolis":     "https://www.minneapolismn.gov/business-services/permits/",
        "bloomington":     "https://www.bloomingtonmn.gov/departments/community-development/permits",
        "eden prairie":    "https://www.edenprairie.org/departments/planning-zoning-building/building-permits",
        "edenprairie":     "https://www.edenprairie.org/departments/planning-zoning-building/building-permits",
        "plymouth":        "https://www.plymouthmn.gov/departments/community-development/building-permits",
        "burnsville":      "https://www.burnsville.org/departments/community-development/building-division",
        "brooklyn center": "https://www.ci.brooklyn-center.mn.us/departments/community-development",
        "brooklyncenter":  "https://www.ci.brooklyn-center.mn.us/departments/community-development",
        "coon rapids":     "https://www.coonrapidsmn.gov/departments/community-development",
        "coonrapids":      "https://www.coonrapidsmn.gov/departments/community-development",
        "richfield":       "https://www.cityofrichfield.org/departments/community_development",
        "st. louis park":  "https://www.stlouispark.org/government/departments/inspections",
        "stlouispark":     "https://www.stlouispark.org/government/departments/inspections",
    }

    # Fallback: use state to build a plausible URL
    portal_url = KNOWN_PORTALS.get(
        city,
        KNOWN_PORTALS.get(city.replace(" ", ""),
        f"https://www.{city}{state}.gov/permits")
    )

    goal = (
        f"You are analyzing commercial building activity for {city_state}. "
        f"On this city permit portal, find permits filed in the past 90 days specifically for: "
        f"(1) New commercial or retail construction, (2) Commercial tenant improvements (a new retailer moving in), "
        f"(3) Large-format retail or mixed-use development approvals. "
        f"Do NOT count residential permits. "
        f"Return JSON: "
        f'{{"permit_count": int, "recent_commercial": int, "tenant_improvement_count": int, '
        f'"large_format_retail_count": int, '
        f'"top_permit_types": [str], "source": str, '
        f'"development_activity_level": "high"|"moderate"|"low"|"none"}}'
    )

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _agent_sync, portal_url, goal, None)
    if isinstance(result, dict) and "permit_count" in result:
        return result
    return {
        "permit_count": 0, "recent_commercial": 0,
        "tenant_improvement_count": 0, "large_format_retail_count": 0,
        "source": "unavailable", "development_activity_level": "unknown"
    }


async def scrape_new_store_openings(city_state: str, store_category: str, brand_name: str = "") -> dict:
    """
    Dedicated new store opening intelligence scrape.
    Answers: 'What stores just opened nearby, and does that make this a good location for me?'
    """
    city = city_state.split(",")[0].strip()
    category_context = f"specifically for {store_category} retailers" if store_category else "for retailers"
    brand_context = f" We are evaluating whether to open a {brand_name} store." if brand_name else ""

    url = f"https://www.yelp.com/search?find_desc={store_category}&find_loc={city_state}&sortby=date_desc"

    goal = (
        f"You are a retail site intelligence analyst evaluating {city_state} {category_context}.{brand_context} "
        f"Your job: determine whether the NEW store openings in this area validate it as a good location to open. "
        f""
        f"Find all stores that opened OR announced openings in {city_state} in the past 6 months. For each: "
        f"1. Name, category, and approximate location "
        f"2. Is it a DEMAND VALIDATOR (proves consumers exist for this category)? "
        f"3. Is it a DIRECT COMPETITOR that makes the area less attractive? "
        f"4. Does it create useful CO-TENANCY (shoppers from that store will walk by yours)? "
        f"5. Estimate the NET VERDICT: given all openings, is this area now BETTER or WORSE for opening a {store_category} store? "
        f""
        f"Also find: any CLOSURES in the past 6 months (stores that failed = warning signal). "
        f"Return JSON: "
        f'{{"site_verdict": "strong_yes"|"yes"|"neutral"|"caution"|"no", '
        f'"confidence": float 0-1, '
        f'"reasoning": str, '
        f'"demand_validation_score": int 0-100, '
        f'"saturation_risk_score": int 0-100, '
        f'"new_openings": [{{"brand": str, "category": str, "is_validator": bool, "is_competitor": bool, '
        f'"opened_date": str, "co_tenancy_score": float 0-1}}], '
        f'"closures": [{{"brand": str, "reason_if_known": str}}], '
        f'"net_new_stores": int, '
        f'"whitespace_categories": [str]}}'
    )

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _agent_sync, url, goal, None)
    if isinstance(result, dict):
        return result
    return {
        "site_verdict": "neutral", "confidence": 0.3,
        "reasoning": "Insufficient data from TinyFish agent.",
        "demand_validation_score": 50, "saturation_risk_score": 50,
        "new_openings": [], "closures": [], "net_new_stores": 0,
        "whitespace_categories": []
    }
