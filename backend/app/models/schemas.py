"""
RetailIQ — Pydantic Data Models (v2)

Supports:
- Universal retailer input (known brand OR custom store spec)
- TinyFish-powered hotspot signals
- Business amenity / infrastructure profiling
- All original demographic, competitor, simulation, scoring models
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


# ──────────────────────────────────────────────
# Retailer Input — Universal (replaces Brand enum)
# ──────────────────────────────────────────────

class StoreSizeEnum(str, Enum):
    SMALL = "small"          # < 5,000 sq ft  (convenience, liquor, pharmacy)
    MEDIUM = "medium"        # 5,000–25,000 sq ft  (specialty, mid-format grocery)
    LARGE = "large"          # 25,000–80,000 sq ft  (department, full grocery)
    BIG_BOX = "big_box"      # 80,000+ sq ft  (Walmart, Target, Costco)


class ProductCategory(str, Enum):
    GROCERY = "grocery"
    LIQUOR = "liquor"
    APPAREL = "apparel"
    ELECTRONICS = "electronics"
    GENERAL_MERCHANDISE = "general_merchandise"
    HARDWARE = "hardware"
    PHARMACY = "pharmacy"
    SPECIALTY = "specialty"
    RESTAURANT = "restaurant"
    HOME_GOODS = "home_goods"
    SPORTING_GOODS = "sporting_goods"
    PET_SUPPLIES = "pet_supplies"


class PricePositioning(str, Enum):
    BUDGET = "budget"
    MID_RANGE = "mid_range"
    PREMIUM = "premium"


class RetailerProfile(BaseModel):
    """
    Two-path retailer definition:
      Path A: known brand → brand_name = "Costco" (Gemini resolves DNA)
      Path B: custom spec → store_size + categories + price_positioning
    At least one of brand_name OR (store_size + categories) must be provided.
    """
    # Path A — Known brand
    brand_name: Optional[str] = Field(
        None,
        description='Known retail brand, e.g. "Costco", "Aldi", "Trader Joe\'s", "H-Mart"'
    )

    # Path B — Custom store specification
    store_size: Optional[StoreSizeEnum] = None
    categories: Optional[List[ProductCategory]] = None
    price_positioning: Optional[PricePositioning] = PricePositioning.MID_RANGE

    def display_name(self) -> str:
        if self.brand_name:
            return self.brand_name.title()
        cats = ", ".join(c.value.replace("_", " ").title() for c in (self.categories or []))
        size = (self.store_size or StoreSizeEnum.MEDIUM).value.replace("_", " ").title()
        pos = (self.price_positioning or PricePositioning.MID_RANGE).value.replace("_", " ").title()
        return f"Custom {size} {pos} {cats} Store"


class BrandDNA(BaseModel):
    """Resolved brand positioning — output of BrandResolverAgent."""
    display_name: str
    ideal_income_low: float          # USD household income
    ideal_income_high: float
    ideal_population_min: int        # trade area minimum pop
    footprint_sqft: int              # typical store sq ft
    primary_categories: List[str]
    price_positioning: str           # "budget" | "mid_range" | "premium"
    store_format: str                # "supercenter" | "urban" | "warehouse" | etc.
    family_skew: bool                # True = skews toward families
    college_edu_skew: bool           # True = skews toward college-educated
    known_brand: bool                # True = recognized national/regional brand
    expansion_velocity: str         # "rapid" | "moderate" | "selective"
    reasoning: str                   # 1–2 sentence Gemini narrative


class AnalyzeRequest(BaseModel):
    lat: float = Field(..., ge=24.0, le=50.0, description="Latitude of candidate site")
    lng: float = Field(..., ge=-125.0, le=-65.0, description="Longitude of candidate site")
    retailer: RetailerProfile
    radius_miles: float = Field(10.0, ge=1.0, le=25.0)
    region_city: str = Field("Phoenix, AZ", description="City context for TinyFish searches")


# ──────────────────────────────────────────────
# Demographics
# ──────────────────────────────────────────────

class DemographicsProfile(BaseModel):
    population: int
    median_income: float
    household_count: int
    avg_household_size: float
    owner_occupied_pct: float
    family_households_pct: float
    median_age: float
    college_educated_pct: float
    population_growth_est: float   # % annual est
    demand_score: float            # 0–100


# ──────────────────────────────────────────────
# Competitors
# ──────────────────────────────────────────────

class CompetitorStore(BaseModel):
    brand_name: str
    lat: float
    lng: float
    distance_miles: float
    store_type: str
    osm_id: Optional[str] = None


class CompetitorProfile(BaseModel):
    stores: List[CompetitorStore]
    total_count: int
    big_box_count: int
    same_category_count: int = 0      # competitors in same product category
    saturation_score: float           # 0–100 (100 = very saturated)
    demand_signal_score: float        # 0–100 (presence = demand signal)
    competition_score: float          # 0–100 (100 = best competitive position)
    underserved: bool


# ──────────────────────────────────────────────
# Neighborhood & Schools
# ──────────────────────────────────────────────

class SchoolPoint(BaseModel):
    name: str
    lat: float
    lng: float
    type: str = "school"   # "school" | "college" | "university"
    level: Optional[str] = None


class GrowthCorridor(BaseModel):
    name: str
    lat: float
    lng: float
    kind: str = "residential"   # "residential" | "commercial"


class NeighborhoodProfile(BaseModel):
    school_quality_index: float     # 0–100
    family_density_score: float     # 0–100
    neighborhood_stability: float   # 0–100
    housing_growth_signal: float    # proxy
    overall_score: float            # 0–100
    district_name: Optional[str] = None
    schools:           List[SchoolPoint]    = Field(default_factory=list)
    growth_corridors:  List[GrowthCorridor] = Field(default_factory=list)


# ──────────────────────────────────────────────
# TinyFish Hotspot (Layer 1)
# ──────────────────────────────────────────────

class RetailSignal(BaseModel):
    """A single live retail momentum signal gathered by TinyFish."""
    source: str              # "yelp_new" | "news" | "permit" | "loopnet" | "search"
    title: str
    signal_strength: float   # 0.0–1.0  (1.0 = strongest positive signal)
    category: Optional[str] = None
    url: Optional[str] = None
    recency_days: int = 90   # how many days ago this signal was detected
    sentiment: str = "positive"  # "positive" | "neutral" | "negative"


class HotspotProfile(BaseModel):
    """
    TinyFish-powered live retail momentum intelligence.
    Covers: new openings, permit activity, trending categories, available commercial spaces.
    """
    hotspot_score: float                # 0–100 composite
    signals: List[RetailSignal]
    trending_categories: List[str]      # e.g. ["grocery", "fitness", "fast_casual"]
    new_openings_count: int             # businesses opened in past 90 days in trade area
    permit_activity_score: float        # 0–100
    loopnet_active_listings: int        # available commercial development spaces
    narrative: str                      # 1-sentence Gemini or fallback summary
    tinyfish_powered: bool = False      # False = fallback mode (no API key)


# ──────────────────────────────────────────────
# Business Amenity / Infrastructure
# ──────────────────────────────────────────────

class AmenityProfile(BaseModel):
    """
    Physical + infrastructure site suitability assessment.
    Sources: OSM (free), FCC Broadband API (free), Loopnet via TinyFish (optional).
    """
    power_infrastructure_score: float   # 0–100  (substations within 2mi)
    water_sewer_score: float            # 0–100  (OSM utility nodes)
    internet_reliability_score: float   # 0–100  (FCC ≥100Mbps %)
    available_commercial_spaces: int    # Loopnet listings count near site
    zoning_compatibility_score: float   # 0–100  (OSM landuse=commercial/retail coverage)
    development_activity_score: float   # 0–100  (under-construction OSM + permit proxy)
    overall_amenity_score: float        # 0–100 weighted composite
    available_space_types: List[str]    # ["lease", "build_to_suit", "purchase"]
    tinyfish_powered: bool = False


# ──────────────────────────────────────────────
# Market Simulation
# ──────────────────────────────────────────────

class HouseholdAgentResult(BaseModel):
    typology: str
    income_bracket: str
    shopping_frequency_per_month: float
    brand_preference: str
    will_visit_new_store: bool
    monthly_spend_estimate: float
    word_of_mouth_influence: float


class SimulationResult(BaseModel):
    simulated_households: int
    pct_will_visit: float
    predicted_monthly_visits: int
    predicted_annual_revenue_usd: float
    market_share_6mo: float
    market_share_24mo: float
    word_of_mouth_score: float
    cannibalization_risk: float
    confidence_interval_low: float
    confidence_interval_high: float


# ──────────────────────────────────────────────
# Brand Fit (universal)
# ──────────────────────────────────────────────

class BrandFitProfile(BaseModel):
    brand: str
    fit_score: float
    recommended_format: str
    income_alignment: float
    density_alignment: float
    reasoning: str


# ──────────────────────────────────────────────
# Composite Score (8 dimensions now)
# ──────────────────────────────────────────────

class LocationScore(BaseModel):
    total_score: float
    demand_score: float
    competition_score: float
    accessibility_score: float
    neighborhood_score: float
    brand_fit_score: float
    risk_score: float
    hotspot_score: float         # NEW — TinyFish live signal
    amenity_score: float         # NEW — infrastructure
    rank_label: str
    why_this_wins: List[str]
    top_risks: List[str]


# ──────────────────────────────────────────────
# Full Analysis Result
# ──────────────────────────────────────────────

class AnalysisResult(BaseModel):
    lat: float
    lng: float
    brand: str                   # display name resolved from retailer
    address_label: str
    retailer_profile: Optional[RetailerProfile] = None
    brand_dna: Optional[BrandDNA] = None
    demographics: DemographicsProfile
    competitors: CompetitorProfile
    neighborhood: NeighborhoodProfile
    hotspot: Optional[HotspotProfile] = None   # TinyFish Layer 1
    amenity: Optional[AmenityProfile] = None   # Infrastructure
    simulation: Optional[SimulationResult] = None   # on-demand — user clicks "Run AI Simulation"
    brand_fit: BrandFitProfile
    score: LocationScore
    agent_trace: List[dict]


# ──────────────────────────────────────────────
# Candidate Site
# ──────────────────────────────────────────────

class CandidateSite(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    description: str
    acreage: float
    zoning_type: str


class AgentTraceEvent(BaseModel):
    agent: str
    status: str    # "running" | "done" | "error" | "complete"
    message: str
    data: Optional[dict] = None
