"""
Auto-Scout — finds the top-N best retail candidate locations inside a
user-bounded search circle.

Algorithm (deterministic, no LLM in the loop):

  1. ONE big fetch: pull every parcel, competitor, tract, school, traffic
     point inside the search area. Persist to Supabase as one analysis_run.
  2. Score every retail-compatible parcel using format-aware demand + Huff.
  3. Spatial diversification (NMS / non-maximum suppression):
        sort parcels by score DESC, greedily keep top-N that are at least
        MIN_SPACING km apart from each already-accepted parcel.
     This guarantees recommendations live in DIFFERENT neighborhoods, not
     three lots in the same shopping district.

Output: a `run_id` (the underlying analysis run, reusable by the dashboard
+ debate flow) and a ranked list of N candidates with all the stats a
human operator needs to make a deep-dive call.
"""

from __future__ import annotations

import math
from typing import Any

from backend.db.client import get_client
from backend.db.persist_run import persist_run
from backend.pipeline.fetch_all import run_all
from backend.scoring.metrics import (
    STORE_FORMATS,
    _competitor_brand_weight,
    _haversine_km,
    _normalize,
    _spending_index,
)


# ─────────────────────────────────────────────────────────────────────────────
# Per-parcel feature engineering — pull spatial signals around each parcel
# ─────────────────────────────────────────────────────────────────────────────

