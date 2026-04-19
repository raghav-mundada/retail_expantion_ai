"""
Maps the fetch_all output dict into Supabase tables.
Called after every pipeline run.
"""

import logging
from typing import Any

from backend.db.client import get_client

log = logging.getLogger(__name__)

CHUNK = 500  # max rows per insert to stay under Supabase limits


def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _safe_float(val) -> float | None:
    try:
        return float(val) if val not in (None, "null", "") else None
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    try:
        return int(float(val)) if val not in (None, "null", "") else None
    except (TypeError, ValueError):
        return None


def persist_run(data: dict[str, Any]) -> str:
    """
    Persist a full fetch_all result dict to Supabase.
    Returns the run_id (uuid string).
    """
    db = get_client()
    q  = data["query"]

    # ── 1. analysis_runs (upsert so re-running same lat/lon is idempotent) ──
    log.info("Persisting analysis_runs...")
    run_row = {
        "lat"        : q["lat"],
        "lon"        : q["lon"],
        "radius_km"  : q["radius_km"],
        "fetched_at" : q["fetched_at"],
    }
    res = (
        db.table("analysis_runs")
        .upsert(run_row, on_conflict="lat,lon,radius_km")
        .execute()
    )
    run_id = res.data[0]["id"]
    log.info(f"  run_id = {run_id}")

    # ── 2. demographics_summaries ────────────────────────────────────────────
    demo = data.get("demographics", {})
    if "summary" in demo:
        s = demo["summary"]
        log.info("Persisting demographics_summaries...")
        db.table("demographics_summaries").upsert({
            "run_id"               : run_id,
            "tract_count"          : s.get("tract_count"),
            "total_population"     : s.get("total_population"),
            "total_households"     : s.get("total_households"),
            "median_hh_income_avg" : _safe_float(s.get("median_hh_income_area_avg")),
            "avg_poverty_rate"     : _safe_float(s.get("avg_poverty_rate")),
            "avg_owner_share"      : _safe_float(s.get("avg_owner_share")),
            "avg_renter_share"     : _safe_float(s.get("avg_renter_share")),
        }, on_conflict="run_id").execute()

    # ── 3. tract_snapshots ───────────────────────────────────────────────────
    tracts = demo.get("tracts", [])
    if tracts:
        log.info(f"Persisting {len(tracts)} tract_snapshots...")
        rows = [
            {
                "run_id"          : run_id,
                "tract_geoid"     : t.get("tract_geoid"),
                "name"            : t.get("NAME"),
                "dist_km"         : _safe_float(t.get("dist_km")),
                "centroid_lat"    : _safe_float(t.get("centroid_lat")),
                "centroid_lon"    : _safe_float(t.get("centroid_lon")),
                "total_population": _safe_int(t.get("total_population")),
                "total_households": _safe_int(t.get("total_households")),
                "median_hh_income": _safe_float(t.get("median_hh_income")),
                "owner_share"     : _safe_float(t.get("owner_share")),
                "renter_share"    : _safe_float(t.get("renter_share")),
                "poverty_rate"    : _safe_float(t.get("poverty_rate")),
            }
            for t in tracts
        ]
        for chunk in _chunks(rows, CHUNK):
            db.table("tract_snapshots").upsert(chunk, on_conflict="run_id,tract_geoid").execute()

    # ── 4. competitor_stores ─────────────────────────────────────────────────
    stores = data.get("competitor_stores", {}).get("stores", [])
    if stores:
        log.info(f"Persisting {len(stores)} competitor_stores...")
        rows = [
            {
                "run_id"   : run_id,
                "place_id" : s.get("place_id"),
                "name"     : s.get("name"),
                "shop_type": s.get("shop_type"),
                "lat"      : _safe_float(s.get("lat")),
                "lon"      : _safe_float(s.get("lon")),
                "dist_km"  : _safe_float(s.get("dist_km")),
                "address"  : s.get("address"),
            }
            for s in stores
        ]
        for chunk in _chunks(rows, CHUNK):
            db.table("competitor_stores").upsert(chunk, on_conflict="run_id,place_id").execute()

    # ── 5. parcel_summaries ──────────────────────────────────────────────────
    cp = data.get("commercial_parcels", {})
    if "summary" in cp:
        s = cp["summary"]
        log.info("Persisting parcel_summaries...")
        db.table("parcel_summaries").upsert({
            "run_id"                   : run_id,
            "total_count"              : s.get("total_count"),
            "retail_compatible_count"  : s.get("retail_compatible_count"),
            "avg_parcel_acres"         : _safe_float(s.get("avg_parcel_acres")),
            "max_parcel_acres"         : _safe_float(s.get("max_parcel_acres")),
            "commercial_type_breakdown": s.get("commercial_type_breakdown"),
        }, on_conflict="run_id").execute()

    # ── 6. parcels ───────────────────────────────────────────────────────────
    parcels = cp.get("parcels", [])
    if parcels:
        log.info(f"Persisting {len(parcels)} parcels...")
        rows = [
            {
                "run_id"              : run_id,
                "pid"                 : p.get("PID"),
                "address"             : p.get("address"),
                "zip_code"            : p.get("zip_code"),
                "lat"                 : _safe_float(p.get("latitude") or p.get("lat")),
                "lon"                 : _safe_float(p.get("longitude") or p.get("lon")),
                "dist_km"             : _safe_float(p.get("dist_km")),
                "land_use_label"      : p.get("land_use_label"),
                "commercial_type"     : p.get("commercial_type"),
                "parcel_acres"        : _safe_float(p.get("parcel_acres")),
                "is_retail_compatible": bool(p.get("is_retail_compatible")),
                "market_value"        : _safe_float(p.get("market_value")),
                "build_year"          : _safe_int(p.get("build_year")),
            }
            for p in parcels
        ]
        for chunk in _chunks(rows, CHUNK):
            db.table("parcels").upsert(chunk, on_conflict="run_id,pid").execute()

    # ── 7. schools ───────────────────────────────────────────────────────────
    schools = data.get("schools", {}).get("schools", [])
    if schools:
        log.info(f"Persisting {len(schools)} schools...")
        rows = [
            {
                "run_id"      : run_id,
                "place_id"    : s.get("place_id"),
                "name"        : s.get("name"),
                "amenity_type": s.get("amenity_type"),
                "lat"         : _safe_float(s.get("lat")),
                "lon"         : _safe_float(s.get("lon")),
                "dist_km"     : _safe_float(s.get("dist_km")),
            }
            for s in schools
        ]
        for chunk in _chunks(rows, CHUNK):
            db.table("schools").upsert(chunk, on_conflict="run_id,place_id").execute()

    # ── 8. traffic_summaries ─────────────────────────────────────────────────
    traffic = data.get("traffic_aadt", {})
    if "summary" in traffic:
        s = traffic["summary"]
        log.info("Persisting traffic_summaries...")
        db.table("traffic_summaries").upsert({
            "run_id"      : run_id,
            "point_count" : s.get("count"),
            "nearest_road": s.get("nearest_road"),
            "nearest_aadt": _safe_int(s.get("nearest_aadt")),
            "max_aadt"    : _safe_int(s.get("max_aadt")),
            "avg_aadt"    : _safe_float(s.get("avg_aadt")),
        }, on_conflict="run_id").execute()

    # ── 9. traffic_points ────────────────────────────────────────────────────
    points = traffic.get("points", [])
    if points:
        log.info(f"Persisting {len(points)} traffic_points...")
        rows = [
            {
                "run_id"     : run_id,
                "street_name": p.get("street_name"),
                "route_label": p.get("route_label"),
                "aadt"       : _safe_int(p.get("aadt")),
                "distance_m" : _safe_float(p.get("distance_m")),
                "lat"        : _safe_float(p.get("lat")),
                "lon"        : _safe_float(p.get("lon")),
            }
            for p in points
        ]
        for chunk in _chunks(rows, CHUNK):
            db.table("traffic_points").insert(chunk).execute()

    # ── 10. neighborhoods ────────────────────────────────────────────────────
    hoods = data.get("neighborhoods", {}).get("neighborhoods", [])
    if hoods:
        log.info(f"Persisting {len(hoods)} neighborhoods...")
        rows = [
            {
                "run_id"           : run_id,
                "neighborhood_id"  : str(n.get("neighborhood_id")),
                "neighborhood_name": n.get("neighborhood_name"),
                "centroid_lat"     : _safe_float(n.get("centroid_lat")),
                "centroid_lon"     : _safe_float(n.get("centroid_lon")),
                "dist_km"          : _safe_float(n.get("dist_km")),
                "in_radius"        : bool(n.get("in_radius")),
            }
            for n in hoods
        ]
        for chunk in _chunks(rows, CHUNK):
            db.table("neighborhoods").upsert(chunk, on_conflict="run_id,neighborhood_id").execute()

    log.info(f"Done — all data persisted for run_id={run_id}")
    return run_id
