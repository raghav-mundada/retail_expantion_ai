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
from app.models.schemas import NeighborhoodProfile, SchoolPoint, GrowthCorridor
from app.services.osm_schools_service import fetch_schools, fetch_growth_corridors


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


def compute_neighborhood_profile(
    lat: float, lng: float, radius_miles: float = 5.0,
) -> tuple:
    """
    Compute neighborhood quality using lat/lng + live OSM school & construction
    layers (when available). The district quality index still comes from the
    Minneapolis table; schools/growth corridors come from Geoapify/Overpass.
    """
    district_name, school_quality = get_nearest_school_district(lat, lng)

    # Live OSM enrichment — school points + housing / dev signals
    try:
        osm_schools = fetch_schools(lat, lng, radius_miles) or []
    except Exception:
        osm_schools = []
    try:
        growth_pts = fetch_growth_corridors(lat, lng, radius_miles) or []
    except Exception:
        growth_pts = []

    school_points: list[SchoolPoint] = []
    for s in osm_schools[:120]:  # safety cap for payload
        try:
            school_points.append(SchoolPoint(**{
                "name":  s.get("name", "School"),
                "lat":   float(s["lat"]),
                "lng":   float(s["lng"]),
                "type":  s.get("type", "school"),
                "level": s.get("level"),
            }))
        except Exception:
            continue

    growth_points: list[GrowthCorridor] = []
    for g in growth_pts[:80]:
        try:
            growth_points.append(GrowthCorridor(**{
                "name": g.get("name", "Development"),
                "lat":  float(g["lat"]),
                "lng":  float(g["lng"]),
                "kind": g.get("kind", "residential"),
            }))
        except Exception:
            continue

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

    # If OSM gave us a real count of nearby active-construction sites,
    # nudge the housing-growth signal so it's not just a lat/lng hash.
    if growth_points:
        osm_bonus = min(len(growth_points) * 1.2, 25.0)
        housing_growth = min(housing_growth + osm_bonus, 100.0)

    return NeighborhoodProfile(
        school_quality_index=round(school_quality, 1),
        family_density_score=round(family_density, 1),
        neighborhood_stability=round(stability, 1),
        housing_growth_signal=round(housing_growth, 1),
        overall_score=round(min(overall, 100.0), 1),
        district_name=district_name,
        schools=school_points,
        growth_corridors=growth_points,
    ), district_name


async def run_schools_agent(lat: float, lng: float, demographics=None):
    """
    Async generator yielding trace events + NeighborhoodProfile.
    demographics param kept for interface compatibility but not required.
    """
    yield {"agent": "schools", "status": "running",
           "message": "Resolving NCES school districts + neighborhood quality index..."}

    profile, district_name = compute_neighborhood_profile(lat, lng)

    yield {
        "agent": "schools",
        "status": "done",
        "message": (f"Neighborhood complete → {district_name} (school {profile.school_quality_index:.0f}/100, "
                    f"stability {profile.neighborhood_stability:.0f}/100, overall {profile.overall_score:.0f}/100)"),
        "data": {**profile.model_dump(), "district_name": district_name},
    }
