"""
Scout Service — K-Means Top-N retail candidate finder (ported from main).

Ported + streamlined from `backend/scoring/scout.py` + `backend/agents/K_means.py`
to live without the full Supabase ingestion pipeline: we assemble the required
tract+competitor+schools layers live from the existing Yash-merge services.

Flow:
  1. TIGERweb → tract centroids within `radius_km` of the search point
  2. ACS 2023 5-Year → demographics for those tracts (population, income, poverty)
  3. OSM (Geoapify/Overpass) → competitor stores + schools inside the circle
  4. Score every tract with the composite weighted sum (population, schools,
     competitor distance, low poverty, income, traffic-proxy)
  5. Weighted K-Means → N cluster centers → top-N candidates, sorted by score

The output contract matches the `ScoutResponse` expected by the frontend
`ScoutResults.tsx` component (ported from main).
"""
from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional

import numpy as np

from app.services.census_service import (
    get_tracts_in_radius, _fetch_acs_county, _safe_float, CENSUS_NULL,
)
from app.services.osm_service import fetch_competitors
from app.services.osm_schools_service import fetch_schools
from app.services.store_formats import (
    STORE_FORMATS, resolve_store_format, haversine_km, is_rival,
)
from app.core.config import get_settings

log = logging.getLogger(__name__)


# K-Means tract-scoring weights (match main's K_means.py)
WEIGHTS = {
    "population":           0.25,
    "schools":              0.15,
    "competitor_distance":  0.20,
    "low_poverty":          0.15,
    "income":               0.20,
    "traffic":              0.05,
}


def _norm(arr: np.ndarray) -> np.ndarray:
    lo, hi = float(arr.min()), float(arr.max())
    if hi == lo:
        return np.full_like(arr, 0.5, dtype=float)
    return (arr - lo) / (hi - lo)


def _pull_tract_demographics(tract_meta: List[Dict]) -> List[Dict]:
    """Join TIGERweb centroids with ACS 5-Year (pop, income, poverty, HH)."""
    from itertools import groupby
    settings = get_settings()

    keyfn = lambda t: (t["state"], t["county"])
    sorted_meta = sorted(tract_meta, key=keyfn)
    lookup = {t["geoid"]: t for t in tract_meta}

    out: List[Dict] = []
    for (state, county), group in groupby(sorted_meta, key=keyfn):
        wanted = {t["geoid"] for t in group}
        try:
            rows = _fetch_acs_county(state, county, settings.census_api_key)
        except Exception as e:
            log.warning(f"[Scout] ACS fetch failed for {state}/{county}: {e}")
            rows = []
        for row in rows:
            geoid = (row.get("state", "") + row.get("county", "") + row.get("tract", ""))
            if geoid not in wanted:
                continue
            meta = lookup[geoid]
            pop   = _safe_float(row.get("B01003_001E"), 0)
            hh    = _safe_float(row.get("B11001_001E"), 0)
            inc   = _safe_float(row.get("B19013_001E"), 0)
            pov_u = _safe_float(row.get("B17001_001E"), 0)
            pov_n = _safe_float(row.get("B17001_002E"), 0)
            poverty_rate = (pov_n / pov_u) if pov_u > 0 else 0.0
            if pop <= 0:
                continue
            out.append({
                "geoid":             geoid,
                "NAME":              row.get("NAME", "").split(";")[0].strip(),
                "centroid_lat":      meta["centroid_lat"],
                "centroid_lon":      meta["centroid_lon"],
                "total_population":  pop,
                "total_households":  hh,
                "median_hh_income":  inc,
                "poverty_rate":      round(poverty_rate, 4),
                "dist_km":           meta["dist_km"],
            })
    return out


# ── Per-tract feature helpers ───────────────────────────────────────────────

def _school_count_2km(lat: float, lon: float, schools: List[Dict]) -> int:
    return sum(
        1 for s in schools
        if s.get("lat") and s.get("lng")
        and haversine_km(lat, lon, s["lat"], s["lng"]) <= 2.0
    )


def _nearest_comp_km(lat: float, lon: float, competitors: List[Dict]) -> Optional[float]:
    dists = []
    for c in competitors:
        clat = c.get("lat")
        clng = c.get("lng") or c.get("lon")
        if clat is None or clng is None:
            continue
        dists.append(haversine_km(lat, lon, clat, clng))
    return min(dists) if dists else None


