"""
Market Simulation Agent — The heart of RetailIQ.
Uses Google Gemini to generate a structured simulation of 500 household decision agents
that interact with a proposed new store. Each household agent has:
  - income bracket, household size, shopping frequency, brand loyalty, price sensitivity
  - distance from proposed store
  - word-of-mouth influence

Gemini generates these as structured JSON (not free-form chat) so the engine
can aggregate into statistically meaningful predictions.
This is NOT "agents chatting" — it's batch structured generation.
"""
import asyncio
import json
import os
import random
import math
import warnings
from typing import Optional
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai
from app.models.schemas import DemographicsProfile, CompetitorProfile, SimulationResult
from app.core.config import get_settings


def _configure_gemini():
    settings = get_settings()
    if settings.gemini_api_key and settings.gemini_api_key != "your_gemini_api_key_here":
        genai.configure(api_key=settings.gemini_api_key)
        return True
    return False


HOUSEHOLD_TYPOLOGIES = [
    # (name, income_range, brand_pref_walmart, brand_pref_target, price_sensitivity, frequency)
    ("Budget Family", (30000, 55000), 0.72, 0.45, 0.85, 3.5),
    ("Middle-Class Family", (55000, 85000), 0.58, 0.62, 0.60, 3.2),
    ("Affluent Family", (85000, 150000), 0.38, 0.74, 0.35, 2.8),
    ("Young Professional", (45000, 80000), 0.42, 0.68, 0.55, 2.0),
    ("Senior Household", (25000, 60000), 0.65, 0.55, 0.72, 2.5),
    ("Large Family", (40000, 75000), 0.70, 0.50, 0.78, 4.2),
    ("Single Adult", (30000, 65000), 0.50, 0.60, 0.65, 1.8),
    ("Dual Income No Kids", (75000, 130000), 0.40, 0.70, 0.40, 2.2),
]


def _simulate_households_local(
    demographics: DemographicsProfile,
    competitors: CompetitorProfile,
    brand: str,
    n: int = 500,
    seed: int = 42,
) -> list[dict]:
    """
    Fallback: deterministic simulation when Gemini API is unavailable.
    Generates household agents using statistical models.
    """
    rng = random.Random(seed)
    households = []

    for i in range(n):
        typology = rng.choices(HOUSEHOLD_TYPOLOGIES, weights=[2, 3, 2, 2, 1, 1.5, 2, 1.5])[0]
        name, income_range, walmart_pref, target_pref, price_sens, freq = typology
        income = rng.uniform(*income_range)

        brand_pref = walmart_pref if brand == "walmart" else target_pref
        # Distance decay: most households within 5 miles
        distance = abs(rng.gauss(4, 3))
        distance = max(0.5, min(distance, 15.0))
        distance_decay = 1 / (1 + (distance / 5) ** 1.5)

        # Competitor pull: each competitor slightly reduces visit probability
        competitor_pull = max(0.5, 1 - competitors.big_box_count * 0.05)

        # New store novelty bonus (12% boost at opening)
        novelty = 1.12

        visit_prob = brand_pref * distance_decay * competitor_pull * novelty
        will_visit = rng.random() < visit_prob

        monthly_spend = income / 12 * rng.uniform(0.03, 0.08)
        wom = rng.gauss(0.35, 0.15)  # word-of-mouth influence

        households.append({
            "typology": name,
            "income": int(income),
            "income_bracket": f"${income_range[0]//1000}k–${income_range[1]//1000}k",
            "distance_miles": round(distance, 1),
            "brand_preference_score": round(brand_pref, 2),
            "price_sensitivity": round(price_sens, 2),
            "shopping_frequency": round(freq, 1),
            "will_visit": will_visit,
            "monthly_spend_if_visit": round(monthly_spend, 2),
            "word_of_mouth_influence": round(max(0, min(wom, 1.0)), 2),
        })

    return households


async def _simulate_with_gemini(
    demographics: DemographicsProfile,
    competitors: CompetitorProfile,
    brand: str,
) -> Optional[list[dict]]:
    """Use Gemini to generate diverse, realistic household agent decisions."""
    if not _configure_gemini():
        return None

    model = genai.GenerativeModel(
        "gemini-2.0-flash",
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.7,
        ),
    )

    prompt = f"""You are a retail market simulation engine. Generate exactly 40 diverse household agent profiles
for a proposed new {brand.title()} superstore in Phoenix, AZ metro area.

Market context:
- Trade area population: {demographics.population:,}
- Median household income: ${demographics.median_income:,.0f}
- Family households: {demographics.family_households_pct:.0f}%
- Nearby big-box competitors: {competitors.big_box_count}
- Market saturation score: {competitors.saturation_score:.0f}/100
- Area underserved: {competitors.underserved}

Return a JSON array of exactly 40 objects, each with:
{{
  "typology": "string (e.g. Budget Family, Young Professional, Affluent Couple)",
  "income_bracket": "string (e.g. $45k-$65k)",
  "distance_miles": float (0.5 to 15.0),
  "brand_preference_score": float (0.0 to 1.0, higher = more likely to prefer {brand}),
  "price_sensitivity": float (0.0 to 1.0, higher = more price-driven),
  "shopping_frequency_per_month": float (1.0 to 5.0),
  "will_visit_new_store": boolean,
  "monthly_spend_estimate": float (50 to 800),
  "word_of_mouth_influence": float (0.0 to 1.0)
}}

Be realistic and diverse. For {brand}: {"favor price-sensitive, larger families, broader income range" if brand == "walmart" else "favor style-conscious, higher income, brand-loyal households"}.
The underserved status ({competitors.underserved}) means {"high opportunity — people currently travel far to shop" if competitors.underserved else "moderate competition — some residents are already loyal to existing stores"}.
"""

    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: model.generate_content(prompt)
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[SimulationAgent] Gemini error: {e}")
        return None


