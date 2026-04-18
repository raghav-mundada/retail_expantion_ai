"""
ACS 5-Year Demographics Ingestion Pipeline  —  Coordinate + Radius Mode
------------------------------------------------------------------------
Usage:
    python fetch_acs_demographics.py --lat 44.977 --lon -93.265 --radius 50

    lat/lon   : WGS-84 decimal degrees (center point)
    radius    : kilometres  (default 50)

Pipeline:
  1. Compute bounding box from center + radius
  2. Query Census TIGERweb for all tracts in that bounding box
  3. Filter by exact haversine distance  →  keep tracts within the circle
  4. Group surviving tracts by state+county
  5. Pull ACS 5-year demographics for each state+county from the Census API
  6. Keep only the tracts in our list, clean, validate, save

Source  : ACS 5-Year Estimates, 2023
Output  : data/processed/demographics/<lat>_<lon>_<radius>km_tract_demographics.parquet
          data/processed/demographics/<lat>_<lon>_<radius>km_tract_demographics.csv

ACS Tables:
  B01003  Total Population
  B11001  Households
  B19013  Median Household Income
  B25003  Tenure (owner vs renter)
  B17001  Poverty Status
"""

import argparse
import logging
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACS_BASE_URL  = "https://api.census.gov/data/2023/acs/acs5"
ACS_YEAR      = 2023
TIGERWEB_URL  = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services"
    "/TIGERweb/Tracts_Blocks/MapServer/0/query"
)
CENSUS_NULL   = -666666666

ACS_VARIABLES = {
    "B01003_001E": "total_population",
    "B11001_001E": "total_households",
    "B19013_001E": "median_hh_income",
    "B25003_001E": "tenure_total",
    "B25003_002E": "owner_occupied",
    "B25003_003E": "renter_occupied",
    "B17001_001E": "poverty_universe",
    "B17001_002E": "poverty_count",
}

PROJECT_ROOT  = Path(__file__).resolve().parents[3]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "demographics"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step 1 — Spatial helpers
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two WGS-84 points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def bounding_box(lat: float, lon: float, radius_km: float) -> dict:
    """
    Compute a rectangular bounding box that fully contains the circle.
    Returns min_lon, min_lat, max_lon, max_lat in decimal degrees.
    """
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * math.cos(math.radians(lat)))
    return {
        "min_lat": lat - lat_delta,
        "max_lat": lat + lat_delta,
        "min_lon": lon - lon_delta,
        "max_lon": lon + lon_delta,
    }


# ---------------------------------------------------------------------------
# Step 2 — Find tracts within the circle via TIGERweb
# ---------------------------------------------------------------------------

def get_tracts_in_radius(lat: float, lon: float, radius_km: float) -> pd.DataFrame:
    """
    Query TIGERweb for every census tract whose centroid falls within
    radius_km kilometres of (lat, lon).

    Returns a DataFrame with columns:
        geoid, state, county, tract, centroid_lat, centroid_lon, dist_km
    """
    bbox = bounding_box(lat, lon, radius_km)

    log.info(
        f"Querying TIGERweb — center ({lat}, {lon})  radius {radius_km} km"
    )
    log.info(
        f"  Bounding box: lat [{bbox['min_lat']:.4f}, {bbox['max_lat']:.4f}]"
        f"  lon [{bbox['min_lon']:.4f}, {bbox['max_lon']:.4f}]"
    )

    params = {
        "geometry": (
            f"{bbox['min_lon']},{bbox['min_lat']},"
            f"{bbox['max_lon']},{bbox['max_lat']}"
        ),
        "geometryType"   : "esriGeometryEnvelope",
        "inSR"           : "4326",
        "outSR"          : "4326",
        "outFields"      : "GEOID,STATE,COUNTY,TRACT,CENTLAT,CENTLON",
        "returnGeometry" : "false",
        "resultRecordCount": 2000,
        "f"              : "json",
    }

    resp = requests.get(TIGERWEB_URL, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise RuntimeError(f"TIGERweb API error: {data['error']}")

    features = data.get("features", [])
    log.info(f"  TIGERweb returned {len(features)} tracts in bounding box")

    rows = []
    for f in features:
        a = f["attributes"]
        clat = float(a["CENTLAT"])
        clon = float(a["CENTLON"])
        dist = haversine_km(lat, lon, clat, clon)
        if dist <= radius_km:
            # GEOID is 11 digits: SS  CCC  TTTTTT
            geoid = str(a["GEOID"]).zfill(11)
            rows.append({
                "geoid"       : geoid,
                "state"       : geoid[:2],
                "county"      : geoid[2:5],
                "tract"       : geoid[5:],
                "centroid_lat": clat,
                "centroid_lon": clon,
                "dist_km"     : round(dist, 2),
            })

    df = pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["geoid","state","county","tract",
                 "centroid_lat","centroid_lon","dist_km"]
    )
    log.info(
        f"  {len(df)} tracts within {radius_km} km  "
        f"(covering {df['state'].nunique()} state(s), "
        f"{df[['state','county']].drop_duplicates().shape[0]} county/ies)"
    )
    return df