def _traffic_proxy(lat: float, lon: float, center_lat: float, center_lon: float) -> float:
    """
    Lightweight traffic proxy: we don't have AADT data, so we approximate by
    *inverse* distance from the search center — the assumption being the user
    dropped the pin on something interesting (intersection, corridor), so
    nearby tracts see more traffic than distant rural ones.
    """
    d = max(haversine_km(lat, lon, center_lat, center_lon), 0.25)
    # Saturating curve: 0.25km → ~20000 AADT proxy, 10km → ~2500.
    return float(round(20000.0 / (d ** 0.6)))


# ── K-Means scoring (matches main's K_means.score_tracts + find_gmm_points) ──

def _score_tracts(
    tracts: List[Dict],
    schools: List[Dict],
    competitors: List[Dict],
    search_lat: float,
    search_lon: float,
) -> List[Dict]:
    if not tracts:
        return []
    pop = np.array([t["total_population"] for t in tracts], dtype=float)
    inc = np.array([t["median_hh_income"] for t in tracts], dtype=float)
    pov = np.array([t["poverty_rate"] for t in tracts], dtype=float)

    school_counts = np.array(
        [_school_count_2km(t["centroid_lat"], t["centroid_lon"], schools) for t in tracts],
        dtype=float,
    )
    comp_dists = np.array(
        [
            (_nearest_comp_km(t["centroid_lat"], t["centroid_lon"], competitors) or 5.0)
            for t in tracts
        ],
        dtype=float,
    )
    traffic = np.array(
        [_traffic_proxy(t["centroid_lat"], t["centroid_lon"], search_lat, search_lon) for t in tracts],
        dtype=float,
    )

    scores = (
        WEIGHTS["population"]          * _norm(pop)           +
        WEIGHTS["schools"]             * _norm(school_counts) +
        WEIGHTS["competitor_distance"] * _norm(comp_dists)    +
        WEIGHTS["low_poverty"]         * _norm(1.0 - pov)     +
        WEIGHTS["income"]              * _norm(inc)           +
        WEIGHTS["traffic"]             * _norm(traffic)
    )

    for i, t in enumerate(tracts):
        t["density_score"]     = round(float(scores[i]), 4)
        t["school_count_2km"]  = int(school_counts[i])
        t["nearest_comp_km"]   = round(float(comp_dists[i]), 3)
        t["avg_traffic_aadt"]  = round(float(traffic[i]), 0)

    return tracts


def _kmeans_candidates(tracts: List[Dict], n: int) -> List[Dict]:
    """Weighted K-Means → n cluster centers → sorted top-N candidates."""
    # Avoid pulling sklearn at import time (slow cold-start) — lazy import.
    try:
        from sklearn.cluster import KMeans
    except Exception as e:
        log.warning(f"[Scout] sklearn unavailable ({e}); falling back to top-N tracts")
        return _fallback_topn(tracts, n)

    if not tracts:
        return []

    coords  = np.array([[t["centroid_lat"], t["centroid_lon"]] for t in tracts], dtype=float)
    weights = np.array([t["density_score"] for t in tracts], dtype=float)
    k = min(max(n, 1), len(tracts))

    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    km.fit(coords, sample_weight=weights)

    out: List[Dict] = []
    for center in km.cluster_centers_:
        idx = int(np.sqrt(((coords - center) ** 2).sum(axis=1)).argmin())
        t = tracts[idx]
        out.append({
            "lat":             round(float(center[0]), 6),
            "lng":             round(float(center[1]), 6),
            "density_score":   round(float(weights[idx]), 4),
            "nearest_tract":   t.get("NAME", "Unknown tract"),
            "median_income":   round(float(t["median_hh_income"]), 0),
            "population":      int(t["total_population"]),
            "school_count_2km": int(t["school_count_2km"]),
            "nearest_comp_km": t["nearest_comp_km"],
            "avg_traffic_aadt": int(t["avg_traffic_aadt"]),
        })
    return sorted(out, key=lambda x: x["density_score"], reverse=True)


def _fallback_topn(tracts: List[Dict], n: int) -> List[Dict]:
    best = sorted(tracts, key=lambda t: t["density_score"], reverse=True)[:n]
    return [{
        "lat": t["centroid_lat"], "lng": t["centroid_lon"],
        "density_score":    t["density_score"],
        "nearest_tract":    t.get("NAME", "Unknown tract"),
        "median_income":    round(float(t["median_hh_income"]), 0),
        "population":       int(t["total_population"]),
        "school_count_2km": int(t["school_count_2km"]),
        "nearest_comp_km":  t["nearest_comp_km"],
        "avg_traffic_aadt": int(t["avg_traffic_aadt"]),
    } for t in best]


