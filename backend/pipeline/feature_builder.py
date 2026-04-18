"""
backend/pipeline/feature_builder.py
─────────────────────────────────────
Reads data/processed/*.json  →  computes location features for every
retail-compatible parcel  →  writes to data/outputs/features/*.json
(PostGIS load comes later via loaders/load_features.py)

Run:
    python backend/pipeline/feature_builder.py
    python backend/pipeline/feature_builder.py --file data/processed/retail_data_44.977_-93.265_10.0km.json
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


# ── Spatial helper ────────────────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# ── Huff Gravity Model ────────────────────────────────────────────────────────
#
# Probability that a customer chooses store j:
#
#   P(j) = A(j) / Σ A(k)    where    A(j) = Size(j) / Distance(j) ^ λ
#
# λ (lambda) = distance decay exponent
#   λ = 2.0  →  standard gravity (distance squared)
#   λ = 1.5  →  moderate decay (urban, transit-rich areas)
#   λ = 2.5  →  high decay (suburban, car-dependent)
#
# brand_weight scales A(j) — bigger brand = higher attraction per sq ft.
# If we don't know sq ft we fall back to brand_weight alone.
# ─────────────────────────────────────────────────────────────────────────────

BRAND_WEIGHTS = {
    # value = relative attractiveness index (tunable)
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
    "aldi"        : 60,
    "default"     : 55,   # unknown brand
}

# Proposed new store defaults (tunable at call time)
NEW_STORE_DEFAULTS = {
    "size_sqft"    : 45000,   # sq ft — mid-size grocery/general
    "brand_weight" : 75,      # treat as a competitive mid-tier brand
    "lambda"       : 2.0,     # distance decay exponent
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
    """Single store attraction score. Returns 0 if distance is 0."""
    if dist_km <= 0:
        return 0.0
    return size_sqft / (dist_km ** lam)


def huff_probability(
    candidate_lat: float,
    candidate_lon: float,
    competitors: list[dict],
    new_store_size: float = NEW_STORE_DEFAULTS["size_sqft"],
    new_store_brand_weight: int = NEW_STORE_DEFAULTS["brand_weight"],
    lam: float = NEW_STORE_DEFAULTS["lambda"],
) -> dict:
    """
    Returns Huff probability that a customer at (candidate_lat, candidate_lon)
    chooses the NEW proposed store over all existing competitors.

    competitors: list of dicts with keys: name, lat, lon
                 optionally: size_sqft

    Returns:
        {
            "probability"        : float,   # 0–1, new store capture probability
            "nearest_comp_km"    : float,
            "competitor_count"   : int,
            "top_competitor"     : str,
            "attraction_new"     : float,
            "attraction_total"   : float,
        }
    """
    if not competitors:
        # No competitors → new store captures everything
        return {
            "probability"      : 1.0,
            "nearest_comp_km"  : None,
            "competitor_count" : 0,
            "top_competitor"   : None,
            "attraction_new"   : None,
            "attraction_total" : None,
        }

    # Distance from candidate parcel to each competitor
    comp_data = []
    for c in competitors:
        clat = c.get("lat") or c.get("latitude")
        clon = c.get("lon") or c.get("longitude")
        if clat is None or clon is None:
            continue
        dist = haversine_km(candidate_lat, candidate_lon, clat, clon)
        size = c.get("size_sqft") or (c.get("parcel_acres", 1) * 43560 * 0.6)
        bw   = get_brand_weight(c.get("name", ""))
        # Effective attraction = (size * brand_weight_ratio) / dist^λ
        # We normalise brand weight against 100 so it acts as a multiplier
        eff_size = size * (bw / 100)
        comp_data.append({
            "name"  : c.get("name", "Unknown"),
            "dist"  : dist,
            "attr"  : attraction(eff_size, dist, lam),
        })

    comp_data.sort(key=lambda x: x["dist"])

    # New store attraction (same formula)
    eff_new_size   = new_store_size * (new_store_brand_weight / 100)
    attr_new       = attraction(eff_new_size, 0.001, lam)  # at the parcel itself → ~0 dist
    # ^ distance from parcel to itself is ~0 → cap it to avoid inf
    # In practice we compute P from customer tract centroid, not parcel centroid.
    # Here we use dist=0.001 km (1 m) as a stand-in for "at location."
    # When called tract-by-tract in simulate_market_share(), dist is real.

    attr_competitors = sum(c["attr"] for c in comp_data)
    attr_total       = attr_new + attr_competitors
    prob             = attr_new / attr_total if attr_total > 0 else 0.0

    top_comp = comp_data[0]["name"] if comp_data else None

    return {
        "probability"      : round(prob, 4),
        "nearest_comp_km"  : round(comp_data[0]["dist"], 3) if comp_data else None,
        "competitor_count" : len(comp_data),
        "top_competitor"   : top_comp,
        "attraction_new"   : round(attr_new, 2),
        "attraction_total" : round(attr_total, 2),
    }


def huff_from_tract(
    tract_lat: float,
    tract_lon: float,
    candidate_lat: float,
    candidate_lon: float,
    competitors: list[dict],
    new_store_size: float = NEW_STORE_DEFAULTS["size_sqft"],
    new_store_brand_weight: int = NEW_STORE_DEFAULTS["brand_weight"],
    lam: float = NEW_STORE_DEFAULTS["lambda"],
) -> float:
    """
    Compute Huff probability from a TRACT CENTROID's perspective.
    This is used in market share simulation — the customer lives at the tract,
    not at the store.
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


