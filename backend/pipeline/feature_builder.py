"""
backend/pipeline/feature_builder.py
"""

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs" / "features"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# -- Spatial helper -----------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# -- Brand weights ------------------------------------------------------------

BRAND_WEIGHTS = {
    "target"      : 90,
    "walmart"     : 85,
    "costco"      : 95,
    "whole foods" : 80,
    "trader joe"  : 75,
    "aldi"        : 60,
    "lidl"        : 58,
    "kroger"      : 70,
    "cub foods"   : 68,
    "hy-vee"      : 72,
    "rainbow"     : 62,
    "fresh thyme" : 65,
    "default"     : 55,
}

NEW_STORE_DEFAULTS = {
    "size_sqft"    : 45000,
    "brand_weight" : 75,
    "lambda"       : 2.0,
}


def get_brand_weight(name: str) -> int:
    if not name:
        return BRAND_WEIGHTS["default"]
    name_lower = name.lower()
    for brand, w in BRAND_WEIGHTS.items():
        if brand in name_lower:
            return w
    return BRAND_WEIGHTS["default"]


def attraction(size_sqft: float, dist_km: float, lam: float) -> float:
    if dist_km <= 0:
        return 0.0
    return size_sqft / (dist_km ** lam)


# -- Huff from tract centroid (correct implementation) ------------------------

def huff_from_tract(
    tract_lat: float,
    tract_lon: float,
    candidate_lat: float,
    candidate_lon: float,
    competitors: list,
    new_store_size: float = NEW_STORE_DEFAULTS["size_sqft"],
    new_store_brand_weight: int = NEW_STORE_DEFAULTS["brand_weight"],
    lam: float = NEW_STORE_DEFAULTS["lambda"],
) -> float:
    """
    Compute Huff probability from a TRACT CENTROID perspective.
    Customer lives at tract_lat/lon and chooses between the new store
    and all competitors.
    """
    dist_to_new = haversine_km(tract_lat, tract_lon, candidate_lat, candidate_lon)
    if dist_to_new <= 0:
        dist_to_new = 0.01

    eff_new_size = new_store_size * (new_store_brand_weight / 100)
    attr_new     = attraction(eff_new_size, dist_to_new, lam)

    comp_attrs = []
    for c in competitors:
        clat = c.get("lat") or c.get("latitude")
        clon = c.get("lon") or c.get("longitude")
        if clat is None or clon is None:
            continue
        dist_c   = haversine_km(tract_lat, tract_lon, clat, clon)
        size_c   = c.get("size_sqft") or 30000
        bw_c     = get_brand_weight(c.get("name", ""))
        eff_size = size_c * (bw_c / 100)
        comp_attrs.append(attraction(eff_size, dist_c, lam))

    attr_total = attr_new + sum(comp_attrs)
    return attr_new / attr_total if attr_total > 0 else 0.0


# -- Legacy huff_probability (kept for compatibility) -------------------------

def huff_probability(
    candidate_lat: float,
    candidate_lon: float,
    competitors: list,
    new_store_size: float = NEW_STORE_DEFAULTS["size_sqft"],
    new_store_brand_weight: int = NEW_STORE_DEFAULTS["brand_weight"],
    lam: float = NEW_STORE_DEFAULTS["lambda"],
) -> dict:
    """
    Compute Huff score by averaging across nearby tract centroids.
    This is the correct approach — customers live at tract centroids,
    not at the parcel itself.
    """
    if not competitors:
        return {
            "probability"     : 1.0,
            "nearest_comp_km" : None,
            "competitor_count": 0,
            "top_competitor"  : None,
            "attraction_new"  : None,
            "attraction_total": None,
        }

    comp_data = []
    for c in competitors:
        clat = c.get("lat") or c.get("latitude")
        clon = c.get("lon") or c.get("longitude")
        if clat and clon:
            comp_data.append({
                "name": c.get("name", "Unknown"),
                "dist": haversine_km(candidate_lat, candidate_lon, clat, clon),
            })
    comp_data.sort(key=lambda x: x["dist"])

    return {
        "probability"     : 0.0,
        "nearest_comp_km" : round(comp_data[0]["dist"], 3) if comp_data else None,
        "competitor_count": len(comp_data),
        "top_competitor"  : comp_data[0]["name"] if comp_data else None,
        "attraction_new"  : None,
        "attraction_total": None,
    }


# -- Radial helpers -----------------------------------------------------------

