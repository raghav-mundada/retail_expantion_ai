"""
Deterministic Scoring Engine (v2 — 8 dimensions)
Computes a weighted location score from all sub-agent outputs.
Intentionally NOT an LLM call — structured, reproducible, auditable.

Dimensions + weights (sum = 1.0):
  demand       20%  — demographics demand score
  competition  18%  — competitive position
  accessibility 12% — highway/transit access
  neighborhood 12%  — school quality, stability
  brand_fit    12%  — brand-demographics alignment
  risk          8%  — cannibalization + saturation
  hotspot      15%  — TinyFish live signals NEW
  amenity       3%  — infrastructure/utility suitability NEW
"""
from typing import Optional
from app.models.schemas import (
    DemographicsProfile, CompetitorProfile, NeighborhoodProfile,
    SimulationResult, BrandFitProfile, LocationScore,
    HotspotProfile, AmenityProfile,
)
from app.services.store_formats import (
    STORE_FORMATS, resolve_store_format, income_fit_score, normalize,
)

# Simulation is now optional (runs on demand). When it's absent we fall back
# to deterministic proxies for cannibalization / word-of-mouth signals.
#
# Format-aware blending (Huff-lite from `main`):
#   We keep Yash-merge's 8-dimension engine + TinyFish, but every dimension
#   that depends on retailer DNA (demand, competition, brand_fit) is nudged
#   with the STORE_FORMATS profile — so Walmart is scored differently from
#   Whole Foods even at the same lat/lng. Weights still sum to 1.0.


# Scoring weights — must sum to 1.0
WEIGHTS = {
    "demand":        0.20,
    "competition":   0.18,
    "accessibility": 0.12,
    "neighborhood":  0.12,
    "brand_fit":     0.12,
    "risk":          0.08,
    "hotspot":       0.15,   # TinyFish live retail signals
    "amenity":       0.03,   # infrastructure suitability (folded into risk)
}

RANK_THRESHOLDS = [
    (88, "🏆 Exceptional"),
    (72, "✅ Strong"),
    (57, "⚡ Promising"),
    (42, "⚠️ Moderate"),
    (0,  "❌ Not Recommended"),
]


def compute_accessibility_score(lat: float, lng: float) -> float:
    """
    Approximate accessibility score for US metros using proximity to major
    urban cores + interstate corridors. Wire in OSRM / Google Directions
    for a production-grade score.
    """
    major_corridors = [
        # Minneapolis / St. Paul metro (primary UI focus)
        (44.9778, -93.2650),   # Downtown Minneapolis (I-35W + I-94)
        (44.9537, -93.0900),   # Downtown St. Paul (I-35E + I-94)
        (44.8547, -93.4708),   # Eden Prairie (169 + 494)
        (45.0105, -93.4555),   # Plymouth (494 + 55)
        (44.8408, -93.3376),   # Bloomington / MOA (494 + 77)
        (44.8763, -93.2839),   # Richfield (62 + 35W)
        (45.0720, -93.3317),   # Brooklyn Center (694 + 94)
        (44.7677, -93.2777),   # Burnsville (35W + 13)

        # Phoenix metro (legacy coverage)
        (33.4484, -112.0740), (33.3742, -111.9397), (33.6391, -111.9275),

        # Other top US metros so the score stays sane outside MSP:
        (40.7128,  -74.0060),  # NYC
        (34.0522, -118.2437),  # LA
        (41.8781,  -87.6298),  # Chicago
        (29.7604,  -95.3698),  # Houston
        (32.7767,  -96.7970),  # Dallas
        (39.7392, -104.9903),  # Denver
        (47.6062, -122.3321),  # Seattle
    ]

    # Rough haversine-ish distance in degrees — good enough for a coarse score.
    min_dist = min(
        ((lat - clat) ** 2 + (lng - clng) ** 2) ** 0.5
        for clat, clng in major_corridors
    )
    # Within ~5 km (0.05°) of a corridor anchor → near-max score; decays linearly.
    corridor_score = max(0.0, 100.0 - (min_dist / 0.05) * 20.0)
    # Metro bonus: anywhere inside the MSP bounding box gets a lift.
    msp_bonus = 15.0 if (44.70 < lat < 45.25 and -93.60 < lng < -92.80) else 0.0
    return round(min(corridor_score + msp_bonus, 100.0), 1)


