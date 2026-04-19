"""
backend/agents/K_means.py
──────────────────────────
KMeans-based optimal search point finder using full composite tract score.

Tract score uses all 6 data sources:
  population, schools, competitor distance, poverty, income, traffic

Steps:
  1. Score every tract using weighted sum of normalized factors
  2. Fit KMeans weighted by composite score
  3. Return n cluster centers as optimal search points
"""

import math
import numpy as np
from sklearn.cluster import KMeans

# Weights — must sum to 1.0
WEIGHTS = {
    "population"          : 0.25,
    "schools"             : 0.15,
    "competitor_distance" : 0.20,
    "low_poverty"         : 0.15,
    "income"              : 0.20,
    "traffic"             : 0.05,
}


def norm(arr: np.ndarray) -> np.ndarray:
    lo, hi = arr.min(), arr.max()
    if hi == lo:
        return np.full_like(arr, 0.5)
    return (arr - lo) / (hi - lo)


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def get_school_count(tract_lat, tract_lon, schools, radius_km=2.0):
    """Count schools within radius_km of tract centroid."""
    count = 0
    for s in schools:
        slat = s.get("lat") or s.get("latitude")
        slon = s.get("lon") or s.get("longitude")
        if slat and slon:
            if haversine_km(tract_lat, tract_lon, slat, slon) <= radius_km:
                count += 1
    return count


def get_nearest_competitor_km(tract_lat, tract_lon, competitors):
    """Distance in km to nearest competitor store."""
    min_dist = 999.0
    for c in competitors:
        clat = c.get("lat") or c.get("latitude")
        clon = c.get("lon") or c.get("longitude")
        if clat and clon:
            d = haversine_km(tract_lat, tract_lon, clat, clon)
            if d < min_dist:
                min_dist = d
    return min_dist if min_dist < 999.0 else None


def get_avg_traffic(tract_lat, tract_lon, traffic_points, radius_km=2.0):
    """Average AADT within radius_km of tract centroid."""
    vals = []
    for p in traffic_points:
        plat = p.get("lat")
        plon = p.get("lon")
        aadt = p.get("aadt") or 0
        if plat and plon and aadt > 0:
            if haversine_km(tract_lat, tract_lon, plat, plon) <= radius_km:
                vals.append(aadt)
    return sum(vals) / len(vals) if vals else 0.0


def score_tracts(data: dict) -> list[dict]:
    """
    Score every tract using composite weighted sum.
    Uses all 6 data sources from the pipeline output.
    """
    tracts      = data.get("demographics", {}).get("tracts", [])
    schools     = data.get("schools", {}).get("schools", [])
    competitors = data.get("competitor_stores", {}).get("stores", [])
    traffic_pts = data.get("traffic_aadt", {}).get("points", [])

    # filter tracts with valid centroids
    valid = [
        t for t in tracts
        if t.get("centroid_lat") not in (None, "null")
        and t.get("centroid_lon") not in (None, "null")
        and (t.get("total_population") or 0) > 0
    ]

    if not valid:
        return []

    print(f"  [kmeans] scoring {len(valid)} tracts across 6 factors")

    # compute raw factor values per tract
    pop      = np.array([t.get("total_population") or 0   for t in valid], dtype=float)
    inc      = np.array([t.get("median_hh_income")  or 0  for t in valid], dtype=float)
    pov      = np.array([t.get("poverty_rate")       or 0 for t in valid], dtype=float)

    school_counts = np.array([
        get_school_count(
            t["centroid_lat"], t["centroid_lon"], schools
        ) for t in valid
    ], dtype=float)

    comp_dists = np.array([
        get_nearest_competitor_km(
            t["centroid_lat"], t["centroid_lon"], competitors
        ) or 5.0
        for t in valid
    ], dtype=float)

    traffic = np.array([
        get_avg_traffic(
            t["centroid_lat"], t["centroid_lon"], traffic_pts
        ) for t in valid
    ], dtype=float)

    # weighted sum of normalized factors
    scores = (
        WEIGHTS["population"]          * norm(pop)           +
        WEIGHTS["schools"]             * norm(school_counts) +
        WEIGHTS["competitor_distance"] * norm(comp_dists)    +
        WEIGHTS["low_poverty"]         * norm(1 - pov)       +
        WEIGHTS["income"]              * norm(inc)           +
        WEIGHTS["traffic"]             * norm(traffic)
    )

    for i, t in enumerate(valid):
        t["density_score"]      = round(float(scores[i]), 4)
        t["school_count_2km"]   = int(school_counts[i])
        t["nearest_comp_km"]    = round(float(comp_dists[i]), 3)
        t["avg_traffic_aadt"]   = round(float(traffic[i]), 0)

    return valid


def find_gmm_points(tracts_or_data, n_points: int = 5) -> list[dict]:
    """
    Main entry point. Accepts either:
      - list of tracts (legacy, demographic scoring only)
      - full pipeline data dict (new, composite scoring)

    Fits KMeans weighted by composite score.
    Returns n_points optimal search locations.
    """
    # handle both calling conventions
    if isinstance(tracts_or_data, dict):
        scored = score_tracts(tracts_or_data)
    else:
        # legacy: just tracts list — fall back to demographic scoring only
        scored = _score_tracts_demographic(tracts_or_data)

    if not scored:
        return []

    coords  = np.array([[t["centroid_lat"], t["centroid_lon"]] for t in scored])
    weights = np.array([t["density_score"] for t in scored])

    k = min(n_points, len(scored))

    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    km.fit(coords, sample_weight=weights)

    points = []
    for center in km.cluster_centers_:
        nearest_idx = np.sqrt(((coords - center) ** 2).sum(axis=1)).argmin()
        t = scored[nearest_idx]
        points.append({
            "lat"              : round(float(center[0]), 6),
            "lon"              : round(float(center[1]), 6),
            "density_score"    : round(float(weights[nearest_idx]), 4),
            "nearest_tract"    : t.get("NAME", ""),
            "school_count_2km" : t.get("school_count_2km", 0),
            "nearest_comp_km"  : t.get("nearest_comp_km", None),
            "avg_traffic_aadt" : t.get("avg_traffic_aadt", 0),
        })

    return sorted(points, key=lambda x: x["density_score"], reverse=True)


def _score_tracts_demographic(tracts: list[dict]) -> list[dict]:
    """Fallback demographic-only scoring for legacy calls."""
    valid = [
        t for t in tracts
        if t.get("centroid_lat") not in (None, "null")
        and t.get("centroid_lon") not in (None, "null")
        and (t.get("total_population") or 0) > 0
    ]
    if not valid:
        return []

    pop = np.array([t.get("total_population") or 0   for t in valid], dtype=float)
    inc = np.array([t.get("median_hh_income")  or 0  for t in valid], dtype=float)
    pov = np.array([t.get("poverty_rate")       or 0 for t in valid], dtype=float)
    hh  = np.array([t.get("total_households")   or 0 for t in valid], dtype=float)

    scores = 0.35*norm(pop) + 0.30*norm(inc) + 0.25*norm(1-pov) + 0.10*norm(hh)
    for i, t in enumerate(valid):
        t["density_score"] = round(float(scores[i]), 4)
    return valid