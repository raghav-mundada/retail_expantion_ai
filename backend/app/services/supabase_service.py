"""
Supabase Service — saves completed analyses and reads history.
Uses raw REST API calls (no supabase-py SDK) to avoid dependency bloat.
Service key used for writes (backend), anon key exposed to frontend for reads.
"""
import json
import requests
from datetime import datetime
from typing import Optional
from app.core.config import get_settings


def _headers(use_service_key: bool = True) -> dict:
    settings = get_settings()
    key = settings.supabase_service_key if use_service_key else settings.supabase_anon_key
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _base_url() -> str:
    return get_settings().supabase_url.rstrip("/") + "/rest/v1"


def _is_configured() -> bool:
    s = get_settings()
    return bool(s.supabase_url and s.supabase_service_key
                and "your_" not in s.supabase_service_key
                and len(s.supabase_service_key) > 20)


def save_analysis(result: dict) -> Optional[dict]:
    """
    Save a completed analysis to Supabase `analyses` table.
    Called after the orchestrator emits the final 'complete' event.
    Fails silently — never blocks the analysis pipeline.
    """
    if not _is_configured():
        print("[Supabase] Not configured, skipping save.")
        return None

    try:
        score_breakdown = result.get("score_breakdown", {})
        demographics = result.get("demographics", {})
        competitors = result.get("competitors", {})

        row = {
            "lat": result.get("lat"),
            "lng": result.get("lng"),
            "address": result.get("address", ""),
            "retailer_name": result.get("retailer_name", ""),
            "retailer_profile": json.dumps(result.get("retailer_profile", {})),
            "overall_score": result.get("overall_score"),
            "recommendation": result.get("recommendation", ""),
            "score_breakdown": json.dumps(score_breakdown),
            "hotspot_score": result.get("hotspot_score"),
            "competitor_count": competitors.get("total_count", 0) if isinstance(competitors, dict) else 0,
            "population": demographics.get("population") if isinstance(demographics, dict) else None,
            "median_income": demographics.get("median_income") if isinstance(demographics, dict) else None,
            "region_city": result.get("region_city", ""),
            "demand_score": score_breakdown.get("demand"),
            "competition_score": score_breakdown.get("competition"),
            "neighborhood_score": score_breakdown.get("neighborhood"),
        }

        resp = requests.post(
            f"{_base_url()}/analyses",
            headers=_headers(use_service_key=True),
            json=row,
            timeout=8,
        )

        if resp.status_code in (200, 201):
            print(f"[Supabase] ✅ Analysis saved → id: {resp.json()[0].get('id', '?')}")
            return resp.json()[0]
        else:
            print(f"[Supabase] Save failed {resp.status_code}: {resp.text[:200]}")
            return None

    except Exception as e:
        print(f"[Supabase] Save error: {e}")
        return None


def get_recent_analyses(limit: int = 20) -> list[dict]:
    """
    Fetch recent analyses for the history panel.
    Uses the service key (backend endpoint) or anon key with RLS.
    """
    if not _is_configured():
        return []

    try:
        resp = requests.get(
            f"{_base_url()}/analyses",
            headers=_headers(use_service_key=True),
            params={
                "order": "created_at.desc",
                "limit": limit,
                "select": "id,created_at,lat,lng,address,retailer_name,overall_score,"
                          "recommendation,hotspot_score,competitor_count,population,"
                          "median_income,region_city",
            },
            timeout=8,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"[Supabase] History fetch failed {resp.status_code}: {resp.text[:200]}")
            return []
    except Exception as e:
        print(f"[Supabase] History fetch error: {e}")
        return []