def compute_risk_score(
    competitors: CompetitorProfile,
    simulation: Optional[SimulationResult],
    demographics: DemographicsProfile,
    amenity: Optional[AmenityProfile] = None,
) -> float:
    """
    Risk score: 100 = no risk, 0 = very high risk.
    When the user hasn't run the simulation yet we approximate
    cannibalization from big-box competitor density (~3% per big-box).
    """
    if simulation is not None:
        cannibalization_penalty = simulation.cannibalization_risk * 0.35
    else:
        # Proxy: every same-category competitor inside the trade area
        # roughly lifts cannibalization risk ~3 points.
        proxy_cannibalization = min(competitors.same_category_count * 3.0, 30.0)
        cannibalization_penalty = proxy_cannibalization * 0.35
    saturation_penalty = competitors.saturation_score * 0.30
    low_income_penalty = max(0, (50000 - demographics.median_income) / 50000 * 25)

    # Infrastructure risk: very low amenity score = risk factor
    infra_penalty = 0.0
    if amenity and amenity.overall_amenity_score < 40:
        infra_penalty = (40 - amenity.overall_amenity_score) * 0.2

    raw_risk = cannibalization_penalty + saturation_penalty + low_income_penalty + infra_penalty
    risk_score = max(0.0, 100.0 - raw_risk)
    return round(min(risk_score, 100.0), 1)


def generate_why_wins(
    demographics: DemographicsProfile,
    competitors: CompetitorProfile,
    neighborhood: NeighborhoodProfile,
    simulation: Optional[SimulationResult],
    brand_fit: BrandFitProfile,
    hotspot: Optional[HotspotProfile],
    amenity: Optional[AmenityProfile],
    score: float,
) -> list[str]:
    reasons = []

    if demographics.population > 40000:
        reasons.append(f"High-density catchment: ~{demographics.population:,} residents in trade radius")
    if demographics.median_income > 70000:
        reasons.append(f"Above-average income (${demographics.median_income:,.0f} median) → strong basket potential")
    if competitors.underserved:
        reasons.append("Area is underserved — no dominant big-box competitor within 5 miles")
    if competitors.demand_signal_score > 50:
        reasons.append("Existing retail density confirms proven consumer demand in this corridor")
    if neighborhood.school_quality_index > 65:
        reasons.append(f"Strong school district ({neighborhood.school_quality_index:.0f}/100) → stable family household base")
    if demographics.family_households_pct > 60:
        reasons.append(f"Family-dominant area ({demographics.family_households_pct:.0f}% family HHs) aligns with superstore shopping patterns")
    if simulation is not None and simulation.predicted_monthly_visits > 25000:
        reasons.append(f"Simulation projects ~{simulation.predicted_monthly_visits:,} monthly visits at maturity")
    if brand_fit.fit_score > 70:
        reasons.append(f"Strong {brand_fit.brand} brand alignment — {brand_fit.recommended_format[:50]}")
    if hotspot and hotspot.hotspot_score > 65:
        reasons.append(
            f"High retail momentum detected: {hotspot.new_openings_count} recent new openings, "
            f"{hotspot.loopnet_active_listings} available commercial spaces"
        )
    if hotspot and hotspot.trending_categories:
        cats = ", ".join(hotspot.trending_categories[:3])
        reasons.append(f"Trending retail categories in area: {cats}")

    return reasons[:6] if reasons else ["Location shows moderate potential across multiple indicators"]


def generate_top_risks(
    competitors: CompetitorProfile,
    simulation: Optional[SimulationResult],
    demographics: DemographicsProfile,
    hotspot: Optional[HotspotProfile],
    amenity: Optional[AmenityProfile],
) -> list[str]:
    risks = []

    if competitors.saturation_score > 60:
        risks.append(f"High competitor saturation ({competitors.big_box_count} big-box stores) — contested market share")
    if competitors.same_category_count > 3:
        risks.append(f"{competitors.same_category_count} same-category competitors nearby — differentiation critical")
    if simulation is not None and simulation.cannibalization_risk > 50:
        risks.append("Significant cannibalization risk — may draw from an existing company store")
    if demographics.median_income < 50000:
        risks.append("Below-average income may limit basket size and discretionary spend")
    if demographics.population < 20000:
        risks.append("Low trade area population — may not reach breakeven foot traffic thresholds")
    if competitors.big_box_count > 4:
        risks.append("Market approaching saturation — aggressive opening promotion needed")
    if amenity and amenity.overall_amenity_score < 45:
        risks.append(
            f"Infrastructure concerns: power/water/zoning score {amenity.overall_amenity_score:.0f}/100 "
            f"— development costs may be elevated"
        )
    if hotspot and hotspot.loopnet_active_listings == 0:
        risks.append("No available commercial spaces detected — site acquisition may require greenfield development")

    return risks[:4] if risks else ["No major risk factors identified — standard new-store execution risks apply"]


