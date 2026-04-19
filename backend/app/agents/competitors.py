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
           "message": f"Querying OSM Overpass for retail competitors within {radius_miles:.0f} miles..."}

    try:
        profile = await asyncio.get_event_loop().run_in_executor(
            None, get_competitor_profile, lat, lng, radius_miles, brand
        )
    except Exception as e:
        yield {"agent": "competitor", "status": "error", "message": f"OSM query error: {e}"}
        return

    saturation_label = "LOW" if profile.saturation_score < 40 else ("MODERATE" if profile.saturation_score < 70 else "HIGH")
    underserved_msg = " · UNDERSERVED" if profile.underserved else ""
    yield {
        "agent": "competitor",
        "status": "done",
        "message": (f"Competitor analysis done → {profile.total_count} stores "
                    f"({profile.big_box_count} big-box) · saturation {saturation_label} · "
                    f"Competition {profile.competition_score:.0f}/100{underserved_msg}"),
        "data": {
            **profile.model_dump(),
            "stores": [s.model_dump() for s in profile.stores[:30]],
        },
    }
