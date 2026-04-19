"""
Unified Retail Expansion Data Pipeline
----------------------------------------
Calls all 6 data sources in one shot and returns a single JSON output.

Sources:
  1. ACS 5-Year  — Census tract demographics  (Census API + TIGERweb)
  2. Geoapify    — Competitor stores nearby
  3. Minneapolis — Commercial parcels + assessor data
  4. Geoapify    — Schools nearby
  5. MnDOT       — AADT traffic counts
  6. Minneapolis — Neighborhood boundaries + centroids

Usage:
    python backend/pipeline/fetch_all.py --lat 44.977 --lon -93.265 --radius 10
    python backend/pipeline/fetch_all.py --lat 44.977 --lon -93.265 --radius 25 --out custom_output.json
"""

import argparse
import io
import json
import logging
import math
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ── path setup so we can import our own ingestion modules ───────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.ingestion.demographics.fetch_acs_demographics import (
    get_tracts_in_radius, fetch_acs_for_tracts, clean as clean_demographics,
)
from backend.ingestion.parcels.fetch_parcels import (
    fetch_commercial_parcels, fetch_assessor_data, clean as clean_parcels,
)
from backend.ingestion.neighborhoods.fetch_neighborhoods import (
    fetch_neighborhoods, build_dataframe,
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

import time

# ── Name helpers ─────────────────────────────────────────────────────────────

_TYPE_LABELS = {
    "school"           : "School",
    "kindergarten"     : "Kindergarten",
    "college"          : "College",
    "university"       : "University",
    "library"          : "Library",
    "driving_school"   : "Driving School",
    "language_school"  : "Language School",
    "music_school"     : "Music School",
    "supermarket"      : "Supermarket",
    "convenience"      : "Convenience Store",
    "department_store" : "Department Store",
    "discount_store"   : "Discount Store",
    "marketplace"      : "Marketplace",
    "shopping_mall"    : "Shopping Mall",
    "warehouse_store"  : "Warehouse Store",
}


def _humanize_type(category_leaf: str) -> str:
    if not category_leaf:
        return "Place"
    return _TYPE_LABELS.get(
        category_leaf.lower(),
        category_leaf.replace("_", " ").title(),
    )


def _clean(val):
    if val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("", "null", "none", "unknown") else s


def _derive_name(props: dict, type_label: str) -> str:
    name = _clean(props.get("name"))
    if name:
        return name
    street  = _clean(props.get("street")) or _clean(props.get("address_line1"))
    housenr = _clean(props.get("housenumber"))
    area    = _clean(props.get("district")) or _clean(props.get("suburb")) or _clean(props.get("city"))
    if street:
        loc = f"{housenr} {street}".strip() if housenr else street
        return f"{type_label} on {loc}"
    if area:
        return f"{type_label} · {area}"
    formatted = _clean(props.get("formatted"))
    if formatted:
        short = formatted.split(",")[0]
        return f"{type_label} near {short}"
    return f"Unnamed {type_label.lower()}"


# ── Spatial helper ───────────────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# ── Geoapify helper with retry ───────────────────────────────────────────────

def _geoapify_query(lat: float, lon: float, radius_km: float, categories: str) -> list:
    api_key = os.environ.get("GEOAPIFY_API_KEY")
    if not api_key:
        log.warning("  GEOAPIFY_API_KEY not found in environment (.env). Returning empty list.")
        return []

    url = "https://api.geoapify.com/v2/places"
    params = {
        "categories": categories,
        "filter": f"circle:{lon},{lat},{int(radius_km * 1000)}",
        "limit": 500,
        "apiKey": api_key,
    }

    delays = [2, 5, 10]
    retries = 3

    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                wait = delays[attempt - 1]
                log.warning(f"  Geoapify {r.status_code} — retrying in {wait}s (attempt {attempt}/{retries})")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json().get("features", [])
        except requests.exceptions.RequestException as e:
            if attempt < retries:
                wait = delays[attempt - 1]
                log.warning(f"  Geoapify timeout/error — retrying in {wait}s (attempt {attempt}/{retries})")
                time.sleep(wait)
            else:
                log.error(f"  Geoapify final failure: {e}")
                return []

    return []


# ── Source 1: ACS Demographics ───────────────────────────────────────────────

def pull_demographics(lat, lon, radius_km):
    log.info("[1/6] ACS Demographics...")
    try:
        tract_meta = get_tracts_in_radius(lat, lon, radius_km)
        if tract_meta.empty:
            return {"error": "No tracts found", "tracts": []}

        acs_raw = fetch_acs_for_tracts(tract_meta)
        df      = clean_demographics(acs_raw, tract_meta)

        summary = {
            "tract_count"              : len(df),
            "total_population"         : int(df["total_population"].sum()),
            "total_households"         : int(df["total_households"].sum()),
            "median_hh_income_area_avg": round(float(df["median_hh_income"].mean()), 2),
            "avg_poverty_rate"         : round(float(df["poverty_rate"].mean()), 4),
            "avg_owner_share"          : round(float(df["owner_share"].mean()), 4),
            "avg_renter_share"         : round(float(df["renter_share"].mean()), 4),
        }
        tracts = df[[
            "tract_geoid", "NAME",
            "centroid_lat", "centroid_lon", "dist_km",
            "total_population", "total_households", "median_hh_income",
            "owner_share", "renter_share", "poverty_rate",
        ]].fillna("null").to_dict(orient="records")

        return {"summary": summary, "tracts": tracts}
    except Exception as e:
        log.error(f"  Demographics failed: {e}")
        return {"error": str(e), "tracts": []}


# ── Source 2: Competitor Stores (Geoapify) ───────────────────────────────────

RIVAL_TYPES = {
    "grocery":          {"supermarket", "convenience", "department_store", "food_and_drink", "bakery"},
    "supermarket":      {"supermarket", "convenience", "department_store"},
    "convenience":      {"convenience", "supermarket", "food_and_drink"},
    "pharmacy":         {"chemist", "department_store", "health_and_beauty"},
    "department_store": {"department_store", "supermarket"},
    "default":          {"supermarket", "convenience", "department_store", "chemist", "food_and_drink", "bakery"},
}


def pull_competitor_stores(lat, lon, radius_km, store_type="grocery"):
    log.info("[2/6] Competitor stores (Geoapify)...")
    try:
        categories = ",".join([
            "commercial.supermarket",
            "commercial.department_store",
            "commercial.convenience",
            "commercial.chemist",
            "commercial.food_and_drink",
        ])
        features = _geoapify_query(lat, lon, radius_km, categories)

        stores = []
        for f in features:
            props = f.get("properties", {})
            geom  = f.get("geometry", {}).get("coordinates", [None, None])
            slon, slat = geom[0], geom[1]
            dist_km = round(haversine_km(lat, lon, slat, slon), 3) if slat and slon else None

            # ── KEY FIX: only look at commercial.* categories ──
            categories_list = props.get("categories") or []
            commercial_cats = [c for c in categories_list if c.startswith("commercial.")]
            shop_leaf  = commercial_cats[-1].split(".")[-1] if commercial_cats else "store"
            type_label = _humanize_type(shop_leaf)
            derived    = _derive_name(props, type_label)

            stores.append({
                "place_id" : props.get("place_id"),
                "name"     : derived,
                "shop_type": shop_leaf,
                "lat"      : slat,
                "lon"      : slon,
                "dist_km"  : dist_km,
                "address"  : _clean(props.get("address_line1")) or _clean(props.get("formatted")) or None,
                "street"   : _clean(props.get("street")) or None,
                "district" : _clean(props.get("district")) or _clean(props.get("suburb")) or None,
            })

        # Filter to only actual rivals for this store type
        rival_set = RIVAL_TYPES.get(store_type, RIVAL_TYPES["default"])
        stores = [s for s in stores if s["shop_type"] in rival_set]

        stores.sort(key=lambda x: x["dist_km"] or 999)
        log.info(f"  Found {len(stores)} stores ({store_type} rivals only)")
        return {"count": len(stores), "stores": stores}
    except Exception as e:
        log.error(f"  Stores failed: {e}")
        return {"error": str(e), "count": 0, "stores": []}


# ── Source 3: Commercial Parcels ─────────────────────────────────────────────

def pull_parcels(lat, lon, radius_km):
    log.info("[3/6] Commercial parcels...")
    try:
        comm_df     = fetch_commercial_parcels(lat, lon, radius_km)
        if comm_df.empty:
            return {"error": "No parcels found", "count": 0, "parcels": []}

        pids        = comm_df["PID"].dropna().astype(str).tolist()
        assessor_df = fetch_assessor_data(pids)
        df          = clean_parcels(comm_df, assessor_df)

        summary = {
            "total_count"            : len(df),
            "retail_compatible_count": int(df["is_retail_compatible"].sum()),
            "avg_parcel_acres"       : round(float(df["parcel_acres"].mean()), 3),
            "max_parcel_acres"       : round(float(df["parcel_acres"].max()), 3),
            "commercial_type_breakdown": df["commercial_type"].value_counts().to_dict(),
        }

        keep_cols = [
            "PID", "address", "zip_code", "latitude", "longitude", "dist_km",
            "land_use_label", "commercial_type", "parcel_acres",
            "is_retail_compatible", "market_value", "build_year",
        ]
        parcels = df[[c for c in keep_cols if c in df.columns]].fillna("null").to_dict(orient="records")

        log.info(f"  {len(df)} parcels, {summary['retail_compatible_count']} retail-compatible")
        return {"summary": summary, "count": len(df), "parcels": parcels}
    except Exception as e:
        log.error(f"  Parcels failed: {e}")
        return {"error": str(e), "count": 0, "parcels": []}


# ── Source 4: Schools (Geoapify) ─────────────────────────────────────────────

def pull_schools(lat, lon, radius_km):
    log.info("[4/6] Schools (Geoapify)...")
    try:
        categories = "education.school,education.college,education.university"
        features   = _geoapify_query(lat, lon, radius_km, categories)

        schools = []
        for f in features:
            props = f.get("properties", {})
            geom  = f.get("geometry", {}).get("coordinates", [None, None])
            slon, slat = geom[0], geom[1]
            dist_km = round(haversine_km(lat, lon, slat, slon), 3) if slat and slon else None

            categories_list = props.get("categories") or []
            amenity_leaf = categories_list[-1].split(".")[-1] if categories_list else "school"
            type_label   = _humanize_type(amenity_leaf)
            derived      = _derive_name(props, type_label)

            schools.append({
                "place_id"    : props.get("place_id"),
                "name"        : derived,
                "amenity_type": amenity_leaf,
                "lat"         : slat,
                "lon"         : slon,
                "dist_km"     : dist_km,
                "street"      : _clean(props.get("street")) or None,
                "district"    : _clean(props.get("district")) or _clean(props.get("suburb")) or None,
            })

        schools.sort(key=lambda x: x["dist_km"] or 999)
        log.info(f"  Found {len(schools)} schools/universities")
        return {"count": len(schools), "schools": schools}
    except Exception as e:
        log.error(f"  Schools failed: {e}")
        return {"error": str(e), "count": 0, "schools": []}


# ── Source 5: AADT Traffic (MnDOT) ───────────────────────────────────────────

def pull_traffic(lat, lon, radius_km):
    log.info("[5/6] AADT traffic data (MnDOT)...")
    radius_m = radius_km * 1000

    try:
        import geopandas as gpd
        from shapely.geometry import Point

        aadt_dir = PROJECT_ROOT / "aadt_data"

        if not aadt_dir.exists() or not any(aadt_dir.glob("*.shp")):
            log.info("  Downloading MnDOT AADT shapefile...")
            url = (
                "https://resources.gisdata.mn.gov/pub/gdrs/data/pub/us_mn_state_dot"
                "/trans_aadt_traffic_count_locs/shp_trans_aadt_traffic_count_locs.zip"
            )
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            z = zipfile.ZipFile(io.BytesIO(r.content))
            aadt_dir.mkdir(exist_ok=True)
            z.extractall(aadt_dir)
            log.info("  Download complete.")

        gdf      = gpd.read_file(str(aadt_dir)).to_crs(epsg=4326)
        pin      = gpd.GeoDataFrame(geometry=[Point(lon, lat)], crs="EPSG:4326")
        gdf_proj = gdf.to_crs(epsg=3857)
        pin_proj = pin.to_crs(epsg=3857)

        gdf_proj["distance_m"] = gdf_proj.geometry.distance(pin_proj.geometry[0])
        nearby = (
            gdf_proj[gdf_proj["distance_m"] <= radius_m]
            .copy()
            .sort_values("distance_m")
        )

        if nearby.empty:
            return {"error": "No AADT points in radius", "count": 0, "points": []}

        # MnDOT sometimes leaves STREET_NAM blank for ramps / unnamed segments.
        # Walk the nearest rows until we find a real name; fall back to ROUTE_LABE
        # (e.g. "I-35W") and finally "Unknown" so we never persist the literal "nan".
        def _clean_road(val) -> str | None:
            if val is None:
                return None
            s = str(val).strip()
            if not s or s.lower() in ("nan", "none", "null"):
                return None
            return s

        nearest_road = None
        for _, row in nearby.iterrows():
            nearest_road = _clean_road(row.get("STREET_NAM")) \
                        or _clean_road(row.get("ROUTE_LABE"))
            if nearest_road:
                break
        nearest_road = nearest_road or "Unknown"

        summary = {
            "count"        : len(nearby),
            "nearest_road" : nearest_road,
            "nearest_aadt" : int(nearby.iloc[0].get("CURRENT_VO", 0)),
            "max_aadt"     : int(nearby["CURRENT_VO"].max()),
            "avg_aadt"     : round(float(nearby["CURRENT_VO"].mean()), 0),
        }

        points = []
        for _, row in nearby.head(50).iterrows():
            geom = row.geometry
            wgs_geom = gpd.GeoDataFrame(
                geometry=[geom], crs="EPSG:3857"
            ).to_crs(epsg=4326).geometry[0]

            street = _clean_road(row.get("STREET_NAM"))
            aadt   = int(row.get("CURRENT_VO", 0))

            # Skip rows with no usable street name or zero traffic
            if not street or aadt == 0:
                continue

            points.append({
                "street_name" : street,
                "route_label" : _clean_road(row.get("ROUTE_LABE")) or "",
                "aadt"        : aadt,
                "distance_m"  : round(float(row["distance_m"]), 0),
                "lat"         : round(wgs_geom.y, 6),
                "lon"         : round(wgs_geom.x, 6),
            })

        log.info(f"  {len(nearby)} AADT points, nearest: {summary['nearest_road']} ({summary['nearest_aadt']:,} veh/day)")
        return {"summary": summary, "count": len(nearby), "points": points}

    except ImportError:
        log.warning("  geopandas not installed — skipping AADT. Run: pip install geopandas")
        return {"error": "geopandas not installed", "count": 0, "points": []}
    except Exception as e:
        log.error(f"  Traffic failed: {e}")
        return {"error": str(e), "count": 0, "points": []}


# ── Source 6: Neighborhoods ───────────────────────────────────────────────────

def pull_neighborhoods(lat, lon, radius_km):
    log.info("[6/6] Minneapolis neighborhoods...")
    try:
        features, _ = fetch_neighborhoods()
        df          = build_dataframe(features)

        def dist(row):
            if row["centroid_lat"] and row["centroid_lon"]:
                return round(haversine_km(lat, lon, row["centroid_lat"], row["centroid_lon"]), 3)
            return None

        df["dist_km"]   = df.apply(dist, axis=1)
        df["in_radius"] = df["dist_km"].apply(lambda d: d is not None and d <= radius_km)
        in_radius_count = int(df["in_radius"].sum())

        neighborhoods = df[[
            "neighborhood_id", "neighborhood_name",
            "centroid_lat", "centroid_lon", "dist_km", "in_radius",
        ]].sort_values("dist_km").fillna("null").to_dict(orient="records")

        log.info(f"  87 total, {in_radius_count} within {radius_km} km radius")
        return {
            "total_count"    : 87,
            "in_radius_count": in_radius_count,
            "neighborhoods"  : neighborhoods,
        }
    except Exception as e:
        log.error(f"  Neighborhoods failed: {e}")
        return {"error": str(e), "neighborhoods": []}


# ── Unified runner ────────────────────────────────────────────────────────────

def run_all(lat: float, lon: float, radius_km: float, out_path: Path = None, store_type: str = "grocery") -> dict:
    log.info("=" * 65)
    log.info(f"Unified Pipeline  —  ({lat}, {lon})  radius={radius_km} km")
    log.info("=" * 65)

    result = {
        "query": {
            "lat"       : lat,
            "lon"       : lon,
            "radius_km" : radius_km,
            "radius_m"  : radius_km * 1000,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        },
        "demographics"      : pull_demographics(lat, lon, radius_km),
        "competitor_stores" : pull_competitor_stores(lat, lon, radius_km, store_type=store_type),
        "commercial_parcels": pull_parcels(lat, lon, radius_km),
        "schools"           : pull_schools(lat, lon, radius_km),
        "traffic_aadt"      : pull_traffic(lat, lon, radius_km),
        "neighborhoods"     : pull_neighborhoods(lat, lon, radius_km),
    }

    if out_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / f"retail_data_{lat}_{lon}_{radius_km}km.json"

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    log.info("=" * 65)
    log.info(f"Done ✓  →  {out_path}  ({out_path.stat().st_size / 1024:.1f} KB)")
    log.info("=" * 65)
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pull all retail expansion data sources into one JSON."
    )
    parser.add_argument("--lat",    type=float, default=44.977,  help="Center latitude")
    parser.add_argument("--lon",    type=float, default=-93.265, help="Center longitude")
    parser.add_argument("--radius", type=float, default=10.0,    help="Radius in km")
    parser.add_argument("--out",    type=str,   default=None,    help="Custom output JSON path")
    args = parser.parse_args()

    out  = Path(args.out) if args.out else None
    data = run_all(lat=args.lat, lon=args.lon, radius_km=args.radius, out_path=out)

    print("\n" + "=" * 65)
    print("SUMMARY")
    print("=" * 65)
    q = data["query"]
    print(f"  Center          : ({q['lat']}, {q['lon']})")
    print(f"  Radius          : {q['radius_km']} km")
    print(f"  Fetched at      : {q['fetched_at']}")
    print()
    d = data["demographics"]
    if "summary" in d:
        s = d["summary"]
        print(f"  [1] Demographics: {s['tract_count']} tracts | pop {s['total_population']:,} | "
              f"med income ${s['median_hh_income_area_avg']:,.0f}")
    cs = data["competitor_stores"]
    print(f"  [2] Stores      : {cs.get('count', 0)} competitor stores")
    cp = data["commercial_parcels"]
    print(f"  [3] Parcels     : {cp.get('count', 0)} commercial parcels "
          f"({cp.get('summary', {}).get('retail_compatible_count', '?')} retail-compatible)")
    sc = data["schools"]
    print(f"  [4] Schools     : {sc.get('count', 0)} schools/universities")
    tr = data["traffic_aadt"]
    if "summary" in tr:
        print(f"  [5] Traffic     : {tr['summary']['count']} AADT points | "
              f"nearest {tr['summary']['nearest_road']} ({tr['summary']['nearest_aadt']:,} veh/day)")
    else:
        print(f"  [5] Traffic     : {tr.get('error', 'N/A')}")
    nb = data["neighborhoods"]
    print(f"  [6] Neighborhoods: {nb.get('in_radius_count', '?')} of 87 within radius")
    print("=" * 65)