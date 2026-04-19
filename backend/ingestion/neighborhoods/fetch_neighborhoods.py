"""
Minneapolis Neighborhood Context Ingestion Pipeline
-----------------------------------------------------
Source  : Minneapolis Open Data ArcGIS REST API
          - Minneapolis_Neighborhoods (87 official neighborhoods)
Output  : data/processed/neighborhoods/minneapolis_neighborhoods.parquet
          data/processed/neighborhoods/minneapolis_neighborhoods.csv
          data/processed/neighborhoods/minneapolis_neighborhoods.geojson

This is a reference dataset — run once, re-run to refresh.
No coordinate input needed; it always fetches all 87 neighborhoods.

What this gives you downstream:
  - Neighborhood name for any candidate site (spatial point-in-polygon)
  - Neighborhood centroid for distance calculations
  - Neighborhood ID (BDNUM) to join with other city datasets
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NEIGHBORHOODS_URL = (
    "https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services"
    "/Minneapolis_Neighborhoods/FeatureServer/0/query"
)

PROJECT_ROOT  = Path(__file__).resolve().parents[3]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "neighborhoods"

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
# Step 1 — Fetch all neighborhoods with polygon geometry
# ---------------------------------------------------------------------------

def fetch_neighborhoods() -> tuple[pd.DataFrame, dict]:
    """
    Fetch all 87 Minneapolis neighborhoods.
    Returns:
      - df       : flat DataFrame with neighborhood attributes + centroid
      - geojson  : GeoJSON FeatureCollection (for mapping / spatial joins)
    """
    log.info("Fetching Minneapolis neighborhoods from Open Data portal...")

    params = {
        "where"          : "1=1",
        "outFields"      : "OBJECTID,BDNAME,BDNUM,INT_REFNO,SYMBOL_NAM",
        "returnGeometry" : "true",     # need polygons for centroids + GeoJSON
        "outSR"          : "4326",     # WGS-84 lat/lon
        "f"              : "geojson",  # ask ArcGIS to return GeoJSON directly
    }

    resp = requests.get(NEIGHBORHOODS_URL, params=params, timeout=60)
    resp.raise_for_status()
    geojson = resp.json()

    features = geojson.get("features", [])
    log.info(f"  Received {len(features)} neighborhoods")
    return features, geojson


# ---------------------------------------------------------------------------
# Step 2 — Compute centroid from polygon ring
# ---------------------------------------------------------------------------

def polygon_centroid(geometry: dict) -> tuple[float, float]:
    """
    Simple centroid estimate: average of outer ring coordinates.
    Accurate enough for neighborhood-level labelling.
    """
    try:
        geo_type = geometry.get("type", "")
        if geo_type == "Polygon":
            coords = geometry["coordinates"][0]
        elif geo_type == "MultiPolygon":
            # Use the largest ring
            coords = max(geometry["coordinates"], key=lambda p: len(p[0]))[0]
        else:
            return None, None
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        return round(sum(lats) / len(lats), 6), round(sum(lons) / len(lons), 6)
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Step 3 — Build flat DataFrame
# ---------------------------------------------------------------------------

def build_dataframe(features: list) -> pd.DataFrame:
    rows = []
    for feat in features:
        props = feat.get("properties", {})
        geom  = feat.get("geometry", {})
        clat, clon = polygon_centroid(geom)
        rows.append({
            "neighborhood_id"  : props.get("BDNUM"),
            "neighborhood_name": props.get("BDNAME"),
            "symbol_name"      : props.get("SYMBOL_NAM"),
            "int_refno"        : props.get("INT_REFNO"),
            "centroid_lat"     : clat,
            "centroid_lon"     : clon,
            "fetched_at"       : datetime.now(timezone.utc).isoformat(),
        })
    df = pd.DataFrame(rows)
    df = df.sort_values("neighborhood_name").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Step 4 — Validate
# ---------------------------------------------------------------------------

def validate(df: pd.DataFrame) -> None:
    errors = []
    if df.empty:
        errors.append("DataFrame is empty")
    if df["neighborhood_name"].isna().any():
        errors.append(f"{df['neighborhood_name'].isna().sum()} rows missing neighborhood name")
    if df["centroid_lat"].isna().any():
        n = df["centroid_lat"].isna().sum()
        log.warning(f"  {n} neighborhoods missing centroid — geometry may be null")
    if errors:
        raise ValueError("Validation failed:\n  " + "\n  ".join(errors))
    log.info(f"Validation passed — {len(df)} neighborhoods")
    log.info(f"  Sample names: {df['neighborhood_name'].head(5).tolist()}")


# ---------------------------------------------------------------------------
# Step 5 — Save (parquet + CSV + GeoJSON)
# ---------------------------------------------------------------------------

def save(df: pd.DataFrame, geojson: dict) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    parquet_path = PROCESSED_DIR / "minneapolis_neighborhoods.parquet"
    csv_path     = PROCESSED_DIR / "minneapolis_neighborhoods.csv"
    geojson_path = PROCESSED_DIR / "minneapolis_neighborhoods.geojson"

    df.to_parquet(parquet_path, index=False)
    df.to_csv(csv_path, index=False)

    with open(geojson_path, "w") as f:
        json.dump(geojson, f)

    log.info(f"Saved parquet → {parquet_path}  ({parquet_path.stat().st_size/1024:.1f} KB)")
    log.info(f"Saved CSV    → {csv_path}")
    log.info(f"Saved GeoJSON → {geojson_path}  ({geojson_path.stat().st_size/1024:.1f} KB)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run() -> pd.DataFrame:
    log.info("=" * 65)
    log.info("Minneapolis Neighborhood Context Pipeline")
    log.info("=" * 65)

    features, geojson = fetch_neighborhoods()
    df       = build_dataframe(features)
    validate(df)
    save(df, geojson)

    log.info("=" * 65)
    log.info("Pipeline complete ✓")
    log.info("=" * 65)
    return df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    df = run()
    print("\n--- All Minneapolis neighborhoods (sorted) ---")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 160)
    print(df[["neighborhood_id", "neighborhood_name", "centroid_lat", "centroid_lon"]].to_string(index=False))
