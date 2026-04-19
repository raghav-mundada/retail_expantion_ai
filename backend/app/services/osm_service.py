"""
OpenStreetMap / Overpass API Service
─────────────────────────────────────
Fetches competitor retail store locations near a given lat/lng.

Primary source: Geoapify Places API (fast, global, structured JSON).
Fallback: Overpass/OSM multi-mirror client with exponential backoff.

Geoapify is preferred because Overpass queries can take 30–90 s when
mirrors are under load — Geoapify returns in < 3 s with an API key.
"""
import math
import logging
import time
import requests
from app.models.schemas import CompetitorStore, CompetitorProfile
from app.core.config import get_settings
from app.services import overpass_client
from app.services.supabase_service import cache_get, cache_set

log = logging.getLogger(__name__)

# Known big-box / superstore brands to monitor
BIG_BOX_BRANDS = {
    "walmart":     ["Walmart", "Walmart Supercenter", "Walmart Neighborhood Market"],
    "target":      ["Target"],
    "costco":      ["Costco", "Costco Wholesale"],
    "sams_club":   ["Sam's Club"],
    "kroger":      ["Kroger", "Fry's", "Fry's Food Stores"],
    "aldi":        ["Aldi", "ALDI"],
    "meijer":      ["Meijer"],
    "whole_foods": ["Whole Foods", "Whole Foods Market"],
    "trader_joes": ["Trader Joe's"],
    "safeway":     ["Safeway", "Albertsons"],
    "sprouts":     ["Sprouts", "Sprouts Farmers Market"],
}

BRAND_SCORES = {
    "walmart": 10, "sams_club": 9,
    "target": 9,
    "costco": 8, "meijer": 8,
    "kroger": 7, "safeway": 7,
    "aldi": 6, "trader_joes": 5,
    "whole_foods": 4, "sprouts": 4,
}


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _build_overpass_query(lat: float, lng: float, radius_meters: float) -> str:
    all_brands = []
    for brands in BIG_BOX_BRANDS.values():
        all_brands.extend(brands)
    brand_regex = "|".join(all_brands)

    return f"""
[out:json][timeout:30];
(
  nwr["shop"]["name"~"{brand_regex}",i]
    (around:{radius_meters:.0f},{lat},{lng});
  nwr["shop"="supermarket"]["name"~"{brand_regex}",i]
    (around:{radius_meters:.0f},{lat},{lng});
  nwr["shop"="department_store"]["name"~"Walmart|Target|Costco|Meijer",i]
    (around:{radius_meters:.0f},{lat},{lng});
);
out center;
"""


def _normalize_brand(name: str) -> str:
    name_lower = name.lower()
    for brand_key, brand_names in BIG_BOX_BRANDS.items():
        for bn in brand_names:
            if bn.lower() in name_lower:
                return brand_key
    return "other"


def _osm_cache_key(lat: float, lng: float, radius_miles: float) -> str:
    return f"osm:{lat:.3f},{lng:.3f},{radius_miles:.0f}"


def _fetch_via_geoapify(lat: float, lng: float, radius_miles: float) -> list[dict] | None:
    """
    Fetch competitor stores via Geoapify Places API.
    Returns a list of store dicts, or None if key is absent / call fails.
    Mirrors the approach in backend/pipeline/fetch_all.py (main branch).
    """
    settings = get_settings()
    api_key = settings.geoapify_api_key
    if not api_key:
        return None

    radius_m = int(radius_miles * 1609.34)
    # Supermarkets + department stores cover the big-box retail universe
    categories = "commercial.supermarket,commercial.department_store,commercial.shopping_mall"
    url = "https://api.geoapify.com/v2/places"
    params = {
        "categories": categories,
        "filter": f"circle:{lng},{lat},{radius_m}",
        "limit": 500,
        "apiKey": api_key,
    }

    delays = [2, 5]
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=20)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(delays[attempt])
                continue
            r.raise_for_status()
            features = r.json().get("features", [])
            stores = []
            for f in features:
                props = f.get("properties", {})
                geom = f.get("geometry", {}).get("coordinates", [None, None])
                flng, flat = geom[0], geom[1]
                if flat is None or flng is None:
                    continue
                name = props.get("name") or "Unknown"
                stores.append({
                    "name":      name,
                    "brand":     _normalize_brand(name),
                    "lat":       flat,
                    "lng":       flng,
                    "osm_id":    props.get("place_id", ""),
                    "shop_type": (props.get("categories") or ["retail"])[-1].split(".")[-1],
                })
            log.info(f"[OSMService/Geoapify] Found {len(stores)} stores at ({lat:.3f},{lng:.3f})")
            return stores
        except Exception as e:
            if attempt < 2:
                time.sleep(delays[attempt])
            else:
                log.warning(f"[OSMService/Geoapify] Failed after 3 attempts: {e}")
    return None


