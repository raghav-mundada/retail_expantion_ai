"""
/me/* — endpoints scoped to the currently logged-in Supabase user.

Currently:
  • GET /me/runs — past analysis runs ordered by most recent
"""

from fastapi import APIRouter, Depends, Query

from backend.api.deps import require_user
from backend.db.client import get_client

router = APIRouter()


@router.get("/me/runs")
def list_my_runs(
    user_id: str = Depends(require_user),
    limit: int   = Query(default=50, ge=1, le=200),
):
    """
    Returns the runs this user has created or claimed, with a quick summary
    pulled from `demographics_summaries` so the history page can render
    "12 tracts · 87,500 HH" badges without N+1 queries.
    """
    db = get_client()

    runs = (
        db.table("analysis_runs")
        .select(
            "id, lat, lon, radius_km, store_format, label, fetched_at, created_at"
        )
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    ) or []

    if not runs:
        return {"runs": []}

    run_ids = [r["id"] for r in runs]

    # Pull per-run demographic summaries in one shot
    demos = (
        db.table("demographics_summaries")
        .select("run_id, tract_count, total_population, total_households, median_hh_income_avg")
        .in_("run_id", run_ids)
        .execute()
        .data
    ) or []
    demo_by_run = {d["run_id"]: d for d in demos}

    # Counts of competitors / parcels for badges
    stores = (
        db.table("competitor_stores")
        .select("run_id", count="exact")
        .in_("run_id", run_ids)
        .execute()
    )
    # Supabase Python client doesn't easily group by, so count individually
    # for the small list (<= 50). Cheap.
    store_counts = {rid: 0 for rid in run_ids}
    for row in stores.data or []:
        store_counts[row["run_id"]] = store_counts.get(row["run_id"], 0) + 1

    enriched = []
    for r in runs:
        d = demo_by_run.get(r["id"], {}) or {}
        enriched.append({
            **r,
            "summary": {
                "tract_count"       : d.get("tract_count"),
                "total_population"  : d.get("total_population"),
                "total_households"  : d.get("total_households"),
                "median_hh_income"  : d.get("median_hh_income_avg"),
                "competitors_count" : store_counts.get(r["id"], 0),
            },
        })

    return {"runs": enriched}
