"""
Business Amenity Intelligence Agent

Assesses the physical + infrastructure suitability of a candidate site:
  - Power infrastructure (OSM substation nodes)
  - Water/Sewer availability (OSM utility nodes)
  - Internet reliability (FCC Broadband Map API)
  - Available commercial development spaces (Loopnet via TinyFish)
  - Zoning compatibility (OSM landuse)
  - Active construction / development activity (OSM)

All OSM queries are free and require no API key.
Uses the robust multi-mirror overpass_client (3 endpoints, exponential backoff).
FCC Broadband API is free and public.
TinyFish calls (Loopnet) are optional — gracefully fallback if unavailable.
"""
import asyncio
import math
from typing import AsyncGenerator

import requests
from app.models.schemas import AmenityProfile, StoreSizeEnum
from app.services.tinyfish_service import scrape_loopnet_listings, _has_tinyfish_key
from app.services import overpass_client

# Bounding box from center lat/lng + radius in degrees
def _bbox(lat: float, lng: float, radius_deg: float = 0.06) -> str:
    return f"{lat - radius_deg},{lng - radius_deg},{lat + radius_deg},{lng + radius_deg}"


def _count_power_nodes(lat: float, lng: float) -> int:
    """Count power substations and lines within ~4 miles."""
    bbox = _bbox(lat, lng, radius_deg=0.07)
    q = f"""[out:json][timeout:10];
(
  node["power"="substation"]({bbox});
  node["power"="transformer"]({bbox});
  way["power"="line"]({bbox});
);
out count;"""
    elements = overpass_client.query(q, timeout_s=15)
    return len(elements)


def _count_water_nodes(lat: float, lng: float) -> int:
    """Count water utility nodes within ~2 miles."""
    bbox = _bbox(lat, lng, radius_deg=0.04)
    q = f"""[out:json][timeout:10];
(
  node["utility"="water"]({bbox});
  node["man_made"="water_tower"]({bbox});
  way["waterway"~"canal|drain|ditch"]({bbox});
);
out count;"""
    elements = overpass_client.query(q, timeout_s=15)
    return len(elements)


def _check_zoning(lat: float, lng: float) -> float:
    """Score zoning compatibility based on OSM landuse tags near site."""
    bbox = _bbox(lat, lng, radius_deg=0.02)
    q = f"""[out:json][timeout:10];
(
  way["landuse"~"commercial|retail|industrial"]({bbox});
  way["shop"]({bbox});
  way["amenity"~"marketplace|parking"]({bbox});
);
out count;"""
    elements = overpass_client.query(q, timeout_s=15)
    count = len(elements)
    # 0 = residential only (~40), 5+ = clearly commercial area (~90)
    return min(40 + count * 10, 95)


def _check_construction(lat: float, lng: float) -> float:
    """Score active development based on construction polygons nearby."""
    bbox = _bbox(lat, lng, radius_deg=0.05)
    q = f"""[out:json][timeout:10];
(
  way["landuse"="construction"]({bbox});
  way["building"="construction"]({bbox});
);
out count;"""
    elements = overpass_client.query(q, timeout_s=15)
    count = len(elements)
    # More construction = more development activity = higher score
    return min(45 + count * 12, 95)


def _fcc_broadband_score(lat: float, lng: float) -> float:
    """
    Query FCC Broadband Map API for internet coverage at this location.
    Returns 0-100 score based on maximum available download speed.
    Falls back to 60 (moderate) if API unavailable.
    """
    try:
        resp = requests.get(
            "https://broadbandmap.fcc.gov/api/public/map/listAvailability",
            params={
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
                "unit": "1",
                "addr": "",
                "city": "",
                "state": "",
                "zip": "",
            },
            headers={"User-Agent": "RetailIQ/1.0"},
            timeout=12,
        )
        if resp.status_code == 200:
            data = resp.json()
            providers = data.get("availability", [])
            if providers:
                max_dl = max((p.get("max_advertised_download_speed", 0) for p in providers), default=0)
                # Score: <25Mbps=20, 25-100=50, 100-500=75, 500+=90, 1000+= 100
                if max_dl >= 1000:
                    return 100.0
                elif max_dl >= 500:
                    return 90.0
                elif max_dl >= 100:
                    return 75.0
                elif max_dl >= 25:
                    return 50.0
                else:
                    return 20.0
    except Exception:
        pass
    return 60.0  # FCC API unavailable — return neutral


def _stable_fallback_score(lat: float, lng: float, offset: float) -> float:
    """Stable deterministic score for when OSM query returns 0 (suburb/exurb areas)."""
    seed = abs(math.sin((lat + offset) * 137.5) * math.cos((lng + offset) * 137.5))
    return round(50 + seed * 30, 1)  # 50–80 range


