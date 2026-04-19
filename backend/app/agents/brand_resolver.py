"""
Brand Resolver Agent — Phase 0

Resolves a RetailerProfile into a structured BrandDNA used by all downstream agents.

Path A (known brand): Uses Gemini to look up positioning, income target, footprint, etc.
Path B (custom store): Synthesizes BrandDNA from user-specified size/category/positioning.

Runs BEFORE all other agents — its output feeds brand_fit, simulation, and competitor agents.
"""
import json
import asyncio
from typing import AsyncGenerator, Optional, Dict
from openai import OpenAI

from app.models.schemas import RetailerProfile, BrandDNA, StoreSizeEnum, PricePositioning
from app.core.config import get_settings

settings = get_settings()

# Footprint estimates by size
FOOTPRINT_MAP = {
    StoreSizeEnum.SMALL: 3500,
    StoreSizeEnum.MEDIUM: 15000,
    StoreSizeEnum.LARGE: 50000,
    StoreSizeEnum.BIG_BOX: 120000,
}

# Income targets by positioning
INCOME_MAP = {
    PricePositioning.BUDGET:    (30_000, 65_000),
    PricePositioning.MID_RANGE: (50_000, 110_000),
    PricePositioning.PREMIUM:   (90_000, 250_000),
}

# Known brand quick-lookup (Gemini backs this up with richer data)
KNOWN_BRANDS: Dict[str, dict] = {
    "walmart":      {"income": (35_000, 80_000),  "sqft": 180_000, "format": "supercenter",        "position": "budget",    "cat": ["general_merchandise", "grocery"]},
    "target":       {"income": (50_000, 110_000), "sqft": 120_000, "format": "discount_department", "position": "mid_range", "cat": ["general_merchandise", "apparel", "grocery"]},
    "costco":       {"income": (75_000, 200_000), "sqft": 150_000, "format": "warehouse_club",      "position": "mid_range", "cat": ["grocery", "general_merchandise"]},
    "aldi":         {"income": (30_000, 75_000),  "sqft": 18_000,  "format": "limited_assortment",  "position": "budget",    "cat": ["grocery"]},
    "trader joe's": {"income": (60_000, 150_000), "sqft": 15_000,  "format": "specialty_grocery",   "position": "mid_range", "cat": ["grocery", "specialty"]},
    "whole foods":  {"income": (90_000, 300_000), "sqft": 40_000,  "format": "premium_grocery",     "position": "premium",   "cat": ["grocery", "specialty"]},
    "sprouts":      {"income": (60_000, 150_000), "sqft": 28_000,  "format": "natural_grocery",     "position": "mid_range", "cat": ["grocery", "specialty"]},
    "kroger":       {"income": (45_000, 95_000),  "sqft": 65_000,  "format": "full_grocery",        "position": "mid_range", "cat": ["grocery"]},
    "h-mart":       {"income": (50_000, 120_000), "sqft": 30_000,  "format": "asian_grocery",       "position": "mid_range", "cat": ["grocery", "specialty"]},
    "nordstrom rack":{"income": (55_000, 130_000),"sqft": 40_000, "format": "off_price_apparel",   "position": "mid_range", "cat": ["apparel"]},
    "dollar general":{"income": (25_000, 60_000), "sqft": 7_500,   "format": "dollar_store",        "position": "budget",    "cat": ["general_merchandise"]},
    "home depot":   {"income": (50_000, 130_000), "sqft": 105_000, "format": "home_improvement",    "position": "mid_range", "cat": ["hardware", "home_goods"]},
    "lowe's":       {"income": (50_000, 130_000), "sqft": 112_000, "format": "home_improvement",    "position": "mid_range", "cat": ["hardware", "home_goods"]},
    "tj maxx":      {"income": (40_000, 110_000), "sqft": 30_000,  "format": "off_price_apparel",   "position": "budget",    "cat": ["apparel", "home_goods"]},
    "burlington":   {"income": (35_000,  95_000), "sqft": 45_000,  "format": "off_price_apparel",   "position": "budget",    "cat": ["apparel", "home_goods"]},
    "five below":   {"income": (30_000,  85_000), "sqft": 10_000,  "format": "dollar_store",        "position": "budget",    "cat": ["general_merchandise"]},
    "bj's wholesale":{"income": (60_000,150_000), "sqft": 115_000, "format": "warehouse_club",      "position": "mid_range", "cat": ["grocery", "general_merchandise"]},
    "sam's club":   {"income": (55_000, 140_000), "sqft": 134_000, "format": "warehouse_club",      "position": "mid_range", "cat": ["grocery", "general_merchandise"]},
    "lidl":         {"income": (30_000,  75_000), "sqft": 22_000,  "format": "limited_assortment",  "position": "budget",    "cat": ["grocery"]},
    "fresh thyme":  {"income": (55_000, 130_000), "sqft": 28_000,  "format": "natural_grocery",     "position": "mid_range", "cat": ["grocery", "specialty"]},
    "meijer":       {"income": (40_000, 100_000), "sqft": 200_000, "format": "supercenter",         "position": "mid_range", "cat": ["general_merchandise", "grocery"]},
    "cub foods":    {"income": (40_000,  95_000), "sqft": 65_000,  "format": "full_grocery",        "position": "mid_range", "cat": ["grocery"]},
    "hy-vee":       {"income": (45_000, 115_000), "sqft": 90_000,  "format": "full_grocery",        "position": "mid_range", "cat": ["grocery"]},
}


