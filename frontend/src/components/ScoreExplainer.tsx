"use client";
import { useState } from "react";
import type { AnalysisResult } from "@/lib/api";

/* ─────────────────────────────────────────────────
   Helpers
───────────────────────────────────────────────── */
function toTen(score: number) {
  return Math.round(score / 10);
}

function quality(score: number): { label: string; color: string; bg: string } {
  if (score >= 80) return { label: "Excellent", color: "#10b981", bg: "rgba(16,185,129,0.08)" };
  if (score >= 65) return { label: "Good",      color: "#3b82f6", bg: "rgba(59,130,246,0.08)" };
  if (score >= 45) return { label: "Moderate",  color: "#f59e0b", bg: "rgba(245,158,11,0.08)" };
  if (score >= 25) return { label: "Poor",      color: "#ef4444", bg: "rgba(239,68,68,0.08)" };
  return              { label: "Critical",  color: "#dc2626", bg: "rgba(220,38,38,0.12)" };
}

function Bar({ score }: { score: number }) {
  const q = quality(score);
  return (
    <div style={{ marginTop: 6, background: "rgba(255,255,255,0.05)", borderRadius: 4, height: 5, overflow: "hidden" }}>
      <div style={{ width: `${score}%`, height: "100%", background: q.color, borderRadius: 4, transition: "width 0.5s ease" }} />
    </div>
  );
}

function RatingPill({ score }: { score: number }) {
  const q = quality(score);
  return (
    <span style={{
      background: q.bg, color: q.color,
      border: `1px solid ${q.color}33`,
      borderRadius: 20, padding: "2px 10px",
      fontSize: 11, fontWeight: 700,
      whiteSpace: "nowrap",
    }}>
      {toTen(score)}/10 · {q.label}
    </span>
  );
}

