"""
Brand Fit Agent
Determines how well a specific location fits the Target vs Walmart brand strategy.
Uses Gemini for narrative generation; scoring is deterministic.
"""
import asyncio
import json
import google.generativeai as genai
from app.models.schemas import DemographicsProfile, CompetitorProfile, BrandFitProfile
from app.core.config import get_settings


# Brand positioning thresholds (based on public Target/Walmart strategic reports)
BRAND_PROFILES = {
    "walmart": {
        "ideal_income_range": (35000, 75000),
        "ideal_density": "suburban to rural",
        "price_sensitive": True,
        "grocery_strength": True,
        "style_conscious": False,
        "formats": ["Supercenter", "Neighborhood Market", "Sam's Club adjacent"],
    },
    "target": {
        "ideal_income_range": (55000, 120000),
        "ideal_density": "dense suburban to urban edge",
        "price_sensitive": False,
        "grocery_strength": False,
        "style_conscious": True,
        "formats": ["SuperTarget", "Target Express", "Urban small-format"],
    },
}


def _compute_brand_fit_score(brand: str, demographics: DemographicsProfile, competitors: CompetitorProfile) -> float:
    profile = BRAND_PROFILES[brand]
    ideal_low, ideal_high = profile["ideal_income_range"]
    income = demographics.median_income

    # Income alignment
    if ideal_low <= income <= ideal_high:
        income_align = 90.0
    elif income < ideal_low:
        income_align = max(30.0, 90.0 - (ideal_low - income) / 1000.0)
    else:
        income_align = max(40.0, 90.0 - (income - ideal_high) / 2000.0)

    # Density alignment
    if brand == "walmart":
        pop_align = min(demographics.population / 60000.0 * 100, 100.0)
    else:
        # Target prefers denser areas
        pop_align = min(demographics.population / 40000.0 * 100, 100.0)

    # Family alignment (both brands love families)
    family_align = demographics.family_households_pct

    # Education alignment (Target skews toward college-educated)
    if brand == "target":
        edu_align = min(demographics.college_educated_pct * 1.5, 100.0)
    else:
        edu_align = 70.0  # Walmart is broad

    fit = (
        income_align * 0.40
        + pop_align * 0.25
        + family_align * 0.20
        + edu_align * 0.15
    )
    return round(min(fit, 100.0), 1)


def _recommended_format(brand: str, demographics: DemographicsProfile) -> str:
    if brand == "walmart":
        if demographics.population > 80000:
            return "Walmart Supercenter (full grocery + general merchandise)"
        elif demographics.median_income > 65000:
            return "Walmart Supercenter with enhanced pharmacy + grocery"
        else:
            return "Walmart Neighborhood Market (grocery-focused)"
    else:
        if demographics.median_income > 90000:
            return "SuperTarget (full format with Starbucks + optical)"
        elif demographics.population > 60000:
            return "Target (standard format with expanded fresh grocery)"
        else:
            return "Target (standard format)"


async def _generate_brand_narrative(brand: str, fit_score: float, demographics: DemographicsProfile, income_align: float) -> str:
    """Use Gemini to generate a 2-sentence brand fit explanation."""
    settings = get_settings()
    if not settings.gemini_api_key or settings.gemini_api_key == "your_gemini_api_key_here":
        # Fallback narrative
        if brand == "walmart":
            return (
                f"This location aligns well with Walmart's value-driven format. "
                f"The area's median income of ${demographics.median_income:,.0f} and "
                f"{demographics.family_households_pct:.0f}% family household rate makes it ideal for "
                f"Walmart's grocery-anchored supercenter strategy. "
                f"Strong price sensitivity and household size signal high basket potential."
            )
        else:
            return (
                f"This location presents a strong fit for Target's elevated shopping experience. "
                f"With {demographics.college_educated_pct:.0f}% college-educated residents and "
                f"${demographics.median_income:,.0f} median income, the community skews toward "
                f"Target's style-conscious, brand-loyal shopper profile."
            )

    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    prompt = f"""Write exactly 2 sentences explaining why {brand.title()} (brand fit score: {fit_score:.0f}/100) 
fits or doesn't fit this Phoenix metro location:
- Median income: ${demographics.median_income:,.0f}
- Family households: {demographics.family_households_pct:.0f}%
- College educated: {demographics.college_educated_pct:.0f}%
- Population: {demographics.population:,}

Be direct, specific, and business-focused. No filler. Reference actual brand positioning strategy."""

    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: model.generate_content(prompt)
        )
        return response.text.strip()
    except Exception:
        return f"{brand.title()} brand fit score: {fit_score:.0f}/100 based on income and demographic alignment."


async def run_brand_fit_agent(
    lat: float, lng: float,
    brand: str,
    demographics: DemographicsProfile,
    competitors: CompetitorProfile,
):
    """Async generator yielding trace events + BrandFitProfile."""
    yield {"agent": "brand_fit", "status": "running",
           "message": f"Evaluating {brand.title()} brand positioning strategy for this market..."}
    await asyncio.sleep(0.3)

    fit_score = _compute_brand_fit_score(brand, demographics, competitors)
    recommended_format = _recommended_format(brand, demographics)

    profile = BRAND_PROFILES[brand]
    ideal_low, ideal_high = profile["ideal_income_range"]
    income = demographics.median_income

    income_alignment = max(0, 100 - abs(income - (ideal_low + ideal_high) / 2) / 500)
    density_alignment = min(demographics.population / 50000 * 100, 100.0)

    report = f"{brand.title()} ideal income range: ${ideal_low:,}–${ideal_high:,}. " \
             f"This area: ${income:,.0f}. " \
             f"{'✅ Strong alignment' if ideal_low <= income <= ideal_high else '⚠️ Income mismatch'}."

    yield {"agent": "brand_fit", "status": "running",
           "message": f"Analyzing income alignment, demographic profile, and competitor positioning. {report}"}
    await asyncio.sleep(0.5)

    narrative = await _generate_brand_narrative(brand, fit_score, demographics, income_alignment)

    brand_profile = BrandFitProfile(
        brand=brand,
        fit_score=fit_score,
        recommended_format=recommended_format,
        income_alignment=round(min(income_alignment, 100.0), 1),
        density_alignment=round(density_alignment, 1),
        reasoning=narrative,
    )

    yield {
        "agent": "brand_fit",
        "status": "done",
        "message": f"Brand fit analysis complete → {brand.title()} Score: {fit_score:.0f}/100. "
                   f"Recommended: {recommended_format}",
        "data": brand_profile.model_dump(),
    }