def _build_from_custom(retailer: RetailerProfile) -> BrandDNA:
    """Build BrandDNA deterministically from custom store spec."""
    size = retailer.store_size or StoreSizeEnum.MEDIUM
    positioning = retailer.price_positioning or PricePositioning.MID_RANGE
    categories = [c.value for c in (retailer.categories or [])] or ["general_merchandise"]

    income_low, income_high = INCOME_MAP[positioning]
    sqft = FOOTPRINT_MAP[size]

    category_display = " & ".join(c.replace("_", " ").title() for c in categories)
    format_str = f"{size.value.replace('_', ' ').title()} {positioning.value.replace('_', ' ').title()} {category_display}"

    return BrandDNA(
        display_name=f"Custom {format_str} Store",
        ideal_income_low=income_low,
        ideal_income_high=income_high,
        ideal_population_min=_min_pop_for_size(size),
        footprint_sqft=sqft,
        primary_categories=categories,
        price_positioning=positioning.value,
        store_format=format_str.lower().replace(" ", "_"),
        family_skew="grocery" in categories or "general_merchandise" in categories,
        college_edu_skew=positioning == PricePositioning.PREMIUM,
        known_brand=False,
        expansion_velocity="selective",
        reasoning=(
            f"Custom {positioning.value.replace('_', ' ')} {category_display.lower()} store "
            f"({sqft:,} sq ft). Target household income ${income_low:,}–${income_high:,}."
        ),
    )


def _min_pop_for_size(size: StoreSizeEnum) -> int:
    return {StoreSizeEnum.SMALL: 5000, StoreSizeEnum.MEDIUM: 25000,
            StoreSizeEnum.LARGE: 75000, StoreSizeEnum.BIG_BOX: 150000}[size]


def _build_from_lookup(brand_name: str) -> Optional[BrandDNA]:
    """Check quick-lookup dictionary first before calling Gemini."""
    key = brand_name.lower().strip()
    if key in KNOWN_BRANDS:
        b = KNOWN_BRANDS[key]
        return BrandDNA(
            display_name=brand_name.title(),
            ideal_income_low=b["income"][0],
            ideal_income_high=b["income"][1],
            ideal_population_min=50_000,
            footprint_sqft=b["sqft"],
            primary_categories=b["cat"],
            price_positioning=b["position"],
            store_format=b["format"],
            family_skew="grocery" in b["cat"] or "general_merchandise" in b["cat"],
            college_edu_skew=b["position"] == "premium",
            known_brand=True,
            expansion_velocity="moderate",
            reasoning=f"{brand_name.title()} is a recognized national retail brand with established market positioning.",
        )
    return None


