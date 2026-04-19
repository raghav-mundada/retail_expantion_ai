"use client";
import { useState } from "react";
import type { AnalysisResult } from "@/lib/api";

/* ── helpers ───────────────────────────────────────────────── */
function pct(n: number | null | undefined, total = 100) {
  if (n == null) return "N/A";
  return `${((n / total) * 100).toFixed(1)}%`;
}
function fmt(n: number | null | undefined, prefix = "", suffix = "") {
  if (n == null) return "N/A";
  return `${prefix}${n.toLocaleString()}${suffix}`;
}
function score(n: number | null | undefined) {
  if (n == null) return "N/A";
  const v = Math.round(n);
  const color = v >= 75 ? "#10b981" : v >= 50 ? "#f59e0b" : "#ef4444";
  return <span style={{ color, fontWeight: 700 }}>{v}/100</span>;
}

/* ── shared layout primitives ──────────────────────────────── */
function Section({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 8, marginBottom: 10,
        paddingBottom: 6, borderBottom: "1px solid rgba(255,255,255,0.08)",
      }}>
        <span style={{ fontSize: 16 }}>{icon}</span>
        <span style={{ fontSize: 12, fontWeight: 800, color: "#818cf8", letterSpacing: "0.08em" }}>
          {title}
        </span>
      </div>
      {children}
    </div>
  );
}

function Grid({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: 8 }}>
      {children}
    </div>
  );
}

function Metric({
  label, value, sub, raw,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  raw?: string;
}) {
  return (
    <div style={{
      background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)",
      borderRadius: 10, padding: "10px 12px",
    }}>
      <div style={{ fontSize: 10, color: "#4b5563", marginBottom: 4, fontWeight: 600, letterSpacing: "0.04em" }}>
        {label}
      </div>
      <div style={{ fontSize: 16, fontWeight: 800, color: "#e5e7eb" }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: "#6b7280", marginTop: 2 }}>{sub}</div>}
      {raw && <div style={{ fontSize: 9, color: "#374151", marginTop: 3, fontFamily: "monospace" }}>{raw}</div>}
    </div>
  );
}

function Bar({ value, color = "#6366f1" }: { value: number; color?: string }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.06)", borderRadius: 4, height: 5, marginTop: 6, overflow: "hidden" }}>
      <div style={{ width: `${Math.min(value, 100)}%`, height: "100%", background: color, borderRadius: 4, transition: "width 0.4s ease" }} />
    </div>
  );
}

/* ── TABS ──────────────────────────────────────────────────── */
const TABS = ["Demographics", "Competitors", "Neighborhood", "Hotspot", "Scores", "Simulation"] as const;
type Tab = typeof TABS[number];

