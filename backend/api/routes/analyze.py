"""
POST /analyze

Triggers the full 6-source data pipeline for a given lat/lon/radius,
persists everything to Supabase, and returns the run_id.

If the exact same lat/lon/radius has been fetched before, we skip the
pipeline entirely and return the cached run_id from Supabase — so the
frontend never waits 20 seconds for data it already has.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.deps import optional_user
from backend.db.client import get_client
from backend.db.persist_run import persist_run
from backend.pipeline.fetch_all import run_all

router = APIRouter()


class AnalyzeRequest(BaseModel):
    """JSON body for POST /analyze. Accepts both `radius_km` (preferred) and
    `radius` (legacy) for backward compatibility."""
    lat: float = Field(..., description="Center latitude")
    lon: float = Field(..., description="Center longitude")
    radius_km: float | None = Field(default=None, description="Search radius in km")
    radius: float | None    = Field(default=None, description="Alias for radius_km")
    store_format: str | None = Field(default=None, description="Optional store format label to persist on the run")

    @property
    def effective_radius(self) -> float:
        return self.radius_km or self.radius or 10.0


@router.post("/analyze")
def analyze(
    body: AnalyzeRequest,
    user_id: str | None = Depends(optional_user),
):
    # Round to 6 decimals (~11cm) so float drift between requests doesn't
    # break cache lookups. persist_run rounds with the same rule on insert.
    lat    = round(body.lat, 6)
    lon    = round(body.lon, 6)
    radius = round(body.effective_radius, 3)

    db = get_client()

    # ── Cache check using UNIQUE(lat, lon, radius_km) constraint ────────────
    existing = (
        db.table("analysis_runs")
        .select("id, fetched_at, user_id")
        .eq("lat", lat)
        .eq("lon", lon)
        .eq("radius_km", radius)
        .execute()
    )

    if existing.data:
        existing_run = existing.data[0]
        # Cache hit. If a logged-in user just searched a location they
        # didn't originally create, claim it for their history (only if
        # the original was anonymous — never overwrite another user's run).
        if user_id and not existing_run.get("user_id"):
            updates: dict = {"user_id": user_id}
            if body.store_format:
                updates["store_format"] = body.store_format
            db.table("analysis_runs").update(updates).eq("id", existing_run["id"]).execute()
        return {
            "run_id"    : existing_run["id"],
            "fetched_at": existing_run["fetched_at"],
            "cached"    : True,
        }

    # ── No existing run — fire the full pipeline ────────────────────────────
    try:
        data = run_all(lat=lat, lon=lon, radius_km=radius)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")

    try:
        run_id = persist_run(data, user_id=user_id, store_format=body.store_format)
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
