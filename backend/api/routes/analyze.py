"""
POST /analyze

Triggers the full 6-source data pipeline for a given lat/lon/radius,
persists everything to Supabase, and returns the run_id.

If the exact same lat/lon/radius has been fetched before, we skip the
pipeline entirely and return the cached run_id from Supabase — so the
frontend never waits 20 seconds for data it already has.
"""

from fastapi import APIRouter, HTTPException, Query
from backend.db.client import get_client
from backend.db.persist_run import persist_run
from backend.pipeline.fetch_all import run_all

router = APIRouter()


@router.post("/analyze")
def analyze(
    lat: float = Query(..., description="Center latitude"),
    lon: float = Query(..., description="Center longitude"),
    radius: float = Query(10.0, description="Search radius in km"),
):
    db = get_client()

    # ── Check if we already have data for this exact location ──────────────
    # Uses the UNIQUE(lat, lon, radius_km) constraint on analysis_runs.
    # .maybe_single() returns None when no row exists, crashing .data access.
    # Use plain .execute() instead — returns an empty list when nothing found.
    existing = (
        db.table("analysis_runs")
        .select("id, fetched_at")
        .eq("lat", lat)
        .eq("lon", lon)
        .eq("radius_km", radius)
        .execute()
    )

    if existing.data:
        # Cache hit — return the existing run_id immediately
        return {
            "run_id"    : existing.data[0]["id"],
            "fetched_at": existing.data[0]["fetched_at"],
            "cached"    : True,
        }

    # ── No existing run — fire the full pipeline ────────────────────────────
    try:
        data = run_all(lat=lat, lon=lon, radius_km=radius)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")

    # ── Persist all 10 tables to Supabase ──────────────────────────────────
    try:
        run_id = persist_run(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB persist failed: {e}")

    return {
        "run_id"    : run_id,
        "fetched_at": data["query"]["fetched_at"],
        "cached"    : False,
        "summary"   : {
            "demographics"  : data["demographics"].get("summary"),
            "stores_count"  : data["competitor_stores"].get("count", 0),
            "parcels_count" : data["commercial_parcels"].get("count", 0),
            "schools_count" : data["schools"].get("count", 0),
            "traffic"       : data["traffic_aadt"].get("summary"),
            "neighborhoods" : data["neighborhoods"].get("in_radius_count", 0),
        },
    }