def _features_for_parcel(
    parcel: dict,
    tracts: list[dict],
    competitors: list[dict],
    schools: list[dict],
    traffic_points: list[dict],
    store_format: str,
) -> dict:
    """
    Compute the local context for ONE parcel:
      • pop_1km, hh_1km, income_1km     — sum/weighted-avg of nearby tracts
      • nearest_rival_km, rivals_1km   — direct rivals only (format-aware)
      • schools_2km                    — proxy for daytime foot traffic
      • avg_aadt_1km                   — mean of nearby road counts
      • huff_capture                   — gravity model probability vs rivals
    """
    fmt = STORE_FORMATS.get(store_format, STORE_FORMATS["Target"])
    rival_keywords = fmt.get("rival_keywords", [])
    p_lat = parcel.get("lat")
    p_lon = parcel.get("lon")
    if p_lat is None or p_lon is None:
        return {}

    # ── Demographics within 1 km ───────────────────────────────────────────
    pop_1km, hh_1km, income_num, income_den, poverty_sum, poverty_n = 0, 0, 0.0, 0.0, 0.0, 0
    for t in tracts:
        t_lat = t.get("centroid_lat") or t.get("lat")
        t_lon = t.get("centroid_lon") or t.get("lon")
        if t_lat in (None, "null") or t_lon in (None, "null"):
            continue
        d = _haversine_km(p_lat, p_lon, float(t_lat), float(t_lon))
        if d > 1.0:
            continue
        hh   = t.get("total_households") or 0
        pop  = t.get("total_population") or 0
        inc  = t.get("median_hh_income") or 0
        pov  = t.get("poverty_rate") or 0
        pop_1km    += pop
        hh_1km     += hh
        if hh and inc:
            income_num += hh * inc
            income_den += hh
        poverty_sum += pov
        poverty_n   += 1

    median_income_1km = (income_num / income_den) if income_den else 0
    poverty_1km       = (poverty_sum / poverty_n) if poverty_n else 0.15

    # ── Competition — direct rivals only ──────────────────────────────────
    is_rival = lambda name: any(kw in (name or "").lower() for kw in rival_keywords)
    nearest_rival_km = None
    nearest_rival_name = None
    rivals_1km = 0
    rival_distances: list[tuple[float, str]] = []
    for c in competitors:
        c_lat = c.get("lat")
        c_lon = c.get("lon")
        if c_lat is None or c_lon is None:
            continue
        if not is_rival(c.get("name", "")):
            continue
        d = _haversine_km(p_lat, p_lon, c_lat, c_lon)
        rival_distances.append((d, c.get("name", "")))
        if d <= 1.0:
            rivals_1km += 1

    if rival_distances:
        rival_distances.sort(key=lambda x: x[0])
        nearest_rival_km, nearest_rival_name = rival_distances[0]

    # ── Schools within 2 km (proxy for daytime activity) ──────────────────
    schools_2km = 0
    for s in schools:
        s_lat = s.get("lat")
        s_lon = s.get("lon")
        if s_lat is None or s_lon is None:
            continue
        if _haversine_km(p_lat, p_lon, s_lat, s_lon) <= 2.0:
            schools_2km += 1

    # ── Traffic — average AADT within 1 km ────────────────────────────────
    aadt_vals = []
    for tp in traffic_points:
        tp_lat = tp.get("lat")
        tp_lon = tp.get("lon")
        aadt   = tp.get("aadt") or 0
        if tp_lat is None or tp_lon is None or aadt <= 0:
            continue
        if _haversine_km(p_lat, p_lon, tp_lat, tp_lon) <= 1.0:
            aadt_vals.append(aadt)
    avg_aadt_1km = (sum(aadt_vals) / len(aadt_vals)) if aadt_vals else 0

    # ── Huff capture for THIS parcel vs all direct rivals ─────────────────
    BETA = 2.0
    MIN_DIST = 0.3
    candidate_attractiveness = fmt["brand_weight"]

    captured_hh, total_hh = 0.0, 0
    for t in tracts:
        t_lat = t.get("centroid_lat") or t.get("lat")
        t_lon = t.get("centroid_lon") or t.get("lon")
        if t_lat in (None, "null") or t_lon in (None, "null"):
            continue
        hh = t.get("total_households") or 0
        if not hh:
            continue
        d_to_us = max(_haversine_km(p_lat, p_lon, float(t_lat), float(t_lon)), MIN_DIST)
        attr_us = candidate_attractiveness / (d_to_us ** BETA)

        attr_rivals = 0.0
        for c in competitors:
            c_lat = c.get("lat")
            c_lon = c.get("lon")
            if c_lat is None or c_lon is None:
                continue
            if not is_rival(c.get("name", "")):
                continue
            d_to_r = max(_haversine_km(float(t_lat), float(t_lon), c_lat, c_lon), MIN_DIST)
            attr_rivals += _competitor_brand_weight(c.get("name", "")) / (d_to_r ** BETA)

        denom = attr_us + attr_rivals
        if denom <= 0:
            continue
        captured_hh += hh * (attr_us / denom)
        total_hh    += hh

    huff_capture_pct = (captured_hh / total_hh * 100) if total_hh else 0.0

    return {
        "pop_1km"            : int(pop_1km),
        "hh_1km"             : int(hh_1km),
        "median_income_1km"  : round(median_income_1km, 0),
        "poverty_1km"        : round(poverty_1km, 3),
        "nearest_rival_km"   : round(nearest_rival_km, 2) if nearest_rival_km is not None else None,
        "nearest_rival_name" : nearest_rival_name,
        "rivals_1km"         : rivals_1km,
        "schools_2km"        : schools_2km,
        "avg_aadt_1km"       : round(avg_aadt_1km, 0),
        "huff_capture_pct"   : round(huff_capture_pct, 2),
        "captured_hh"        : round(captured_hh),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Composite score per parcel — weighted blend of normalized signals
# ─────────────────────────────────────────────────────────────────────────────

# Per-parcel scoring weights. Sum to 1.0. Different spirit than the
# location-level COMPOSITE_WEIGHTS in metrics.py — here we want to rank
# *parcels* against each other, so demand & huff dominate.
PARCEL_WEIGHTS = {
    "huff"           : 0.35,   # winning the demand vs rivals
    "demand"         : 0.25,   # raw size of the local market
    "income_fit"     : 0.15,
    "rival_distance" : 0.10,   # closer rivals = worse
    "traffic"        : 0.10,
    "schools"        : 0.05,   # mild positive (foot traffic)
}


def _income_fit_score(income: float, store_format: str) -> float:
    """Cheap version of metrics.compute_income_fit — 0–100 score."""
    fmt = STORE_FORMATS.get(store_format, STORE_FORMATS["Target"])
    low, high = fmt["income_sweet_spot"]
    if income <= 0:
        return 0
    if income < low * 0.5 or income > high * 1.5:
        return 0
    if low <= income <= high:
        midpoint = (low + high) / 2
        return 100 * (1 - (abs(income - midpoint) / ((high - low) / 2)) * 0.3)
    if income < low:
        return 70 * (income / low)
    return max(0, 70 * (1 - ((income - high) / high)))


def _score_parcel(features: dict, parcel: dict, store_format: str) -> dict:
    """Blend the per-parcel features into a 0–100 final score."""
    huff_score   = _normalize(features["huff_capture_pct"], 1.0, 30.0)
    demand_score = _normalize(features["hh_1km"], 500, 8_000)
    income_score = _income_fit_score(features["median_income_1km"], store_format)
    rival_dist   = features["nearest_rival_km"] if features["nearest_rival_km"] is not None else 5.0
    rival_score  = _normalize(rival_dist, 0.0, 3.0)         # farther = better
    traffic_score = _normalize(features["avg_aadt_1km"], 2_000, 30_000)
    school_score  = _normalize(features["schools_2km"], 0, 10)

    final = round(
        PARCEL_WEIGHTS["huff"]           * huff_score   +
        PARCEL_WEIGHTS["demand"]         * demand_score +
        PARCEL_WEIGHTS["income_fit"]     * income_score +
        PARCEL_WEIGHTS["rival_distance"] * rival_score  +
        PARCEL_WEIGHTS["traffic"]        * traffic_score +
        PARCEL_WEIGHTS["schools"]        * school_score,
        1,
    )

    return {
        "final_score" : final,
        "breakdown"   : {
            "huff"          : round(huff_score, 1),
            "demand"        : round(demand_score, 1),
            "income_fit"    : round(income_score, 1),
            "rival_distance": round(rival_score, 1),
            "traffic"       : round(traffic_score, 1),
            "schools"       : round(school_score, 1),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# NMS — keep top-N parcels that are spatially diverse
# ─────────────────────────────────────────────────────────────────────────────

def _spatial_nms(
    ranked: list[dict],
    n: int,
    min_spacing_km: float,
) -> list[dict]:
    """
    Greedy non-maximum suppression: walk parcels from highest score down,
    keep any that's at least `min_spacing_km` from every already-kept parcel.
    Stops once we have N. This is the only thing that prevents all 3
    recommendations from clustering in the same hot block.
    """
    selected: list[dict] = []
    for p in ranked:
        if all(
            _haversine_km(p["lat"], p["lon"], s["lat"], s["lon"]) >= min_spacing_km
            for s in selected
        ):
            selected.append(p)
            if len(selected) == n:
                break
    return selected


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_scout(
    lat: float,
    lon: float,
    radius_km: float,
    store_format: str = "Target",
    n_candidates: int = 3,
    user_id: str | None = None,
) -> dict:
    """
    Find top-N spatially-diverse retail candidates inside a circle.

    Steps: cache check → fetch (or reuse) → score every parcel → NMS → return.
    Returns the underlying `run_id` so the frontend can hand it straight to
    the dashboard / debate flow without refetching.
    """
    db = get_client()
    fmt = STORE_FORMATS.get(store_format, STORE_FORMATS["Target"])
    min_acres = fmt["min_parcel_acres"]

    # Round to 6 decimals (~11cm) so float precision drift between requests
    # can't bypass the cache and create duplicate runs for the same point.
    lat       = round(float(lat), 6)
    lon       = round(float(lon), 6)
    radius_km = round(float(radius_km), 3)

    # ── 1. Cache check or fetch ──────────────────────────────────────────
    existing = (
        db.table("analysis_runs")
        .select("id")
        .eq("lat", lat).eq("lon", lon).eq("radius_km", radius_km)
        .execute()
    )

    cached = False
    run_id: str | None = None

    if existing.data:
        candidate_run_id = existing.data[0]["id"]
        # Claim ownership for the logged-in user if it was an anonymous run
        if user_id:
            db.table("analysis_runs").update({
                "user_id"     : user_id,
                "store_format": store_format,
            }).eq("id", candidate_run_id).is_("user_id", "null").execute()
        # Make sure the cached tracts have centroid coords — older runs
        # were persisted before we added these columns and would silently
        # produce zero scores. If they're missing, blow it away and refetch.
        sample = (
            db.table("tract_snapshots")
            .select("centroid_lat")
            .eq("run_id", candidate_run_id)
            .not_.is_("centroid_lat", "null")
            .limit(1)
            .execute()
            .data
        )
        if sample:
            run_id = candidate_run_id
            cached = True
        else:
            # Stale cache — drop the parent and let cascades clean children
            db.table("analysis_runs").delete().eq("id", candidate_run_id).execute()

    if run_id is None:
        data   = run_all(lat=lat, lon=lon, radius_km=radius_km)
        run_id = persist_run(data, user_id=user_id, store_format=store_format)

    # ── 2. Pull what we need from Supabase ───────────────────────────────
    parcels = (
        db.table("parcels")
        .select("*")
        .eq("run_id", run_id)
        .eq("is_retail_compatible", True)
        .execute()
        .data
    ) or []
    tracts = db.table("tract_snapshots").select("*").eq("run_id", run_id).execute().data or []
    competitors = db.table("competitor_stores").select("*").eq("run_id", run_id).execute().data or []
    schools = db.table("schools").select("*").eq("run_id", run_id).execute().data or []
    traffic_points = db.table("traffic_points").select("*").eq("run_id", run_id).execute().data or []

    # ── 3. Filter parcels by format minimum size ─────────────────────────
    candidates_pool = [
        p for p in parcels
        if (p.get("parcel_acres") or 0) >= min_acres
        and p.get("lat") is not None
        and p.get("lon") is not None
    ]

    if not candidates_pool:
        return {
            "run_id"      : run_id,
            "store_format": store_format,
            "search"      : {"lat": lat, "lon": lon, "radius_km": radius_km},
            "candidates"  : [],
            "summary"     : {
                "parcels_considered": 0,
                "parcels_in_box"    : len(parcels),
                "min_acres_filter"  : min_acres,
                "cached"            : cached,
            },
        }

    # ── 4. Score every candidate parcel ──────────────────────────────────
    scored = []
    for p in candidates_pool:
        features = _features_for_parcel(
            p, tracts, competitors, schools, traffic_points, store_format
        )
        if not features:
            continue
        score   = _score_parcel(features, p, store_format)
        scored.append({
            "lat"             : p["lat"],
            "lon"             : p["lon"],
            "address"         : p.get("address"),
            "parcel_acres"    : p.get("parcel_acres"),
            "market_value"    : p.get("market_value"),
            "commercial_type" : p.get("commercial_type"),
            "final_score"     : score["final_score"],
            "breakdown"       : score["breakdown"],
            "features"        : features,
        })

    # ── 5. Sort + NMS spatial diversification ────────────────────────────
    scored.sort(key=lambda x: x["final_score"], reverse=True)

    # spacing scales with the search area — bigger box → spread out more
    min_spacing_km = max(1.0, radius_km / (n_candidates + 1))
    top = _spatial_nms(scored, n_candidates, min_spacing_km)

    # rank labels
    for i, c in enumerate(top, 1):
        c["rank"] = i

    return {
        "run_id"      : run_id,
        "store_format": store_format,
        "search"      : {"lat": lat, "lon": lon, "radius_km": radius_km},
        "candidates"  : top,
        "summary"     : {
            "parcels_considered" : len(scored),
            "parcels_in_box"     : len(parcels),
            "min_acres_filter"   : min_acres,
            "min_spacing_km"     : round(min_spacing_km, 2),
            "cached"             : cached,
            "rivals_considered"  : sum(1 for c in competitors if any(
                kw in (c.get("name") or "").lower()
                for kw in fmt.get("rival_keywords", [])
            )),
        },
    }
