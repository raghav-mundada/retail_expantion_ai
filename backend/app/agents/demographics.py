"""
Demographics Agent
Wraps census_service with an agent interface that yields trace events.
Note: Python async generators cannot use 'return value' — results are embedded in done event data.
"""
import asyncio
from app.services.census_service import get_demographics_for_location
from app.models.schemas import DemographicsProfile


async def run_demographics_agent(lat: float, lng: float, radius_miles: float = 10.0):  # noqa: E501
    """
    Async generator that yields trace events and ultimately yields DemographicsProfile.
    """
    yield {"agent": "demographics", "status": "running", "message": "Connecting to U.S. Census ACS API..."}
    await asyncio.sleep(0.3)

    yield {"agent": "demographics", "status": "running",
           "message": f"Fetching tract-level ACS 5-Year data for Maricopa County, AZ (state:04 county:013)"}
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
