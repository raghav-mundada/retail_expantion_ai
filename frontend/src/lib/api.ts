// ────────────────────────────────────────────────────────────
// Backend API client — talks to FastAPI on :8000
// ────────────────────────────────────────────────────────────

const BASE = "http://localhost:8000";

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
