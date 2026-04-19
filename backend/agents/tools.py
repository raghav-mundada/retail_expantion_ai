"""
backend/agents/tools.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.pipeline.feature_builder import build_features, haversine_km, huff_probability

_fetched_data = {}


# -- Tool 1: Geocode ----------------------------------------------------------

def geocode_neighborhood(neighborhood: str, city: str = "Minneapolis, MN") -> dict:
    """Convert a neighborhood name to lat/lon using Nominatim."""
    import requests
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{neighborhood}, {city}", "format": "json", "limit": 1},
            headers={"User-Agent": "retail-expansion-ai/1.0"},
            timeout=10,
        )
        results = r.json()
        if not results:
            return {"error": f"Could not geocode: {neighborhood}"}
        top = results[0]
        return {
            "lat"         : float(top["lat"]),
            "lon"         : float(top["lon"]),
            "display_name": top["display_name"],
        }
    except Exception as e:
        return {"error": str(e)}


# -- Tool 2: Fetch data -------------------------------------------------------

def fetch_location_data(lat: float, lon: float, radius_km: float = 5.0) -> dict:
    """Run full ingestion pipeline for a lat/lon. Saves data internally."""
    from backend.pipeline.fetch_all import run_all
    try:
        data = run_all(lat=lat, lon=lon, radius_km=radius_km)
        demo = data.get("demographics", {}).get("summary", {})
        comp = data.get("competitor_stores", {})
        parc = data.get("commercial_parcels", {}).get("summary", {})
        return {
            "lat"                    : lat,
            "lon"                    : lon,
            "radius_km"              : radius_km,
            "tract_count"            : demo.get("tract_count", 0),
            "total_population"       : demo.get("total_population", 0),
            "median_hh_income"       : demo.get("median_hh_income_area_avg", 0),
            "avg_poverty_rate"       : demo.get("avg_poverty_rate", 0),
            "competitor_count"       : comp.get("count", 0),
            "total_parcels"          : parc.get("total_count", 0),
            "retail_compatible_count": parc.get("retail_compatible_count", 0),
            "data"                   : data,
        }
    except Exception as e:
        return {"error": str(e)}


# -- Tool 3: Score parcels ----------------------------------------------------

def score_parcels(
    data: dict,
    store_type: str = "grocery",
    store_size_sqft: int = 45000,
    brand_weight: int = 75,
    top_n: int = 10,
    min_acres: float = 0.5,
) -> dict:
    """Score retail parcels using Huff gravity. Returns top N ranked parcels."""
    try:
        cfg = {"size_sqft": store_size_sqft, "brand_weight": brand_weight, "lambda": 2.0}
        features = build_features(data, new_store_config=cfg)
        if not features:
            return {"error": "No retail-compatible parcels found", "top_parcels": []}

        features = [f for f in features if (f.get("parcel_acres") or 0) >= min_acres]
        if not features:
            return {"error": f"No parcels >= {min_acres} acres", "top_parcels": []}

        ranked = sorted(features, key=lambda x: x.get("huff_capture_prob", 0), reverse=True)
        return {
            "total_scored": len(features),
            "top_parcels" : [
                {
                    "rank"                 : i + 1,
                    "parcel_id"            : p.get("parcel_id"),
                    "address"              : p.get("address"),
                    "lat"                  : p.get("lat"),
                    "lon"                  : p.get("lon"),
                    "huff_capture_prob"    : p.get("huff_capture_prob"),
                    "pop_1km"              : p.get("pop_1km"),
                    "median_income_1km"    : p.get("median_income_1km"),
                    "competitor_count_1km" : p.get("competitor_count_1km"),
                    "nearest_competitor_km": p.get("nearest_competitor_km"),
                    "top_competitor"       : p.get("top_competitor"),
                    "est_weekly_visits"    : p.get("est_weekly_visits"),
                    "parcel_acres"         : p.get("parcel_acres"),
                    "commercial_type"      : p.get("commercial_type"),
                    "market_value"         : p.get("market_value"),
                }
                for i, p in enumerate(ranked[:top_n])
            ],
        }
    except Exception as e:
        return {"error": str(e), "top_parcels": []}


# -- Tool 4: Expand radius ----------------------------------------------------

def expand_radius(current_radius_km: float, reason: str = "") -> dict:
    """Return a suggested larger radius, capped at 25km."""
    new_radius = round(min(current_radius_km * 1.5, 25.0), 1)
    return {
        "old_radius_km": current_radius_km,
        "new_radius_km": new_radius,
        "reason"       : reason,
        "capped"       : new_radius == 25.0,
    }


# -- Tool 5: KMeans optimal point finder --------------------------------------

def find_optimal_points(
    lat: float,
    lon: float,
    radius_km: float = 10.0,
    n_points: int = 5,
) -> dict:
    """
    Fetch tract demographics once at center point.
    Score every tract: weighted sum of population, income, low_poverty, households.
    Run KMeans weighted by density score to find n_points optimal search locations.
    Returns points — no parcel scoring yet.
    """
    from backend.pipeline.fetch_all import run_all
    from backend.agents.K_means import find_gmm_points

    print(f"  [kmeans] fetching demographics ({lat}, {lon}) radius={radius_km}km")
    data   = run_all(lat=lat, lon=lon, radius_km=radius_km)
    tracts = data.get("demographics", {}).get("tracts", [])
    _fetched_data["initial"] = data

    print(f"  [kmeans] scoring {len(tracts)} tracts with 6 factors, fitting KMeans n={n_points}")
    points = find_gmm_points(data, n_points)

    return {
        "tracts_used"  : len(tracts),
        "n_points"     : len(points),
        "search_points": points,
    }