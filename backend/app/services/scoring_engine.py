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
    Approximate accessibility score for Phoenix metro using lat/lng heuristics.
    Heuristic: proximity to major Phoenix corridors raises score.
    In production, wire in OSRM or Google Directions API here.
    """
    major_corridors = [
        (33.4484, -112.0740),  # Phoenix I-10/I-17 downtown
        (33.5092, -112.1126),  # I-17 Glendale
        (33.5724, -112.1126),  # Loop 101 N
        (33.3742, -111.9397),  # US-60 Tempe
        (33.4149, -111.8315),  # Loop 202 / Chandler
        (33.6391, -111.9275),  # Scottsdale / 101
        (33.3806, -112.1306),  # I-10 Laveen
        (33.3528, -111.7896),  # Queen Creek / 24
    ]

    min_dist = min(
        ((lat - clat) ** 2 + (lng - clng) ** 2) ** 0.5
        for clat, clng in major_corridors
    )
    corridor_score = max(0, 100 - (min_dist / 0.05) * 30)
    metro_bonus = 20 if (33.2 < lat < 33.9 and -112.5 < lng < -111.5) else 0
    return min(corridor_score + metro_bonus, 100.0)


def compute_risk_score(
    competitors: CompetitorProfile,
    simulation: SimulationResult,
    demographics: DemographicsProfile,
    amenity: Optional[AmenityProfile] = None,
) -> float:
    """
    Risk score: 100 = no risk, 0 = very high risk.
    Now includes infrastructure risk from AmenityProfile.
    """
    cannibalization_penalty = simulation.cannibalization_risk * 0.35
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
    simulation: SimulationResult,
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
    if simulation.predicted_monthly_visits > 25000:
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
    simulation: SimulationResult,
    demographics: DemographicsProfile,
    hotspot: Optional[HotspotProfile],
    amenity: Optional[AmenityProfile],
) -> list[str]:
    risks = []

    if competitors.saturation_score > 60:
        risks.append(f"High competitor saturation ({competitors.big_box_count} big-box stores) — contested market share")
    if competitors.same_category_count > 3:
        risks.append(f"{competitors.same_category_count} same-category competitors nearby — differentiation critical")
    if simulation.cannibalization_risk > 50:
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


def compute_location_score(
    lat: float,
    lng: float,
    demographics: DemographicsProfile,
    competitors: CompetitorProfile,
    neighborhood: NeighborhoodProfile,
    simulation: SimulationResult,
    brand_fit: BrandFitProfile,
    hotspot: Optional[HotspotProfile] = None,
    amenity: Optional[AmenityProfile] = None,
) -> LocationScore:
    """Compute weighted 8-dimension composite score."""

    accessibility = compute_accessibility_score(lat, lng)
    risk = compute_risk_score(competitors, simulation, demographics, amenity)

    # Hotspot score: use actual if available, else neutral 55
    hotspot_score = hotspot.hotspot_score if hotspot else 55.0
    amenity_score = amenity.overall_amenity_score if amenity else 65.0

    total = (
        demographics.demand_score   * WEIGHTS["demand"]
        + competitors.competition_score * WEIGHTS["competition"]
        + accessibility              * WEIGHTS["accessibility"]
        + neighborhood.overall_score * WEIGHTS["neighborhood"]
        + brand_fit.fit_score        * WEIGHTS["brand_fit"]
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
        demand_score=demographics.demand_score,
        competition_score=competitors.competition_score,
        accessibility_score=round(accessibility, 1),
        neighborhood_score=neighborhood.overall_score,
        brand_fit_score=brand_fit.fit_score,
        risk_score=risk,
        hotspot_score=round(hotspot_score, 1),
        amenity_score=round(amenity_score, 1),
        rank_label=rank_label,
        why_this_wins=why_wins,
        top_risks=top_risks,
    )