# ── Radial counts ─────────────────────────────────────────────────────────────

def count_in_radius(items: list[dict], center_lat, center_lon, radius_km, lat_key="lat", lon_key="lon"):
    count = 0
    for item in items:
        lat = item.get(lat_key) or item.get("latitude")
        lon = item.get(lon_key) or item.get("longitude")
        if lat is None or lon is None:
            continue
        if haversine_km(center_lat, center_lon, lat, lon) <= radius_km:
            count += 1
    return count


def pop_within_radius(tracts: list[dict], center_lat, center_lon, radius_km):
    """Sum population of tracts whose dist_km <= radius_km."""
    total = 0
    for t in tracts:
        if t.get("dist_km") is not None and t["dist_km"] <= radius_km:
            total += t.get("total_population", 0) or 0
    return total


def income_within_radius(tracts: list[dict], center_lat, center_lon, radius_km):
    vals = [
        t.get("median_hh_income", 0) or 0
        for t in tracts
        if t.get("dist_km") is not None and t["dist_km"] <= radius_km
           and t.get("median_hh_income") not in (None, "null")
    ]
    return round(sum(vals) / len(vals), 2) if vals else None


def poverty_within_radius(tracts: list[dict], center_lat, center_lon, radius_km):
    vals = [
        t.get("poverty_rate", 0) or 0
        for t in tracts
        if t.get("dist_km") is not None and t["dist_km"] <= radius_km
           and t.get("poverty_rate") not in (None, "null")
    ]
    return round(sum(vals) / len(vals), 4) if vals else None


# ── Market share simulation ───────────────────────────────────────────────────

def simulate_market_share(
    candidate_lat: float,
    candidate_lon: float,
    tracts: list[dict],
    competitors: list[dict],
    new_store_size: float = NEW_STORE_DEFAULTS["size_sqft"],
    new_store_brand_weight: int = NEW_STORE_DEFAULTS["brand_weight"],
    lam: float = NEW_STORE_DEFAULTS["lambda"],
    max_tract_dist_km: float = 10.0,
) -> dict:
    """
    For each tract within max_tract_dist_km, compute the Huff probability
    that a resident shops at the new store. Multiply by population.
    Sum = estimated weekly customer draw.

    Assumes avg grocery trip = 1.5x per week per household,
    avg household size = 2.4 (US average).
    """
    total_captured_pop   = 0
    total_nearby_pop     = 0
    tract_results        = []

    for t in tracts:
        tdist = t.get("dist_km")
        if tdist is None or tdist > max_tract_dist_km:
            continue

        tlat = t.get("centroid_lat")
        tlon = t.get("centroid_lon")
        pop  = t.get("total_population", 0) or 0

        # If tract doesn't have centroid, skip (we'll enrich later)
        if tlat is None or tlon is None:
            total_nearby_pop += pop
            continue

        p = huff_from_tract(tlat, tlon, candidate_lat, candidate_lon,
                             competitors, new_store_size, new_store_brand_weight, lam)
        captured = pop * p
        total_captured_pop += captured
        total_nearby_pop   += pop

        tract_results.append({
            "tract_geoid"      : t.get("tract_geoid"),
            "dist_km"          : tdist,
            "population"       : pop,
            "huff_probability" : round(p, 4),
            "captured_pop"     : round(captured),
        })

    capture_rate = total_captured_pop / total_nearby_pop if total_nearby_pop > 0 else 0
    avg_hh_size  = 2.4
    trips_per_wk = 1.5
    weekly_visits = (total_captured_pop / avg_hh_size) * trips_per_wk

    return {
        "total_nearby_pop"   : round(total_nearby_pop),
        "total_captured_pop" : round(total_captured_pop),
        "capture_rate"       : round(capture_rate, 4),
        "est_weekly_visits"  : round(weekly_visits),
        "tract_breakdown"    : sorted(tract_results, key=lambda x: x["dist_km"])[:20],
    }


# ── Feature builder ───────────────────────────────────────────────────────────

