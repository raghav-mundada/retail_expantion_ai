"""
Deterministic Scoring Engine
Computes a weighted location score from sub-agent outputs.
This is intentionally NOT an LLM call — it is a structured, reproducible model.
Weights are calibrated for U.S. suburban superstore placement.
"""
from app.models.schemas import (
    DemographicsProfile, CompetitorProfile, NeighborhoodProfile,
    SimulationResult, BrandFitProfile, LocationScore
)


# Scoring weights — must sum to 1.0
WEIGHTS = {
    "demand": 0.28,
    "competition": 0.22,
    "accessibility": 0.15,
    "neighborhood": 0.15,
    "brand_fit": 0.12,
    "risk": 0.08,
}

RANK_THRESHOLDS = [
    (85, "🏆 Exceptional"),
    (70, "✅ Strong"),
    (55, "⚡ Promising"),
    (40, "⚠️ Moderate"),
    (0,  "❌ Not Recommended"),
]


def compute_accessibility_score(lat: float, lng: float) -> float:
    """
    Approximate accessibility score for Phoenix metro using lat/lng heuristics.
    In production, this would use OSRM or Google Directions API.
    Heuristic: proximity to major Phoenix corridors raises score.
    """
    # Major Phoenix highway corridors (I-10, I-17, US-60, Loop 101, Loop 202)
    major_corridors = [
        (33.4484, -112.0740),  # Phoenix downtown I-10/I-17 interchange
        (33.5092, -112.1126),  # I-17 Glendale
        (33.5724, -112.1126),  # Loop 101 N
        (33.3742, -111.9397),  # US-60 Tempe
        (33.4149, -111.8315),  # Loop 202 / Chandler
        (33.6391, -111.9275),  # Scottsdale/101 corridor
        (33.3806, -112.1306),  # I-10 Laveen
    ]

    min_dist_to_corridor = min(
        ((lat - clat) ** 2 + (lng - clng) ** 2) ** 0.5
        for clat, clng in major_corridors
    )

    # Score drops with distance from corridors (in degrees)
    # 0.05 degrees ≈ 3.5 miles
    corridor_score = max(0, 100 - (min_dist_to_corridor / 0.05) * 30)

    # Phoenix metro base accessibility bonus (as opposed to rural)
    metro_bonus = 20 if (33.2 < lat < 33.9 and -112.5 < lng < -111.5) else 0

    return min(corridor_score + metro_bonus, 100.0)


def compute_risk_score(
    competitors: CompetitorProfile,
    simulation: SimulationResult,
    demographics: DemographicsProfile,
) -> float:
    """
    Risk score: 100 = no risk, 0 = very high risk.
    Factors: cannibalization, competitor response, economic sensitivity.
    """
    cannibalization_penalty = simulation.cannibalization_risk * 0.4
    saturation_penalty = competitors.saturation_score * 0.3
    low_income_penalty = max(0, (50000 - demographics.median_income) / 50000 * 30)

    raw_risk = cannibalization_penalty + saturation_penalty + low_income_penalty
    risk_score = max(0.0, 100.0 - raw_risk)
    return round(min(risk_score, 100.0), 1)


def generate_why_wins(
    demographics: DemographicsProfile,
    competitors: CompetitorProfile,
    neighborhood: NeighborhoodProfile,
    simulation: SimulationResult,
    brand_fit: BrandFitProfile,
    score: float,
) -> list[str]:
    reasons = []

    if demographics.population > 40000:
        reasons.append(f"High-density catchment area with ~{demographics.population:,} residents within trade radius")
    if demographics.median_income > 70000:
        reasons.append(f"Above-average household income (${demographics.median_income:,.0f} median) signals strong basket size potential")
    if competitors.underserved:
        reasons.append("Area is underserved — no dominant big-box competitor within 5 miles")
    if competitors.demand_signal_score > 50:
        reasons.append("Existing retail density confirms proven consumer demand in this corridor")
    if neighborhood.school_quality_index > 65:
        reasons.append(f"Strong school district ({neighborhood.school_quality_index:.0f}/100) attracts stable family households")
    if demographics.family_households_pct > 60:
        reasons.append(f"Family-dominant area ({demographics.family_households_pct:.0f}% family HHs) aligns with superstore shopping patterns")
    if simulation.predicted_monthly_visits > 30000:
        reasons.append(f"Simulation predicts ~{simulation.predicted_monthly_visits:,} monthly visits at maturity")
    if brand_fit.fit_score > 70:
        reasons.append(f"Strong {brand_fit.brand.title()} brand alignment — {brand_fit.recommended_format}")

    if not reasons:
        reasons.append("Location shows moderate potential across multiple indicators")

    return reasons[:5]


def generate_top_risks(
    competitors: CompetitorProfile,
    simulation: SimulationResult,
    demographics: DemographicsProfile,
) -> list[str]:
    risks = []

    if competitors.saturation_score > 60:
        risks.append(f"High competitor saturation ({competitors.big_box_count} big-box stores nearby) — market share capture will be contested")
    if simulation.cannibalization_risk > 50:
        risks.append("Significant cannibalization risk — proposed site may draw from an existing company store")
    if demographics.median_income < 50000:
        risks.append("Below-average income area may limit basket size and discretionary spend")
    if demographics.population < 20000:
        risks.append("Low trade area population — may not reach breakeven foot traffic thresholds")
    if competitors.big_box_count > 4:
        risks.append("Market may be approaching saturation — aggressive promotion needed at opening")

    if not risks:
        risks.append("No major risk factors identified — execution risk remains standard for new store openings")

    return risks[:3]


def compute_location_score(
    lat: float,
    lng: float,
    demographics: DemographicsProfile,
    competitors: CompetitorProfile,
    neighborhood: NeighborhoodProfile,
    simulation: SimulationResult,
    brand_fit: BrandFitProfile,
) -> LocationScore:
    """Compute weighted total score from all sub-agent outputs."""

    accessibility = compute_accessibility_score(lat, lng)
    risk = compute_risk_score(competitors, simulation, demographics)

    total = (
        demographics.demand_score * WEIGHTS["demand"]
        + competitors.competition_score * WEIGHTS["competition"]
        + accessibility * WEIGHTS["accessibility"]
        + neighborhood.overall_score * WEIGHTS["neighborhood"]
        + brand_fit.fit_score * WEIGHTS["brand_fit"]
        + risk * WEIGHTS["risk"]
    )
    total = round(min(total, 100.0), 1)

    # Determine rank
    rank_label = RANK_THRESHOLDS[-1][1]
    for threshold, label in RANK_THRESHOLDS:
        if total >= threshold:
            rank_label = label
            break

    why_wins = generate_why_wins(demographics, competitors, neighborhood, simulation, brand_fit, total)
    top_risks = generate_top_risks(competitors, simulation, demographics)

    return LocationScore(
        total_score=total,
        demand_score=demographics.demand_score,
        competition_score=competitors.competition_score,
        accessibility_score=round(accessibility, 1),
        neighborhood_score=neighborhood.overall_score,
        brand_fit_score=brand_fit.fit_score,
        risk_score=risk,
        rank_label=rank_label,
        why_this_wins=why_wins,
        top_risks=top_risks,
    )
