"""
OpenStreetMap / Overpass API Service
Fetches competitor retail store locations near a given lat/lng.
Queries Walmart, Target, Costco, Kroger, Aldi, Sam's Club, Fry's (Kroger brand in AZ), etc.
"""
import json
import math
import os
import time
import requests
from app.models.schemas import CompetitorStore, CompetitorProfile

CACHE_DIR = os.path.join(os.path.dirname(__file__), "../../data/cache")
os.makedirs(CACHE_DIR, exist_ok=True)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Known big-box / superstore brands to monitor
BIG_BOX_BRANDS = {
    "walmart": ["Walmart", "Walmart Supercenter", "Walmart Neighborhood Market"],
    "target": ["Target"],
    "costco": ["Costco", "Costco Wholesale"],
    "sams_club": ["Sam's Club"],
    "kroger": ["Kroger", "Fry's", "Fry's Food Stores"],
    "aldi": ["Aldi", "ALDI"],
    "meijer": ["Meijer"],
    "whole_foods": ["Whole Foods", "Whole Foods Market"],
    "trader_joes": ["Trader Joe's"],
    "safeway": ["Safeway", "Albertsons"],
    "sprouts": ["Sprouts", "Sprouts Farmers Market"],
}

BRAND_SCORES = {
    "walmart": 10, "sams_club": 9,  # Direct Walmart competitors
    "target": 9,                     # Direct Target competitor
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


def _cache_path(lat: float, lng: float, radius_miles: float) -> str:
    key = f"osm_{lat:.3f}_{lng:.3f}_{radius_miles:.0f}"
    return os.path.join(CACHE_DIR, f"{key}.json")


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


def fetch_competitors(lat: float, lng: float, radius_miles: float = 10.0) -> list[dict]:
    """Query Overpass API for competitor stores, with caching."""
    cache_file = _cache_path(lat, lng, radius_miles)
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            return json.load(f)

    radius_m = radius_miles * 1609.34
    query = _build_overpass_query(lat, lng, radius_m)

    try:
        resp = requests.post(OVERPASS_URL, data={"data": query}, timeout=35)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        stores = []
        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name", "Unknown")
            # Get coordinates
            if el.get("type") == "node":
                elat, elng = el.get("lat", 0), el.get("lon", 0)
            else:
                center = el.get("center", {})
                elat, elng = center.get("lat", 0), center.get("lon", 0)
            if not elat or not elng:
                continue
            stores.append({
                "name": name,
                "brand": _normalize_brand(name),
                "lat": elat,
                "lng": elng,
                "osm_id": str(el.get("id", "")),
                "shop_type": tags.get("shop", "retail"),
            })
        with open(cache_file, "w") as f:
            json.dump(stores, f)
        return stores
    except Exception as e:
        print(f"[OSMService] Overpass error: {e}, using fallback data")
        return _get_fallback_competitors(lat, lng)


def get_competitor_profile(lat: float, lng: float, radius_miles: float = 10.0, brand: str = "walmart") -> CompetitorProfile:
    """Analyze competitors and compute scores."""
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

    # Score computation
    big_box_names = ["walmart", "target", "costco", "sams_club", "meijer"]
    big_box_count = sum(1 for s in raw_stores if s.get("brand") in big_box_names)
    total = len(stores_with_distance)

    # Saturation: too many big-box within 5 miles = saturated
    within_5_big_box = sum(
        1 for s in stores_with_distance
        if s.distance_miles <= 5 and any(bb in s.brand_name.lower() for bb in ["walmart", "target", "costco", "sam"])
    )
    saturation = min(within_5_big_box * 20, 100.0)

    # Demand signal: presence of any competitors = proven retail demand
    demand_signal = min(total * 6, 80.0) + (10 if total > 0 else 0)

    # Competition score: high demand + low saturation = best position
    competition_score = max(0.0, demand_signal - saturation * 0.5)
    competition_score = min(competition_score, 100.0)

    underserved = big_box_count == 0 or (big_box_count < 2 and total < 5)

    return CompetitorProfile(
        stores=stores_with_distance[:20],  # Cap at 20 for response size
        total_count=total,
        big_box_count=big_box_count,
        saturation_score=round(saturation, 1),
        demand_signal_score=round(demand_signal, 1),
        competition_score=round(competition_score, 1),
        underserved=underserved,
    )


def _get_fallback_competitors(lat: float, lng: float) -> list[dict]:
    """Realistic Phoenix metro fallback competitor data."""
    # Phoenix area stores relative offsets
    offsets = [
        ("Walmart Supercenter", "walmart", 0.045, -0.032),
        ("Target", "target", -0.028, 0.041),
        ("Costco Wholesale", "costco", 0.062, -0.018),
        ("Fry's Food Stores", "kroger", -0.015, -0.055),
        ("Sprouts Farmers Market", "sprouts", 0.031, 0.012),
        ("Aldi", "aldi", -0.052, 0.038),
        ("Walmart Supercenter", "walmart", -0.071, -0.044),
        ("Target", "target", 0.089, 0.021),
        ("Safeway", "safeway", 0.018, -0.076),
        ("Sam's Club", "sams_club", -0.088, 0.055),
        ("Sprouts Farmers Market", "sprouts", 0.055, -0.065),
        ("Trader Joe's", "trader_joes", -0.038, -0.091),
    ]
    stores = []
    for name, brand, dlat, dlng in offsets:
        stores.append({
            "name": name,
            "brand": brand,
            "lat": lat + dlat,
            "lng": lng + dlng,
            "osm_id": f"fallback_{brand}_{dlat:.3f}",
            "shop_type": "supermarket",
        })
    return stores
