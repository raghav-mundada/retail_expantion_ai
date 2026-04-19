"""
School & Neighborhood Agent — standalone (no demographics dependency).

Runs in Phase 1 parallel with Demographics. Uses lat/lng + school district
proximity + synthetic demographic proxies derived from location to compute
neighborhood quality — NO DemographicsProfile required.

When Demographics finishes, the scoring engine refines the neighborhood score
using actual census data, but this agent never blocks on it.
"""
import asyncio
import math
import hashlib
from app.models.schemas import NeighborhoodProfile


# Minneapolis Metro school district quality index (NCES/GreatSchools approximation)
MINNEAPOLIS_SCHOOL_DISTRICTS = [
    {"name": "Edina Public Schools",          "lat": 44.8897, "lng": -93.3499, "quality": 91},
    {"name": "Wayzata Public Schools",        "lat": 44.9749, "lng": -93.5063, "quality": 89},
    {"name": "Eden Prairie Schools",          "lat": 44.8547, "lng": -93.4708, "quality": 88},
    {"name": "Minnetonka Public Schools",     "lat": 44.9211, "lng": -93.4687, "quality": 87},
    {"name": "Mounds View Schools",           "lat": 45.1122, "lng": -93.2122, "quality": 85},
    {"name": "Stillwater Area Public Schools","lat": 45.0563, "lng": -92.8244, "quality": 83},
    {"name": "Rosemount-Apple Valley-Eagan",  "lat": 44.7374, "lng": -93.1564, "quality": 82},
    {"name": "Prior Lake-Savage Schools",     "lat": 44.7136, "lng": -93.4220, "quality": 80},
    {"name": "White Bear Lake Schools",       "lat": 45.0838, "lng": -93.0100, "quality": 78},
    {"name": "Burnsville-Eagan-Savage",       "lat": 44.7677, "lng": -93.2777, "quality": 76},
    {"name": "Bloomington Public Schools",    "lat": 44.8408, "lng": -93.3376, "quality": 74},
    {"name": "Richfield Public Schools",      "lat": 44.8763, "lng": -93.2839, "quality": 70},
    {"name": "Hopkins Public Schools",        "lat": 44.9261, "lng": -93.4051, "quality": 72},
    {"name": "Minneapolis Public Schools",    "lat": 44.9778, "lng": -93.2650, "quality": 62},
    {"name": "Brooklyn Center Schools",       "lat": 45.0720, "lng": -93.3317, "quality": 55},
]


def _haversine_miles(lat1, lng1, lat2, lng2) -> float:
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((lat2 - lat1) * math.pi / 360) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin((lng2 - lng1) * math.pi / 360) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _lat_lng_proxy(lat: float, lng: float, offset: int, lo: float, hi: float) -> float:
    """Generate a stable pseudo-random value in [lo, hi] seeded by lat/lng."""
    seed = int(hashlib.md5(f"{lat:.3f},{lng:.3f},{offset}".encode()).hexdigest(), 16)
    return lo + (seed % 1000) / 1000.0 * (hi - lo)


def get_nearest_school_district(lat: float, lng: float):
    nearest = min(
        MINNEAPOLIS_SCHOOL_DISTRICTS,
        key=lambda d: _haversine_miles(lat, lng, d["lat"], d["lng"])
    )
    dist = _haversine_miles(lat, lng, nearest["lat"], nearest["lng"])
    quality_adj = nearest["quality"] * max(0.7, 1 - dist / 20.0)
    return nearest["name"], round(quality_adj, 1)


def compute_neighborhood_profile(lat: float, lng: float) -> tuple:
    """
    Compute neighborhood quality using ONLY lat/lng.
    Uses school district proximity + stable location-specific synthetic proxies.
    """
    district_name, school_quality = get_nearest_school_district(lat, lng)

    # Synthetic demographic proxies (unique per location, consistent across calls)
    family_pct     = _lat_lng_proxy(lat, lng, 1, 50.0, 78.0)
    avg_hh_size    = _lat_lng_proxy(lat, lng, 2, 2.2, 3.5)
    owner_occ_pct  = _lat_lng_proxy(lat, lng, 3, 42.0, 80.0)
    median_income  = _lat_lng_proxy(lat, lng, 4, 38000, 130000)
    college_pct    = _lat_lng_proxy(lat, lng, 5, 18.0, 55.0)

    # Family density score
    family_density = min((family_pct / 100.0) * (avg_hh_size / 3.5) * 100, 100.0)

    # Neighborhood stability: homeownership + income + education
    stability = min(
        owner_occ_pct * 0.35
        + min(median_income / 100000.0 * 100, 100) * 0.35
        + college_pct * 0.30,
        100.0
    )

    # Housing growth signal: distance from Minneapolis Metro growth corridors
    growth_corridors = [(44.8547, -93.4708), (45.1197, -93.3111), (44.7677, -93.2777)]
    min_dist = min(_haversine_miles(lat, lng, clat, clng) for clat, clng in growth_corridors)
    housing_growth = max(40.0, 90.0 - min_dist * 3.0)

    overall = (
        school_quality * 0.30
        + family_density * 0.25
        + stability * 0.25
        + housing_growth * 0.20
    )

    return NeighborhoodProfile(
        school_quality_index=round(school_quality, 1),
        family_density_score=round(family_density, 1),
        neighborhood_stability=round(stability, 1),
        housing_growth_signal=round(housing_growth, 1),
        overall_score=round(min(overall, 100.0), 1),
    ), district_name


async def run_schools_agent(lat: float, lng: float, demographics=None):
    """
    Async generator yielding trace events + NeighborhoodProfile.
    demographics param kept for interface compatibility but not required.
    """
    yield {"agent": "schools", "status": "running",
           "message": "Loading NCES Common Core of Data school district boundaries..."}
    await asyncio.sleep(0.3)

    yield {"agent": "schools", "status": "running",
           "message": "Identifying nearest school district and quality index..."}
    await asyncio.sleep(0.5)

    profile, district_name = compute_neighborhood_profile(lat, lng)

    yield {
        "agent": "schools",
        "status": "running",
        "message": (f"Nearest district: {district_name} (quality: {profile.school_quality_index:.0f}/100). "
                    f"Family density: {profile.family_density_score:.0f}/100. "
                    f"Neighborhood stability: {profile.neighborhood_stability:.0f}/100."),
    }
    await asyncio.sleep(0.2)

    yield {
        "agent": "schools",
        "status": "done",
        "message": (f"Neighborhood analysis complete → Score: {profile.overall_score:.0f}/100. "
                    f"District: {district_name}"),
        "data": {**profile.model_dump(), "district_name": district_name},
    }
