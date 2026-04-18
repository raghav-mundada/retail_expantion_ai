"""
API Routes for RetailIQ v2
Supports universal RetailerProfile input (brand_name OR custom store spec).
"""
import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schemas import (
    AnalyzeRequest, CandidateSite, RetailerProfile,
    StoreSizeEnum, ProductCategory, PricePositioning,
)
from app.agents.orchestrator import run_orchestrator
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
    CandidateSite(id="ph1", name="Gilbert Gateway Towne Center Area", lat=33.34, lng=-111.76,
                  description="High-growth East Valley corridor, family-dense, strong school district", acreage=18.5, zoning_type="C-2 Commercial"),
    CandidateSite(id="ph2", name="Peoria 101 Corridor", lat=33.5806, lng=-112.23,
                  description="Growing suburban northwest, new housing developments nearby", acreage=22.0, zoning_type="C-3 General Commercial"),
    CandidateSite(id="ph3", name="Queen Creek Marketplace Area", lat=33.2487, lng=-111.66,
                  description="Fastest-growing submarket in metro Phoenix, underserved retail", acreage=25.0, zoning_type="C-2 Commercial"),
    CandidateSite(id="ph4", name="Scottsdale McDowell Road", lat=33.4862, lng=-111.9095,
                  description="High-income urban edge, premium-aligned demographics", acreage=12.0, zoning_type="B-1 Retail"),
    CandidateSite(id="ph5", name="Laveen Village Center", lat=33.3806, lng=-112.17,
                  description="Emerging southwest Phoenix, low competition, high growth", acreage=30.0, zoning_type="C-2 Commercial"),
    CandidateSite(id="ph6", name="Mesa Superstition Springs Area", lat=33.395, lng=-111.69,
                  description="Established East Mesa retail corridor, strong family base", acreage=20.0, zoning_type="C-3 General Commercial"),
    CandidateSite(id="ph7", name="Avondale Estrella Corridor", lat=33.4355, lng=-112.38,
                  description="West Valley growth zone, budget-friendly demographics", acreage=28.0, zoning_type="C-2 Commercial"),
    CandidateSite(id="ph8", name="Chandler Fashion Triangle", lat=33.3062, lng=-111.89,
                  description="Affluent South Chandler, strong premium brand alignment", acreage=15.0, zoning_type="B-2 General Business"),
    CandidateSite(id="ph9", name="North Scottsdale 101 Node", lat=33.6391, lng=-111.87,
                  description="High-income Scottsdale fringe, premium household incomes", acreage=16.0, zoning_type="C-1 Neighborhood Commercial"),
    CandidateSite(id="ph10", name="Goodyear Cotton Lane Area", lat=33.4353, lng=-112.45,
                  description="Far West Valley newcomers, underserved big-box market", acreage=35.0, zoning_type="C-2 Commercial"),
]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/candidates")
async def get_candidates():
    """Return pre-defined Phoenix metro candidate sites."""
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
async def get_competitors(lat: float = 33.4484, lng: float = -112.0740, radius: float = 25.0):
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
        "version": "2.0.0",
        "features": ["brand_resolver", "hotspot_agent", "amenity_agent", "universal_retailer"],
    }
