"""
API Routes for RetailIQ v2
Supports universal RetailerProfile input (brand_name OR custom store spec).
"""
import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.models.schemas import (
    AnalyzeRequest,
    CandidateSite,
    RetailerProfile,
    StoreSizeEnum,
    ProductCategory,
    PricePositioning,
    DemographicsProfile,
    CompetitorProfile,
    CompetitorStore,
    SimulationResult,
)
from app.agents.orchestrator import run_orchestrator
from app.agents.simulation import run_simulation_agent
from app.services.osm_service import fetch_competitors

router = APIRouter()

# ── Known brand definitions for frontend autocomplete ────────────────────────
KNOWN_BRANDS_LIST = [
    {"name": "Walmart", "category": "general_merchandise", "size": "big_box", "positioning": "budget"},
    {"name": "Target", "category": "general_merchandise", "size": "big_box", "positioning": "mid_range"},
    {"name": "Costco", "category": "grocery", "size": "big_box", "positioning": "mid_range"},
    {"name": "Aldi", "category": "grocery", "size": "medium", "positioning": "budget"},
    {"name": "Trader Joe's", "category": "grocery", "size": "medium", "positioning": "mid_range"},
    {"name": "Whole Foods", "category": "grocery", "size": "large", "positioning": "premium"},
    {"name": "Sprouts", "category": "grocery", "size": "large", "positioning": "mid_range"},
    {"name": "Kroger", "category": "grocery", "size": "large", "positioning": "mid_range"},
    {"name": "H-Mart", "category": "grocery", "size": "large", "positioning": "mid_range"},
    {"name": "Nordstrom Rack", "category": "apparel", "size": "large", "positioning": "mid_range"},
    {"name": "Dollar General", "category": "general_merchandise", "size": "small", "positioning": "budget"},
    {"name": "Home Depot", "category": "hardware", "size": "big_box", "positioning": "mid_range"},
    {"name": "Lowe's", "category": "hardware", "size": "big_box", "positioning": "mid_range"},
    {"name": "TJ Maxx", "category": "apparel", "size": "large", "positioning": "budget"},
    {"name": "Burlington", "category": "apparel", "size": "large", "positioning": "budget"},
    {"name": "Five Below", "category": "general_merchandise", "size": "medium", "positioning": "budget"},
    {"name": "BJ's Wholesale", "category": "general_merchandise", "size": "big_box", "positioning": "mid_range"},
    {"name": "Sam's Club", "category": "general_merchandise", "size": "big_box", "positioning": "mid_range"},
    {"name": "Lidl", "category": "grocery", "size": "medium", "positioning": "budget"},
    {"name": "Fresh Thyme", "category": "grocery", "size": "medium", "positioning": "mid_range"},
]

# ── Candidate Sites ───────────────────────────────────────────────────────────
CANDIDATE_SITES = [
    CandidateSite(id="mpls1", name="Uptown Hennepin Corridor", lat=44.9479, lng=-93.2988,
                  description="Dense urban village, high foot traffic, strong millennial and young-family demo", acreage=8.5, zoning_type="C-3A Community Activity Center"),
    CandidateSite(id="mpls2", name="Northeast Minneapolis Arts District", lat=44.9968, lng=-93.2535,
                  description="Rapidly gentrifying creative district, rising incomes, underserved grocery", acreage=10.0, zoning_type="C-2 Neighborhood Commercial"),
    CandidateSite(id="mpls3", name="Bloomington Penn Avenue Node", lat=44.8408, lng=-93.3376,
                  description="South-ring suburb corridor, family-dense, strong school district signal", acreage=20.0, zoning_type="C-2 General Commercial"),
    CandidateSite(id="mpls4", name="Eden Prairie Town Center Area", lat=44.8547, lng=-93.4708,
                  description="Affluent southwest suburb, premium-income households, limited competition", acreage=18.0, zoning_type="C-REG Regional Commercial"),
    CandidateSite(id="mpls5", name="Richfield 66th Street Corridor", lat=44.8763, lng=-93.2839,
                  description="Established inner-ring suburb, budget-friendly demographics, high AADT", acreage=14.0, zoning_type="C-2 General Commercial"),
    CandidateSite(id="mpls6", name="Coon Rapids Northdale Boulevard", lat=45.1197, lng=-93.3111,
                  description="Growing northern suburb, new housing developments, underserved big-box", acreage=25.0, zoning_type="B-4 Community Business"),
    CandidateSite(id="mpls7", name="Burnsville Heart of the City", lat=44.7677, lng=-93.2777,
                  description="South metro redevelopment zone, mixed-income base, transit-adjacent", acreage=16.0, zoning_type="PUD Planned Unit Development"),
    CandidateSite(id="mpls8", name="Plymouth Hwy 55 Retail Node", lat=45.0105, lng=-93.4555,
                  description="High-growth western suburb, young families, strong household incomes", acreage=22.0, zoning_type="C-2 General Commercial"),
    CandidateSite(id="mpls9", name="St. Louis Park Excelsior Blvd", lat=44.9275, lng=-93.3594,
                  description="Inner-ring premium corridor, high walkability, educated affluent demo", acreage=11.0, zoning_type="MX Mixed-Use"),
    CandidateSite(id="mpls10", name="Brooklyn Center Shingle Creek Crossing", lat=45.0720, lng=-93.3317,
                  description="Redeveloping north suburb, low competition, value-oriented consumer base", acreage=30.0, zoning_type="C-2 Commerce"),
]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/candidates")
async def get_candidates():
    """Return pre-defined Minneapolis metro candidate sites."""
    return {"candidates": [s.model_dump() for s in CANDIDATE_SITES]}