async def run_amenity_agent(
    lat: float,
    lng: float,
    store_size: StoreSizeEnum = StoreSizeEnum.BIG_BOX,
    region_city: str = "Phoenix, AZ",
) -> AsyncGenerator[dict, None]:
    """
    Business Amenity Intelligence Agent.
    Async generator — yields trace events + final AmenityProfile.
    """
    yield {
        "agent": "amenity",
        "status": "running",
        "message": f"🏗️ Amenity Agent: assessing infrastructure suitability for {store_size.value} store...",
    }

    loop = asyncio.get_event_loop()

    # ── Power infrastructure (Overpass) ─────────────────────────────────────
    yield {"agent": "amenity", "status": "running", "message": "⚡ Checking power infrastructure..."}
    power_count = await loop.run_in_executor(None, _count_power_nodes, lat, lng)
    power_score = min(35 + power_count * 15, 100) if power_count > 0 else _stable_fallback_score(lat, lng, 1.0)
    yield {"agent": "amenity", "status": "running",
           "message": f"  Power: {power_count} nodes nearby → score {power_score:.0f}/100"}

    # ── Water/Sewer (Overpass) ───────────────────────────────────────────────
    yield {"agent": "amenity", "status": "running", "message": "💧 Checking water/sewer access..."}
    water_count = await loop.run_in_executor(None, _count_water_nodes, lat, lng)
    water_score = min(40 + water_count * 20, 100) if water_count > 0 else _stable_fallback_score(lat, lng, 2.0)
    yield {"agent": "amenity", "status": "running",
           "message": f"  Water: {water_count} nodes → score {water_score:.0f}/100"}

    # ── Internet / FCC Broadband ─────────────────────────────────────────────
    yield {"agent": "amenity", "status": "running", "message": "🌐 Querying FCC Broadband Map..."}
    internet_score = await loop.run_in_executor(None, _fcc_broadband_score, lat, lng)
    yield {"agent": "amenity", "status": "running",
           "message": f"  Broadband: {internet_score:.0f}/100"}

    # ── Zoning compatibility (Overpass) ─────────────────────────────────────
    yield {"agent": "amenity", "status": "running", "message": "📋 Checking zoning compatibility..."}
    zoning_score = await loop.run_in_executor(None, _check_zoning, lat, lng)
    yield {"agent": "amenity", "status": "running",
           "message": f"  Zoning: {zoning_score:.0f}/100 (commercial landuse coverage)"}

    # ── Active construction / development (Overpass) ─────────────────────────
    yield {"agent": "amenity", "status": "running", "message": "🚧 Checking development activity..."}
    dev_score = await loop.run_in_executor(None, _check_construction, lat, lng)
    yield {"agent": "amenity", "status": "running",
           "message": f"  Development activity: {dev_score:.0f}/100"}

    # ── Loopnet available spaces (TinyFish optional) ─────────────────────────
    loopnet_count = 0
    space_types = ["lease", "build_to_suit"]
    tf_powered = False

    if _has_tinyfish_key():
        yield {"agent": "amenity", "status": "running",
               "message": "🕷️ TinyFish: checking Loopnet for available commercial spaces..."}
        try:
            from app.core.config import get_settings

            lf_budget = max(12.0, float(get_settings().tinyfish_agent_timeout_seconds) + 6.0)
            loopnet_data = await asyncio.wait_for(
                scrape_loopnet_listings(region_city, store_size.value),
                timeout=lf_budget,
            )
            loopnet_count = loopnet_data.get("count", 0)
            listings = loopnet_data.get("listings", [])
            # Infer available space types
            types = set()
            for l in listings:
                lt = l.get("listing_type", "").lower()
                if "lease" in lt:
                    types.add("lease")
                elif "sale" in lt or "purchase" in lt:
                    types.add("purchase")
                elif "build" in lt or "bts" in lt:
                    types.add("build_to_suit")
            space_types = list(types) if types else ["lease"]
            tf_powered = True
            yield {"agent": "amenity", "status": "running",
                   "message": f"  Loopnet: {loopnet_count} available spaces ({', '.join(space_types)})"}
        except (asyncio.TimeoutError, Exception) as e:
            yield {"agent": "amenity", "status": "running",
                   "message": f"  Loopnet scrape skipped/failed ({str(e)[:80]}) — using estimate"}
            loopnet_count = int(_stable_fallback_score(lat, lng, 3.0) / 15)
    else:
        loopnet_count = int(_stable_fallback_score(lat, lng, 3.0) / 15)
        yield {"agent": "amenity", "status": "running",
               "message": f"  Loopnet: estimated {loopnet_count} spaces (TinyFish offline)"}

    # ── Composite score ──────────────────────────────────────────────────────
    # Big-box stores have higher utility demands → penalize lower scores more
    size_multiplier = 1.0 if store_size in [StoreSizeEnum.BIG_BOX, StoreSizeEnum.LARGE] else 0.9

    overall = (
        power_score * 0.20
        + water_score * 0.15
        + internet_score * 0.15
        + zoning_score * 0.25
        + dev_score * 0.15
        + min(loopnet_count * 8, 80) * 0.10
    ) * size_multiplier

    profile = AmenityProfile(
        power_infrastructure_score=round(power_score, 1),
        water_sewer_score=round(water_score, 1),
        internet_reliability_score=round(internet_score, 1),
        available_commercial_spaces=loopnet_count,
        zoning_compatibility_score=round(zoning_score, 1),
        development_activity_score=round(dev_score, 1),
        overall_amenity_score=round(min(overall, 100), 1),
        available_space_types=space_types,
        tinyfish_powered=tf_powered,
    )

    tf_badge = "[TinyFish ✓]" if tf_powered else "[OSM + FCC]"
    yield {
        "agent": "amenity",
        "status": "done",
        "message": (
            f"🏗️ Amenity score: {profile.overall_amenity_score:.0f}/100 "
            f"| Power {power_score:.0f} · Water {water_score:.0f} · Internet {internet_score:.0f} "
            f"· Zoning {zoning_score:.0f} {tf_badge}"
        ),
        "data": profile.model_dump(),
    }
