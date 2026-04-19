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
        "operating_margin"  : 0.05,               # 5% net margin
        "min_parcel_acres"  : 8.0,
        # % of household disposable income spent in this store category
        # (general merchandise / big box) — BLS Consumer Expenditure Survey
        "category_share"    : 0.045,
        "rival_keywords"    : [
            "target", "walmart", "costco", "sam's club", "kohl",
            "macy", "jcpenney", "meijer", "fred meyer",
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
    },
    "Whole Foods": {
        "income_sweet_spot" : (85_000, 200_000),
        "min_population"    : 30_000,
        "brand_weight"      : 80,
        "capex_usd"         : 12_000_000,
        "operating_margin"  : 0.04,
        "min_parcel_acres"  : 3.0,
        "category_share"    : 0.085,  # premium grocery share
        "rival_keywords"    : [
            "whole foods", "trader joe", "lunds", "byerly", "fresh thyme",
            "sprouts", "kowalski", "fresh market",
        ],
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
        "id"      : "tap",
        "name"    : "Trade Area Population",
        "formula" : "TAP = Σ households across all tracts in radius",
        "purpose" : "Total potential customer base.",
    },
    {
        "id"      : "ebp",
        "name"    : "Effective Buying Power",
        "formula" : "EBP = Σ (households × median_income × spending_index)",
        "purpose" : "Total annual retail dollars in the catchment. Spending index = 0.35 − (poverty_rate × 0.4).",
    },
    {
        "id"      : "huff",
        "name"    : "Huff Gravity Model",
        "formula" : "P_ij = (S_j / D_ij²) ÷ Σ_k (S_k / D_ik²)",
        "purpose" : "Probability customers from tract i visit our store j vs each rival k. β = 2 industry standard. Tract→rival distance = √(tract_dist² + rival_dist²).",
    },
    {
        "id"      : "sales",
        "name"    : "Sales Forecast",
        "formula" : "Revenue = captured_HH × median_income × 0.30 × category_share",
        "purpose" : "30% of income flows to retail (BLS); category_share is format-specific (Target = 4.5%, Whole Foods = 8.5%, Walgreens = 1.8%).",
    },
    {
        "id"      : "traffic",
        "name"    : "Traffic Score",
        "formula" : "blend = 0.6 × nearest_AADT + 0.4 × avg_AADT, normalized 0–100",
        "purpose" : "AADT (Annual Average Daily Traffic) — visibility & accessibility. 50K+ AADT = premium location.",
    },
    {
        "id"      : "competition",
        "name"    : "Competitive Pressure",
        "formula" : "Pressure = Σ (rival_brand_weight / dist²)",
        "purpose" : "Distance-weighted threat from existing stores. Closer + bigger rivals = exponentially worse.",
    },
    {
        "id"      : "income_fit",
        "name"    : "Income Fit",
        "formula" : "Triangular fit of median_income against format sweet spot",
        "purpose" : "Target sweet spot = $55K–$110K. Whole Foods = $85K–$200K. Closer to midpoint = higher score.",
    },
    {
        "id"      : "roi",
        "name"    : "Return on Investment",
        "formula" : "Annual Profit = Revenue × operating_margin\nPayback = CapEx ÷ Annual Profit",
        "purpose" : "Format-specific CapEx (Target $15M, Walgreens $4M) and margin (4–5%).",
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


# ─────────────────────────────────────────────────────────────────────────────
# Metric 1+2+3 — TAP, EBP, Demand Density
# ─────────────────────────────────────────────────────────────────────────────

def compute_demand(tracts: list[dict], radius_km: float) -> dict:
    """
    TAP = Σ households                          → total households in catchment
    EBP = Σ households × income × spending_idx  → total annual retail spend
    Demand Density = EBP / area_km²
    """
    if not tracts:
        return {"tap": 0, "ebp": 0, "demand_density": 0, "score": 0}

    tap = sum((t.get("total_households") or 0) for t in tracts)

    ebp = 0.0
    for t in tracts:
        hh     = t.get("total_households") or 0
        income = t.get("median_hh_income") or 0
        spend  = _spending_index(t.get("poverty_rate"))
        ebp   += hh * income * spend

    area_km2       = math.pi * (radius_km ** 2)
    demand_density = ebp / area_km2 if area_km2 > 0 else 0

    # Normalize to a 0-100 score: $50M EBP = baseline, $500M = max
    score = _normalize(ebp, 50_000_000, 500_000_000)

    return {
        "tap"           : tap,
        "ebp"           : round(ebp, 2),
        "demand_density": round(demand_density, 2),
        "score"         : round(score, 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Metric 4 — Huff Gravity Model (Market Capture %)
# ─────────────────────────────────────────────────────────────────────────────

def _filter_rivals(competitors: list[dict], store_format: str) -> list[dict]:
    """
    Keep only competitors that are actual direct rivals to the proposed format.
    A Target doesn't really compete with a corner deli — only with other big
    boxes. This drastically reduces the noise in the Huff calculation.
    """
    fmt = STORE_FORMATS.get(store_format, STORE_FORMATS["Target"])
    keywords = fmt.get("rival_keywords", [])
    if not keywords:
        return competitors

    rivals = []
    for c in competitors:
        name = (c.get("name") or "").lower()
        if any(kw in name for kw in keywords):
            rivals.append(c)
    return rivals


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

    rivals = _filter_rivals(competitors, store_format)

    captured_households = 0
    total_households    = 0

    for t in tracts:
        hh         = t.get("total_households") or 0
        tract_dist = max(t.get("dist_km") or MIN_DIST_KM, MIN_DIST_KM)
        attractiveness_us = candidate_attractiveness / (tract_dist ** BETA)

        attractiveness_rivals = 0.0
        for c in rivals:
            comp_dist = c.get("dist_km") or 0
            d_tract_to_comp = max(
                math.sqrt(tract_dist ** 2 + comp_dist ** 2),
                MIN_DIST_KM,
            )
            comp_brand = _competitor_brand_weight(c.get("name", ""))
            attractiveness_rivals += comp_brand / (d_tract_to_comp ** BETA)

        denominator = attractiveness_us + attractiveness_rivals
        if denominator <= 0:
            continue

        prob_to_us = attractiveness_us / denominator
        captured_households += hh * prob_to_us
        total_households    += hh

    capture_rate_pct = (captured_households / total_households * 100) if total_households else 0
    score = _normalize(capture_rate_pct, 5, 40)  # 5% = poor, 40% = dominant

    return {
        "captured_households": round(captured_households),
        "total_households"   : total_households,
        "capture_rate_pct"   : round(capture_rate_pct, 2),
        "rivals_considered"  : len(rivals),
        "rivals_total"       : len(competitors),
        "score"              : round(score, 1),
    }


def _competitor_brand_weight(name: str) -> float:
    """Rough attractiveness for known brands. Anything unknown gets a default."""
    name_lower = (name or "").lower()
    if "walmart" in name_lower or "target" in name_lower:
        return 100
    if "whole foods" in name_lower:
        return 80
    if "trader joe" in name_lower:
        return 70
    if "lunds" in name_lower or "byerly" in name_lower:
        return 60
    if "aldi" in name_lower:
        return 55
    return 40  # default for unknown stores


# ─────────────────────────────────────────────────────────────────────────────
# Metric 5 — Sales Forecast
# ─────────────────────────────────────────────────────────────────────────────

def compute_sales_forecast(huff: dict, median_income: float, store_format: str) -> dict:
    """
    Industry-correct revenue formula:

        Revenue = captured_HH × median_income × spending_index × category_share

    Where:
      • captured_HH      : households likely to shop here (from Huff model)
      • median_income    : average household income in the area
      • spending_index   : ~30% of income flows to retail (BLS)
      • category_share   : % of retail spend in THIS specific category
                           (Target: 4.5%, Walgreens: 1.8%, Whole Foods: 8.5%)

    A typical Target captures ~25k households in its trade area, each
    spending ~$3.9k/yr on general merchandise → ~$95M/store. Real Target
    average is $50–80M, our model lands in that ballpark.
    """
    fmt = STORE_FORMATS.get(store_format, STORE_FORMATS["Target"])
    cat_share        = fmt["category_share"]
    spending_index   = 0.30  # ~30% of income to retail (BLS Consumer Expenditure)
    captured_hh      = huff["captured_households"]

    revenue_per_hh   = median_income * spending_index * cat_share
    annual_revenue   = captured_hh * revenue_per_hh

    return {
        "annual_revenue_usd"   : round(annual_revenue, 2),
        "annual_revenue_m"     : round(annual_revenue / 1_000_000, 2),
        "revenue_per_household": round(revenue_per_hh, 2),
        "captured_households"  : captured_hh,
        "category_share_pct"   : round(cat_share * 100, 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Metric 6 — Traffic Score
# ─────────────────────────────────────────────────────────────────────────────

def compute_traffic(traffic_summary: dict | None) -> dict:
    """
    AADT (Average Annual Daily Traffic) score. Industry benchmarks:
      <5,000   → low visibility
      15,000+  → viable
      50,000+  → premium
    """
    if not traffic_summary:
        return {"nearest_aadt": 0, "avg_aadt": 0, "score": 0}

    nearest = traffic_summary.get("nearest_aadt") or 0
    avg     = traffic_summary.get("avg_aadt") or 0
    blended = (nearest * 0.6) + (avg * 0.4)

    score = _normalize(blended, 2_000, 50_000)

    return {
        "nearest_aadt": nearest,
        "avg_aadt"    : avg,
        "score"       : round(score, 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Metric 7+8 — Competition Density + Pressure
# ─────────────────────────────────────────────────────────────────────────────

def compute_competition(competitors: list[dict], radius_km: float) -> dict:
    """
    Density: count per km²
    Pressure: distance-weighted threat (closer = exponentially worse)
    Score: lower competition = higher score (inverted)
    """
    count = len(competitors)
    area_km2 = math.pi * (radius_km ** 2)
    density = count / area_km2 if area_km2 else 0

    # Pressure: sum of (brand_weight / dist²) — same formula as Huff but inverted
    pressure = 0.0
    BETA = 2.0
    MIN_DIST_KM = 0.1
    for c in competitors:
        d = max(c.get("dist_km") or MIN_DIST_KM, MIN_DIST_KM)
        brand = _competitor_brand_weight(c.get("name", ""))
        pressure += brand / (d ** BETA)

    # Score: inverted normalization (lower count = better)
    score = 100 - _normalize(count, 10, 200)

    return {
        "count"            : count,
        "density_per_km2"  : round(density, 3),
        "pressure"         : round(pressure, 2),
        "nearest_brand"    : competitors[0].get("name") if competitors else None,
        "nearest_dist_km"  : competitors[0].get("dist_km") if competitors else None,
        "score"            : round(score, 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Income fit — how well does the area's income match the store format?
# ─────────────────────────────────────────────────────────────────────────────

def compute_income_fit(median_income: float, store_format: str) -> dict:
    """Triangular distribution: 100 at the sweet spot midpoint, 0 at the edges."""
    fmt = STORE_FORMATS.get(store_format, STORE_FORMATS["Target"])
    low, high = fmt["income_sweet_spot"]
    midpoint  = (low + high) / 2

    if median_income < low * 0.5 or median_income > high * 1.5:
        score = 0
    elif low <= median_income <= high:
        # Inside the sweet spot → score scales by closeness to midpoint
        distance_from_mid = abs(median_income - midpoint)
        max_distance      = (high - low) / 2
        score = 100 * (1 - (distance_from_mid / max_distance) * 0.3)
    else:
        # Outside but within tolerance → linear falloff
        if median_income < low:
            score = 70 * (median_income / low)
        else:
            score = max(0, 70 * (1 - ((median_income - high) / high)))

    return {
        "median_income"     : round(median_income, 2),
        "sweet_spot"        : f"${low:,}–${high:,}",
        "score"             : round(score, 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Metric 9 — ROI / Payback (uses industry-average CapEx)
# ─────────────────────────────────────────────────────────────────────────────

def compute_roi(sales: dict, store_format: str) -> dict:
    fmt = STORE_FORMATS.get(store_format, STORE_FORMATS["Target"])
    capex          = fmt["capex_usd"]
    margin         = fmt["operating_margin"]
    annual_revenue = sales["annual_revenue_usd"]

    annual_profit  = annual_revenue * margin
    payback_years  = (capex / annual_profit) if annual_profit > 0 else float("inf")
    roi_pct        = (annual_profit / capex * 100) if capex > 0 else 0

    return {
        "capex_usd"     : capex,
        "annual_profit" : round(annual_profit, 2),
        "roi_pct"       : round(roi_pct, 2),
        "payback_years" : round(payback_years, 1) if payback_years != float("inf") else None,
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
            "rationale"   : f"TAP {demand['tap']:,} households · EBP ${demand['ebp']/1e6:,.1f}M",
        },
        {
            "dimension"   : "Competition",
            "weight"      : COMPOSITE_WEIGHTS["competition"],
            "raw_score"   : competition["score"],
            "contribution": round(competition["score"] * COMPOSITE_WEIGHTS["competition"], 2),
            "rationale"   : f"{competition['count']} rivals · pressure {competition['pressure']:,.0f}",
        },
        {
            "dimension"   : "Huff Capture",
            "weight"      : COMPOSITE_WEIGHTS["huff"],
            "raw_score"   : huff["score"],
            "contribution": round(huff["score"] * COMPOSITE_WEIGHTS["huff"], 2),
            "rationale"   : f"{huff['capture_rate_pct']:.1f}% market share vs {huff['rivals_considered']} direct rivals",
        },
        {
            "dimension"   : "Traffic",
            "weight"      : COMPOSITE_WEIGHTS["traffic"],
            "raw_score"   : traffic["score"],
            "contribution": round(traffic["score"] * COMPOSITE_WEIGHTS["traffic"], 2),
            "rationale"   : f"{traffic['nearest_aadt']:,} AADT nearest · {traffic['avg_aadt']:,.0f} avg",
        },
        {
            "dimension"   : "Income Fit",
            "weight"      : COMPOSITE_WEIGHTS["income_fit"],
            "raw_score"   : income_fit["score"],
            "contribution": round(income_fit["score"] * COMPOSITE_WEIGHTS["income_fit"], 2),
            "rationale"   : f"Median ${income_fit['median_income']:,.0f} vs target {income_fit['sweet_spot']}",
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
    sales       = compute_sales_forecast(huff, median_income, store_format)
    traffic     = compute_traffic(traffic_row)
    competition = compute_competition(competitors, run["radius_km"])
    income_fit  = compute_income_fit(median_income, store_format)
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
