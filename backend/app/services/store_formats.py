"""
Store Format Profiles — deterministic retail format DNA (ported from main).

Each format defines income sweet spot, minimum viable population, brand
attractiveness for the Huff gravity model, build CapEx, operating margin,
min parcel acreage, spending-share of household income, and rival keywords.

`resolve_store_format(display_name)` maps an arbitrary brand string to the
closest known format — with a generic fallback for unknown brands.
"""
from __future__ import annotations

import math
from typing import Any, Dict


STORE_FORMATS: Dict[str, Dict[str, Any]] = {
    "Target": {
        "income_sweet_spot": (55_000, 110_000),
        "min_population":     40_000,
        "brand_weight":          100,
        "capex_usd":         15_000_000,
        "capex_multiplier":      1.8,
        "operating_margin":      0.05,
        "min_parcel_acres":      8.0,
        "category_share":        0.045,
        "rival_keywords": [
            "target", "walmart", "costco", "sam's club", "kohl",
            "macy", "jcpenney", "meijer", "fred meyer",
            "hy-vee", "cub", "menards", "home depot", "lowe", "best buy",
            "ikea", "fleet farm", "homegoods", "tjmaxx", "marshall",
        ],
    },
    "Walmart": {
        "income_sweet_spot": (35_000,  90_000),
        "min_population":     40_000,
        "brand_weight":          110,
        "capex_usd":         25_000_000,
        "capex_multiplier":      1.8,
        "operating_margin":      0.026,
        "min_parcel_acres":     12.0,
        "category_share":        0.055,
        "rival_keywords": [
            "walmart", "target", "costco", "sam's club", "bj",
            "meijer", "fred meyer", "kmart", "hy-vee", "cub",
            "menards", "home depot",
        ],
    },
    "Costco": {
        "income_sweet_spot": (70_000, 180_000),
        "min_population":     60_000,
        "brand_weight":          120,
        "capex_usd":         30_000_000,
        "capex_multiplier":      1.7,
        "operating_margin":      0.026,
        "min_parcel_acres":     15.0,
        "category_share":        0.060,
        "rival_keywords": ["costco", "sam's club", "bj", "walmart", "target"],
    },
    "Home Depot": {
        "income_sweet_spot": (45_000, 140_000),
        "min_population":     25_000,
        "brand_weight":           90,
        "capex_usd":         14_000_000,
        "capex_multiplier":      1.6,
        "operating_margin":      0.10,
        "min_parcel_acres":     10.0,
        "category_share":        0.030,
        "rival_keywords": [
            "home depot", "lowe", "menards", "ace hardware", "true value", "harbor freight",
        ],
    },
    "Best Buy": {
        "income_sweet_spot": (50_000, 150_000),
        "min_population":     20_000,
        "brand_weight":           65,
        "capex_usd":          5_000_000,
        "capex_multiplier":      1.5,
        "operating_margin":      0.04,
        "min_parcel_acres":      3.0,
        "category_share":        0.020,
        "rival_keywords": ["best buy", "microcenter", "apple store", "target", "walmart", "costco"],
    },
    "Walgreens": {
        "income_sweet_spot": (35_000, 80_000),
        "min_population":     15_000,
        "brand_weight":           60,
        "capex_usd":          4_000_000,
        "capex_multiplier":      1.5,
        "operating_margin":      0.04,
        "min_parcel_acres":      1.0,
        "category_share":        0.018,
        "rival_keywords": ["walgreens", "cvs", "rite aid", "duane reade", "pharmacy"],
    },
    "Whole Foods": {
        "income_sweet_spot": (85_000, 200_000),
        "min_population":     30_000,
        "brand_weight":           80,
        "capex_usd":         12_000_000,
        "capex_multiplier":      1.7,
        "operating_margin":      0.04,
        "min_parcel_acres":      3.0,
        "category_share":        0.085,
        "rival_keywords": [
            "whole foods", "trader joe", "lunds", "byerly", "fresh thyme",
            "sprouts", "kowalski", "fresh market",
        ],
    },
    "Trader Joe's": {
        "income_sweet_spot": (75_000, 180_000),
        "min_population":     25_000,
        "brand_weight":           70,
        "capex_usd":          6_000_000,
        "capex_multiplier":      1.6,
        "operating_margin":      0.05,
        "min_parcel_acres":      2.0,
        "category_share":        0.065,
        "rival_keywords": [
            "trader joe", "whole foods", "lunds", "byerly", "aldi", "fresh thyme", "sprouts",
        ],
    },
    "Aldi": {
        "income_sweet_spot": (30_000, 85_000),
        "min_population":     15_000,
        "brand_weight":           50,
        "capex_usd":          3_000_000,
        "capex_multiplier":      1.5,
        "operating_margin":      0.045,
        "min_parcel_acres":      1.5,
        "category_share":        0.042,
        "rival_keywords": [
            "aldi", "lidl", "cub", "rainbow", "save-a-lot",
            "winco", "food 4 less", "hy-vee", "walmart",
        ],
    },
    "Starbucks": {
        "income_sweet_spot": (55_000, 220_000),
        "min_population":      5_000,
        "brand_weight":           55,
        "capex_usd":            700_000,
        "capex_multiplier":      1.4,
        "operating_margin":      0.14,
        "min_parcel_acres":      0.15,
        "category_share":        0.014,
        "rival_keywords": ["starbucks", "caribou", "dunkin", "peet", "dutch bros", "coffee bean"],
    },
    "Local Grocery": {
        "income_sweet_spot": (40_000, 110_000),
        "min_population":      8_000,
        "brand_weight":           35,
        "capex_usd":          1_500_000,
        "capex_multiplier":      1.4,
        "operating_margin":      0.03,
        "min_parcel_acres":      0.5,
        "category_share":        0.040,
        "rival_keywords": [
            "grocery", "market", "foods", "supermercado", "deli",
            "aldi", "cub foods", "lunds", "byerly", "fresh thyme",
            "trader joe", "whole foods", "kowalski",
        ],
    },
    "Convenience Store": {
        "income_sweet_spot": (25_000, 90_000),
        "min_population":      5_000,
        "brand_weight":           30,
        "capex_usd":            800_000,
        "capex_multiplier":      1.3,
        "operating_margin":      0.06,
        "min_parcel_acres":      0.25,
        "category_share":        0.022,
        "rival_keywords": [
            "convenience", "7-eleven", "holiday", "speedway", "kwik",
            "casey", "circle k", "bp", "shell", "mobil",
        ],
    },
    "Coffee Shop": {
        "income_sweet_spot": (50_000, 200_000),
        "min_population":      4_000,
        "brand_weight":           25,
        "capex_usd":            400_000,
        "capex_multiplier":      1.3,
        "operating_margin":      0.10,
        "min_parcel_acres":      0.15,
        "category_share":        0.012,
        "rival_keywords": ["coffee", "starbucks", "caribou", "dunkin", "peet", "espresso", "cafe", "café"],
    },
}

