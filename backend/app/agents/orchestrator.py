"""
Orchestrator Agent v2 — 8-Agent Pipeline

Phase 0: Brand Resolver (always runs first — resolves RetailerProfile → BrandDNA)
Phase 1: Demographics + Competitors + Schools + Hotspot (parallel interleaved)
Phase 2: Simulation + BrandFit + Amenity (parallel interleaved)
Phase 3: Scoring Engine

Yields SSE-compatible trace events throughout.
Results captured from 'done' event data payloads.
"""
import asyncio
from typing import AsyncGenerator, Optional

from geopy.geocoders import Nominatim

from app.models.schemas import (
    AnalysisResult, DemographicsProfile, CompetitorProfile, CompetitorStore,
    NeighborhoodProfile, SimulationResult, BrandFitProfile,
    HotspotProfile, AmenityProfile, BrandDNA, RetailerProfile, RetailSignal,
    StoreSizeEnum,
)
from app.agents.demographics import run_demographics_agent
from app.agents.competitors import run_competitor_agent
from app.agents.schools import run_schools_agent
from app.agents.simulation import run_simulation_agent
from app.agents.brand_fit import run_brand_fit_agent
from app.agents.brand_resolver import run_brand_resolver_agent
from app.agents.hotspot import run_hotspot_agent
from app.agents.amenity import run_amenity_agent
from app.services.scoring_engine import compute_location_score


# ── Helpers ──────────────────────────────────────────────────────────────────

def _reverse_geocode(lat: float, lng: float) -> str:
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


async def _interleave_agents(
    *generators,
    field_map: dict,  # {agent_name: dict_key} — maps agent name to results key
) -> tuple[list[dict], dict]:
    """
    Run multiple async generators concurrently by round-robin polling.
    Returns (all_events, results_dict).
    """
    iters = [(gen.__aiter__(), name) for gen, name in generators]
    done_set = set()
    results = {}
    all_events = []

    while len(done_set) < len(iters):
        for gen_iter, name in iters:
            if name in done_set:
                continue
            try:
                event = await gen_iter.__anext__()
                all_events.append(event)
                # Capture result from done event
                if event.get("status") == "done" and event.get("agent") == name:
                    key = field_map.get(name)
                    if key:
                        results[key] = event.get("data") or {}
            except StopAsyncIteration:
                done_set.add(name)

    return all_events, results


# ── Main Orchestrator ─────────────────────────────────────────────────────────

