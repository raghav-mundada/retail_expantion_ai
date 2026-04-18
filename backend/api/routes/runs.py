"""
GET /runs/{run_id}               — full data bundle for a run
GET /runs/{run_id}/demographics  — tract-level demographic breakdown
GET /runs/{run_id}/competitors   — competitor stores list
GET /runs/{run_id}/parcels       — commercial parcels (filterable)
GET /runs/{run_id}/schools       — schools and universities
GET /runs/{run_id}/traffic       — AADT traffic summary + points
GET /runs/{run_id}/neighborhoods — neighborhood list

All routes validate that the run_id exists before querying child tables.
The frontend uses these to populate the map and data cards.
The agents use /parcels and /competitors to build their arguments.
"""

from fastapi import APIRouter, HTTPException, Query

from backend.db.client import get_client

router = APIRouter()


def _get_run_or_404(db, run_id: str) -> dict:
    """Fetch the parent run row, raise 404 if it doesn't exist."""
    res = (
        db.table("analysis_runs")
        .select("*")
        .eq("id", run_id)
        .maybe_single()
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return res.data


# ── Full bundle ──────────────────────────────────────────────────────────────

@router.get("/runs/{run_id}")
def get_run(run_id: str):
    """
    Returns everything for a run in one shot.
    Used by the frontend on initial load to populate all map layers at once.
    """
    db  = get_client()
    run = _get_run_or_404(db, run_id)

    return {
        "run"          : run,
        "demographics" : db.table("demographics_summaries").select("*").eq("run_id", run_id).execute().data,
        "competitors"  : db.table("competitor_stores").select("*").eq("run_id", run_id).order("dist_km").execute().data,
        "parcels"      : db.table("parcels").select("*").eq("run_id", run_id).eq("is_retail_compatible", True).order("dist_km").execute().data,
        "schools"      : db.table("schools").select("*").eq("run_id", run_id).order("dist_km").execute().data,
        "traffic"      : db.table("traffic_summaries").select("*").eq("run_id", run_id).execute().data,
        "neighborhoods": db.table("neighborhoods").select("*").eq("run_id", run_id).eq("in_radius", True).order("dist_km").execute().data,
    }


# ── Demographics ─────────────────────────────────────────────────────────────

@router.get("/runs/{run_id}/demographics")
def get_demographics(
    run_id: str,
    max_dist_km: float = Query(None, description="Only return tracts within this distance"),
):
    """
    Returns the rolled-up summary plus individual census tracts.
    Agents use this to understand income distribution and population density.
    """
    db  = get_client()
    _get_run_or_404(db, run_id)

    summary = db.table("demographics_summaries").select("*").eq("run_id", run_id).execute().data

    # Optionally filter tracts by distance from center
    tract_q = db.table("tract_snapshots").select("*").eq("run_id", run_id)
    if max_dist_km is not None:
        tract_q = tract_q.lte("dist_km", max_dist_km)
    tracts = tract_q.order("dist_km").execute().data

    return {"summary": summary, "tracts": tracts}


# ── Competitor stores ────────────────────────────────────────────────────────

@router.get("/runs/{run_id}/competitors")
def get_competitors(
    run_id: str,
    max_dist_km: float = Query(None, description="Filter by distance from center"),
):
    """
    Returns competitor stores sorted by distance.
    The Bear agent uses this to argue saturation / competitive pressure.
    The gravity model uses this to compute market share decay.
    """
    db  = get_client()
    _get_run_or_404(db, run_id)

    q = db.table("competitor_stores").select("*").eq("run_id", run_id)
    if max_dist_km is not None:
        q = q.lte("dist_km", max_dist_km)

    return q.order("dist_km").execute().data


# ── Parcels ──────────────────────────────────────────────────────────────────

@router.get("/runs/{run_id}/parcels")
def get_parcels(
    run_id: str,
    retail_only: bool = Query(True, description="Only return retail-compatible parcels"),
    max_dist_km: float = Query(None, description="Filter by distance from center"),
    limit: int = Query(100, description="Max rows to return"),
):
    """
    Returns commercial parcels sorted by distance.
    The Scout agent uses this to pick the best candidate sites.
    The frontend uses this to highlight parcels on the map.
    """
    db  = get_client()
    _get_run_or_404(db, run_id)

    q = db.table("parcels").select("*").eq("run_id", run_id)

    # Filter to retail-compatible only (default on — agents only care about viable sites)
    if retail_only:
        q = q.eq("is_retail_compatible", True)

    if max_dist_km is not None:
        q = q.lte("dist_km", max_dist_km)

    return q.order("dist_km").limit(limit).execute().data


# ── Schools ──────────────────────────────────────────────────────────────────

@router.get("/runs/{run_id}/schools")
def get_schools(
    run_id: str,
    max_dist_km: float = Query(None, description="Filter by distance from center"),
):
    """
    Returns schools and universities sorted by distance.
    Used by the Bull agent as a footfall signal (schools = daytime pedestrian traffic).
    """
    db  = get_client()
    _get_run_or_404(db, run_id)

    q = db.table("schools").select("*").eq("run_id", run_id)
    if max_dist_km is not None:
        q = q.lte("dist_km", max_dist_km)

    return q.order("dist_km").execute().data


# ── Traffic ──────────────────────────────────────────────────────────────────

@router.get("/runs/{run_id}/traffic")
def get_traffic(run_id: str):
    """
    Returns the AADT traffic summary plus individual measurement points.
    High AADT = high car traffic = good for a big-box store.
    """
    db  = get_client()
    _get_run_or_404(db, run_id)

    summary = db.table("traffic_summaries").select("*").eq("run_id", run_id).execute().data
    points  = db.table("traffic_points").select("*").eq("run_id", run_id).order("distance_m").execute().data

    return {"summary": summary, "points": points}


# ── Neighborhoods ────────────────────────────────────────────────────────────

@router.get("/runs/{run_id}/neighborhoods")
def get_neighborhoods(run_id: str):
    """
    Returns all neighborhoods within the search radius sorted by distance.
    Used by the frontend to label the map and by agents for geographic context.
    """
    db  = get_client()
    _get_run_or_404(db, run_id)

    return (
        db.table("neighborhoods")
        .select("*")
        .eq("run_id", run_id)
        .eq("in_radius", True)
        .order("dist_km")
        .execute()
        .data
    )
