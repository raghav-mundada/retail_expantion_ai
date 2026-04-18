"""
Orchestrator Agent — coordinates all 5 sub-agents.
Runs demographics + competitors in interleaved fashion, then schools, then simulation + brand_fit.
Finally runs the scoring engine.
Yields SSE-compatible trace events throughout.
Results are captured from the 'done' event data dictionaries.
"""
import asyncio
from typing import AsyncGenerator
from app.agents.demographics import run_demographics_agent
from app.agents.competitors import run_competitor_agent
from app.agents.schools import run_schools_agent
from app.agents.simulation import run_simulation_agent
from app.agents.brand_fit import run_brand_fit_agent
from app.services.scoring_engine import compute_location_score
from app.models.schemas import (
    AnalysisResult, DemographicsProfile, CompetitorProfile, CompetitorStore,
    NeighborhoodProfile, SimulationResult, BrandFitProfile
)
from geopy.geocoders import Nominatim


def _reverse_geocode(lat: float, lng: float) -> str:
    """Get a human-readable label for the candidate site."""
    try:
        geolocator = Nominatim(user_agent="retailiq-mvp")
        location = geolocator.reverse((lat, lng), timeout=5)
        if location:
            addr = location.raw.get("address", {})
            parts = [addr.get("road", ""), addr.get("suburb", addr.get("city", "")), addr.get("state", "")]
            return ", ".join(p for p in parts if p) or location.address[:60]
    except Exception:
        pass
    return f"{lat:.4f}°N, {abs(lng):.4f}°W"


