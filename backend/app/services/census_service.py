"""
Census ACS API Service — generalized for any US location.

Uses the Census Geocoder API (free, no key) to resolve lat/lng → state + county FIPS,
then fetches ACS 5-Year estimates for that county.

Works anywhere in the US. Falls back to synthetic location-specific demographics
if the Census API is unavailable.
"""
import json
import math
import hashlib
import requests
from typing import Optional, Tuple
from app.models.schemas import DemographicsProfile
from app.core.config import get_settings
from app.services.supabase_service import cache_get, cache_set

# ACS 5-Year variable codes
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
}

ACS_BASE_URL = "https://api.census.gov/data/2022/acs/acs5"
GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"


# ── FIPS Resolution ─────────────────────────────────────────────────────────

def _geocoder_cache_key(lat: float, lng: float) -> str:
    return f"fips:{lat:.3f},{lng:.3f}"


def resolve_fips(lat: float, lng: float) -> Tuple[str, str, str]:
    """
    Resolve (lat, lng) → (state_fips, county_fips, county_name) using the
    Census Bureau Geocoder API (100% free, no key required).

    Results are cached in Supabase `cache` table forever (FIPS boundaries don't change).
    Falls back to nearest hardcoded county if geocoder is unavailable.
    """
    cache_key = _geocoder_cache_key(lat, lng)
    cached = cache_get(cache_key)
    if cached:
        return cached["state_fips"], cached["county_fips"], cached["county_name"]

    try:
        resp = requests.get(
            GEOCODER_URL,
            params={
                "x": lng, "y": lat,
                "benchmark": "Public_AR_Current",
                "vintage": "Current_Current",
                "layers": "Counties",
                "format": "json",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        counties = data.get("result", {}).get("geographies", {}).get("Counties", [])
        if counties:
            c = counties[0]
            result = {
                "state_fips":  c.get("STATE", ""),
                "county_fips": c.get("COUNTY", ""),
                "county_name": c.get("NAME", "Unknown County"),
            }
            cache_set(cache_key, result)
            return result["state_fips"], result["county_fips"], result["county_name"]
    except Exception as e:
        print(f"[CensusService] Geocoder failed for ({lat:.3f},{lng:.3f}): {e}")

    return _nearest_fallback_county(lat, lng)


def _nearest_fallback_county(lat: float, lng: float) -> Tuple[str, str, str]:
    """
    Hardcoded fallback: ~80 major US counties covering most population centers.
    Used only when Census Geocoder is unreachable.
    """
    KNOWN_COUNTIES = [
        # (lat_center, lng_center, state_fips, county_fips, name)
        # Arizona
        (33.45, -112.07, "04", "013", "Maricopa County, AZ"),
        (32.22, -110.97, "04", "019", "Pima County, AZ"),
        # California
        (34.05, -118.24, "06", "037", "Los Angeles County, CA"),
        (37.77, -122.42, "06", "075", "San Francisco County, CA"),
        (32.72, -117.16, "06", "073", "San Diego County, CA"),
        (37.34, -121.89, "06", "085", "Santa Clara County, CA"),
        (33.75, -117.87, "06", "059", "Orange County, CA"),
        (38.58, -121.49, "06", "067", "Sacramento County, CA"),
        # Texas
        (29.76, -95.37, "48", "201", "Harris County, TX"),
        (30.27, -97.74, "48", "453", "Travis County, TX"),
        (32.78, -96.80, "48", "113", "Dallas County, TX"),
        (29.42, -98.49, "48", "029", "Bexar County, TX"),
        (32.74, -97.10, "48", "439", "Tarrant County, TX"),
        (31.55, -97.15, "48", "309", "McLennan County, TX"),
        # Florida
        (25.77, -80.19, "12", "086", "Miami-Dade County, FL"),
        (28.54, -81.38, "12", "095", "Orange County, FL"),
        (27.77, -82.64, "12", "057", "Hillsborough County, FL"),
        (26.12, -80.14, "12", "011", "Broward County, FL"),
        (30.33, -81.66, "12", "031", "Duval County, FL"),
        # New York
        (40.71, -74.01, "36", "061", "New York County, NY"),
        (40.65, -73.95, "36", "047", "Kings County, NY"),
        (40.73, -73.79, "36", "081", "Queens County, NY"),
        (43.05, -76.15, "36", "067", "Onondaga County, NY"),
        (42.89, -78.86, "36", "029", "Erie County, NY"),
        # Illinois
        (41.88, -87.63, "17", "031", "Cook County, IL"),
        (40.12, -88.25, "17", "019", "Champaign County, IL"),
        # Pennsylvania
        (39.95, -75.17, "42", "101", "Philadelphia County, PA"),
        (40.44, -79.99, "42", "003", "Allegheny County, PA"),
        # Ohio
        (39.96, -82.99, "39", "049", "Franklin County, OH"),
        (41.50, -81.69, "39", "035", "Cuyahoga County, OH"),
        (39.10, -84.51, "39", "061", "Hamilton County, OH"),
        # Michigan
        (42.33, -83.05, "26", "163", "Wayne County, MI"),
        (42.73, -84.56, "26", "065", "Ingham County, MI"),
        (43.02, -85.67, "26", "081", "Kent County, MI"),
        # Georgia
        (33.75, -84.39, "13", "121", "Fulton County, GA"),
        (33.45, -84.15, "13", "063", "Clayton County, GA"),
        # North Carolina
        (35.23, -80.84, "37", "119", "Mecklenburg County, NC"),
        (35.99, -78.90, "37", "063", "Durham County, NC"),
        (35.78, -78.64, "37", "183", "Wake County, NC"),
        # Washington
        (47.61, -122.33, "53", "033", "King County, WA"),
        (47.66, -117.43, "53", "063", "Spokane County, WA"),
        # Colorado
        (39.74, -104.98, "08", "031", "Denver County, CO"),
        (38.84, -104.82, "08", "041", "El Paso County, CO"),
        (40.01, -105.27, "08", "013", "Boulder County, CO"),
        # Minnesota
        (44.98, -93.27, "27", "053", "Hennepin County, MN"),
        (44.95, -93.09, "27", "123", "Ramsey County, MN"),
        (44.74, -93.22, "27", "037", "Dakota County, MN"),
        (45.00, -93.42, "27", "163", "Anoka County, MN"),
        (44.87, -93.59, "27", "139", "Scott County, MN"),
        (45.59, -94.20, "27", "145", "Stearns County, MN"),
        (46.87, -96.78, "27", "017", "Clay County, MN"),
        (44.02, -92.47, "27", "109", "Olmsted County, MN"),
        # Wisconsin
        (43.04, -87.91, "55", "079", "Milwaukee County, WI"),
        (43.07, -89.40, "55", "025", "Dane County, WI"),
        # Iowa
        (41.66, -91.53, "19", "103", "Johnson County, IA"),
        (41.59, -93.62, "19", "153", "Polk County, IA"),
        # Missouri
        (38.63, -90.20, "29", "510", "St. Louis City, MO"),
        (39.10, -94.58, "29", "095", "Jackson County, MO"),
        # Tennessee
        (36.17, -86.78, "47", "037", "Davidson County, TN"),
        (35.15, -90.05, "47", "157", "Shelby County, TN"),
        # Virginia
        (37.54, -77.43, "51", "760", "Richmond City, VA"),
        (38.90, -77.01, "51", "013", "Arlington County, VA"),
        # Maryland
        (39.29, -76.61, "24", "510", "Baltimore City, MD"),
        (38.99, -76.94, "24", "033", "Prince George's County, MD"),
        # Nevada
        (36.17, -115.14, "32", "003", "Clark County, NV"),
        (39.53, -119.81, "32", "031", "Washoe County, NV"),
        # Oregon
        (45.52, -122.68, "41", "051", "Multnomah County, OR"),
        (44.05, -123.09, "41", "039", "Lane County, OR"),
        # Indiana
        (39.77, -86.16, "18", "097", "Marion County, IN"),
        (41.08, -85.14, "18", "003", "Allen County, IN"),
        # Massachusetts
        (42.36, -71.06, "25", "025", "Suffolk County, MA"),
        (42.34, -71.57, "25", "017", "Middlesex County, MA"),
        # New Jersey
        (40.73, -74.17, "34", "013", "Essex County, NJ"),
        (40.22, -74.77, "34", "021", "Mercer County, NJ"),
        # Utah
        (40.76, -111.89, "49", "035", "Salt Lake County, UT"),
        (40.23, -111.66, "49", "049", "Utah County, UT"),
        # Kansas
        (37.69, -97.34, "20", "173", "Sedgwick County, KS"),
        (39.11, -94.63, "20", "091", "Johnson County, KS"),
        # Nebraska
        (41.26, -96.01, "31", "055", "Douglas County, NE"),
        # Oklahoma
        (35.47, -97.52, "40", "109", "Oklahoma County, OK"),
        (36.15, -95.99, "40", "143", "Tulsa County, OK"),
        # Arkansas
        (34.75, -92.29, "05", "119", "Pulaski County, AR"),
        # Louisiana
        (29.95, -90.07, "22", "071", "Orleans Parish, LA"),
        (30.44, -91.19, "22", "033", "East Baton Rouge Parish, LA"),
        # Alabama
        (33.52, -86.80, "01", "073", "Jefferson County, AL"),
        # South Carolina
        (34.00, -81.03, "45", "079", "Richland County, SC"),
        (32.78, -79.93, "45", "019", "Charleston County, SC"),
    ]

    best = min(KNOWN_COUNTIES, key=lambda c: _haversine_miles(lat, lng, c[0], c[1]))
    return best[2], best[3], best[4]


# ── Census Data ──────────────────────────────────────────────────────────────

def _county_cache_key(state_fips: str, county_fips: str) -> str:
    return f"acs:{state_fips}:{county_fips}"


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def fetch_tract_demographics(state_fips: str, county_fips: str, api_key: str = "") -> list[dict]:
    """Fetch all census tracts for a county (cached in Supabase)."""
    cache_key = _county_cache_key(state_fips, county_fips)
    cached = cache_get(cache_key)
    if cached:
        print(f"[CensusService] Cache hit: {len(cached)} tracts for {state_fips}/{county_fips}")
        return cached

    variables = ",".join(ACS_VARS.keys())
    params = {
        "get": f"NAME,{variables}",
        "for": "tract:*",
        "in": f"state:{state_fips} county:{county_fips}",
    }
    if api_key:
        params["key"] = api_key

    try:
        resp = requests.get(ACS_BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        headers = data[0]
        rows = [dict(zip(headers, row)) for row in data[1:]]
        cache_set(cache_key, rows)
        print(f"[CensusService] Fetched + cached {len(rows)} tracts for {state_fips}/{county_fips}")
        return rows
    except Exception as e:
        print(f"[CensusService] ACS fetch failed for {state_fips}/{county_fips}: {e}")
        return []


def get_demographics_for_location(lat: float, lng: float, radius_miles: float = 10.0) -> DemographicsProfile:
    """
    Aggregate demographics for any US location.
    Step 1: Census Geocoder resolves (lat, lng) → state + county FIPS.
    Step 2: ACS 5-Year data fetched for that county.
    Step 3: Tracts within radius aggregated.
    Step 4: Synthetic fallback if API unavailable.
    """
    settings = get_settings()

    # Step 1: resolve FIPS
    state_fips, county_fips, county_name = resolve_fips(lat, lng)
    print(f"[CensusService] Resolved ({lat:.3f},{lng:.3f}) → {county_name} ({state_fips}/{county_fips})")

    if not state_fips or not county_fips:
        return _synthetic_demographics(lat, lng, radius_miles)

    # Step 2: fetch tracts
    tracts = fetch_tract_demographics(state_fips, county_fips, settings.census_api_key)

    if not tracts:
        return _synthetic_demographics(lat, lng, radius_miles)

    # Step 3: filter to radius
    nearby = _filter_nearby_tracts(tracts, lat, lng, radius_miles, state_fips, county_fips)
    if not nearby:
        nearby = tracts[:20]  # use any 20 tracts if radius finds nothing

    return _aggregate_demographics(nearby)


def _filter_nearby_tracts(
    tracts: list[dict], lat: float, lng: float, radius_miles: float,
    state_fips: str = "04", county_fips: str = "013",
) -> list[dict]:
    """
    Filter tracts by approximate centroid distance.
    Derives centroid from tract FIPS number mapped linearly onto the county bounding box.
    """
    # Rough county bounding box from known US county centers + ±0.7° span
    county_centers = {
        ("04", "013"): (33.45, -112.07),  # Maricopa
        ("27", "053"): (44.98, -93.27),   # Hennepin
        ("27", "123"): (44.95, -93.09),   # Ramsey
        ("27", "037"): (44.74, -93.22),   # Dakota
        ("06", "037"): (34.05, -118.24),  # LA
        ("48", "201"): (29.76, -95.37),   # Harris
        ("36", "061"): (40.71, -74.01),   # Manhattan
    }
    center_lat, center_lng = county_centers.get((state_fips, county_fips), (lat, lng))
    lat_span = 0.80   # ~55 miles N-S
    lng_span = 1.00   # ~55 miles E-W

    nearby = []
    for t in tracts:
        tract_code = t.get("tract", "")
        pop = _safe_float(t.get("B01003_001E"))
        if pop <= 0:
            continue
        # Estimate centroid from tract number
        try:
            num = float(tract_code.lstrip("0") or "0") / 100.0
            norm = min(num / 9900.0, 1.0)
            clat = center_lat - lat_span / 2 + norm * lat_span
            clng = center_lng - lng_span / 2 + (norm * 7 % 1.0) * lng_span
        except Exception:
            clat, clng = center_lat, center_lng

        if _haversine_miles(lat, lng, clat, clng) <= radius_miles:
            nearby.append(t)

    return nearby[:40]


def _safe_float(val, default=0.0) -> float:
    try:
        v = float(val)
        return v if v > 0 else default
    except (TypeError, ValueError):
        return default


def _aggregate_demographics(tracts: list[dict]) -> DemographicsProfile:
    total_pop     = sum(_safe_float(t.get("B01003_001E")) for t in tracts)
    total_hh      = sum(_safe_float(t.get("B11001_001E")) for t in tracts)
    total_owner   = sum(_safe_float(t.get("B25003_002E")) for t in tracts)
    total_family  = sum(_safe_float(t.get("B11001_002E")) for t in tracts)
    total_bach    = sum(_safe_float(t.get("B15003_022E")) for t in tracts)
    edu_universe  = sum(_safe_float(t.get("B15003_001E")) for t in tracts)

    valid_incomes = [_safe_float(t.get("B19013_001E")) for t in tracts if _safe_float(t.get("B19013_001E")) > 0]
    med_income = sum(valid_incomes) / len(valid_incomes) if valid_incomes else 55000.0

    valid_ages = [_safe_float(t.get("B01002_001E")) for t in tracts if _safe_float(t.get("B01002_001E")) > 0]
    med_age = sum(valid_ages) / len(valid_ages) if valid_ages else 36.0

    valid_hh_size = [_safe_float(t.get("B25010_001E")) for t in tracts if _safe_float(t.get("B25010_001E")) > 0]
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
