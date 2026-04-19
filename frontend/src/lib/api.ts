// ────────────────────────────────────────────────────────────
// Backend API client — talks to FastAPI on :8000
// ────────────────────────────────────────────────────────────

const BASE = "http://localhost:8000";

// ── Legacy v1 types (debate/run endpoints) ────────────────────────────────────

export interface AnalyzeResponse {
  run_id: string;
  fetched_at: string;
  cached: boolean;
  summary: {
    demographics: {
      tract_count: number;
      total_population: number;
      total_households: number;
      median_hh_income_area_avg: number;
      avg_poverty_rate: number;
      avg_owner_share: number;
      avg_renter_share: number;
    };
    stores_count: number;
    parcels_count: number;
    schools_count: number;
    traffic: {
      count: number;
      nearest_road: string;
      nearest_aadt: number;
      max_aadt: number;
      avg_aadt: number;
    };
    neighborhoods: number;
  };
}

export interface ScoreContribution {
  dimension: string;
  weight: number;
  raw_score: number;
  contribution: number;
  rationale: string;
}

export interface FormulaDoc {
  id: string;
  name: string;
  formula: string;
  purpose: string;
}

export interface DebateResponse {
  session_id: string;
  run_id: string;
  store_format: string;
  metrics: any;
  composite_score: number;
  score_breakdown: ScoreContribution[];
  weights: Record<string, number>;
  formulas: FormulaDoc[];
  bull: string;
  bear: string;
  verdict: {
    score: number;
    recommendation: string;
    confidence: string;
    summary: string;
    deciding_factors: { factor: string; direction: string; evidence: string }[];
    key_risks: string[];
    key_strengths: string[];
  };
}

// ── v2 types (8-agent pipeline) ───────────────────────────────────────────────

export type StoreSizeEnum = "small" | "medium" | "large" | "big_box";
export type PricePositioning = "budget" | "mid_range" | "premium";

export interface RetailerProfile {
  brand_name?: string;
  store_size?: StoreSizeEnum;
  categories?: string[];
  price_positioning?: PricePositioning;
}

export interface RetailSignal {
  source: string;
  title: string;
  signal_strength: number;
  category?: string;
  url?: string;
  recency_days: number;
  sentiment: string;
}

export interface HotspotProfile {
  hotspot_score: number;
  signals: RetailSignal[];
  trending_categories: string[];
  new_openings_count: number;
  permit_activity_score: number;
  loopnet_active_listings: number;
  narrative: string;
  tinyfish_powered: boolean;
}

export interface AmenityProfile {
  power_infrastructure_score: number;
  water_sewer_score: number;
  internet_reliability_score: number;
  available_commercial_spaces: number;
  zoning_compatibility_score: number;
  development_activity_score: number;
  overall_amenity_score: number;
  available_space_types: string[];
  tinyfish_powered: boolean;
}

export interface DemographicsProfile {
  population: number;
  median_income: number;
  household_count: number;
  avg_household_size: number;
  owner_occupied_pct: number;
  family_households_pct: number;
  median_age: number;
  college_educated_pct: number;
  population_growth_est: number;
  demand_score: number;
}

export interface CompetitorStore {
  brand_name: string;
  lat: number;
  lng: number;
  distance_miles: number;
  store_type: string;
}

export interface CompetitorProfile {
  stores: CompetitorStore[];
  total_count: number;
  big_box_count: number;
  same_category_count: number;
  saturation_score: number;
  demand_signal_score: number;
  competition_score: number;
  underserved: boolean;
}

export interface NeighborhoodProfile {
  school_quality_index: number;
  family_density_score: number;
  neighborhood_stability: number;
  housing_growth_signal: number;
  overall_score: number;
}

export interface SimulationResult {
  simulated_households: number;
  pct_will_visit: number;
  predicted_monthly_visits: number;
  predicted_annual_revenue_usd: number;
  market_share_6mo: number;
  market_share_24mo: number;
  word_of_mouth_score: number;
  cannibalization_risk: number;
  confidence_interval_low: number;
  confidence_interval_high: number;
}

export interface BrandFitProfile {
  brand: string;
  fit_score: number;
  recommended_format: string;
  income_alignment: number;
  density_alignment: number;
  reasoning: string;
}

export interface LocationScore {
  total_score: number;
  demand_score: number;
  competition_score: number;
  accessibility_score: number;
  neighborhood_score: number;
  brand_fit_score: number;
  risk_score: number;
  hotspot_score: number;
  amenity_score: number;
  rank_label: string;
  why_this_wins: string[];
  top_risks: string[];
}

export interface AnalysisResultV2 {
  lat: number;
  lng: number;
  brand: string;
  address_label: string;
  demographics: DemographicsProfile;
  competitors: CompetitorProfile;
  neighborhood: NeighborhoodProfile;
  hotspot?: HotspotProfile;
  amenity?: AmenityProfile;
  simulation: SimulationResult;
  brand_fit: BrandFitProfile;
  score: LocationScore;
  agent_trace: { agent: string; status: string; message: string; data?: any }[];
}

export interface AnalyzeV2Request {
  lat: number;
  lng: number;
  retailer: RetailerProfile;
  radius_miles?: number;
  region_city?: string;
}

// ── v2 API functions ───────────────────────────────────────────────────────────

export async function analyzeV2(req: AnalyzeV2Request): Promise<AnalysisResultV2> {
  const res = await fetch(`${BASE}/api/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...req, radius_miles: req.radius_miles ?? 10.0 }),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

export async function getKnownBrands(): Promise<{ brands: any[]; categories: string[]; sizes: string[]; positioning: string[] }> {
  const res = await fetch(`${BASE}/api/brands`);
  return res.json();
}

// ── Legacy v1 functions (kept for backward compatibility) ─────────────────────

export async function analyze(lat: number, lon: number, radius_km: number): Promise<AnalyzeResponse> {
  const res = await fetch(`${BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lon, radius_km }),
  });
  if (!res.ok) throw new Error(`Analyze failed: ${res.status}`);
  return res.json();
}

export async function getRun(run_id: string): Promise<any> {
  const res = await fetch(`${BASE}/runs/${run_id}`);
  if (!res.ok) throw new Error(`Get run failed: ${res.status}`);
  return res.json();
}

export async function getCompetitors(run_id: string, max_dist_km?: number): Promise<any> {
  const url = max_dist_km
    ? `${BASE}/runs/${run_id}/competitors?max_dist_km=${max_dist_km}`
    : `${BASE}/runs/${run_id}/competitors`;
  const res = await fetch(url);
  return res.json();
}

export async function getDemographics(run_id: string): Promise<any> {
  const res = await fetch(`${BASE}/runs/${run_id}/demographics`);
  return res.json();
}

export async function getTraffic(run_id: string): Promise<any> {
  const res = await fetch(`${BASE}/runs/${run_id}/traffic`);
  return res.json();
}

export async function getSchools(run_id: string): Promise<any> {
  const res = await fetch(`${BASE}/runs/${run_id}/schools`);
  return res.json();
}

export async function getNeighborhoods(run_id: string): Promise<any> {
  const res = await fetch(`${BASE}/runs/${run_id}/neighborhoods`);
  return res.json();
}

export async function getParcels(run_id: string, retail_only = true): Promise<any> {
  const res = await fetch(`${BASE}/runs/${run_id}/parcels?retail_only=${retail_only}`);
  return res.json();
}

export async function startDebate(run_id: string, store_format = "Target"): Promise<DebateResponse> {
  const res = await fetch(`${BASE}/runs/${run_id}/debate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ store_format }),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}