/* ── MAIN ──────────────────────────────────────────────────── */
export default function MetricsModal({
  result,
  onClose,
}: {
  result: AnalysisResult;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<Tab>("Demographics");
  const { demographics: d, competitors: c, neighborhood: n, hotspot: hs, score: s, simulation: sim, brand_fit: bf } = result;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const simAny = sim as any;

  return (
    // Backdrop
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 9999,
        background: "rgba(0,0,0,0.75)", backdropFilter: "blur(6px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 20,
      }}
    >
      {/* Modal */}
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(880px, 100%)", maxHeight: "88vh",
          background: "linear-gradient(160deg, #0d0f1a 0%, #0a0c17 100%)",
          border: "1px solid rgba(99,102,241,0.25)",
          borderRadius: 18, overflow: "hidden",
          display: "flex", flexDirection: "column",
          boxShadow: "0 24px 80px rgba(0,0,0,0.7)",
        }}
      >
        {/* Header */}
        <div style={{
          padding: "18px 22px 14px",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
          background: "rgba(99,102,241,0.05)",
          flexShrink: 0,
        }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontSize: 16, fontWeight: 800, color: "#e5e7eb" }}>
                📊 Full Metrics Report
              </div>
              <div style={{ fontSize: 11, color: "#6b7280", marginTop: 3 }}>
                {result.address_label} · {result.brand} · raw API data + score translations
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              {/* Final score badge */}
              <div style={{
                background: s.total_score >= 75 ? "rgba(16,185,129,0.12)" : s.total_score >= 55 ? "rgba(245,158,11,0.12)" : "rgba(239,68,68,0.12)",
                border: `1px solid ${s.total_score >= 75 ? "#10b981" : s.total_score >= 55 ? "#f59e0b" : "#ef4444"}44`,
                borderRadius: 10, padding: "6px 14px", textAlign: "center",
              }}>
                <div style={{ fontSize: 22, fontWeight: 900, color: s.total_score >= 75 ? "#10b981" : s.total_score >= 55 ? "#f59e0b" : "#ef4444", lineHeight: 1 }}>
                  {s.total_score.toFixed(0)}
                </div>
                <div style={{ fontSize: 9, color: "#6b7280", marginTop: 1 }}>{s.rank_label}</div>
              </div>
              <button
                onClick={onClose}
                style={{
                  background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: 8, color: "#9ca3af", fontSize: 18, width: 34, height: 34,
                  cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
                }}
              >
                ×
              </button>
            </div>
          </div>

          {/* Tab bar */}
          <div style={{ display: "flex", gap: 4, marginTop: 14, flexWrap: "wrap" }}>
            {TABS.map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                style={{
                  padding: "5px 13px", borderRadius: 8, fontSize: 12, fontWeight: 600,
                  border: "1px solid",
                  cursor: "pointer",
                  background: tab === t ? "rgba(99,102,241,0.18)" : "rgba(255,255,255,0.03)",
                  borderColor: tab === t ? "rgba(99,102,241,0.4)" : "rgba(255,255,255,0.07)",
                  color: tab === t ? "#a5b4fc" : "#6b7280",
                  transition: "all 0.15s",
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Scrollable body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "18px 22px" }}>

          {/* ── DEMOGRAPHICS ── */}
          {tab === "Demographics" && (
            <>
              <Section title="CENSUS ACS 5-YEAR — TRADE AREA AGGREGATE" icon="📊">
                <Grid>
                  <Metric label="Total Population" value={fmt(d.population)} sub="Within analysis radius" raw="Source: Census ACS B01003" />
                  <Metric label="Median HH Income" value={`$${((d.median_income ?? 0) / 1000).toFixed(0)}k`} sub="Annual" raw="Census ACS B19013" />
                  <Metric label="Household Count" value={fmt(d.household_count)} raw="Census ACS B11001" />
                  <Metric label="Avg HH Size" value={`${d.avg_household_size ?? "N/A"} persons`} raw="Census ACS B25010" />
                  <Metric label="Owner Occupied" value={`${(d.owner_occupied_pct ?? 0).toFixed(1)}%`} sub="Of housing units" raw="Census ACS B25003" />
                  <Metric label="Family HHs" value={`${(d.family_households_pct ?? 0).toFixed(1)}%`} sub="Of all households" raw="Census ACS B11001" />
                  <Metric label="Median Age" value={`${d.median_age ?? "N/A"} yrs`} raw="Census ACS B01002" />
                  <Metric label="College Educated" value={`${(d.college_educated_pct ?? 0).toFixed(1)}%`} sub="Bachelor's + above" raw="Census ACS B15003" />
                  <Metric label="Pop Growth Est." value={`+${(d.population_growth_est ?? 0).toFixed(1)}%/yr`} sub="Estimated annual" />
                </Grid>
              </Section>

              <Section title="DEMAND SCORE TRANSLATION" icon="🔢">
                <div style={{ marginBottom: 10, fontSize: 12, color: "#9ca3af", lineHeight: 1.7 }}>
                  Raw census data is converted into a 0–100 demand index via:
                  <br />
                  <span style={{ color: "#6366f1" }}>Population component</span> (40pts): population ÷ 50k cap →{" "}
                  <strong style={{ color: "#e5e7eb" }}>{Math.min((d.population ?? 0) / 50000, 1).toFixed(2)} × 40 = {(Math.min((d.population ?? 0) / 50000, 1) * 40).toFixed(1)}pts</strong>
                  <br />
                  <span style={{ color: "#6366f1" }}>Income component</span> (30pts): income ÷ $75k →{" "}
                  <strong style={{ color: "#e5e7eb" }}>{Math.min((d.median_income ?? 0) / 75000, 1.5).toFixed(2)} × 30 = {(Math.min((d.median_income ?? 0) / 75000, 1.5) * 30).toFixed(1)}pts</strong>
                  <br />
                  <span style={{ color: "#6366f1" }}>Growth component</span> (14pts fixed neutral baseline)
                  <br />
                  <span style={{ color: "#6366f1" }}>Education component</span> (10pts): college% ÷ 50% →{" "}
                  <strong style={{ color: "#e5e7eb" }}>{(Math.min((d.college_educated_pct ?? 0) / 50, 1) * 10).toFixed(1)}pts</strong>
                </div>
                <Grid>
                  <Metric label="Raw Demand Index" value={score(d.demand_score)} sub="From census data" />
                  <Metric label="Final Demand Score" value={score(s.demand_score)} sub="After weighting" />
                </Grid>
                <Bar value={s.demand_score} color="#6366f1" />
              </Section>
            </>
          )}

          {/* ── COMPETITORS ── */}
          {tab === "Competitors" && (
            <>
              <Section title="OPENSTREETMAP OVERPASS — DETECTED STORES" icon="🏪">
                <Grid>
                  <Metric label="Total Stores Found" value={fmt(c.total_count)} raw="OSM query radius match" />
                  <Metric label="Big-Box Count" value={fmt(c.big_box_count)} sub="Walmart/Target/Costco etc." />
                  <Metric label="Same-Category" value={fmt(c.same_category_count ?? null)} sub="Direct competitors" />
                  <Metric label="Saturation Score" value={score(c.saturation_score)} sub="Higher = more crowded" />
                  <Metric label="Demand Signal" value={score(c.demand_signal_score)} sub="Presence = proven demand" />
                  <Metric label="Underserved?" value={c.underserved ? "✅ Yes" : "❌ No"} />
                </Grid>
              </Section>

              <Section title="COMPETITION SCORE TRANSLATION" icon="🔢">
                <div style={{ fontSize: 12, color: "#9ca3af", lineHeight: 1.7, marginBottom: 10 }}>
                  Competition score balances two signals:
                  <br />· <span style={{ color: "#6366f1" }}>Saturation penalty</span>: high saturation → lower score
                  <br />· <span style={{ color: "#6366f1" }}>Demand signal bonus</span>: competitor presence = customers exist
                  <br />· Formula: <strong style={{ color: "#e5e7eb" }}>demand_signal × 0.55 + (100 − saturation) × 0.45</strong>
                </div>
                <Grid>
                  <Metric label="Saturation" value={score(c.saturation_score)} />
                  <Metric label="Demand Signal" value={score(c.demand_signal_score)} />
                  <Metric label="Final Competition Score" value={score(s.competition_score)} sub="Weighted composite" />
                </Grid>
                <Bar value={s.competition_score} color="#3b82f6" />
              </Section>

              {c.stores?.length > 0 && (
                <Section title="INDIVIDUAL STORES DETECTED" icon="📍">
                  <div style={{ display: "flex", flexDirection: "column", gap: 5, maxHeight: 200, overflowY: "auto" }}>
                    {c.stores.slice(0, 20).map((store, i) => (
                      <div key={i} style={{
                        display: "flex", justifyContent: "space-between", alignItems: "center",
                        padding: "6px 10px", background: "rgba(255,255,255,0.02)",
                        border: "1px solid rgba(255,255,255,0.05)", borderRadius: 7, fontSize: 11, color: "#9ca3af",
                      }}>
                        <span>{store.name || store.brand_name || "Unknown"}</span>
                        <span style={{ color: "#4b5563", fontFamily: "monospace", fontSize: 10 }}>
                          {store.lat?.toFixed(4)}, {store.lng?.toFixed(4)}
                        </span>
                      </div>
                    ))}
                  </div>
                </Section>
              )}
            </>
          )}

          {/* ── NEIGHBORHOOD ── */}
          {tab === "Neighborhood" && (
            <>
              <Section title="NEIGHBORHOOD PROFILE — NCES + CENSUS DERIVED" icon="🏘️">
                <Grid>
                  <Metric label="School Quality Index" value={score(n.school_quality_index)} sub="NCES district data" />
                  <Metric label="Family Density Score" value={score(n.family_density_score)} sub="Families/sq mile proxy" />
                  <Metric label="Neighborhood Stability" value={score(n.neighborhood_stability)} sub="Homeownership + tenure" />
                  <Metric label="Housing Growth Signal" value={score(n.housing_growth_signal)} sub="Permit + construction" />
                  <Metric label="Overall Neighborhood" value={score(n.overall_score)} sub="Composite" />
                </Grid>
              </Section>

              <Section title="SCORE TRANSLATION" icon="🔢">
                <div style={{ fontSize: 12, color: "#9ca3af", lineHeight: 1.7, marginBottom: 10 }}>
                  Neighborhood score weights: school quality (40%) + family density (25%) + stability (20%) + housing growth (15%)
                </div>
                <Grid>
                  <Metric label="Final Neighborhood Score" value={score(s.neighborhood_score)} />
                  <Metric label="Brand Fit Score" value={score(s.brand_fit_score)} sub={bf?.recommended_format} />
                  <Metric label="Income Alignment" value={score(bf?.income_alignment)} />
                  <Metric label="Density Alignment" value={score(bf?.density_alignment)} />
                </Grid>
                <Bar value={s.neighborhood_score} color="#8b5cf6" />
              </Section>

              {bf?.reasoning && (
                <Section title="BRAND FIT AI REASONING" icon="🎯">
                  <div style={{ fontSize: 12, color: "#d1d5db", lineHeight: 1.7, background: "rgba(99,102,241,0.05)", border: "1px solid rgba(99,102,241,0.15)", borderRadius: 8, padding: "10px 12px" }}>
                    {bf.reasoning}
                  </div>
                </Section>
              )}
            </>
          )}

          {/* ── HOTSPOT ── */}
          {tab === "Hotspot" && (
            <>
              {hs ? (
                <>
                  <Section title={`TINYFISH AI — ${hs.tinyfish_powered ? "LIVE SCRAPING ✓" : "PROXY MODE"}`} icon="🔥">
                    <Grid>
                      <Metric label="Hotspot Score" value={score(hs.hotspot_score)} />
                      <Metric label="New Openings Detected" value={fmt(hs.new_openings_count)} sub="Yelp + news signals" />
                      <Metric label="Available Spaces" value={fmt(hs.loopnet_active_listings)} sub="Loopnet active listings" />
                      <Metric label="Permit Activity" value={score(hs.permit_activity_score)} sub="Commercial permit index" />
                    </Grid>
                  </Section>

                  {hs.trending_categories?.length > 0 && (
                    <Section title="TRENDING CATEGORIES" icon="📈">
                      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                        {hs.trending_categories.map((c, i) => (
                          <span key={i} style={{
                            background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)",
                            borderRadius: 8, padding: "4px 12px", fontSize: 12, color: "#fca5a5",
                          }}>{c}</span>
                        ))}
                      </div>
                    </Section>
                  )}

                  {hs.signals?.length > 0 && (
                    <Section title="RAW SIGNALS" icon="📡">
                      <div style={{ display: "flex", flexDirection: "column", gap: 5, maxHeight: 250, overflowY: "auto" }}>
                        {hs.signals.slice(0, 15).map((sig, i) => (
                          <div key={i} style={{
                            padding: "8px 12px", background: "rgba(255,255,255,0.02)",
                            border: "1px solid rgba(255,255,255,0.05)", borderRadius: 8,
                            display: "grid", gridTemplateColumns: "1fr auto", gap: 8,
                          }}>
                            <div>
                              <div style={{ fontSize: 12, color: "#e5e7eb", fontWeight: 600 }}>{sig.title}</div>
                              <div style={{ fontSize: 10, color: "#4b5563", marginTop: 2 }}>
                                {sig.source} · {sig.recency_days}d ago · sentiment: {sig.sentiment}
                              </div>
                            </div>
                            <div style={{ textAlign: "right" }}>
                              <div style={{ fontSize: 11, color: "#6366f1", fontWeight: 700 }}>
                                {(sig.signal_strength * 100).toFixed(0)}%
                              </div>
                              <div style={{ fontSize: 9, color: "#374151" }}>strength</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </Section>
                  )}

                  {hs.narrative && (
                    <Section title="HOTSPOT NARRATIVE" icon="💬">
                      <div style={{ fontSize: 12, color: "#d1d5db", lineHeight: 1.7, background: "rgba(239,68,68,0.04)", border: "1px solid rgba(239,68,68,0.12)", borderRadius: 8, padding: "10px 12px" }}>
                        {hs.narrative}
                      </div>
                    </Section>
                  )}
                </>
              ) : (
                <div style={{ textAlign: "center", color: "#4b5563", padding: "40px 0", fontSize: 13 }}>
                  🔥 TinyFish agent ran in fallback mode — no live signal data available.<br />
                  Set TINYFISH_API_KEY in backend/.env to enable live scraping.
                </div>
              )}
            </>
          )}

          {/* ── SCORES ── */}
          {tab === "Scores" && (
            <>
              <Section title="8-DIMENSION COMPOSITE SCORE — RAW BREAKDOWN" icon="🏆">
                {[
                  { label: "Market Demand", value: s.demand_score, color: "#6366f1", note: "Population × Income × Education" },
                  { label: "Competitive Position", value: s.competition_score, color: "#3b82f6", note: "Demand signal vs saturation balance" },
                  { label: "Accessibility", value: s.accessibility_score, color: "#06b6d4", note: "Road network + transit proximity" },
                  { label: "Neighborhood Quality", value: s.neighborhood_score, color: "#8b5cf6", note: "Schools + stability + housing growth" },
                  { label: "Brand Fit", value: s.brand_fit_score, color: "#ec4899", note: `Income alignment + density match (${bf?.brand ?? result.brand})` },
                  { label: "Risk Profile", value: s.risk_score, color: "#f59e0b", note: "Inverted: higher = lower risk" },
                  { label: "Hotspot Signal", value: s.hotspot_score ?? 55, color: "#ef4444", note: "TinyFish live retail momentum" },
                  { label: "Amenity Infrastructure", value: s.amenity_score ?? 65, color: "#10b981", note: "Power + broadband + zoning" },
                ].map(({ label, value, color, note }) => (
                  <div key={label} style={{ marginBottom: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                      <div>
                        <span style={{ fontSize: 12, fontWeight: 600, color: "#e5e7eb" }}>{label}</span>
                        <span style={{ fontSize: 10, color: "#4b5563", marginLeft: 8 }}>{note}</span>
                      </div>
                      <span style={{ fontSize: 14, fontWeight: 800, color }}>{Math.round(value)}/100</span>
                    </div>
                    <Bar value={value} color={color} />
                  </div>
                ))}
              </Section>

              <Section title="WEIGHTS APPLIED" icon="⚖️">
                <div style={{ fontSize: 11, color: "#6b7280", lineHeight: 2, fontFamily: "monospace", background: "rgba(255,255,255,0.02)", borderRadius: 8, padding: "10px 14px" }}>
                  Demand: 20% · Competition: 20% · Accessibility: 10%<br />
                  Neighborhood: 15% · Brand Fit: 15% · Risk: 10%<br />
                  Hotspot: 5% · Amenity: 5%
                </div>
              </Section>

              {s.why_this_wins?.length > 0 && (
                <Section title="AI REASONING — WHY IT WINS" icon="✅">
                  {s.why_this_wins.map((w, i) => (
                    <div key={i} style={{ fontSize: 12, color: "#d1d5db", marginBottom: 5, display: "flex", gap: 8 }}>
                      <span style={{ color: "#10b981" }}>✓</span><span>{w}</span>
                    </div>
                  ))}
                </Section>
              )}

              {s.top_risks?.length > 0 && (
                <Section title="TOP RISKS" icon="⚠️">
                  {s.top_risks.map((r, i) => (
                    <div key={i} style={{ fontSize: 12, color: "#d1d5db", marginBottom: 5, display: "flex", gap: 8 }}>
                      <span style={{ color: "#ef4444" }}>⚠</span><span>{r}</span>
                    </div>
                  ))}
                </Section>
              )}
            </>
          )}

          {/* ── SIMULATION ── */}
          {tab === "Simulation" && (
            <>
              <Section title="AGENT-BASED MARKET SIMULATION (GEMINI)" icon="🧪">
                <Grid>
                  <Metric label="Simulated Households" value={fmt(simAny.simulated_households)} sub="In agent population" />
                  <Metric label="Will Visit (%)" value={`${((simAny.pct_will_visit ?? 0) * 100).toFixed(1)}%`} sub="Of simulated HHs" />
                  <Metric label="Predicted Monthly Visits" value={fmt(simAny.predicted_monthly_visits)} />
                  <Metric label="Annual Revenue Est." value={`$${((simAny.predicted_annual_revenue_usd ?? 0) / 1e6).toFixed(2)}M`} sub="Best estimate" />
                  <Metric label="Revenue CI Low" value={`$${((simAny.confidence_interval_low ?? 0) / 1e6).toFixed(2)}M`} sub="90% CI lower" />
                  <Metric label="Revenue CI High" value={`$${((simAny.confidence_interval_high ?? 0) / 1e6).toFixed(2)}M`} sub="90% CI upper" />
                  <Metric label="Market Share (6mo)" value={`${((simAny.market_share_6mo ?? 0)).toFixed(1)}%`} />
                  <Metric label="Market Share (24mo)" value={`${((simAny.market_share_24mo ?? 0)).toFixed(1)}%`} />
                  <Metric label="Word of Mouth" value={score(simAny.word_of_mouth_score)} sub="Virality proxy" />
                  <Metric label="Cannibalization Risk" value={`${((simAny.cannibalization_risk ?? 0) * 100).toFixed(1)}%`} sub="Own-store overlap" />
                </Grid>
              </Section>
            </>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: "10px 22px", borderTop: "1px solid rgba(255,255,255,0.06)",
          background: "rgba(0,0,0,0.3)", flexShrink: 0,
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <span style={{ fontSize: 10, color: "#374151" }}>
            Sources: Census ACS 5-Year · OpenStreetMap Overpass · TinyFish AI · Gemini · OSM + FCC
          </span>
          <button
            onClick={onClose}
            style={{
              background: "rgba(99,102,241,0.15)", border: "1px solid rgba(99,102,241,0.3)",
              borderRadius: 8, color: "#818cf8", fontSize: 12, fontWeight: 600,
              padding: "6px 16px", cursor: "pointer",
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
