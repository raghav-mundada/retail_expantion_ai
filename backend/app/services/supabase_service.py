"""
Supabase Service — single source of truth for all persistence.

Two Supabase tables:
  1. `cache`    — Key-Value store replacing all local JSON file caches
                  (FIPS geocoding, ACS data, OSM competitor results)
  2. `analyses` — Completed analysis results for history panel

The service degrades gracefully: if Supabase is not configured or
unreachable, callers fall back to their own synthetic/default logic.
"""
import json
import requests
from typing import Any, Optional
from app.core.config import get_settings


# ── Connection ───────────────────────────────────────────────────────────────

def _is_configured() -> bool:
    s = get_settings()
    return bool(
        s.supabase_url
        and s.supabase_service_key
        and not s.supabase_service_key.startswith("your_")
        and len(s.supabase_service_key) > 20
    )


def _headers() -> dict:
    key = get_settings().supabase_service_key
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _url(table: str) -> str:
    return get_settings().supabase_url.rstrip("/") + f"/rest/v1/{table}"


# ── Cache Table (KV store) ────────────────────────────────────────────────────

def cache_get(key: str) -> Optional[Any]:
    """
    Retrieve a cached value by key.
    Returns the deserialized value or None if not found / Supabase unavailable.
    """
    if not _is_configured():
        return None
    try:
        resp = requests.get(
            _url("cache"),
            headers=_headers(),
            params={"key": f"eq.{key}", "select": "value", "limit": 1},
            timeout=5,
        )
        if resp.status_code == 200:
            rows = resp.json()
            if rows:
                return rows[0]["value"]
    except Exception as e:
        print(f"[Supabase Cache] GET {key[:40]!r} failed: {e}")
    return None


def cache_set(key: str, value: Any, ttl_days: int = 365) -> bool:
    """
    Store a value in the cache table (upsert by key).
    Returns True if stored successfully.
    """
    if not _is_configured():
        return False
    try:
        payload = {"key": key, "value": value if isinstance(value, (dict, list)) else json.dumps(value)}
        resp = requests.post(
            _url("cache"),
            headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
            json=payload,
            timeout=8,
        )
        return resp.status_code in (200, 201, 204)
    except Exception as e:
        print(f"[Supabase Cache] SET {key[:40]!r} failed: {e}")
        return False


# ── Analyses Table ────────────────────────────────────────────────────────────

def save_analysis(result: dict) -> Optional[dict]:
    """
    Save a completed analysis to the `analyses` table.
    Called after orchestrator emits the final 'complete' event.
    Fails silently — never blocks the analysis pipeline.
    """
    if not _is_configured():
        print("[Supabase] Not configured — skipping save. Set SUPABASE_URL + SUPABASE_SERVICE_KEY in .env")
        return None

    try:
        score_breakdown = result.get("score_breakdown", {})
        demographics   = result.get("demographics", {})
        competitors    = result.get("competitors", {})

        row = {
            "lat":              result.get("lat"),
            "lng":              result.get("lng"),
            "address":          result.get("address", ""),
            "retailer_name":    result.get("retailer_name", ""),
            "retailer_profile": result.get("retailer_profile", {}),
            "overall_score":    result.get("overall_score"),
            "recommendation":   result.get("recommendation", ""),
            "score_breakdown":  score_breakdown,
            "hotspot_score":    result.get("hotspot_score"),
            "demand_score":     score_breakdown.get("demand"),
            "competition_score":score_breakdown.get("competition"),
            "neighborhood_score":score_breakdown.get("neighborhood"),
            "competitor_count": competitors.get("total_count", 0) if isinstance(competitors, dict) else 0,
            "population":       demographics.get("population") if isinstance(demographics, dict) else None,
            "median_income":    demographics.get("median_income") if isinstance(demographics, dict) else None,
            "region_city":      result.get("region_city", ""),
        }

        resp = requests.post(
            _url("analyses"),
            headers=_headers(),
            json=row,
            timeout=10,
        )

        if resp.status_code in (200, 201):
            saved = resp.json()
            row_id = saved[0].get("id", "?") if saved else "?"
            print(f"[Supabase] ✅ Analysis saved → id: {row_id}")
            return saved[0] if saved else None
        else:
            print(f"[Supabase] Save failed {resp.status_code}: {resp.text[:300]}")
            return None

    except Exception as e:
        print(f"[Supabase] Save error: {e}")
        return None


def get_recent_analyses(limit: int = 20) -> list[dict]:
    """Fetch recent analyses for the history panel."""
    if not _is_configured():
        return []
    try:
        resp = requests.get(
            _url("analyses"),
            headers=_headers(),
            params={
                "order":  "created_at.desc",
                "limit":  limit,
                "select": (
                    "id,created_at,lat,lng,address,retailer_name,overall_score,"
                    "recommendation,hotspot_score,competitor_count,population,"
                    "median_income,region_city"
                ),
            },
            timeout=8,
        )
        if resp.status_code == 200:
            return resp.json()
        print(f"[Supabase] History fetch {resp.status_code}: {resp.text[:200]}")
        return []
    except Exception as e:
        print(f"[Supabase] History fetch error: {e}")
        return []