def _format_adjusted_demand(demographics: DemographicsProfile, fmt_name: str) -> float:
    """
    Format-aware demand score. Takes the agent-computed `demand_score` and
    reweights it by:
      • income_fit — how close median income is to the format's sweet spot
      • population_fit — saturating curve around the format's min_population
    """
    fmt = STORE_FORMATS[fmt_name]
    base = demographics.demand_score

    inc_fit = income_fit_score(demographics.median_income, fmt_name)           # 0–100
    pop_fit = normalize(demographics.population, fmt["min_population"] * 0.25,
                                              fmt["min_population"] * 3.0)      # 0–100

    # 55% base demand, 25% income alignment, 20% population fit
    blended = 0.55 * base + 0.25 * inc_fit + 0.20 * pop_fit
    return round(min(blended, 100.0), 1)


def _format_adjusted_brand_fit(brand_fit: BrandFitProfile, demographics: DemographicsProfile, fmt_name: str) -> float:
    """
    Blend the agent's brand_fit.fit_score with a deterministic income-fit
    check against STORE_FORMATS. Guards against LLM hallucination by anchoring
    to the format's documented sweet spot.
    """
    inc_fit = income_fit_score(demographics.median_income, fmt_name)
    blended = 0.65 * brand_fit.fit_score + 0.35 * inc_fit
    return round(min(blended, 100.0), 1)


def compute_location_score(
    lat: float,
    lng: float,
    demographics: DemographicsProfile,
    competitors: CompetitorProfile,
    neighborhood: NeighborhoodProfile,
    brand_fit: BrandFitProfile,
    hotspot: Optional[HotspotProfile] = None,
    amenity: Optional[AmenityProfile] = None,
    simulation: Optional[SimulationResult] = None,
) -> LocationScore:
    """Compute weighted 8-dimension composite score — format-aware."""

    fmt_name = resolve_store_format(brand_fit.brand)

    accessibility = compute_accessibility_score(lat, lng)
    risk          = compute_risk_score(competitors, simulation, demographics, amenity)

    # Format-aware dimension adjustments
    demand_score  = _format_adjusted_demand(demographics, fmt_name)
    brand_fit_adj = _format_adjusted_brand_fit(brand_fit, demographics, fmt_name)

    # Hotspot + amenity defaults
    hotspot_score = hotspot.hotspot_score if hotspot else 55.0
    amenity_score = amenity.overall_amenity_score if amenity else 65.0

    total = (
        demand_score                 * WEIGHTS["demand"]
        + competitors.competition_score * WEIGHTS["competition"]
        + accessibility              * WEIGHTS["accessibility"]
        + neighborhood.overall_score * WEIGHTS["neighborhood"]
        + brand_fit_adj              * WEIGHTS["brand_fit"]
        + risk                       * WEIGHTS["risk"]
        + hotspot_score              * WEIGHTS["hotspot"]
        + amenity_score              * WEIGHTS["amenity"]
    )
    total = round(min(total, 100.0), 1)

    rank_label = RANK_THRESHOLDS[-1][1]
    for threshold, label in RANK_THRESHOLDS:
        if total >= threshold:
            rank_label = label
            break

    why_wins = generate_why_wins(demographics, competitors, neighborhood, simulation,
                                 brand_fit, hotspot, amenity, total)
    top_risks = generate_top_risks(competitors, simulation, demographics, hotspot, amenity)

    return LocationScore(
        total_score=total,
        demand_score=demand_score,
        competition_score=competitors.competition_score,
        accessibility_score=round(accessibility, 1),
        neighborhood_score=neighborhood.overall_score,
        brand_fit_score=brand_fit_adj,
        risk_score=risk,
        hotspot_score=round(hotspot_score, 1),
        amenity_score=round(amenity_score, 1),
        rank_label=rank_label,
        why_this_wins=why_wins,
        top_risks=top_risks,
    )
