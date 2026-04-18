"""
API Routes for RetailIQ
"""
import asyncio
import json
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import AnalyzeRequest, CandidateSite
from app.agents.orchestrator import run_orchestrator
from app.services.osm_service import fetch_competitors

router = APIRouter()

# In-memory job store for simplicity (replace with Redis in production)
_jobs: dict[str, dict] = {}

# Pre-defined Phoenix metro candidate sites for demo
CANDIDATE_SITES = [
    CandidateSite(id="ph1", name="Gilbert Gateway Towne Center Area", lat=33.3400, lng=-111.7600,
                  description="High-growth East Valley corridor, family-dense, strong school district", acreage=18.5, zoning_type="C-2 Commercial"),
    CandidateSite(id="ph2", name="Peoria 101 Corridor", lat=33.5806, lng=-112.2300,
                  description="Growing suburban northwest, new housing developments nearby", acreage=22.0, zoning_type="C-3 General Commercial"),
    CandidateSite(id="ph3", name="Queen Creek Marketplace Area", lat=33.2487, lng=-111.6600,
                  description="Fastest-growing submarket in metro Phoenix, underserved retail", acreage=25.0, zoning_type="C-2 Commercial"),
    CandidateSite(id="ph4", name="Scottsdale McDowell Road", lat=33.4862, lng=-111.9095,
                  description="High-income urban edge, Target-aligned demographics", acreage=12.0, zoning_type="B-1 Retail"),
    CandidateSite(id="ph5", name="Laveen Village Center", lat=33.3806, lng=-112.1700,
                  description="Emerging southwest Phoenix, low competition, high growth", acreage=30.0, zoning_type="C-2 Commercial"),
    CandidateSite(id="ph6", name="Mesa Superstition Springs Area", lat=33.3950, lng=-111.6900,
                  description="Established East Mesa retail corridor, strong family base", acreage=20.0, zoning_type="C-3 General Commercial"),
    CandidateSite(id="ph7", name="Avondale Estrella Corridor", lat=33.4355, lng=-112.3800,
                  description="West Valley growth zone, budget-friendly demographics, Walmart fit", acreage=28.0, zoning_type="C-2 Commercial"),
    CandidateSite(id="ph8", name="Chandler Fashion Triangle", lat=33.3062, lng=-111.8900,
                  description="Affluent South Chandler, strong Target brand alignment", acreage=15.0, zoning_type="B-2 General Business"),
    CandidateSite(id="ph9", name="North Scottsdale 101 Node", lat=33.6391, lng=-111.8700,
                  description="High-income Scottsdale fringe, premium household incomes", acreage=16.0, zoning_type="C-1 Neighborhood Commercial"),
    CandidateSite(id="ph10", name="Goodyear Cotton Lane Area", lat=33.4353, lng=-112.4500,
                  description="Far West Valley newcomers, underserved big-box market", acreage=35.0, zoning_type="C-2 Commercial"),
]


@router.get("/candidates")
async def get_candidates():
    """Return pre-defined Phoenix metro candidate sites."""
    return {"candidates": [s.model_dump() for s in CANDIDATE_SITES]}


@router.get("/competitors")
async def get_competitors(lat: float = 33.4484, lng: float = -112.0740, radius: float = 25.0):
    """Return competitor store locations for the Phoenix metro area."""
    try:
        stores = fetch_competitors(lat, lng, radius)
        return {"stores": stores, "count": len(stores)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/stream")
async def analyze_stream(request: AnalyzeRequest):
    """
    SSE endpoint: runs the full agent pipeline and streams trace events.
    Each event is a JSON object on a data: line.
    """
    async def event_generator():
        try:
            async for event in run_orchestrator(
                lat=request.lat,
                lng=request.lng,
                brand=request.brand.value,
                radius_miles=request.radius_miles,
            ):
                yield f"data: {json.dumps(event)}\n\n"
                await asyncio.sleep(0)  # Yield control to event loop
        except Exception as e:
            yield f"data: {json.dumps({'agent': 'orchestrator', 'status': 'error', 'message': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/analyze")
async def analyze(request: AnalyzeRequest):
    """
    Blocking endpoint: runs the full agent pipeline and returns when complete.
    Use /analyze/stream for real-time updates.
    """
    final_result = None
    async for event in run_orchestrator(
        lat=request.lat,
        lng=request.lng,
        brand=request.brand.value,
        radius_miles=request.radius_miles,
    ):
        if event.get("status") == "complete" and event.get("data"):
            final_result = event["data"]

    if not final_result:
        raise HTTPException(status_code=500, detail="Analysis failed — no result produced")

    return final_result


@router.get("/health")
async def health():
    return {"status": "ok", "service": "RetailIQ API", "version": "1.0.0"}
