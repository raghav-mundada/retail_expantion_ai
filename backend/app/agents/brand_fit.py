"""
Brand Fit Agent (Universal Edition)
Works with ANY retailer — known brands or custom store specs.
Accepts BrandDNA from the BrandResolverAgent instead of hardcoded BRAND_PROFILES.
"""
import asyncio
import json
import warnings
from typing import Optional
from openai import OpenAI

from app.models.schemas import DemographicsProfile, CompetitorProfile, BrandFitProfile, BrandDNA
from app.core.config import get_settings



def _compute_brand_fit_score(
    brand_dna: BrandDNA,
    demographics: DemographicsProfile,
    competitors: CompetitorProfile,
) -> tuple[float, float, float]:
    """
    Returns (fit_score, income_alignment, density_alignment).
    Fully driven by BrandDNA — works for any retailer.
    """
    ideal_low = brand_dna.ideal_income_low
    ideal_high = brand_dna.ideal_income_high
    income = demographics.median_income

    # Income alignment (40% weight)
    if ideal_low <= income <= ideal_high:
        income_align = 90.0
    elif income < ideal_low:
        income_align = max(25.0, 90.0 - (ideal_low - income) / 1200.0)
    else:
        income_align = max(35.0, 90.0 - (income - ideal_high) / 2500.0)

    # Population/density alignment (25% weight)
    min_pop = brand_dna.ideal_population_min
    pop_align = min(demographics.population / max(min_pop, 1) * 80, 100.0)

    # Family alignment (20% weight)
    family_align = demographics.family_households_pct
    if not brand_dna.family_skew:
        family_align = max(family_align, 60.0)   # non-family brands less sensitive

    # Education alignment (15% weight)
    edu_align = min(demographics.college_educated_pct * 1.5, 100.0) \
        if brand_dna.college_edu_skew else 70.0

    # Same-category competitor penalty (if area already saturated with same type)
    saturation_penalty = min(competitors.same_category_count * 5, 20)

    fit = (
        income_align * 0.40
        + pop_align * 0.25
        + family_align * 0.20
        + edu_align * 0.15
    ) - saturation_penalty

    return round(max(0.0, min(fit, 100.0)), 1), round(income_align, 1), round(pop_align, 1)


def _recommended_format(brand_dna: BrandDNA, demographics: DemographicsProfile) -> str:
    """Recommend a store format based on resolved BrandDNA and local demographics."""
    sqft = brand_dna.footprint_sqft
    fmt = brand_dna.store_format.replace("_", " ").title()

    # Size guidance
    if demographics.population > 100000:
        size_note = "Full-size format recommended"
    elif demographics.population > 50000:
        size_note = "Standard format appropriate"
    else:
        size_note = "Consider reduced-footprint format"

    # Income guidance
    if demographics.median_income > brand_dna.ideal_income_high * 1.2:
        extra = " with premium service enhancements"
    elif demographics.median_income < brand_dna.ideal_income_low * 0.8:
        extra = " with value-focused product mix"
    else:
        extra = ""

    return f"{brand_dna.display_name} — {fmt}{extra} ({sqft:,} sq ft typical). {size_note}."


def _brand_fit_narrative_fallback(
    brand_dna: BrandDNA,
    fit_score: float,
    demographics: DemographicsProfile,
    income_align: float,
) -> str:
    level = "strong" if fit_score >= 70 else "moderate" if fit_score >= 50 else "weak"
    return (
        f"{brand_dna.display_name} shows {level} fit for this location (score: {fit_score:.0f}/100). "
        f"The area's ${demographics.median_income:,.0f} median household income "
        f"{'falls within' if income_align > 75 else 'deviates from'} "
        f"the {brand_dna.price_positioning} retail sweet spot. "
        f"{demographics.family_households_pct:.0f}% family households "
        f"{'aligns well' if brand_dna.family_skew else 'is a secondary factor'} for this format."
    )