def _why_it_wins(c: Dict, fmt: Dict) -> List[str]:
    """Human-readable breakdown — shown in ScoutResults.tsx."""
    why: List[str] = []
    low, high = fmt["income_sweet_spot"]
    if low <= c["median_income"] <= high:
        why.append(f"Median income ${c['median_income']:,.0f} sits in the {fmt_name_display(fmt)} sweet spot")
    elif c["median_income"] > 0:
        bias = "above" if c["median_income"] > high else "below"
        why.append(f"Median income ${c['median_income']:,.0f} is {bias} the format's sweet spot (${low:,}–${high:,})")

    if c["population"] >= fmt["min_population"]:
        why.append(f"Trade-area population {c['population']:,} clears the {fmt['min_population']:,} viability threshold")
    else:
        why.append(f"Trade-area population {c['population']:,} is below {fmt['min_population']:,} — thin market")

    if c["nearest_comp_km"] is not None:
        if c["nearest_comp_km"] >= 3.0:
            why.append(f"Nearest direct rival {c['nearest_comp_km']:.1f} km away — strong opportunity")
        elif c["nearest_comp_km"] <= 1.0:
            why.append(f"Direct rival only {c['nearest_comp_km']:.1f} km away — contested corridor")

    if c["school_count_2km"] >= 5:
        why.append(f"{c['school_count_2km']} schools within 2 km — family foot-traffic signal")
    elif c["school_count_2km"] == 0:
        why.append("No schools within 2 km — lower daytime family traffic")

    return why[:4]


def fmt_name_display(fmt: Dict) -> str:
    """Return a human-friendly format name via reverse-lookup."""
    for name, v in STORE_FORMATS.items():
        if v is fmt:
            return name
    return "retailer"


# ── Public entry point ──────────────────────────────────────────────────────

def run_scout(
    lat: float,
    lon: float,
    radius_km: float,
    display_name: str,
    n_candidates: int = 3,
) -> Dict:
    """
    Find the top-N best retail candidate locations inside a search circle.
    Returns a dict compatible with the frontend `ScoutResponse` type.
    """
    fmt_name = resolve_store_format(display_name)
    fmt      = STORE_FORMATS[fmt_name]

    lat       = round(float(lat), 6)
    lon       = round(float(lon), 6)
    radius_km = round(float(radius_km), 3)

    # ── 1. TIGERweb tracts ────────────────────────────────────────────────
    tract_meta = get_tracts_in_radius(lat, lon, radius_km) or []

    # ── 2. ACS enrichment ─────────────────────────────────────────────────
    tracts_full = _pull_tract_demographics(tract_meta) if tract_meta else []

    # ── 3. OSM layers (filter competitors to direct rivals only) ─────────
    radius_miles = radius_km / 1.60934
    try:
        all_competitors = fetch_competitors(lat, lon, radius_miles) or []
    except Exception:
        all_competitors = []
    direct_rivals = [c for c in all_competitors if is_rival(c.get("name", ""), fmt_name)]

    try:
        schools = fetch_schools(lat, lon, radius_miles) or []
    except Exception:
        schools = []

    if not tracts_full:
        return {
            "search":       {"lat": lat, "lon": lon, "radius_km": radius_km},
            "store_format": fmt_name,
            "summary":      {"tracts_considered": 0, "valid_tracts": 0,
                             "rivals_considered": len(direct_rivals), "schools": len(schools)},
            "candidates":   [],
        }

    # ── 4. Score tracts (K-Means composite) ──────────────────────────────
    scored = _score_tracts(tracts_full, schools, direct_rivals, lat, lon)

    # ── 5. K-Means centers → sorted top-N ────────────────────────────────
    picked = _kmeans_candidates(scored, n_candidates)
    for i, c in enumerate(picked, 1):
        c["rank"] = i
        c["why_it_wins"] = _why_it_wins(c, fmt)

    return {
        "search":       {"lat": lat, "lon": lon, "radius_km": radius_km},
        "store_format": fmt_name,
        "summary":      {
            "tracts_considered": len(tract_meta),
            "valid_tracts":      len(tracts_full),
            "rivals_considered": len(direct_rivals),
            "schools":           len(schools),
        },
        "candidates":   picked,
    }