# Weights for the deterministic composite (location-level, blends into
# Yash-merge's 8-dim engine via `blended_total_score` in scoring_engine).
COMPOSITE_WEIGHTS = {
    "demand":       0.30,
    "competition":  0.25,
    "huff":         0.20,
    "traffic":      0.15,
    "income_fit":   0.10,
}


# ── Brand alias → format ────────────────────────────────────────────────────
_BRAND_ALIASES: Dict[str, str] = {
    "walmart":          "Walmart",
    "target":           "Target",
    "costco":           "Costco",
    "sam's club":       "Costco",
    "sams club":        "Costco",
    "bj's wholesale":   "Costco",
    "home depot":       "Home Depot",
    "lowe's":           "Home Depot",
    "lowes":            "Home Depot",
    "menards":          "Home Depot",
    "best buy":         "Best Buy",
    "walgreens":        "Walgreens",
    "cvs":              "Walgreens",
    "whole foods":      "Whole Foods",
    "sprouts":          "Whole Foods",
    "fresh thyme":      "Whole Foods",
    "trader joe's":     "Trader Joe's",
    "trader joes":      "Trader Joe's",
    "aldi":             "Aldi",
    "lidl":             "Aldi",
    "save-a-lot":       "Aldi",
    "starbucks":        "Starbucks",
    "caribou":          "Coffee Shop",
    "dunkin":           "Coffee Shop",
    "7-eleven":         "Convenience Store",
    "circle k":         "Convenience Store",
    "casey's":          "Convenience Store",
    "kwik trip":        "Convenience Store",
    "cub foods":        "Local Grocery",
    "hy-vee":           "Local Grocery",
    "kroger":           "Local Grocery",
    "meijer":           "Walmart",
    "dollar general":   "Aldi",
    "dollar tree":      "Aldi",
    "tj maxx":          "Target",
    "nordstrom rack":   "Target",
    "h-mart":           "Whole Foods",
}


def resolve_store_format(display_name: str | None) -> str:
    """Map any brand/profile display name to the closest known format key.
    Falls back to 'Target' (generic mid-range big-box) for unknown brands.
    """
    if not display_name:
        return "Target"
    key = display_name.lower().strip()
    if key in _BRAND_ALIASES:
        return _BRAND_ALIASES[key]
    # Substring scan — e.g. "Walmart Supercenter" → Walmart
    for alias, fmt in _BRAND_ALIASES.items():
        if alias in key:
            return fmt
    # Custom-store display names contain a category hint we can use:
    if "grocery" in key:    return "Local Grocery"
    if "coffee"  in key:    return "Coffee Shop"
    if "conveni" in key:    return "Convenience Store"
    if "pharmac" in key:    return "Walgreens"
    if "hardware" in key or "home goods" in key: return "Home Depot"
    if "electron" in key:   return "Best Buy"
    if "premium"  in key:   return "Whole Foods"
    return "Target"


def get_format(display_name: str | None) -> Dict[str, Any]:
    return STORE_FORMATS[resolve_store_format(display_name)]


# ── Shared math helpers ────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def spending_index(poverty_rate: float | None) -> float:
    if poverty_rate is None:
        return 0.30
    return max(0.15, 0.35 - (poverty_rate * 0.40))


def normalize(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    pct = (value - low) / (high - low)
    return max(0.0, min(100.0, pct * 100))


def income_fit_score(income: float, store_format: str) -> float:
    """0–100 score for how well a median income matches the format's sweet spot."""
    fmt = STORE_FORMATS.get(store_format, STORE_FORMATS["Target"])
    low, high = fmt["income_sweet_spot"]
    if income <= 0:
        return 0.0
    if income < low * 0.5 or income > high * 1.5:
        return 0.0
    if low <= income <= high:
        midpoint = (low + high) / 2
        return 100 * (1 - (abs(income - midpoint) / ((high - low) / 2)) * 0.3)
    if income < low:
        return 70 * (income / low)
    return max(0.0, 70 * (1 - ((income - high) / high)))


def is_rival(competitor_name: str, store_format: str) -> bool:
    fmt = STORE_FORMATS.get(store_format, STORE_FORMATS["Target"])
    kws = fmt.get("rival_keywords", [])
    name_low = (competitor_name or "").lower()
    return any(kw in name_low for kw in kws)
