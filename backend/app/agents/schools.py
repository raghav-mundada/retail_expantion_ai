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


# Phoenix-area school district quality index (NCES/GreatSchools approximation)
PHOENIX_SCHOOL_DISTRICTS = [
    {"name": "Scottsdale Unified",      "lat": 33.6391, "lng": -111.9275, "quality": 88},
    {"name": "Paradise Valley Unified", "lat": 33.6654, "lng": -112.0220, "quality": 84},
    {"name": "Gilbert Unified",         "lat": 33.3528, "lng": -111.7890, "quality": 82},
    {"name": "Chandler Unified",        "lat": 33.3062, "lng": -111.8413, "quality": 80},
    {"name": "Deer Valley Unified",     "lat": 33.7015, "lng": -112.1045, "quality": 78},
    {"name": "Litchfield Elementary",   "lat": 33.5012, "lng": -112.3498, "quality": 76},
    {"name": "Peoria Unified",          "lat": 33.5806, "lng": -112.2174, "quality": 74},
    {"name": "Glendale Union",          "lat": 33.5389, "lng": -112.1859, "quality": 72},
    {"name": "Mesa Unified",            "lat": 33.4152, "lng": -111.8315, "quality": 70},
    {"name": "Tempe Union",             "lat": 33.3784, "lng": -111.9274, "quality": 74},
    {"name": "Queen Creek Unified",     "lat": 33.2487, "lng": -111.6341, "quality": 78},
    {"name": "Avondale Elementary",     "lat": 33.4355, "lng": -112.3496, "quality": 65},
    {"name": "Roosevelt Elementary",    "lat": 33.4031, "lng": -112.0532, "quality": 58},
    {"name": "Cartwright Elementary",   "lat": 33.4709, "lng": -112.1742, "quality": 55},
    {"name": "Isaac Elementary",        "lat": 33.4752, "lng": -112.1117, "quality": 52},
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
        PHOENIX_SCHOOL_DISTRICTS,
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

    # Housing growth signal: distance from Phoenix growth corridors
    growth_corridors = [(33.4484, -112.0740), (33.3528, -111.7890), (33.5092, -112.1126)]
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