async def _generate_brand_narrative(
    brand_dna: BrandDNA,
    fit_score: float,
    demographics: DemographicsProfile,
    income_align: float,
) -> str:
    """Use OpenAI to generate a 2–3 sentence brand fit explanation for any retailer."""
    settings = get_settings()

    if not settings.openai_api_key or settings.openai_api_key == "your_openai_api_key_here":
        return _brand_fit_narrative_fallback(brand_dna, fit_score, demographics, income_align)

    prompt = f"""Write exactly 2-3 sentences explaining how well {brand_dna.display_name} fits this location.

Store profile: {brand_dna.store_format} | {brand_dna.price_positioning} pricing | {', '.join(brand_dna.primary_categories)} | {brand_dna.footprint_sqft:,} sq ft typical
Ideal customer income: ${brand_dna.ideal_income_low:,}–${brand_dna.ideal_income_high:,}
Brand fit score: {fit_score:.0f}/100

Location demographics:
- Median income: ${demographics.median_income:,.0f}
- Family households: {demographics.family_households_pct:.0f}%
- College educated: {demographics.college_educated_pct:.0f}%
- Population: {demographics.population:,}

Be direct, specific, business-focused. Reference actual demographic signals. No filler sentences."""

    def _call() -> str:
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.4,
        )
        return resp.choices[0].message.content.strip()

    try:
        return await asyncio.get_event_loop().run_in_executor(None, _call)
    except Exception:
        return _brand_fit_narrative_fallback(brand_dna, fit_score, demographics, income_align)


async def run_brand_fit_agent(
    lat: float,
    lng: float,
    brand: str,  # kept for backward compatibility — display name
    demographics: DemographicsProfile,
    competitors: CompetitorProfile,
    brand_dna: Optional[BrandDNA] = None,

):
    """
    Universal Brand Fit Agent — async generator.
    Uses BrandDNA if provided (from brand_resolver); falls back to basic logic otherwise.
    """
    display = brand_dna.display_name if brand_dna else brand.title()

    yield {
        "agent": "brand_fit",
        "status": "running",
        "message": f"Evaluating {display} brand positioning strategy for this market...",
    }
    await asyncio.sleep(0.2)

    # Build a minimal BrandDNA from brand name if not provided (backward compat)
    if brand_dna is None:
        from app.agents.brand_resolver import _build_from_lookup, KNOWN_BRANDS
        brand_dna = _build_from_lookup(brand)
        if brand_dna is None:
            from app.models.schemas import BrandDNA as BD
            brand_dna = BD(
                display_name=brand.title(),
                ideal_income_low=40_000, ideal_income_high=100_000,
                ideal_population_min=40_000, footprint_sqft=80_000,
                primary_categories=["general_merchandise"],
                price_positioning="mid_range", store_format="general_retail",
                family_skew=True, college_edu_skew=False,
                known_brand=True, expansion_velocity="moderate",
                reasoning="Baseline retail profile.",
            )

    fit_score, income_align, density_align = _compute_brand_fit_score(brand_dna, demographics, competitors)
    recommended_format = _recommended_format(brand_dna, demographics)

    report = (
        f"{display} ideal income: ${brand_dna.ideal_income_low:,}–${brand_dna.ideal_income_high:,}. "
        f"This area: ${demographics.median_income:,.0f}. "
        f"{'✅ Strong alignment' if income_align > 75 else '⚠️ Income deviation detected'}."
    )

    yield {
        "agent": "brand_fit",
        "status": "running",
        "message": f"Analyzing income alignment, demographic profile, competitor context. {report}",
    }
    await asyncio.sleep(0.3)

    budget = float(get_settings().analysis_brand_narrative_timeout_seconds)
    budget = max(4.0, min(budget, 60.0))
    try:
        narrative = await asyncio.wait_for(
            _generate_brand_narrative(brand_dna, fit_score, demographics, income_align),
            timeout=budget,
        )
    except asyncio.TimeoutError:
        print(f"[BrandFit] narrative OpenAI exceeded {budget:.0f}s — using template")
        narrative = _brand_fit_narrative_fallback(brand_dna, fit_score, demographics, income_align)

    brand_profile = BrandFitProfile(
        brand=display,
        fit_score=fit_score,
        recommended_format=recommended_format,
        income_alignment=round(min(income_align, 100.0), 1),
        density_alignment=round(min(density_align, 100.0), 1),
        reasoning=narrative,
    )

    yield {
        "agent": "brand_fit",
        "status": "done",
        "message": (
            f"Brand fit analysis complete → {display} Score: {fit_score:.0f}/100. "
            f"Recommended: {recommended_format[:60]}"
        ),
        "data": brand_profile.model_dump(),
    }
