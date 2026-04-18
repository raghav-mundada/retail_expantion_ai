"""
Unified Retail Expansion Data Pipeline
----------------------------------------
Calls all 6 data sources in one shot and returns a single JSON output.

Sources:
  1. ACS 5-Year  — Census tract demographics  (Census API + TIGERweb)
  2. Overpass    — Competitor supermarkets nearby
  3. Minneapolis — Commercial parcels + assessor data
  4. Overpass    — Schools nearby
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
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

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

# ── Spatial helper ──────────────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


# ── Overpass helper with retry ───────────────────────────────────────────────

def _overpass_query(query: str, method: str = "get", retries: int = 3) -> list:
    """
    Send a query to the Overpass API with automatic retry on 429/504 errors.
    Waits 5 s → 10 s → 20 s between attempts.
    Returns the list of elements, or raises on final failure.
    """
    url    = "https://overpass-api.de/api/interpreter"
    delays = [5, 10, 20]

    for attempt in range(1, retries + 1):
        try:
            if method == "post":
                r = requests.post(url, data=query, timeout=60)
            else:
                r = requests.get(url, params={"data": query}, timeout=60)

            if r.status_code in (429, 504) and attempt < retries:
                wait = delays[attempt - 1]
                log.warning(f"  Overpass {r.status_code} — retrying in {wait}s (attempt {attempt}/{retries})")
                time.sleep(wait)
                continue

            r.raise_for_status()
            return r.json().get("elements", [])

        except requests.exceptions.Timeout:
            if attempt < retries:
                wait = delays[attempt - 1]
                log.warning(f"  Overpass timeout — retrying in {wait}s (attempt {attempt}/{retries})")
                time.sleep(wait)
            else:
                raise

    return []


# ── Source 1: ACS Demographics ──────────────────────────────────────────────

def pull_demographics(lat, lon, radius_km):
    log.info("[1/6] ACS Demographics...")
    try:
        tract_meta = get_tracts_in_radius(lat, lon, radius_km)
        if tract_meta.empty:
            return {"error": "No tracts found", "tracts": []}

        acs_raw  = fetch_acs_for_tracts(tract_meta)
        df       = clean_demographics(acs_raw, tract_meta)

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
            "tract_geoid", "NAME", "dist_km", "total_population",
            "total_households", "median_hh_income",
            "owner_share", "renter_share", "poverty_rate",
        ]].fillna("null").to_dict(orient="records")

        return {"summary": summary, "tracts": tracts}
    except Exception as e:
        log.error(f"  Demographics failed: {e}")
        return {"error": str(e), "tracts": []}


# ── Source 2: Competitor Stores (Overpass) ──────────────────────────────────

def pull_competitor_stores(lat, lon, radius_km):
    log.info("[2/6] Competitor stores (Overpass)...")
    radius_m = int(radius_km * 1000)
    try:
        query = f"""
[out:json][timeout:55];
(
  node["shop"="supermarket"](around:{radius_m},{lat},{lon});
  node["shop"="grocery"](around:{radius_m},{lat},{lon});
  node["shop"="convenience"](around:{radius_m},{lat},{lon});
);
out body;
"""
        elements = _overpass_query(query, method="post")

        stores = []
        for n in elements:
            tags    = n.get("tags", {})
            slat    = n.get("lat")
            slon    = n.get("lon")
            dist_km = round(haversine_km(lat, lon, slat, slon), 3) if slat and slon else None
            stores.append({
                "osm_id"     : n.get("id"),
                "name"       : tags.get("name", "Unknown"),
                "shop_type"  : tags.get("shop"),
                "brand"      : tags.get("brand"),
                "lat"        : slat,
                "lon"        : slon,
                "dist_km"    : dist_km,
                "address"    : tags.get("addr:street"),
                "opening_hours": tags.get("opening_hours"),
            })

        stores.sort(key=lambda x: x["dist_km"] or 999)
        log.info(f"  Found {len(stores)} stores")
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
            "total_count"           : len(df),
            "retail_compatible_count": int(df["is_retail_compatible"].sum()),
            "avg_parcel_acres"      : round(float(df["parcel_acres"].mean()), 3),
            "max_parcel_acres"      : round(float(df["parcel_acres"].max()), 3),
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


# ── Source 4: Schools (Overpass) ─────────────────────────────────────────────

def pull_schools(lat, lon, radius_km):
    log.info("[4/6] Schools (Overpass)...")
    radius_m = int(radius_km * 1000)
    try:
        query = f"""
[out:json][timeout:55];
(
  node["amenity"="school"](around:{radius_m},{lat},{lon});
  node["amenity"="college"](around:{radius_m},{lat},{lon});
  node["amenity"="university"](around:{radius_m},{lat},{lon});
);
out body;
"""
        elements = _overpass_query(query, method="post")

        schools = []
        for n in elements:
            tags    = n.get("tags", {})
            slat    = n.get("lat")
            slon    = n.get("lon")
            dist_km = round(haversine_km(lat, lon, slat, slon), 3) if slat and slon else None
            schools.append({
                "osm_id"     : n.get("id"),
                "name"       : tags.get("name", "Unknown"),
                "amenity_type": tags.get("amenity"),
                "lat"        : slat,
                "lon"        : slon,
                "dist_km"    : dist_km,
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

        # Download shapefile only if not already cached
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
        nearby_wgs = nearby.to_crs(epsg=4326)

        if nearby.empty:
            return {"error": "No AADT points in radius", "count": 0, "points": []}

        summary = {
            "count"        : len(nearby),
            "nearest_road" : str(nearby.iloc[0].get("STREET_NAM", "Unknown")),
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
            points.append({
                "street_name" : str(row.get("STREET_NAM", "")),
                "route_label" : str(row.get("ROUTE_LABE", "")),
                "aadt"        : int(row.get("CURRENT_VO", 0)),
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

        # Flag which neighborhoods are within radius
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

def run_all(lat: float, lon: float, radius_km: float, out_path: Path = None) -> dict:
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
        "competitor_stores" : pull_competitor_stores(lat, lon, radius_km),
        "commercial_parcels": pull_parcels(lat, lon, radius_km),
        "schools"           : pull_schools(lat, lon, radius_km),
        "traffic_aadt"      : pull_traffic(lat, lon, radius_km),
        "neighborhoods"     : pull_neighborhoods(lat, lon, radius_km),
    }

    # Save JSON
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
    parser.add_argument("--lat",    type=float, default=44.977,  help="Center latitude  (default: Minneapolis)")
    parser.add_argument("--lon",    type=float, default=-93.265, help="Center longitude (default: Minneapolis)")
    parser.add_argument("--radius", type=float, default=10.0,    help="Radius in km     (default: 10)")
    parser.add_argument("--out",    type=str,   default=None,    help="Custom output JSON path")
    args = parser.parse_args()

    out = Path(args.out) if args.out else None
    data = run_all(lat=args.lat, lon=args.lon, radius_km=args.radius, out_path=out)

    # Print a clean summary to stdout
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
