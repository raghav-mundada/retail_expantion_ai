"""
Commercial Parcel & Site Ingestion Pipeline
--------------------------------------------
Source  : Minneapolis Open Data ArcGIS REST API
          - CommercialRetailUses  (parcel-level commercial sites)
          - Assessor_Parcels_2024 (market value, build year, sale data)
Geography: Coordinate + radius (same interface as demographics pipeline)
Output  : data/processed/parcels/<lat>_<lon>_<radius>km_parcels.parquet
          data/processed/parcels/<lat>_<lon>_<radius>km_parcels.csv

Usage:
    python fetch_parcels.py --lat 44.977 --lon -93.265 --radius 10
    python fetch_parcels.py --lat 44.977 --lon -93.265 --radius 25 --min-acres 0.5

Commercial CommType values in dataset:
    Activity Center | Community Commercial | Neighborhood Commercial
    Scattered Commercial | Transit Station Area

Land Use codes (LAND_USE field):
    CRET = Retail | CMXD = Mixed Commercial | CAUT = Auto Commercial
    CBRE = Commercial Real Estate | COFF = Office
"""

import argparse
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMMERCIAL_URL = (
    "https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services"
    "/CommercialRetailUses/FeatureServer/0/query"
)
ASSESSOR_URL = (
    "https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services"
    "/Assessor_Parcels_2024/FeatureServer/0/query"
)

# Fields we want from each source
COMMERCIAL_FIELDS = (
    "PID,HOUSENUM,STREETNM,ZIPCD,LATITUDE,LONGITUDE,"
    "LAND_USE,BLDG_USE,ELUC,TwoLetterE,Acres,CommType"
)
ASSESSOR_FIELDS = (
    "PID,MKT_VAL_TO,TAXABLE_VA,BUILD_YR,SALE_DATE,SALE_PRICE,PR_TYP_NM1"
)

# Land use codes to prioritise (retail-compatible)
RETAIL_LAND_USES = {"CRET", "CMXD", "CBRE", "COFF"}

PROJECT_ROOT  = Path(__file__).resolve().parents[3]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "parcels"

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
# Spatial helpers (same as demographics pipeline)
# ---------------------------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def bounding_box(lat, lon, radius_km):
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * math.cos(math.radians(lat)))
    return {
        "min_lat": lat - lat_delta, "max_lat": lat + lat_delta,
        "min_lon": lon - lon_delta, "max_lon": lon + lon_delta,
    }


# ---------------------------------------------------------------------------
# Step 1 — Fetch commercial parcels (paginated, bbox pre-filter)
# ---------------------------------------------------------------------------

def fetch_commercial_parcels(lat: float, lon: float, radius_km: float) -> pd.DataFrame:
    """
    Pull all commercial retail parcels from Minneapolis Open Data,
    using a bounding-box WHERE clause to cut down the initial fetch,
    then filter exactly by haversine distance.
    """
    bbox = bounding_box(lat, lon, radius_km)
    where = (
        f"LATITUDE >= {bbox['min_lat']} AND LATITUDE <= {bbox['max_lat']} "
        f"AND LONGITUDE >= {bbox['min_lon']} AND LONGITUDE <= {bbox['max_lon']}"
    )

    log.info(f"Fetching commercial parcels — bbox pre-filter ({radius_km} km)")
    all_rows = []
    offset   = 0
    page_size = 1000

    while True:
        params = {
            "where"            : where,
            "outFields"        : COMMERCIAL_FIELDS,
            "returnGeometry"   : "false",
            "resultOffset"     : offset,
            "resultRecordCount": page_size,
            "f"                : "json",
        }
        resp = requests.get(COMMERCIAL_URL, params=params, timeout=60)
        resp.raise_for_status()
        feats = resp.json().get("features", [])
        if not feats:
            break
        all_rows.extend(f["attributes"] for f in feats)
        log.info(f"  Fetched {len(all_rows)} commercial parcels so far...")
        if len(feats) < page_size:
            break
        offset += page_size

    df = pd.DataFrame(all_rows)
    if df.empty:
        return df

    # Exact distance filter
    df["LATITUDE"]  = pd.to_numeric(df["LATITUDE"],  errors="coerce")
    df["LONGITUDE"] = pd.to_numeric(df["LONGITUDE"], errors="coerce")
    df = df.dropna(subset=["LATITUDE", "LONGITUDE"])
    df["dist_km"] = df.apply(
        lambda r: haversine_km(lat, lon, r["LATITUDE"], r["LONGITUDE"]), axis=1
    )
    df = df[df["dist_km"] <= radius_km].copy()
    df["Acres"] = pd.to_numeric(df["Acres"], errors="coerce")

    log.info(
        f"  {len(df)} commercial parcels within {radius_km} km  "
        f"| CommTypes: {dict(df['CommType'].value_counts())}"
    )
    return df