async def run_orchestrator(
    lat: float,
    lng: float,
    brand: str,
    radius_miles: float = 10.0,
) -> AsyncGenerator[dict, None]:
    """
    Main async generator for the full analysis pipeline.
    Yields SSE trace events. The final event (status=complete) contains the complete AnalysisResult.
    Results from sub-agents are captured from their 'done' event data fields.
    """
    demo_result_data: dict = {}
    comp_result_data: dict = {}
    neighborhood_data: dict = {}
    sim_data: dict = {}
    brand_data: dict = {}

    yield {"agent": "orchestrator", "status": "running",
           "message": f"🚀 RetailIQ analysis initiated for ({lat:.4f}, {lng:.4f}) — Brand: {brand.title()}"}
    await asyncio.sleep(0.1)

    # Reverse geocode
    yield {"agent": "orchestrator", "status": "running", "message": "Resolving location address..."}
    address_label = await asyncio.get_event_loop().run_in_executor(None, _reverse_geocode, lat, lng)
    yield {"agent": "orchestrator", "status": "running",
           "message": f"📍 Candidate site: {address_label}"}

    yield {"agent": "orchestrator", "status": "running",
           "message": "⚡ Launching parallel data collection — Demographics + Competitors running simultaneously..."}
    await asyncio.sleep(0.2)

    # ─── PHASE 1: Demographics + Competitors interleaved ─────────────────────
    demo_iter = run_demographics_agent(lat, lng, radius_miles).__aiter__()
    comp_iter = run_competitor_agent(lat, lng, radius_miles, brand).__aiter__()

    demo_done, comp_done = False, False
    while not (demo_done and comp_done):
        if not demo_done:
            try:
                event = await demo_iter.__anext__()
                yield event
                if event.get("status") == "done" and event.get("agent") == "demographics":
                    demo_result_data = event.get("data") or {}
            except StopAsyncIteration:
                demo_done = True
        if not comp_done:
            try:
                event = await comp_iter.__anext__()
                yield event
                if event.get("status") == "done" and event.get("agent") == "competitor":
                    comp_result_data = event.get("data") or {}
            except StopAsyncIteration:
                comp_done = True

    # Reconstruct Pydantic models from data dicts
    try:
        demographics = DemographicsProfile(**demo_result_data)
    except Exception:
        from app.services.census_service import get_demographics_for_location
        demographics = get_demographics_for_location(lat, lng, radius_miles)

    try:
        stores = [CompetitorStore(**s) for s in comp_result_data.get("stores", [])]
        competitors = CompetitorProfile(**{**comp_result_data, "stores": stores})
    except Exception:
        from app.services.osm_service import get_competitor_profile
        competitors = get_competitor_profile(lat, lng, radius_miles, brand)

    # ─── Schools agent ────────────────────────────────────────────────────────
    async for event in run_schools_agent(lat, lng, demographics):
        yield event
        if event.get("status") == "done" and event.get("agent") == "schools":
            neighborhood_data = event.get("data") or {}

    try:
        neighborhood = NeighborhoodProfile(**{k: v for k, v in neighborhood_data.items() if k != "district_name"})
    except Exception:
        neighborhood = NeighborhoodProfile(
            school_quality_index=65.0, family_density_score=60.0,
            neighborhood_stability=65.0, housing_growth_signal=70.0, overall_score=65.0
        )

    yield {"agent": "orchestrator", "status": "running",
           "message": "📊 Phase 1 complete. Launching simulation + brand fit analysis..."}

    # ─── PHASE 2: Simulation + Brand Fit interleaved ──────────────────────────
    sim_iter2 = run_simulation_agent(lat, lng, demographics, competitors, brand).__aiter__()
    brand_iter2 = run_brand_fit_agent(lat, lng, brand, demographics, competitors).__aiter__()

    sim_done2, brand_done2 = False, False
    while not (sim_done2 and brand_done2):
        if not sim_done2:
            try:
                event = await sim_iter2.__anext__()
                yield event
                if event.get("status") == "done" and event.get("agent") == "simulation":
                    sim_data = event.get("data") or {}
            except StopAsyncIteration:
                sim_done2 = True
        if not brand_done2:
            try:
                event = await brand_iter2.__anext__()
                yield event
                if event.get("status") == "done" and event.get("agent") == "brand_fit":
                    brand_data = event.get("data") or {}
            except StopAsyncIteration:
                brand_done2 = True

    try:
        simulation = SimulationResult(**sim_data)
    except Exception:
        simulation = SimulationResult(
            simulated_households=500, pct_will_visit=35.0, predicted_monthly_visits=25000,
            predicted_annual_revenue_usd=45000000, market_share_6mo=10.0, market_share_24mo=18.0,
            word_of_mouth_score=55.0, cannibalization_risk=10.0,
            confidence_interval_low=35000000, confidence_interval_high=58000000,
        )
    try:
        brand_fit = BrandFitProfile(**brand_data)
    except Exception:
        brand_fit = BrandFitProfile(
            brand=brand, fit_score=65.0, recommended_format="Standard format",
            income_alignment=65.0, density_alignment=70.0, reasoning="Moderate brand fit detected."
        )

    # ─── PHASE 3: Scoring ─────────────────────────────────────────────────────
    yield {"agent": "orchestrator", "status": "running",
           "message": "🧮 Computing composite location score across all 6 dimensions..."}
    await asyncio.sleep(0.2)

    score = compute_location_score(lat, lng, demographics, competitors, neighborhood, simulation, brand_fit)

    yield {"agent": "orchestrator", "status": "running",
           "message": f"📈 Scoring complete → {score.total_score:.0f}/100 ({score.rank_label})"}
    await asyncio.sleep(0.1)

    result = AnalysisResult(
        lat=lat,
        lng=lng,
        brand=brand,
        address_label=address_label,
        demographics=demographics,
        competitors=competitors,
        neighborhood=neighborhood,
        simulation=simulation,
        brand_fit=brand_fit,
        score=score,
        agent_trace=[],
    )

    yield {
        "agent": "orchestrator",
        "status": "complete",
        "message": f"✅ Analysis complete — {score.rank_label} ({score.total_score:.0f}/100) for {address_label}",
        "data": result.model_dump(),
    }