async def _openai_resolve(brand_name: str) -> BrandDNA:
    """Use OpenAI GPT-4o-mini to resolve unknown brand DNA."""
    if not settings.openai_api_key:
        raise ValueError("No OpenAI API key")

    prompt = f"""You are a retail industry expert. Analyze the retail brand "{brand_name}" and return a JSON object with this exact schema:

{{
  "display_name": "{brand_name}",
  "ideal_income_low": <annual household income $ lower bound for typical customer>,
  "ideal_income_high": <annual household income $ upper bound>,
  "ideal_population_min": <minimum trade area population needed for viability>,
  "footprint_sqft": <typical store size in sq ft>,
  "primary_categories": [<list of: grocery, liquor, apparel, electronics, general_merchandise, hardware, pharmacy, specialty, restaurant, home_goods, sporting_goods, pet_supplies>],
  "price_positioning": <"budget" | "mid_range" | "premium">,
  "store_format": <brief format descriptor like "discount_grocery" or "warehouse_club">,
  "family_skew": <true if typically attracts families>,
  "college_edu_skew": <true if college-educated customers over-indexed>,
  "known_brand": true,
  "expansion_velocity": <"rapid" | "moderate" | "selective">,
  "reasoning": "<1-2 sentence brand positioning summary>"
}}

If "{brand_name}" is not a real known retail brand, make a best-effort estimation based on the name.
Return ONLY the JSON object, no markdown."""

    def _call() -> BrandDNA:
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        data = json.loads(resp.choices[0].message.content)
        return BrandDNA(**data)

    return await asyncio.get_event_loop().run_in_executor(None, _call)


async def run_brand_resolver_agent(
    retailer: RetailerProfile,
) -> AsyncGenerator[dict, None]:
    """
    Phase 0 agent — resolves any RetailerProfile into a BrandDNA.
    Fastest possible path: lookup dict → Gemini → custom synthesizer.
    """
    display = retailer.display_name()

    yield {
        "agent": "brand_resolver",
        "status": "running",
        "message": f"🔍 Resolving brand DNA for: {display}",
    }

    brand_dna: BrandDNA

    # Path A: known brand
    if retailer.brand_name:
        # 1. Quick lookup
        brand_dna = _build_from_lookup(retailer.brand_name)

        if brand_dna is None:
            yield {"agent": "brand_resolver", "status": "running",
                   "message": f"Brand '{retailer.brand_name}' not in quick-lookup, querying OpenAI..."}
            try:
                budget = float(get_settings().analysis_brand_resolver_openai_timeout_seconds)
                budget = max(6.0, min(budget, 90.0))
                brand_dna = await asyncio.wait_for(
                    _openai_resolve(retailer.brand_name),
                    timeout=budget,
                )
                yield {"agent": "brand_resolver", "status": "running",
                       "message": f"✓ OpenAI resolved: {brand_dna.store_format} | ${brand_dna.ideal_income_low:,}–${brand_dna.ideal_income_high:,} income target"}
            except Exception as e:
                # Final fallback — treat as mid_range general merchandise
                yield {"agent": "brand_resolver", "status": "running",
                       "message": f"⚠ OpenAI unavailable ({e}) — using generic brand profile"}
                brand_dna = BrandDNA(
                    display_name=retailer.brand_name.title(),
                    ideal_income_low=45_000, ideal_income_high=110_000,
                    ideal_population_min=50_000, footprint_sqft=30_000,
                    primary_categories=["general_merchandise"],
                    price_positioning="mid_range", store_format="general_retail",
                    family_skew=True, college_edu_skew=False,
                    known_brand=True, expansion_velocity="moderate",
                    reasoning=f"{retailer.brand_name.title()} — brand intelligence unavailable, using general retail baseline.",
                )
        else:
            yield {"agent": "brand_resolver", "status": "running",
                   "message": f"✓ Found in brand library: {brand_dna.store_format} | {brand_dna.price_positioning}"}

    # Path B: custom store
    else:
        yield {"agent": "brand_resolver", "status": "running",
               "message": "⚙️ Synthesizing DNA from custom store specifications..."}
        brand_dna = _build_from_custom(retailer)
        yield {"agent": "brand_resolver", "status": "running",
               "message": f"✓ Custom profile: {brand_dna.footprint_sqft:,} sq ft | ${brand_dna.ideal_income_low:,}–${brand_dna.ideal_income_high:,} | {brand_dna.store_format}"}

    yield {
        "agent": "brand_resolver",
        "status": "done",
        "message": f"✅ Brand DNA resolved → {brand_dna.display_name} ({brand_dna.price_positioning}, {brand_dna.store_format})",
        "data": brand_dna.model_dump(),
    }
