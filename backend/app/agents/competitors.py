"""
Competitor Analysis Agent
Queries OSM for competitor store locations and computes saturation/opportunity scores.
"""
import asyncio
from app.services.osm_service import get_competitor_profile
from app.models.schemas import CompetitorProfile


async def run_competitor_agent(lat: float, lng: float, radius_miles: float = 10.0, brand: str = "walmart"):
    """Async generator yielding trace events + CompetitorProfile."""
    yield {"agent": "competitor", "status": "running",
           "message": "Querying OpenStreetMap Overpass API for nearby retail competitors..."}
    await asyncio.sleep(0.4)

    yield {"agent": "competitor", "status": "running",
           "message": f"Scanning {radius_miles:.0f}-mile radius for Walmart, Target, Costco, Kroger/Fry's, "
                       "Aldi, Sam's Club, Safeway, Sprouts, Trader Joe's..."}
    await asyncio.sleep(0.8)

    try:
        profile = await asyncio.get_event_loop().run_in_executor(
            None, get_competitor_profile, lat, lng, radius_miles, brand
        )
    except Exception as e:
        yield {"agent": "competitor", "status": "error", "message": f"OSM query error: {e}"}
        return

    saturation_label = "LOW" if profile.saturation_score < 40 else ("MODERATE" if profile.saturation_score < 70 else "HIGH")
    yield {
        "agent": "competitor",
        "status": "running",
        "message": f"Found {profile.total_count} competitor stores ({profile.big_box_count} big-box). "
                   f"Market saturation: {saturation_label} ({profile.saturation_score:.0f}/100). "
                   f"Demand signal: {profile.demand_signal_score:.0f}/100.",
    }
    await asyncio.sleep(0.3)

    underserved_msg = " ⚡ Area appears UNDERSERVED — no dominant big-box within 5 miles." if profile.underserved else ""
    yield {
        "agent": "competitor",
        "status": "done",
        "message": f"Competitor analysis complete → Competition Score: {profile.competition_score:.0f}/100.{underserved_msg}",
        "data": {
            **profile.model_dump(),
            "stores": [s.model_dump() for s in profile.stores[:10]]
        },
    }