@router.get("/brands")
async def get_known_brands():
    """Return list of known brands for frontend autocomplete."""
    return {
        "brands": KNOWN_BRANDS_LIST,
        "categories": [c.value for c in ProductCategory],
        "sizes": [s.value for s in StoreSizeEnum],
        "positioning": [p.value for p in PricePositioning],
    }


@router.get("/competitors")
async def get_competitors(lat: float = 44.9778, lng: float = -93.2650, radius: float = 25.0):
    """Return competitor store locations for map overlay."""
    try:
        stores = fetch_competitors(lat, lng, radius)
        return {"stores": stores, "count": len(stores)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/stream")
async def analyze_stream(request: AnalyzeRequest):
    """
    SSE endpoint: streams the full 8-agent analysis pipeline in real time.
    Each event is a JSON object on a 'data:' line. Final event is [DONE].
    """
    async def event_generator():
        try:
            async for event in run_orchestrator(
                lat=request.lat,
                lng=request.lng,
                retailer=request.retailer,
                radius_miles=request.radius_miles,
                region_city=request.region_city,
            ):
                yield f"data: {json.dumps(event)}\n\n"
                await asyncio.sleep(0)
        except Exception as e:
            yield f"data: {json.dumps({'agent': 'orchestrator', 'status': 'error', 'message': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/analyze")
async def analyze(request: AnalyzeRequest):
    """
    Blocking endpoint: runs full analysis pipeline and returns when complete.
    Use /analyze/stream for real-time agent trace.
    """
    final_result = None
    async for event in run_orchestrator(
        lat=request.lat,
        lng=request.lng,
        retailer=request.retailer,
        radius_miles=request.radius_miles,
        region_city=request.region_city,
    ):
        if event.get("status") == "complete" and event.get("data"):
            final_result = event["data"]

    if not final_result:
        raise HTTPException(status_code=500, detail="Analysis failed — no result produced")

    return final_result


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "RetailIQ API",
        "version": "2.1.0",
        "features": [
            "brand_resolver", "hotspot_agent", "amenity_agent",
            "universal_retailer", "history",
            "on_demand_simulation", "kmeans_scout",
        ],
    }


# ── On-demand Simulation ──────────────────────────────────────────────────────

class SimulateRequest(BaseModel):
    lat: float = Field(..., ge=24.0, le=50.0)
    lng: float = Field(..., ge=-125.0, le=-65.0)
    retailer: RetailerProfile
    demographics: DemographicsProfile
    competitors: CompetitorProfile


@router.post("/simulate", response_model=SimulationResult)
async def simulate(body: SimulateRequest):
    """
    Run just the market simulation agent against an already-analyzed site.
    Called on-demand when the user clicks "Run AI Simulation" in the dashboard,
    so /api/analyze stays fast.
    """
    brand = body.retailer.display_name()
    final: SimulationResult | None = None
    async for event in run_simulation_agent(body.lat, body.lng, body.demographics, body.competitors, brand):
        if event.get("status") == "done" and event.get("data"):
            try:
                final = SimulationResult(**event["data"])
            except Exception:
                final = None
    if final is None:
        raise HTTPException(status_code=500, detail="Simulation failed — no result produced")
    return final


@router.get("/history")
async def get_history(limit: int = 20):
    """Return recent analyses from Supabase for the history panel."""
    from app.services.supabase_service import get_recent_analyses
    analyses = get_recent_analyses(limit=limit)
    return {"analyses": analyses, "count": len(analyses)}
