"""
POST /api/scout — K-Means Top-N retail candidate finder.

Ported from `main:backend/api/routes/scout.py`, but adapted to our lean
Yash-merge pipeline (no Supabase ingestion required — scout pulls tracts
+ competitors + schools live from TIGERweb / ACS / Geoapify / OSM).

The frontend (`ScoutResults.tsx`) calls this at the end of the Top-3 flow
and renders the returned candidates on a leaflet map.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.models.schemas import RetailerProfile
from app.services.scout_service import run_scout
from app.services.supabase_service import cache_get, cache_set

log = logging.getLogger(__name__)
router = APIRouter()


def _scout_cache_key(lat: float, lon: float, radius_km: float, retailer: RetailerProfile, n: int) -> str:
    payload = f"{lat:.4f}|{lon:.4f}|{radius_km:.2f}|{retailer.display_name().lower()}|{n}"
    return "scout:" + hashlib.sha1(payload.encode()).hexdigest()[:16]


class ScoutRequest(BaseModel):
    lat: float = Field(..., ge=24.0, le=50.0)
    lon: float = Field(..., ge=-125.0, le=-65.0)
    radius_km: float = Field(8.0, ge=1.0, le=50.0)
    retailer: RetailerProfile
    n_candidates: int = Field(3, ge=1, le=5)


@router.post("/scout")
async def scout_endpoint(body: ScoutRequest):
    """Find the top-N best retail candidate locations in a search circle."""
    ck = _scout_cache_key(body.lat, body.lon, body.radius_km, body.retailer, body.n_candidates)

    # Warm-cache fast path
    try:
        cached = cache_get(ck)
        if cached and isinstance(cached, dict) and cached.get("candidates"):
            cached["cached"] = True
            return cached
    except Exception as e:
        log.warning(f"[/api/scout] cache_get failed: {e}")

    try:
        # run_scout is CPU-bound + sync (TIGERweb/OSM calls). Off-thread it
        # so the async loop isn't blocked while we do the K-Means fit.
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            run_scout,
            body.lat, body.lon, body.radius_km,
            body.retailer.display_name(),
            body.n_candidates,
        )
        # Fire-and-forget cache write (don't block the response)
        try:
            loop.run_in_executor(None, cache_set, ck, result)
        except Exception as e:
            log.warning(f"[/api/scout] cache_set failed: {e}")
        return result
    except Exception as e:
        log.exception("[/api/scout] failure")
        raise HTTPException(status_code=500, detail=f"Scout failed: {e}")