# ---------------------------------------------------------------------------
# Step 3 — Pull ACS demographics for those tracts
# ---------------------------------------------------------------------------

def fetch_acs_for_tracts(tract_df: pd.DataFrame) -> pd.DataFrame:
    """
    Group tracts by state+county, make one ACS API call per group,
    then filter results to only the tracts in tract_df.
    """
    variables_str = "NAME," + ",".join(ACS_VARIABLES.keys())

    # Build lookup set of GEOIDs we actually want
    target_geoids = set(tract_df["geoid"].tolist())

    # Group by state + county  → one API call per combination
    groups = tract_df.groupby(["state", "county"])
    all_rows = []

    log.info(f"Fetching ACS {ACS_YEAR} 5-year — {len(groups)} county group(s)")

    for (state, county), _ in groups:
        params = {
            "get": variables_str,
            "for": "tract:*",
            "in" : f"state:{state} county:{county}",
        }
        resp = requests.get(ACS_BASE_URL, params=params, timeout=60)
        resp.raise_for_status()
        raw  = resp.json()
        cols = raw[0]
        for row in raw[1:]:
            rec = dict(zip(cols, row))
            geoid = rec["state"] + rec["county"] + rec["tract"]
            if geoid in target_geoids:
                all_rows.append(rec)

        log.info(
            f"  state={state} county={county}  → "
            f"{len(raw)-1} tracts in county, "
            f"{sum(1 for r in raw[1:] if (r[cols.index('state')]+r[cols.index('county')]+r[cols.index('tract')]) in target_geoids)} in radius"
        )

    if not all_rows:
        raise ValueError("No ACS data returned for the selected tracts.")

    df = pd.DataFrame(all_rows)
    log.info(f"ACS pull complete — {len(df)} tracts with demographics")
    return df


# ---------------------------------------------------------------------------
# Step 4 — Clean
# ---------------------------------------------------------------------------

def clean(acs_df: pd.DataFrame, tract_meta: pd.DataFrame) -> pd.DataFrame:
    """Rename, type-cast, derive columns, merge spatial metadata."""
    # Cast numeric
    num_cols = list(ACS_VARIABLES.keys())
    acs_df[num_cols] = acs_df[num_cols].apply(pd.to_numeric, errors="coerce")
    acs_df.replace(CENSUS_NULL, float("nan"), inplace=True)

    # Rename ACS codes → readable names
    acs_df = acs_df.rename(columns=ACS_VARIABLES)

    # Build GEOID
    acs_df["tract_geoid"] = acs_df["state"] + acs_df["county"] + acs_df["tract"]

    # Merge spatial metadata (centroid, distance)
    df = acs_df.merge(
        tract_meta[["geoid", "centroid_lat", "centroid_lon", "dist_km"]],
        left_on="tract_geoid",
        right_on="geoid",
        how="left",
    ).drop(columns=["geoid"])

    # Derived ratios
    df["poverty_rate"] = (df["poverty_count"] / df["poverty_universe"]).round(4)
    df["renter_share"] = (df["renter_occupied"] / df["tenure_total"]).round(4)
    df["owner_share"]  = (df["owner_occupied"]  / df["tenure_total"]).round(4)

    # Metadata
    df["acs_year"]   = ACS_YEAR
    df["fetched_at"] = datetime.now(timezone.utc).isoformat()

    # Final column order
    final_cols = [
        "tract_geoid",
        "NAME",
        "centroid_lat",
        "centroid_lon",
        "dist_km",
        "total_population",
        "total_households",
        "median_hh_income",
        "owner_occupied",
        "renter_occupied",
        "owner_share",
        "renter_share",
        "poverty_universe",
        "poverty_count",
        "poverty_rate",
        "acs_year",
        "fetched_at",
        "state",
        "county",
        "tract",
    ]
    df = df[[c for c in final_cols if c in df.columns]]
    df = df.sort_values("dist_km").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Step 5 — Validate