async def run_orchestrator(
    lat: float,
    lng: float,
    retailer: RetailerProfile,
    radius_miles: float = 10.0,
    region_city: str = "Phoenix, AZ",
) -> AsyncGenerator[dict, None]:
    """
    Full 8-agent analysis pipeline.
    Yields SSE trace events. Final event (status=complete) contains AnalysisResult.
    """
    display_name = retailer.display_name()

    yield {
        "agent": "orchestrator",
        "status": "running",
        "message": f"🚀 RetailIQ analysis initiated — {display_name} @ ({lat:.4f}, {lng:.4f})",
    }
    await asyncio.sleep(0.1)

    # Resolve address
    yield {"agent": "orchestrator", "status": "running", "message": "📍 Resolving site address..."}
    address_label = await asyncio.get_event_loop().run_in_executor(None, _reverse_geocode, lat, lng)
    yield {"agent": "orchestrator", "status": "running",
           "message": f"📍 Candidate site: {address_label}"}

    # ── PHASE 0: Brand Resolver ────────────────────────────────────────────
    yield {"agent": "orchestrator", "status": "running",
           "message": "🔍 Phase 0: Resolving retailer brand DNA..."}

    brand_dna_data: dict = {}
    async for event in run_brand_resolver_agent(retailer):
        yield event
        if event.get("status") == "done" and event.get("agent") == "brand_resolver":
            brand_dna_data = event.get("data") or {}

    try:
        brand_dna = BrandDNA(**brand_dna_data)
    except Exception:
        brand_dna = BrandDNA(
            display_name=display_name,
            ideal_income_low=45_000, ideal_income_high=100_000,
            ideal_population_min=40_000, footprint_sqft=60_000,
            primary_categories=["general_merchandise"],
            price_positioning="mid_range", store_format="general_retail",
            family_skew=True, college_edu_skew=False,
            known_brand=False, expansion_velocity="moderate",
            reasoning="Fallback baseline brand profile.",
        )

    # Determine store size for amenity agent
    store_size = StoreSizeEnum.BIG_BOX
    if brand_dna.footprint_sqft < 5_000:
        store_size = StoreSizeEnum.SMALL
    elif brand_dna.footprint_sqft < 25_000:
        store_size = StoreSizeEnum.MEDIUM
    elif brand_dna.footprint_sqft < 80_000:
        store_size = StoreSizeEnum.LARGE

    # Primary category for hotspot search
    primary_cat = brand_dna.primary_categories[0] if brand_dna.primary_categories else "retail"

    # ── PHASE 1: Parallel — Demo + Competitors + Schools + Hotspot ────────
    yield {"agent": "orchestrator", "status": "running",
           "message": "⚡ Phase 1: Launching Demographics, Competitors, Schools, and Hotspot in parallel..."}
    await asyncio.sleep(0.1)

    # Run the four Phase 1 agents, interleaving events manually
    demo_iter = run_demographics_agent(lat, lng, radius_miles).__aiter__()
    comp_iter = run_competitor_agent(lat, lng, radius_miles, brand_dna.display_name).__aiter__()
    school_iter = run_schools_agent(lat, lng).__aiter__()
    hotspot_iter = run_hotspot_agent(lat, lng, region_city, primary_cat).__aiter__()

    demo_result_data: dict = {}
    comp_result_data: dict = {}
    neighborhood_data: dict = {}
    hotspot_data: dict = {}

    agents_done = {"demographics": False, "competitor": False, "schools": False, "hotspot": False}
    iters = {
        "demographics": demo_iter,
        "competitor": comp_iter,
        "schools": school_iter,
        "hotspot": hotspot_iter,
    }

    while not all(agents_done.values()):
        for name, it in iters.items():
            if agents_done[name]:
                continue
            try:
                event = await it.__anext__()
                yield event
                if event.get("status") == "done" and event.get("agent") == name:
                    data = event.get("data") or {}
                    if name == "demographics":
                        demo_result_data = data
                    elif name == "competitor":
                        comp_result_data = data
                    elif name == "schools":
                        neighborhood_data = data
                    elif name == "hotspot":
                        hotspot_data = data
            except StopAsyncIteration:
                agents_done[name] = True

    # Reconstruct Phase 1 models — ALWAYS produce non-None objects
    demographics = None
    try:
        if demo_result_data:
            demographics = DemographicsProfile(**demo_result_data)
    except Exception as e:
        print(f"[Orchestrator] DemographicsProfile rebuild failed: {e}")

    if demographics is None:
        try:
            from app.services.census_service import get_demographics_for_location
            demographics = get_demographics_for_location(lat, lng, radius_miles)
        except Exception as e2:
            print(f"[Orchestrator] Census fallback failed: {e2}")
            from app.services.census_service import _synthetic_demographics
            demographics = _synthetic_demographics(lat, lng, radius_miles)

    competitors = None
    try:
        if comp_result_data:
            stores = [CompetitorStore(**s) for s in comp_result_data.get("stores", [])]
            competitors = CompetitorProfile(**{**comp_result_data, "stores": stores})
    except Exception as e:
        print(f"[Orchestrator] CompetitorProfile rebuild failed: {e}")

    if competitors is None:
        try:
            from app.services.osm_service import get_competitor_profile
            competitors = get_competitor_profile(lat, lng, radius_miles, brand_dna.display_name)
        except Exception as e2:
            print(f"[Orchestrator] OSM fallback failed: {e2}")
            competitors = CompetitorProfile(
                stores=[], total_count=0, big_box_count=0, same_category_count=0,
                saturation_score=50.0, demand_signal_score=60.0,
                competition_score=60.0, underserved=True,
            )

    try:
        neighborhood = NeighborhoodProfile(**{k: v for k, v in neighborhood_data.items() if k != "district_name"})
    except Exception:
        neighborhood = NeighborhoodProfile(
            school_quality_index=65.0, family_density_score=60.0,
            neighborhood_stability=65.0, housing_growth_signal=70.0, overall_score=65.0
        )

    try:
        hotspot = HotspotProfile(
            **{k: v for k, v in hotspot_data.items() if k != "signals"},
            signals=[RetailSignal(**s) for s in hotspot_data.get("signals", [])]
        )
    except Exception:
        hotspot = None

    yield {"agent": "orchestrator", "status": "running",
           "message": "📊 Phase 1 complete. Launching Simulation, Brand Fit, and Amenity analysis..."}

    # ── PHASE 2: Parallel — Simulation + BrandFit + Amenity ───────────────
    sim_iter2 = run_simulation_agent(lat, lng, demographics, competitors, brand_dna.display_name).__aiter__()
    bf_iter2 = run_brand_fit_agent(
        lat, lng, brand_dna.display_name, demographics, competitors, brand_dna
    ).__aiter__()
    amenity_iter2 = run_amenity_agent(lat, lng, store_size, region_city).__aiter__()

    sim_data: dict = {}
    brand_data: dict = {}
    amenity_data: dict = {}

    agents2_done = {"simulation": False, "brand_fit": False, "amenity": False}
    iters2 = {
        "simulation": sim_iter2,
        "brand_fit": bf_iter2,
        "amenity": amenity_iter2,
    }

    while not all(agents2_done.values()):
        for name, it in iters2.items():
            if agents2_done[name]:
                continue
            try:
                event = await it.__anext__()
                yield event
                if event.get("status") == "done" and event.get("agent") == name:
                    data = event.get("data") or {}
                    if name == "simulation":
                        sim_data = data
                    elif name == "brand_fit":
                        brand_data = data
                    elif name == "amenity":
                        amenity_data = data
            except StopAsyncIteration:
                agents2_done[name] = True

    # Reconstruct Phase 2 models
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
            brand=display_name, fit_score=65.0,
            recommended_format="Standard format",
            income_alignment=65.0, density_alignment=70.0,
            reasoning="Moderate brand fit detected.",
        )

    try:
        amenity = AmenityProfile(**amenity_data)
    except Exception:
        amenity = None

    # ── PHASE 3: Scoring ──────────────────────────────────────────────────
    yield {"agent": "orchestrator", "status": "running",
           "message": "🧮 Phase 3: Computing 8-dimension composite location score..."}
    await asyncio.sleep(0.2)

    score = compute_location_score(
        lat, lng, demographics, competitors, neighborhood,
        simulation, brand_fit, hotspot, amenity,
    )

    yield {"agent": "orchestrator", "status": "running",
           "message": f"📈 Scoring complete → {score.total_score:.0f}/100 ({score.rank_label})"}
    await asyncio.sleep(0.1)

    result = AnalysisResult(
        lat=lat, lng=lng,
        brand=display_name,
        address_label=address_label,
        retailer_profile=retailer,
        brand_dna=brand_dna,
        demographics=demographics,
        competitors=competitors,
        neighborhood=neighborhood,
        hotspot=hotspot,
        amenity=amenity,
        simulation=simulation,
        brand_fit=brand_fit,
        score=score,
        agent_trace=[],
    )

    yield {
        "agent": "orchestrator",
        "status": "complete",
        "message": (
            f"✅ Analysis complete — {score.rank_label} ({score.total_score:.0f}/100) "
            f"for {address_label} · {display_name}"
        ),
        "data": result.model_dump(),
    }

    # ── Persist to Supabase (async, non-blocking) ─────────────────────────
    try:
        from app.services.supabase_service import save_analysis
        score_dict = score.model_dump()
        save_payload = {
            "lat": lat,
            "lng": lng,
            "address": address_label,
            "retailer_name": display_name,
            "retailer_profile": retailer.model_dump(),
            "overall_score": score.total_score,
            "recommendation": score.rank_label,
            "score_breakdown": {
                "demand":       score_dict.get("demand_score"),
                "competition":  score_dict.get("competition_score"),
                "access":       score_dict.get("access_score"),
                "neighborhood": score_dict.get("neighborhood_score"),
                "brand_fit":    score_dict.get("brand_fit_score"),
                "risk":         score_dict.get("risk_score"),
                "hotspot":      score_dict.get("hotspot_score"),
                "amenity":      score_dict.get("amenity_score"),
            },
            "hotspot_score": score_dict.get("hotspot_score"),
            "competitor_count": competitors.total_count if competitors else 0,
            "population": demographics.population if demographics else None,
            "median_income": demographics.median_income if demographics else None,
            "region_city": region_city,
        }
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, save_analysis, save_payload)
    except Exception as e:
        print(f"[Supabase] Background save failed: {e}")