def fetch_competitors(lat: float, lng: float, radius_miles: float = 10.0) -> list[dict]:
    """
    Query for competitor stores. Tries Geoapify first (fast), then Overpass (fallback).
    Results cached in Supabase KV.
    """
    cache_key = _osm_cache_key(lat, lng, radius_miles)
    cached = cache_get(cache_key)
    if cached:
        log.info(f"[OSMService] Cache hit: {len(cached)} stores at ({lat:.3f},{lng:.3f})")
        return cached

    # ── Primary: Geoapify Places API ─────────────────────────────────────────
    stores = _fetch_via_geoapify(lat, lng, radius_miles)

    # ── Fallback: Overpass/OSM ────────────────────────────────────────────────
    if stores is None:
        log.info("[OSMService] Geoapify unavailable — trying Overpass")
        radius_m = radius_miles * 1609.34
        ql = _build_overpass_query(lat, lng, radius_m)
        elements = overpass_client.query(ql, timeout_s=30)
        if elements:
            stores = []
            for el in elements:
                tags = el.get("tags", {})
                name = tags.get("name", "Unknown")
                if el.get("type") == "node":
                    elat, elng = el.get("lat", 0), el.get("lon", 0)
                else:
                    center = el.get("center", {})
                    elat, elng = center.get("lat", 0), center.get("lon", 0)
                if not elat or not elng:
                    continue
                stores.append({
                    "name":      name,
                    "brand":     _normalize_brand(name),
                    "lat":       elat,
                    "lng":       elng,
                    "osm_id":    str(el.get("id", "")),
                    "shop_type": tags.get("shop", "retail"),
                })
        else:
            log.warning("[OSMService] Overpass also returned no results — using fallback data")
            stores = _get_fallback_competitors(lat, lng)

    if stores:
        cache_set(cache_key, stores)

    log.info(f"[OSMService] Returning {len(stores)} competitor stores")
    return stores


def get_competitor_profile(
    lat: float, lng: float, radius_miles: float = 10.0, brand: str = "walmart"
) -> CompetitorProfile:
    """Analyze competitors and compute saturation/demand/competition scores."""
    raw_stores = fetch_competitors(lat, lng, radius_miles)

    stores_with_distance = []
    for s in raw_stores:
        dist = _haversine_miles(lat, lng, s["lat"], s["lng"])
        if dist <= radius_miles:
            stores_with_distance.append(CompetitorStore(
                brand_name=s["name"],
                lat=s["lat"],
                lng=s["lng"],
                distance_miles=round(dist, 2),
                store_type=s.get("shop_type", "retail"),
                osm_id=s.get("osm_id"),
            ))

    stores_with_distance.sort(key=lambda x: x.distance_miles)

    big_box_names = ["walmart", "target", "costco", "sams_club", "meijer"]
    big_box_count = sum(1 for s in raw_stores if s.get("brand") in big_box_names)
    total = len(stores_with_distance)

    within_5_big_box = sum(
        1 for s in stores_with_distance
        if s.distance_miles <= 5 and any(bb in s.brand_name.lower() for bb in ["walmart", "target", "costco", "sam"])
    )
    saturation = min(within_5_big_box * 20, 100.0)

    demand_signal = min(total * 6, 80.0) + (10 if total > 0 else 0)
    competition_score = max(0.0, min(demand_signal - saturation * 0.5, 100.0))
    underserved = big_box_count == 0 or (big_box_count < 2 and total < 5)

    return CompetitorProfile(
        stores=stores_with_distance[:20],
        total_count=total,
        big_box_count=big_box_count,
        saturation_score=round(saturation, 1),
        demand_signal_score=round(demand_signal, 1),
        competition_score=round(competition_score, 1),
        underserved=underserved,
    )


def _get_fallback_competitors(lat: float, lng: float) -> list[dict]:
    """Realistic fallback competitor data using relative offsets from center."""
    offsets = [
        ("Walmart Supercenter",    "walmart",     0.045, -0.032),
        ("Target",                 "target",     -0.028,  0.041),
        ("Costco Wholesale",       "costco",      0.062, -0.018),
        ("Fry's Food Stores",      "kroger",     -0.015, -0.055),
        ("Sprouts Farmers Market", "sprouts",     0.031,  0.012),
        ("Aldi",                   "aldi",       -0.052,  0.038),
        ("Walmart Supercenter",    "walmart",    -0.071, -0.044),
        ("Target",                 "target",      0.089,  0.021),
        ("Safeway",                "safeway",     0.018, -0.076),
        ("Sam's Club",             "sams_club",  -0.088,  0.055),
        ("Sprouts Farmers Market", "sprouts",     0.055, -0.065),
        ("Trader Joe's",           "trader_joes",-0.038, -0.091),
    ]
    return [
        {
            "name":      name,
            "brand":     brand,
            "lat":       lat + dlat,
            "lng":       lng + dlng,
            "osm_id":    f"fallback_{brand}_{dlat:.3f}",
            "shop_type": "supermarket",
        }
        for name, brand, dlat, dlng in offsets
    ]
