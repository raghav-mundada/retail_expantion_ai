"""
POST /scout

Auto-scout endpoint — given a search circle and store format, returns the
top-N spatially-diverse retail candidates inside the area.

Reuses the standard analysis_run pipeline under the hood, so the returned
`run_id` slots straight into the existing dashboard + debate routes.
"""

import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.scoring.scout import run_scout
from backend.scoring.metrics import STORE_FORMATS

router = APIRouter()


class ScoutRequest(BaseModel):
    lat: float = Field(..., description="Search circle center latitude")
    lon: float = Field(..., description="Search circle center longitude")
    radius_km: float = Field(..., gt=0, le=15, description="Search radius (km)")
    store_format: str = Field(default="Target", description="Format key from STORE_FORMATS")
    n_candidates: int = Field(default=3, ge=1, le=10)


@router.post("/scout")
def scout(body: ScoutRequest):
    if body.store_format not in STORE_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown store_format '{body.store_format}'. Available: {list(STORE_FORMATS.keys())}",
        )

    try:
        result = run_scout(
            lat          = body.lat,
            lon          = body.lon,
            radius_km    = body.radius_km,
            store_format = body.store_format,
            n_candidates = body.n_candidates,
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Scout failed: {type(e).__name__}: {e}",
        )

    return result


@router.get("/store-formats")
def list_store_formats():
    """Expose the canonical list of store formats + their config to the frontend."""
    return {
        "formats": [
            {
                "key"              : k,
                "income_sweet_spot": v["income_sweet_spot"],
                "min_population"   : v["min_population"],
                "min_parcel_acres" : v["min_parcel_acres"],
                "capex_usd"        : v["capex_usd"],
                "category_share"   : v["category_share"],
            }
            for k, v in STORE_FORMATS.items()
        ],
    }
