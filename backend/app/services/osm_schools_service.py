"""
OSM Schools Service — fetches schools + housing-growth signals within a radius.

Supports two queries:
  * fetch_schools(lat, lng, radius_miles)      → list[{name,lat,lng,type}]
  * fetch_growth_corridors(lat, lng, radius)   → list[{name,lat,lng,kind}]
      (residential construction + commercial construction, inferred from OSM
       `building:construction`, `landuse=construction`, `construction=yes`)

Primary source: Geoapify (when `geoapify_api_key` is set).
Fallback: OSM Overpass via shared `overpass_client`.
Both layers are cached via Supabase KV so the scout + analyze routes don't
re-hit OSM for the same neighborhood.
"""
from __future__ import annotations

import logging
import math
import time
from typing import List, Dict, Optional

import requests

from app.core.config import get_settings
from app.services import overpass_client
from app.services.supabase_service import cache_get, cache_set

log = logging.getLogger(__name__)


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Schools ─────────────────────────────────────────────────────────────────

def fetch_schools(lat: float, lng: float, radius_miles: float = 10.0) -> List[Dict]:
    """Returns a list of nearby schools (K–12 + colleges) from OSM/Geoapify."""
    cache_key = f"schools:{lat:.3f},{lng:.3f},{radius_miles:.0f}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    settings = get_settings()
    schools: List[Dict] = []

    if settings.geoapify_api_key:
        schools = _fetch_schools_geoapify(lat, lng, radius_miles) or []

    if not schools:
        schools = _fetch_schools_overpass(lat, lng, radius_miles) or []

    if schools:
        cache_set(cache_key, schools)
    return schools


def _fetch_schools_geoapify(lat: float, lng: float, radius_miles: float) -> Optional[List[Dict]]:
    api_key = get_settings().geoapify_api_key
    radius_m = int(radius_miles * 1609.34)
    categories = "education.school,education.college,education.university"
    try:
        r = requests.get(
            "https://api.geoapify.com/v2/places",
            params={
                "categories": categories,
                "filter":     f"circle:{lng},{lat},{radius_m}",
                "limit":      400,
                "apiKey":     api_key,
            },
            timeout=10,
        )
        r.raise_for_status()
        feats = r.json().get("features", [])
        out: List[Dict] = []
        for f in feats:
            props = f.get("properties", {})
            geom = f.get("geometry", {}).get("coordinates", [None, None])
            flng, flat = geom[0], geom[1]
            if flat is None or flng is None:
                continue
            cats = props.get("categories") or []
            kind = "college" if any("college" in c or "university" in c for c in cats) else "school"
            out.append({
                "name":  props.get("name") or "Unnamed school",
                "lat":   flat,
                "lng":   flng,
                "type":  kind,
                "level": props.get("datasource", {}).get("raw", {}).get("school:type")
                          or props.get("datasource", {}).get("raw", {}).get("amenity"),
            })
        return out
    except Exception as e:
        log.warning(f"[OSMSchools/Geoapify] failed: {e}")
        return None


def _fetch_schools_overpass(lat: float, lng: float, radius_miles: float) -> List[Dict]:
    radius_m = int(radius_miles * 1609.34)
    ql = f"""
[out:json][timeout:20];
(
  nwr["amenity"="school"](around:{radius_m},{lat},{lng});
  nwr["amenity"="college"](around:{radius_m},{lat},{lng});
  nwr["amenity"="university"](around:{radius_m},{lat},{lng});
);
out center;
"""
    elements = overpass_client.query(ql, timeout_s=20) or []
    out: List[Dict] = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name") or "Unnamed school"
        if el.get("type") == "node":
            elat, elng = el.get("lat"), el.get("lon")
        else:
            center = el.get("center", {})
            elat, elng = center.get("lat"), center.get("lon")
        if not elat or not elng:
            continue
        amenity = tags.get("amenity", "school")
        out.append({
            "name":  name,
            "lat":   elat,
            "lng":   elng,
            "type":  "college" if amenity in ("college", "university") else "school",
            "level": tags.get("isced:level") or tags.get("school:type"),
        })
    return out


# ── Housing / growth corridors (residential + commercial construction) ─────

def fetch_growth_corridors(lat: float, lng: float, radius_miles: float = 10.0) -> List[Dict]:
    """
    Proxy for new-housing / development activity — looks for OSM features
    tagged `landuse=construction`, `building=construction`, or having a
    `construction=*` tag. Approximates housing growth signals without
    needing a permits API.
    """
    cache_key = f"growth:{lat:.3f},{lng:.3f},{radius_miles:.0f}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    radius_m = int(radius_miles * 1609.34)
    ql = f"""
[out:json][timeout:20];
(
  nwr["landuse"="construction"](around:{radius_m},{lat},{lng});
  nwr["building"="construction"](around:{radius_m},{lat},{lng});
  nwr["construction"="residential"](around:{radius_m},{lat},{lng});
  nwr["construction"="yes"](around:{radius_m},{lat},{lng});
  nwr["landuse"="residential"]["start_date"~"^202[3-9]"](around:{radius_m},{lat},{lng});
);
out center;
"""
    out: List[Dict] = []
    try:
        elements = overpass_client.query(ql, timeout_s=20) or []
    except Exception as e:
        log.warning(f"[OSMSchools/growth] overpass failed: {e}")
        elements = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("construction") or tags.get("landuse") or "Construction / dev site"
        if el.get("type") == "node":
            elat, elng = el.get("lat"), el.get("lon")
        else:
            center = el.get("center", {})
            elat, elng = center.get("lat"), center.get("lon")
        if not elat or not elng:
            continue
        kind = "residential"
        if tags.get("building") == "commercial" or tags.get("landuse") == "commercial":
            kind = "commercial"
        elif tags.get("construction") == "residential" or tags.get("landuse") == "residential":
            kind = "residential"
        out.append({
            "name": name[:60],
            "lat":  elat,
            "lng":  elng,
            "kind": kind,
        })
    if out:
        cache_set(cache_key, out)
    return out