# ---------------------------------------------------------------------------

def validate(df: pd.DataFrame) -> None:
    errors = []
    if df.empty:
        errors.append("DataFrame is empty")
    if df["tract_geoid"].duplicated().any():
        errors.append(f"{df['tract_geoid'].duplicated().sum()} duplicate GEOIDs")
    if df["total_population"].lt(0).any():
        errors.append("Negative population values")
    null_pct = df["median_hh_income"].isna().mean() * 100
    if null_pct > 15:
        errors.append(
            f"median_hh_income null for {null_pct:.1f}% of tracts (threshold: 15%)"
        )
    if errors:
        raise ValueError("Validation failed:\n  " + "\n  ".join(errors))

    log.info(f"Validation passed — {len(df)} tracts, {df['tract_geoid'].nunique()} unique")
    log.info(f"  Population  : {df['total_population'].sum():,} total in area")
    log.info(f"  Income range: ${df['median_hh_income'].min():,.0f} – ${df['median_hh_income'].max():,.0f}")
    log.info(f"  Poverty rate: {df['poverty_rate'].min():.1%} – {df['poverty_rate'].max():.1%}")


# ---------------------------------------------------------------------------
# Step 6 — Save
# ---------------------------------------------------------------------------

def save(df: pd.DataFrame, lat: float, lon: float, radius_km: float) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{lat}_{lon}_{radius_km}km_tract_demographics"
    parquet_path = PROCESSED_DIR / f"{stem}.parquet"
    csv_path     = PROCESSED_DIR / f"{stem}.csv"

    df.to_parquet(parquet_path, index=False)
    df.to_csv(csv_path, index=False)

    log.info(f"Saved parquet → {parquet_path}  ({parquet_path.stat().st_size/1024:.1f} KB)")
    log.info(f"Saved CSV    → {csv_path}")
    return parquet_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(lat: float, lon: float, radius_km: float) -> pd.DataFrame:
    log.info("=" * 65)
    log.info(f"ACS Demographics Pipeline  —  ({lat}, {lon})  radius={radius_km} km")
    log.info("=" * 65)

    tract_meta = get_tracts_in_radius(lat, lon, radius_km)

    if tract_meta.empty:
        raise ValueError(
            f"No census tracts found within {radius_km} km of ({lat}, {lon})"
        )

    acs_raw  = fetch_acs_for_tracts(tract_meta)
    clean_df = clean(acs_raw, tract_meta)
    validate(clean_df)
    save(clean_df, lat, lon, radius_km)

    log.info("=" * 65)
    log.info("Pipeline complete ✓")
    log.info("=" * 65)
    return clean_df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch ACS 5-year tract demographics around a coordinate."
    )
    parser.add_argument("--lat",    type=float, required=True,
                        help="Latitude of center point (decimal degrees)")
    parser.add_argument("--lon",    type=float, required=True,
                        help="Longitude of center point (decimal degrees)")
    parser.add_argument("--radius", type=float, default=50.0,
                        help="Search radius in kilometres (default: 50)")
    args = parser.parse_args()

    df = run(lat=args.lat, lon=args.lon, radius_km=args.radius)

    print(f"\n--- Preview: closest 10 tracts to center ---")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 240)
    print(df[[
        "tract_geoid", "dist_km", "total_population",
        "median_hh_income", "owner_share", "renter_share", "poverty_rate"
    ]].head(10).to_string(index=False))
