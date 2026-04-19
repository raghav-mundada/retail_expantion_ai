"""
Scoring engine for retail location feasibility.

Computes 9 industry-standard metrics from Supabase data + a composite
weighted score. All metrics are deterministic Python math — no LLM
involvement. The agents read these numbers and argue about them.

Metrics computed:
  1. Trade Area Population (TAP)               — total households in catchment
  2. Effective Buying Power (EBP)              — income-weighted spending power
  3. Demand Density                            — EBP per square km
  4. Huff Capture Rate                         — gravity-based market share
  5. Sales Forecast                            — annual revenue estimate
  6. Traffic Score                             — AADT-based accessibility
  7. Competition Density                       — competitors per square km
  8. Competitive Pressure                      — distance-weighted threat
  9. ROI / Payback Period                      — using industry CapEx averages

Composite score: weighted blend of normalized sub-scores (0–100).
Weights are format-specific (Target vs Whole Foods vs Walgreens, etc.)
"""

import math
from typing import Any

from backend.db.client import get_client


# ─────────────────────────────────────────────────────────────────────────────
# Store format profiles — each format has different demographic preferences,
# CapEx, and brand attractiveness in the Huff model.
# ─────────────────────────────────────────────────────────────────────────────

STORE_FORMATS: dict[str, dict[str, Any]] = {
    "Target": {
        "income_sweet_spot" : (55_000, 110_000),  # min, max income band
        "min_population"    : 40_000,             # below this = thin market
        "brand_weight"      : 100,                # Huff attractiveness
        "capex_usd"         : 15_000_000,         # build cost
        "capex_multiplier"  : 1.8,                # build → all-in (land + WC + inventory)
        "operating_margin"  : 0.05,               # 5% net margin
        "min_parcel_acres"  : 8.0,
        # % of household disposable income spent in this store category
        # (general merchandise / big box) — BLS Consumer Expenditure Survey
        "category_share"    : 0.045,
        "rival_keywords"    : [
            "target", "walmart", "costco", "sam's club", "kohl",
            "macy", "jcpenney", "meijer", "fred meyer",
            "hy-vee", "cub", "menards", "home depot", "lowe", "best buy",
            "ikea", "fleet farm", "homegoods", "tjmaxx", "marshall",
        ],
        "rival_categories"  : [
            "supermarket", "department_store", "discount_store",
            "hypermarket", "general", "wholesale", "warehouse_club",
        ],
    },
    "Walmart": {
        "income_sweet_spot" : (35_000, 90_000),   # broader, lower band than Target
        "min_population"    : 40_000,
        "brand_weight"      : 110,                # largest pull of any US retailer
        "capex_usd"         : 25_000_000,         # supercenter build
        "capex_multiplier"  : 1.8,
        "operating_margin"  : 0.026,              # razor-thin but volume-driven
        "min_parcel_acres"  : 12.0,
        "category_share"    : 0.055,              # GM + grocery combined
        "rival_keywords"    : [
            "walmart", "target", "costco", "sam's club", "bj",
            "meijer", "fred meyer", "kmart", "hy-vee", "cub",
            "menards", "home depot",
        ],
        "rival_categories"  : [
            "supermarket", "department_store", "discount_store",
            "hypermarket", "warehouse_club", "general",
        ],
    },
    "Costco": {
        "income_sweet_spot" : (70_000, 180_000),  # higher-income members
        "min_population"    : 60_000,             # needs a big catchment
        "brand_weight"      : 120,                # strongest membership pull
        "capex_usd"         : 30_000_000,
        "capex_multiplier"  : 1.7,
        "operating_margin"  : 0.026,              # thin on goods; profit is membership
        "min_parcel_acres"  : 15.0,
        "category_share"    : 0.060,
        "rival_keywords"    : [
            "costco", "sam's club", "bj", "walmart", "target",
        ],
        "rival_categories"  : [
            "warehouse_club", "hypermarket", "department_store",
        ],
    },
    "Home Depot": {
        "income_sweet_spot" : (45_000, 140_000),  # homeowners skew
        "min_population"    : 25_000,
        "brand_weight"      : 90,
        "capex_usd"         : 14_000_000,
        "capex_multiplier"  : 1.6,
        "operating_margin"  : 0.10,               # actual HD net margin ≈ 10%
        "min_parcel_acres"  : 10.0,
        "category_share"    : 0.030,              # DIY / home-improvement share
        "rival_keywords"    : [
            "home depot", "lowe", "menards", "ace hardware", "true value",
            "harbor freight",
        ],
        "rival_categories"  : [
            "doityourself", "hardware", "home_improvement", "garden_center",
        ],
    },
    "Best Buy": {
        "income_sweet_spot" : (50_000, 150_000),
        "min_population"    : 20_000,
        "brand_weight"      : 65,
        "capex_usd"         : 5_000_000,
        "capex_multiplier"  : 1.5,
        "operating_margin"  : 0.04,
        "min_parcel_acres"  : 3.0,
        "category_share"    : 0.020,              # electronics HH-spend share
        "rival_keywords"    : [
            "best buy", "microcenter", "apple store", "target",
            "walmart", "costco",
        ],
        "rival_categories"  : [
            "electronics", "computer", "mobile_phone", "department_store",
        ],
    },
    "Walgreens": {
        "income_sweet_spot" : (35_000, 80_000),
        "min_population"    : 15_000,
        "brand_weight"      : 60,
        "capex_usd"         : 4_000_000,
        "operating_margin"  : 0.04,
        "min_parcel_acres"  : 1.0,
        "category_share"    : 0.018,  # drug/pharmacy share of income
        "rival_keywords"    : [
            "walgreens", "cvs", "rite aid", "duane reade", "pharmacy",
        ],
        "rival_categories"  : ["pharmacy", "chemist", "drugstore"],
    },
    "CVS": {
        "income_sweet_spot" : (35_000, 85_000),
        "min_population"    : 15_000,
        "brand_weight"      : 60,
        "capex_usd"         : 4_000_000,
        "operating_margin"  : 0.04,
        "min_parcel_acres"  : 1.0,
        "category_share"    : 0.018,
        "rival_keywords"    : [
            "cvs", "walgreens", "rite aid", "duane reade", "pharmacy",
        ],
        "rival_categories"  : ["pharmacy", "chemist", "drugstore"],
    },
    "Whole Foods": {
        "income_sweet_spot" : (85_000, 200_000),
        "min_population"    : 30_000,
        "brand_weight"      : 80,
        "capex_usd"         : 12_000_000,
        "capex_multiplier"  : 1.7,
        "operating_margin"  : 0.04,
        "min_parcel_acres"  : 3.0,
        "category_share"    : 0.085,  # premium grocery share
        "rival_keywords"    : [
            "whole foods", "trader joe", "lunds", "byerly", "fresh thyme",
            "sprouts", "kowalski", "fresh market",
        ],
        "rival_categories"  : ["supermarket", "organic", "health_food", "gourmet"],
    },
    "Trader Joe's": {
        "income_sweet_spot" : (75_000, 180_000),
        "min_population"    : 25_000,
        "brand_weight"      : 70,
        "capex_usd"         : 6_000_000,
        "operating_margin"  : 0.05,
        "min_parcel_acres"  : 2.0,
        "category_share"    : 0.065,
        "rival_keywords"    : [
            "trader joe", "whole foods", "lunds", "byerly", "aldi",
            "fresh thyme", "sprouts",
        ],
        "rival_categories"  : ["supermarket", "organic", "health_food"],
    },
    "Aldi": {
        "income_sweet_spot" : (30_000, 85_000),   # value-seeking shoppers
        "min_population"    : 15_000,
        "brand_weight"      : 50,
        "capex_usd"         : 3_000_000,
        "capex_multiplier"  : 1.5,
        "operating_margin"  : 0.045,
        "min_parcel_acres"  : 1.5,
        "category_share"    : 0.042,
        "rival_keywords"    : [
            "aldi", "lidl", "cub", "rainbow", "save-a-lot",
            "winco", "food 4 less", "hy-vee", "walmart",
        ],
        "rival_categories"  : ["supermarket", "discount_store"],
    },
    "Starbucks": {
        "income_sweet_spot" : (55_000, 220_000),  # skews higher than generic cafe
        "min_population"    : 5_000,
        "brand_weight"      : 55,
        "capex_usd"         : 700_000,
        "operating_margin"  : 0.14,               # stronger unit economics than indie
        "min_parcel_acres"  : 0.15,
        "category_share"    : 0.014,
        "rival_keywords"    : [
            "starbucks", "caribou", "dunkin", "peet", "dutch bros",
            "coffee bean", "tim hortons",
        ],
        "rival_categories"  : ["coffee", "cafe", "tea"],
    },
    # ── Small / independent formats — for the local-business operator ──
    "Local Grocery": {
        "income_sweet_spot" : (40_000, 110_000),  # serves a wider band
        "min_population"    : 8_000,              # neighborhood-scale market
        "brand_weight"      : 35,                 # weak brand pull vs chains
        "capex_usd"         : 1_500_000,          # leasehold buildout
        "operating_margin"  : 0.03,               # razor-thin grocery margin
        "min_parcel_acres"  : 0.5,
        "category_share"    : 0.040,              # ~4% of HH spend on grocery
        "rival_keywords"    : [
            "grocery", "market", "foods", "supermercado", "deli",
            "aldi", "cub foods", "lunds", "byerly", "fresh thyme",
            "trader joe", "whole foods", "kowalski",
        ],
        "rival_categories"  : [
            "supermarket", "convenience", "organic", "deli", "butcher",
            "greengrocer", "grocery",
        ],
    },
    "Convenience Store": {
        "income_sweet_spot" : (25_000, 90_000),
        "min_population"    : 5_000,
        "brand_weight"      : 30,
        "capex_usd"         : 800_000,
        "operating_margin"  : 0.06,               # higher margin per dollar
        "min_parcel_acres"  : 0.25,
        "category_share"    : 0.022,
        "rival_keywords"    : [
            "convenience", "7-eleven", "holiday", "speedway", "kwik",
            "casey", "circle k", "bp", "shell", "mobil",
        ],
        "rival_categories"  : ["convenience", "gas", "fuel"],
    },
    "Coffee Shop": {
        "income_sweet_spot" : (50_000, 200_000),
        "min_population"    : 4_000,
        "brand_weight"      : 25,
        "capex_usd"         : 400_000,
        "operating_margin"  : 0.10,
        "min_parcel_acres"  : 0.15,
        "category_share"    : 0.012,              # food-away-from-home slice
        "rival_keywords"    : [
            "coffee", "starbucks", "caribou", "dunkin", "peet",
            "espresso", "cafe", "café",
        ],
        "rival_categories"  : ["coffee", "cafe", "tea"],
    },
}


