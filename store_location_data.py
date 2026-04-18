import requests
import math
import time

LAT = 44.9778
LON = -93.2650
RADIUS_M = 5000

# OSM tags differently by store type -- need all three
COMPETITOR_QUERY = f"""
[out:json][timeout:25];
(
  node["shop"="supermarket"](around:{RADIUS_M},{LAT},{LON});
  way["shop"="supermarket"](around:{RADIUS_M},{LAT},{LON});
  node["shop"="department_store"](around:{RADIUS_M},{LAT},{LON});
  way["shop"="department_store"](around:{RADIUS_M},{LAT},{LON});
  node["shop"="wholesale"](around:{RADIUS_M},{LAT},{LON});
  way["shop"="wholesale"](around:{RADIUS_M},{LAT},{LON});
);
out center;
"""

TARGET_BRANDS = {
    "walmart", "target", "costco", "aldi", "cub foods",
    "whole foods", "whole foods market", "trader joe's",
    "hy-vee", "fresh thyme", "lunds & byerlys", "kowalski's"
}

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    p = math.pi / 180
    a = (math.sin((lat2-lat1)*p/2)**2 +
         math.cos(lat1*p) * math.cos(lat2*p) *
         math.sin((lon2-lon1)*p/2)**2)
    return 2 * R * math.asin(math.sqrt(a))

def fetch_competitors(lat, lon):
    r = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": COMPETITOR_QUERY},
        timeout=30
    )
    elements = r.json().get("elements", [])
    
    stores = []
    for e in elements:
        tags = e.get("tags", {})
        name = tags.get("name", "Unknown")
        lat2 = e.get("lat") or e.get("center", {}).get("lat")
        lon2 = e.get("lon") or e.get("center", {}).get("lon")
        if lat2 and lon2:
            stores.append({
                "name": name,
                "lat": lat2,
                "lon": lon2,
                "dist_m": haversine(lat, lon, lat2, lon2),
                "is_major": name.lower() in TARGET_BRANDS
            })
    return stores

def analyze(lat, lon, stores):
    major = [s for s in stores if s["is_major"]]
    
    nearest = min(stores, key=lambda s: s["dist_m"]) if stores else None
    nearest_major = min(major, key=lambda s: s["dist_m"]) if major else None
    
    density = len(stores) / ((RADIUS_M/1000)**2 * math.pi)  # stores per sq km
    
    # white space: no major competitor within 2km
    whitespace = not any(s["dist_m"] < 2000 for s in major)

    print(f"\n--- Competitor Analysis for ({lat}, {lon}) ---")
    print(f"Total competitors within {RADIUS_M}m : {len(stores)}")
    print(f"Major brand competitors               : {len(major)}")
    print(f"Competitor density (per sq km)        : {density:.2f}")
    print(f"Nearest competitor                    : {nearest['name']} ({nearest['dist_m']:.0f}m)" if nearest else "None")
    print(f"Nearest major brand                   : {nearest_major['name']} ({nearest_major['dist_m']:.0f}m)" if nearest_major else "None")
    print(f"White space opportunity               : {'YES' if whitespace else 'NO'}")

    print(f"\nAll competitors:")
    for s in sorted(stores, key=lambda x: x["dist_m"]):
        flag = " *** MAJOR" if s["is_major"] else ""
        print(f"  {s['name']:<35} {s['dist_m']:>6.0f}m{flag}")

stores = fetch_competitors(LAT, LON)
analyze(LAT, LON, stores)