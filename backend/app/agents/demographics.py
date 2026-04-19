"""
Demographics Agent
Wraps census_service with an agent interface that yields trace events.

Uses TIGERweb to resolve census tracts by exact radius (main branch approach),
then pulls ACS 2023 5-Year estimates for those specific tracts.
Note: Python async generators cannot use 'return value' — results are embedded in done event data.
"""
import asyncio
from app.services.census_service import get_demographics_for_location
from app.models.schemas import DemographicsProfile


async def run_demographics_agent(lat: float, lng: float, radius_miles: float = 10.0):  # noqa: E501
    """
    Async generator that yields trace events and ultimately yields DemographicsProfile.
    Uses Census TIGERweb to find exact tracts within radius (generalized for any US city).
    """
    yield {"agent": "demographics", "status": "running", "message": "Connecting to U.S. Census ACS 2023 API..."}
    await asyncio.sleep(0.3)

    yield {"agent": "demographics", "status": "running",
           "message": f"Resolving census tracts within {radius_miles:.0f}-mile radius via TIGERweb spatial query..."}
    await asyncio.sleep(0.5)

    try:
        profile = await asyncio.get_event_loop().run_in_executor(
            None, get_demographics_for_location, lat, lng, radius_miles
        )
    except Exception as e:
        yield {"agent": "demographics", "status": "error", "message": f"Census API error: {e}"}
        return

    yield {
        "agent": "demographics",
        "status": "running",
        "message": f"Aggregating {radius_miles:.0f}-mile trade area: {profile.population:,} residents, "
                   f"${profile.median_income:,.0f} median income, {profile.family_households_pct:.0f}% family HHs",
    }
    await asyncio.sleep(0.2)

    yield {
        "agent": "demographics",
        "status": "done",
        "message": f"Demographics analysis complete → Demand Score: {profile.demand_score:.0f}/100",
        "data": profile.model_dump(),
    }