# Composite weights per dimension — what matters most for the verdict.
# These are the weights that get multiplied with each metric's 0-100 score.
COMPOSITE_WEIGHTS = {
    "demand"      : 0.30,   # TAP, EBP, demand density
    "competition" : 0.25,   # density + pressure
    "huff"        : 0.20,   # market capture %
    "traffic"     : 0.15,   # AADT
    "income_fit"  : 0.10,   # how well median income matches the format
}


# Formula documentation — exposed to the frontend for the methodology panel
FORMULA_DOCS = [
    {
        "id"      : "demand",
        "name"    : "Demand Score",
        "formula" : "0.40·TAP_score + 0.35·EBP/HH_score + 0.25·Density_score",
        "purpose" : "Three-signal blend so a $5B metro and a $500M neighborhood score differently. TAP & Density use saturating curves (target 25k HH and $50M/km²); EBP/HH normalizes purchasing power on a $25k–$95k band.",
    },
    {
        "id"      : "tap",
        "name"    : "Trade Area Population (TAP)",
        "formula" : "TAP = Σ households across all tracts in radius\nTAP_score = 100 · (1 − e^(−TAP/25,000))",
        "purpose" : "Total potential customer base. Saturating curve: 25k HH ≈ one big-box trade area. Past 25k still differentiates instead of clamping at 100.",
    },
    {
        "id"      : "ebp",
        "name"    : "Effective Buying Power (EBP)",
        "formula" : "EBP = Σ (households × median_income × spending_index)\nEBP/HH_score = normalize(EBP/TAP, $12k, $45k)",
        "purpose" : "Total annual retail dollars in the catchment. Spending index = 0.35 − (poverty_rate × 0.4). Per-HH normalization removes radius bias.",
    },
    {
        "id"      : "density",
        "name"    : "Demand Density",
        "formula" : "Density = EBP / (π·radius²)\nDensity_score = 100 · (1 − e^(−Density/$50M))",
        "purpose" : "Distinguishes urban from suburban from rural even when total EBP is similar. Loring Park hits this; the suburbs don't.",
    },
    {
        "id"      : "huff",
        "name"    : "Huff Gravity Model",
        "formula" : (
            "rivals = filter(competitors by keyword OR Geoapify category)\n"
            "P_ij = (S_j / D_ij²) ÷ Σ_k (S_k / D_ik²)\n"
            "score = normalize(capture %, 2%, 25%)"
        ),
        "purpose" : "Probability customers from tract i visit our store j vs each rival k. β = 2 industry standard. Tract→rival distance uses orthogonal combine √(tract_dist² + rival_dist²) with a 0.3km floor on both legs. Rivals matched via name OR category — falls back to all competitors at half-weight if neither matches. Saturation at 25% reflects realistic urban Huff capture.",
    },
    {
        "id"      : "sales",
        "name"    : "Sales Forecast",
        "formula" : (
            "Revenue = captured_HH × HH-weighted(median_income) × HH-weighted(spending_index) × category_share\n"
            "spending_index = 0.35 − 0.4·poverty_rate (per tract, then HH-weighted)"
        ),
        "purpose" : "Spending index is now poverty-adjusted per tract (range 0.15–0.35) and HH-weighted, not a flat 0.30. Income is also HH-weighted across tracts. Category_share is format-specific (Target 4.5%, Whole Foods 8.5%, Walgreens 1.8%, Coffee 1.2%).",
    },
    {
        "id"      : "traffic",
        "name"    : "Traffic Score",
        "formula" : (
            "score = 0.40·normalize(max_AADT_in_radius, 10K, 60K)\n"
            "      + 0.35·normalize(avg_AADT,            5K, 25K)\n"
            "      + 0.25·normalize(max(nearest, avg),   5K, 30K)"
        ),
        "purpose" : "Three-signal AADT (Annual Avg Daily Traffic) blend. max_in_radius captures freeway proximity; avg captures corridor strength; frontage uses max(nearest,avg) so a side-street directly adjacent doesn't drag the score. Calibrated for arterials (25–30K = strong), not freeways (60K = premium).",
    },
    {
        "id"      : "competition",
        "name"    : "Competitive Pressure",
        "formula" : (
            "direct_rivals = filter(competitors, format.rival_keywords)\n"
            "pressure      = Σ (rival_brand_weight / dist²)\n"
            "score = 0.7·(100 − normalize(pressure, 50, 2000)) + 0.3·(100 − normalize(rival_count, 0, 8))"
        ),
        "purpose" : "Format-aware: only counts actual rivals (Target vs other big-boxes, not delis). Distance + brand weighted — closer + bigger rivals are exponentially worse. Pressure carries 70% weight; raw count is the tie-breaker.",
    },
    {
        "id"      : "income_fit",
        "name"    : "Income Fit",
        "formula" : (
            "For each tract: triangular_fit(median_income_t, sweet_spot)\n"
            "score = Σ(score_t × hh_t) / Σ(hh_t)"
        ),
        "purpose" : "Household-weighted aggregation of per-tract triangular fits. Captures heterogeneity: a $40K + $120K mix is correctly scored as TWO bad fits, not one good $80K average. Sweet spots: Target $55K–$110K, Whole Foods $85K–$200K, Coffee Shop $50K–$200K.",
    },
    {
        "id"      : "roi",
        "name"    : "Return on Investment",
        "formula" : (
            "All-in CapEx = build_capex × capex_multiplier (default 1.5×)\n"
            "Annual Profit = Revenue × operating_margin\n"
            "Payback = All-in CapEx ÷ Annual Profit"
        ),
        "purpose" : "Build cost alone undercounts total invested capital. Multiplier covers land/lease + working capital + opening inventory. Format-specific build CapEx (Target $15M, Whole Foods $12M, Walgreens $4M, Coffee $400K) and margin (3–10%).",
    },
    {
        "id"      : "composite",
        "name"    : "Composite Feasibility Score",
        "formula" : "Score = 0.30·Demand + 0.25·Competition + 0.20·Huff + 0.15·Traffic + 0.10·IncomeFit",
        "purpose" : "Final 0–100 score blending all five dimensions.",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Helper: distance + spending index proxy
# ─────────────────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _spending_index(poverty_rate: float | None) -> float:
    """
    Proxy for the BLS spending index — fraction of income that flows to retail.
    Lower poverty = higher discretionary spending.
    """
    if poverty_rate is None:
        return 0.30  # default: 30% of income to retail
    # Maps poverty rate 0.0 → 0.35 (high spend) and 0.50 → 0.15 (suppressed)
    return max(0.15, 0.35 - (poverty_rate * 0.40))


def _normalize(value: float, low: float, high: float) -> float:
    """Clamp + normalize a value into a 0–100 score."""
    if high <= low:
        return 0.0
    pct = (value - low) / (high - low)
    return max(0.0, min(100.0, pct * 100))


def _saturate(value: float, target: float) -> float:
    """
    Saturating 0-100 score: 0 at value=0, ~63 at value=target, asymptotes to 100.
    Use when a signal has no real ceiling but you still want diminishing returns
    (e.g. trade-area population — 10× more HHs is not 10× more demand).
    """
    if value <= 0 or target <= 0:
        return 0.0
    return 100.0 * (1.0 - math.exp(-value / target))


# ─────────────────────────────────────────────────────────────────────────────
# Metric 1+2+3 — TAP, EBP, Demand Density
# ─────────────────────────────────────────────────────────────────────────────

def compute_demand(tracts: list[dict], radius_km: float) -> dict:
    """
    Three-signal demand score — fixes the old "absolute EBP" formulation that
    saturated to 100 for any urban radius.

      • TAP score (40%)          → saturating curve on households (target 25k)
      • EBP-per-HH score (35%)   → linear normalize on $25k–$95k purchasing power
      • Density score (25%)      → saturating curve on EBP/km² (target $50M/km²)

    Why this matters:
      1. EBP alone makes a $5B 10km-Minneapolis catchment indistinguishable from
         a $500M neighborhood — both clamp at 100. The blend separates them.
      2. EBP-per-HH adds purchasing power per customer, decoupled from radius.
      3. Density captures the urban/suburban/rural axis the other two miss.
      4. Saturating curves keep separating signal past the target instead of
         hard-clamping at 100, so a dense Manhattan block and a Kansas suburb
         can still score differently.
    """
    if not tracts:
        return {
            "tap"           : 0,
            "ebp"           : 0,
            "ebp_per_hh"    : 0,
            "demand_density": 0,
            "score"         : 0,
            "subscores"     : {"tap": 0, "ebp_per_hh": 0, "density": 0},
        }

    tap = sum((t.get("total_households") or 0) for t in tracts)

    ebp = 0.0
    for t in tracts:
        hh     = t.get("total_households") or 0
        income = t.get("median_hh_income") or 0
        spend  = _spending_index(t.get("poverty_rate"))
        ebp   += hh * income * spend

    area_km2       = math.pi * (radius_km ** 2) if radius_km > 0 else 1
    demand_density = ebp / area_km2 if area_km2 > 0 else 0
    ebp_per_hh     = (ebp / tap) if tap else 0

    # Sub-scores
    tap_score        = _saturate(tap, 25_000)                       # 25k HH ≈ one big-box trade area
    ebp_per_hh_score = _normalize(ebp_per_hh, 12_000, 45_000)       # retail $/HH (post-spending-index)
    density_score    = _saturate(demand_density, 50_000_000)        # $50M/km² = solid urban density

    score = 0.40 * tap_score + 0.35 * ebp_per_hh_score + 0.25 * density_score

    return {
        "tap"           : tap,
        "ebp"           : round(ebp, 2),
        "ebp_per_hh"    : round(ebp_per_hh, 2),
        "demand_density": round(demand_density, 2),
        "score"         : round(score, 1),
        "subscores"     : {
            "tap"       : round(tap_score, 1),
            "ebp_per_hh": round(ebp_per_hh_score, 1),
            "density"   : round(density_score, 1),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Metric 4 — Huff Gravity Model (Market Capture %)
# ─────────────────────────────────────────────────────────────────────────────

def _filter_rivals(
    competitors: list[dict],
    store_format: str,
) -> tuple[list[dict], float]:
    """
    Keep only competitors that are actual direct rivals to the proposed format.

    Matches a competitor as a rival if EITHER signal hits:
      • Name keyword match (e.g. "Walmart" for Target)
      • Geoapify category match (e.g. shop_type == "supermarket" for Local Grocery)

    The keyword list alone was too brittle — it dropped 69 of 71 Minneapolis
    big-boxes for Target because Hy-Vee, Menards, Best Buy, etc. weren't on
    the hardcoded list. Adding category match catches what the keywords miss.

    Safety fallback: if NO rivals match but there ARE competitors, return all
    of them with a 0.5× brand-weight multiplier. This prevents Huff from
    dividing by "us only" and inflating the capture rate to absurd numbers.

    Returns (rivals, brand_weight_multiplier). Multiplier is 1.0 normally,
    0.5 when fallback is used.
    """
    fmt = STORE_FORMATS.get(store_format, STORE_FORMATS["Target"])
    keywords   = [k.lower() for k in fmt.get("rival_keywords", [])]
    categories = [c.lower() for c in fmt.get("rival_categories", [])]

    if not keywords and not categories:
        return competitors, 1.0

    rivals = []
    for c in competitors:
        name      = (c.get("name") or "").lower()
        shop_type = (c.get("shop_type") or "").lower()

        kw_hit  = any(kw in name for kw in keywords) if keywords else False
        cat_hit = any(cat in shop_type for cat in categories) if (categories and shop_type) else False

        if kw_hit or cat_hit:
            rivals.append(c)

    if rivals:
        return rivals, 1.0

    # Fallback: nothing matched but there ARE competitors. Treat them as
    # "soft" rivals at half brand weight so Huff doesn't divide by us alone.
    if competitors:
        return competitors, 0.5

    return [], 1.0


def compute_huff(
    center_lat: float,
    center_lon: float,
    tracts: list[dict],
    competitors: list[dict],
    store_format: str,
) -> dict:
    """
    Huff Gravity Model — for each tract, compute the probability that customers
    from that tract visit the candidate store vs each direct rival. Aggregate to
    a total market capture %.

        P_ij = (S_j / D_ij^β) / Σ_k (S_k / D_ik^β)

    Implementation notes:
      • β = 2 (industry standard for retail).
      • Only DIRECT rivals are counted (Target vs Walmart, not Target vs deli).
      • Tract→rival distance is approximated as the Euclidean diagonal:
            sqrt(tract_dist² + rival_dist²)
        This represents the average expected distance assuming tract and rival
        sit at random bearings from the center — much more accurate than the
        radial-difference approach which biased toward best-case for the rival.
    """
    fmt = STORE_FORMATS.get(store_format, STORE_FORMATS["Target"])
    candidate_attractiveness = fmt["brand_weight"]
    BETA = 2.0
    MIN_DIST_KM = 0.3  # half-mile floor — nothing meaningful inside that

    rivals, brand_multiplier = _filter_rivals(competitors, store_format)

    captured_households = 0
    total_households    = 0

    for t in tracts:
        hh         = t.get("total_households") or 0
        tract_dist = max(t.get("dist_km") or MIN_DIST_KM, MIN_DIST_KM)
        attractiveness_us = candidate_attractiveness / (tract_dist ** BETA)

        attractiveness_rivals = 0.0
        for c in rivals:
            # Floor BOTH legs before the orthogonal combine. Old code only
            # floored the diagonal, so a rival sitting on top of us
            # (comp_dist ≈ 0) collapsed to just tract_dist — under-penalizing.
            comp_dist = max(c.get("dist_km") or MIN_DIST_KM, MIN_DIST_KM)
            d_tract_to_comp = max(
                math.sqrt(tract_dist ** 2 + comp_dist ** 2),
                MIN_DIST_KM,
            )
            comp_brand = _competitor_brand_weight(c.get("name", "")) * brand_multiplier
            attractiveness_rivals += comp_brand / (d_tract_to_comp ** BETA)

        denominator = attractiveness_us + attractiveness_rivals
        if denominator <= 0:
            continue

        prob_to_us = attractiveness_us / denominator
        captured_households += hh * prob_to_us
        total_households    += hh

    capture_rate_pct = (captured_households / total_households * 100) if total_households else 0
    # Recalibrated: 2% = floor, 25% = dominant. Real urban Huff rarely > 25%.
    # Old (5, 40) saturated at any moderate share and pinned at 100/100.
    score = _normalize(capture_rate_pct, 2, 25)

    return {
        "captured_households": round(captured_households),
        "total_households"   : total_households,
        "capture_rate_pct"   : round(capture_rate_pct, 2),
        "rivals_considered"  : len(rivals),
        "rivals_total"       : len(competitors),
        "rival_match_mode"   : "matched" if brand_multiplier == 1.0 else "fallback (0.5× weight)",
        "score"              : round(score, 1),
    }


_BRAND_WEIGHTS = [
    # Tier 1 — national big-box destinations (90-100)
    (100, ("walmart", "target", "costco", "sam's club", "ikea")),
    # Tier 2 — strong regional/national chains (75-90)
    (85,  ("home depot", "lowe", "menards", "best buy", "fleet farm",
           "kohl", "macy", "jcpenney", "meijer", "fred meyer",
           "whole foods", "wegmans", "publix", "h-e-b")),
    # Tier 3 — established mid-market (60-75)
    (70,  ("trader joe", "hy-vee", "lunds", "byerly", "kowalski",
           "fresh thyme", "sprouts", "fresh market", "marshall",
           "tjmaxx", "homegoods", "ross", "burlington")),
    # Tier 4 — discount / value chains (50-60)
    (55,  ("aldi", "cub", "supervalu", "dollar general", "dollar tree",
           "five below", "ollie")),
    # Tier 5 — pharmacies / specialty (40-50)
    (45,  ("walgreens", "cvs", "rite aid", "duane reade")),
    # Tier 6 — convenience / cafes (25-40)
    (30,  ("7-eleven", "holiday", "speedway", "kwik trip", "casey",
           "circle k", "starbucks", "caribou", "dunkin", "peet")),
]


def _competitor_brand_weight(name: str) -> float:
    """
    Tiered brand attractiveness for the Huff/competition models.

    Old version only knew 5 brands and gave everything else a default of 40 —
    that under-weighted real competitors (Costco, Menards, Best Buy, IKEA…)
    and inflated capture rates for Target by 50%+ in mixed urban catchments.
    """
    name_lower = (name or "").lower()
    for weight, brands in _BRAND_WEIGHTS:
        if any(b in name_lower for b in brands):
            return weight
    return 35  # default — unknown independent


# ─────────────────────────────────────────────────────────────────────────────
# Metric 5 — Sales Forecast
# ─────────────────────────────────────────────────────────────────────────────

def compute_sales_forecast(
    huff: dict,
    tracts: list[dict],
    store_format: str,
    fallback_median_income: float = 0,
) -> dict:
    """
    Industry-correct revenue formula:

        Revenue = captured_HH × median_income × spending_index × category_share

    Where:
      • captured_HH      : households likely to shop here (from Huff model)
      • median_income    : household-weighted across tracts
      • spending_index   : poverty-adjusted (0.15–0.35 per tract, weighted)
      • category_share   : % of retail spend in THIS category
                           (Target 4.5%, Walgreens 1.8%, Whole Foods 8.5%)

    Old version hardcoded spending_index = 0.30, ignoring poverty entirely.
    Now derived per-tract from _spending_index(poverty_rate) and HH-weighted —
    a low-income catchment correctly forecasts ~15-20% lower revenue than
    spreadsheet 0.30 would suggest.

    A typical Target captures ~25k HH × ~$3.9k/HH/yr → ~$95M/store.
    Real Target average: $50–80M; our model lands in that ballpark.
    """
    fmt         = STORE_FORMATS.get(store_format, STORE_FORMATS["Target"])
    cat_share   = fmt["category_share"]
    captured_hh = huff["captured_households"]

    weight_total       = 0.0
    weighted_inc_sum   = 0.0
    weighted_spend_sum = 0.0
    for t in tracts or []:
        hh     = t.get("total_households") or 0
        income = t.get("median_hh_income") or 0
        if hh <= 0 or income <= 0:
            continue
        spend = _spending_index(t.get("poverty_rate"))
        weighted_inc_sum   += income * hh
        weighted_spend_sum += spend  * hh
        weight_total       += hh

    if weight_total > 0:
        median_income  = weighted_inc_sum   / weight_total
        spending_index = weighted_spend_sum / weight_total
    else:
        median_income  = fallback_median_income
        spending_index = _spending_index(None)  # 0.30 default

    revenue_per_hh = median_income * spending_index * cat_share
    annual_revenue = captured_hh * revenue_per_hh

    return {
        "annual_revenue_usd"   : round(annual_revenue, 2),
        "annual_revenue_m"     : round(annual_revenue / 1_000_000, 2),
        "revenue_per_household": round(revenue_per_hh, 2),
        "captured_households"  : captured_hh,
        "category_share_pct"   : round(cat_share * 100, 2),
        "spending_index"       : round(spending_index, 3),
        "median_income_used"   : round(median_income, 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Metric 6 — Traffic Score
# ─────────────────────────────────────────────────────────────────────────────

def compute_traffic(traffic_summary: dict | None) -> dict:
    """
    AADT (Annual Average Daily Traffic) — three-signal blend.

    Old version had two flaws:
      1. Saturation cap at 50K AADT was freeway-onramp territory. A normal
         suburban arterial next to a Target sits at 20-30K, so every site
         that wasn't a freeway scored < 30/100.
      2. Weighted "nearest_aadt" at 60% — but the *nearest* road is often a
         side street or feeder. If your Target sits 200m off I-394, the
         nearest road is the feeder (3K AADT) not the freeway (180K), and
         you score awful for what's actually a premium location.

    New scoring:
      • 40% on max_aadt_in_radius — is there a real freeway/arterial nearby?
      • 35% on avg_aadt — overall corridor strength
      • 25% on max(nearest, avg) — frontage signal but resilient to side-street trap

    Calibrations:
      • max_aadt:     normalize(10K, 60K)   — 60K = adjacent to a major freeway
      • avg_aadt:     normalize(5K, 25K)    — 25K = strong corridor average
      • frontage:     normalize(5K, 30K)    — 30K = strong arterial frontage
    """
    if not traffic_summary:
        return {
            "nearest_aadt": 0,
            "avg_aadt"    : 0,
            "max_aadt"    : 0,
            "score"       : 0,
            "subscores"   : {"max_in_radius": 0, "avg": 0, "frontage": 0},
        }

    nearest = traffic_summary.get("nearest_aadt") or 0
    avg     = traffic_summary.get("avg_aadt")     or 0
    peak    = traffic_summary.get("max_aadt")     or max(nearest, avg)

    frontage = max(nearest, avg)

    max_score      = _normalize(peak,     10_000, 60_000)
    avg_score      = _normalize(avg,       5_000, 25_000)
    frontage_score = _normalize(frontage,  5_000, 30_000)

    score = 0.40 * max_score + 0.35 * avg_score + 0.25 * frontage_score

    return {
        "nearest_aadt": nearest,
        "avg_aadt"    : avg,
        "max_aadt"    : peak,
        "score"       : round(score, 1),
        "subscores"   : {
            "max_in_radius": round(max_score, 1),
            "avg"          : round(avg_score, 1),
            "frontage"     : round(frontage_score, 1),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Metric 7+8 — Competition Density + Pressure
# ─────────────────────────────────────────────────────────────────────────────

def compute_competition(
    competitors: list[dict],
    radius_km: float,
    store_format: str = "Target",
) -> dict:
    """
    Format-aware competition scoring — fixes two flaws in the old version:

      1. Old score was 100 − normalize(count, 10, 200) — raw POI count, mixing
         delis, gas stations and dry cleaners with actual rivals. A Target site
         with 71 mixed POIs but only 2 real big-boxes would look saturated.
      2. The brand- and distance-weighted `pressure` value (the actually useful
         signal) was computed and then thrown away.

    New scoring:
      • Filter competitors by format-specific `rival_keywords` (same gate Huff
        uses). 71 mixed POIs collapses to maybe 3-8 real rivals.
      • pressure_score = 100 − normalize(pressure, 50, 2000)   — 70% weight
      • count_score    = 100 − normalize(direct_rivals, 0, 8)  — 30% weight
      • Final = 0.7·pressure_score + 0.3·count_score

    The rationale string surfaces direct-rival count, average distance, and
    pressure separately so users can see *why* the score is what it is.
    """
    direct_rivals, brand_multiplier = _filter_rivals(competitors, store_format)
    rival_count   = len(direct_rivals)
    total_count   = len(competitors)

    area_km2 = math.pi * (radius_km ** 2) if radius_km > 0 else 1
    density  = rival_count / area_km2 if area_km2 else 0

    pressure = 0.0
    BETA = 2.0
    MIN_DIST_KM = 0.1
    rival_dists = []
    for c in direct_rivals:
        d = max(c.get("dist_km") or MIN_DIST_KM, MIN_DIST_KM)
        brand = _competitor_brand_weight(c.get("name", "")) * brand_multiplier
        pressure += brand / (d ** BETA)
        rival_dists.append(d)

    avg_rival_dist_km     = (sum(rival_dists) / len(rival_dists)) if rival_dists else None
    nearest_rival         = direct_rivals[0] if direct_rivals else None
    nearest_rival_brand   = nearest_rival.get("name") if nearest_rival else None
    nearest_rival_dist_km = nearest_rival.get("dist_km") if nearest_rival else None

    pressure_score = 100 - _normalize(pressure, 50, 2000)
    count_score    = 100 - _normalize(rival_count, 0, 8)
    score          = 0.7 * pressure_score + 0.3 * count_score

    return {
        "count"                : rival_count,
        "total_poi_count"      : total_count,
        "density_per_km2"      : round(density, 3),
        "pressure"             : round(pressure, 2),
        "avg_rival_dist_km"    : round(avg_rival_dist_km, 2) if avg_rival_dist_km else None,
        "nearest_brand"        : nearest_rival_brand,
        "nearest_dist_km"      : nearest_rival_dist_km,
        "score"                : round(score, 1),
        "subscores"            : {
            "pressure": round(pressure_score, 1),
            "count"   : round(count_score, 1),
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Income fit — how well does the area's income match the store format?
# ─────────────────────────────────────────────────────────────────────────────

def _triangular_fit(income: float, low: float, high: float) -> float:
    """
    Per-tract triangular fit: 100 at sweet-spot midpoint, falls off symmetrically.

    Old version had a 0.3 dampener (floor at 70 inside the band) that flattered
    edge-of-band tracts. Bumped to 0.5 — a tract right at $110K is meaningfully
    worse than one at $82K for a Target site.
    """
    if income <= 0:
        return 0.0
    midpoint = (low + high) / 2

    if income < low * 0.5 or income > high * 1.5:
        return 0.0

    if low <= income <= high:
        dist     = abs(income - midpoint)
        max_dist = (high - low) / 2
        return 100.0 * (1 - (dist / max_dist) * 0.5)

    # Outside band but within tolerance — linear falloff
    if income < low:
        return 70.0 * (income / low)
    return max(0.0, 70.0 * (1 - ((income - high) / high)))


def compute_income_fit(
    tracts: list[dict],
    store_format: str,
    fallback_median: float = 0,
) -> dict:
    """
    Household-weighted income-fit score.

    Old version used a single area-wide median, which collapsed heterogeneity:
    one tract at $40K + one at $120K averaged to $80K and scored as a perfect
    fit for Target — but it's actually two bad fits, not one good one.

    New approach:
      • Score every tract individually with the triangular fit
      • Weighted average by household count (bigger tracts count more)
      • Surface dispersion: an area where ALL tracts score 70 is more
        confident than one with high spread
    """
    fmt = STORE_FORMATS.get(store_format, STORE_FORMATS["Target"])
    low, high = fmt["income_sweet_spot"]

    if not tracts:
        score = _triangular_fit(fallback_median, low, high)
        return {
            "median_income"  : round(fallback_median, 2),
            "sweet_spot"     : f"${low:,}–${high:,}",
            "score"          : round(score, 1),
            "tracts_scored"  : 0,
            "score_dispersion": 0,
            "method"         : "fallback (no tracts)",
        }

    weighted_sum = 0.0
    weight_total = 0.0
    weighted_inc = 0.0
    per_tract_scores = []

    for t in tracts:
        hh     = t.get("total_households") or 0
        income = t.get("median_hh_income") or 0
        if hh <= 0 or income <= 0:
            continue
        s = _triangular_fit(income, low, high)
        weighted_sum += s * hh
        weighted_inc += income * hh
        weight_total += hh
        per_tract_scores.append(s)

    if weight_total == 0:
        score = _triangular_fit(fallback_median, low, high)
        weighted_median = fallback_median
        dispersion = 0.0
    else:
        score           = weighted_sum / weight_total
        weighted_median = weighted_inc / weight_total
        # Population stddev of per-tract scores — captures heterogeneity
        mean = sum(per_tract_scores) / len(per_tract_scores)
        var  = sum((s - mean) ** 2 for s in per_tract_scores) / len(per_tract_scores)
        dispersion = math.sqrt(var)

    return {
        "median_income"   : round(weighted_median, 2),
        "sweet_spot"      : f"${low:,}–${high:,}",
        "score"           : round(score, 1),
        "tracts_scored"   : len(per_tract_scores),
        "score_dispersion": round(dispersion, 1),
        "method"          : "household-weighted tract aggregation",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Metric 9 — ROI / Payback (uses industry-average CapEx)
# ─────────────────────────────────────────────────────────────────────────────

def compute_roi(sales: dict, store_format: str) -> dict:
    """
    All-in CapEx = build cost × capex_multiplier.

    Old version used build cost only, which under-counted total invested
    capital by ~50%. Real all-in includes:
      • Build/leasehold improvements (the base capex_usd)
      • Land acquisition or upfront lease (often 30-50% of build)
      • Working capital + opening inventory (~20-30% of build)

    Default multiplier is 1.5×; can be overridden per-format.
    """
    fmt              = STORE_FORMATS.get(store_format, STORE_FORMATS["Target"])
    build_capex      = fmt["capex_usd"]
    capex_multiplier = fmt.get("capex_multiplier", 1.5)
    capex            = build_capex * capex_multiplier
    margin           = fmt["operating_margin"]
    annual_revenue   = sales["annual_revenue_usd"]

    annual_profit  = annual_revenue * margin
    payback_years  = (capex / annual_profit) if annual_profit > 0 else float("inf")
    roi_pct        = (annual_profit / capex * 100) if capex > 0 else 0

    return {
        "capex_usd"        : round(capex, 2),
        "build_capex_usd"  : build_capex,
        "capex_multiplier" : capex_multiplier,
        "annual_profit"    : round(annual_profit, 2),
        "roi_pct"          : round(roi_pct, 2),
        "payback_years"    : round(payback_years, 1) if payback_years != float("inf") else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Composite score — weighted blend of dimension scores
# ─────────────────────────────────────────────────────────────────────────────

def compute_composite(
    demand: dict,
    competition: dict,
    huff: dict,
    traffic: dict,
    income_fit: dict,
) -> dict:
    """
    Weighted blend → final 0-100 feasibility score.

    Returns both the total AND a per-dimension breakdown showing exactly how
    much each dimension contributed to the final score. This is what makes
    the system explainable.
    """
    contributions = [
        {
            "dimension"   : "Demand",
            "weight"      : COMPOSITE_WEIGHTS["demand"],
            "raw_score"   : demand["score"],
            "contribution": round(demand["score"] * COMPOSITE_WEIGHTS["demand"], 2),
            "rationale"   : (
                f"TAP {demand['tap']:,} HH ({demand['subscores']['tap']:.0f}/100) · "
                f"EBP/HH ${demand['ebp_per_hh']:,.0f} ({demand['subscores']['ebp_per_hh']:.0f}/100) · "
                f"Density ${demand['demand_density']/1e6:,.1f}M/km² ({demand['subscores']['density']:.0f}/100)"
            ),
        },
        {
            "dimension"   : "Competition",
            "weight"      : COMPOSITE_WEIGHTS["competition"],
            "raw_score"   : competition["score"],
            "contribution": round(competition["score"] * COMPOSITE_WEIGHTS["competition"], 2),
            "rationale"   : (
                f"{competition['count']} direct rivals"
                + (f" · avg {competition['avg_rival_dist_km']:.1f} km" if competition.get("avg_rival_dist_km") else "")
                + f" · pressure {competition['pressure']:,.0f} ({competition['subscores']['pressure']:.0f}/100)"
                + f" · count score {competition['subscores']['count']:.0f}/100"
                + f" · {competition['total_poi_count']} total POIs in radius"
            ),
        },
        {
            "dimension"   : "Huff Capture",
            "weight"      : COMPOSITE_WEIGHTS["huff"],
            "raw_score"   : huff["score"],
            "contribution": round(huff["score"] * COMPOSITE_WEIGHTS["huff"], 2),
            "rationale"   : (
                f"{huff['capture_rate_pct']:.1f}% market share vs "
                f"{huff['rivals_considered']}/{huff['rivals_total']} direct rivals "
                f"({huff['rival_match_mode']})"
            ),
        },
        {
            "dimension"   : "Traffic",
            "weight"      : COMPOSITE_WEIGHTS["traffic"],
            "raw_score"   : traffic["score"],
            "contribution": round(traffic["score"] * COMPOSITE_WEIGHTS["traffic"], 2),
            "rationale"   : (
                f"Peak {traffic['max_aadt']:,} AADT in radius ({traffic['subscores']['max_in_radius']:.0f}/100) · "
                f"avg {traffic['avg_aadt']:,.0f} ({traffic['subscores']['avg']:.0f}/100) · "
                f"frontage {max(traffic['nearest_aadt'], traffic['avg_aadt']):,.0f} ({traffic['subscores']['frontage']:.0f}/100)"
            ),
        },
        {
            "dimension"   : "Income Fit",
            "weight"      : COMPOSITE_WEIGHTS["income_fit"],
            "raw_score"   : income_fit["score"],
            "contribution": round(income_fit["score"] * COMPOSITE_WEIGHTS["income_fit"], 2),
            "rationale"   : (
                f"HH-weighted ${income_fit['median_income']:,.0f} vs target {income_fit['sweet_spot']}"
                + (f" · {income_fit['tracts_scored']} tracts, dispersion ±{income_fit['score_dispersion']:.0f}"
                   if income_fit.get('tracts_scored') else "")
            ),
        },
    ]
    total = round(sum(c["contribution"] for c in contributions), 1)
    return {
        "total"        : total,
        "contributions": contributions,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Top-level: pull data from Supabase and compute everything
# ─────────────────────────────────────────────────────────────────────────────

def compute_all_metrics(run_id: str, store_format: str = "Target") -> dict:
    """
    Pulls all run data from Supabase, computes every metric, and returns a
    structured object the agents can argue over.
    """
    db = get_client()

    # Parent run
    run = db.table("analysis_runs").select("*").eq("id", run_id).execute().data
    if not run:
        raise ValueError(f"Run {run_id} not found")
    run = run[0]

    # All child data
    demo_summary  = db.table("demographics_summaries").select("*").eq("run_id", run_id).execute().data
    tracts        = db.table("tract_snapshots").select("*").eq("run_id", run_id).execute().data
    competitors   = db.table("competitor_stores").select("*").eq("run_id", run_id).order("dist_km").execute().data
    traffic_data  = db.table("traffic_summaries").select("*").eq("run_id", run_id).execute().data

    median_income = (demo_summary[0].get("median_hh_income_avg") if demo_summary else 0) or 0
    traffic_row   = traffic_data[0] if traffic_data else None

    # Compute each metric
    demand      = compute_demand(tracts, run["radius_km"])
    huff        = compute_huff(run["lat"], run["lon"], tracts, competitors, store_format)
    sales       = compute_sales_forecast(huff, tracts, store_format, fallback_median_income=median_income)
    traffic     = compute_traffic(traffic_row)
    competition = compute_competition(competitors, run["radius_km"], store_format)
    income_fit  = compute_income_fit(tracts, store_format, fallback_median=median_income)
    roi         = compute_roi(sales, store_format)
    composite   = compute_composite(demand, competition, huff, traffic, income_fit)

    return {
        "run_id"         : run_id,
        "store_format"   : store_format,
        "center"         : {"lat": run["lat"], "lon": run["lon"], "radius_km": run["radius_km"]},
        "metrics": {
            "demand"      : demand,
            "huff"        : huff,
            "sales"       : sales,
            "traffic"     : traffic,
            "competition" : competition,
            "income_fit"  : income_fit,
            "roi"         : roi,
        },
        "composite_score": composite["total"],
        "score_breakdown": composite["contributions"],
        "weights"        : COMPOSITE_WEIGHTS,
        "formulas"       : FORMULA_DOCS,
    }
