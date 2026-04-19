"""
Census ACS API Service — generalized for any US location.

Uses the Census Bureau TIGERweb API to find all census tracts within a given
radius, then pulls ACS 5-Year estimates (2023) for those exact tracts.

This replaces the county-level heuristic approach with the same high-accuracy
method used in backend/ingestion/demographics/fetch_acs_demographics.py
(main branch).

Falls back to synthetic location-specific demographics if the Census API
is unavailable.
"""
import json
import math
import hashlib
import logging
import requests
from typing import Optional, Tuple
from app.models.schemas import DemographicsProfile
from app.core.config import get_settings
from app.services.supabase_service import cache_get, cache_set

log = logging.getLogger(__name__)

# ── ACS 2023 variables ────────────────────────────────────────────────────────
ACS_VARS = {
    "B01003_001E": "population",
    "B19013_001E": "median_income",
    "B11001_001E": "household_count",
    "B25003_002E": "owner_occupied",
    "B11001_002E": "family_households",
    "B01002_001E": "median_age",
    "B15003_022E": "bachelors_degree",
    "B15003_001E": "edu_universe",
    "B25010_001E": "avg_household_size",
    # Extras for richer output (matches ingestion pipeline)
    "B25003_001E": "tenure_total",
    "B25003_003E": "renter_occupied",
    "B17001_001E": "poverty_universe",
    "B17001_002E": "poverty_count",
}

ACS_BASE_URL = "https://api.census.gov/data/2023/acs/acs5"        # ← 2023 data
TIGERWEB_URL = (
    "https://tigerweb.geo.census.gov/arcgis/rest/services"
    "/TIGERweb/Tracts_Blocks/MapServer/0/query"
)
CENSUS_NULL = -666666666


# ── Spatial helpers ───────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return _haversine_km(lat1, lng1, lat2, lng2) * 0.621371


def _bounding_box(lat: float, lon: float, radius_km: float) -> dict:
    """Rectangular bounding box that fully contains the circle."""
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * math.cos(math.radians(lat)))
    return {
        "min_lat": lat - lat_delta,
        "max_lat": lat + lat_delta,
        "min_lon": lon - lon_delta,
        "max_lon": lon + lon_delta,
    }


# ── Step 1: Find tracts within radius via TIGERweb ───────────────────────────

def get_tracts_in_radius(lat: float, lon: float, radius_km: float):
    """
    Query TIGERweb for every census tract whose centroid falls within
    radius_km kilometres of (lat, lon).

    Returns list of dicts with: geoid, state, county, tract,
    centroid_lat, centroid_lon, dist_km
    """
    cache_key = f"tigerweb:{lat:.3f},{lon:.3f},{radius_km}"
    cached = cache_get(cache_key)
    if cached:
        log.info(f"[CensusService] TIGERweb cache hit: {len(cached)} tracts")
        return cached

    bb = _bounding_box(lat, lon, radius_km)

    params = {
        "where"          : "1=1",
        "geometry"       : f"{bb['min_lon']},{bb['min_lat']},{bb['max_lon']},{bb['max_lat']}",
        "geometryType"   : "esriGeometryEnvelope",
        "spatialRel"     : "esriSpatialRelIntersects",
        "outFields"      : "STATE,COUNTY,TRACT,CENTLAT,CENTLON,GEOID",
        "returnGeometry" : "false",
        "f"              : "json",
        "resultRecordCount": 1000,
    }

    try:
        resp = requests.get(TIGERWEB_URL, params=params, timeout=30)
        resp.raise_for_status()
        features = resp.json().get("features", [])
        log.info(f"[CensusService] TIGERweb returned {len(features)} tracts in bounding box")
    except Exception as e:
        log.error(f"[CensusService] TIGERweb failed: {e}")
        return []

    tracts = []
    for feat in features:
        attrs = feat.get("attributes", {})
        clat = attrs.get("CENTLAT")
        clon = attrs.get("CENTLON")
        if clat is None or clon is None:
            continue
        try:
            clat, clon = float(clat), float(clon)
        except (ValueError, TypeError):
            continue

        dist_km = _haversine_km(lat, lon, clat, clon)
        if dist_km > radius_km:
            continue

        tracts.append({
            "geoid"       : attrs.get("GEOID", ""),
            "state"       : str(attrs.get("STATE", "")).zfill(2),
            "county"      : str(attrs.get("COUNTY", "")).zfill(3),
            "tract"       : str(attrs.get("TRACT", "")).zfill(6),
            "centroid_lat": round(clat, 6),
            "centroid_lon": round(clon, 6),
            "dist_km"     : round(dist_km, 3),
        })

    tracts.sort(key=lambda t: t["dist_km"])
    log.info(f"[CensusService] {len(tracts)} tracts within {radius_km} km of ({lat:.3f},{lon:.3f})")

    if tracts:
        cache_set(cache_key, tracts)

    return tracts