# ---------------------------------------------------------------------------
# Step 2 — Join assessor data for value / build year
# ---------------------------------------------------------------------------

def fetch_assessor_data(pids: list) -> pd.DataFrame:
    """
    Pull market value, build year, sale info from Assessor_Parcels_2024
    for a specific list of PIDs (batched, using POST to avoid URL limits).
    """
    if not pids:
        return pd.DataFrame()

    log.info(f"Fetching assessor data for {len(pids)} PIDs...")
    BATCH = 300
    all_rows = []

    for i in range(0, len(pids), BATCH):
        batch    = pids[i : i + BATCH]
        pid_list = ",".join(f"'{p}'" for p in batch)   # PIDs are strings — must be quoted
        # Use POST to avoid URL length limits with large PID lists
        data = {
            "where"          : f"PID IN ({pid_list})",
            "outFields"      : ASSESSOR_FIELDS,
            "returnGeometry" : "false",
            "f"              : "json",
        }
        resp = requests.post(ASSESSOR_URL, data=data, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        if "error" in result:
            log.warning(f"  Assessor batch error: {result['error']}")
            continue
        feats = result.get("features", [])
        all_rows.extend(f["attributes"] for f in feats)
        log.info(f"  Assessor batch {i//BATCH + 1}: {len(feats)} records")

    df = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
    log.info(f"  Assessor returned {len(df)} total matching records")
    return df


# ---------------------------------------------------------------------------
# Step 3 — Clean and merge
# ---------------------------------------------------------------------------

def clean(commercial_df: pd.DataFrame, assessor_df: pd.DataFrame) -> pd.DataFrame:
    df = commercial_df.copy()

    # Rename commercial fields
    df = df.rename(columns={
        "HOUSENUM"   : "house_no",
        "STREETNM"   : "street_name",
        "ZIPCD"      : "zip_code",
        "LATITUDE"   : "latitude",
        "LONGITUDE"  : "longitude",
        "LAND_USE"   : "land_use_code",
        "BLDG_USE"   : "bldg_use_code",
        "ELUC"       : "eluc",
        "TwoLetterE" : "eluc_short",
        "Acres"      : "parcel_acres",
        "CommType"   : "commercial_type",
    })

    # Merge assessor data on PID
    if not assessor_df.empty:
        assessor_clean = assessor_df.rename(columns={
            "MKT_VAL_TO" : "market_value",
            "TAXABLE_VA" : "taxable_value",
            "BUILD_YR"   : "build_year",
            "SALE_DATE"  : "sale_date_ms",  # epoch ms from ArcGIS
            "SALE_PRICE" : "sale_price",
            "PR_TYP_NM1" : "property_type",
        })
        assessor_clean["PID"] = assessor_clean["PID"].astype(str)
        df["PID"]             = df["PID"].astype(str)
        df = df.merge(assessor_clean, on="PID", how="left")

        # Convert sale_date from epoch ms to readable date
        df["sale_date"] = pd.to_datetime(
            df["sale_date_ms"], unit="ms", errors="coerce"
        ).dt.strftime("%Y-%m-%d")
        df = df.drop(columns=["sale_date_ms"], errors="ignore")

        # Numeric casts
        for col in ["market_value", "taxable_value", "sale_price", "build_year"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df.replace(-1, float("nan"), inplace=True)

    # Derive address
    df["address"] = (
        df["house_no"].fillna("").astype(str).str.strip()
        + " "
        + df["street_name"].fillna("").astype(str).str.strip()
    ).str.strip()

    # Flag retail-compatible land use
    df["is_retail_compatible"] = df["land_use_code"].isin(RETAIL_LAND_USES)

    # Land use label map
    lu_labels = {
        "CRET": "Retail",
        "CMXD": "Mixed Commercial",
        "CAUT": "Auto Commercial",
        "CBRE": "Commercial Real Estate",
        "COFF": "Office",
        "HMTL": "Hotel/Motel",
        "GMRS": "General Merchandise",
    }
    df["land_use_label"] = df["land_use_code"].map(lu_labels).fillna(df["land_use_code"])

    # Metadata
    df["fetched_at"] = datetime.now(timezone.utc).isoformat()

    # Final column order
    cols = [
        "PID", "address", "zip_code",
        "latitude", "longitude", "dist_km",
        "land_use_code", "land_use_label", "bldg_use_code",
        "eluc_short", "commercial_type",
        "parcel_acres", "is_retail_compatible",
        "market_value", "taxable_value",
        "build_year", "sale_date", "sale_price",
        "property_type", "fetched_at",
    ]
    return df[[c for c in cols if c in df.columns]].sort_values("dist_km").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Step 4 — Validate
# ---------------------------------------------------------------------------

def validate(df: pd.DataFrame, radius_km: float) -> None:
    errors = []
    if df.empty:
        errors.append("No parcels found")
    if df["dist_km"].max() > radius_km + 0.1:
        errors.append("Parcels found beyond radius — distance filter failed")
    if errors:
        raise ValueError("Validation failed:\n  " + "\n  ".join(errors))

    log.info(f"Validation passed — {len(df)} commercial parcels")
    log.info(f"  Retail-compatible : {df['is_retail_compatible'].sum()} parcels")
    log.info(f"  Parcel size       : {df['parcel_acres'].min():.2f} – {df['parcel_acres'].max():.2f} acres")
    if "market_value" in df:
        mv = df["market_value"].dropna()
        if not mv.empty:
            log.info(f"  Market value      : ${mv.min():,.0f} – ${mv.max():,.0f}")
    log.info(f"  CommType breakdown:\n" +
             "\n".join(f"    {k}: {v}" for k, v in df["commercial_type"].value_counts().items()))


# ---------------------------------------------------------------------------
# Step 5 — Save
# ---------------------------------------------------------------------------

def save(df: pd.DataFrame, lat: float, lon: float, radius_km: float) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    stem        = f"{lat}_{lon}_{radius_km}km_parcels"
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

def run(lat: float, lon: float, radius_km: float, min_acres: float = 0.0) -> pd.DataFrame:
    log.info("=" * 65)
    log.info(f"Parcel Ingestion Pipeline  —  ({lat}, {lon})  radius={radius_km} km")
    log.info("=" * 65)

    commercial_df = fetch_commercial_parcels(lat, lon, radius_km)

    if commercial_df.empty:
        raise ValueError(f"No commercial parcels found within {radius_km} km of ({lat}, {lon})")

    # Optional min parcel size filter
    if min_acres > 0 and "Acres" in commercial_df.columns:
        before = len(commercial_df)
        commercial_df = commercial_df[
            commercial_df["Acres"].fillna(0) >= min_acres
        ]
        log.info(f"  Min acres filter ({min_acres}): {before} → {len(commercial_df)} parcels")

    pids        = commercial_df["PID"].dropna().astype(str).tolist()
    assessor_df = fetch_assessor_data(pids)
    clean_df    = clean(commercial_df, assessor_df)
    validate(clean_df, radius_km)
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
        description="Fetch commercial parcel data around a coordinate."
    )
    parser.add_argument("--lat",       type=float, required=True)
    parser.add_argument("--lon",       type=float, required=True)
    parser.add_argument("--radius",    type=float, default=10.0,
                        help="Radius in kilometres (default: 10)")
    parser.add_argument("--min-acres", type=float, default=0.0,
                        help="Minimum parcel size in acres (default: 0 = no filter)")
    args = parser.parse_args()

    df = run(lat=args.lat, lon=args.lon, radius_km=args.radius, min_acres=args.min_acres)

    print(f"\n--- Preview: closest 10 commercial parcels ---")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 260)
    print(df[[
        "PID", "address", "dist_km", "commercial_type",
        "land_use_label", "parcel_acres", "market_value", "build_year"
    ]].head(10).to_string(index=False))
