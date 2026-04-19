"""
Orchestrator Agent v3 — lean 7-agent pipeline (simulation is now on-demand).

Phase 0 (fast-path, parallel with Phase 1): reverse-geocode + brand resolver.
Phase 1: Demographics + Competitors + Schools + Hotspot (parallel)
Phase 2: BrandFit + Amenity (parallel)
Phase 3: Scoring Engine

Simulation (the 26s OpenAI agent) is deliberately excluded — it runs only
when the user hits "Run AI Simulation" on the dashboard, via /api/simulate.
"""
import asyncio
import hashlib
import time
from typing import AsyncGenerator, Optional

from geopy.geocoders import Nominatim

from app.models.schemas import (
    AnalysisResult, DemographicsProfile, CompetitorProfile, CompetitorStore,
    NeighborhoodProfile, BrandFitProfile,
    HotspotProfile, AmenityProfile, BrandDNA, RetailerProfile, RetailSignal,
    StoreSizeEnum,
)
from app.agents.demographics import run_demographics_agent
from app.agents.competitors import run_competitor_agent
from app.agents.schools import run_schools_agent
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


async def _drain_generator(gen, capture_key: str, results: dict, events: list) -> None:
    """Consume an async generator, forwarding events and capturing the final 'done' payload."""
    async for event in gen:
        events.append(event)
        if event.get("status") == "done" and event.get("data") is not None:
            results[capture_key] = event["data"]


# ── Main Orchestrator ─────────────────────────────────────────────────────────

async def run_orchestrator(
    lat: float,
    lng: float,
    retailer: RetailerProfile,
    radius_miles: float = 10.0,
    region_city: str = "Minneapolis, MN",
) -> AsyncGenerator[dict, None]:
    """
    Lean analysis pipeline (no simulation). Yields SSE trace events;
    final event (status=complete) contains AnalysisResult.
    """
    t0 = time.perf_counter()
    display_name = retailer.display_name()

    yield {"agent": "orchestrator", "status": "running",
           "message": f"🚀 RetailIQ analysis — {display_name} @ ({lat:.4f}, {lng:.4f})"}

    # ── Warm-cache fast path (Supabase KV, keyed on lat/lng/retailer/radius) ──
    ck = _cache_key(lat, lng, retailer, radius_miles)
    try:
        from app.services.supabase_service import cache_get
        cached = cache_get(f"analysis:{ck}")
        if cached and isinstance(cached, dict):
            try:
                cached_result = AnalysisResult(**cached)
                yield {
                    "agent": "orchestrator", "status": "running",
                    "message": f"⚡ Cache hit — reusing prior analysis (key {ck})",
                }
                yield {
                    "agent": "orchestrator", "status": "complete",
                    "message": (
                        f"✅ Cached result — {cached_result.score.rank_label} "
                        f"({cached_result.score.total_score:.0f}/100) · "
                        f"{cached_result.address_label} · {display_name}"
                    ),
                    "data": cached_result.model_dump(),
                    "cached": True,
                }
                return
            except Exception as e:
                print(f"[Supabase] Warm cache rehydrate failed ({e}) — recomputing")
    except Exception as e:
        print(f"[Supabase] cache_get failed ({e}) — continuing")

    # ── PHASE 0 (parallel): geocode + brand resolver ─────────────────────
    geocode_task = asyncio.get_event_loop().run_in_executor(None, _reverse_geocode, lat, lng)

    brand_events: list = []
    brand_results: dict = {}
    resolver_task = asyncio.create_task(
        _drain_generator(run_brand_resolver_agent(retailer), "brand_resolver", brand_results, brand_events)
    )

    # Await brand_resolver first (Phase 1 needs display_name / category), flush its events.
    await resolver_task
    for ev in brand_events:
        yield ev

    brand_dna_data = brand_results.get("brand_resolver") or {}
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

    store_size = StoreSizeEnum.BIG_BOX
    if brand_dna.footprint_sqft < 5_000:
        store_size = StoreSizeEnum.SMALL
    elif brand_dna.footprint_sqft < 25_000:
        store_size = StoreSizeEnum.MEDIUM
    elif brand_dna.footprint_sqft < 80_000:
        store_size = StoreSizeEnum.LARGE

    primary_cat = brand_dna.primary_categories[0] if brand_dna.primary_categories else "retail"

    # ── PHASE 1 (parallel): Demo + Competitors + Schools + Hotspot ───────
    yield {"agent": "orchestrator", "status": "running",
           "message": "⚡ Phase 1: Demographics + Competitors + Schools + Hotspot (parallel)"}

    p1_events: list = []
    p1_results: dict = {}
    p1_tasks = [
        asyncio.create_task(_drain_generator(
            run_demographics_agent(lat, lng, radius_miles), "demographics", p1_results, p1_events)),
        asyncio.create_task(_drain_generator(
            run_competitor_agent(lat, lng, radius_miles, brand_dna.display_name), "competitor", p1_results, p1_events)),
        asyncio.create_task(_drain_generator(
            run_schools_agent(lat, lng), "schools", p1_results, p1_events)),
        asyncio.create_task(_drain_generator(
            run_hotspot_agent(lat, lng, region_city, primary_cat), "hotspot", p1_results, p1_events)),
    ]
    await asyncio.gather(*p1_tasks, return_exceptions=True)
    for ev in p1_events:
        yield ev

    demographics = _rebuild_demographics(p1_results.get("demographics") or {}, lat, lng, radius_miles)
    competitors = _rebuild_competitors(p1_results.get("competitor") or {}, lat, lng, radius_miles, brand_dna.display_name)
    neighborhood = _rebuild_neighborhood(p1_results.get("schools") or {})
    hotspot = _rebuild_hotspot(p1_results.get("hotspot") or {})

    # Geocode should have finished by now — grab the resolved address.
    try:
        address_label = await asyncio.wait_for(geocode_task, timeout=1.0)
    except Exception:
        address_label = f"{lat:.4f}°N, {abs(lng):.4f}°W"

    # ── PHASE 2 (parallel): BrandFit + Amenity ───────────────────────────
    yield {"agent": "orchestrator", "status": "running",
           "message": "🎯 Phase 2: Brand Fit + Amenity (parallel)"}

    p2_events: list = []
    p2_results: dict = {}
    p2_tasks = [
        asyncio.create_task(_drain_generator(
            run_brand_fit_agent(lat, lng, brand_dna.display_name, demographics, competitors, brand_dna),
            "brand_fit", p2_results, p2_events)),
        asyncio.create_task(_drain_generator(
            run_amenity_agent(lat, lng, store_size, region_city), "amenity", p2_results, p2_events)),
    ]
    await asyncio.gather(*p2_tasks, return_exceptions=True)
    for ev in p2_events:
        yield ev

    try:
        brand_fit = BrandFitProfile(**(p2_results.get("brand_fit") or {}))
    except Exception:
        brand_fit = BrandFitProfile(
            brand=display_name, fit_score=65.0,
            recommended_format="Standard format",
            income_alignment=65.0, density_alignment=70.0,
            reasoning="Moderate brand fit detected.",
        )

    try:
        amenity = AmenityProfile(**(p2_results.get("amenity") or {}))
    except Exception:
        amenity = None

    # ── PHASE 3: Scoring ──────────────────────────────────────────────────
    yield {"agent": "orchestrator", "status": "running",
           "message": "🧮 Phase 3: composite scoring"}

    score = compute_location_score(
        lat, lng, demographics, competitors, neighborhood,
        brand_fit, hotspot, amenity,
    )

    yield {"agent": "orchestrator", "status": "running",
           "message": f"📈 Scoring complete → {score.total_score:.0f}/100 ({score.rank_label}) · "
                      f"total {time.perf_counter() - t0:.1f}s"}

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
        simulation=None,  # on-demand via /api/simulate
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

    # ── Persist (non-blocking) ────────────────────────────────────────────
    try:
        from app.services.supabase_service import save_analysis, cache_set
        score_dict = score.model_dump()

        # Write the full AnalysisResult into the KV cache for warm-path reuse
        try:
            loop_kv = asyncio.get_event_loop()
            loop_kv.run_in_executor(None, cache_set, f"analysis:{ck}", result.model_dump())
        except Exception as e:
            print(f"[Supabase] cache_set failed: {e}")
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
                "access":       score_dict.get("accessibility_score"),
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
            "result_payload": result.model_dump(),  # for warm-cache hits
            "cache_key": ck,
        }
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, save_analysis, save_payload)
    except Exception as e:
        print(f"[Supabase] Background save failed: {e}")