function MetricRow({
  icon, label, score, dataPoints, what, why,
}: {
  icon: string;
  label: string;
  score: number;
  dataPoints: string[];
  what: string;
  why: string;
}) {
  const [open, setOpen] = useState(false);
  const q = quality(score);

  return (
    <div style={{
      background: "rgba(255,255,255,0.02)",
      border: `1px solid ${open ? q.color + "33" : "rgba(255,255,255,0.06)"}`,
      borderRadius: 10,
      overflow: "hidden",
      transition: "border-color 0.2s",
    }}>
      {/* Row header — always visible */}
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%", display: "flex", alignItems: "center",
          gap: 10, padding: "10px 14px",
          background: "transparent", border: "none",
          cursor: "pointer", textAlign: "left",
        }}
      >
        <span style={{ fontSize: 16, lineHeight: 1 }}>{icon}</span>
        <span style={{ flex: 1, fontSize: 13, fontWeight: 600, color: "#e5e7eb" }}>{label}</span>
        <RatingPill score={score} />
        <span style={{ fontSize: 11, color: "#4b5563", marginLeft: 6, transition: "transform 0.2s", transform: open ? "rotate(180deg)" : "rotate(0deg)" }}>▾</span>
      </button>

      {/* Score bar always shown */}
      <div style={{ padding: "0 14px 8px" }}>
        <Bar score={score} />
      </div>

      {/* Expanded detail */}
      {open && (
        <div style={{
          padding: "0 14px 14px", borderTop: "1px solid rgba(255,255,255,0.05)",
          marginTop: 0, paddingTop: 12,
          display: "flex", flexDirection: "column", gap: 10,
        }}>
          {/* What this measures */}
          <div style={{
            background: "rgba(99,102,241,0.06)", border: "1px solid rgba(99,102,241,0.15)",
            borderRadius: 8, padding: "8px 12px",
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#818cf8", letterSpacing: "0.08em", marginBottom: 4 }}>
              WHAT WE MEASURE
            </div>
            <div style={{ fontSize: 12, color: "#d1d5db", lineHeight: 1.6 }}>{what}</div>
          </div>

          {/* Why this score */}
          <div style={{
            background: `${q.bg}`, border: `1px solid ${q.color}22`,
            borderRadius: 8, padding: "8px 12px",
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: q.color, letterSpacing: "0.08em", marginBottom: 4 }}>
              WHY THIS SCORE
            </div>
            <div style={{ fontSize: 12, color: "#d1d5db", lineHeight: 1.6 }}>{why}</div>
          </div>

          {/* Data points */}
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#4b5563", letterSpacing: "0.08em", marginBottom: 6 }}>
              DATA INPUTS
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {dataPoints.map((dp, i) => (
                <span key={i} style={{
                  background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)",
                  borderRadius: 6, padding: "3px 9px", fontSize: 11, color: "#9ca3af",
                }}>
                  {dp}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────
   Main Component
───────────────────────────────────────────────── */
export default function ScoreExplainer({ result }: { result: AnalysisResult }) {
  const [open, setOpen] = useState(false);
  const { score, demographics, competitors, neighborhood, brand_fit, hotspot } = result;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const simulation = result.simulation as any;

  // Build metric explanations from live data
  const metrics = [
    {
      icon: "📊",
      label: "Market Demand",
      score: score.demand_score,
      what: "Measures how much genuine consumer demand exists in this trade area — population density, household income, family composition, and historical retail spending patterns.",
      why: (() => {
        const pop = demographics?.population ?? 0;
        const income = demographics?.median_income ?? 0;
        const fam = demographics?.family_households_pct ?? 0;
        const demand = demographics?.demand_score ?? score.demand_score;
        return `Trade area has ${(pop / 1000).toFixed(0)}k residents with $${(income / 1000).toFixed(0)}k median income and ${fam.toFixed(0)}% family households. Raw demand index: ${demand.toFixed(0)}/100. ${
          score.demand_score >= 65
            ? "Population density and income levels are sufficient to sustain a superstore."
            : "Area may be underpopulated or income levels below threshold for high-volume retail."
        }`;
      })(),
      dataPoints: [
        `Pop: ${((demographics?.population ?? 0) / 1000).toFixed(0)}k`,
        `Income: $${((demographics?.median_income ?? 0) / 1000).toFixed(0)}k`,
        `Families: ${(demographics?.family_households_pct ?? 0).toFixed(0)}%`,
        `Age: ${demographics?.median_age ?? "N/A"}`,
        "Source: Census ACS 5-Year",
      ],
    },
    {
      icon: "🏪",
      label: "Competitive Position",
      score: score.competition_score,
      what: "Evaluates the balance between competitor presence (proof of demand) and market saturation. Ideal: competitors exist (demand proven) but not wall-to-wall (room to capture share).",
      why: (() => {
        const total = competitors?.total_count ?? 0;
        const bigBox = competitors?.big_box_count ?? 0;
        const sat = competitors?.saturation_score ?? 50;
        const demand = competitors?.demand_signal_score ?? 50;
        return `Found ${total} competitor stores (${bigBox} big-box). Saturation score: ${sat.toFixed(0)}/100. Demand signal: ${demand.toFixed(0)}/100. ${
          sat > 60 ? "High saturation — you'd be entering a crowded market." :
          total === 0 ? "No competitors detected — could mean untapped opportunity or thin demand." :
          "Healthy competitor mix signals proven demand without being oversaturated."
        }`;
      })(),
      dataPoints: [
        `${competitors?.total_count ?? 0} stores found`,
        `${competitors?.big_box_count ?? 0} big-box`,
        `Saturation: ${(competitors?.saturation_score ?? 0).toFixed(0)}/100`,
        `Demand signal: ${(competitors?.demand_signal_score ?? 0).toFixed(0)}/100`,
        "Source: OpenStreetMap Overpass",
      ],
    },
    {
      icon: "🌐",
      label: "Accessibility",
      score: score.accessibility_score,
      what: "How easy is it for customers to reach this location? Considers road network density, highway proximity, transit access, and whether the site is in a high-traffic corridor.",
      why: `Accessibility score of ${score.accessibility_score.toFixed(0)}/100. ${
        score.accessibility_score >= 70
          ? "Location is in a well-connected area with strong road access and predictable traffic flow."
          : score.accessibility_score >= 50
          ? "Moderate accessibility — reachable but may lack major arterial or highway frontage."
          : "Limited access may constrain customer draw radius."
      } Higher scores = more drive-by traffic capture potential.`,
      dataPoints: [
        "Road network density",
        "Highway proximity",
        "Transit access",
        "Drive-time isochrones",
        "Source: OSM + scoring engine",
      ],
    },
    {
      icon: "🏘️",
      label: "Neighborhood Quality",
      score: score.neighborhood_score,
      what: "Composite of school district quality, household stability, homeownership rate, and housing growth signals. High-quality neighborhoods drive basket size and repeat visits.",
      why: (() => {
        const sq = neighborhood?.school_quality_index ?? 0;
        const stab = neighborhood?.neighborhood_stability ?? 0;
        const grow = neighborhood?.housing_growth_signal ?? 0;
        return `School quality: ${sq.toFixed(0)}/100. Neighborhood stability: ${stab.toFixed(0)}/100. Housing growth signal: ${grow.toFixed(0)}/100. ${
          score.neighborhood_score >= 70
            ? "Stable, growing neighborhood — strong repeat customer base likely."
            : "Area shows mixed signals — check whether new development is incoming or decline is occurring."
        }`;
      })(),
      dataPoints: [
        `School index: ${(neighborhood?.school_quality_index ?? 0).toFixed(0)}/100`,
        `Stability: ${(neighborhood?.neighborhood_stability ?? 0).toFixed(0)}/100`,
        `Housing growth: ${(neighborhood?.housing_growth_signal ?? 0).toFixed(0)}/100`,
        `Family density: ${(neighborhood?.family_density_score ?? 0).toFixed(0)}/100`,
        "Source: NCES + Census",
      ],
    },
    {
      icon: "🎯",
      label: "Brand Fit",
      score: score.brand_fit_score,
      what: "How well does the local demographic profile match this retailer's target customer? Compares income alignment, family composition, age distribution, and education level against the brand's known customer profile.",
      why: (() => {
        const incomeAlign = brand_fit?.income_alignment ?? 0;
        const densityAlign = brand_fit?.density_alignment ?? 0;
        return `Income alignment: ${incomeAlign.toFixed(0)}/100. Density alignment: ${densityAlign.toFixed(0)}/100. ${
          brand_fit?.reasoning ?? "Alignment computed against brand demographic profile."
        }`;
      })(),
      dataPoints: [
        `Income match: ${(brand_fit?.income_alignment ?? 0).toFixed(0)}/100`,
        `Density match: ${(brand_fit?.density_alignment ?? 0).toFixed(0)}/100`,
        `Format: ${brand_fit?.recommended_format ?? "Standard"}`,
        `Brand: ${brand_fit?.brand ?? result.brand}`,
        "Source: Gemini BrandDNA + Census",
      ],
    },
    {
      icon: "⚠️",
      label: "Risk Profile",
      score: score.risk_score,
      what: "Inverted risk score — higher = LOWER risk. Factors: market saturation, economic volatility of the area, dependency on a single employer or industry, and new competitor threat signals.",
      why: `Risk score: ${score.risk_score.toFixed(0)}/100 (100 = zero risk, 0 = extreme risk). ${
        score.risk_score >= 70
          ? "Low-risk profile — diversified local economy, moderate competition, stable demographics."
          : score.risk_score >= 45
          ? "Moderate risk — some concentration or saturation concerns worth monitoring."
          : "Elevated risk detected — saturation, economic fragility, or fast competitor movement in this area."
      }`,
      dataPoints: [
        `Saturation: ${(competitors?.saturation_score ?? 0).toFixed(0)}/100`,
        `Competitors: ${competitors?.total_count ?? 0}`,
        "Economic diversity proxy",
        "New entrant threat signal",
        "Source: Composite model",
      ],
    },
    {
      icon: "🔥",
      label: "Hotspot Signal (TinyFish)",
      score: score.hotspot_score ?? 55,
      what: "Live retail momentum score from TinyFish AI — detects where demand is EMERGING NOW via new store openings, Yelp activity, commercial permit filings, and available retail spaces. Not historical — current.",
      why: (() => {
        const hs = hotspot;
        if (!hs) return "TinyFish agent running in fallback mode — live scraping unavailable. Score estimated from OSM density.";
        return `${hs.new_openings_count ?? 0} new store openings detected. ${hs.loopnet_active_listings ?? 0} commercial spaces available. Permit activity: ${(hs.permit_activity_score ?? 0).toFixed(0)}/100. ${hs.narrative ?? ""}`;
      })(),
      dataPoints: [
        `New openings: ${hotspot?.new_openings_count ?? "N/A"}`,
        `Available spaces: ${hotspot?.loopnet_active_listings ?? "N/A"}`,
        `Permit score: ${(hotspot?.permit_activity_score ?? 0).toFixed(0)}/100`,
        `Trending: ${(hotspot?.trending_categories ?? ["—"]).slice(0, 2).join(", ")}`,
        `Powered: ${hotspot?.tinyfish_powered ? "TinyFish live ✓" : "Fallback proxy"}`,
      ],
    },
    {
      icon: "🏗️",
      label: "Amenity Infrastructure",
      score: score.amenity_score ?? 65,
      what: "Quality of supporting infrastructure near the site: road access, parking availability, fiber/broadband connectivity, proximity to logistics routes, and co-tenant anchor stores.",
      why: `Amenity score: ${(score.amenity_score ?? 65).toFixed(0)}/100. ${
        (score.amenity_score ?? 65) >= 70
          ? "Strong infrastructure — good road access, available parking, well-connected area."
          : "Infrastructure gaps detected — may require investment in access roads or parking before viability is maximized."
      }`,
      dataPoints: [
        "Road & highway access",
        "Parking capacity proxy",
        "Broadband connectivity",
        "Logistics proximity",
        "Source: OSM + FCC broadband",
      ],
    },
  ];

  const rankLabel = score.rank_label;
  const rankColor = score.total_score >= 75 ? "#10b981" : score.total_score >= 55 ? "#f59e0b" : "#ef4444";

  // Strongest and weakest dimensions for summary
  const sorted = [...metrics].sort((a, b) => b.score - a.score);
  const topThree = sorted.slice(0, 3);
  const bottomTwo = sorted.slice(-2);

  return (
    <div style={{ marginTop: 12 }}>
      {/* Trigger button */}
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: "100%",
          display: "flex", alignItems: "center", gap: 10,
          padding: "11px 14px",
          background: open ? "rgba(99,102,241,0.08)" : "rgba(255,255,255,0.03)",
          border: `1px solid ${open ? "rgba(99,102,241,0.30)" : "rgba(255,255,255,0.08)"}`,
          borderRadius: 10,
          cursor: "pointer",
          transition: "all 0.2s",
        }}
      >
        <span style={{ fontSize: 15 }}>🔬</span>
        <div style={{ flex: 1, textAlign: "left" }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#e5e7eb" }}>
            Score Explanation
          </div>
          <div style={{ fontSize: 11, color: "#4b5563" }}>
            {open ? "Hide" : "Show"} how each metric was scored and why
          </div>
        </div>
        <span style={{
          fontSize: 11, color: "#818cf8", fontWeight: 600,
          background: "rgba(99,102,241,0.1)", border: "1px solid rgba(99,102,241,0.2)",
          borderRadius: 6, padding: "3px 9px",
        }}>
          {open ? "Collapse ▲" : "Expand ▼"}
        </span>
      </button>

      {/* Expanded panel */}
      {open && (
        <div style={{
          marginTop: 8,
          border: "1px solid rgba(99,102,241,0.15)",
          borderRadius: 12,
          overflow: "hidden",
          background: "rgba(8,10,18,0.7)",
        }}>
          {/* Summary header */}
          <div style={{
            padding: "16px 16px 12px",
            borderBottom: "1px solid rgba(255,255,255,0.06)",
            background: "rgba(99,102,241,0.05)",
          }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#818cf8", letterSpacing: "0.06em", marginBottom: 8 }}>
              OVERALL VERDICT
            </div>
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <span style={{
                fontSize: 28, fontWeight: 900, color: rankColor,
                lineHeight: 1, fontVariantNumeric: "tabular-nums",
              }}>
                {score.total_score.toFixed(0)}
              </span>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: rankColor }}>{rankLabel}</div>
                <div style={{ fontSize: 11, color: "#6b7280" }}>8-dimension composite score</div>
              </div>
            </div>

            {/* Quick strengths / risks */}
            <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <div style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.15)", borderRadius: 8, padding: "8px 10px" }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#10b981", marginBottom: 5, letterSpacing: "0.06em" }}>STRENGTHS</div>
                {topThree.map((m) => (
                  <div key={m.label} style={{ fontSize: 11, color: "#d1d5db", marginBottom: 2 }}>
                    {m.icon} {m.label} — <span style={{ color: "#10b981" }}>{m.score.toFixed(0)}/100</span>
                  </div>
                ))}
              </div>
              <div style={{ background: "rgba(239,68,68,0.04)", border: "1px solid rgba(239,68,68,0.15)", borderRadius: 8, padding: "8px 10px" }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: "#ef4444", marginBottom: 5, letterSpacing: "0.06em" }}>WATCH</div>
                {bottomTwo.map((m) => (
                  <div key={m.label} style={{ fontSize: 11, color: "#d1d5db", marginBottom: 2 }}>
                    {m.icon} {m.label} — <span style={{ color: "#ef4444" }}>{m.score.toFixed(0)}/100</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Simulation summary */}
            {simulation && (
              <div style={{ marginTop: 10, display: "flex", gap: 12, flexWrap: "wrap" }}>
                <span style={{ fontSize: 11, color: "#6b7280" }}>
                  📈 Projected revenue: <strong style={{ color: "#e5e7eb" }}>
                    ${(simulation.predicted_annual_revenue_usd / 1e6).toFixed(1)}M/yr
                  </strong>
                </span>
                <span style={{ fontSize: 11, color: "#6b7280" }}>
                  📅 Predicted market share (6mo): <strong style={{ color: "#e5e7eb" }}>
                    {(simulation.market_share_6mo ?? 0).toFixed(1)}%
                  </strong>
                </span>
                <span style={{ fontSize: 11, color: "#6b7280" }}>
                  📊 Word-of-mouth: <strong style={{ color: "#e5e7eb" }}>
                    {(simulation.word_of_mouth_score ?? 0).toFixed(0)}/100
                  </strong>
                </span>
              </div>
            )}
          </div>

          {/* Per-metric rows */}
          <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#374151", letterSpacing: "0.08em", marginBottom: 2 }}>
              CLICK ANY METRIC TO SEE DETAILED EXPLANATION
            </div>
            {metrics.map((m) => (
              <MetricRow key={m.label} {...m} />
            ))}
          </div>

          {/* Why/risks from score object */}
          {(score.why_this_wins?.length > 0 || score.top_risks?.length > 0) && (
            <div style={{ padding: "0 12px 14px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              {score.why_this_wins?.length > 0 && (
                <div style={{ background: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.12)", borderRadius: 8, padding: "10px 12px" }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: "#10b981", marginBottom: 6, letterSpacing: "0.06em" }}>AI REASONING — WHY IT WINS</div>
                  {score.why_this_wins.map((w, i) => (
                    <div key={i} style={{ fontSize: 11, color: "#d1d5db", marginBottom: 4, display: "flex", gap: 6 }}>
                      <span style={{ color: "#10b981" }}>✓</span><span>{w}</span>
                    </div>
                  ))}
                </div>
              )}
              {score.top_risks?.length > 0 && (
                <div style={{ background: "rgba(239,68,68,0.04)", border: "1px solid rgba(239,68,68,0.12)", borderRadius: 8, padding: "10px 12px" }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: "#ef4444", marginBottom: 6, letterSpacing: "0.06em" }}>AI REASONING — TOP RISKS</div>
                  {score.top_risks.map((r, i) => (
                    <div key={i} style={{ fontSize: 11, color: "#d1d5db", marginBottom: 4, display: "flex", gap: 6 }}>
                      <span style={{ color: "#ef4444" }}>⚠</span><span>{r}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