def count_in_radius(items, center_lat, center_lon, radius_km, lat_key="lat", lon_key="lon"):
    count = 0
    for item in items:
        lat = item.get(lat_key) or item.get("latitude")
        lon = item.get(lon_key) or item.get("longitude")
        if lat is None or lon is None:
            continue
        if haversine_km(center_lat, center_lon, lat, lon) <= radius_km:
            count += 1
    return count


def pop_within_radius(tracts, center_lat, center_lon, radius_km):
    total = 0
    for t in tracts:
        if t.get("dist_km") is not None and t["dist_km"] <= radius_km:
            total += t.get("total_population", 0) or 0
    return total


def income_within_radius(tracts, center_lat, center_lon, radius_km):
    vals = [
        t.get("median_hh_income", 0) or 0
        for t in tracts
        if t.get("dist_km") is not None and t["dist_km"] <= radius_km
        and t.get("median_hh_income") not in (None, "null")
    ]
    return round(sum(vals) / len(vals), 2) if vals else None


def poverty_within_radius(tracts, center_lat, center_lon, radius_km):
    vals = [
        t.get("poverty_rate", 0) or 0
        for t in tracts
        if t.get("dist_km") is not None and t["dist_km"] <= radius_km
        and t.get("poverty_rate") not in (None, "null")
    ]
    return round(sum(vals) / len(vals), 4) if vals else None


# -- Feature builder ----------------------------------------------------------

def build_features(data: dict, new_store_config: dict = None) -> list:
    cfg         = {**NEW_STORE_DEFAULTS, **(new_store_config or {})}
    tracts      = data.get("demographics", {}).get("tracts", [])
    competitors = data.get("competitor_stores", {}).get("stores", [])
    parcels     = data.get("commercial_parcels", {}).get("parcels", [])
    lam         = cfg["lambda"]

    log.info(f"Building features: {len(parcels)} parcels | "
             f"{len(competitors)} competitors | {len(tracts)} tracts")

    if not competitors:
        log.warning("  No competitor data — Huff scores will reflect zero competition.")

    retail_parcels = [p for p in parcels if p.get("is_retail_compatible")]
    log.info(f"  {len(retail_parcels)} retail-compatible parcels to score")

    # pre-filter tracts with valid centroids for Huff computation
    huff_tracts = [
        t for t in tracts
        if t.get("centroid_lat") not in (None, "null")
        and t.get("centroid_lon") not in (None, "null")
        and (t.get("total_population") or 0) > 0
    ]

    features = []
    for i, parcel in enumerate(retail_parcels):
        plat = parcel.get("latitude")
        plon = parcel.get("longitude")
        if plat is None or plon is None:
            continue

        # -- Radial population counts --
        pop_500m = pop_within_radius(tracts, plat, plon, 0.5)
        pop_1km  = pop_within_radius(tracts, plat, plon, 1.0)
        pop_3km  = pop_within_radius(tracts, plat, plon, 3.0)

        # -- Radial demographic averages --
        med_income_1km = income_within_radius(tracts, plat, plon, 1.0)
        poverty_1km    = poverty_within_radius(tracts, plat, plon, 1.0)

        # -- Competitor counts --
        comp_500m = count_in_radius(competitors, plat, plon, 0.5)
        comp_1km  = count_in_radius(competitors, plat, plon, 1.0)
        comp_3km  = count_in_radius(competitors, plat, plon, 3.0)

        # -- Competitor proximity --
        comp_dists = []
        for c in competitors:
            clat = c.get("lat") or c.get("latitude")
            clon = c.get("lon") or c.get("longitude")
            if clat and clon:
                comp_dists.append({
                    "name": c.get("name", "Unknown"),
                    "dist": haversine_km(plat, plon, clat, clon),
                })
        comp_dists.sort(key=lambda x: x["dist"])
        nearest_comp_km = round(comp_dists[0]["dist"], 3) if comp_dists else None
        top_competitor  = comp_dists[0]["name"] if comp_dists else None

        # -- Huff gravity score (tract-averaged) --
        # Find tracts within 3km of this parcel
        nearby_tracts = [
            t for t in huff_tracts
            if haversine_km(plat, plon, t["centroid_lat"], t["centroid_lon"]) <= 3.0
        ]

        if nearby_tracts and competitors:
            tract_probs = [
                huff_from_tract(
                    t["centroid_lat"], t["centroid_lon"],
                    plat, plon, competitors,
                    new_store_size=cfg["size_sqft"],
                    new_store_brand_weight=cfg["brand_weight"],
                    lam=lam,
                )
                for t in nearby_tracts
            ]
            # weight by population so dense tracts matter more
            pops = [t.get("total_population") or 1 for t in nearby_tracts]
            huff_prob = round(
                sum(p * w for p, w in zip(tract_probs, pops)) / sum(pops), 4
            )
        else:
            huff_prob = 0.0

        # -- Market estimate --
        nearby_pop = pop_within_radius(tracts, plat, plon, 5.0)
        mkt = {
            "total_nearby_pop"   : nearby_pop,
            "total_captured_pop" : round(nearby_pop * huff_prob),
            "capture_rate"       : round(huff_prob, 4),
            "est_weekly_visits"  : round((nearby_pop * huff_prob / 2.4) * 1.5),
        }

        feat = {
            "parcel_id"            : parcel.get("PID"),
            "address"              : parcel.get("address"),
            "lat"                  : plat,
            "lon"                  : plon,
            "dist_km_from_center"  : parcel.get("dist_km"),
            "parcel_acres"         : parcel.get("parcel_acres"),
            "commercial_type"      : parcel.get("commercial_type"),
            "is_retail_compatible" : True,
            "market_value"         : parcel.get("market_value"),
            "pop_500m"             : pop_500m,
            "pop_1km"              : pop_1km,
            "pop_3km"              : pop_3km,
            "median_income_1km"    : med_income_1km,
            "poverty_rate_1km"     : poverty_1km,
            "competitor_count_500m": comp_500m,
            "competitor_count_1km" : comp_1km,
            "competitor_count_3km" : comp_3km,
            "nearest_competitor_km": nearest_comp_km,
            "top_competitor"       : top_competitor,
            "huff_capture_prob"    : huff_prob,
            "nearby_pop_5km"       : mkt["total_nearby_pop"],
            "captured_pop_est"     : mkt["total_captured_pop"],
            "market_capture_rate"  : mkt["capture_rate"],
            "est_weekly_visits"    : mkt["est_weekly_visits"],
            "feature_version"      : "v2",
            "lambda_used"          : lam,
            "new_store_size_sqft"  : cfg["size_sqft"],
            "computed_at"          : datetime.now(timezone.utc).isoformat(),
        }
        features.append(feat)

        if (i + 1) % 100 == 0:
            log.info(f"  Scored {i + 1}/{len(retail_parcels)} parcels...")

    log.info(f"  Done — {len(features)} feature rows built")
    return features