# ── Rebuild helpers (keep orchestrator body readable) ────────────────────────

def _rebuild_demographics(data: dict, lat: float, lng: float, radius_miles: float) -> DemographicsProfile:
    try:
        if data:
            return DemographicsProfile(**data)
    except Exception as e:
        print(f"[Orchestrator] DemographicsProfile rebuild failed: {e}")
    try:
        from app.services.census_service import get_demographics_for_location
        return get_demographics_for_location(lat, lng, radius_miles)
    except Exception as e:
        print(f"[Orchestrator] Census fallback failed: {e}")
        from app.services.census_service import _synthetic_demographics
        return _synthetic_demographics(lat, lng, radius_miles)


def _rebuild_competitors(data: dict, lat: float, lng: float, radius_miles: float, brand_name: str) -> CompetitorProfile:
    try:
        if data:
            stores = [CompetitorStore(**s) for s in data.get("stores", [])]
            return CompetitorProfile(**{**data, "stores": stores})
    except Exception as e:
        print(f"[Orchestrator] CompetitorProfile rebuild failed: {e}")
    try:
        from app.services.osm_service import get_competitor_profile
        return get_competitor_profile(lat, lng, radius_miles, brand_name)
    except Exception as e:
        print(f"[Orchestrator] OSM fallback failed: {e}")
        return CompetitorProfile(
            stores=[], total_count=0, big_box_count=0, same_category_count=0,
            saturation_score=50.0, demand_signal_score=60.0,
            competition_score=60.0, underserved=True,
        )


def _rebuild_neighborhood(data: dict) -> NeighborhoodProfile:
    try:
        fields = {k: v for k, v in (data or {}).items() if k in NeighborhoodProfile.model_fields}
        return NeighborhoodProfile(**fields)
    except Exception:
        return NeighborhoodProfile(
            school_quality_index=65.0, family_density_score=60.0,
            neighborhood_stability=65.0, housing_growth_signal=70.0, overall_score=65.0,
        )


def _rebuild_hotspot(data: dict) -> Optional[HotspotProfile]:
    if not data:
        return None
    try:
        return HotspotProfile(
            **{k: v for k, v in data.items() if k != "signals"},
            signals=[RetailSignal(**s) for s in data.get("signals", [])],
        )
    except Exception:
        return None


def _cache_key(lat: float, lng: float, retailer: RetailerProfile, radius_miles: float) -> str:
    payload = f"{lat:.4f}|{lng:.4f}|{radius_miles:.1f}|{retailer.display_name().lower()}"
    return hashlib.sha1(payload.encode()).hexdigest()[:16]
