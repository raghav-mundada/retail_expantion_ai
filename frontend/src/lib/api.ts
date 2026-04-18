// API client for RetailIQ backend

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export interface AnalyzeRequest {
  lat: number;
  lng: number;
  brand: "walmart" | "target";
  radius_miles?: number;
}

export interface CompetitorStore {
  brand_name: string;
  lat: number;
  lng: number;
  distance_miles: number;
  store_type: string;
  osm_id?: string;
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

export interface CompetitorProfile {
  stores: CompetitorStore[];
  total_count: number;
  big_box_count: number;
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
  rank_label: string;
  why_this_wins: string[];
  top_risks: string[];
}

export interface AnalysisResult {
  lat: number;
  lng: number;
  brand: string;
  address_label: string;
  demographics: DemographicsProfile;
  competitors: CompetitorProfile;
  neighborhood: NeighborhoodProfile;
  simulation: SimulationResult;
  brand_fit: BrandFitProfile;
  score: LocationScore;
  agent_trace: Record<string, unknown>[];
}

export interface CandidateSite {
  id: string;
  name: string;
  lat: number;
  lng: number;
  description: string;
  acreage: number;
  zoning_type: string;
}

export interface TraceEvent {
  agent: string;
  status: "running" | "done" | "error" | "complete";
  message: string;
  data?: Record<string, unknown>;
}

export async function getCandidates(): Promise<CandidateSite[]> {
  const res = await fetch(`${API_BASE}/candidates`);
  const data = await res.json();
  return data.candidates;
}

export async function getCompetitors(
  lat: number,
  lng: number,
  radius: number = 25
): Promise<CompetitorStore[]> {
  const res = await fetch(
    `${API_BASE}/competitors?lat=${lat}&lng=${lng}&radius=${radius}`
  );
  const data = await res.json();
  return data.stores || [];
}

export function streamAnalysis(
  request: AnalyzeRequest,
  onEvent: (event: TraceEvent) => void,
  onResult: (result: AnalysisResult) => void,
  onError: (err: string) => void,
  onDone: () => void
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${API_BASE}/analyze/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal: controller.signal,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const raw = line.slice(6).trim();
            if (raw === "[DONE]") {
              onDone();
              return;
            }
            try {
              const event: TraceEvent = JSON.parse(raw);
              onEvent(event);
              if (event.status === "complete" && event.data) {
                onResult(event.data as unknown as AnalysisResult);
              }
            } catch {
              // skip malformed
            }
          }
        }
      }
      onDone();
    } catch (err: unknown) {
      if ((err as Error).name !== "AbortError") {
        onError(String(err));
      }
    }
  })();

  return () => controller.abort();
}