def build_features(data: dict, new_store_config: dict = None) -> list[dict]:
    """
    Main function. Takes the full processed JSON and returns a list of
    feature dicts — one per retail-compatible parcel.
    """
    cfg         = {**NEW_STORE_DEFAULTS, **(new_store_config or {})}
    tracts      = data.get("demographics", {}).get("tracts", [])
    competitors = data.get("competitor_stores", {}).get("stores", [])
    parcels     = data.get("commercial_parcels", {}).get("parcels", [])
    lam         = cfg["lambda"]

    log.info(f"Building features: {len(parcels)} parcels | "
             f"{len(competitors)} competitors | {len(tracts)} tracts")

    if not competitors:
        log.warning("  No competitor data — Huff scores will reflect zero competition.")

    features = []
    retail_parcels = [p for p in parcels if p.get("is_retail_compatible")]
    log.info(f"  {len(retail_parcels)} retail-compatible parcels to score")

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
        med_income_1km  = income_within_radius(tracts, plat, plon, 1.0)
        poverty_1km     = poverty_within_radius(tracts, plat, plon, 1.0)

        # -- Competitor counts --
        comp_500m = count_in_radius(competitors, plat, plon, 0.5)
        comp_1km  = count_in_radius(competitors, plat, plon, 1.0)
        comp_3km  = count_in_radius(competitors, plat, plon, 3.0)

        # -- Huff gravity score --
        huff = huff_probability(
            plat, plon, competitors,
            new_store_size=cfg["size_sqft"],
            new_store_brand_weight=cfg["brand_weight"],
            lam=lam,
        )

        # -- Market share simulation (skipped for speed in agent runs) --
        # Rough estimate: huff_prob * nearby pop / avg_hh_size * trips_per_week
        nearby_pop = pop_within_radius(tracts, plat, plon, 5.0)
        huff_prob  = huff["probability"]
        mkt = {
            "total_nearby_pop"   : nearby_pop,
            "total_captured_pop" : round(nearby_pop * huff_prob),
            "capture_rate"       : round(huff_prob, 4),
            "est_weekly_visits"  : round((nearby_pop * huff_prob / 2.4) * 1.5),
        }

        feat = {
            # identifiers
            "parcel_id"           : parcel.get("PID"),
            "address"             : parcel.get("address"),
            "lat"                 : plat,
            "lon"                 : plon,
            "dist_km_from_center" : parcel.get("dist_km"),
            "parcel_acres"        : parcel.get("parcel_acres"),
            "commercial_type"     : parcel.get("commercial_type"),
            "is_retail_compatible": True,
            "market_value"        : parcel.get("market_value"),

            # demographics
            "pop_500m"            : pop_500m,
            "pop_1km"             : pop_1km,
            "pop_3km"             : pop_3km,
            "median_income_1km"   : med_income_1km,
            "poverty_rate_1km"    : poverty_1km,

            # competition
            "competitor_count_500m" : comp_500m,
            "competitor_count_1km"  : comp_1km,
            "competitor_count_3km"  : comp_3km,
            "nearest_competitor_km" : huff["nearest_comp_km"],
            "top_competitor"        : huff["top_competitor"],

            # huff gravity
            "huff_capture_prob"     : huff["probability"],
            "huff_attraction_new"   : huff["attraction_new"],
            "huff_attraction_total" : huff["attraction_total"],

            # market simulation
            "nearby_pop_10km"       : mkt["total_nearby_pop"],
            "captured_pop_est"      : mkt["total_captured_pop"],
            "market_capture_rate"   : mkt["capture_rate"],
            "est_weekly_visits"     : mkt["est_weekly_visits"],

            # metadata
            "feature_version"       : "v1",
            "lambda_used"           : lam,
            "new_store_size_sqft"   : cfg["size_sqft"],
            "computed_at"           : datetime.now(timezone.utc).isoformat(),
        }
        features.append(feat)

        if (i + 1) % 100 == 0:
            log.info(f"  Scored {i + 1}/{len(retail_parcels)} parcels...")

    log.info(f"  Done — {len(features)} feature rows built")
    return features


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build location features from processed JSON.")
    parser.add_argument("--file", type=str, default=None,
                        help="Path to processed JSON (default: latest in data/processed/)")
    parser.add_argument("--size",   type=float, default=45000, help="New store size in sq ft")
    parser.add_argument("--brand",  type=int,   default=75,    help="Brand weight 0-100")
    parser.add_argument("--lambda", type=float, default=2.0,   dest="lam",
                        help="Distance decay exponent (default 2.0)")
    args = parser.parse_args()

    # Find input file
    if args.file:
        src = Path(args.file)
    else:
        processed_dir = PROJECT_ROOT / "data" / "processed"
        candidates = sorted(processed_dir.glob("retail_data_*.json"), key=lambda f: f.stat().st_mtime)
        if not candidates:
            log.error("No processed JSON found. Run fetch_all.py first.")
            sys.exit(1)
        src = candidates[-1]

    log.info(f"Loading: {src}")
    with open(src) as f:
        data = json.load(f)

    cfg = {"size_sqft": args.size, "brand_weight": args.brand, "lambda": args.lam}
    features = build_features(data, new_store_config=cfg)

    # Save output
    out_name = src.stem + "_features.json"
    out_path = OUTPUT_DIR / out_name
    with open(out_path, "w") as f:
        json.dump({"meta": cfg, "count": len(features), "features": features}, f, indent=2, default=str)

    log.info(f"Saved → {out_path}  ({out_path.stat().st_size / 1024:.1f} KB)")

    # Print top 10 by Huff capture probability
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
