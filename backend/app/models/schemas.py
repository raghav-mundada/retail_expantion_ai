from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class Brand(str, Enum):
    WALMART = "walmart"
    TARGET = "target"


class AnalyzeRequest(BaseModel):
    lat: float = Field(..., ge=24.0, le=50.0, description="Latitude of candidate site")
    lng: float = Field(..., ge=-125.0, le=-65.0, description="Longitude of candidate site")
    brand: Brand = Brand.WALMART
    radius_miles: float = Field(10.0, ge=1.0, le=25.0)


class DemographicsProfile(BaseModel):
    population: int
    median_income: float
    household_count: int
    avg_household_size: float
    owner_occupied_pct: float
    family_households_pct: float
    median_age: float
    college_educated_pct: float
    population_growth_est: float  # % annual est
    demand_score: float  # 0–100


class CompetitorStore(BaseModel):
    brand_name: str
    lat: float
    lng: float
    distance_miles: float
    store_type: str
    osm_id: Optional[str] = None


class CompetitorProfile(BaseModel):
    stores: list[CompetitorStore]
    total_count: int
    big_box_count: int
    saturation_score: float   # 0–100 (100 = very saturated)
    demand_signal_score: float  # 0–100 (presence = demand)
    competition_score: float   # 0–100 (100 = best competitive position = low saturation but high demand)
    underserved: bool


class NeighborhoodProfile(BaseModel):
    school_quality_index: float   # 0–100
    family_density_score: float   # 0–100
    neighborhood_stability: float # 0–100
    housing_growth_signal: float  # proxy
    overall_score: float          # 0–100


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
    market_share_6mo: float    # %
    market_share_24mo: float   # %
    word_of_mouth_score: float # 0–100
    cannibalization_risk: float # 0–100
    confidence_interval_low: float
    confidence_interval_high: float


class BrandFitProfile(BaseModel):
    brand: str
    fit_score: float             # 0–100
    recommended_format: str
    income_alignment: float      # 0–100
    density_alignment: float     # 0–100
    reasoning: str


class LocationScore(BaseModel):
    total_score: float           # 0–100
    demand_score: float
    competition_score: float
    accessibility_score: float
    neighborhood_score: float
    brand_fit_score: float
    risk_score: float
    rank_label: str              # "Excellent" | "Good" | "Fair" | "Poor"
    why_this_wins: list[str]
    top_risks: list[str]


class AnalysisResult(BaseModel):
    lat: float
    lng: float
    brand: str
    address_label: str
    demographics: DemographicsProfile
    competitors: CompetitorProfile
    neighborhood: NeighborhoodProfile
    simulation: SimulationResult
    brand_fit: BrandFitProfile
    score: LocationScore
    agent_trace: list[dict]


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
    status: str   # "running" | "done" | "error"
    message: str
    data: Optional[dict] = None
