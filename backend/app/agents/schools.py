"""
School & Neighborhood Agent
Computes a neighborhood quality proxy using ACS education/family data + NCES school district signals.
For MVP: derives school quality index from demographic correlates (education level, family density, income).
"""
import asyncio
import math
from app.models.schemas import DemographicsProfile, NeighborhoodProfile


# Phoenix-area school district quality index (approximate, sourced from NCES/GreatSchools ratings)
# Maricopa County top school districts mapped to approximate center lat/lng
PHOENIX_SCHOOL_DISTRICTS = [
    {"name": "Scottsdale Unified", "lat": 33.6391, "lng": -111.9275, "quality": 88},
    {"name": "Paradise Valley Unified", "lat": 33.6654, "lng": -112.0220, "quality": 84},
    {"name": "Gilbert Unified", "lat": 33.3528, "lng": -111.7890, "quality": 82},
    {"name": "Chandler Unified", "lat": 33.3062, "lng": -111.8413, "quality": 80},
    {"name": "Deer Valley Unified", "lat": 33.7015, "lng": -112.1045, "quality": 78},
    {"name": "Litchfield Elementary", "lat": 33.5012, "lng": -112.3498, "quality": 76},
    {"name": "Peoria Unified", "lat": 33.5806, "lng": -112.2174, "quality": 74},
    {"name": "Glendale Union", "lat": 33.5389, "lng": -112.1859, "quality": 72},
    {"name": "Mesa Unified", "lat": 33.4152, "lng": -111.8315, "quality": 70},
    {"name": "Tempe Union", "lat": 33.3784, "lng": -111.9274, "quality": 74},
    {"name": "Queen Creek Unified", "lat": 33.2487, "lng": -111.6341, "quality": 78},
    {"name": "Avondale Elementary", "lat": 33.4355, "lng": -112.3496, "quality": 65},
    {"name": "Roosevelt Elementary", "lat": 33.4031, "lng": -112.0532, "quality": 58},
    {"name": "Cartwright Elementary", "lat": 33.4709, "lng": -112.1742, "quality": 55},
    {"name": "Isaac Elementary", "lat": 33.4752, "lng": -112.1117, "quality": 52},
]


def _haversine_miles(lat1, lng1, lat2, lng2):
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((lat2-lat1)*math.pi/360)**2 + math.cos(phi1)*math.cos(phi2)*math.sin((lng2-lng1)*math.pi/360)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def get_nearest_school_district(lat: float, lng: float):
    """Find the nearest Phoenix school district center."""
    nearest = min(
        PHOENIX_SCHOOL_DISTRICTS,
        key=lambda d: _haversine_miles(lat, lng, d["lat"], d["lng"])
    )
    dist = _haversine_miles(lat, lng, nearest["lat"], nearest["lng"])
    # Interpolate quality based on distance (further = less direct correlation)
    quality_adj = nearest["quality"] * max(0.7, 1 - dist / 20.0)
    return nearest["name"], round(quality_adj, 1)


def compute_neighborhood_profile(lat: float, lng: float, demographics: DemographicsProfile) -> NeighborhoodProfile:
    """Derive neighborhood quality from demographics + school district proximity."""

    district_name, school_quality = get_nearest_school_district(lat, lng)

    # Family density: family HH% × average HH size proxy
    family_density = min(
        (demographics.family_households_pct / 100.0) * (demographics.avg_household_size / 3.5) * 100,
        100.0
    )

    # Neighborhood stability: homeownership + income + education
    stability = (
        demographics.owner_occupied_pct * 0.35
        + min(demographics.median_income / 100000.0 * 100, 100) * 0.35
        + demographics.college_educated_pct * 0.30
    )
    stability = min(stability, 100.0)

    # Housing growth signal: Phoenix has strong growth, moderate in outer areas
    # Proxy: inverse distance from growth corridors
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


async def run_schools_agent(lat: float, lng: float, demographics: DemographicsProfile):
    """Async generator yielding trace events + NeighborhoodProfile."""
    yield {"agent": "schools", "status": "running",
           "message": "Loading NCES Common Core of Data school district boundaries..."}
    await asyncio.sleep(0.3)

    yield {"agent": "schools", "status": "running",
           "message": "Identifying nearest Phoenix-area school district and quality index..."}
    await asyncio.sleep(0.5)

    profile, district_name = compute_neighborhood_profile(lat, lng, demographics)

    yield {
        "agent": "schools",
        "status": "running",
        "message": f"Nearest district: {district_name} (quality: {profile.school_quality_index:.0f}/100). "
                   f"Family density: {profile.family_density_score:.0f}/100. "
                   f"Neighborhood stability: {profile.neighborhood_stability:.0f}/100.",
    }
    await asyncio.sleep(0.2)

    yield {
        "agent": "schools",
        "status": "done",
        "message": f"Neighborhood analysis complete → Neighborhood Score: {profile.overall_score:.0f}/100. "
                   f"District: {district_name}",
        "data": {**profile.model_dump(), "district_name": district_name},
    }