# -- CLI ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file",   type=str,   default=None)
    parser.add_argument("--size",   type=float, default=45000)
    parser.add_argument("--brand",  type=int,   default=75)
    parser.add_argument("--lambda", type=float, default=2.0, dest="lam")
    args = parser.parse_args()

    if args.file:
        src = Path(args.file)
    else:
        processed_dir = PROJECT_ROOT / "data" / "processed"
        candidates = sorted(processed_dir.glob("retail_data_*.json"),
                            key=lambda f: f.stat().st_mtime)
        if not candidates:
            log.error("No processed JSON found.")
            sys.exit(1)
        src = candidates[-1]

    log.info(f"Loading: {src}")
    with open(src) as f:
        data = json.load(f)

    cfg      = {"size_sqft": args.size, "brand_weight": args.brand, "lambda": args.lam}
    features = build_features(data, new_store_config=cfg)

    out_path = OUTPUT_DIR / (src.stem + "_features.json")
    with open(out_path, "w") as f:
        json.dump({"meta": cfg, "count": len(features), "features": features},
                  f, indent=2, default=str)
    log.info(f"Saved → {out_path}")

    top10 = sorted(features, key=lambda x: x["huff_capture_prob"], reverse=True)[:10]
    print("\n=== TOP 10 PARCELS BY HUFF CAPTURE PROBABILITY ===")
    print(f"{'Address':<40} {'Huff%':>6} {'Pop1km':>7} {'Comp1km':>8} {'WklyVis':>8}")
    print("-" * 72)
    for feat in top10:
        addr = str(feat.get("address") or "Unknown")[:39]
        print(f"{addr:<40} {feat['huff_capture_prob']*100:>5.1f}%"
              f" {feat['pop_1km']:>7,}"
              f" {feat['competitor_count_1km']:>8}"
              f" {feat['est_weekly_visits']:>8,}")
    print("=" * 72)


if __name__ == "__main__":
    main()