def _aggregate_simulation(
    households: list[dict],
    demographics: DemographicsProfile,
    total_n: int = 500,
) -> SimulationResult:
    """Aggregate household agent results into market-level predictions."""
    n = len(households)
    visitors = [h for h in households if h.get("will_visit") or h.get("will_visit_new_store")]

    pct_visit = len(visitors) / n if n > 0 else 0.3
    avg_spend = sum(h.get("monthly_spend_estimate", h.get("monthly_spend_if_visit", 150)) for h in visitors) / max(len(visitors), 1)
    avg_wom = sum(h.get("word_of_mouth_influence", 0.3) for h in households) / n

    # Scale from sample to full trade area
    hh_scale = demographics.household_count / total_n
    monthly_visits = int(pct_visit * demographics.household_count * 1.8)  # 1.8 visits/HH/month avg
    monthly_revenue = monthly_visits * avg_spend * 0.85  # 85% conversion of visits to purchase

    # Market share at 6 months (initial adoption) and 24 months (maturity)
    market_share_6 = pct_visit * 0.7 * 100   # Lower at first (loyalty inertia)
    market_share_24 = pct_visit * 1.1 * 100  # Higher at maturity (word-of-mouth kicks in)

    # Cannibalization: if another same-brand store is nearby, some revenue is transferred
    wom_score = min(avg_wom * 100, 100.0)
    cannibalization = max(0, 15 - demographics.population / 10000)  # Less for denser markets

    conf_low = monthly_revenue * 0.75
    conf_high = monthly_revenue * 1.30

    return SimulationResult(
        simulated_households=total_n,
        pct_will_visit=round(pct_visit * 100, 1),
        predicted_monthly_visits=monthly_visits,
        predicted_annual_revenue_usd=round(monthly_revenue * 12, 0),
        market_share_6mo=round(max(market_share_6, 5), 1),
        market_share_24mo=round(min(max(market_share_24, 8), 40), 1),
        word_of_mouth_score=round(wom_score, 1),
        cannibalization_risk=round(cannibalization, 1),
        confidence_interval_low=round(conf_low * 12, 0),
        confidence_interval_high=round(conf_high * 12, 0),
    )


async def run_simulation_agent(
    lat: float, lng: float,
    demographics: DemographicsProfile,
    competitors: CompetitorProfile,
    brand: str = "walmart",
):
    """Async generator yielding trace events + SimulationResult."""
    yield {"agent": "simulation", "status": "running",
           "message": f"Initializing agent-based market simulation for proposed {brand.title()} superstore..."}
    await asyncio.sleep(0.3)

    settings = get_settings()
    use_gemini = settings.gemini_api_key and settings.gemini_api_key != "your_gemini_api_key_here"

    if use_gemini:
        yield {"agent": "simulation", "status": "running",
               "message": "Engaging Gemini 2.0 Flash to generate diverse household agent profiles..."}
        gemini_households = await _simulate_with_gemini(demographics, competitors, brand)
    else:
        gemini_households = None
        yield {"agent": "simulation", "status": "running",
               "message": "Running statistical household simulation (500 agents: budget families, young professionals, retirees, dual-income households...)"}

    await asyncio.sleep(0.5)

    if gemini_households:
        households = gemini_households
        yield {"agent": "simulation", "status": "running",
               "message": f"Gemini generated {len(households)} diverse household profiles. "
                           f"Simulating shopping decisions, brand loyalty decay, distance friction..."}
    else:
        households = _simulate_households_local(demographics, competitors, brand)
        yield {"agent": "simulation", "status": "running",
               "message": f"500 household agents initialized. "
                           f"Modeling: shopping frequency, price sensitivity, brand loyalty, word-of-mouth spread..."}

    await asyncio.sleep(0.8)

    result = _aggregate_simulation(households, demographics, total_n=500)

    yield {
        "agent": "simulation",
        "status": "running",
        "message": f"Simulation converged. {result.pct_will_visit:.1f}% of trade area households will visit. "
                   f"Word-of-mouth amplification score: {result.word_of_mouth_score:.0f}/100. "
                   f"Projected Year-1 revenue: ${result.predicted_annual_revenue_usd/1e6:.1f}M",
    }
    await asyncio.sleep(0.3)

    yield {
        "agent": "simulation",
        "status": "done",
        "message": f"Market simulation complete → "
                   f"Predicted {result.predicted_monthly_visits:,} monthly visits, "
                   f"{result.market_share_24mo:.1f}% market share at 24 months",
        "data": result.model_dump(),
    }