# ── Step 2: Fetch ACS data for those specific tracts ─────────────────────────

def _acs_county_cache_key(state: str, county: str) -> str:
    return f"acs2023:{state}:{county}"


def _fetch_acs_county(state: str, county: str, api_key: str = "") -> list[dict]:
    """Pull all ACS tracts for a state+county combo (cached)."""
    cache_key = _acs_county_cache_key(state, county)
    cached = cache_get(cache_key)
    if cached:
        log.info(f"[CensusService] ACS cache hit: {len(cached)} tracts for {state}/{county}")
        return cached

    variables_str = "NAME," + ",".join(ACS_VARS.keys())
    params = {
        "get": variables_str,
        "for": "tract:*",
        "in" : f"state:{state} county:{county}",
    }
    if api_key:
        params["key"] = api_key

    try:
        resp = requests.get(ACS_BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        raw = resp.json()
        headers = raw[0]
        rows = [dict(zip(headers, row)) for row in raw[1:]]
        log.info(f"[CensusService] ACS 2023: fetched {len(rows)} tracts for state={state} county={county}")
        cache_set(cache_key, rows)
        return rows
    except Exception as e:
        log.error(f"[CensusService] ACS fetch failed for {state}/{county}: {e}")
        return []


# ── Step 3: Aggregate demographics ───────────────────────────────────────────

def _safe_float(val, default=0.0) -> float:
    try:
        v = float(val)
        return v if v > 0 and v != CENSUS_NULL else default
    except (TypeError, ValueError):
        return default


def get_demographics_for_location(
    lat: float, lng: float, radius_miles: float = 10.0
) -> DemographicsProfile:
    """
    Aggregate demographics for any US location using TIGERweb tract resolution.

    Step 1: TIGERweb finds all tracts whose centroid is within radius.
    Step 2: ACS 2023 5-Year fetched per state+county group.
    Step 3: Only tracts from step 1 are used.
    Step 4: Synthetic fallback if APIs unavailable.
    """
    settings = get_settings()
    radius_km = radius_miles * 1.60934

    # Step 1: find tracts
    tract_meta = get_tracts_in_radius(lat, lng, radius_km)
    if not tract_meta:
        log.warning("[CensusService] No tracts found via TIGERweb — using synthetic fallback")
        return _synthetic_demographics(lat, lng, radius_miles)

    # Build lookup: geoid → metadata
    tract_lookup = {t["geoid"]: t for t in tract_meta}

    # Step 2: fetch by county group
    from itertools import groupby
    keyfn = lambda t: (t["state"], t["county"])
    tract_meta_sorted = sorted(tract_meta, key=keyfn)

    county_name = "Unknown"
    acs_rows = []
    for (state, county), group in groupby(tract_meta_sorted, key=keyfn):
        wanted_geoids = {t["geoid"] for t in group}
        county_rows = _fetch_acs_county(state, county, settings.census_api_key)
        # Filter to only the tracts within radius
        for row in county_rows:
            geoid = row.get("state", "") + row.get("county", "") + row.get("tract", "")
            if geoid in wanted_geoids:
                # Inject centroid metadata
                row["_centroid_lat"] = tract_lookup.get(geoid, {}).get("centroid_lat")
                row["_centroid_lon"] = tract_lookup.get(geoid, {}).get("centroid_lon")
                row["_dist_km"]      = tract_lookup.get(geoid, {}).get("dist_km")
                acs_rows.append(row)
        if county_rows:
            # Grab county name from first valid NAME field
            names = [r.get("NAME", "") for r in county_rows if r.get("NAME")]
            if names:
                # NAME = "Census Tract XXXX; County; State" — extract county
                parts = names[0].split(";")
                if len(parts) >= 2:
                    county_name = parts[1].strip()

    if not acs_rows:
        log.warning("[CensusService] No ACS rows matched TIGERweb tracts — using synthetic fallback")
        return _synthetic_demographics(lat, lng, radius_miles)

    tracts_used = len(acs_rows)
    log.info(f"[CensusService] Aggregating {tracts_used} tracts in {county_name}")

    return _aggregate_demographics(acs_rows, county_name)


def _aggregate_demographics(tracts: list[dict], county_name: str = "Unknown") -> DemographicsProfile:
    total_pop     = sum(_safe_float(t.get("B01003_001E")) for t in tracts)
    total_hh      = sum(_safe_float(t.get("B11001_001E")) for t in tracts)
    total_owner   = sum(_safe_float(t.get("B25003_002E")) for t in tracts)
    total_family  = sum(_safe_float(t.get("B11001_002E")) for t in tracts)
    total_bach    = sum(_safe_float(t.get("B15003_022E")) for t in tracts)
    edu_universe  = sum(_safe_float(t.get("B15003_001E")) for t in tracts)

    valid_incomes = [_safe_float(t.get("B19013_001E")) for t in tracts if _safe_float(t.get("B19013_001E")) > 1000]
    med_income = sum(valid_incomes) / len(valid_incomes) if valid_incomes else 55000.0

    valid_ages = [_safe_float(t.get("B01002_001E")) for t in tracts if _safe_float(t.get("B01002_001E")) > 1]
    med_age = sum(valid_ages) / len(valid_ages) if valid_ages else 36.0

    valid_hh_size = [_safe_float(t.get("B25010_001E")) for t in tracts if _safe_float(t.get("B25010_001E")) > 0.5]
    avg_hh_size = sum(valid_hh_size) / len(valid_hh_size) if valid_hh_size else 2.7

    owner_pct   = (total_owner / total_hh * 100) if total_hh > 0 else 60.0
    family_pct  = (total_family / total_hh * 100) if total_hh > 0 else 65.0
    college_pct = (total_bach / edu_universe * 100) if edu_universe > 0 else 30.0

    income_index  = min(med_income / 75000.0, 1.5)
    pop_score     = min(total_pop / 50000.0, 1.0) * 40
    income_score  = income_index * 30
    growth_score  = 14.0  # neutral
    college_score = min(college_pct / 50.0, 1.0) * 10
    demand_score  = min(pop_score + income_score + growth_score + college_score, 100.0)

    return DemographicsProfile(
        population=int(total_pop),
        median_income=round(med_income, 0),
        household_count=int(total_hh),
        avg_household_size=round(avg_hh_size, 1),
        owner_occupied_pct=round(owner_pct, 1),
        family_households_pct=round(family_pct, 1),
        median_age=round(med_age, 1),
        college_educated_pct=round(college_pct, 1),
        population_growth_est=1.2,
        demand_score=round(demand_score, 1),
    )


def _synthetic_demographics(lat: float, lng: float, radius_miles: float = 10.0) -> DemographicsProfile:
    """
    Location-specific synthetic demographics seeded by coordinate hash.
    Used when Census API is unreachable. No two locations produce identical values.
    """
    seed = int(hashlib.md5(f"{lat:.3f},{lng:.3f}".encode()).hexdigest(), 16)
    rng = lambda offset, lo, hi: lo + ((seed + offset * 7919) % 1000) / 1000.0 * (hi - lo)

    pop    = int(rng(1, 30000, 180000))
    income = round(rng(2, 38000, 130000), 0)
    hh     = int(pop / rng(3, 2.3, 3.2))
    fam    = round(rng(4, 50.0, 78.0), 1)
    col    = round(rng(5, 18.0, 55.0), 1)
    own    = round(rng(6, 45.0, 80.0), 1)
    age    = round(rng(7, 28.0, 45.0), 1)
    hh_sz  = round(rng(8, 2.2, 3.4), 1)

    demand = round(min(
        min(pop / 50000.0, 1.0) * 40
        + min(income / 75000.0, 1.5) * 30
        + 14
        + min(col / 50.0, 1.0) * 10,
        100.0
    ), 1)

    return DemographicsProfile(
        population=pop, median_income=income, household_count=hh,
        avg_household_size=hh_sz, owner_occupied_pct=own,
        family_households_pct=fam, median_age=age,
        college_educated_pct=col,
        population_growth_est=round(rng(9, 0.5, 4.5), 1),
        demand_score=demand,
    )
